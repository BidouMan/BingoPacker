# magic_wand.py 完整精准版

from PySide6.QtGui import QImage, QColor, QRegion, QBitmap
from PySide6.QtCore import QPoint, Qt,QRect

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
            (c1.red() - c2.red())**2 +
            (c1.green() - c2.green())**2 +
            (c1.blue() - c2.blue())**2 +
            (c1.alpha() - c2.alpha())**2
        )
        
        # 此时的 tolerance 建议设置在 10-30 之间
        return distance <= self.tolerance

    def get_selection_region(self, image, start_point, contiguous=True):
        if image.isNull() or not image.rect().contains(start_point):
            return QRegion()

        img = image.convertToFormat(QImage.Format_ARGB32)
        width, height = img.width(), img.height()
        target_color = img.pixelColor(start_point)
        
        # 创建一个单色掩码，确保初始为全黑 (0)
        mask = QImage(img.size(), QImage.Format_Mono)
        mask.fill(0) 

        if not contiguous:
            # --- 非连续模式：遍历全图 ---
            for y in range(height):
                for x in range(width):
                    if self.is_color_similar(target_color, img.pixelColor(x, y)):
                        mask.setPixel(x, y, 1)
        else:
            # --- 连续模式：泛洪算法 ---
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

        # --- 核心修复：更稳定的 QRegion 构造方案 ---
        # 1. 将 mask 强制转换为 QBitmap
        selection_bitmap = QBitmap.fromImage(mask)
        
        # 2. 从位图提取区域
        region = QRegion(selection_bitmap)
        
        # 3. 终极逻辑检查：如果点击点 (start_point) 竟然不在结果区域内，说明 0/1 彻底反了
        # 注意：这里不用 intersected 或 subtracted，直接利用 mask 的 setPixelColor 逻辑强制纠偏
        if not region.contains(start_point):
            # 获取全图矩形区域
            full_rect_region = QRegion(QRect(0, 0, width, height))
            # 只有当 mask 填充的是“背景”时才执行取反
            region = full_rect_region.subtracted(region)

        return region.intersected(QRect(0, 0, width, height))