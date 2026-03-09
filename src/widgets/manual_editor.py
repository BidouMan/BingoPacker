import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
                               QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QLabel,
                               QPushButton, QFrame,QButtonGroup)
from PySide6.QtCore import Qt, QRectF, QPoint, QSize
from PySide6.QtGui import QPixmap, QWheelEvent, QPainter, QMouseEvent, QIcon
from .selection_manager import SelectionManager


class ManualEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
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
        self.frame_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frame_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frame_list.setFixedWidth(82) 
        
        self.frame_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.frame_list.setFlow(QListWidget.Flow.TopToBottom)
        self.frame_list.setMovement(QListWidget.Movement.Static)
        self.frame_list.setWordWrap(False)
        self.frame_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.frame_list.setUniformItemSizes(True)
        self.frame_list.setGridSize(QSize(78, 72)) 
        self.frame_list.setIconSize(QSize(45, 45)) 

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
        self.btn_auto = QPushButton() # 假设缩短文字或也换成图标
        self.btn_auto.setCheckable(True)
        icon_path = os.path.join("assets", "icons", "on_slice_clicked.svg")
        self.btn_auto.setIcon(QIcon(icon_path))
        self.btn_auto.setIconSize(QSize(16, 16)) # 18px 在 32px 的工具栏里视觉最平衡


        self.btn_clear = QPushButton("清空") # 清空通常是触发式按钮，不需要 Checkable，可以不加进 group

        # 4. 将需要互斥的工具加入组
        self.tool_group.addButton(self.btn_pick)
        self.tool_group.addButton(self.btn_auto)


        # 5. 添加到布局
        toolbar_layout.addWidget(self.btn_pick)
        toolbar_layout.addWidget(self.btn_auto)
        toolbar_layout.addWidget(self.btn_clear)

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
        # 绑定选取功能
        self.btn_pick.toggled.connect(self.selection_manager.set_active)

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