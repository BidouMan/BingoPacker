import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTextEdit, QLabel, QFrame)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QTextCursor
from .utils import get_resource_path

class BingoPacker(QMainWindow):
    def __init__(self):
        super().__init__()
        # 基础数据初始化（保持原版变量名）
        self.selected_folders = []
        self.selected_images = []
        self.asset_files = []
        
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        # 1. 窗口基础设置
        self.setWindowTitle("Bingo Sprite Packer")
        self.setFixedWidth(760)
        self.setFixedHeight(620)
        
        icon_path = get_resource_path("logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 2. 还原原版深色 QSS 样式
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1e1e2e; color: #cdd6f4; }
            QTextEdit { background-color: #181825; border: 1px solid #313244; border-radius: 10px; color: #cdd6f4; }
            QPushButton { border-radius: 6px; color: white; font-weight: bold; background-color: #313244; }
            QPushButton:hover { background-color: #45475a; }
            QScrollBar:vertical, QScrollBar:horizontal {width: 0px;height: 0px;background: transparent;}
        """)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.global_layout = QHBoxLayout(self.central_widget)
        self.global_layout.setContentsMargins(0, 0, 0, 0)
        self.global_layout.setSpacing(0)

        # --- A. 左侧主功能区 ---
        self.main_container = QWidget()
        self.main_container.setFixedWidth(760)
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        header = QLabel("BLOCKBINGO 资产打包工具")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #89b4fa; font-size: 24px; font-weight: bold;")
        main_layout.addWidget(header)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("可直接将文件夹拖拽至此处导入...")
        main_layout.addWidget(self.console)

        # 底部按钮栏
        self.setup_bottom_buttons(main_layout)
        
        self.global_layout.addWidget(self.main_container)

        # --- B. 右侧预览面板 (初始宽度为0，用于动画展开) ---
        self.preview_drawer = QFrame()
        self.preview_drawer.setFixedWidth(0)
        self.preview_drawer.setStyleSheet("background-color: #11111b; border-left: 2px solid #313244;")
        # 这里暂时留空，下一步填入 Widgets
        self.global_layout.addWidget(self.preview_drawer)

    def setup_bottom_buttons(self, parent_layout):
        button_layout = QHBoxLayout()
        # 按钮配置还原
        btns_config = [
            (" 导入", None, "#313244", "#45475a", "pick_folders"),
            (" 清空", None, "#313244", "#f38ba8", "clear_all"),
            (" 裁切", None, "#313244", "#fab387", "on_slice_clicked"),
            (" 预览", self.toggle_side_preview, "#313244", "#a6e3a1", "toggle_side_preview"),
            ("spacer", None, None, None, None), 
            ("导出 .bgs", None, "#45b573", "#58ce87", None),
            ("导出 .sprite3", None, "#d9793d", "#e68a4d", None)
        ]

        for text, func, bg, hover, icon_file in btns_config:
            if text == "spacer":
                button_layout.addStretch()
                continue
            btn = QPushButton(text)
            if icon_file:
                path = get_resource_path(f"assets/icons/{icon_file}.svg")
                if os.path.exists(path): btn.setIcon(QIcon(path))
            
            btn.setStyleSheet(f"QPushButton {{ background-color: {bg}; padding: 8px 12px; }} QPushButton:hover {{ background-color: {hover}; }}")
            if func: btn.clicked.connect(func)
            button_layout.addWidget(btn)
        
        parent_layout.addLayout(button_layout)

    def toggle_side_preview(self):
        """ 还原抽屉展开动画 """
        is_expanded = self.preview_drawer.width() > 0
        target_panel_w = 0 if is_expanded else 280
        target_win_w = 760 if is_expanded else 760 + 280

        self.anim_panel = QPropertyAnimation(self.preview_drawer, b"minimumWidth")
        self.anim_panel_max = QPropertyAnimation(self.preview_drawer, b"maximumWidth")
        self.anim_win = QPropertyAnimation(self, b"minimumWidth")
        self.anim_win_max = QPropertyAnimation(self, b"maximumWidth")

        for a in [self.anim_panel, self.anim_panel_max, self.anim_win, self.anim_win_max]:
            a.setDuration(300)
            a.setEasingCurve(QEasingCurve.OutCubic)
            a.setEndValue(target_win_w if a.targetObject() == self else target_panel_w)

        self.anim_panel.start(); self.anim_panel_max.start()
        self.anim_win.start(); self.anim_win_max.start()

    def add_log(self, msg, color="#cdd6f4"):
        log_html = f'<div style="color:{color}; line-height: 125%; margin-bottom: 4px;">{msg}</div>'
        self.console.append(log_html)
        self.console.moveCursor(QTextCursor.End)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()