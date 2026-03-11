import os
from PySide6.QtWidgets import QFileDialog, QListView, QTreeView, QAbstractItemView
from PySide6.QtGui import QTextCursor
from .asset_manager import AssetManager

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
        file_dialog.setNameFilter("All Supported (*.png *.jpg *.jpeg *.svg *.webp *.bmp);;Vector (*.svg);;Images (*.png *.jpg)")

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
        path = os.path.normpath(path)
        
        # --- 核心修复：区分文件和文件夹 ---
        if os.path.isdir(path):
            # 如果拖入的是文件夹：读取该目录下所有有效图
            folder_path = path
            valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.svg')
            files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_exts)]
            files.sort()
            
            if not files: return
            
            if folder_path not in self.selected_folders:
                self.selected_folders.append(folder_path)
            
            new_files = [os.path.join(folder_path, f) for f in files]
            self.asset_files.extend(new_files)
            
            # 文件夹导入日志
            self.add_log(f"-> <b>已导入目录:</b> <span style='color:#89b4fa;'>{os.path.basename(folder_path)}</span>", "#89b4fa")
            self.add_log(f"-> 包含帧数: {len(files)} 帧", "#a6e3a1")
        else:
            # 如果拖入的是单张图片：只处理这一张
            valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.svg')
            if path.lower().endswith(valid_exts):
                if path not in self.asset_files:
                    self.asset_files.append(path)
                    # 单图导入日志（完全对齐你要求的格式）
                    self.add_log(f"-> 单帧图片: <span style='color:#fab387;'>{os.path.basename(path)}</span>", "#fab387")

    def add_log(self, msg, color="#cdd6f4", replace_last=False):
        # 构造 HTML 内容
        log_html = f'<div style="color:{color}; line-height: 110%; margin-bottom: 2px;">{msg}</div>'
        
        if replace_last:
            # 获取光标
            cursor = self.console.textCursor()
            # 移动到最后并选中最后一行内容
            cursor.movePosition(QTextCursor.End)
            cursor.movePosition(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
            # 删除最后一行
            cursor.removeSelectedText()
            # 插入新内容（进度条）
            cursor.insertHtml(log_html)
        else:
            # 正常模式：直接追加
            self.console.append(log_html)
            
        # 滚动到底部
        self.console.moveCursor(QTextCursor.End)
    
    def on_clear_content(self):
        # 1. 清空仓库数据
        AssetManager()._storage.clear()
        
        # 2. 清空 UI 显示
        self.console.clear()
        self.preview_panel.asset_tree.clear() # 树也要清空
        
        # 3. 如果编辑器正在显示，也让它重置
        if hasattr(self.editor_page, 'reset_editor'):
            self.editor_page.reset_editor()
        
        # 3. 打印清空成功的提示 (使用原版黄色字体风格)
        self.add_log("♻️ <b>资源列表已清空</b>", "#f38ba8")
  
        
        # 4. 如果预览面板有内容，也进行重置（可选，视你预览面板的实现而定）
        if hasattr(self, 'preview_panel'):
            self.preview_panel.clear_preview()