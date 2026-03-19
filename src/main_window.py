import os
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QStackedWidget,
)
from PySide6.QtGui import QIcon

from .utils import get_resource_path
from .widgets.preview_panel import PreviewPanel

from .logic_export import ExportLogic
from .logic_slice import SliceLogic
from .widgets.manual_editor import ManualEditor
from .asset_manager import AssetManager


class BingoPacker(QMainWindow, ExportLogic, SliceLogic):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        self.setWindowTitle("Bingo Sprite Packer")
        # 考虑到常驻预览面板 (280px)，主窗口总宽度设为 1040 (760+280)
        self.setMinimumSize(1040, 620)
        
        # 设置窗口图标
        from .utils import get_resource_path
        import os
        import sys
        
        # 根据平台选择合适的图标
        if sys.platform == 'win32':
            icon_path = get_resource_path("assets/icons/logo_win.ico")
        elif sys.platform == 'darwin':
            icon_path = get_resource_path("assets/icons/logo.icns")
        else:
            icon_path = get_resource_path("assets/icons/logo.png")
        
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

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
                padding: 10px; 
                color: #abb2bf;
                font-family: 'Consolas', 'Monaco', 'Microsoft YaHei', monospace;
                font-size: 14px;
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
        # self.main_container.setFixedWidth(760)
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # --- 核心切换容器 ---
        self.left_stack = QStackedWidget()

        # 页面 0: Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)

        self.console.setPlaceholderText("-> 批量导入资源...")
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
        self.global_layout.addWidget(self.main_container, stretch=1)

        # --- 右侧预览区 (常驻) ---
        self.preview_panel = PreviewPanel()
        self.preview_panel.setVisible(True)
        self.preview_panel.setFixedWidth(280)
        self.global_layout.addWidget(self.preview_panel, stretch=0)

    def setup_bottom_buttons(self, layout):
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        # 定义按钮 - 严格还原原始颜色和图标名
        self.btn_upload = self.make_btn(" 导入", "#313244", "#89b4fa", "pick_folders")
        self.btn_clear = self.make_btn(" 清空", "#313244", "#89b4fa", "clear_all")
        self.btn_editor = self.make_btn(" 编辑", "#313244", "#89b4fa", "btn_editor")
        self.btn_slice = self.make_btn(" 裁切", "#313244", "#89b4fa", "btn_slice")

        self.btn_bgs = self.make_btn("导出 .bgs", "#45b573", "#58ce87")
        self.btn_sprite = self.make_btn("导出 .sprite3", "#d9793d", "#e68a4d")

        for b in [self.btn_upload, self.btn_clear, self.btn_slice, self.btn_editor]:
            btn_layout.addWidget(b)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_bgs)
        btn_layout.addWidget(self.btn_sprite)

        layout.addLayout(btn_layout)

    def make_btn(self, text, bg, hover, icon=None):
        btn = QPushButton(text)
        if icon:
            relative_icon_path = f"assets/icons/{icon}.svg"
            path = get_resource_path(relative_icon_path)
            if os.path.exists(path):
                btn.setIcon(QIcon(path))
        btn.setStyleSheet(
            f"QPushButton {{ background-color: {bg}; padding: 8px 15px; border: none; }}"
            f"QPushButton:hover {{ background-color: {hover}; }}"
        )
        return btn

    def connect_signals(self):
        # 1. 基础功能
        self.btn_upload.clicked.connect(lambda: self.left_stack.setCurrentIndex(0))
        self.btn_clear.clicked.connect(self.on_clear_content)
        self.btn_editor.clicked.connect(lambda: self.left_stack.setCurrentIndex(1))
        self.btn_slice.clicked.connect(self.on_slice_clicked)

        # 2. 导出功能 - 严格连接到原始代码中对应的函数名
        self.btn_bgs.clicked.connect(self.handle_export_bgs_request)
        self.btn_sprite.clicked.connect(self.handle_export_sprite_request)

        # self.editor_page.bundle_updated.connect(self.on_editor_bundle_changed)
        self.editor_page.bundle_updated.connect(self.on_editor_bundle_changed)
        self.preview_panel.asset_tree.segment_changed.connect(
            self.preview_panel.update_segment_range
        )
        # self.manual_editor.bundle_updated.connect(self.preview_panel.start_segment_preview)

    def on_editor_bundle_changed(self, bundle, segment=None):
        if bundle is None:
            self.preview_panel.stop_and_clear()
            return

        # 更新资源树
        self.preview_panel.asset_tree.reset_with_bundle(bundle)

        # 如果没有传入 segment，尝试从预览面板获取当前的，或者取第一个
        if not segment:
            segment = self.preview_panel.current_segment or (
                bundle.segments[0] if bundle.segments else None
            )

        if segment:
            # 强制预览面板重载画面
            self.preview_panel.start_segment_preview(bundle, segment)

    def handle_export_bgs_request(self):
        target = None
        # 如果在编辑器页面，只导编辑器里的那一个
        if self.left_stack.currentIndex() == 1:
            if (
                hasattr(self.editor_page, "current_bundle")
                and self.editor_page.current_bundle
            ):
                # 直接使用current_bundle.name，确保使用最新的名称
                target = self.editor_page.current_bundle.name
                # 确保AssetManager中存在这个资源
                from .asset_manager import AssetManager
                manager = AssetManager()
                if target not in manager._storage and self.editor_page.current_bundle:
                    # 如果不存在，重新注册
                    manager._storage[target] = self.editor_page.current_bundle

        # 显式传递 target。如果是 Console 模式，target 就是 None
        self.on_export_bgs(target_name=target)

    def handle_export_sprite_request(self):
        target = None
        if self.left_stack.currentIndex() == 1:
            if (
                hasattr(self.editor_page, "current_bundle")
                and self.editor_page.current_bundle
            ):
                # 直接使用current_bundle.name，确保使用最新的名称
                target = self.editor_page.current_bundle.name
                # 确保AssetManager中存在这个资源
                from .asset_manager import AssetManager
                manager = AssetManager()
                if target not in manager._storage and self.editor_page.current_bundle:
                    # 如果不存在，重新注册
                    manager._storage[target] = self.editor_page.current_bundle
        self.on_export_sprite3(target_name=target)

    def on_clear_content(self):
        AssetManager().clear_all()
        self.console.clear()

        if hasattr(self.preview_panel, "asset_tree"):
            self.preview_panel.asset_tree.clear()

        if hasattr(self.editor_page, "current_bundle"):
            self.editor_page.current_bundle = None  # 确保编辑器不再持有旧数据引用

        if hasattr(self.editor_page, "scene"):
            self.editor_page.scene.clear()
            self.editor_page.frame_list.clear()

        self.add_log("♻️ 资源列表已清空", "#f38ba8")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return

        manager = AssetManager()
        manager.clear_all()
        self.console.clear()

        # 如果是编辑器模式，执行“重载”逻辑
        if self.left_stack.currentIndex() == 1:
            path = urls[0].toLocalFile()  # 编辑器通常一次只吃一个

            # 1. 直接让管家加载（管家内部已适配单图/文件夹/bgs）
            bundle = manager.load_from_file(path) or manager.load_from_folder(path)

            if bundle:
                # 2. 编辑器模式下，我们通常希望它是唯一的
                # 我们可以先清空仓库，确保编辑器里只操作这一个素材
                manager._storage.clear()
                manager.register_asset(bundle)

                # 3. 通知编辑器（这里后面我们要改 ManualEditor 接收 bundle）
                # self.editor_page.load_bundle(bundle)

                # 临时兼容旧逻辑 - 移除目录检查，让 display_image 处理目录
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

            # Todo
            # 暂时注释掉报错行，稍后处理
            # self.preview_panel.asset_tree.refresh_from_manager()

    def add_log(self, msg, color="#cdd6f4", replace_last=False):
        """
        完全还原老代码：通过控制光标选中整行来实现原地替换
        """
        from PySide6.QtGui import QTextCursor

        # 构造 HTML 内容
        log_html = f'<div style="color:{color}; line-height: 110%; margin-bottom: 2px;">{msg}</div>'

        if replace_last:
            cursor = self.console.textCursor()
            # 1. 移动到文档最末尾
            cursor.movePosition(QTextCursor.End)
            # 2. 选中当前行（即最后一行）
            cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
            # 3. 删除旧内容并插入新 HTML
            cursor.removeSelectedText()
            cursor.insertHtml(log_html)
        else:
            # 正常模式：追加新行
            self.console.append(log_html)

        # 始终滚动到底部
        self.console.moveCursor(QTextCursor.End)
