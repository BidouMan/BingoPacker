import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTextEdit, QLabel, QStackedWidget)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QTextCursor, QTextBlockFormat, QTextCharFormat

from .utils import get_resource_path
from .widgets.preview_panel import PreviewPanel
from .logic_upload import UploadLogic 
from .logic_export import ExportLogic
from .logic_slice import SliceLogic
from .widgets.manual_editor import ManualEditor

class BingoPacker(QMainWindow, UploadLogic, ExportLogic,SliceLogic): 
    def __init__(self):
        super().__init__()
        # 还原原版核心变量名
        self.selected_folders = []
        self.asset_files = []
        
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        self.setWindowTitle("Bingo Sprite Packer")
        # --- 布局优化：既然预览面板常驻(280px)，主窗口总宽度应适当增加 ---
        # 原左侧 760 + 右侧 280 = 1040。如果你希望维持原感，建议设为 1040
        self.setFixedWidth(1040) 
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
        self.main_container.setFixedWidth(760) # 保持原左侧区域宽度不变
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

        # 页面 1: 编辑器
        self.editor_page = ManualEditor()
        self.left_stack.addWidget(self.editor_page)

        main_layout.addWidget(self.left_stack)
        
        # --- 启动状态设置 ---
        self.left_stack.setCurrentIndex(1) # 默认显示编辑器
        
        self.setup_bottom_buttons(main_layout)
        self.global_layout.addWidget(self.main_container)

        # --- 右侧预览区 (常驻显示) ---
        self.preview_panel = PreviewPanel()
        # 关键修改：移除 setFixedWidth(0)，确保它以其内部定义的 280 宽度显示
        self.preview_panel.setVisible(True) 
        self.global_layout.addWidget(self.preview_panel)

    def setup_bottom_buttons(self, layout):
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        # 定义按钮 - 严格还原原始颜色和图标名
        self.btn_upload = self.make_btn(" 导入", "#313244", "#89b4fa", "pick_folders")
        self.btn_clear = self.make_btn(" 清空", "#313244", "#89b4fa", "clear_all")
        self.btn_editor = self.make_btn(' 编辑',"#313244", "#89b4fa", "btn_editor")
        self.btn_slice = self.make_btn(" 裁切", "#313244", "#89b4fa", "on_slice_clicked")
        self.btn_preview = self.make_btn(" 预览", "#313244", "#89b4fa", "toggle_side_preview")
        
        self.btn_bgs = self.make_btn("导出 .bgs", "#45b573", "#58ce87")
        self.btn_sprite = self.make_btn("导出 .sprite3", "#d9793d", "#e68a4d")

        for b in [self.btn_upload, self.btn_clear, self.btn_editor,self.btn_slice, self.btn_preview]:
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
        self.btn_editor.clicked.connect(self.toggle_editor_view)
        # self.btn_editor.clicked.connect(self.toggle_side_preview)
        self.btn_slice.clicked.connect(self.on_slice_clicked)
        # self.btn_preview.clicked.connect(self.toggle_side_preview)

        # 2. 导出功能 - 严格连接到原始代码中对应的函数名
        self.btn_bgs.clicked.connect(self.on_export_bgs)    
        self.btn_sprite.clicked.connect(self.on_export_sprite3)

        self.editor_page.slice_completed.connect(self.preview_panel.asset_tree.add_editor_source)

    # 供外部/PreviewPanel 调用的页面切换接口
    def toggle_editor_view(self):
        new_idx = 1 if self.left_stack.currentIndex() == 0 else 0
        self.left_stack.setCurrentIndex(new_idx)
        return new_idx == 1

    # def toggle_side_preview(self):
    #     """侧边栏动画 - 严格复刻原始代码"""
    #     is_expanded = self.preview_panel.width() > 0
    #     target_p = 0 if is_expanded else 280
    #     target_w = 760 if is_expanded else 760 + 280

    #     self.anim_p = QPropertyAnimation(self.preview_panel, b"minimumWidth")
    #     self.anim_p_max = QPropertyAnimation(self.preview_panel, b"maximumWidth")
    #     self.anim_w = QPropertyAnimation(self, b"minimumWidth")
    #     self.anim_w_max = QPropertyAnimation(self, b"maximumWidth")

    #     for a in [self.anim_p, self.anim_p_max, self.anim_w, self.anim_w_max]:
    #         a.setDuration(300)
    #         a.setEasingCurve(QEasingCurve.OutCubic)
    #         a.setEndValue(target_w if a.targetObject() == self else target_p)

    #     self.anim_p.start(); self.anim_p_max.start()
    #     self.anim_w.start(); self.anim_w_max.start()
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    # 在 main_window.py 的 dropEvent 中修改
    # 在 main_window.py 中修改
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls: return

        # --- 核心修复：如果是编辑器模式，且拖入的是单张图片，执行强制重置 ---
        is_editor_mode = (self.left_stack.currentIndex() == 1)
        
        for url in urls:
            path = url.toLocalFile()
            
            # 如果是编辑器模式且是图片：先清空，再加载（确保全局只有一个素材）
            if is_editor_mode and path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                # 1. 清空主窗口的全局缓存
                self.asset_files = [] 
                self.selected_folders = []
                
                # 2. 调用编辑器的显示逻辑（它内部已经有了你要求的严格清理）
                self.editor_page.display_image(path)
                
                # 3. 同步主窗口列表数据
                self.asset_files.append(path)
                
                # 4. 打印一个干净的日志
                self.console.clear() 
                self.add_log(f"-> 编辑器已重载新素材: {os.path.basename(path)}", "#a6e3a1")
                break # 编辑器模式通常一次只处理一张大图
                
            # 否则执行原本的追加逻辑（普通 Console 模式）
            elif os.path.isdir(path):
                self.process_import_path(path)
            elif path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                if path not in self.asset_files:
                    self.asset_files.append(path)
                    self.add_log(f"-> 已载入图片: {os.path.basename(path)}", "#89b4fa")
                else:
                    self.add_log(f"-> 提示: 该图片已在列表中", "#f38ba8")

