import os
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QMenu, QAbstractItemView
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon
from ..utils import get_resource_path

class AssetTree(QTreeWidget):
    # 定义信号：(文件夹路径, 起始帧, 结束帧)
    segment_selected = Signal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setIndentation(18)
        self.setAnimated(True)
        # 允许双击编辑名称
        self.setEditTriggers(QAbstractItemView.DoubleClicked)
        
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 10px;
                color: #cdd6f4;
                font-family: 'Segoe UI', sans-serif;
            }
            QTreeWidget::item { height: 32px; border-bottom: 1px solid #1e1e2e; }
            QTreeWidget::item:selected { background-color: #313244; color: #89b4fa; border-radius: 4px; }
        """)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.itemClicked.connect(self.handle_item_clicked)

    def add_asset(self, folder_path, frame_count):
        """添加主资产文件夹节点"""
        folder_name = os.path.basename(folder_path)
        root_item = QTreeWidgetItem(self)
        root_item.setText(0, f"📁 {folder_name}")
        # 存储原始路径和信息
        root_item.setData(0, Qt.UserRole, {"type": "root", "path": folder_path, "total": frame_count})
        
        # 默认生成一个“全周期”片段
        self.add_segment(root_item, "Default Loop", 0, frame_count - 1)
        root_item.setExpanded(True)

    def add_segment(self, parent_item, name, start, end):
        """添加动画片段子节点"""
        child = QTreeWidgetItem(parent_item)
        child.setText(0, f"🎬 {name} [{start}-{end}]")
        child.setFlags(child.flags() | Qt.ItemIsEditable) # 允许改名
        child.setData(0, Qt.UserRole, {"type": "segment", "start": start, "end": end})
        return child

    def handle_item_clicked(self, item, column):
        """点击列表项，触发预览"""
        data = item.data(0, Qt.UserRole)
        if not data: return
        
        # 如果点的是根目录，播全部；点的是片段，播片段
        if data["type"] == "root":
            self.segment_selected.emit(data["path"], 0, data["total"] - 1)
        else:
            parent_path = item.parent().data(0, Qt.UserRole)["path"]
            self.segment_selected.emit(parent_path, data["start"], data["end"])

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item: return
        
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244; }")
        
        if item.data(0, Qt.UserRole)["type"] == "root":
            act_add = QAction("➕ 新增动画片段", self)
            # 这里将来连接弹出输入框逻辑
            menu.addAction(act_add)
            
        act_del = QAction("🗑️ 删除", self)
        menu.addAction(act_del)
        menu.exec(self.mapToGlobal(pos))