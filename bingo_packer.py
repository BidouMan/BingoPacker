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
        # --- 2. 窗口初始化与 QSS 样式 (完整保留) ---
        self.setWindowTitle("Bingo Sprite Packer")
        self.setFixedWidth(760)
        self.setFixedHeight(620)

        icon_path = get_resource_path("logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1e1e2e; color: #cdd6f4; }
            QSizeGrip { width: 0; height: 0; image: none; }
            QFileDialog QAbstractItemView {
                background-color: #181825; color: #cdd6f4;
                border: 1px solid #313244; border-radius: 8px;
            }
            QFileDialog QPushButton {
                background-color: #313244; color: white;
                border-radius: 6px; padding: 5px 12px; min-width: 60px;
            }
            QFileDialog QPushButton:hover { background-color: #45475a; }
            QFileDialog QHeaderView::section { background-color: #313244; color: #cdd6f4; padding: 4px; border: none; }
            QFileDialog QLineEdit {
                background-color: #11111b; color: #cdd6f4;
                border: 1px solid #313244; border-radius: 4px; padding: 2px;
            }
            QFileDialog QLabel { color: #cdd6f4; }
        """)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.global_layout = QHBoxLayout(self.central_widget)
        self.global_layout.setContentsMargins(0, 0, 0, 0)
        self.global_layout.setSpacing(0)

        # --- 3. 左侧主功能区 (保持原有 760 布局) ---
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
        self.console.setPlaceholderText("可直接将文件夹拖拽至此处导入...")
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #181825; border: 1px solid #313244; border-radius: 12px;
                padding: 10px; color: #cdd6f4; font-family: 'Consolas', 'Menlo', 'monospace'; font-size: 16px;
            }
        """)
        main_layout.addWidget(self.console)

        # 底部动作条 (带色彩逻辑的按钮)
        button_layout = QHBoxLayout()
        btn_base_style = "QPushButton { border-radius: 8px; padding: 8px 12px; color: white; font-weight: bold; font-family: 'Microsoft YaHei', 'PingFang SC'; }"
        
        # 按钮定义配置 (合并了旧逻辑与新 UI)
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
            btn.setStyleSheet(f"{btn_base_style} QPushButton {{ background-color: {bg}; }} QPushButton:hover {{ background-color: {hover}; }}")
            btn.clicked.connect(func)
            button_layout.addWidget(btn)

        main_layout.addLayout(button_layout)
        self.global_layout.addWidget(self.main_container)

        # --- 4. 右侧预览管理面板 (完整新 UI 设计) ---
        self.preview_drawer = QFrame()
        self.preview_drawer.setFixedWidth(0)
        self.preview_drawer.setStyleSheet("background-color: #11111b; border-left: 1px solid #313244;")
        drawer_layout = QVBoxLayout(self.preview_drawer)
        drawer_layout.setContentsMargins(12, 15, 12, 15)
        drawer_layout.setSpacing(8)

        title = QLabel("动画预览")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #89b4fa; font-weight: bold; border: none; font-size: 14px; margin-bottom: 2px;")
        drawer_layout.addWidget(title)

        self.preview_screen = QLabel("🎬")
        self.preview_screen.setFixedSize(256, 256)
        self.preview_screen.setAlignment(Qt.AlignCenter)
        self.preview_screen.setStyleSheet("background-color: #000000; border-radius: 6px; border: 1px solid #313244; color: #45475a;")
        drawer_layout.addWidget(self.preview_screen, 0, Qt.AlignCenter)

        playback_layout = QHBoxLayout()
        playback_layout.setSpacing(4)
        self.btn_first = self.create_mini_btn("⏮", self.first_frame)
        self.btn_prev = self.create_mini_btn("◀", self.prev_frame)
        self.btn_play = self.create_mini_btn("▶", self.toggle_playback)
        self.btn_next = self.create_mini_btn("▶️", self.next_frame)
        self.btn_last = self.create_mini_btn("⏭", self.last_frame)
        for b in [self.btn_first, self.btn_prev, self.btn_play, self.btn_next, self.btn_last]:
            playback_layout.addWidget(b)
        drawer_layout.addLayout(playback_layout)

        self.res_list_display = QTextEdit()
        self.res_list_display.setReadOnly(True)
        self.res_list_display.setPlaceholderText("待加载资源序列...")
        self.res_list_display.setStyleSheet("background-color: #181825; border: 1px solid #313244; font-size: 12px; color: #a6adc8;")
        drawer_layout.addWidget(self.res_list_display)
        
        self.global_layout.addWidget(self.preview_drawer)

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
        self.add_log(f"🎬 预览面板已{'收起' if is_expanded else '展开'}", "#a6e3a1")

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = BingoPacker()
    window.show()
    sys.exit(app.exec())