import sys
import os
import json
import zipfile
import hashlib
import platform
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QTextEdit, QLabel, QSlider,
                               QFileDialog, QListView, QTreeView, QAbstractItemView, QFrame)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QIcon, QTextCursor, QPixmap,QTextBlockFormat
from PySide6 import QtSvg

# --- 1. 资源路径与环境锁定逻辑 (终极兼容版) ---
def get_resource_path(relative_path):
    """ 
    核心逻辑：
    1. 优先检查 PyInstaller 的临时释放目录 (_MEIPASS)
    2. 针对 macOS 打包后的 Resources 目录进行二次定位
    3. 开发环境下使用绝对路径防止 os.chdir 干扰
    """
    # 处理 PyInstaller 打包后的路径
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    
    # 获取脚本所在的绝对路径，不依赖当前工作目录
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # 适配 macOS .app 束路径 (Resources 文件夹)
    if platform.system() == "Darwin" and getattr(sys, 'frozen', False):
        # 路径通常在 ../Resources/relative_path
        mac_res_path = os.path.join(base_path, '..', 'Resources', relative_path)
        if os.path.exists(mac_res_path):
            return os.path.normpath(mac_res_path)
            
    return os.path.join(base_path, relative_path)

# 锁定工作目录：确保文件读写操作在程序所在目录进行
if getattr(sys, 'frozen', False):
    # 打包后：exe/app 可执行文件所在位置
    executable_dir = os.path.dirname(sys.executable)
    # macOS 特殊处理：如果是在 .app 内运行，定位到 .app 所在文件夹而不是 MacOS 内部
    if platform.system() == "Darwin" and ".app/Contents/MacOS" in executable_dir:
        executable_dir = os.path.abspath(os.path.join(executable_dir, "../../../"))
    os.chdir(executable_dir)
else:
    # 开发环境
    os.chdir(os.path.dirname(os.path.abspath(__file__)))


