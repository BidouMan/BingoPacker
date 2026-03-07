import os
import zipfile
import json
from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QPushButton, 
                               QHBoxLayout, QWidget, QLineEdit, QLabel)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QIcon

class AssetTree(QTreeWidget):
    segment_selected = Signal(str, str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setIndentation(0)
        self.setAnimated(True)
        self.setAcceptDrops(True)
        
        # 强制隐藏滚动条
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.setStyleSheet("""
            QTreeWidget { 
                background-color: #181825; 
                border: 2px solid #313244; 
                border-radius: 12px;
                color: #cdd6f4;
                outline: none;
            }
            QTreeWidget::item { height: 40px; border-bottom: 1px solid #1e1e2e; }
            QTreeWidget::item:hover { background-color: #313244; }
            QTreeWidget::item:selected { background-color: #45475a; }
            
            /* 隐藏滚动条QSS补丁 */
            QScrollBar:vertical, QScrollBar:horizontal { width: 0px; height: 0px; }
        """)

    def add_asset(self, path):
        if not os.path.exists(path): return
        is_bundle = path.lower().endswith(('.bgs', '.sprite3'))
        name = os.path.basename(path)
        total_frames = self._calculate_frame_count(path)
        
        root_item = QTreeWidgetItem(self)
        root_item.setData(0, Qt.UserRole, {"path": path, "type": "root", "total": total_frames})
        
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 0, 10, 0)
        
        icon_str = "📦" if is_bundle else "📂"
        name_label = QLabel(f"{icon_str} {name}")
        name_label.setStyleSheet("font-weight: bold; color: #89b4fa; background: transparent;")
        
        add_btn = QPushButton("+")
        add_btn.setFixedSize(22, 22)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton { background-color: #313244; color: #a6adc8; border-radius: 6px; border: none; }
            QPushButton:hover { background-color: #89b4fa; color: #11111b; }
        """)
        add_btn.clicked.connect(lambda: self.add_segment(root_item, "新片段", 0, max(0, total_frames - 1)))
        
        layout.addWidget(name_label)
        layout.addStretch()
        layout.addWidget(add_btn)
        self.setItemWidget(root_item, 0, container)
        
        self.add_segment(root_item, "Default Loop", 0, max(0, total_frames - 1))
        root_item.setExpanded(True)

    def add_segment(self, parent_item, name, start, end):
        child = QTreeWidgetItem(parent_item)
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(25, 0, 10, 0)
        layout.setSpacing(6)
        
        # 1. 动画名称编辑框 (关键逻辑)
        name_edit = QLineEdit(name)
        name_edit.setFixedWidth(100)
        # 默认样式：像 Label 一样透明、无边框
        name_edit.setReadOnly(True)
        name_edit.setFocusPolicy(Qt.NoFocus)
        name_edit.setStyleSheet("""
            QLineEdit { 
                background: transparent; border: none; color: #cdd6f4; padding: 2px;
            }
        """)
        # 安装过滤器拦截双击
        name_edit.installEventFilter(self)
        # 失去焦点自动锁定
        name_edit.editingFinished.connect(lambda: self._lock_name_edit(name_edit))

        # 2. 帧数显示 (保持现状)
        start_edit = QLineEdit(str(start))
        start_edit.setFixedWidth(35)
        start_edit.setAlignment(Qt.AlignCenter)
        start_edit.setStyleSheet("background: #11111b; border: 1px solid #313244; color: #fab387; border-radius: 4px;")
        
        end_edit = QLineEdit(str(end))
        end_edit.setFixedWidth(35)
        end_edit.setAlignment(Qt.AlignCenter)
        end_edit.setStyleSheet("background: #11111b; border: 1px solid #313244; color: #fab387; border-radius: 4px;")
        
        layout.addWidget(QLabel("🎬"))
        layout.addWidget(name_edit)
        layout.addStretch()
        layout.addWidget(start_edit)
        layout.addWidget(QLabel("-"))
        layout.addWidget(end_edit)
        
        self.setItemWidget(child, 0, container)
        self.scrollToItem(child)
        return child

    def eventFilter(self, obj, event):
        """实现双击进入编辑模式"""
        if isinstance(obj, QLineEdit) and event.type() == QEvent.MouseButtonDblClick:
            self._unlock_name_edit(obj)
            return True
        return super().eventFilter(obj, event)

    def _unlock_name_edit(self, edit):
        """激活编辑状态"""
        edit.setReadOnly(False)
        edit.setFocusPolicy(Qt.StrongFocus)
        edit.setFocus()
        edit.selectAll()
        # 切换到高亮编辑样式
        edit.setStyleSheet("""
            QLineEdit { 
                background: #1e1e2e; border: 1px solid #89b4fa; color: #cdd6f4; border-radius: 4px; padding: 2px;
            }
        """)

    def _lock_name_edit(self, edit):
        """恢复只读状态并取消高亮"""
        # 1. 核心逻辑：取消文本选中高亮
        edit.deselect() 
        
        # 2. 状态锁定
        edit.setReadOnly(True)
        edit.setFocusPolicy(Qt.NoFocus)
        edit.clearFocus()
        
        # 3. 恢复静默样式
        edit.setStyleSheet("""
            QLineEdit { 
                background: transparent; 
                border: none; 
                color: #cdd6f4; 
                padding: 2px; 
            }
        """)

    def _calculate_frame_count(self, path):
        try:
            if os.path.isdir(path):
                valid_exts = ('.png', '.jpg', '.jpeg', '.webp')
                return len([f for f in os.listdir(path) if f.lower().endswith(valid_exts)])
            elif path.lower().endswith(('.bgs', '.sprite3')):
                with zipfile.ZipFile(path, 'r') as z:
                    return len([f for f in z.namelist() if f.lower().endswith(('.png', '.jpg', '.svg'))])
        except: return 1
        return 0

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self, event):
        for url in event.mimeData().urls(): self.add_asset(url.toLocalFile())