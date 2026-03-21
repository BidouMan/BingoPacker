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
            original_rect = QRectF(rect)
            
            # 获取父项的初始宽高比（用于等比缩放）
            initial_ratio = self.parentItem().initial_ratio
            
            # 检查是否按下了Shift键
            from PySide6.QtWidgets import QApplication
            is_shift_pressed = QApplication.keyboardModifiers() & Qt.ShiftModifier
            
            # 根据不同位置的手柄限制移动方向
            if self.pos_key == "tl":  # 左上角：可以调整宽高
                if rect.right() - new_pos.x() > 5 and rect.bottom() - new_pos.y() > 5:
                    if is_shift_pressed:
                        # 等比缩放：保持初始宽高比
                        new_width = rect.right() - new_pos.x()
                        new_height = new_width / initial_ratio
                        rect.setTopLeft(QPointF(new_pos.x(), rect.bottom() - new_height))
                    else:
                        rect.setTopLeft(new_pos)
            elif self.pos_key == "tr":  # 右上角：可以调整宽高
                if new_pos.x() - rect.left() > 5 and rect.bottom() - new_pos.y() > 5:
                    if is_shift_pressed:
                        # 等比缩放：保持初始宽高比
                        new_width = new_pos.x() - rect.left()
                        new_height = new_width / initial_ratio
                        rect.setTopRight(QPointF(new_pos.x(), rect.bottom() - new_height))
                    else:
                        rect.setTopRight(new_pos)
            elif self.pos_key == "bl":  # 左下角：可以调整宽高
                if rect.right() - new_pos.x() > 5 and new_pos.y() - rect.top() > 5:
                    if is_shift_pressed:
                        # 等比缩放：保持初始宽高比
                        new_height = new_pos.y() - rect.top()
                        new_width = new_height * initial_ratio
                        rect.setBottomLeft(QPointF(rect.right() - new_width, new_pos.y()))
                    else:
                        rect.setBottomLeft(new_pos)
            elif self.pos_key == "br":  # 右下角：可以调整宽高
                if new_pos.x() - rect.left() > 5 and new_pos.y() - rect.top() > 5:
                    if is_shift_pressed:
                        # 等比缩放：保持初始宽高比
                        new_width = new_pos.x() - rect.left()
                        new_height = new_width / initial_ratio
                        rect.setBottomRight(QPointF(new_pos.x(), rect.top() + new_height))
                    else:
                        rect.setBottomRight(new_pos)

            # 如果矩形尺寸没有变化（达到最小限制），阻止手柄移动
            if rect == original_rect:
                # 返回手柄应该在的位置（选框角落）
                if self.pos_key == "tl":
                    return rect.topLeft()
                elif self.pos_key == "tr":
                    return rect.topRight()
                elif self.pos_key == "bl":
                    return rect.bottomLeft()
                elif self.pos_key == "br":
                    return rect.bottomRight()

            # 像素吸附：将矩形坐标对齐到整数像素
            aligned_rect = QRectF(
                round(rect.left()),
                round(rect.top()),
                round(rect.width()),
                round(rect.height())
            )
            self.parentItem().setRect(aligned_rect)
            self.parentItem().update_handles_pos()
            
            # 实时更新图像变换
            if hasattr(self.parentItem(), 'update_transform'):
                self.parentItem().update_transform()
                
            # 返回手柄的新位置（应该是矩形的角落）
            if self.pos_key == "tl":
                return rect.topLeft()
            elif self.pos_key == "tr":
                return rect.topRight()
            elif self.pos_key == "bl":
                return rect.bottomLeft()
            elif self.pos_key == "br":
                return rect.bottomRight()
            
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
        
        # 保存初始宽高比，用于等比缩放
        self.initial_width = initial_rect.width()
        self.initial_height = initial_rect.height()
        self.initial_ratio = self.initial_width / self.initial_height if self.initial_height > 0 else 1

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
            # 直接设置手柄位置到矩形的精确角落位置
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
