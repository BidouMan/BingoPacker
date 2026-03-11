from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QFrame, QPushButton, QButtonGroup
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
import os

class EditorUI:
    def setup_ui(self, widget: QWidget):
        widget.setStyleSheet("""
            QWidget { background-color: #282c34; color: #abb2bf; border: none; }
            QListWidget { background-color: #21252b; border-right: 1px solid #181a1f; padding: 5px; color: #ffffff; }
            QListWidget::item { background-color: #2c313a; border-radius: 4px; margin-bottom: 4px; padding: 5px; }
            QListWidget::item:selected { background-color: #3e4451; border: 1px solid #61afef; }
            QPushButton { background-color: #353b45; border: 1px solid #181a1f; border-radius: 4px; padding: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #3e4451; }
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部工具栏
        self.toolbar = QFrame()
        self.toolbar.setFixedHeight(40)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(5, 0, 5, 0)
        toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.btn_save = self._create_tool_btn("btn_save", "保存")
        self.btn_pick = self._create_tool_btn("btn_pick", "选取", checkable=True)
        self.btn_slice = self._create_tool_btn("on_slice_clicked", "裁切", checkable=True)
        self.btn_clear = QPushButton("清空")

        self.tool_group = QButtonGroup(widget)
        self.tool_group.addButton(self.btn_pick)
        self.tool_group.addButton(self.btn_slice)

        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addWidget(self.btn_pick)
        toolbar_layout.addWidget(self.btn_slice)
        toolbar_layout.addWidget(self.btn_clear)
        layout.addWidget(self.toolbar)

        # 内容区
        content_layout = QHBoxLayout()
        self.frame_list = QListWidget()
        self.frame_list.setFixedWidth(82)
        self.frame_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content_layout.addWidget(self.frame_list)
        self.canvas_layout = QVBoxLayout() # 给逻辑层留出的 Canvas 容器
        content_layout.addLayout(self.canvas_layout)
        
        layout.addLayout(content_layout)

    def _create_tool_btn(self, icon_name, tip, checkable=False):
        btn = QPushButton()
        btn.setToolTip(tip)
        # 注意图标路径可能需要调整
        icon_path = os.path.join("assets", "icons", f"{icon_name}.svg")
        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
        btn.setIconSize(QSize(16, 16))
        btn.setCheckable(checkable)
        return btn