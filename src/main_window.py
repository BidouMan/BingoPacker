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
from .asset_manager import AssetManager
from .asset_model import FrameData,AssetBundle

class BingoPacker(QMainWindow, ExportLogic,SliceLogic): 
    def __init__(self):
        super().__init__()        
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        self.setWindowTitle("Bingo Sprite Packer")
        # 考虑到常驻预览面板 (280px)，主窗口总宽度设为 1040 (760+280)
        self.setFixedWidth(1040)
        self.setFixedHeight(620)
        
        # --- One Dark 风格配色方案 ---
        # 背景: #282c34 | 容器: #21252b | 边框: #3e4451 
        # 蓝色: #61afef | 灰色文本: #abb2bf | 悬停: #30353f
        self.setStyleSheet("""
            QMainWindow, QWidget { 
                background-color: #282c34; 
                color: #abb2bf; 
            }
            QTextEdit { 
                background-color: #21252b; 
                border: 1px solid #181a1f; 
                border-radius: 8px; 
                padding: 10px; 
                color: #abb2bf;
                font-family: 'Consolas', 'Monaco', 'Microsoft YaHei', monospace;
                font-size: 13px;
            }
            QPushButton { 
                background-color: #353b45; 
                color: #d7dae0;
                border: 1px solid #181a1f;
                border-radius: 4px; 
                font-weight: normal; 
                padding: 5px 15px;
            }
            QPushButton:hover { 
                background-color: #3e4451; 
                color: #ffffff;
            }
            QPushButton#AssetActionBtn {
                background-color: transparent;
                border: none;
                color: #56b6c2; /* 青色点缀 */
            }
            QPushButton#AssetActionBtn:hover {
                color: #61afef;
                background-color: #3e4451;
            }
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
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 标题采用 One Dark 经典的软蓝色
        # header = QLabel("BINGO SPRITE PACKER")
        # header.setAlignment(Qt.AlignCenter)
        # header.setStyleSheet("color: #61afef; font-size: 18px; font-weight: bold; letter-spacing: 2px;")
        # main_layout.addWidget(header)

        # --- 核心切换容器 ---
        self.left_stack = QStackedWidget()
        
        # 页面 0: Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("- Drag and drop assets here...")
        # 控制台文本颜色微调，更具代码感
        self.console.setStyleSheet("""
            QTextEdit { 
                background-color: #21252b; 
                border: 1px solid #181a1f; 
                color: #98c379; /* 运行成功的绿色提示感 */
            }
        """)
        self.left_stack.addWidget(self.console)

        # 页面 1: ManualEditor
        self.editor_page = ManualEditor()
        self.left_stack.addWidget(self.editor_page)

        main_layout.addWidget(self.left_stack)
        
        # 默认启动进入编辑器
        self.left_stack.setCurrentIndex(1)
        
        self.setup_bottom_buttons(main_layout)
        self.global_layout.addWidget(self.main_container)

        # --- 右侧预览区 (常驻) ---
        self.preview_panel = PreviewPanel()
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

        
        self.btn_bgs = self.make_btn("导出 .bgs", "#45b573", "#58ce87")
        self.btn_sprite = self.make_btn("导出 .sprite3", "#d9793d", "#e68a4d")

        for b in [self.btn_upload, self.btn_clear, self.btn_editor,self.btn_slice]:
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
        # self.btn_upload.clicked.connect(self.on_upload_folder)
        self.btn_clear.clicked.connect(self.on_clear_content)
        self.btn_editor.clicked.connect(self.toggle_editor_view)
        self.btn_slice.clicked.connect(self.on_slice_clicked)


        # 2. 导出功能 - 严格连接到原始代码中对应的函数名
        self.btn_bgs.clicked.connect(self.on_export_bgs)    
        self.btn_sprite.clicked.connect(self.on_export_sprite3)

        self.editor_page.slice_completed.connect(self.preview_panel.asset_tree.add_editor_source)

    # 供外部/PreviewPanel 调用的页面切换接口
    def toggle_editor_view(self):
        new_idx = 1 if self.left_stack.currentIndex() == 0 else 0
        self.left_stack.setCurrentIndex(new_idx)
        return new_idx == 1

    def on_clear_content(self):
        """
        全量清空：清空管家的仓库 + 清空控制台 + 清空资产树
        """
        from .asset_manager import AssetManager
        # 1. 清空大管家的存储字典
        AssetManager()._storage.clear()
        
        # 2. 清空控制台日志
        self.console.clear()
        
        # 3. 清空右侧资产树 (暂时调用 clear()，等 refresh 好了再换)
        if hasattr(self.preview_panel, 'asset_tree'):
            self.preview_panel.asset_tree.clear()
            
        # 4. 如果编辑器有图片，也给它洗了
        if hasattr(self.editor_page, 'clear_image'):
            self.editor_page.clear_image()
            
        self.add_log("-> 全局仓库与界面已重置", "#f38ba8")
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

   
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls: return

        manager = AssetManager()
        is_editor_mode = (self.left_stack.currentIndex() == 1)
        
        # 如果是编辑器模式，执行“重载”逻辑
        if is_editor_mode:
            self.console.clear()
            path = urls[0].toLocalFile() # 编辑器通常一次只吃一个
            
            # 1. 直接让管家加载（管家内部已适配单图/文件夹/bgs）
            bundle = manager.load_from_file(path) or manager.load_from_folder(path)
            
            if bundle:
                # 2. 编辑器模式下，我们通常希望它是唯一的
                # 我们可以先清空仓库，确保编辑器里只操作这一个素材
                manager._storage.clear() 
                manager.register_asset(bundle)
                
                # 3. 通知编辑器（这里后面我们要改 ManualEditor 接收 bundle）
                # self.editor_page.load_bundle(bundle) 
                
                # 临时兼容旧逻辑
                if not os.path.isdir(path):
                    self.editor_page.display_image(path)
                
                self.add_log(f"-> 编辑器已重载素材: {bundle.name}", "#a6e3a1")
        
        # 如果是 Console 模式，执行“追加”逻辑
        else:
            for url in urls:
                path = url.toLocalFile()
                # 自动尝试从文件或文件夹加载
                bundle = manager.load_from_file(path) or manager.load_from_folder(path)
                
                if bundle:
                    # 注册入库，自动查重名
                    final_name = manager.register_asset(bundle)
                    self.add_log(f"-> 已载入资源: {final_name}", "#89b4fa")
            
            # 暂时注释掉报错行，稍后处理
            # self.preview_panel.asset_tree.refresh_from_manager()
    def add_log(self, message, color="#abb2bf"):
        """统一的日志输出方法"""
        from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor
        
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        
        cursor.insertText(f"{message}\n")
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()
