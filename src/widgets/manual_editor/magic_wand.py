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

    def get_selection_region(self, image, start_point):
        """
        执行泛洪填充算法，返回一个精准的 QRegion。
        """
        # 1. 基础合法性检查
        if image.isNull() or not image.rect().contains(start_point):
            return QRegion()

        # 2. 预处理图片：统一转为带 Alpha 的 32 位格式，确保像素读取一致性
        img = image.convertToFormat(QImage.Format_ARGB32)
        width, height = img.width(), img.height()
        target_color = img.pixelColor(start_point)
        
        # 3. 准备单色位图掩码 (Format_Mono)
        # Qt 的单色图：0 通常对应 Qt.color0，1 对应 Qt.color1
        mask = QImage(img.size(), QImage.Format_Mono)
        mask.fill(0) # 初始化为全黑（未选中）

        # 4. 泛洪填充 (Flood Fill)
        stack = [start_point]
        visited = set()
        visited.add((start_point.x(), start_point.y()))

        while stack:
            p = stack.pop()
            x, y = p.x(), p.y()
            
            # 在掩码上标记该像素已选中
            mask.setPixel(x, y, 1)

            # 检查上下左右四邻域
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                
                if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                    current_color = img.pixelColor(nx, ny)
                    
                    # 使用 self.is_color_similar 比较颜色
                    if self.is_color_similar(target_color, current_color):
                        visited.add((nx, ny))
                        stack.append(QPoint(nx, ny))

        # 5. 【核心】将位图掩码转换为精细的 QRegion
        # QBitmap 会自动将值为 1 的像素识别为有效区域（Foreground）
        # QRegion 构造函数会自动将这些像素合并成最高效的矩形集合
        # 显式创建位图，并确保其格式
        # 1. 生成初始选区
        selection_bitmap = QBitmap.fromImage(mask)
        
        # 2. 从位图构造选区
        region = QRegion(selection_bitmap)
        
        # 3. 【纠偏关键】检查点击点是否在选区内
        # 如果 start_point 不在 region 里，说明 0 和 1 真的反了
        if not region.contains(start_point):
            # 这种方法比 invertPixels 更稳，因为它直接反转了区域逻辑
            full_region = QRegion(QRect(0, 0, width, height))
            region = full_region.subtracted(region)

        # 4. 最后的边界约束
        return region.intersected(QRect(0, 0, width, height))