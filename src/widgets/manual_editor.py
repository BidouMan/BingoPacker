import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
                               QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QLabel,
                               QPushButton, QFrame,QButtonGroup, QAbstractItemView)
from PySide6.QtCore import Qt, QRectF, QPoint, QSize
from PySide6.QtGui import QPixmap, QWheelEvent, QPainter, QMouseEvent, QIcon
from .selection_manager import SelectionManager
from ..logic_slice import SliceLogic

class ManualEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.slice_logic = SliceLogic() # 初始化逻辑类
        self.current_frames = []        # 存储裁切后的帧数据: [{"pixmap": QPixmap, "rect": QRect}, ...]
        self.preview_item = None        # 用于显示单帧预览的 Item
        self.init_ui()

    def init_ui(self):
        # 整体 QSS 样式
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
        
        # 1. 基础模式
        self.frame_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.frame_list.setFlow(QListWidget.Flow.TopToBottom)
        self.frame_list.setMovement(QListWidget.Movement.Static)
        
        # 2. 彻底禁用网格对齐，允许 Item 自由重叠/裁剪
        # 将 GridSize 设为空，意味着由 Item 的 SizeHint 决定位置
        self.frame_list.setGridSize(QSize()) 
        
        # 3. 强制关闭换行和自适应留白
        self.frame_list.setWrapping(False) 
        self.frame_list.setResizeMode(QListWidget.ResizeMode.Fixed)
        self.frame_list.setSpacing(2) # 仅保留微小间距
        
        # 4. 滚动模式保持像素级
        # self.frame_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.frame_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frame_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        main_layout.addWidget(self.frame_list)


        # --- 右侧：工具栏 + 画布 ---
        right_container = QVBoxLayout()
        right_container.setSpacing(0) # 让工具栏和画布紧贴

        # 1. 工具栏
        self.toolbar = QFrame()
        self.toolbar.setObjectName("Toolbar")
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(5, 0, 5, 0)
        toolbar_layout.setSpacing(4)
        toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)


        # 添加占位按钮
        # 1. 创建工具组实现互斥选中
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True) # 开启互斥模式

        # 2. 设置“选取”按钮
        self.btn_pick = QPushButton() # 移除文字
        self.btn_pick.setCheckable(True) # 开启可选中状态
        # self.btn_pick.setChecked(True)   # 默认选中第一个
        self.btn_pick.setToolTip("选取工具")
        # 加载 SVG 图标
        icon_path = os.path.join("assets", "icons", "btn_pick.svg")
        self.btn_pick.setIcon(QIcon(icon_path))
        self.btn_pick.setIconSize(QSize(16, 16)) # 18px 在 32px 的工具栏里视觉最平衡

        # 3. 设置其他按钮（也要设为 Checkable 才能加入互斥组）
        self.btn_slice = QPushButton() # 假设缩短文字或也换成图标
        self.btn_slice.setCheckable(True)
        icon_path = os.path.join("assets", "icons", "on_slice_clicked.svg")
        self.btn_slice.setIcon(QIcon(icon_path))
        self.btn_slice.setIconSize(QSize(16, 16)) # 18px 在 32px 的工具栏里视觉最平衡


        self.btn_clear = QPushButton("清空") # 清空通常是触发式按钮，不需要 Checkable，可以不加进 group
        self.btn_save = QPushButton()
        icon_path = os.path.join("assets", "icons", "btn_save.svg")
        self.btn_save.setIcon(QIcon(icon_path))
        self.btn_slice.setIconSize(QSize(16, 16))

        # 4. 将需要互斥的工具加入组
        self.tool_group.addButton(self.btn_pick)
        self.tool_group.addButton(self.btn_slice)


        # 5. 添加到布局
        toolbar_layout.addWidget(self.btn_pick)
        toolbar_layout.addWidget(self.btn_slice)
        toolbar_layout.addWidget(self.btn_clear)
        toolbar_layout.addWidget(self.btn_save)

        # 2. 画布区
        self.scene = QGraphicsScene()
        self.view = ScalableView(self.scene)
        # 让画布稍微带一点顶部圆角
        self.view.setStyleSheet("border-top-left-radius: 0px; border-top-right-radius: 0px;")

        right_container.addWidget(self.toolbar)
        right_container.addWidget(self.view)
        
        main_layout.addLayout(right_container)

        self.selection_manager = SelectionManager(self.scene)

        self.set_connect()

    def set_connect(self):
        # 1. 选取工具开关
        self.btn_pick.toggled.connect(self.selection_manager.set_active)
        
        # 2. 绑定裁切按钮
        self.btn_slice.clicked.connect(self.on_do_slice)
        
        # 3. 绑定左侧列表切换
        self.frame_list.currentRowChanged.connect(self.switch_frame_preview)

    def display_image(self, file_path):
        """显示导入的精灵图并更新左侧列表"""
        if not os.path.exists(file_path): return
        
        pixmap = QPixmap(file_path)
        if pixmap.isNull(): return

        # --- 更新画布 ---
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.FastTransformation) 
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        
        self.view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self.view.centerOn(self.pixmap_item)

        # --- 更新左侧列表 ---
        self.frame_list.clear()
        item = QListWidgetItem()
        
        icon_area = 45 
        canvas = QPixmap(icon_area, icon_area)
        canvas.fill(Qt.GlobalColor.transparent)
        thumb = pixmap.scaled(icon_area, icon_area, 
                             Qt.AspectRatioMode.KeepAspectRatio, 
                             Qt.TransformationMode.SmoothTransformation)
        painter = QPainter(canvas)
        painter.drawPixmap((icon_area - thumb.width()) // 2, (icon_area - thumb.height()) // 2, thumb)
        painter.end()
        
        item.setIcon(QIcon(canvas))
        item.setText(os.path.basename(file_path))
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.frame_list.addItem(item)

    
    def on_do_slice(self):
        """裁切按钮逻辑：有选区则按选区裁，无选区则自动识别裁"""
        # 1. 找到底图对象
        bg_item = next((i for i in self.scene.items() 
                       if isinstance(i, QGraphicsPixmapItem) and not hasattr(i, 'is_clone')), None)
        if not bg_item:
            return

        # 2. 获取选区坐标
        rects = self.selection_manager.get_sorted_selections()
        
        if rects:
            # --- 情况 A: 存在手动选区 ---
            print("执行手动选区裁切...")
            self.current_frames = self.slice_logic.run_manual_slice(bg_item, rects)
        else:
            # --- 情况 B: 无选区，执行自动识别 ---
            print("未发现选区，执行智能自动识别...")
            # 我们需要把当前底图的 QPixmap 传给逻辑类进行分析
            self.current_frames = self.slice_logic.run_auto_slice_to_preview(bg_item.pixmap())

        # 3. 后续通用 UI 更新
        if self.current_frames:
            bg_item.setVisible(False) # 隐藏原图
            self.selection_manager.clear_selections() # 清理残留虚线框
            self.selection_manager.set_active(False) # 关闭选取模式
            self.btn_pick.setChecked(False) 
            
            self.update_frame_list_ui() # 更新左侧列表
            self.frame_list.setCurrentRow(0) # 默认选中第一帧预览

    def update_frame_list_ui(self):
        """将切好的帧显示在左侧 - 优化显示布局"""
        self.frame_list.clear()
        for i, frame in enumerate(self.current_frames):
            pix = frame["pixmap"]
            item = QListWidgetItem(f"帧 {i:02d}")
            
            # 设置固定尺寸，确保布局引擎不会因为文字长短产生额外偏移
            item.setSizeHint(QSize(78, 80)) 
            
            icon_pix = pix.scaled(45, 45, Qt.AspectRatioMode.KeepAspectRatio, 
                                 Qt.TransformationMode.SmoothTransformation)
            item.setIcon(QIcon(icon_pix))
            
            # 关键：确保文本对齐方式不会撑大 Item 区域
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            self.frame_list.addItem(item)

    def switch_frame_preview(self, index):
        """切换显示特定的帧 - 强力防崩溃版"""
        if index < 0 or index >= len(self.current_frames):
            return
            
        pix = self.current_frames[index]["pixmap"]

        # 检查 item 是否存在且未被 C++ 端销毁
        try:
            if not hasattr(self, 'preview_item') or self.preview_item is None:
                self.preview_item = QGraphicsPixmapItem()
                self.scene.addItem(self.preview_item)
            
            # 尝试操作，如果底层对象已删除会触发 RuntimeError
            self.preview_item.setPixmap(pix)
            self.preview_item.setVisible(True)
            self.preview_item.setZValue(100)
            
            # 居中逻辑
            scene_rect = self.scene.sceneRect()
            self.preview_item.setPos(
                scene_rect.center().x() - pix.width() / 2,
                scene_rect.center().y() - pix.height() / 2
            )
        except (RuntimeError, AttributeError):
            # 如果挂了，彻底重新生成一个
            self.preview_item = QGraphicsPixmapItem(pix)
            self.scene.addItem(self.preview_item)


# 自定义视图类 (ScalableView 保持不变)
class ScalableView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        self._is_panning = False
        self._last_mouse_pos = QPoint()

    def wheelEvent(self, event: QWheelEvent):
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)

    def mousePressEvent(self, event: QMouseEvent):
        # 转换坐标到 Scene 坐标系
        scene_pos = self.mapToScene(event.pos())
        
        if event.button() == Qt.MouseButton.LeftButton:
            # 只有当父级 ManualEditor 的选取工具激活时，才拦截
            if hasattr(self.parent(), 'selection_manager'):
                self.parent().selection_manager.handle_press(scene_pos, event.modifiers())
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
        
        if hasattr(self.parent(), 'selection_manager'):
            self.parent().selection_manager.handle_move(scene_pos)

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
            if hasattr(self.parent(), 'selection_manager'):
                # 增加了 modifiers 参数传递
                self.parent().selection_manager.handle_release(scene_pos, event.modifiers())
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
            if hasattr(self.parent(), 'selection_manager'):
                self.parent().selection_manager.handle_double_click(scene_pos)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)
    

    