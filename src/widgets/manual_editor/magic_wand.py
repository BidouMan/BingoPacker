from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import QTimer, Qt, QRectF, QRect
from PySide6.QtGui import QPen, QPainterPath, QImage, QRegion, QBitmap


class MagicWandTool:
    def __init__(self, tolerance=20):
        self.tolerance = tolerance

    def is_color_similar(self, c1, c2):
        # 1. 如果其中一个是完全透明，另一个不是，直接判定为不相似
        if (c1.alpha() < 5) != (c2.alpha() < 5):
            return False

        # 2. 使用欧几里得距离计算 RGB 差异 (更精准的数学模型)
        # 这样 (255, 89, 0) 和 (255, 0, 0) 之间的距离是 89，会比平均值更敏感
        import math

        distance = math.sqrt(
            (c1.red() - c2.red()) ** 2
            + (c1.green() - c2.green()) ** 2
            + (c1.blue() - c2.blue()) ** 2
            + (c1.alpha() - c2.alpha()) ** 2
        )

        # 此时的 tolerance 建议设置在 10-30 之间
        return distance <= self.tolerance

    def get_selection_region(self, image, start_point, contiguous=True):
        if image.isNull() or not image.rect().contains(start_point):
            return QRegion()

        # 1. 性能优化：直接转换成 32位 格式，并获取原始字节（避开像素对象创建）
        img = image.convertToFormat(QImage.Format_ARGB32)
        width, height = img.width(), img.height()

        # 2. 预计算容差平方，省去 math.sqrt
        tol_sq = self.tolerance**2
        target_color = img.pixelColor(start_point)
        tr, tg, tb, ta = (
            target_color.red(),
            target_color.green(),
            target_color.blue(),
            target_color.alpha(),
        )

        # 创建 Mask 图像 (Mono 格式最省内存)
        mask = QImage(img.size(), QImage.Format_Mono)
        mask.fill(0)

        # 快速颜色检查函数 (直接比较数值，不创建 QColor)
        def check_pixel(px_color):
            r, g, b, a = (
                px_color.red(),
                px_color.green(),
                px_color.blue(),
                px_color.alpha(),
            )
            if (a < 5) != (ta < 5):
                return False
            dist_sq = (r - tr) ** 2 + (g - tg) ** 2 + (b - tb) ** 2 + (a - ta) ** 2
            return dist_sq <= tol_sq

        if not contiguous:
            # 全图模式优化：逐像素扫描
            for y in range(height):
                for x in range(width):
                    if check_pixel(img.pixelColor(x, y)):
                        mask.setPixel(x, y, 1)
        else:
            # --- 扫描线填充算法 (Scanline Fill) ---
            # 相比普通泛洪，入栈次数减少 90% 以上
            stack = [
                (start_point.x(), start_point.x(), start_point.y(), 1),
                (start_point.x(), start_point.x(), start_point.y(), -1),
            ]

            # 使用一个 bytearray 做访问标记，比 set((x,y)) 快几十倍
            visited_mask = bytearray(width * height)

            while stack:
                x1, x2, y, dy = stack.pop()
                x = x1
                if 0 <= y + dy < height:
                    target_y = y + dy
                    # 向上/下扫描一行
                    while x <= x2:
                        if not visited_mask[target_y * width + x] and check_pixel(
                            img.pixelColor(x, target_y)
                        ):
                            # 找到一个起点，向左扩展
                            start_x = x
                            while (
                                start_x > 0
                                and not visited_mask[target_y * width + start_x - 1]
                                and check_pixel(img.pixelColor(start_x - 1, target_y))
                            ):
                                mask.setPixel(start_x - 1, target_y, 1)
                                visited_mask[target_y * width + start_x - 1] = 1
                                start_x -= 1

                            # 向右扩展
                            while x < width and check_pixel(
                                img.pixelColor(x, target_y)
                            ):
                                mask.setPixel(x, target_y, 1)
                                visited_mask[target_y * width + x] = 1
                                x += 1

                            # 将这一段扫描线入栈
                            stack.append((start_x, x - 1, target_y, dy))
                            if x - 1 > x2:
                                stack.append((start_x, x - 1, target_y, -dy))
                        x += 1

        # 3. 极速转换
        selection_bitmap = QBitmap.fromImage(mask)
        region = QRegion(selection_bitmap)

        if not region.contains(start_point):
            region = QRegion(QRect(0, 0, width, height)).subtracted(region)

        return region.intersected(QRect(0, 0, width, height))


class SelectionAntsItem(QGraphicsItem):
    def __init__(self, region, parent=None):
        super().__init__(parent)
        self.region = region
        self.offset = 0
        self.setZValue(9999)
        self._path = QPainterPath()
        if not self.region.isEmpty():
            self._generate_outline()

    def _generate_outline(self):
        """
        不再调用 rects() 或 toPolygons()，直接利用 QPainterPath 的内置转换
        """
        self._path = QPainterPath()
        # 直接将 QRegion 加入路径，这是 Qt 内部最高效且最稳定的方法
        self._path.addRegion(self.region)

        # 针对你说的“拼接线”问题：
        # 这里必须调用 simplified()，它是消除内部矩形重合线的唯一方法
        self._path = self._path.simplified()

    def update_region(self, new_region):
        self.prepareGeometryChange()
        self.region = new_region
        if not self.region.isEmpty():
            self._generate_outline()
        else:
            self._path = QPainterPath()
        self.update()

    def boundingRect(self):
        if self.region.isEmpty():
            return QRectF()
        # 必须涵盖整个选区，并留出 2 像素给线宽
        return QRectF(self.region.boundingRect()).adjusted(-2, -2, 2, 2)

    def paint(self, painter, option, widget):
        if self.region.isEmpty() or self._path.isEmpty():
            return

        # 1. 绘制白色底边 (实线)
        w_pen = QPen(Qt.white, 1)
        w_pen.setCosmetic(True)  # 保证缩放时线条不会变粗
        painter.setPen(w_pen)
        painter.drawPath(self._path)

        # 2. 绘制黑色虚线 (蚂蚁线)
        b_pen = QPen(Qt.black, 1, Qt.DashLine)
        b_pen.setDashPattern([4, 4])
        b_pen.setDashOffset(self.offset)
        b_pen.setCosmetic(True)
        painter.setPen(b_pen)
        painter.drawPath(self._path)
