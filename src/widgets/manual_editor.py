import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
                               QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QLabel)
from PySide6.QtCore import Qt, QRectF, QPoint, QSize
from PySide6.QtGui import QPixmap, QWheelEvent, QPainter, QMouseEvent, QIcon

class ManualEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # 优化 QSS：通过强制宽高锁定正方形
        self.setStyleSheet("""
            QWidget { background-color: #181825; color: #cdd6f4; border: none; }
            
            QListWidget { 
                background-color: #1e1e2e; 
                border-radius: 10px; 
                border: 1px solid #313244; 
                outline: none;
                padding: 10px;
            }
            
            QListWidget::item { 
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 8px;
                margin: 5px;
                /* 锁定正方形尺寸 */
                min-width: 120px; max-width: 120px;
                min-height: 120px; max-height: 120px;
            }
            
            QListWidget::item:selected { 
                background-color: #45475a; 
                border: 2px solid #89b4fa; 
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.frame_list = QListWidget()
        self.frame_list.setFixedWidth(180) # 稍微加宽一点防止滚动条遮挡卡片
        
        # 核心布局模式
        self.frame_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.frame_list.setFlow(QListWidget.Flow.TopToBottom) # 确保图标在上文字在下
        self.frame_list.setMovement(QListWidget.Movement.Static)
        
        # 关键：GridSize 必须大于 IconSize，留出的空间就是文字区域
        self.frame_list.setGridSize(QSize(130, 130))
        self.frame_list.setIconSize(QSize(90, 90)) # 图标区域控制在 90x90
        self.frame_list.setWordWrap(True) 

        layout.addWidget(self.frame_list)

        self.scene = QGraphicsScene()
        self.view = ScalableView(self.scene) 
        layout.addWidget(self.view)

    def display_image(self, file_path):
        """显示导入的精灵图并更新左侧列表"""
        if not os.path.exists(file_path): return
        
        pixmap = QPixmap(file_path)
        if pixmap.isNull(): return

        # 1. 更新画布显示 (保持不变)
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.FastTransformation) 
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        self.view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self.view.centerOn(self.pixmap_item)

        # 2. 更新左侧卡片列表
        self.frame_list.clear() 
        item = QListWidgetItem()
        
        # --- 居中处理关键步骤 ---
        canvas_size = 90  # 对应 setIconSize
        # 创建一个透明的 90x90 正方形画布
        center_canvas = QPixmap(canvas_size, canvas_size)
        center_canvas.fill(Qt.GlobalColor.transparent)
        
        # 生成等比缩小的原始缩略图
        thumb = pixmap.scaled(canvas_size, canvas_size, 
                             Qt.AspectRatioMode.KeepAspectRatio, 
                             Qt.TransformationMode.SmoothTransformation)
        
        # 将缩略图绘制在透明画布的中心
        painter = QPainter(center_canvas)
        x = (canvas_size - thumb.width()) // 2
        y = (canvas_size - thumb.height()) // 2
        painter.drawPixmap(x, y, thumb)
        painter.end()
        
        item.setIcon(QIcon(center_canvas))
        # ----------------------

        file_name = os.path.basename(file_path)
        item.setText(file_name)
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        
        self.frame_list.addItem(item)

# 自定义视图类
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
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._last_mouse_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)