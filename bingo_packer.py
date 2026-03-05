import sys
import os
import json
import zipfile
import hashlib
import platform
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                               QFileDialog, QListView, QTreeView, QAbstractItemView, QFrame)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QIcon, QTextCursor, QPixmap

# --- 1. 资源路径与环境锁定逻辑 (完整保留) ---
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    if platform.system() == "Darwin":
        main_dir = os.path.dirname(sys.executable)
        mac_res_path = os.path.join(os.path.dirname(main_dir), 'Resources', relative_path)
        if os.path.exists(mac_res_path):
            return mac_res_path
    return os.path.join(os.path.abspath("."), relative_path)

if getattr(sys, 'frozen', False):
    bundle_dir = os.path.dirname(sys.executable)
    os.chdir(bundle_dir)
else:
    bundle_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(bundle_dir)

class BingoPacker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_folders = []
        self.asset_files = []
        # 动画播放相关
        self.preview_images = []
        self.current_frame = 0
        self.is_playing = False
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self.next_frame)
        self.play_timer.setInterval(100)

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

        # --- 恢复你最开始的全局 QSS 样式 (确保不破坏左侧) ---
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

        # --- 左侧主功能区 (保持 760 宽度和原始样式) ---
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
        # 针对左侧控制台
        self.console.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.console.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        
        self.console.setPlaceholderText("可直接将文件夹拖拽至此处导入...")
        # 针对左侧控制台的特定样式
        self.console.setStyleSheet("border: 1px solid #313244; border-radius: 12px; padding: 10px; font-size: 16px;")
        main_layout.addWidget(self.console)

        button_layout = QHBoxLayout()
        btns_config = [
            (" 导入", self.pick_folders, "#313244", "#45475a"),
            (" 清空", self.clear_all, "#313244", "#f38ba8"),
            (" ✂️ 裁切", self.on_slice_clicked, "#313244", "#fab387"),
            (" 👁️ 预览", self.toggle_side_preview, "#313244", "#a6e3a1"),
            ("spacer", None, None, None), 
            (" 导出 .bgs", lambda: self.run_pack("BGS"), "#45b573", "#58ce87"),
            (" 导出 .sprite3", lambda: self.run_pack("Sprite3"), "#d9793d", "#e68a4d")
        ]

        for text, func, bg, hover in btns_config:
            if text == "spacer":
                button_layout.addStretch()
                continue
            btn = QPushButton(text)
            # 锁定导出按钮和普通按钮的原始色彩逻辑
            btn.setStyleSheet(f"QPushButton {{ background-color: {bg}; padding: 8px 12px; }} QPushButton:hover {{ background-color: {hover}; }}")
            btn.clicked.connect(func)
            button_layout.addWidget(btn)

        main_layout.addLayout(button_layout)
        self.global_layout.addWidget(self.main_container)

        # --- 右侧预览管理面板 (独立局部样式) ---
        self.preview_drawer = QFrame()
        self.preview_drawer.setFixedWidth(0)
        self.preview_drawer.setStyleSheet("background-color: #11111b; border-left: 2px solid #313244;")
        drawer_layout = QVBoxLayout(self.preview_drawer)
        drawer_layout.setContentsMargins(12, 15, 12, 15)
        drawer_layout.setSpacing(10)

        # 1. 标题 (去边框)
        title = QLabel("动画预览")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #89b4fa; font-weight: bold; border: none; font-size: 14px;")
        drawer_layout.addWidget(title)

        # 2. 预览显示窗 (去边框)
        self.preview_screen = QLabel("🎬")
        self.preview_screen.setFixedSize(256, 256)
        self.preview_screen.setAlignment(Qt.AlignCenter)
        self.preview_screen.setStyleSheet("background-color: #000000; border-radius: 12px; border: none;")
        drawer_layout.addWidget(self.preview_screen, 0, Qt.AlignCenter)

        # 3. 播放控制条 (使用 create_mini_btn)
        playback_layout = QHBoxLayout()
        playback_layout.setSpacing(4)
        for icon, func in [("⏮", self.first_frame), ("◀", self.prev_frame), 
                           ("▶", self.toggle_playback), ("▶️", self.next_frame), ("⏭", self.last_frame)]:
            btn = self.create_mini_btn(icon, func)
            if icon == "▶":
                self.btn_play =btn
            playback_layout.addWidget(btn)
        drawer_layout.addLayout(playback_layout)

        # 4 & 5. 资源列表区域 (按照你的要求：亮色底、无 border、圆角)
        self.res_container = QWidget()
        # 容器设置为亮一点的底色 #181825，无边框
        self.res_container.setStyleSheet("background-color: #181825; border-radius: 12px; border: none;")
        res_container_layout = QVBoxLayout(self.res_container)
        res_container_layout.setContentsMargins(0, 0, 0, 0)

        self.res_list_display = QTextEdit()
        # 内部 List 完全透明无边框
        self.res_list_display.setStyleSheet("background-color: transparent; border: none; padding: 5px;")
        self.res_list_display.setReadOnly(True)
        self.res_list_display.setPlaceholderText("导入资源以预览...")
        # 针对右侧资源列表
        self.res_list_display.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.res_list_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.res_list_display.setTextInteractionFlags(Qt.NoTextInteraction) # 禁止文本选择
        self.res_list_display.viewport().setCursor(Qt.ArrowCursor)       # 强制显示标准箭头光标


        res_container_layout.addWidget(self.res_list_display)

        # 6. 右下角悬浮按钮 (修复 + 号显示不全和样式)
        self.btn_upload = QPushButton("+", self.res_container)
        # 样式维持现状颜色 #313244，去掉 border，修复居中
        self.btn_upload.setFixedSize(32, 32)
        self.btn_upload.setCursor(Qt.PointingHandCursor)
        self.btn_upload.setStyleSheet("""
            QPushButton { 
                background-color: #313244; 
                border: none; 
                border-radius: 8px; 
                font-size: 20px; 
                padding-bottom: 2px; /* 视觉微调让+号垂直居中 */
            } 
            QPushButton:hover { background-color: #45475a; }
        """)

        
        # 确保只连接一次
        self.btn_upload.clicked.connect(self.import_preview_assets)
        self.res_list_display.mousePressEvent = self.on_res_list_click


        
        drawer_layout.addWidget(self.res_container)
        self.global_layout.addWidget(self.preview_drawer)

    def resizeEvent(self, event):
        """ 确保上传按钮始终在资源列表的右下角 """
        super().resizeEvent(event)
        if hasattr(self, 'btn_upload') and hasattr(self, 'res_container'):
            margin = 10
            self.btn_upload.move(
                self.res_container.width() - self.btn_upload.width() - margin,
                self.res_container.height() - self.btn_upload.height() - margin
            )

    def create_mini_btn(self, text, func):
        btn = QPushButton(text)
        btn.setFixedSize(40, 24)
        btn.setStyleSheet("font-size: 12px; background-color: #1e1e2e; border: 1px solid #313244; padding: 0px;")
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
        # self.add_log(f"🎬 预览面板已{'收起' if is_expanded else '展开'}", "#a6e3a1")




    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        found = 0
        for f in files:
            f = os.path.normpath(f)
            if os.path.isdir(f) and f not in self.selected_folders:
                self.selected_folders.append(f)
                self.add_log(f"📥 拖拽载入: {os.path.basename(f)}", "#89b4fa")
                found += 1
        if found > 0: self.add_log(f"✅ 成功增加 {found} 个项目", "#a6e3a1")

    def pick_folders(self):
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("选择素材文件夹 (支持多选)")
        file_dialog.setFileMode(QFileDialog.Directory)
        file_dialog.setOption(QFileDialog.ShowDirsOnly, True)
        file_dialog.setOption(QFileDialog.DontUseNativeDialog, True) 
        list_view = file_dialog.findChild(QListView, "listView")
        if list_view: list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        tree_view = file_dialog.findChild(QTreeView)
        if tree_view: tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        if file_dialog.exec():
            paths = file_dialog.selectedFiles()
            found = 0
            for p in paths:
                p = os.path.normpath(p)
                if os.path.isdir(p) and p not in self.selected_folders:
                    self.selected_folders.append(p)
                    self.add_log(f"📁 导入: {os.path.basename(p)}", "#89b4fa")
                    found += 1
            if found > 0: self.add_log(f"✅ 成功载入 {found} 个项目", "#a6e3a1")

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
        if not self.selected_folders:
            self.add_log("⚠️ 列表为空，请先导入！", "#fab387")
            return
        self.add_log(f"🚀 开始执行 {mode} 打包...", "#94e2d5")
        sc = 0
        for folder_path in self.selected_folders:
            success, result = self.process_bgs(folder_path) if mode == "BGS" else self.process_sprite3(folder_path)
            if success:
                self.add_log(f"✅ 生成成功: {os.path.basename(result)}", "#a6e3a1")
                sc += 1
            else:
                self.add_log(f"❌ 失败 [{os.path.basename(folder_path)}]: {result}", "#f38ba8")
        self.add_log(f"✨ 完成: 成功 {sc}/{len(self.selected_folders)}", "#fab387")

    # 播放控制逻辑
    def toggle_playback(self):
        self.is_playing = not self.is_playing
        self.btn_play.setText("⏸" if self.is_playing else "▶")
        if self.is_playing: self.play_timer.start()
        else: self.play_timer.stop()

    def first_frame(self): self.current_frame = 0; self.update_display()
    def last_frame(self): self.current_frame = len(self.preview_images)-1; self.update_display()
    def next_frame(self): 
        if self.preview_images: self.current_frame = (self.current_frame + 1) % len(self.preview_images); self.update_display()
    def prev_frame(self): 
        if self.preview_images: self.current_frame = (self.current_frame - 1) % len(self.preview_images); self.update_display()
    def update_display(self): pass
    def on_slice_clicked(self): self.add_log("✂️ 智能裁切功能待接入", "#fab387")
    def add_log(self, msg, color="#cdd6f4"):
        self.console.append(f'<span style="color:{color}">{msg}</span>')
        self.console.moveCursor(QTextCursor.End)
    def clear_all(self):
        self.selected_folders.clear(); self.console.clear(); self.add_log("♻️ 列表已清空", "#f38ba8")



    def import_preview_assets(self):
        """ 
        实现步骤 1: 点击 upload 按钮导入文件并在列表中显示
        """
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "选择预览资源", 
            "", 
            "Bingo Assets (*.bgs *.sprite3)"
        )
        
        if not file_paths:
            return

        found_new = 0
        for path in file_paths:
            path = os.path.normpath(path)
            if path not in self.asset_files:
                self.asset_files.append(path)
                found_new += 1
        
        if found_new > 0:
            self.refresh_asset_list()
            self.add_log(f"📦 成功导入 {found_new} 个预览资源", "#cba6f7")

    def refresh_asset_list(self, highlight_path=None):
        """ 
        刷新资源列表：
        - 资源之间增加 margin-bottom 实现行间距
        - 路径过长时自动显示省略号 (...)
        """
        self.res_list_display.clear()
        
        # 获取控件宽度，用于计算截断范围（略小于实际宽度以防溢出）
        display_width = self.res_list_display.width() - 40 

        html_content = ""
        for path in self.asset_files:
            file_name = os.path.basename(path)
            ext = os.path.splitext(file_name)[1].lower()
            icon_color = "#45b573" if ext == ".bgs" else "#d9793d"
            
            is_selected = (path == highlight_path)
            bg_color = "#313244" if is_selected else "transparent"
            
            # 条目容器样式
            item_style = (
                f"background-color: {bg_color}; "
                "margin-bottom: 12px; " 
                "padding: 10px 12px; "
                "display: block;"
                
            )
            
            # 路径文字样式：强制不换行 + 溢出隐藏 + 省略号
            # width 是触发 ellipsis 的关键
            path_style = (
                f"width: {display_width}px; "
                "color: #6c7086; "
                "font-size: 10px; "
                "text-overflow: ellipsis; "
                "white-space: nowrap; "
                "overflow: hidden; "
                "display: inline-block;"
            )

            html_content += f"""
            <div style="{item_style}">
                <div style="white-space: nowrap; color: #cdd6f4; font-size: 13px; font-weight: bold;">
                    <span style="color: {icon_color};">●</span> {file_name}
                </div>
                <div style="height: 4px;"></div>
                <div style="{path_style}">
                    &nbsp;&nbsp;&nbsp;{path}
                </div>
            </div>
            """
        
        self.res_list_display.setHtml(html_content)


    def on_res_list_click(self, event):
        """ 捕获资源列表的点击事件并识别选中的文件 """
        # 获取点击位置的光标
        cursor = self.res_list_display.cursorForPosition(event.pos())
        cursor.select(QTextCursor.BlockUnderCursor)
        selected_text = cursor.selectedText().strip()

        if not selected_text:
            return

        clicked_path = None
        # 匹配路径逻辑
        for path in self.asset_files:
            if os.path.basename(path) in selected_text:
                clicked_path = path
                break

        if clicked_path:
            # 记录当前选中
            self.current_selected_asset = clicked_path
            self.add_log(f"🎯 已选中预览: {os.path.basename(clicked_path)}", "#89b4fa")
            
            # 关键：调用带参数的刷新函数来实现高亮视觉效果
            self.refresh_asset_list(highlight_path=clicked_path)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = BingoPacker()
    window.show()
    sys.exit(app.exec())