from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsObject
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QColor, QPen, QBrush, QCursor, QPainterPath,QPainter

class CropHandle(QGraphicsRectItem):
    def __init__(self, parent, pos_key):
        super().__init__(parent)
        self.pos_key = pos_key
        self.size = 6 # 开启忽略变换后，6像素通常更易点击
        self.setRect(-self.size/2, -self.size/2, self.size, self.size)
        
        self.setBrush(QColor("#61afef"))
        self.setPen(QPen(Qt.GlobalColor.white, 1))
        
        # --- 核心修复：让手柄不随视图缩放 ---
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        # ----------------------------------
        
        self.setZValue(1001)
        self.setFlags(self.flags() | 
                      QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

    def paint(self, painter, option, widget):
        """重绘为圆形"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) # 开启抗锯齿
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawEllipse(self.rect()) # 画圆形

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.enabledSignals:
            new_pos = value
            rect = self.parentItem().rect()

            # --- 3. 核心：轴向锁定逻辑 ---
            # 如果是中间的点，强制固定其中一个坐标，使其只能沿直线滑动
            if self.pos_key == 'tm':   # 上中：x 固定在中心
                new_pos.setX(rect.center().x())
            elif self.pos_key == 'bm': # 下中：x 固定在中心
                new_pos.setX(rect.center().x())
            elif self.pos_key == 'ml': # 左中：y 固定在中心
                new_pos.setY(rect.center().y())
            elif self.pos_key == 'mr': # 右中：y 固定在中心
                new_pos.setY(rect.center().y())
            
            self.parentItem().update_rect_from_handle(self.pos_key, new_pos)
            return new_pos # 返回限制后的坐标
            
        return super().itemChange(change, value)

class CropBoxItem(QGraphicsRectItem):
    """裁切框主图元，包含遮罩和九宫格"""
    def __init__(self, scene_rect, initial_rect):
        super().__init__(initial_rect)
        self.scene_rect = scene_rect # 整个画布的范围，用于绘制遮罩
        self.setPen(QPen(QColor("#61afef"), 1, Qt.PenStyle.SolidLine))
        self.setZValue(1000)
        
        # 初始化 8 个手柄
        self.handles = {}
        for key in ['tl', 'tm', 'tr', 'ml', 'mr', 'bl', 'bm', 'br']:
            handle = CropHandle(self, key)
            handle.enabledSignals = False # 初始化时禁用信号
            self.handles[key] = handle
            
        self.update_handles_pos()

    def update_handles_pos(self):
        """根据当前矩形位置更新所有手柄位置"""
        r = self.rect()
        h_map = {
            'tl': r.topLeft(),
            'tm': QPointF(r.center().x(), r.top()),
            'tr': r.topRight(),
            'ml': QPointF(r.left(), r.center().y()),
            'mr': QPointF(r.right(), r.center().y()),
            'bl': r.bottomLeft(),
            'bm': QPointF(r.center().x(), r.bottom()),
            'br': r.bottomRight()
        }
        for key, pos in h_map.items():
            self.handles[key].enabledSignals = False
            self.handles[key].setPos(pos)
            self.handles[key].enabledSignals = True

    def update_rect_from_handle(self, key, new_pos):
        """当手柄被拖动时更新矩形"""
        r = self.rect()
        # 限制不让矩形翻转（缩到最小宽度）
        min_size = 10
        
        if 't' in key:
            if r.bottom() - new_pos.y() > min_size: r.setTop(new_pos.y())
        if 'b' in key:
            if new_pos.y() - r.top() > min_size: r.setBottom(new_pos.y())
        if 'l' in key:
            if r.right() - new_pos.x() > min_size: r.setLeft(new_pos.x())
        if 'r' in key:
            if new_pos.x() - r.left() > min_size: r.setRight(new_pos.x())
            
        self.setRect(r.normalized())
        self.update_handles_pos()
        self.update() # 重新绘制遮罩和九宫格

    def paint(self, painter, option, widget):
        # 1. 绘制外部阴影遮罩
        r = self.rect()
        painter.save()
        mask_color = QColor(0, 0, 0, 150) # 半透明黑色
        
        # 计算遮罩路径：大矩形减去当前裁切矩形
        path = QPainterPath()
        path.addRect(self.scene_rect)
        path.addRect(r)
        
        painter.setBrush(QBrush(mask_color))
        # --- 修复此处 ---
        painter.setPen(Qt.PenStyle.NoPen) 
        # ----------------
        
        # 使用 OddEvenFill 规则，这样相交的部分（裁切框内）会被镂空
        path.setFillRule(Qt.FillRule.OddEvenFill)
        painter.drawPath(path)
        painter.restore()