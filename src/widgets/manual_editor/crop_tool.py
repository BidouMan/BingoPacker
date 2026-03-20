from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF, QPoint
from PySide6.QtGui import QColor, QPen, QPainter, QPixmap, QBrush, QPainterPath, QFont


class CropHandle(QGraphicsRectItem):
    def __init__(self, parent, pos_key):
        super().__init__(parent)
        self.pos_key = pos_key
        self.size = 8  # 开启忽略变换后，6像素通常更易点击
        self.setRect(-self.size / 2, -self.size / 2, self.size, self.size)

        self.setBrush(QColor("#61afef"))
        self.setPen(QPen(Qt.GlobalColor.white, 1))

        # --- 核心修复：让手柄不随视图缩放 ---
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        # ----------------------------------

        self.setZValue(1001)
        self.setFlags(
            self.flags()
            | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    def paint(self, painter, option, widget):
        """重绘为圆形"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 开启抗锯齿
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawEllipse(self.rect())  # 画圆形

    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self.enabledSignals
        ):
            new_pos = value
            rect = self.parentItem().rect()

            # --- 3. 核心：轴向锁定逻辑 ---
            # 如果是中间的点，强制固定其中一个坐标，使其只能沿直线滑动
            if self.pos_key == "tm":  # 上中：x 固定在中心
                new_pos.setX(rect.center().x())
            elif self.pos_key == "bm":  # 下中：x 固定在中心
                new_pos.setX(rect.center().x())
            elif self.pos_key == "ml":  # 左中：y 固定在中心
                new_pos.setY(rect.center().y())
            elif self.pos_key == "mr":  # 右中：y 固定在中心
                new_pos.setY(rect.center().y())

            self.parentItem().update_rect_from_handle(self.pos_key, new_pos)
            return new_pos  # 返回限制后的坐标

        return super().itemChange(change, value)


class CropBoxItem(QGraphicsRectItem):
    
    def __init__(self, initial_rect, parent_item=None, update_callback=None):
        super().__init__(initial_rect, parent_item)
        pen = QPen(QColor("#61afef"), 1.5)  # 1.5 像素宽，蓝白色
        pen.setCosmetic(True)  # 关键：让线宽不随缩放改变
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)  # 让拐角尖锐
        self.setPen(pen)
        self.setZValue(1000)
        self.update_callback = update_callback  # 添加回调函数

        self.handles = {}
        for key in ["tl", "tm", "tr", "ml", "mr", "bl", "bm", "br"]:
            handle = CropHandle(self, key)
            handle.enabledSignals = False
            self.handles[key] = handle

        # 这里报错是因为下面这个方法没定义
        self.update_handles_pos()

    def update_handles_pos(self):
        """核心修复：根据当前矩形位置，将8个手柄对齐到顶点和中点"""
        r = self.rect()
        h_map = {
            "tl": r.topLeft(),
            "tm": QPointF(r.center().x(), r.top()),
            "tr": r.topRight(),
            "ml": QPointF(r.left(), r.center().y()),
            "mr": QPointF(r.right(), r.center().y()),
            "bl": r.bottomLeft(),
            "bm": QPointF(r.center().x(), r.bottom()),
            "br": r.bottomRight(),
        }
        for key, pos in h_map.items():
            self.handles[key].enabledSignals = False
            self.handles[key].setPos(pos)
            self.handles[key].enabledSignals = True

    def update_rect_from_handle(self, key, new_pos):
        """当用户拖动某个手柄时，重新计算矩形大小"""
        r = self.rect()
        min_size = 5  # 允许裁切的最小像素尺寸
        
        # 简单像素吸附：直接吸附到最近的整数像素
        snapped_pos = QPointF(round(new_pos.x()), round(new_pos.y()))

        if "t" in key:
            if r.bottom() - snapped_pos.y() > min_size:
                r.setTop(snapped_pos.y())
        if "b" in key:
            if snapped_pos.y() - r.top() > min_size:
                r.setBottom(snapped_pos.y())
        if "l" in key:
            if r.right() - snapped_pos.x() > min_size:
                r.setLeft(snapped_pos.x())
        if "r" in key:
            if snapped_pos.x() - r.left() > min_size:
                r.setRight(snapped_pos.x())

        self.setRect(r.normalized())
        self.update_handles_pos()  # 联动更新其他手柄位置
        self.update()  # 触发重绘遮罩和九宫格
        
        # 调用回调函数更新状态栏
        if self.update_callback:
            self.update_callback()

    def paint(self, painter, option, widget):
        r = self.rect()
        painter.save()

        # 1. 绘制外部深色阴影 (遮罩)
        if self.parentItem():
            # 使用父图元（即被裁剪的图片）作为遮罩范围，避免依赖 sceneRect 导致的黑色空白
            parent_rect = self.parentItem().boundingRect()
            local_scene = parent_rect
        elif self.scene():
            # 兜底：没有父图元时再用场景范围
            scene_rect = self.scene().sceneRect()
            local_scene = self.mapFromScene(scene_rect).boundingRect()

        mask_path = QPainterPath()
        mask_path.addRect(local_scene)  # 外圈
        mask_path.addRect(r)  # 内圈（裁切框）

        # 使用 OddEvenFill，两个矩形重叠的部分（框内）会变透明，不重叠的部分（框外）填深色
        mask_path.setFillRule(Qt.FillRule.OddEvenFill)
        painter.setBrush(QBrush(QColor(0, 0, 0, 160)))  # 半透明黑色
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(mask_path)

        # 3. 绘制主蓝色边框
        painter.setPen(self.pen())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r)

        # 2. 绘制九宫格辅助线
        painter.setPen(QPen(QColor(255, 255, 255, 100), 0, Qt.PenStyle.DashLine))
        w, h = r.width(), r.height()
        # 纵线
        painter.drawLine(
            QPointF(r.left() + w / 3, r.top()), QPointF(r.left() + w / 3, r.bottom())
        )
        painter.drawLine(
            QPointF(r.left() + 2 * w / 3, r.top()),
            QPointF(r.left() + 2 * w / 3, r.bottom()),
        )
        # 横线
        painter.drawLine(
            QPointF(r.left(), r.top() + h / 3), QPointF(r.right(), r.top() + h / 3)
        )
        painter.drawLine(
            QPointF(r.left(), r.top() + 2 * h / 3),
            QPointF(r.right(), r.top() + 2 * h / 3),
        )

        painter.restore()

    def get_cropped_pixmap(self):
        """根据当前框的位置从父图元提取 Pixmap"""
        target_item = self.parentItem()  # 即 pixmap_item 或 preview_item
        if not target_item or not hasattr(target_item, "pixmap"):
            return None

        original_pixmap = target_item.pixmap()
        if original_pixmap.isNull():
            return None

        # 因为 self.parent_item 是底图，所以 self.rect() 的坐标就是相对于图片的像素偏移
        crop_rect = self.rect().normalized().toRect()

        # 执行切割
        new_pixmap = QPixmap(crop_rect.width(), crop_rect.height())
        new_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(new_pixmap)
        # 将原图平移绘制到新画布上
        painter.drawPixmap(QPoint(-crop_rect.x(), -crop_rect.y()), original_pixmap)
        painter.end()

        return new_pixmap
