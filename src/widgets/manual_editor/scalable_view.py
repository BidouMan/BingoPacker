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
        self._user_panned = False  # 用于判断用户是否主动平移过视图
        self._last_mouse_pos = QPoint()

        # 当前“内容”的边界（通常是图片的场景坐标范围）
        self._content_rect = QRectF()

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
        # 默认不显示手掌，仅在按下中键时显示（ClosedHandCursor）
        return Qt.ArrowCursor

    def update_cursor_style(self):
        """唯一允许修改光标的入口"""
        self.viewport().setCursor(self.get_appropriate_cursor())

    def reset_pan_state(self):
        """重置用户是否已平移的状态（如新加载图片时调用）。"""
        self._user_panned = False

    def has_user_panned(self):
        return self._user_panned

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
            # 用户主动拖动后，不再自动重置为居中视图
            self._user_panned = True
            event.accept()
            return

        # 模式分发交给 eventFilter 拦截，这里只做基础透传
        super().mouseMoveEvent(event)

        # 允许通过滚动条或缩放改变后重新计算 sceneRect
        self._update_scene_rect_for_panning()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._is_panning = False
            self.update_cursor_style()
            event.accept()
            return

        super().mouseReleaseEvent(event)

        # 鼠标释放后更新 sceneRect，确保本次拖拽后的最新偏移仍可平移
        self._update_scene_rect_for_panning()

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

        # 3. 缩放后刷新 sceneRect，保持可拖动范围
        self._update_scene_rect_for_panning()

        # 4. 关键：接受事件，阻止它继续向上传递或向下分发给 Item
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if hasattr(self, "selection_manager") and self.selection_manager.active:
            scene_pos = self.mapToScene(event.pos())
            self.selection_manager.handle_double_click(scene_pos)
            return
        super().mouseDoubleClickEvent(event)

    def _update_scene_rect_for_panning(self):
        """在保持内容可见的前提下，为画布平移提供可用滚动范围。

        如果内容（例如图片）比视口小，默认 QGraphicsView 会关闭滚动范围，
        导致中键拖动无法移动视图。我们通过让 sceneRect 扩展为至少与视口等大，
        并在两侧留出空白来实现“自由拖动但不让内容完全移出视口”。
        """
        if self._content_rect.isNull():
            return

        if self.viewport().width() == 0 or self.viewport().height() == 0:
            # 视图尚未布局完成时，先保证 sceneRect 至少和内容一致。
            self.setSceneRect(self._content_rect)
            return

        # 以当前变换后的视口尺寸为基准（已考虑缩放）
        view_scene_rect = self.mapToScene(self.viewport().rect()).boundingRect()

        # 计算一个可拖动的 sceneRect：
        # - 如果内容比视口大，则直接使用内容大小（支持滚动）
        # - 如果内容比视口小，则将 sceneRect 扩大到 "2*视口 - 内容"，
        #   这样可以在不让内容完全离开视口的前提下实现左右/上下拖动
        vw = view_scene_rect.width()
        vh = view_scene_rect.height()
        cw = self._content_rect.width()
        ch = self._content_rect.height()

        width = max(cw, 2 * vw - cw)
        height = max(ch, 2 * vh - ch)

        dx = (width - cw) / 2
        dy = (height - ch) / 2

        padded = QRectF(
            self._content_rect.x() - dx,
            self._content_rect.y() - dy,
            width,
            height,
        )

        # 只有在需要时才设置（避免频繁触发 scroll 更新）
        if self.sceneRect() != padded:
            self.setSceneRect(padded)

    def set_content_rect(self, rect: QRectF):
        """设置当前内容（如图片）的边界，并更新 sceneRect 以支持平移。"""
        self._content_rect = rect
        self._update_scene_rect_for_panning()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 视口大小变化后，重新计算 sceneRect 以保持可拖动范围。
        self._update_scene_rect_for_panning()

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
