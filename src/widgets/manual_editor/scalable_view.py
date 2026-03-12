from PySide6.QtWidgets import QGraphicsView, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPoint
from PySide6.QtGui import QPainter, QColor, QBrush, QTransform, QPixmap, QDragEnterEvent, QDropEvent, QWheelEvent, QMouseEvent
from .selection_manager import SelectionManager

class ScalableView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)

        self.selection_manager = SelectionManager(self.scene)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QColor(30, 33, 39)) 
        
        self.checker_item = None
        self.setAcceptDrops(True)
        self._is_panning = False
        self._last_mouse_pos = QPoint()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls: return
        
        path = urls[0].toLocalFile()
        ext = path.lower()

        # 寻找 ManualEditor (向上查找容器)
        target = self.parent()
        while target and not hasattr(target, 'display_image'):
            target = target.parent()
        
        if not target: return

        # --- 核心分流逻辑 ---
        if ext.endswith(('.bgs', '.sprite3')):
            # 如果是工程文件，调用我们新增的 import_project_file
            if hasattr(target, 'import_project_file'):
                target.import_project_file(path)
                event.acceptProposedAction()
        
        elif ext.endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
            # 如果是单图，走原有逻辑
            target.display_image(path)
            event.acceptProposedAction()

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)

    # scalable_view.py

    def mousePressEvent(self, event):
        # 1. 中键平移逻辑
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return

        # 2. 选取模式转发
        if hasattr(self, 'selection_manager') and self.selection_manager.active:
            if event.button() == Qt.MouseButton.LeftButton:
                # 转换坐标并提取修饰键
                scene_pos = self.mapToScene(event.pos())
                modifiers = event.modifiers()
                # 调用你代码中真实的名字：handle_press
                self.selection_manager.handle_press(scene_pos, modifiers)
                return 

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 中键平移逻辑
        if self._is_panning:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return

        # 选取模式转发
        if hasattr(self, 'selection_manager') and self.selection_manager.active:
            # 转换坐标
            scene_pos = self.mapToScene(event.pos())
            # 调用你代码中真实的名字：handle_move
            self.selection_manager.handle_move(scene_pos)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # 中键平移结束
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False
            cursor = Qt.CrossCursor if (hasattr(self, 'selection_manager') and self.selection_manager.active) else Qt.ArrowCursor
            self.setCursor(cursor)
            return

        # 选取模式转发
        if hasattr(self, 'selection_manager') and self.selection_manager.active:
            if event.button() == Qt.MouseButton.LeftButton:
                # 转换坐标并提取修饰键
                scene_pos = self.mapToScene(event.pos())
                modifiers = event.modifiers()
                # 调用你代码中真实的名字：handle_release
                self.selection_manager.handle_release(scene_pos, modifiers)
                return

        super().mouseReleaseEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        if hasattr(self, 'selection_manager') and self.selection_manager.active:
            scene_pos = self.mapToScene(event.pos())
            self.selection_manager.handle_double_click(scene_pos)
            return
        super().mouseDoubleClickEvent(event)

class CheckerboardItem(QGraphicsItem):
    def __init__(self, rect=QRectF()):
        super().__init__()
        self.rect = rect
        self.color1 = QColor(50, 50, 50)
        self.color2 = QColor(60, 60, 60)
        self.setZValue(-100)
        self._cached_pixmap = None
        self._last_side = -1

    def set_rect(self, rect):
        self.prepareGeometryChange()
        self.rect = rect
        self._cached_pixmap = None 
        self.update()

    def boundingRect(self):
        return self.rect if not self.rect.isNull() else QRectF(0, 0, 1000, 1000)

    def paint(self, painter, option, widget):
        if self.rect.isEmpty(): return
        painter.save()
        scale = painter.worldTransform().m11()
        side = max(1.0, round(16.0 / scale))
        
        dpr = widget.devicePixelRatioF() if widget else 1.0
        if self._cached_pixmap is None or abs(self._last_side - side) > 0.1:
            self._last_side = side
            phys_side = max(1, int(side * dpr))
            tile = QPixmap(phys_side * 2, phys_side * 2)
            tile.setDevicePixelRatio(dpr)
            tile.fill(self.color2)
            tp = QPainter(tile)
            tp.fillRect(0, 0, int(side), int(side), self.color1)
            tp.fillRect(int(side), int(side), int(side), int(side), self.color1)
            tp.end()
            self._cached_pixmap = tile

        brush = QBrush(self._cached_pixmap)
        brush_tx = QTransform()
        brush_tx.translate(self.rect.x(), self.rect.y())
        brush.setTransform(brush_tx)
        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect)
        painter.restore()