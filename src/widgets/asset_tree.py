import os
from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QPushButton, 
                               QHBoxLayout, QWidget, QLineEdit, QLabel, QStackedWidget)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QCursor

class AssetTree(QTreeWidget):
    segment_selected = Signal(str, str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setIndentation(0)
        self.setAcceptDrops(True)
        
        # --- 滚动优化：修复点击最后一行时的跳动 ---
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QTreeWidget.ScrollPerPixel) # 像素级滚动更平滑
        self.setAutoScroll(False) # 禁用自动滚动校准
        # ---------------------------------------

        self.setStyleSheet("""
            QTreeWidget { 
                background-color: #181825; 
                border: 2px solid #313244; 
                border-radius: 12px; 
                outline: none;
                /* 关键：确保容器不会裁剪掉内部的 margin 效果 */
                padding: 2px; 
            }
            
            /* 必须针对 viewport 设置透明，否则圆角处会有底色残留 */
            QTreeWidget QWidget {
                background: transparent;
            }

            QTreeWidget::item { 
                height: 40px; 
                border-bottom: 1px solid #1e1e2e; 
                /* 左右留出空隙，防止高亮块直接撞上父容器的边框 */
                margin-left: 2px;
                margin-right: 2px;
            }
            
            QTreeWidget::item:selected { 
                background-color: #2d3f5d; 
                /* 赋予选中块自己的圆角，使其与父容器弧度匹配 */
                border-radius: 8px; 
            }
            
            /* 移除最后一行底部的分割线，防止视觉干扰 */
            QTreeWidget::item:last {
                border-bottom: none;
            }

            QLabel#NameLabel { 
                background: transparent; border: none; color: #cdd6f4; font-size: 13px; 
            }
            QTreeWidget::item:selected QLabel#NameLabel { color: #89b4fa; }

            QLineEdit#NameEditor { 
                background: #1e1e2e; border: 1px solid #89b4fa; 
                border-radius: 4px; color: #cdd6f4;
                padding: 0px 4px; selection-background-color: #45475a;
            }
        """)

    def _create_name_widget(self, initial_text, width):
        stack = QStackedWidget()
        stack.setFixedWidth(width)
        stack.setFixedHeight(30)
        # 核心：将 stack 本身存入子控件，方便在过滤器中直接取出
        
        label = QLabel(initial_text)
        label.setObjectName("NameLabel")
        label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        label.setProperty("parent_stack", stack) # 绑定引用
        
        editor = QLineEdit(initial_text)
        editor.setObjectName("NameEditor")
        editor.setProperty("parent_stack", stack) # 绑定引用
        
        stack.addWidget(label)  # Index 0
        stack.addWidget(editor) # Index 1
        
        label.installEventFilter(self)
        editor.installEventFilter(self)
        editor.editingFinished.connect(lambda: self._finalize_edit(stack))
        
        return stack

    def eventFilter(self, obj, event):
        # 处理 Label 双击
        if isinstance(obj, QLabel) and obj.objectName() == "NameLabel":
            if event.type() == QEvent.MouseButtonDblClick:
                stack = obj.property("parent_stack")
                if stack:
                    editor = stack.widget(1)
                    editor.setText(obj.text())
                    stack.setCurrentIndex(1) # 切换到 QLineEdit
                    editor.setFocus()
                    editor.selectAll()
                    return True
        
        # 处理 Editor 失去焦点
        elif isinstance(obj, QLineEdit) and obj.objectName() == "NameEditor":
            if event.type() == QEvent.FocusOut:
                stack = obj.property("parent_stack")
                if stack:
                    self._finalize_edit(stack)
                    
        return super().eventFilter(obj, event)

    def _finalize_edit(self, stack):
        """同步文字并切回展示态"""
        label = stack.widget(0)
        editor = stack.widget(1)
        if stack.currentIndex() == 1: # 确保当前是编辑态才切回
            label.setText(editor.text())
            stack.setCurrentIndex(0)
            self.setFocus()

    # --- 保持 add_asset, add_segment 等逻辑不变 ---
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
        dot.setStyleSheet(f"color: {dot_color}; font-size: 14px; background: none;")
        
        name_stack = self._create_name_widget(name, 140)
        
        btn = QPushButton("+")
        btn.setFixedSize(22, 22)
        btn.setStyleSheet("QPushButton{background:#313244;color:#a6adc8;border:none;border-radius:4px;} QPushButton:hover{background:#45475a;}")
        btn.clicked.connect(lambda: self.add_segment(root, "新片段", 0, 10))
        
        layout.addWidget(dot)
        layout.addWidget(name_stack)
        layout.addStretch()
        layout.addWidget(btn)
        
        self.setItemWidget(root, 0, container)
        self.add_segment(root, "Default Loop", 0, 10)
        root.setExpanded(True)

    def add_segment(self, parent, name, start, end):
        child = QTreeWidgetItem(parent)
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(28, 0, 10, 0)
        
        name_stack = self._create_name_widget(name, 100)

        f_style = "background:#11111b; border:1px solid #313244; color:#fab387; border-radius:4px;"
        s_edit = QLineEdit(str(start)); s_edit.setFixedWidth(30); s_edit.setStyleSheet(f_style)
        e_edit = QLineEdit(str(end)); e_edit.setFixedWidth(30); e_edit.setStyleSheet(f_style)
        
        layout.addWidget(QLabel("🎬"))
        layout.addWidget(name_stack)
        layout.addStretch()
        layout.addWidget(s_edit); layout.addWidget(QLabel("-")); layout.addWidget(e_edit)
        
        self.setItemWidget(child, 0, container)
        return child

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
    
    # def mousePressEvent(self, event):
    #     # 记录当前的滚动条位置
    #     pos = self.verticalScrollBar().value()
    #     super().mousePressEvent(event)
    #     # 强制恢复位置，防止因为 EnsureVisible 导致的自动跳动
    #     self.verticalScrollBar().setValue(pos)