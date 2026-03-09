import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTextEdit, QLabel, QStackedWidget)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QTextCursor, QTextBlockFormat, QTextCharFormat

from .utils import get_resource_path
from .widgets.preview_panel import PreviewPanel
from .logic_upload import UploadLogic 
from .logic_export import ExportLogic
# from .logic_slice import SliceLogic
from .widgets.manual_editor import ManualEditor

class BingoPacker(QMainWindow, UploadLogic, ExportLogic): 
    def __init__(self):
        super().__init__()
        # 还原原版核心变量名
        self.selected_folders = []
        self.asset_files = []
        
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        self.setWindowTitle("Bingo Sprite Packer")
        self.setFixedWidth(760)
        self.setFixedHeight(620)
        
        # 样式还原 - 严格遵守原始代码
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1e1e2e; color: #cdd6f4; }
            QTextEdit { 
                background-color: #181825; 
                border: 1px solid #313244; 
                border-radius: 10px; 
                padding: 5px; 
                           font-family: 'Consolas', 'Monaco', 'Menlo', 'Microsoft YaHei', 'PingFang SC', monospace;
                font-size: 14px;
            }
            QPushButton { border-radius: 6px; color: white; font-weight: bold; background-color: #313244; }
            QPushButton:hover { background-color: #45475a; }
        """)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.global_layout = QHBoxLayout(self.central_widget)
        self.global_layout.setContentsMargins(0, 0, 0, 0)
        self.global_layout.setSpacing(0)

        # --- 左侧主区 ---
        self.main_container = QWidget()
        self.main_container.setFixedWidth(760)
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(12)

        header = QLabel("BLOCKBINGO 资产打包工具")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #89b4fa; font-size: 22px; font-weight: bold;")
        main_layout.addWidget(header)

        # --- 核心切换容器 (QStackedWidget) ---
        self.left_stack = QStackedWidget()
        
        # 页面 0: 原始 Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("- 可直接点击导入或拖拽文件夹...")
        self.console.setStyleSheet("""
                QTextEdit { 
                    background-color: #181825; 
                    border: 1px solid #313244; 
                    border-radius: 10px; 
                    padding: 10px; 
                    color: #cdd6f4;
                    letter-spacing: 1px; 
                    line-height: 120%; 
                    font-family: 'Microsoft YaHei', 'PingFang SC', 'Consolas', monospace;
                    font-size: 14px;
                }
            """)
        self.left_stack.addWidget(self.console)

        # 页面 1: 编辑器占位
        self.editor_page = ManualEditor() # <--- 替换掉原来简单的 QWidget
        self.left_stack.addWidget(self.editor_page)

        main_layout.addWidget(self.left_stack)
        
        self.setup_bottom_buttons(main_layout)
        self.global_layout.addWidget(self.main_container)

        # --- 右侧预览区 ---
        self.preview_panel = PreviewPanel()
        self.preview_panel.setFixedWidth(0) 
        self.global_layout.addWidget(self.preview_panel)

    def setup_bottom_buttons(self, layout):
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        # 定义按钮 - 严格还原原始颜色和图标名
        self.btn_upload = self.make_btn(" 导入", "#313244", "#45475a", "pick_folders")
        self.btn_clear = self.make_btn(" 清空", "#313244", "#f38ba8", "clear_all")
        self.btn_slice = self.make_btn(" 裁切", "#313244", "#fab387", "on_slice_clicked")
        self.btn_preview = self.make_btn(" 预览", "#313244", "#a6e3a1", "toggle_side_preview")
        
        self.btn_bgs = self.make_btn("导出 .bgs", "#45b573", "#58ce87")
        self.btn_sprite = self.make_btn("导出 .sprite3", "#d9793d", "#e68a4d")

        for b in [self.btn_upload, self.btn_clear, self.btn_slice, self.btn_preview]:
            btn_layout.addWidget(b)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_bgs)
        btn_layout.addWidget(self.btn_sprite)
        
        layout.addLayout(btn_layout)

    def make_btn(self, text, bg, hover, icon=None):
        btn = QPushButton(text)
        if icon:
            path = get_resource_path(f"assets/icons/{icon}.svg")
            if os.path.exists(path): btn.setIcon(QIcon(path))
        btn.setStyleSheet(f"QPushButton {{ background-color: {bg}; padding: 8px 15px; border: none; }}"
                          f"QPushButton:hover {{ background-color: {hover}; }}")
        return btn

    def connect_signals(self):
        # 1. 基础功能
        self.btn_upload.clicked.connect(self.on_upload_folder)
        self.btn_clear.clicked.connect(self.on_clear_content)
        # self.btn_slice.clicked.connect(self.on_slice_clicked)
        self.btn_preview.clicked.connect(self.toggle_side_preview)

        # 2. 导出功能 - 严格连接到原始代码中对应的函数名
        # self.btn_bgs.clicked.connect(self.on_export_bgs)  
        self.btn_bgs.clicked.connect(self.on_export_bgs)    
        self.btn_sprite.clicked.connect(self.on_export_sprite3)

    # 供外部/PreviewPanel 调用的页面切换接口
    def toggle_editor_view(self):
        new_idx = 1 if self.left_stack.currentIndex() == 0 else 0
        self.left_stack.setCurrentIndex(new_idx)
        return new_idx == 1

    def toggle_side_preview(self):
        """侧边栏动画 - 严格复刻原始代码"""
        is_expanded = self.preview_panel.width() > 0
        target_p = 0 if is_expanded else 280
        target_w = 760 if is_expanded else 760 + 280

        self.anim_p = QPropertyAnimation(self.preview_panel, b"minimumWidth")
        self.anim_p_max = QPropertyAnimation(self.preview_panel, b"maximumWidth")
        self.anim_w = QPropertyAnimation(self, b"minimumWidth")
        self.anim_w_max = QPropertyAnimation(self, b"maximumWidth")

        for a in [self.anim_p, self.anim_p_max, self.anim_w, self.anim_w_max]:
            a.setDuration(300)
            a.setEasingCurve(QEasingCurve.OutCubic)
            a.setEndValue(target_w if a.targetObject() == self else target_p)

        self.anim_p.start(); self.anim_p_max.start()
        self.anim_w.start(); self.anim_w_max.start()
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    # 在 main_window.py 的 dropEvent 中修改
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            
            # 1. 如果是文件夹 -> 执行原有的打包逻辑
            if os.path.isdir(path):
                self.process_import_path(path)
                
            # 2. 如果是单张图片 -> 切换到编辑器并显示
            elif path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                # 切换到编辑器页面 (Index 1)
                self.left_stack.setCurrentIndex(1)
                # 加载图片
                if hasattr(self, 'editor_page'):
                    self.editor_page.display_image(path)
                self.add_log(f"-> 已载入图片: {os.path.basename(path)}", "#89b4fa")

