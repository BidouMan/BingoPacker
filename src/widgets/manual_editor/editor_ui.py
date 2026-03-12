from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QFrame, QPushButton, QButtonGroup
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
import os

class EditorUI:
    def setup_ui(self, widget: QWidget):
        widget.setStyleSheet("""
            QWidget { background-color: #282c34; color: #abb2bf; border: none; }
            
            QListWidget { 
                background-color: #21252b; 
                border-right: 1px solid #181a1f; 
                outline: none; 
                padding: 0px; 
            }
            /* 强制 Item 内部边距和间距 */
            QListWidget::item { 
                background-color: #2c313a; 
                border-radius: 4px; 
                margin: 4px;
                color: #ffffff;
                /* 确保文字和图片有足够的间距 */
                padding: 2px; 
            }
            QListWidget::item:selected { 
                background-color: #3e4451; 
                border: 1px solid #61afef; 
            }
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

        self.btn_new_file = self._create_tool_btn("btn_new_file",'新建')
        self.btn_save = self._create_tool_btn("btn_save", "保存")
        self.btn_pick = self._create_tool_btn("btn_pick", "选取", checkable=True)
        self.btn_pick.setCheckable(True)
        self.btn_slice = self._create_tool_btn("on_slice_clicked", "裁切", checkable=True)
        self.btn_slice.setCheckable(True)
        self.btn_clear = QPushButton("清空")

        self.tool_group = QButtonGroup(widget)
        self.tool_group.addButton(self.btn_pick)
        self.tool_group.addButton(self.btn_slice)

        toolbar_layout.addWidget(self.btn_new_file)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addWidget(self.btn_pick)
        toolbar_layout.addWidget(self.btn_slice)
        toolbar_layout.addWidget(self.btn_clear)
        layout.addWidget(self.toolbar)

        # 内容区
        content_layout = QHBoxLayout()
        self.frame_list = QListWidget()
        
        # --- 核心 UI 修正点 ---
        self.frame_list.setFixedWidth(82)
        self.frame_list.setViewMode(QListWidget.IconMode) # 设为图标模式
        self.frame_list.setResizeMode(QListWidget.Adjust) # 自动调整
        self.frame_list.setMovement(QListWidget.Static)
        
        # 1. 显式设置图标尺寸（卡片内的图片大小）
        self.frame_list.setIconSize(QSize(48, 48)) 
        
        # 2. 设置网格尺寸：宽度74保证正好塞入82的容器(考虑margin)，高度也要接近74实现正方形感
        # 因为下方要写字，高度稍微给多一点点（例如 78）看起来会更像视觉上的正方形
        self.frame_list.setGridSize(QSize(74, 78)) 
        
        # 3. 彻底禁用并隐藏滚动条空间
        self.frame_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frame_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frame_list.verticalScrollBar().setFixedWidth(0)
        self.frame_list.verticalScrollBar().setStyleSheet("width: 0px; height: 0px;")
        
        content_layout.addWidget(self.frame_list)
        self.canvas_layout = QVBoxLayout()
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