import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                               QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QLabel)
from PySide6.QtCore import Qt, QRectF,QPoint
from PySide6.QtGui import QPixmap, QWheelEvent,QPainter,QMouseEvent

class ManualEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #181825; color: #cdd6f4; border: none; }
            QListWidget { background-color: #1e1e2e; border-radius: 10px; border: 1px solid #313244; }
            QGraphicsView { background-color: #11111b; border-radius: 10px; border: 1px solid #313244; }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 左侧列表：用于显示切割后的帧
        self.frame_list = QListWidget()
        self.frame_list.setFixedWidth(140)
        layout.addWidget(self.frame_list)

        # 右侧：画布区
        self.scene = QGraphicsScene()
        self.view = ScalableView(self.scene) # 使用自定义的可缩放视图
        layout.addWidget(self.view)

    def display_image(self, file_path):
        """显示导入的精灵图"""
        if not os.path.exists(file_path): return
        
        pixmap = QPixmap(file_path)
        if pixmap.isNull(): return

        self.scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        # 针对像素画，设置平滑缩放为 False，保持硬轮廓
        self.pixmap_item.setTransformationMode(Qt.FastTransformation) 
        
        self.scene.addItem(self.pixmap_item)
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        
        # 视图自动适应图片大小并居中
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.view.centerOn(self.pixmap_item)

# 自定义视图类，支持滚轮缩放画布
class ScalableView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        
        # 1. 彻底去掉滚动条
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 2. 渲染设置：保持像素硬轮廓，不启用抗锯齿
        self.setRenderHint(QPainter.Antialiasing, False)
        
        # 3. 设置拖拽模式为无（我们将通过中键手动接管）
        self.setDragMode(QGraphicsView.NoDrag)
        
        # 4. 缩放中心锚点设置
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        # 用于记录中键拖拽状态
        self._is_panning = False
        self._last_mouse_pos = QPoint()

    def wheelEvent(self, event: QWheelEvent):
        """缩放功能：保持不变"""
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下：识别中键"""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._last_mouse_pos = event.pos()
            # 改变光标为抓取手势
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动：实现画布位移"""
        if self._is_panning:
            # 计算位移差
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()
            
            # 手动调整滚动条数值（即使滚动条隐藏了，内部数值依然有效）
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标松开：恢复状态"""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)