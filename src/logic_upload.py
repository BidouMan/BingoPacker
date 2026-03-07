import os
from PySide6.QtWidgets import QFileDialog, QListView, QTreeView, QAbstractItemView
from PySide6.QtGui import QTextCursor

class UploadLogic:
    def on_upload_folder(self):
        """
        严格还原并修复样式的导入功能：
        1. 禁用原生对话框以实现多选。
        2. 修复按钮过大的问题。
        3. 彻底隐藏右下角的色块遮挡。
        """
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("选择素材 (文件夹或 PNG 图片)")
        file_dialog.setFileMode(QFileDialog.Directory)
        file_dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        file_dialog.setNameFilter("All Files (*);;PNG Images (*.png)")

        # --- 核心修复：对话框专属样式表 ---
        file_dialog.setStyleSheet("""
            /* 1. 按钮基础样式：取消加粗，控制具体高度和内边距 */
            QPushButton { 
                font-weight: normal; 
                padding: 4px 15px; 
                min-width: 70px;
                max-width: 100px;
                height: 24px;
                background-color: #313244;
                border: 1px solid #45475a;
                margin-right: 10px; /* 关键：给右侧留出空间 */
            }
            QPushButton:hover { background-color: #45475a; }

            /* 2. 彻底消灭右下角的“色块手柄”遮挡 */
            QSizeGrip {
                width: 0px;
                height: 0px;
                background: transparent;
            }

            /* 3. 列表区域背景，防止出现奇怪的白色边缘 */
            QListView, QTreeView {
                background-color: #181825;
                border: 1px solid #313244;
                color: #cdd6f4;
            }
        """)

        # 开启多选
        list_view = file_dialog.findChild(QListView, "listView")
        if list_view:
            list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        tree_view = file_dialog.findChild(QTreeView)
        if tree_view:
            tree_view.setSelectionMode(QAbstractItemView.ExtendedSelection)

        if file_dialog.exec():
            paths = file_dialog.selectedFiles()
            for p in paths:
                self.process_import_path(p)

    def process_import_path(self, path):
        """路径解析逻辑，根据原版进行兼容处理"""
        path = os.path.normpath(path)
        # 如果是文件夹
        if os.path.isdir(path):
            folder_path = path
        # 如果是文件，取其所在目录
        else:
            folder_path = os.path.dirname(path)

        valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
        files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_exts)]
        files.sort()

        if not files:
            return

        if folder_path not in self.selected_folders:
            self.selected_folders.append(folder_path)
        
        new_files = [os.path.join(folder_path, f) for f in files]
        self.asset_files.extend(new_files)

        # 还原原版日志
        # self.add_log("-"*40, "#6272a4")
        self.add_log(f"-> <b>已导入:</b> <span style='color:#89b4fa;'>{os.path.basename(folder_path)}</span>", "#89b4fa")
        self.add_log(f"-> 包含帧数: {len(files)} 帧", "#a6e3a1")
        self.add_log("-"*40, "#6272a4")

    def add_log(self, msg, color="#cdd6f4"):
        # 核心改动：只设置颜色和行高，不设置字体，让它自动继承 console 的 Consolas 字体
        log_html = f'<div style="color:{color}; line-height: 110%; margin-bottom: 2px;">{msg}</div>'
        self.console.append(log_html)
        self.console.moveCursor(QTextCursor.End)
    
    def on_clear_content(self):
        """严格还原原版的清空逻辑"""
        # 1. 清空核心数据变量
        self.selected_folders = []
        self.asset_files = []
        
        # 2. 清空 UI 显示
        self.console.clear()
        
        # 3. 打印清空成功的提示 (使用原版黄色字体风格)
        self.add_log("♻️ <b>资源列表已清空</b>", "#f38ba8")
  
        
        # 4. 如果预览面板有内容，也进行重置（可选，视你预览面板的实现而定）
        if hasattr(self, 'preview_panel'):
            self.preview_panel.clear_preview()