class BingoPacker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_folders = []
        self.asset_files = []
        self.selected_images = []
        # 动画播放相关
        self.preview_images = []
        self.current_frame = 0
        self.is_playing = False
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self.next_frame)
        self.play_timer.setInterval(80)
        self.is_light_bg = False
        self.is_full_scale = True

        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        # --- 窗口初始化 ---
        self.setWindowTitle("Bingo Sprite Packer")
        self.setFixedWidth(760)
        self.setFixedHeight(620)

        icon_path = get_resource_path("logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # --- 全局 QSS 样式 ---
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1e1e2e; color: #cdd6f4; }
            QTextEdit { background-color: #181825; border: 1px solid #313244; border-radius: 10px; color: #cdd6f4; }
            QPushButton { border-radius: 6px; color: white; font-weight: bold; background-color: #313244; }
            QPushButton:hover { background-color: #45475a; }
            QScrollBar:vertical, QScrollBar:horizontal {width: 0px;height: 0px;background: transparent;}
            QMainWindow, QWidget#MainContainer, QFrame {border: none;outline: none;}
        """)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.global_layout = QHBoxLayout(self.central_widget)
        self.global_layout.setContentsMargins(0, 0, 0, 0)
        self.global_layout.setSpacing(0)

        # --- 左侧主功能区 ---
        self.main_container = QWidget()
        self.main_container.setFixedWidth(760)
        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        header = QLabel("BLOCKBINGO 资产打包工具")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #89b4fa; font-size: 24px; font-weight: bold; font-family: 'Microsoft YaHei', 'PingFang SC';")
        main_layout.addWidget(header)

        self.console = QTextEdit()   
        self.console.setReadOnly(True)
        self.console.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.console.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.console.setPlaceholderText("可直接将文件夹拖拽至此处导入...")
        self.console.setStyleSheet("border: 1px solid #313244; border-radius: 12px; padding: 10px; font-size: 14px;")
        main_layout.addWidget(self.console)

        button_layout = QHBoxLayout()
        btns_config = [
            # (显示文字, 回调函数, 背景色, 悬浮色, 图标文件名)
            (" 导入", self.pick_folders, "#313244", "#45475a", "pick_folders"),
            (" 清空", self.clear_all, "#313244", "#f38ba8", "clear_all"),
            (" 裁切", self.on_slice_clicked, "#313244", "#fab387", "on_slice_clicked"),
            (" 预览", self.toggle_side_preview, "#313244", "#a6e3a1", "toggle_side_preview"),
            ("spacer", None, None, None, None), 
            ("导出 .bgs", lambda: self.run_pack("BGS"), "#45b573", "#58ce87", None),
            ("导出 .sprite3", lambda: self.run_pack("Sprite3"), "#d9793d", "#e68a4d", None)
        ]

        for text, func, bg, hover, icon_file in btns_config:
            if text == "spacer":
                button_layout.addStretch()
                continue
            btn = QPushButton(text)
            if icon_file:
                path = get_resource_path(f"assets/icons/{icon_file}.svg")
                if os.path.exists(path):
                    btn.setIcon(QIcon(path))
            
            btn.setStyleSheet(f"QPushButton {{ background-color: {bg}; padding: 8px 12px; }} QPushButton:hover {{ background-color: {hover}; }}")
            if func: btn.clicked.connect(func)
            button_layout.addWidget(btn)

        main_layout.addLayout(button_layout)
        self.global_layout.addWidget(self.main_container)

        # --- 右侧预览管理面板 ---
        self.preview_drawer = QFrame()
        self.preview_drawer.setFixedWidth(0)
        self.preview_drawer.setStyleSheet("background-color: #11111b; border-left: 2px solid #313244;")
        drawer_layout = QVBoxLayout(self.preview_drawer)
        drawer_layout.setContentsMargins(12, 15, 12, 15)
        drawer_layout.setSpacing(10)

        title = QLabel("ANIMATION 预览")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #89b4fa; font-weight: bold; border: none; font-size: 14px;")
        drawer_layout.addWidget(title)

        # --- 预览区域组合 (屏幕 + 悬浮滑块) ---
        self.preview_drawer = QFrame()
        self.preview_drawer.setFixedWidth(0)
        self.preview_drawer.setStyleSheet("background-color: #11111b; border-left: 2px solid #313244;")
        drawer_layout = QVBoxLayout(self.preview_drawer)
        drawer_layout.setContentsMargins(12, 15, 12, 15)
        drawer_layout.setSpacing(10)

        title = QLabel("ANIMATION 预览")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #89b4fa; font-weight: bold; border: none; font-size: 14px;")
        drawer_layout.addWidget(title)

        # --- 预览屏幕 (作为滑块的父容器) ---
        self.preview_screen = QLabel(
            "<div style='color: #313244;'>"
            "<span style='font-size: 20px;'>▶</span><br>"
            "<span style='font-size: 14px; letter-spacing: 2px;'>等待导入中...</span>"
            "</div>"
        )
        self.preview_screen.setTextFormat(Qt.RichText)
        self.preview_screen.setFixedSize(256, 256)
        self.preview_screen.setAlignment(Qt.AlignCenter)
        self.preview_screen.setStyleSheet("background-color: #181825; border-radius: 12px; border: none;")
        
        # --- 重点：将 speed_slider 设为 preview_screen 的子控件以实现悬浮 ---
        self.speed_slider = QSlider(Qt.Horizontal, self.preview_screen)
        self.speed_slider.setMinimum(10)   
        self.speed_slider.setMaximum(300)  
        self.speed_slider.setValue(120)    
        self.speed_slider.setInvertedAppearance(True) 
        
        # 设置滑块在预览窗内的绝对位置：底部居中，宽度略小于 256
        # move(x, y) -> x: 左右留白, y: 底部向上偏移
        self.speed_slider.setGeometry(64, 230, 128, 20) 
        
        self.speed_slider.setStyleSheet("""
            QSlider { background: transparent; outline: none; }
            QSlider::groove:horizontal { background: rgba(49, 50, 68, 180); height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #89b4fa; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
        """)
        self.speed_slider.valueChanged.connect(self.update_speed)
        
        # 布局中只需添加屏幕，滑块会跟随屏幕移动
        drawer_layout.addWidget(self.preview_screen, 0, Qt.AlignCenter)

        # --- 播放控制按钮条 (保持 5 按钮) ---
        playback_layout = QHBoxLayout()
        playback_layout.setSpacing(4)
        playback_layout.setAlignment(Qt.AlignCenter)
        playback_layout.setContentsMargins(0, 5, 0, 5)
        
        
        self.btn_prev = self.create_mini_btn("prev", self.prev_frame)
        self.btn_play = self.create_mini_btn("play", self.toggle_playback)
        self.btn_next = self.create_mini_btn("next", self.next_frame)
        self.btn_scale_mode = self.create_mini_btn("btn_scale_mode", self.toggle_scale_mode)

        self.btn_bg_color = self.create_mini_btn("btn_bg_color", self.toggle_preview_bg)


        playback_layout.addStretch()
        playback_layout.addWidget(self.btn_prev)
        playback_layout.addWidget(self.btn_play)
        playback_layout.addWidget(self.btn_next)        
        playback_layout.addWidget(self.btn_scale_mode)
        playback_layout.addWidget(self.btn_bg_color)
        playback_layout.addStretch()
        drawer_layout.addLayout(playback_layout)

        # 资源列表区域
        self.res_container = QWidget()
        self.res_container.setStyleSheet("background-color: #181825; border-radius: 12px; border: none;")
        res_container_layout = QVBoxLayout(self.res_container)
        res_container_layout.setContentsMargins(0, 0, 0, 0)

        self.res_list_display = QTextEdit()
        self.res_list_display.setStyleSheet("background-color: transparent; border: none; padding: 5px;")
        self.res_list_display.setReadOnly(True)
        self.res_list_display.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.res_list_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.res_list_display.setAcceptDrops(True)
        self.res_list_display.viewport().setAcceptDrops(True) 
        self.res_list_display.dragEnterEvent = self.res_dragEnterEvent
        self.res_list_display.dragMoveEvent = self.res_dragMoveEvent 
        self.res_list_display.dropEvent = self.res_dropEvent
        self.res_list_display.setTextInteractionFlags(Qt.NoTextInteraction)
        self.res_list_display.viewport().setCursor(Qt.ArrowCursor)
        self.res_list_display.mousePressEvent = self.on_res_list_click
        res_container_layout.addWidget(self.res_list_display)

        # 悬浮按钮组
        self.float_ctrl_container = QWidget(self.res_container)
        self.float_ctrl_container.setAttribute(Qt.WA_TranslucentBackground) 
        self.float_ctrl_container.setStyleSheet("background: transparent; border: none;")
        self.float_ctrl_layout = QHBoxLayout(self.float_ctrl_container)
        self.float_ctrl_layout.setContentsMargins(0, 0, 0, 0)
        self.float_ctrl_layout.setSpacing(2)

        self.btn_upload = QPushButton(self.float_ctrl_container)
        upload_icon = get_resource_path("assets/icons/btn_upload.svg")
        if os.path.exists(upload_icon): self.btn_upload.setIcon(QIcon(upload_icon))
        self.btn_upload.setFixedSize(24, 24)
        self.btn_upload.setStyleSheet("""
            QPushButton { 
                background-color: #313244; 
                border: 1px solid transparent; 
                border-radius: 8px; 
            }
            QPushButton:hover { 
                background-color: #45475a; 
                border: none; 
            }
        """)
        self.btn_upload.clicked.connect(self.import_preview_assets)

        self.btn_clear_list = QPushButton(self.float_ctrl_container)
        clear_list_icon = get_resource_path("assets/icons/btn_clear_list.svg")
        if os.path.exists(clear_list_icon): self.btn_clear_list.setIcon(QIcon(clear_list_icon))
        self.btn_clear_list.setFixedSize(24, 24)
        self.btn_clear_list.setStyleSheet("""
            QPushButton { 
                background-color: #313244; 
                border: 1px solid transparent; 
                border-radius: 8px; 
            }
            QPushButton:hover { 
                background-color: #45475a; 
                border: none; 
            }
        """)
        self.btn_clear_list.clicked.connect(self.clear_asset_list)

        self.float_ctrl_layout.addWidget(self.btn_upload)
        self.float_ctrl_layout.addWidget(self.btn_clear_list)
        self.float_ctrl_container.setFixedSize(60, 32)

        drawer_layout.addWidget(self.res_container)
        self.global_layout.addWidget(self.preview_drawer)

    def create_mini_btn(self, text, func):
        btn = QPushButton(text)
        btn.setFixedSize(40, 24)
        btn.setStyleSheet("font-size: 12px; background-color: #1e1e2e; border: 1px solid #313244; padding: 0px;")
        if func is not None:
            btn.clicked.connect(func)
        return btn

    def update_speed(self):
        """同步滑块数值到定时器"""
        self.play_timer.setInterval(self.speed_slider.value())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 调整悬浮按钮组的位置，距离右边缘 15px，底边缘 15px
        if hasattr(self, 'float_ctrl_container'):
            self.float_ctrl_container.move(
                self.res_container.width() - self.float_ctrl_container.width() - 2,
                self.res_container.height() - self.float_ctrl_container.height() - 2
            )

    def clear_asset_list(self):
        """彻底清空右侧预览列表及物理缓存"""
        # 1. 统一变量名：使用代码中实际存在的 asset_files
        self.asset_files = [] 
        
        # 2. 调用你现有的刷新逻辑来更新那个 QTextEdit (res_list_display)
        self.refresh_asset_list()
        
        # 3. 停止播放器并重置预览屏
        if hasattr(self, 'play_timer'):
            self.play_timer.stop()
        self.is_playing = False
        self.btn_play.setText("▶")
        self.preview_images = []
        self.preview_screen.clear()
        self.preview_screen.setText("<div style='color: #313244; font-size: 50px;'>∅</div>")
        
        # self.add_log("- 预览列表已彻底重置", "#f38ba8")

    def create_mini_btn(self, icon_name, func):
        btn = QPushButton()
        btn.setFixedSize(40, 24)
        
        icon_path = get_resource_path(f"assets/icons/{icon_name}.svg")
        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(btn.size() * 0.7)
        else:
            btn.setText("?")

        # --- 更新样式：增加 Hover 高亮效果 ---
        btn.setStyleSheet("""
            QPushButton { 
                background-color: #1e1e2e; 
                border: none; 
                padding: 0px; 
            }
            QPushButton:hover { 
                background-color: #313244; 
                border: none; 
            }
        """)
        
        if func is not None:
            btn.clicked.connect(func)
        return btn




    # --- 5. 动画与功能逻辑 (完整保留原有核心逻辑) ---
    def toggle_side_preview(self):
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





    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        f_dir, f_img = 0, 0
        for u in urls:
            path = os.path.normpath(u.toLocalFile())
            if os.path.isdir(path) and path not in self.selected_folders:
                self.selected_folders.append(path)
                self.add_log(f"- 文件夹: {os.path.basename(path)}", "#89b4fa")
                f_dir += 1
            elif os.path.isfile(path) and path.lower().endswith(".png"):
                if path not in self.selected_images:
                    self.selected_images.append(path)
                    # 使用单帧图标标识
                    self.add_log(f"- 单帧图片: {os.path.basename(path)}", "#fab387")
                    f_img += 1
        
        # if f_dir + f_img > 0:
        #     self.add_log(f"- 已载入 {f_dir} 组序列 / {f_img} 个单帧", "#a6e3a1")

    def pick_folders(self):
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("选择素材 (文件夹或 PNG 图片)")
        file_dialog.setFileMode(QFileDialog.Directory)
        file_dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        file_dialog.setNameFilter("All Files (*);;PNG Images (*.png)")

        # --- 新增：修复对话框按钮样式 ---
        file_dialog.setStyleSheet("""
            /* 1. 修复按钮样式，取消加粗，增加内边距 */
            QPushButton { 
                font-weight: normal; 
                padding: 4px 12px; 
                min-width: 65px;
                border: 1px solid #45475a;
                margin-right: 5px; /* 给按钮右侧留一点空隙，避开手柄 */
            }
            QPushButton:hover { background-color: #45475a; }

            /* 2. 彻底隐藏右下角的尺寸手柄，防止遮挡按钮 */
            QSizeGrip {
                width: 0px;
                height: 0px;
                background: transparent;
            }

            /* 3. 统一对话框内的列表样式（可选，为了更好看） */
            QListView, QTreeView {
                background-color: #181825;
                border: 1px solid #313244;
            }
        """)

        # 强制开启多选
        list_view = file_dialog.findChild(QListView, "listView")
        if list_view:
            list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        tree_view = file_dialog.findChild(QTreeView)
        if tree_view:
            tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        if file_dialog.exec():
            paths = file_dialog.selectedFiles()
            f_dir, f_img = 0, 0
            for p in paths:
                p = os.path.normpath(p)
                if os.path.isdir(p) and p not in self.selected_folders:
                    self.selected_folders.append(p)
                    self.add_log(f"- 文件夹: {os.path.basename(p)}", "#89b4fa")
                    f_dir += 1
                elif os.path.isfile(p) and p.lower().endswith(".png") and p not in self.selected_images:
                    self.selected_images.append(p)
                    self.add_log(f"- 单帧图片: {os.path.basename(p)}", "#fab387")
                    f_img += 1
            


    

    # 完整保留打包逻辑
    def process_bgs(self, source):
        try:
            name = os.path.basename(source)
            out = os.path.join(os.path.dirname(source), f"{name}.bgs")
            valid_exts = ('.png', '.jpg', '.jpeg', '.webp')
            imgs = sorted([i for i in os.listdir(source) if i.lower().endswith(valid_exts)])
            if not imgs: return False, "目录内无图片"
            cfg = {"name": name, "costumes": [{"id": i, "name": os.path.splitext(img)[0], "file": img} for i, img in enumerate(imgs)]}
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as bgs:
                for img in imgs: bgs.write(os.path.join(source, img), img)
                bgs.writestr("config.json", json.dumps(cfg, indent=4, ensure_ascii=False))
            return True, out
        except Exception as e: return False, str(e)

    def process_sprite3(self, source):
        try:
            name = os.path.basename(source)
            out = os.path.join(os.path.dirname(source), f"{name}.sprite3")
            valid_exts = ('.png', '.jpg', '.jpeg', '.svg')
            files = sorted([f for f in os.listdir(source) if f.lower().endswith(valid_exts)])
            if not files: return False, "目录内无有效图片"
            scratch_json = {"isStage": False, "name": name, "variables": {}, "lists": {}, "broadcasts": {}, "blocks": {}, "comments": {}, "currentCostume": 0, "costumes": [], "sounds": [], "volume": 100, "layerOrder": 0, "visible": True, "x": 0, "y": 0, "size": 100, "direction": 90, "draggable": False, "rotationStyle": "all around"}
            costume_data = []
            for img in files:
                img_path = os.path.join(source, img)
                ext = os.path.splitext(img)[1].lower().replace('.', '')
                if ext == "jpeg": ext = "jpg"
                with open(img_path, 'rb') as f: file_hash = hashlib.md5(f.read()).hexdigest()
                new_filename = f"{file_hash}.{ext}"
                scratch_json["costumes"].append({"name": os.path.splitext(img)[0], "assetId": file_hash, "dataFormat": ext, "md5ext": new_filename, "bitmapResolution": 1, "rotationCenterX": 0, "rotationCenterY": 0})
                costume_data.append((img_path, new_filename))
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as s3:
                for img_path, new_filename in costume_data: s3.write(img_path, new_filename)
                s3.writestr("sprite.json", json.dumps(scratch_json, indent=4, ensure_ascii=False))
            return True, out
        except Exception as e: return False, str(e)

    def run_pack(self, mode):
        # 准备任务列表
        tasks = [(f, "dir") for f in self.selected_folders] + [(i, "img") for i in self.selected_images]
        
        if not tasks:
            self.add_log("⚠️ 列表为空，请先导入！", "#fab387")
            return

        sc = 0
        import shutil
        for source, s_type in tasks:
            if s_type == "dir":
                # 文件夹直接打包
                success, result = self.process_bgs(source) if mode == "BGS" else self.process_sprite3(source)
            else:
                # 单图处理：修正 temp_ 命名问题
                img_name_with_ext = os.path.basename(source)
                name_base = os.path.splitext(img_name_with_ext)[0]
                
                # 创建一个与图片同名的临时目录 (不再加 temp_ 前缀)
                temp_dir = os.path.join(os.path.dirname(source), name_base)
                os.makedirs(temp_dir, exist_ok=True)
                shutil.copy(source, os.path.join(temp_dir, img_name_with_ext))
                
                # 打包
                success, result = self.process_bgs(temp_dir) if mode == "BGS" else self.process_sprite3(temp_dir)
                
                # 清理
                shutil.rmtree(temp_dir)

            if success:
                self.add_log(f"- 生成成功: {os.path.basename(result)}", "#a6e3a1")
                sc += 1
        self.add_log(f"- 完成: 成功 {sc}/{len(tasks)}", "#fab387")

    # 播放控制逻辑
    def toggle_playback(self):
        """切换播放/暂停状态"""
        if not self.preview_images:
            return
            
        self.is_playing = not self.is_playing
        
        # 如果当前是播放状态，按钮应该显示“暂停”图标 (让用户点击去暂停)
        # 如果当前是停止状态，按钮应该显示“播放”图标 (让用户点击去开始)
        icon_name = "pause" if self.is_playing else "play"
        icon_path = get_resource_path(f"assets/icons/{icon_name}.svg")
        
        if os.path.exists(icon_path):
            self.btn_play.setIcon(QIcon(icon_path))
        
        if self.is_playing:
            self.play_timer.start()
        else:
            self.play_timer.stop()

    def first_frame(self): 
        self.current_frame = 0
        self.update_display()

    def last_frame(self): 
        self.current_frame = len(self.preview_images)-1
        self.update_display()

    def next_frame(self): 
        if self.preview_images: 
            self.current_frame = (self.current_frame + 1) % len(self.preview_images)
            self.update_display()

    def prev_frame(self): 
        if self.preview_images: 
            self.current_frame = (self.current_frame - 1) % len(self.preview_images)
            self.update_display()
    




    def add_log(self, msg, color="#cdd6f4"):
        # 直接在 div 标签里写 CSS 的 line-height
        # 1.6 代表 1.6 倍行距，你可以根据喜好调成 1.8 或 2.0
        log_html = f'''
            <div style="color:{color}; line-height: 125%; margin-bottom: 4px;">
                {msg}
            </div>
        '''
        self.console.append(log_html)
        
        # 保持滚动条到底部
        self.console.moveCursor(QTextCursor.End)


    def clear_all(self):
        self.selected_folders.clear()
        self.selected_images.clear() # 也要清理单图
        self.console.clear()
        self.add_log("♻️  列表已清空", "#f38ba8")



    def import_preview_assets(self):
        """导入预览资源 - 保持导入顺序并预览最新项"""
        if not hasattr(self, 'asset_files'):
            self.asset_files = []

        files, _ = QFileDialog.getOpenFileNames(
            self, "选择预览资源", "", "Bingo Files (*.bgs *.sprite3)"
        )
        
        if files:
            # 记录本次新导入的文件
            added_files = []
            for f in files:
                f = os.path.normpath(f)
                if f not in self.asset_files:
                    self.asset_files.append(f) # append 确保了它在列表末尾
                    added_files.append(f)
            
            if added_files:
                self.refresh_asset_list()
                self.add_log(f"- 成功追加 {len(added_files)} 个预览资源", "#a6e3a1")

                # --- 核心修改：永远预览本次导入的最末尾一项 ---
                last_path = added_files[-1] 
                self.current_selected_asset = last_path
                self.refresh_asset_list(highlight_path=last_path, auto_scroll=True)
                self.load_asset_preview(last_path)

    def refresh_asset_list(self, highlight_path=None, auto_scroll=False):
        """ 
        刷新资源列表：
        - 使用 table 布局确保左对齐
        - 修复点击时滚动条回弹顶部的 Bug
        """
        # --- 核心修复：记录当前滚动条位置 ---
        scrollbar = self.res_list_display.verticalScrollBar()
        current_pos = scrollbar.value()
        
        self.res_list_display.clear()
        
        # 减小宽度 buffer 确保不触发横向滚动
        display_width = self.res_list_display.width() - 25 

        html_content = ""
        for path in self.asset_files:
            file_name = os.path.basename(path)
            ext = os.path.splitext(file_name)[1].lower()
            icon_color = "#45b573" if ext == ".bgs" else "#d9793d"
            
            is_selected = (path == highlight_path)
            bg_color = "#313244" if is_selected else "transparent"
            
            # 使用 table 强制左对齐并处理边距
            html_content += f"""
            <table width="{display_width}" border="0" cellpadding="8" cellspacing="0" style="margin-bottom: 8px; background-color: {bg_color}; border-radius: 8px;">
                <tr>
                    <td align="left">
                        <div style="color: #cdd6f4; font-size: 13px; font-weight: bold;">
                            <span style="color: {icon_color};">●</span> {file_name}
                        </div>
                        <div style="color: #6c7086; font-size: 10px; margin-top: 2px;">
                            &nbsp;&nbsp;{path}
                        </div>
                    </td>
                </tr>
            </table>
            """
        
        self.res_list_display.setHtml(html_content)
        
        # --- 核心修复：根据逻辑恢复位置或滚动到底部 ---
        if auto_scroll:
            # 如果是新导入，滚动到底部
            self.res_list_display.moveCursor(QTextCursor.End)
        else:
            # 如果是点击切换，恢复之前的滚动位置，防止回弹
            scrollbar.setValue(current_pos)


    def on_res_list_click(self, event):
        cursor = self.res_list_display.cursorForPosition(event.pos())
        cursor.select(QTextCursor.BlockUnderCursor)
        selected_text = cursor.selectedText().strip()

        if not selected_text: return

        clicked_path = None
        for path in self.asset_files:
            if os.path.basename(path) in selected_text:
                clicked_path = path
                break

        if clicked_path:
            self.current_selected_asset = clicked_path
            self.refresh_asset_list(highlight_path=clicked_path, auto_scroll=False)
            # --- 新增：加载预览资源 ---
            self.load_asset_preview(clicked_path)
    
    def load_asset_preview(self, file_path):
        """解析 .bgs 或 .sprite3 文件并加载图片序列"""
        self.play_timer.stop()
        self.is_playing = False
        icon_path = get_resource_path("assets/icons/play.svg")
        if os.path.exists(icon_path):
            self.btn_play.setIcon(QIcon(icon_path))
        self.preview_images = []
        self.current_frame = 0

        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                # 逻辑 A: 处理 .bgs (自研格式)
                if file_path.lower().endswith(".bgs"):
                    if "config.json" in z.namelist():
                        config = json.loads(z.read("config.json").decode('utf-8'))
                        # 按照 config.json 里的 costumes 顺序加载
                        for costume in config.get("costumes", []):
                            img_name = costume.get("file")
                            if img_name in z.namelist():
                                pix = QPixmap()
                                pix.loadFromData(z.read(img_name))
                                self.preview_images.append(pix)
                
                # 逻辑 B: 处理 .sprite3 (Scratch 格式)
                elif file_path.lower().endswith(".sprite3"):
                    if "sprite.json" in z.namelist():
                        s_json = json.loads(z.read("sprite.json").decode('utf-8'))
                        for costume in s_json.get("costumes", []):
                            md5ext = costume.get("md5ext")
                            if md5ext in z.namelist():
                                pix = QPixmap()
                                pix.loadFromData(z.read(md5ext))
                                self.preview_images.append(pix)

            if self.preview_images:
                self.add_log(f"- 预览已载入: {len(self.preview_images)} 帧", "#a6e3a1")
                self.update_display()

                if not self.is_playing:
                    self.toggle_playback() # 自动开始播放并更新按钮状态为 ⏸
            else:
                self.add_log("❌ 资源内未找到有效帧", "#f38ba8")
                self.preview_screen.setText("🎬")

        except Exception as e:
            self.add_log(f"❌ 加载失败: {str(e)}", "#f38ba8")
    
    def update_display(self):
        """更新预览窗口的图像显示 - 支持缩放模式切换"""
        if not self.preview_images:
            return
        
        pixmap = self.preview_images[self.current_frame]
        
        # 根据 self.is_full_scale 决定显示模式
        if self.is_full_scale:
            # 模式 A：缩放填充 (保持比例，像素锐利)
            scaled_pixmap = pixmap.scaled(
                self.preview_screen.size(), 
                Qt.KeepAspectRatio, 
                Qt.FastTransformation  # 像素风格必须用 Fast
            )
            self.preview_screen.setPixmap(scaled_pixmap)
        else:
            # 模式 B：原始大小 (不缩放，居中显示)
            self.preview_screen.setPixmap(pixmap)

    
    def on_slice_clicked(self):
        """
        全平台兼容版（支持中文路径）：
        - 智能裁切 ->
        - ■■■■■■■■■■■■■■■■■■■■  [100.0%]
        - 处理完成 
        - 文件夹: 洛克人
        """
        if not self.selected_images:
            self.add_log("- ⚠️ 待处理列表为空，请先导入 PNG 素材", "#f38ba8")
            return

        import cv2
        import numpy as np
        from PIL import Image
        import os

        # 确保等宽字体显示，防止进度条错位
        self.console.setFontFamily("'Consolas', 'Monaco', 'Courier New', monospace")

        total_imgs = len(self.selected_images)
        self.add_log("- 智能裁切 ->", "#89b4fa")
        
        new_folders = [] # 记录本次生成的文件夹名

        # 使用切片 [:] 复制列表，防止在循环中 remove 导致跳过元素
        for i, img_path in enumerate(self.selected_images[:]):
            try:
                # --- 1. 进度视觉设计 ---
                current_idx = i + 1
                percent = current_idx / total_imgs
                bar_width = 30 
                filled = int(bar_width * percent)
                bar_content = "■" * filled + "∙" * (bar_width - filled)
                progress_info = f"- {bar_content}  [{percent*100:>5.1f}%]"
                
                # --- 2. 路径与文件名处理 ---
                img_name_with_ext = os.path.basename(img_path)
                name_base = os.path.splitext(img_name_with_ext)[0]
                output_dir = os.path.join(os.path.dirname(img_path), name_base)
                
                # --- 3. 核心：跨平台中文路径读取兼容 ---
                # 不直接使用 cv2.imread，因为在 Windows 下它不支持非 ASCII 路径
                try:
                    # 使用 Python 原生 open 读取二进制流，这在 Win/Mac 下都完美支持中文
                    with open(img_path, "rb") as f:
                        file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
                        # 从内存中解码图像
                        src = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
                except Exception as read_error:
                    self.add_log(f"- 读取失败: {img_name_with_ext}", "#f38ba8")
                    continue

                if src is None:
                    continue
                
                # 提取 Alpha 通道或转为灰度
                alpha = src[:, :, 3] if src.shape[2] == 4 else cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
                contours, _ = cv2.findContours(alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if not contours:
                    continue

                # 寻找最大外接矩形以统一尺寸
                max_w, max_h = 0, 0
                valid_rects = []
                for cnt in contours:
                    x, y, w, h = cv2.boundingRect(cnt)
                    if w < 2 or h < 2: continue 
                    max_w = max(max_w, w)
                    max_h = max(max_h, h)
                    valid_rects.append((x, y, w, h))

                if not valid_rects:
                    continue

                # 计算带填充的方形画布尺寸
                padding = 8 
                side_length = max(max_w, max_h) + padding
                if side_length % 2 != 0: side_length += 1
                target_size = (side_length, side_length)

                # 按位置排序（从上到下，从左到右）
                valid_rects.sort(key=lambda r: (r[1], r[0]))

                # 创建输出目录
                os.makedirs(output_dir, exist_ok=True)
                
                # 使用 PIL 进行裁切和保存（PIL 原生支持中文路径）
                pil_img = Image.open(img_path).convert("RGBA")
                
                for idx, (x, y, w, h) in enumerate(valid_rects):
                    sprite_crop = pil_img.crop((x, y, x + w, y + h))
                    final_canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
                    # 居中对齐
                    offset_x = (side_length - w) // 2
                    offset_y = (side_length - h) // 2
                    final_canvas.paste(sprite_crop, (offset_x, offset_y), sprite_crop)
                    
                    save_name = f"{name_base}_{idx:02d}.png"
                    final_canvas.save(os.path.join(output_dir, save_name))

                # --- 4. 更新 UI 反馈 ---
                self.add_log(progress_info, "#74c7ec") 
                # 强制刷新 GUI，防止界面在处理大量图片时卡死
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()

                # 更新已选文件夹列表（用于导出功能）
                if output_dir not in self.selected_folders:
                    self.selected_folders.append(output_dir)
                    new_folders.append(name_base)
                
                # 处理完后从待处理列表中移除
                if img_path in self.selected_images:
                    self.selected_images.remove(img_path)

            except Exception as e:
                # 打印详细错误到终端以便调试，控制台只显示简要提示
                import traceback
                print(traceback.format_exc())
                self.add_log(f"- 错误: {os.path.basename(img_path)}", "#f38ba8")

        # --- 5. 汇总显示 ---
        self.add_log("- 处理完成", "#a6e3a1")
        for folder_name in new_folders:
            self.add_log(f"- 文件夹 : {folder_name}", "#89b4fa") # 使用蓝色显示生成的文件夹 # 结束语颜色-绿色
    

    def res_dragEnterEvent(self, event):
        """当文件拖入区域时触发"""
        if event.mimeData().hasUrls():
            # 检查是否有符合条件的文件
            for url in event.mimeData().urls():
                path = url.toLocalFile().lower()
                if path.endswith(('.bgs', '.sprite3')):
                    event.acceptProposedAction() # 接受动作
                    return
        event.ignore()

    def res_dragMoveEvent(self, event):
        """拖拽过程中持续触发，必须接受才能成功 Drop"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def res_dropEvent(self, event):
        """处理拖入的预览文件 - 保持顺序并预览最新"""
        urls = event.mimeData().urls()
        new_files = []
        
        for u in urls:
            path = os.path.normpath(u.toLocalFile())
            if path.lower().endswith(('.bgs', '.sprite3')):
                if path not in self.asset_files:
                    self.asset_files.append(path) # 始终添加在末尾
                    new_files.append(path)
        
        if new_files:
            # 【注意】：这里千万不要写 self.asset_files.sort()
            self.refresh_asset_list()
            self.add_log(f"- 导入 {len(new_files)} 个预览资源", "#a6e3a1")
            
            # 无论之前是否有文件，永远播放本次拖入的最末尾一个
            last_path = new_files[-1]
            self.current_selected_asset = last_path
            self.refresh_asset_list(highlight_path=last_path, auto_scroll=True)
            self.load_asset_preview(last_path)
        
        event.acceptProposedAction()

    def toggle_preview_bg(self):
        """切换预览窗口的背景颜色 (深色/浅色)"""
        self.is_light_bg = not self.is_light_bg
        
        if self.is_light_bg:
            # 浅色模式：白色背景，深色文字
            bg_color = "#ffffff"
            text_color = "#313244"
        else:
            # 深色模式：回归你原本的颜色
            bg_color = "#181825"
            text_color = "#cdd6f4"
            
        # 更新预览窗样式 (保留你原来的 12px 圆角)
        self.preview_screen.setStyleSheet(f"background-color: {bg_color}; border-radius: 12px; border: none; color: {text_color};")
        
        # 如果当前没有图片，更新“等待导入”提示文字的颜色
        if not self.preview_images:
            self.preview_screen.setText(
                f"<div style='color: {text_color};'>"
                "<span style='font-size: 20px;'>▶</span><br>"
                "<span style='font-size: 14px; letter-spacing: 2px;'>等待导入中...</span>"
                "</div>"
            )
        
        if self.is_light_bg:
            # 浅色模式下，让轨道稍微浅一点
            self.speed_slider.setStyleSheet("""
                QSlider { background: transparent; outline: none; }
                QSlider::groove:horizontal { background: rgba(0, 0, 0, 40); height: 4px; border-radius: 2px; }
                QSlider::handle:horizontal { background: #89b4fa; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            """)
        else:
            # 恢复深色模式滑块样式
            self.speed_slider.setStyleSheet("""
                QSlider { background: transparent; outline: none; }
                QSlider::groove:horizontal { background: rgba(49, 50, 68, 180); height: 4px; border-radius: 2px; }
                QSlider::handle:horizontal { background: #89b4fa; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
            """)

    def toggle_scale_mode(self):
        """切换预览图的显示模式：缩放填充 / 原始大小"""
        self.is_full_scale = not self.is_full_scale
        # 立即刷新当前帧以看到效果
        self.update_display()

    def get_pip_style_bar(self, current, total):
        """ 生成 pip 风格的进度条字符串 """
        width = 30  # 进度条总长度
        progress = current / total
        filled_width = int(width * progress)
        
        # 使用 pip 风格的字符：实心 ━ 和 空心 ━
        # 也可以用 █
        bar = "━" * filled_width + " " * (width - filled_width)
        percent = progress * 100
        
        return f" {percent:3.0f}% |{bar}| {current}/{total}"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = BingoPacker()
    window.show()
    sys.exit(app.exec())