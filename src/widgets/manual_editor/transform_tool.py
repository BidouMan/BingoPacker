from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPen, QPainter


class TransformHandle(QGraphicsRectItem):
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

            # 根据不同位置的手柄限制移动方向
            if self.pos_key == "tl":  # 左上角：可以调整宽高
                if rect.right() - new_pos.x() > 5 and rect.bottom() - new_pos.y() > 5:
                    rect.setTopLeft(new_pos)
            elif self.pos_key == "tr":  # 右上角：可以调整宽高
                if new_pos.x() - rect.left() > 5 and rect.bottom() - new_pos.y() > 5:
                    rect.setTopRight(new_pos)
            elif self.pos_key == "bl":  # 左下角：可以调整宽高
                if rect.right() - new_pos.x() > 5 and new_pos.y() - rect.top() > 5:
                    rect.setBottomLeft(new_pos)
            elif self.pos_key == "br":  # 右下角：可以调整宽高
                if new_pos.x() - rect.left() > 5 and new_pos.y() - rect.top() > 5:
                    rect.setBottomRight(new_pos)

            self.parentItem().setRect(rect)
            self.parentItem().update_handles_pos()
            
            # 实时更新图像变换
            if hasattr(self.parentItem(), 'update_transform'):
                self.parentItem().update_transform()
                
            return new_pos  # 返回限制后的坐标

        return super().itemChange(change, value)


class TransformBoxItem(QGraphicsRectItem):
    
    def __init__(self, initial_rect, parent_item=None, transform_callback=None):
        super().__init__(initial_rect, parent_item)
        pen = QPen(QColor("#61afef"), 1.5)  # 1.5 像素宽，蓝白色
        pen.setCosmetic(True)  # 关键：让线宽不随缩放改变
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)  # 让拐角尖锐
        self.setPen(pen)
        self.setZValue(1000)
        self.transform_callback = transform_callback  # 添加回调函数

        self.handles = {}
        for key in ["tl", "tr", "bl", "br"]:
            handle = TransformHandle(self, key)
            handle.enabledSignals = False
            self.handles[key] = handle

        self.update_handles_pos()

    def update_handles_pos(self):
        """根据当前矩形位置，将4个手柄对齐到顶点"""
        r = self.rect()
        h_map = {
            "tl": r.topLeft(),
            "tr": r.topRight(),
            "bl": r.bottomLeft(),
            "br": r.bottomRight(),
        }
        for key, pos in h_map.items():
            self.handles[key].enabledSignals = False
            self.handles[key].setPos(pos)
            self.handles[key].enabledSignals = True

    def update_transform(self):
        """实时更新图像变换"""
        if self.transform_callback:
            self.transform_callback(self.rect())

    def paint(self, painter, option, widget):
        r = self.rect()
        painter.save()

        # 绘制主蓝色边框
        painter.setPen(self.pen())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r)

        painter.restore()
