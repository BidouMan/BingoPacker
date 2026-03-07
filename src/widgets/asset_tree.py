import os
import zipfile
import json
from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QPushButton, 
                               QHBoxLayout, QWidget, QLineEdit, QLabel)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon

class AssetTree(QTreeWidget):
    # 定义信号：(资源路径, 片段名称, 起始帧, 结束帧)
    segment_selected = Signal(str, str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setIndentation(0)  # 根节点不缩进，保持整洁
        self.setAnimated(True)
        
        # 核心：开启拖拽支持
        self.setAcceptDrops(True)
        
        # 样式美化
        # --- 物理级隐藏滚动条 ---
        # 强制关闭垂直和水平滚动条显示策略，但保留内部滚动逻辑
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 样式美化：通过 handle 和 add-line 等细分项彻底清空滚动条占位
        self.setStyleSheet("""
            QTreeWidget { 
                background-color: #181825; 
                border: 2px solid #313244; 
                border-radius: 12px;
                color: #cdd6f4;
                outline: none;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            }
            /* QSS 二重保险 */
            QScrollBar:vertical, QScrollBar:horizontal {
                width: 0px;
                height: 0px;
                background: transparent;
            }
            
            QTreeWidget::item { 
                height: 40px; 
                border-bottom: 1px solid #1e1e2e; 
            }
            QTreeWidget::item:hover { 
                background-color: #313244; 
            }
            QTreeWidget::item:selected { 
                background-color: #45475a; 
            }
        """)

    # --- 拖拽核心逻辑 ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """处理从本地拖入的文件夹或文件"""
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            self.add_asset(path)

    def add_asset(self, path):
        """导入资源：兼容文件夹、.bgs、.sprite3"""
        if not os.path.exists(path):
            return

        # 判断是否为有效资源
        is_dir = os.path.isdir(path)
        is_bundle = path.lower().endswith(('.bgs', '.sprite3'))
        
        if not (is_dir or is_bundle):
            return

        name = os.path.basename(path)
        # 自动获取该资源内的总帧数
        total_frames = self._calculate_frame_count(path)
        
        # 1. 创建根节点 (显示名称 + [+][🗑️])
        root_item = QTreeWidgetItem(self)
        root_item.setData(0, Qt.UserRole, {"path": path, "type": "root", "total": total_frames})
        
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 0, 10, 0)
        
        icon_str = "📦" if is_bundle else "📂"
        name_label = QLabel(f"{icon_str} {name}")
        name_label.setStyleSheet("font-weight: bold; color: #89b4fa; font-size: 13px; background: transparent;")
        
        # 右侧功能按钮组
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)
        
        add_btn = QPushButton("+")
        add_btn.setFixedSize(22, 22)
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet("""
            QPushButton { background-color: #313244; color: #a6adc8; border-radius: 6px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #89b4fa; color: #11111b; }
        """)
        # 点击加号，基于总帧数新建一个片段
        add_btn.clicked.connect(lambda: self.add_segment(root_item, "新片段", 0, max(0, total_frames - 1)))
        
        btn_layout.addWidget(add_btn)
        
        layout.addWidget(name_label)
        layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.setItemWidget(root_item, 0, container)
        
        # 2. 默认添加一个全周期的片段
        self.add_segment(root_item, "Default Loop", 0, max(0, total_frames - 1))
        root_item.setExpanded(True)

    def add_segment(self, parent_item, name, start, end):
        """添加动画片段行：🎬 [名称] [起始]-[结束]"""
        child = QTreeWidgetItem(parent_item)
        child.setData(0, Qt.UserRole, {"type": "segment"})
        
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(25, 0, 10, 0) # 子节点左侧缩进，体现层级
        layout.setSpacing(6)
        
        icon = QLabel("🎬")
        
        # 动画名称输入框
        name_edit = QLineEdit(name)
        name_edit.setFixedWidth(90)
        name_edit.setStyleSheet("""
            QLineEdit { background: #1e1e2e; border: none; color: #cdd6f4; border-radius: 4px; padding: 2px; }
            QLineEdit:focus { border: 1px solid #89b4fa; }
        """)
        
        # 帧数范围编辑 (起始)
        start_edit = QLineEdit(str(start))
        start_edit.setFixedWidth(35)
        start_edit.setAlignment(Qt.AlignCenter)
        start_edit.setStyleSheet("background: #11111b; border: 1px solid #313244; color: #fab387; border-radius: 4px;")
        
        # 帧数范围编辑 (结束)
        end_edit = QLineEdit(str(end))
        end_edit.setFixedWidth(35)
        end_edit.setAlignment(Qt.AlignCenter)
        end_edit.setStyleSheet("background: #11111b; border: 1px solid #313244; color: #fab387; border-radius: 4px;")
        
        layout.addWidget(icon)
        layout.addWidget(name_edit)
        layout.addStretch()
        layout.addWidget(start_edit)
        layout.addWidget(QLabel("-"))
        layout.addWidget(end_edit)
        
        self.setItemWidget(child, 0, container)
        
        # 自动滚动到新添加的项
        self.scrollToItem(child)
        return child

    def _calculate_frame_count(self, path):
        """统计资源包含的帧数"""
        try:
            if os.path.isdir(path):
                # 统计文件夹下常见的图片格式
                valid_exts = ('.png', '.jpg', '.jpeg', '.webp')
                return len([f for f in os.listdir(path) if f.lower().endswith(valid_exts)])
            elif path.lower().endswith(('.bgs', '.sprite3')):
                # 读取压缩包内的图片数量
                with zipfile.ZipFile(path, 'r') as z:
                    return len([f for f in z.namelist() if f.lower().endswith(('.png', '.jpg', '.svg'))])
        except Exception:
            return 1
        return 0