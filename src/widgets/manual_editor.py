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
                border-radius: 0px; 
                border: 1px solid #313244; 
                outline: none;
                padding: 2px;
            }
            
            QListWidget::item { 
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 4px;
                margin: 2px;
                min-width: 70px; max-width: 70px;
                min-height: 70px; max-height: 70px;
                padding: 0px;
            }
            
            QListWidget::item:selected { 
                background-color: #45475a; 
                border: 1px solid #89b4fa; 
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.frame_list = QListWidget()

        self.frame_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frame_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frame_list.setFixedWidth(82) # 稍微加宽一点防止滚动条遮挡卡片
        
        # 核心布局模式
        self.frame_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.frame_list.setFlow(QListWidget.Flow.TopToBottom) # 确保图标在上文字在下
        self.frame_list.setMovement(QListWidget.Movement.Static)
        
        # --- 核心改动：禁止换行并开启省略号 ---
        self.frame_list.setWordWrap(False) # 禁用换行
        self.frame_list.setTextElideMode(Qt.TextElideMode.ElideRight) # 开启右侧省略号
        self.frame_list.setUniformItemSizes(True)
        # 关键：GridSize 必须大于 IconSize，留出的空间就是文字区域
        self.frame_list.setGridSize(QSize(78, 78))
        self.frame_list.setIconSize(QSize(45, 45)) # 图标区域控制在 90x90
        self.frame_list.setSpacing(0)


        layout.addWidget(self.frame_list)

        self.scene = QGraphicsScene()
        self.view = ScalableView(self.scene) 
        layout.addWidget(self.view)

    def display_image(self, file_path):
        if not os.path.exists(file_path): return
        
        pixmap = QPixmap(file_path)
        if pixmap.isNull(): return

        # 画布逻辑
        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.FastTransformation) 
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        self.view.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self.view.centerOn(self.pixmap_item)

        # 更新卡片
        self.frame_list.clear() 
        item = QListWidgetItem()
        
        # 居中缩略图合成 (45x45 区域)
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
        
        # 保持居中，AlignBottom 会配合 GridSize 自动留出边距
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
        
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