import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
                               QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QLabel,
                               QPushButton, QFrame,QGraphicsItem, QButtonGroup)
from PySide6.QtCore import Qt, QRectF, QPoint, QSize,Signal
from PySide6.QtGui import QPixmap, QWheelEvent, QPainter, QMouseEvent, QIcon, QDragEnterEvent, QDropEvent,QBrush,QColor,QTransform
from .selection_manager import SelectionManager
from ..logic_slice import SliceLogic
from .asset_loader import AssetLoader

class ManualEditor(QWidget):
    update_assets_data = Signal(str, list)
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
        # --- 1. QSS 样式 (保持不动) ---
        self.setStyleSheet("""
            QWidget { background-color: #282c34; color: #abb2bf; border: none; }
            
            /* 左侧列表区 */
            QListWidget { 
                background-color: #21252b; 
                border-right: 1px solid #181a1f; 
                outline: none; 
                padding: 5px;
                color: #ffffff; /* 强制未选中状态下文字为白色 */
            }
            QListWidget::item { 
                background-color: #2c313a; 
                border-radius: 4px; 
                margin-bottom: 4px; 
                padding: 5px;
                color: #ffffff; /* 确保 item 内部文字也是白色 */
            }
            QListWidget::item:selected { 
                background-color: #3e4451; 
                border: 1px solid #61afef;
                color: #ffffff; /* 选中时文字依然为白色 */
            }
            QGraphicsView { background-color: #181a1f; border: none; }
            QPushButton { background-color: #353b45; border: 1px solid #181a1f; border-radius: 4px; padding: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #3e4451; }
            QPushButton:pressed { background-color: #282c34; }
        """)

        # 主布局改为垂直布局：上工具栏，下内容区
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # --- 2. 顶部：工具栏 (Toolbar) ---
        self.toolbar = QFrame()
        self.toolbar.setObjectName("Toolbar")
        self.toolbar.setFixedHeight(40) # 固定高度让顶部更整洁
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(5, 0, 5, 0)
        toolbar_layout.setSpacing(4)
        toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        

        # 按钮初始化 
        
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)

        self.btn_new_file = QPushButton() 
        self.btn_new_file.setToolTip("选取工具")
        self.btn_new_file.setIcon(QIcon(os.path.join("assets", "icons", "btn_new_file.svg")))
        self.btn_new_file.setIconSize(QSize(16, 16)) 

        self.btn_clear = QPushButton("清空") 
        self.btn_save = QPushButton()
        self.btn_save.setToolTip("保存")
        self.btn_save.setIcon(QIcon(os.path.join("assets", "icons", "btn_save.svg")))
        self.btn_save.setIconSize(QSize(16, 16))

        self.btn_pick = QPushButton() 
        self.btn_pick.setToolTip("选取工具")
        self.btn_pick.setIcon(QIcon(os.path.join("assets", "icons", "btn_pick.svg")))
        self.btn_pick.setIconSize(QSize(16, 16)) 
        self.btn_pick.setCheckable(True)

        self.btn_slice = QPushButton() 
        self.btn_slice.setToolTip("裁切工具")
        self.btn_slice.setIcon(QIcon(os.path.join("assets", "icons", "on_slice_clicked.svg")))
        self.btn_slice.setIconSize(QSize(16, 16)) 
        self.btn_slice.setCheckable(True)

        # --------- 预计添加功能 -------------
        # 修改画布大小/魔棒工具/

        
        self.tool_group.addButton(self.btn_pick)
        self.tool_group.addButton(self.btn_slice)

        toolbar_layout.addWidget(self.btn_new_file)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addWidget(self.btn_pick)
        toolbar_layout.addWidget(self.btn_slice)
        toolbar_layout.addWidget(self.btn_clear)
        
        
        outer_layout.addWidget(self.toolbar)

        # --- 3. 下部：内容区域 (Content Area) ---
        content_container = QHBoxLayout()
        content_container.setSpacing(0)

        # 左侧：资源列表
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
        
        # 右侧：画布区
        self.scene = QGraphicsScene()
        self.view = ScalableView(self.scene)
        
        content_container.addWidget(self.frame_list)
        content_container.addWidget(self.view)
        
        outer_layout.addLayout(content_container)

        # --- 4. 后续初始化 ---
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
        if not os.path.exists(file_path): return
        pixmap = QPixmap(file_path)
        if pixmap.isNull(): return

        self.current_source_path = file_path
        self.frame_list.blockSignals(True)
        
        self.scene.clear()
        self.frame_list.clear()
        self.current_frames = []

        # 创建棋盘格
        self.view.checker_item = CheckerboardItem(QRectF(0, 0, pixmap.width(), pixmap.height()))
        self.scene.addItem(self.view.checker_item)

        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        # --- 核心修改：使用 FastTransformation 保证像素不模糊 ---
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.FastTransformation) 
        self.scene.addItem(self.pixmap_item)
        self.pixmap_item.setZValue(0)
        
        self.scene.setSceneRect(QRectF(0, 0, pixmap.width(), pixmap.height()))
        self.view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

        # 缩略图逻辑：列表里的预览可以保留平滑，否则太小的像素看不清
        icon_area = 45 
        canvas = QPixmap(icon_area, icon_area) 
        canvas.fill(Qt.GlobalColor.transparent)
        thumb = pixmap.scaled(icon_area, icon_area, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        painter = QPainter(canvas)
        painter.drawPixmap((icon_area - thumb.width()) // 2, (icon_area - thumb.height()) // 2, thumb)
        painter.end()
        
        item = QListWidgetItem()
        item.setIcon(QIcon(canvas)) 
        item.setText(os.path.basename(file_path))
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.frame_list.addItem(item)
        
        
        self.frame_list.blockSignals(False)
        self.frame_list.setCurrentRow(0)
        self.sync_to_preview()

        name = os.path.basename(file_path)
        single_frame = [{"pixmap": self.current_pixmap, "rect": self.current_pixmap.rect()}]
        
        # --- 发送给 AssetTree ---
        self.update_assets_data.emit(name, single_frame)


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
            # --- 彻底清理旧状态 ---
            if hasattr(self, 'preview_item') and self.preview_item:
                self.scene.removeItem(self.preview_item)
                self.preview_item = None
            
            # 隐藏底图
            bg_item = next((i for i in self.scene.items() if isinstance(i, QGraphicsPixmapItem) and not hasattr(i, 'is_clone')), None)
            if bg_item: bg_item.setVisible(False)

            self.selection_manager.clear_selections()
            self.selection_manager.set_active(False)

            # --- 强制刷新场景和棋盘格 ---
            first_pix = self.current_frames[0]["pixmap"]
            new_rect = QRectF(0, 0, first_pix.width(), first_pix.height())
            
            # 1. 更新场景尺寸
            self.scene.setSceneRect(new_rect)
            
            # 2. 更新棋盘格：先移除再添加或重设，确保 ID 更新
            if hasattr(self.view, 'checker_item'):
                # 这种做法比 scene.clear() 更安全，因为它只动棋盘格
                self.view.checker_item.set_rect(new_rect)

            self.update_frame_list_ui()

            source_name = os.path.basename(self.current_source_path) if self.current_source_path else "Manual_Slice"
            self.update_assets_data.emit(source_name, self.current_frames)
            self.frame_list.setCurrentRow(0)
            self.switch_frame_preview(0) # 内部会执行 fitInView
                    
    def sync_to_preview(self):
        """裁切完成后，只推送数据"""
        main_win = self.window()
        if hasattr(main_win, 'preview_panel'):
            # 统一调用这个接口
            # 注意：传入的是纯 pixmap 列表
            pixmaps = [f["pixmap"] for f in self.current_frames]
            main_win.preview_panel.load_frames_to_preview(pixmaps)

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
        new_rect = QRectF(0, 0, pix.width(), pix.height())

        self.scene.setSceneRect(new_rect)

        # 如果棋盘格丢失则重建
        if not self.view.checker_item:
            self.view.checker_item = CheckerboardItem(new_rect)
            self.scene.addItem(self.view.checker_item)
        else:
            self.view.checker_item.set_rect(new_rect)

        # --- 核心修复：如果 preview_item 为 None (被 clear 删了)，则新建 ---
        if self.preview_item is None:
            self.preview_item = QGraphicsPixmapItem()
            self.preview_item.setZValue(1) # 确保在棋盘格上方
            self.scene.addItem(self.preview_item)
        
        # 此时 self.preview_item 一定是一个有效的 C++ 对象
        self.preview_item.setPixmap(pix)
        self.preview_item.setPos(0, 0)
        self.preview_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        self.preview_item.setVisible(True)

        self.view.fitInView(new_rect, Qt.AspectRatioMode.KeepAspectRatio)

    # 为了让 ScalableView 的 drop 生效，父级也需要接受 dragEnter
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    # 在 manual_editor.py 的 ManualEditor 类中添加
    def load_bundle_file(self, file_path):
        """处理拖入的文件（图片或包）"""
        if not os.path.exists(file_path): return
        
        self.frame_list.blockSignals(True)
        
        # --- 核心修复：清理阶段 ---
        self.scene.clear()          # 这会销毁 C++ 层的 preview_item
        self.preview_item = None    # 必须手动同步 Python 层的引用，设为 None
        self.view.checker_item = None # 棋盘格同理，也被 clear 删了，设为 None
        
        self.frame_list.clear()
        self.current_frames = []
        self.current_source_path = file_path

        # 加载资源 (假设你已经用了 AssetLoader 或者之前的逻辑)
        frames = AssetLoader.load_resource(file_path) # 或者你之前的逻辑

        if frames:
            self.current_frames = frames
            self.update_frame_list_ui()

            name = os.path.basename(file_path)
            self.update_assets_data.emit(name, self.current_frames)
            print(f"DEBUG: ManualEditor 已发出数据更新信号: {name}")
            # 重新初始化棋盘格 (因为场景被清空了)
            first_pix = frames[0]["pixmap"]
            rect = QRectF(0, 0, first_pix.width(), first_pix.height())
            self.view.checker_item = CheckerboardItem(rect)
            self.scene.addItem(self.view.checker_item)
            
            # 选中并显示第一帧
            self.frame_list.setCurrentRow(0)
            self.switch_frame_preview(0)

        
        self.frame_list.blockSignals(False)
# 自定义视图类 (修正点 2：将渲染设置和拖拽逻辑放入此类)
class ScalableView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # --- 将原本在 ManualEditor 的设置挪到这里 ---
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(Qt.GlobalColor.transparent)
        
        self.setBackgroundBrush(QColor(30, 33, 39)) # 设置默认的 PS 深灰色背景
        
        # 初始化棋盘格管理
        self.checker_item = None
        # 开启画布级别的拖拽接收
        self.setAcceptDrops(True)
        
        self._is_panning = False
        self._last_mouse_pos = QPoint()

    def update_checkerboard(self, pixmap_rect):
        """当图片载入或变化时，更新棋盘格的大小"""
        self.checker_item.set_rect(pixmap_rect)
 
    # --- 修复点 3：实现画布区域专属的拖拽逻辑 ---
    # 在 manual_editor.py 修改 ScalableView 类

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            for url in urls:
                file_path = url.toLocalFile()
                # 在这里增加对 .bgs 和 .sprite3 的判断
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bgs', '.sprite3')):
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if not urls: return
        
        file_path = urls[0].toLocalFile()
        
        # 获取 ManualEditor
        editor = self.window().findChild(ManualEditor)
        if not editor:
            p = self.parent()
            while p and not isinstance(p, ManualEditor): p = p.parent()
            editor = p

        if editor:
            # 不管什么后缀，直接丢给加载函数，Loader 会自己判断
            editor.load_bundle_file(file_path)
                
        event.acceptProposedAction()


    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
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
        painter.setClipRect(self.rect)
        
        # 获取当前缩放倍率
        scale = painter.worldTransform().m11()
        
        # --- 核心改进：非线性视觉对齐 ---
        # 1. 计算理想逻辑尺寸（目标是视觉上看起来约 16px）
        target_side = 16.0 / scale
        
        # 2. 只有在放大到“逻辑尺寸小于1像素”时，才强制锁定为1.0
        # 否则，我们让它保持在 target_side，但进行“步进式”取整，防止缩放时的细微抖动
        if target_side < 1.0:
            side = 1.0
        else:
            # 使用简单的取整或者保留 0.5 步长，能让缩放看起来更平滑
            side = round(target_side)
            if side < 1: side = 1

        # 获取设备像素比
        dpr = widget.devicePixelRatioF() if widget else 1.0
        
        # 只有在 side 发生显著变化时才更新纹理缓存，减少计算量
        if self._cached_pixmap is None or abs(self._last_side - side) > 0.1:
            self._last_side = side
            
            # 物理像素尺寸
            phys_side = max(1, int(side * dpr))
            tile = QPixmap(phys_side * 2, phys_side * 2)
            tile.setDevicePixelRatio(dpr)
            tile.fill(self.color2)
            
            tp = QPainter(tile)
            # 在纹理内部，我们要画 side 长度的格子
            tp.fillRect(0, 0, int(side), int(side), self.color1)
            tp.fillRect(int(side), int(side), int(side), int(side), self.color1)
            tp.end()
            self._cached_pixmap = tile

        brush = QBrush(self._cached_pixmap)
        
        # 坐标对齐：确保起始点精确对齐到图片的 (0,0)
        brush_tx = QTransform()
        brush_tx.translate(self.rect.x(), self.rect.y())
        brush.setTransform(brush_tx)

        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)
        # 像素软件中，棋盘格本身关闭抗锯齿会更干净
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.drawRect(self.rect)
        painter.restore()