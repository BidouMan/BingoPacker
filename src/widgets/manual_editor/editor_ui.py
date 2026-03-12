from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QFrame, QPushButton, QButtonGroup,
                               QLabel,QSlider,QCheckBox)
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
            /* 强制 Item 内部边距 and 间距 */
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

            /* --- 仅为新组件添加必要的样式，不触碰原有组件 --- */
            QSlider::groove:horizontal { border: 1px solid #181a1f; height: 4px; background: #353b45; border-radius: 2px; }
            QSlider::handle:horizontal { background: #89b4fa; width: 10px; height: 10px; margin: -3px 0; border-radius: 5px; }
            
            QCheckBox::indicator { 
                width: 14; 
                height: 14; 
                background-color: #353b45; 
                border: 1px solid #181a1f; 
                border-radius: 3px; 
                /* 核心：在默认状态就预留好 padding，防止切换时尺寸抖动 */
                padding: 2px; 
            }

            QCheckBox::indicator:hover { 
                background-color: #3e4451; 
            }

            /* 2. 选中状态只改背景和图片，不改尺寸相关属性 */
            QCheckBox::indicator:checked { 
                background-color: #89b4fa; 
                /* 引用你的 SVG */
                image: url(assets/icons/magic_wand_select.svg);
            }
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部工具栏
        self.toolbar = QFrame()
        self.toolbar.setFixedHeight(35)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(5, 0, 5, 0)
        toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # 基础按钮 - 严格保持你的原始定义（不限制 size，不改文字）
        self.btn_new_file = self._create_tool_btn("btn_new_file",'新建')
        self.btn_save = self._create_tool_btn("btn_save", "保存")
        self.btn_magic_wand = self._create_tool_btn("btn_magic_wand", "选取", checkable=True)
        self.btn_pick = self._create_tool_btn("btn_pick", "选取", checkable=True)
        self.btn_slice = self._create_tool_btn("on_slice_clicked", "裁切", checkable=True)
        self.btn_cut= self._create_tool_btn("btn_cut", "调整画布", checkable=True)

        self.tool_group = QButtonGroup(widget)
        self.tool_group.addButton(self.btn_magic_wand)
        self.tool_group.addButton(self.btn_pick)
        self.tool_group.addButton(self.btn_slice)

        toolbar_layout.addWidget(self.btn_new_file)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addWidget(self.btn_magic_wand)
        toolbar_layout.addWidget(self.btn_pick)
        toolbar_layout.addWidget(self.btn_slice)
        toolbar_layout.addWidget(self.btn_cut)

        # --- 插入弹簧实现右对齐 ---
        toolbar_layout.addStretch()

        # --- 魔棒工具选项面板 ---
        self.magic_wand_panel = QWidget()
        self.magic_wand_panel.setVisible(False)
        mw_layout = QHBoxLayout(self.magic_wand_panel)
        mw_layout.setContentsMargins(0, 0, 0, 0)
        mw_layout.setSpacing(4)

        # 新增按钮也遵循全局 QPushButton 样式（自动撑开尺寸）
        self.btn_expand = QPushButton("扩")
        self.btn_shrink = QPushButton("缩")
        self.btn_invert = QPushButton("反")
        
        # 容差滑动条与百分比
        mw_layout.addWidget(QLabel("容差"))
        
        self.slider_tolerance = QSlider(Qt.Orientation.Horizontal)
        self.slider_tolerance.setRange(0, 255)
        self.slider_tolerance.setValue(25)
        self.slider_tolerance.setFixedWidth(80)
        mw_layout.addWidget(self.slider_tolerance)

        self.lbl_tolerance_val = QLabel("10%")
        self.lbl_tolerance_val.setFixedWidth(35)
        mw_layout.addWidget(self.lbl_tolerance_val)

        self.check_contiguous = QCheckBox("连续")
        mw_layout.addWidget(self.check_contiguous)

        mw_layout.addSpacing(20)
        mw_layout.addWidget(self.btn_expand)
        mw_layout.addWidget(self.btn_shrink)
        mw_layout.addWidget(self.btn_invert)
        

        toolbar_layout.addWidget(self.magic_wand_panel)
        layout.addWidget(self.toolbar)

        # 内容区 (严格保持你提供的代码，不改动任何尺寸)
        content_layout = QHBoxLayout()
        self.frame_list = QListWidget()
        self.frame_list.setFixedWidth(82)
        self.frame_list.setViewMode(QListWidget.IconMode) 
        self.frame_list.setResizeMode(QListWidget.Adjust) 
        self.frame_list.setMovement(QListWidget.Static)
        self.frame_list.setIconSize(QSize(48, 48)) 
        self.frame_list.setGridSize(QSize(74, 78)) 
        self.frame_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frame_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frame_list.verticalScrollBar().setFixedWidth(0)
        self.frame_list.verticalScrollBar().setStyleSheet("width: 0px; height: 0px;")
        # self.frame_list.installEventFilter(self)
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