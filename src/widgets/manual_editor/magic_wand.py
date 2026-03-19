import numpy as np
import cv2
from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QRect
from PySide6.QtGui import QPen, QPainterPath, QImage, QRegion, QPainter


class MagicWandTool:
    def __init__(self, tolerance=25):
        self.tolerance = tolerance

    def get_selection_region(self, image, start_point, contiguous=True):
        if image.isNull():
            return QRegion()

        temp_img = image.convertToFormat(QImage.Format_ARGB32)
        width, height = temp_img.width(), temp_img.height()

        ix = max(0, min(width - 1, int(start_point.x())))
        iy = max(0, min(height - 1, int(start_point.y())))

        # 1. 提取原始数据
        ptr = temp_img.bits()
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4)).copy()
        target_pixel = arr[iy, ix].astype(np.int32)

        # 2. 计算掩码 (RGB + Alpha)
        # 考虑alpha通道，确保透明区域和非透明区域不会被一起选中
        diff = np.abs(arr[:, :, :4].astype(np.int32) - target_pixel[:4])
        mask = np.all(diff <= self.tolerance, axis=2)

        # 3. 处理连通性
        if contiguous:
            mask_uint8 = mask.astype(np.uint8) * 255
            num_labels, labels = cv2.connectedComponents(mask_uint8, connectivity=4)
            start_label = labels[iy, ix]
            if start_label > 0:
                mask = labels == start_label
            else:
                return QRegion()

        # 4. --- 根源级修复：像素行扫描构建 QRegion ---
        # 这种方法直接通过像素索引构建，保证 100% 对应，不会少一像素
        q_region = QRegion()
        rect_count = 0

        for y in range(height):
            row = mask[y, :]
            # 寻找连续段的起点和终点
            x_diff = np.diff(row.astype(np.int8), prepend=0, append=0)
            starts = np.where(x_diff == 1)[0]
            ends = np.where(x_diff == -1)[0]

            for s, e in zip(starts, ends):
                # QRect(x, y, width, height)
                # 宽度 e-s 严格等于像素个数
                q_region += QRegion(QRect(s, y, e - s, 1))
                rect_count += 1

        return q_region


class SelectionAntsItem(QGraphicsItem):
    def __init__(self, region, parent=None):
        super().__init__(parent)
        self.region = region
        self.offset = 0
        self._path = QPainterPath()
        if not self.region.isEmpty():
            self._generate_outline()

    def _generate_outline(self):
        """
        核心修复：将碎片化的矩形合并为统一的外轮廓
        """
        # 1. 直接将 region 添加到路径中
        # addRegion 内部会尝试组合矩形，但通常还是保留了矩形结构
        raw_path = QPainterPath()
        raw_path.addRegion(self.region)

        # 2. 关键点：使用 simplified()
        # 它会合并所有共线的边，删除图形内部的线条，只留下外边界
        self._path = raw_path.simplified()

        # 3. 容错处理：如果简化失败（极其复杂的情况），至少保证能看到东西
        if self._path.isEmpty() and not self.region.isEmpty():
            for rect in self.region:
                self._path.addRect(QRectF(rect))

    def boundingRect(self):
        # 边界需要稍微扩大，以容纳 1 像素宽的虚线
        return QRectF(self.region.boundingRect()).adjusted(-1, -1, 1, 1)

    def paint(self, painter, option, widget):
        if self.region.isEmpty() or self._path.isEmpty():
            return

        # 保持锐利度
        painter.setRenderHint(QPainter.Antialiasing, False)

        # 设置虚线笔触（Cosmetic 确保缩放不影响线宽）
        w_pen = QPen(Qt.white, 0)
        w_pen.setCosmetic(True)
        w_pen.setStyle(Qt.CustomDashLine)
        w_pen.setDashPattern([4, 4])
        w_pen.setDashOffset(self.offset)

        b_pen = QPen(Qt.black, 0)
        b_pen.setCosmetic(True)
        b_pen.setStyle(Qt.CustomDashLine)
        b_pen.setDashPattern([4, 4])
        b_pen.setDashOffset(self.offset + 4)

        # 只绘制路径，即合并后的外轮廓
        painter.setPen(w_pen)
        painter.drawPath(self._path)
        painter.setPen(b_pen)
        painter.drawPath(self._path)
