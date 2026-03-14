# magic_wand.py 完整精准版

from PySide6.QtGui import QImage, QRegion, QBitmap
from PySide6.QtCore import QPoint, QRect


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
        """
        执行魔棒算法
        contiguous=True: 连续模式（只选粘在一起的）
        contiguous=False: 全图模式（选所有颜色相近的）
        """
        if image.isNull() or not image.rect().contains(start_point):
            return QRegion()

        img = image.convertToFormat(QImage.Format_ARGB32)
        width, height = img.width(), img.height()
        target_color = img.pixelColor(start_point)

        # 创建单色掩码，初始全黑(0)
        mask = QImage(img.size(), QImage.Format_Mono)
        mask.fill(0)

        if not contiguous:
            # --- 全图模式：扫描每一个像素 ---
            for y in range(height):
                for x in range(width):
                    if self.is_color_similar(target_color, img.pixelColor(x, y)):
                        mask.setPixel(x, y, 1)
        else:
            # --- 连续模式：泛洪算法 (保持你原有的逻辑) ---
            stack = [start_point]
            visited = set([(start_point.x(), start_point.y())])
            while stack:
                p = stack.pop()
                x, y = p.x(), p.y()
                mask.setPixel(x, y, 1)

                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                        if self.is_color_similar(target_color, img.pixelColor(nx, ny)):
                            visited.add((nx, ny))
                            stack.append(QPoint(nx, ny))

        # 转换为 QRegion 并处理反向纠偏
        selection_bitmap = QBitmap.fromImage(mask)
        region = QRegion(selection_bitmap)

        # 纠偏：确保点击的点必须在选区内，如果不在，说明 0/1 填反了
        if not region.contains(start_point):
            region = QRegion(QRect(0, 0, width, height)).subtracted(region)

        return region.intersected(QRect(0, 0, width, height))
