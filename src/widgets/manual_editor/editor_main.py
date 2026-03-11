from PySide6.QtWidgets import QWidget, QGraphicsScene, QGraphicsPixmapItem, QListWidgetItem
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPixmap, QIcon

from .editor_ui import EditorUI
from .scalable_view import ScalableView, CheckerboardItem
from .selection_manager import SelectionManager
from ...logic_slice import SliceLogic

class ManualEditor(QWidget, EditorUI):
    slice_completed = Signal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.slice_logic = SliceLogic()
        self.current_frames = []
        self.current_source_path = None
        self.preview_item = None
        
        # 初始化 UI
        self.setup_ui(self)
        self.scene = QGraphicsScene()
        self.view = ScalableView(self.scene)
        self.canvas_layout.addWidget(self.view)
        
        self.selection_manager = SelectionManager(self.scene)
        self.setAcceptDrops(True)
        self.connect_signals()

    def connect_signals(self):
        self.btn_pick.toggled.connect(self.selection_manager.set_active)
        self.btn_slice.clicked.connect(self.on_do_slice)
        self.frame_list.currentRowChanged.connect(self.switch_frame_preview)
        self.btn_save.clicked.connect(self.on_save_clicked)
        self.btn_clear.clicked.connect(self.clear_all)

    def display_image(self, file_path):
        pixmap = QPixmap(file_path)
        if pixmap.isNull(): return
        self.current_source_path = file_path
        
        self.scene.clear()
        self.frame_list.clear()
        
        rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        self.view.checker_item = CheckerboardItem(rect)
        self.scene.addItem(self.view.checker_item)
        
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        self.scene.addItem(self.pixmap_item)
        
        self.scene.setSceneRect(rect)
        self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def on_do_slice(self):
        # 逻辑同原代码，调用 slice_logic 处理...
        pass

    def switch_frame_preview(self, index):
        # 逻辑同原代码，更新预览图层...
        pass

    def on_save_clicked(self):
        # 保存逻辑...
        pass

    def clear_all(self):
        self.scene.clear()
        self.frame_list.clear()
        self.current_frames = []