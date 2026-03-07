import os
import zipfile
from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QPushButton, 
                               QHBoxLayout, QWidget, QLineEdit, QLabel)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QIcon

class AssetTree(QTreeWidget):
    segment_selected = Signal(str, str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setIndentation(0)
        self.setAcceptDrops(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # QSS 样式控制
        self.setStyleSheet("""
            QTreeWidget { 
                background-color: #181825; border: 2px solid #313244; 
                border-radius: 12px; outline: none;
            }
            QTreeWidget::item { height: 40px; border-bottom: 1px solid #1e1e2e; }
            QTreeWidget::item:selected { background-color: #2d3f5d; }
            
            /* 默认态：无边框，无背景，无文字选中高亮 */
            QLineEdit { 
                background: transparent; border: none; color: #cdd6f4; 
                selection-background-color: transparent; /* 关键：禁止平时双击变蓝 */
            }
            QTreeWidget::item:selected QLineEdit { color: #89b4fa; }
            QTreeWidget::item:selected QLabel { color: #89b4fa; }

            /* 编辑态：开启边框和背景 */
            QLineEdit[editing="true"] { 
                background: #1e1e2e; 
                border: 1px solid #89b4fa; 
                border-radius: 4px; 
                color: #cdd6f4 !important;
                selection-background-color: #45475a; /* 编辑时允许看到选中 */
            }
        """)

    def _setup_name_edit(self, edit):
        """初始化输入框：彻底静默"""
        edit.setReadOnly(True)
        edit.setFocusPolicy(Qt.NoFocus)
        edit.setCursor(Qt.ArrowCursor) # 平时是普通指针
        edit.setProperty("editing", "false")
        
        # 必须确保不穿透鼠标事件，否则无法激活
        edit.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        
        edit.installEventFilter(self)
        # 依然保留这个，处理按下回车的情况
        edit.editingFinished.connect(lambda: self._stop_edit(edit))

    def eventFilter(self, obj, event):
        if isinstance(obj, QLineEdit):
            # 情况 1: 双击激活改名
            if event.type() == QEvent.MouseButtonDblClick:
                if obj.property("editing") == "false":
                    self._start_edit(obj)
                    return True
            
            # 情况 2: 核心修复 - 只要失去焦点，立刻恢复指针和样式
            # 无论是因为改了名、按了Esc，还是直接点到了别处
            elif event.type() == QEvent.FocusOut:
                if obj.property("editing") == "true":
                    self._stop_edit(obj)
                    # 注意：这里不 return True，让系统继续处理失去焦点的后续动作
        
        return super().eventFilter(obj, event)

    def _start_edit(self, edit):
        """激活编辑态"""
        edit.setReadOnly(False)
        edit.setFocusPolicy(Qt.StrongFocus)
        edit.setCursor(Qt.IBeamCursor) # 切换为输入光标
        edit.setProperty("editing", "true")
        
        # 刷新 QSS 以显示边框
        edit.style().unpolish(edit)
        edit.style().polish(edit)
        
        edit.setFocus()
        edit.selectAll()

    def _stop_edit(self, edit):
        """退出编辑态：强制恢复指针"""
        # 防止重复触发（因为 editingFinished 和 FocusOut 可能会撞车）
        if edit.property("editing") == "false":
            return

        edit.deselect()
        edit.setReadOnly(True)
        edit.setFocusPolicy(Qt.NoFocus)
        edit.setCursor(Qt.ArrowCursor) # 强制切回普通指针
        edit.setProperty("editing", "false")
        
        # 刷新 QSS 隐藏边框
        edit.style().unpolish(edit)
        edit.style().polish(edit)
        
        edit.clearFocus()
        # 核心：手动让父窗口拿回焦点，彻底断掉 QLineEdit 的光标感应
        self.setFocus()

    # --- 以下保持你的 add_asset 和 add_segment 逻辑即可 ---
    def add_asset(self, path):
        name = os.path.splitext(os.path.basename(path))[0]
        ext = os.path.splitext(path)[1].lower()
        dot_color = "#a6e3a1" if ext == ".sprite3" else "#cba6f7"
        if os.path.isdir(path): dot_color = "#89b4fa"

        root = QTreeWidgetItem(self)
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 0, 10, 0)
        
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {dot_color}; font-size: 14px;")
        
        name_edit = QLineEdit(name)
        name_edit.setFixedWidth(140)
        self._setup_name_edit(name_edit) 
        
        btn = QPushButton("+")
        btn.setFixedSize(22, 22)
        btn.setStyleSheet("QPushButton{background:#313244;color:#a6adc8;border:none;border-radius:4px;} QPushButton:hover{background:#45475a;}")
        btn.clicked.connect(lambda: self.add_segment(root, "新片段", 0, 10))
        
        layout.addWidget(dot); layout.addWidget(name_edit); layout.addStretch(); layout.addWidget(btn)
        self.setItemWidget(root, 0, container)
        self.add_segment(root, "Default Loop", 0, 10)
        root.setExpanded(True)

    def add_segment(self, parent, name, start, end):
        child = QTreeWidgetItem(parent)
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(28, 0, 10, 0)
        
        n_edit = QLineEdit(name)
        n_edit.setFixedWidth(100)
        self._setup_name_edit(n_edit)

        f_style = "background:#11111b; border:1px solid #313244; color:#fab387; border-radius:4px;"
        s_edit = QLineEdit(str(start)); s_edit.setFixedWidth(30); s_edit.setStyleSheet(f_style)
        e_edit = QLineEdit(str(end)); e_edit.setFixedWidth(30); e_edit.setStyleSheet(f_style)
        
        layout.addWidget(QLabel("🎬")); layout.addWidget(n_edit); layout.addStretch()
        layout.addWidget(s_edit); layout.addWidget(QLabel("-")); layout.addWidget(e_edit)
        self.setItemWidget(child, 0, container)
        return child
    
    # ... 其他计算逻辑保持不变 ...

    def _calculate_frame_count(self, path):
        try:
            if os.path.isdir(path):
                return len([f for f in os.listdir(path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))])
            return 10
        except: return 1

    def dragEnterEvent(self, event): event.acceptProposedAction()
    def dragMoveEvent(self, event): event.acceptProposedAction()
    def dropEvent(self, event):
        for url in event.mimeData().urls(): self.add_asset(url.toLocalFile())