import os
from PySide6.QtWidgets import QWidget, QGraphicsScene, QGraphicsPixmapItem, QListWidgetItem
from PySide6.QtCore import Qt, QRectF, Signal, QSize
from PySide6.QtGui import QPixmap, QIcon, QPainter

from .editor_ui import EditorUI
from .scalable_view import ScalableView, CheckerboardItem
from .selection_manager import SelectionManager
from ...logic_slice import SliceLogic
from ...asset_manager import AssetManager
from ...asset_model import AssetBundle, FrameData

class ManualEditor(QWidget, EditorUI):
    slice_completed = Signal(str, list)
    bundle_updated = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.asset_manager = AssetManager()
        self.current_bundle = None
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
        # self.selection_manager = SelectionManager(self.scene)
        # 把 manager 引用塞进 view 里面，否则 view 里的 hasattr(self, 'selection_manager') 永远是 False
        self.view.selection_manager = self.selection_manager
        self.setAcceptDrops(True)
        self.connect_signals()

    # --- 核心：数据驱动的属性拦截 ---
    @property
    def current_bundle(self):
        return self._current_bundle

    @current_bundle.setter
    def current_bundle(self, bundle):
        self._current_bundle = bundle
        # 只要 bundle 对象被重新赋值，立刻通知 AssetTree
        if bundle:
            self.bundle_updated.emit(bundle)

    def connect_signals(self):
        # 确保 UI 中的所有按钮都正确绑定
        self.btn_pick.toggled.connect(self.selection_manager.set_active)
        self.btn_slice.clicked.connect(self.on_do_slice)
        self.frame_list.currentRowChanged.connect(self.switch_frame_preview)
        self.btn_save.clicked.connect(self.on_save_clicked)
        self.btn_clear.clicked.connect(self.clear_all)
        # 补全 btn_new_file 的逻辑（如有需要）
        if hasattr(self, 'btn_new_file'):
            self.btn_new_file.clicked.connect(lambda: print("选取文件"))

    def display_image(self, file_path):
        if not os.path.exists(file_path): return
        pixmap = QPixmap(file_path)
        if pixmap.isNull(): return

        # 1. 模型层处理
        asset_name = os.path.splitext(os.path.basename(file_path))[0]
        self.current_bundle = AssetBundle(asset_name) 
        self.current_bundle.path = file_path
        self.current_bundle.original_pixmap = pixmap
        self.asset_manager.register_asset(self.current_bundle)

        # 2. UI 状态重置
        self.current_source_path = file_path
        self.frame_list.blockSignals(True)
        self.scene.clear()

        self.preview_item = None 
        self.pixmap_item = None

        self.frame_list.clear()
        self.current_frames = []

        # 3. 画布渲染
        rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        self.view.checker_item = CheckerboardItem(rect)
        self.scene.addItem(self.view.checker_item)
        
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        self.scene.addItem(self.pixmap_item)
        
        self.scene.setSceneRect(rect)
        self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

        # 4. 左侧列表：原图卡片 (完全还原原始视觉)
        icon_area = 45 
        canvas = QPixmap(icon_area, icon_area) 
        canvas.fill(Qt.GlobalColor.transparent)
        thumb = pixmap.scaled(icon_area, icon_area, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        painter = QPainter(canvas)
        painter.drawPixmap((icon_area - thumb.width()) // 2, (icon_area - thumb.height()) // 2, thumb)
        painter.end()
        
        item = QListWidgetItem()
        item.setIcon(QIcon(canvas)) 
        item.setText(os.path.basename(file_path))
        # --- 核心修复：强制卡片尺寸，解决不是正方形的问题 ---
        item.setSizeHint(QSize(78, 80)) 
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.frame_list.addItem(item)
        
        self.frame_list.blockSignals(False)
        self.frame_list.setCurrentRow(0)

    def on_do_slice(self):
        """执行裁切"""
        bg_item = next((i for i in self.scene.items() 
                    if isinstance(i, QGraphicsPixmapItem) and not hasattr(i, 'is_clone')), None)
        if not bg_item: return

        rects = self.selection_manager.get_sorted_selections()
        if rects:
            # 手动裁切
            self.current_frames = self.slice_logic.run_manual_slice(bg_item, rects)
        else:
            # 自动裁切：调用补全后的 logic_slice 方法
            self.current_frames = self.slice_logic.run_auto_slice_to_preview(bg_item.pixmap())

        if self.current_frames:
            if self.current_bundle:
                from ...asset_model import FrameData # 确保已导入
                self.current_bundle.frames = [
                    FrameData(f["pixmap"], f["rect"], f"{self.current_bundle.name}_{i}") 
                    for i, f in enumerate(self.current_frames)
                ]
                
                # 发送信号 更新资源表
                self.bundle_updated.emit(self.current_bundle)
                
            # 1. 彻底清理旧状态
            if self.preview_item:        
                try:
                    self.scene.removeItem(self.preview_item)
                except RuntimeError:
                    # 如果已经因为 scene.clear() 被删除了，直接跳过即可
                    pass
                self.preview_item = None
            
            # 隐藏底图
            bg_item.setVisible(False)
            self.selection_manager.clear_selections()
            self.selection_manager.set_active(False)

            # 2. 强制刷新场景和棋盘格
            first_pix = self.current_frames[0]["pixmap"]
            new_rect = QRectF(0, 0, first_pix.width(), first_pix.height())
            self.scene.setSceneRect(new_rect)
            
            if hasattr(self.view, 'checker_item'):
                self.view.checker_item.set_rect(new_rect)

            # 3. 刷新列表显示
            self.update_frame_list_ui()

            # 4. 默认选中第一帧
            self.frame_list.setCurrentRow(0)
            self.switch_frame_preview(0)

    def update_frame_list_ui(self):
        """将裁切后的每一帧存入左侧列表，并强制正方形尺寸"""
        self.frame_list.clear()
        for i, frame in enumerate(self.current_frames):
            pix = frame["pixmap"]
            item = QListWidgetItem(f"帧 {i:02d}")
            # 强制卡片为正方形尺寸，对应 UI 中的 list 宽度
            item.setSizeHint(QSize(78, 80)) 
            
            # 列表内的缩略图处理
            icon_pix = pix.scaled(45, 45, Qt.AspectRatioMode.KeepAspectRatio, 
                                Qt.TransformationMode.FastTransformation)
            item.setIcon(QIcon(icon_pix))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.frame_list.addItem(item)

    def switch_frame_preview(self, index):
        """点击列表项时，在画布中间显示该帧"""
        if index < 0 or index >= len(self.current_frames): return
        
        pix = self.current_frames[index]["pixmap"]
        new_rect = QRectF(0, 0, pix.width(), pix.height())

        # 调整场景大小以适应当前帧
        self.scene.setSceneRect(new_rect)
        if hasattr(self.view, 'checker_item'):
            self.view.checker_item.set_rect(new_rect)

        # 管理预览 Item
        if self.preview_item is None:
            self.preview_item = QGraphicsPixmapItem()
            self.scene.addItem(self.preview_item)
        
        self.preview_item.setPixmap(pix)
        self.preview_item.setVisible(True)
        # 保持像素清晰
        self.preview_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        
        # 自动缩放画布查看该帧
        self.view.fitInView(new_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def on_save_clicked(self):
        """保存逻辑：集成 SliceLogic"""
        if not self.current_frames: return
        pixmaps = [f["pixmap"] for f in self.current_frames]
        save_dir = self.slice_logic.save_sliced_sprites(self.current_source_path, pixmaps)
        print(f"已保存至: {save_dir}")

    def clear_all(self):
        self.scene.clear()
        self.frame_list.clear()
        self.current_frames = []