import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTextEdit, QLabel, QFrame)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QTextCursor
from .utils import get_resource_path
from .widgets.asset_tree import AssetTree
from .widgets.preview_panel import PreviewPanel

class BingoPacker(QMainWindow):
    def __init__(self):
        super().__init__()
        # 基础数据初始化（保持原版变量名）
        self.selected_folders = []
        self.selected_images = []
        self.asset_files = []
        
        self.setAcceptDrops(True)
        self.init_ui()
        self.connect_signals()

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

        # 标题
        header = QLabel("BLOCKBINGO 资产打包工具")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #89b4fa; font-size: 24px; font-weight: bold;")
        main_layout.addWidget(header)

        # 1. 插入 AssetTree (新组件)
        # self.tree = AssetTree()
        # main_layout.addWidget(self.tree)

        # 2. 控制台 (日志输出)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("- 可直接将文件夹拖拽至此处导入...")
        main_layout.addWidget(self.console)

        # 底部按钮栏
        self.setup_bottom_buttons(main_layout)
        
        self.global_layout.addWidget(self.main_container)

        # --- B. 右侧预览面板 (直接实例化新组件) ---
        # 注意：这里不再创建 QFrame 然后 replace，直接创建 PreviewPanel
        self.preview_panel = PreviewPanel()
        self.preview_panel.setFixedWidth(0) # 初始宽度为0，用于点击“预览”按钮时展开
        self.global_layout.addWidget(self.preview_panel)


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
        is_expanded = self.preview_panel.width() > 0
        target_panel_w = 0 if is_expanded else 280
        target_win_w = 760 if is_expanded else 760 + 280

        self.anim_panel = QPropertyAnimation(self.preview_panel, b"minimumWidth")
        self.anim_panel_max = QPropertyAnimation(self.preview_panel, b"maximumWidth")
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

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            if os.path.isdir(path):
                # 模拟获取帧数，实际开发时这里要统计图片数量
                frame_count = len([f for f in os.listdir(path) if f.endswith(('.png', '.jpg'))])
                self.tree.add_asset(path, frame_count)
                self.add_log(f"成功导入资产: {os.path.basename(path)} ({frame_count} 帧)", "#a6e3a1")
    
    def connect_signals(self):
        """ 连接各个组件的信号 """
        # 当 tree 里的片段被点击时，告诉预览面板播哪一段
        # self.tree.segment_selected.connect(self.preview_panel.load_segment)
        
        # 示例：点击“导入”按钮时，手动往 tree 里加个东西看看效果
        # self.btn_import.clicked.connect(lambda: self.tree.add_asset_folder("测试角色", 20))
        pass