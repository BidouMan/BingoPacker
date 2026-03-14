from PySide6.QtWidgets import QGraphicsView, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPoint
from PySide6.QtGui import (
    QPainter,
    QColor,
    QBrush,
    QTransform,
    QPixmap,
    QDragEnterEvent,
    QDropEvent,
)

# from .selection_manager import SelectionManager
# from .constants import ToolMode


class ScalableView(QGraphicsView):
    def __init__(self, scene, parent_editor=None):
        super().__init__(scene)
        self.editor = parent_editor
        self.editor = parent_editor

        # ... (之前的初始化代码保持不变) ...

        # --- 关键修改 1：禁用默认的左键交互模式 ---
        # 如果 DragMode 是 ScrollHandDrag，QGraphicsView 内部会吞掉 mousePressEvent 来处理平移
        # 我们现在统一在过滤器里处理，所以这里设为 NoDrag
        self.setDragMode(QGraphicsView.NoDrag)

        # 确保视图能接收焦点，否则键盘过滤器可能失效
        self.setFocusPolicy(Qt.StrongFocus)
        # self.selection_manager = SelectionManager(self.scene)

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
        if not urls:
            return

        path = urls[0].toLocalFile()
        ext = path.lower()

        # 寻找 ManualEditor (向上查找容器)
        target = self.parent()
        while target and not hasattr(target, "display_image"):
            target = target.parent()

        if not target:
            return

        # --- 核心分流逻辑 ---
        if ext.endswith((".bgs", ".sprite3")):
            # 如果是工程文件，调用我们新增的 import_project_file
            if hasattr(target, "import_project_file"):
                target.import_project_file(path)
                event.acceptProposedAction()

        elif ext.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
            # 如果是单图，走原有逻辑
            target.display_image(path)
            event.acceptProposedAction()

    # scalable_view.py

    def get_appropriate_cursor(self):
        if self._is_panning:
            return Qt.ClosedHandCursor
        editor = self.parent()
        # 寻找 ManualEditor 容器
        while editor and not hasattr(editor, "btn_magic_wand"):
            editor = editor.parent()

        if editor and editor.btn_magic_wand.isChecked():
            return Qt.CrossCursor
        if hasattr(self, "selection_manager") and self.selection_manager.active:
            return Qt.CrossCursor
        return Qt.OpenHandCursor

    def update_cursor_style(self):
        """唯一允许修改光标的入口"""
        self.viewport().setCursor(self.get_appropriate_cursor())

    def mousePressEvent(self, event):
        """
        注意：当你安装了 eventFilter 并在里面返回 True 时，这里的代码根本不会被执行。
        但为了防止过滤器没捕捉到的情况，我们保留基本逻辑。
        """
        # 如果是中键，依然保留在 View 里处理（因为中键通常不涉及复杂的选区逻辑）
        if event.button() == Qt.MiddleButton:
            self._is_panning = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        # 重要：如果是左键，且我们处于选区模式，由 eventFilter 接管，
        # 这里什么都不要做，或者直接透传给父类。
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
            return

        # 模式分发交给 eventFilter 拦截，这里只做基础透传
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._is_panning = False
            self.update_cursor_style()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        """缩放逻辑必须在 View 层级"""
        # 1. 确保锚点设置正确 (这是 QGraphicsView 的方法)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        # 2. 执行缩放
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)

        # 3. 关键：接受事件，阻止它继续向上传递或向下分发给 Item
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if hasattr(self, "selection_manager") and self.selection_manager.active:
            scene_pos = self.mapToScene(event.pos())
            self.selection_manager.handle_double_click(scene_pos)
            return
        super().mouseDoubleClickEvent(event)

    def get_canvas_coordinates(self, pos):
        """将鼠标相对于窗口的坐标转换为相对于图片的像素坐标"""
        # 1. 映射到场景坐标
        scene_pos = self.mapToScene(pos)

        # 2. 如果场景中有底图 (pixmap_item)，则转换为底图的局部像素坐标
        # 假设 ManualEditor 在加载图片时将 pixmap_item 放在了 (0,0)
        return QPoint(int(scene_pos.x()), int(scene_pos.y()))


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
        if self.rect.isEmpty():
            return
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

    def reset_canvas(self, rect):
        self.scene().setSceneRect(rect)
        if not self.checker_item:
            from .scalable_view import CheckerboardItem

            self.checker_item = CheckerboardItem(rect)
            self.scene().addItem(self.checker_item)
        else:
            self.checker_item.set_rect(rect)

    # scalable_view.py
