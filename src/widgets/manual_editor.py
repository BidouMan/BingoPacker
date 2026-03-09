import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
                               QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QLabel,
                               QPushButton, QFrame,QButtonGroup, QAbstractItemView)
from PySide6.QtCore import Qt, QRectF, QPoint, QSize
from PySide6.QtGui import QPixmap, QWheelEvent, QPainter, QMouseEvent, QIcon, QDragEnterEvent, QDropEvent
from .selection_manager import SelectionManager
from ..logic_slice import SliceLogic

class ManualEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.slice_logic = SliceLogic() # 初始化逻辑类
        self.current_frames = []        # 存储裁切后的帧数据: [{"pixmap": QPixmap, "rect": QRect}, ...]
        self.preview_item = None        # 用于显示单帧预览的 Item
        self.current_source_path = None
        # --- 修复点 1：移除原本会导致 AttributeError 的行 ---
        # QWidget 没有 setRenderHint 等方法，这些已经移至下方的 ScalableView
        self.setAcceptDrops(True)       # 这里保留是为了让事件能传导
        self.init_ui()

    def init_ui(self):
        # 整体 QSS 样式 (完全保留你的原始 QSS)
        self.setStyleSheet("""
            QWidget { background-color: #4E5357; color: #cdd6f4; border: 2px solid #313244; }
            
            /* 资源列表样式 */
            QListWidget { 
                background-color: #1e1e2e; 
                border-radius: 0px; 
                border:none;
                border-left: 2px solid #313244; 
                border-top: 2px solid #313244; 
                border-bottom: 2px solid #313244; 
                outline: none;
                padding: 0px;
            }
            QListWidget::item { 
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 4px;
                margin: 4px; 
                min-width: 70px; max-width: 70px;
                min-height: 70px; max-height: 70px;
                           
            }
            QListWidget::item:selected { 
                background-color: #45475a; 
                border: 1px solid #89b4fa; 
            }

            /* 工具栏样式 */
            #Toolbar {
                background-color: #1D1F2E;
                border: 2px solid #313244;
                border-bottom: none; /* 与下方画布无缝连接 */
                min-height: 32;
                max-height: 32;
            }
            
            QPushButton {
                background-color: transparent; /* 平时透明，更有专业感 */
                border:none;
                padding: 0px;
                min-width: 24px;  /* 图标按钮建议设为固定正方形 */
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            
            QPushButton:hover { 
                background-color: #45475a; 
            }

            /* 关键：选中后的状态（类似 PS 的工具被按下） */
            QPushButton:checked {
                background-color: #10111C; /* 选中后的底色 */
                border: 1px solid #575757; /* 选中后的高亮边框 */
            }
        """)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 左侧：资源列表 ---
        self.frame_list = QListWidget()
        self.frame_list.setFixedWidth(82)
        
        self.frame_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.frame_list.setFlow(QListWidget.Flow.TopToBottom)
        self.frame_list.setMovement(QListWidget.Movement.Static)
        self.frame_list.setGridSize(QSize()) 
        self.frame_list.setWrapping(False) 
        self.frame_list.setResizeMode(QListWidget.ResizeMode.Fixed)
        self.frame_list.setSpacing(2) 
        self.frame_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frame_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(self.frame_list)

        # --- 右侧：工具栏 + 画布 ---
        right_container = QVBoxLayout()
        right_container.setSpacing(0) 

        # 1. 工具栏 (完全保留你的原始布局)
        self.toolbar = QFrame()
        self.toolbar.setObjectName("Toolbar")
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(5, 0, 5, 0)
        toolbar_layout.setSpacing(4)
        toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True) 

        self.btn_pick = QPushButton() 
        self.btn_pick.setCheckable(True) 
        self.btn_pick.setToolTip("选取工具")
        icon_path = os.path.join("assets", "icons", "btn_pick.svg")
        self.btn_pick.setIcon(QIcon(icon_path))
        self.btn_pick.setIconSize(QSize(16, 16)) 

        self.btn_slice = QPushButton() 
        self.btn_slice.setCheckable(True)
        icon_path = os.path.join("assets", "icons", "on_slice_clicked.svg")
        self.btn_slice.setIcon(QIcon(icon_path))
        self.btn_slice.setIconSize(QSize(16, 16)) 

        self.btn_clear = QPushButton("清空") 
        self.btn_save = QPushButton()
        icon_path = os.path.join("assets", "icons", "btn_save.svg")
        self.btn_save.setIcon(QIcon(icon_path))
        self.btn_save.setIconSize(QSize(16, 16))

        self.tool_group.addButton(self.btn_pick)
        self.tool_group.addButton(self.btn_slice)

        toolbar_layout.addWidget(self.btn_pick)
        toolbar_layout.addWidget(self.btn_slice)
        toolbar_layout.addWidget(self.btn_clear)
        toolbar_layout.addWidget(self.btn_save)

        # 2. 画布区
        self.scene = QGraphicsScene()
        self.view = ScalableView(self.scene) # 传入 self.scene
        self.view.setStyleSheet("border-top-left-radius: 0px; border-top-right-radius: 0px;")

        right_container.addWidget(self.toolbar)
        right_container.addWidget(self.view)
        
        main_layout.addLayout(right_container)

        self.selection_manager = SelectionManager(self.scene)
        self.set_connect()

    def set_connect(self):
        self.btn_pick.toggled.connect(self.selection_manager.set_active)
        self.btn_slice.clicked.connect(self.on_do_slice)
        self.frame_list.currentRowChanged.connect(self.switch_frame_preview)
        self.btn_save.clicked.connect(self.on_save_clicked)

    def on_save_clicked(self):
        """保存按钮逻辑"""
        if not self.current_frames:
            print("没有可保存的内容")
            return
        
        if not self.current_source_path:
            # 尝试从主窗口兜底获取一次
            p = self.window() # 获取顶层窗口
            if hasattr(p, 'asset_files') and p.asset_files:
                self.current_source_path = p.asset_files[0]
        
        if not self.current_source_path:
            print("找不到原始文件路径")
            return

        # 提取 pixmap 列表
        pixmaps = [f["pixmap"] for f in self.current_frames]
        
        # 现在 SliceLogic 已经有了这个方法
        save_dir = self.slice_logic.save_sliced_sprites(self.current_source_path, pixmaps)
        
        # 反馈日志到主界面控制台
        main_win = self.window()
        if hasattr(main_win, 'add_log'):
            main_win.add_log("-> 保存完成", "#a6e3a1")
            main_win.add_log(f"-> 文件夹:  {os.path.basename(save_dir)}", "#89b4fa")
        

    def display_image(self, file_path):
        """显示导入的精灵图并更新左侧列表 - 补全定义版"""
        if not os.path.exists(file_path): return
        
        pixmap = QPixmap(file_path)
        if pixmap.isNull(): return

        self.current_source_path = file_path
        # --- 1. 严格清理阶段 ---
        self.frame_list.blockSignals(True) # 阻塞信号防止连锁反应
        
        if self.preview_item:
            try: self.scene.removeItem(self.preview_item)
            except: pass
            self.preview_item = None

        self.scene.clear()
        self.frame_list.clear()
        self.current_frames = []
        
        if hasattr(self, 'selection_manager'):
            self.selection_manager.clear_selections()

        # --- 2. 画布加载 ---
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.FastTransformation) 
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        
        self.view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self.view.centerOn(self.pixmap_item)

        # --- 3. 补全 canvas 定义并生成缩略图 ---
        icon_area = 45 
        # 必须先定义 canvas 才能传给 QPainter
        canvas = QPixmap(icon_area, icon_area) 
        canvas.fill(Qt.GlobalColor.transparent)
        
        thumb = pixmap.scaled(icon_area, icon_area, 
                             Qt.AspectRatioMode.KeepAspectRatio, 
                             Qt.TransformationMode.SmoothTransformation)
        
        painter = QPainter(canvas)
        # 居中绘制缩略图
        painter.drawPixmap((icon_area - thumb.width()) // 2, (icon_area - thumb.height()) // 2, thumb)
        painter.end()
        
        item = QListWidgetItem()
        item.setIcon(QIcon(canvas)) # 现在 canvas 已定义
        item.setText(os.path.basename(file_path))
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.frame_list.addItem(item)
        
        self.frame_list.blockSignals(False)
        self.frame_list.setCurrentRow(0)

    def on_do_slice(self):
        bg_item = next((i for i in self.scene.items() 
                       if isinstance(i, QGraphicsPixmapItem) and not hasattr(i, 'is_clone')), None)
        if not bg_item: return

        rects = self.selection_manager.get_sorted_selections()
        if rects:
            self.current_frames = self.slice_logic.run_manual_slice(bg_item, rects)
        else:
            self.current_frames = self.slice_logic.run_auto_slice_to_preview(bg_item.pixmap())

        if self.current_frames:
            bg_item.setVisible(False) 
            self.selection_manager.clear_selections() 
            self.selection_manager.set_active(False) 
            self.btn_pick.setChecked(False) 
            self.update_frame_list_ui() 
            self.frame_list.setCurrentRow(0) 

    def update_frame_list_ui(self):
        self.frame_list.clear()
        for i, frame in enumerate(self.current_frames):
            pix = frame["pixmap"]
            item = QListWidgetItem(f"帧 {i:02d}")
            item.setSizeHint(QSize(78, 80)) 
            icon_pix = pix.scaled(45, 45, Qt.AspectRatioMode.KeepAspectRatio, 
                                 Qt.TransformationMode.SmoothTransformation)
            item.setIcon(QIcon(icon_pix))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.frame_list.addItem(item)

    def switch_frame_preview(self, index):
        if index < 0 or index >= len(self.current_frames): return
        pix = self.current_frames[index]["pixmap"]
        try:
            if not hasattr(self, 'preview_item') or self.preview_item is None:
                self.preview_item = QGraphicsPixmapItem()
                self.scene.addItem(self.preview_item)
            self.preview_item.setPixmap(pix)
            self.preview_item.setVisible(True)
            self.preview_item.setZValue(100)
            scene_rect = self.scene.sceneRect()
            self.preview_item.setPos(
                scene_rect.center().x() - pix.width() / 2,
                scene_rect.center().y() - pix.height() / 2
            )
        except (RuntimeError, AttributeError):
            self.preview_item = QGraphicsPixmapItem(pix)
            self.scene.addItem(self.preview_item)

    # 为了让 ScalableView 的 drop 生效，父级也需要接受 dragEnter
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

# 自定义视图类 (修正点 2：将渲染设置和拖拽逻辑放入此类)
class ScalableView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # --- 将原本在 ManualEditor 的设置挪到这里 ---
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(Qt.GlobalColor.transparent)
        
        # 开启画布级别的拖拽接收
        self.setAcceptDrops(True)
        
        self._is_panning = False
        self._last_mouse_pos = QPoint()

    # --- 修复点 3：实现画布区域专属的拖拽逻辑 ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            # 必须 accept，否则后续会报 drag leave before drag enter
            event.acceptProposedAction() 
            event.accept() 

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            event.accept()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                # 查找 ManualEditor 实例并加载
                p = self.parent()
                while p:
                    if hasattr(p, 'display_image'):
                        p.display_image(path)
                        # 重点：在这里也要同步更新主窗口的 asset_files，防止逻辑断层
                        # 如果你能获取到 main_window，最好把 main_window.asset_files 也设为 [path]
                        break
                    p = p.parent()
                event.acceptProposedAction()
                event.accept()

    def wheelEvent(self, event: QWheelEvent):
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)

    def mousePressEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            # 修改了判断方式，适应布局嵌套
            p = self.parent()
            while p:
                if hasattr(p, 'selection_manager'):
                    p.selection_manager.handle_press(scene_pos, event.modifiers())
                    break
                p = p.parent()
            event.accept()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())
        p = self.parent()
        while p:
            if hasattr(p, 'selection_manager'):
                p.selection_manager.handle_move(scene_pos)
                break
            p = p.parent()

        if self._is_panning:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.parent()
            while p:
                if hasattr(p, 'selection_manager'):
                    p.selection_manager.handle_release(scene_pos, event.modifiers())
                    break
                p = p.parent()
            event.accept()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        scene_pos = self.mapToScene(event.pos())
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.parent()
            while p:
                if hasattr(p, 'selection_manager'):
                    p.selection_manager.handle_double_click(scene_pos)
                    break
                p = p.parent()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)