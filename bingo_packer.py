import sys
import os
import json
import zipfile
import hashlib
import platform
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                               QFileDialog, QListView, QTreeView, QAbstractItemView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QTextCursor

def get_resource_path(relative_path):
    """ 
    超强兼容的资源获取逻辑：
    1. 适配 Windows PyInstaller --onefile (%TEMP% 目录)
    2. 适配 macOS .app Bundle (Contents/Resources 目录)
    3. 适配本地开发环境
    """
    # Windows PyInstaller 临时目录
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    
    # macOS .app 束资源目录检测
    if platform.system() == "Darwin":
        # 获取二进制文件所在目录 (Contents/MacOS)
        main_dir = os.path.dirname(sys.executable)
        # 指向 Contents/Resources
        mac_res_path = os.path.join(os.path.dirname(main_dir), 'Resources', relative_path)
        if os.path.exists(mac_res_path):
            return mac_res_path

    # 本地环境或 fallback
    return os.path.join(os.path.abspath("."), relative_path)

# --- 路径环境锁定 ---
if getattr(sys, 'frozen', False):
    # 强制将工作目录设为程序本体所在目录，防止双击启动时路径偏移
    bundle_dir = os.path.dirname(sys.executable)
    os.chdir(bundle_dir)
else:
    bundle_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(bundle_dir)

class BingoPacker(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_folders = []
        # 启用窗口拖拽接收功能
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        # 1. 窗口属性锁定
        self.setWindowTitle("Bingo Sprite Packer")
        self.setFixedSize(760, 620)

        icon_path = get_resource_path("logo.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 完美保留 QSS 样式设计
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1e1e2e; color: #cdd6f4; }
            
            /* 禁用右下角的缩放手柄，解决按钮被遮挡问题 */
            QSizeGrip {
                width: 0;
                height: 0;
                image: none;
            }

            /* 修复对话框内容 */
            QFileDialog QAbstractItemView {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 8px;
            }
            QFileDialog QPushButton {
                background-color: #313244;
                color: white;
                border-radius: 6px;
                padding: 5px 12px;
                min-width: 60px;
            }
            QFileDialog QPushButton:hover {
                background-color: #45475a;
            }
            
            QFileDialog QHeaderView::section {
                background-color: #313244;
                color: #cdd6f4;
                padding: 4px;
                border: none;
            }
            
            QFileDialog QLineEdit {
                background-color: #11111b;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 2px;
            }
            QFileDialog QLabel { color: #cdd6f4; }
        """)
        
        # 图标处理：Mac 下通常打包为 .app，logo.ico 会被自动转换，这里保留逻辑
        if os.path.exists("logo.ico"):
            self.setWindowIcon(QIcon("logo.ico"))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        header = QLabel("BLOCKBINGO 资产打包工具")
        # PySide6 中的对齐方式写法
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("color: #89b4fa; font-size: 24px; font-weight: bold; font-family: 'Microsoft YaHei', 'PingFang SC';")
        main_layout.addWidget(header)

        # 日志控制台
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setPlaceholderText("可直接将文件夹拖拽至此处导入...")
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 12px;
                padding: 10px;
                color: #cdd6f4;
                font-family: 'Consolas', 'Menlo', 'monospace';
                font-size: 16px;
            }
        """)
        main_layout.addWidget(self.console)

        # 底部动作条
        button_layout = QHBoxLayout()
        # 适配 Mac 的按钮字体
        btn_style = "QPushButton { border-radius: 8px; padding: 8px 15px; color: white; font-weight: bold; font-family: 'Microsoft YaHei', 'PingFang SC'; }"
        
        self.btn_import = QPushButton(" 导入")
        self.btn_import.setStyleSheet(btn_style + "QPushButton { background-color: #313244; } QPushButton:hover { background-color: #45475a; }")
        self.btn_import.clicked.connect(self.pick_folders)

        self.btn_clear = QPushButton(" 清空")
        self.btn_clear.setStyleSheet(btn_style + "QPushButton { background-color: #313244; } QPushButton:hover { background-color: #f38ba8; }")
        self.btn_clear.clicked.connect(self.clear_all)

        self.btn_bgs = QPushButton(" 导出 .bgs")
        self.btn_bgs.setStyleSheet(btn_style + "QPushButton { background-color: #45b573; } QPushButton:hover { background-color: #58ce87; }")
        self.btn_bgs.clicked.connect(lambda: self.run_pack("BGS"))

        self.btn_s3 = QPushButton(" 导出 .sprite3")
        self.btn_s3.setStyleSheet(btn_style + "QPushButton { background-color: #d9793d; } QPushButton:hover { background-color: #e68a4d; }")
        self.btn_s3.clicked.connect(lambda: self.run_pack("Sprite3"))

        button_layout.addWidget(self.btn_import)
        button_layout.addWidget(self.btn_clear)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_bgs)
        button_layout.addWidget(self.btn_s3)
        main_layout.addLayout(button_layout)

    # --- 拖拽识别逻辑 ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        found = 0
        for f in files:
            f = os.path.normpath(f)
            if os.path.isdir(f) and f not in self.selected_folders:
                self.selected_folders.append(f)
                self.add_log(f"📥 拖拽载入: {os.path.basename(f)}", "#89b4fa")
                found += 1
        if found > 0:
            self.add_log(f"✅ 成功增加 {found} 个项目", "#a6e3a1")

    # --- 核心功能逻辑 ---
    def add_log(self, msg, color="#cdd6f4"):
        self.console.append(f'<span style="color:{color}">{msg}</span>')
        self.console.moveCursor(QTextCursor.End)

    def clear_all(self):
        self.selected_folders.clear()
        self.console.clear()
        self.add_log("♻️ 列表已清空", "#f38ba8")

    def pick_folders(self):
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("选择素材文件夹 (支持多选)")
        file_dialog.setFileMode(QFileDialog.Directory)
        file_dialog.setOption(QFileDialog.ShowDirsOnly, True)
        file_dialog.setOption(QFileDialog.DontUseNativeDialog, True) 
        
        # 兼容 PySide6 的多选开启方式
        list_view = file_dialog.findChild(QListView, "listView")
        if list_view:
            list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        tree_view = file_dialog.findChild(QTreeView)
        if tree_view:
            tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        if file_dialog.exec():
            paths = file_dialog.selectedFiles()
            found = 0
            for p in paths:
                p = os.path.normpath(p)
                if os.path.isdir(p) and p not in self.selected_folders:
                    self.selected_folders.append(p)
                    self.add_log(f"📁 导入: {os.path.basename(p)}", "#89b4fa")
                    found += 1
            if found > 0:
                self.add_log(f"✅ 成功载入 {found} 个项目", "#a6e3a1")

    # 保留无损打包逻辑
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Fusion 样式在 Mac 上能保持深色外观的统一性
    app.setStyle("Fusion")
    window = BingoPacker()
    window.show()
    sys.exit(app.exec())