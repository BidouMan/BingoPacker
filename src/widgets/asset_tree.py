import os
from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QPushButton, 
                               QHBoxLayout, QWidget, QLineEdit, QLabel, QStackedWidget, QAbstractItemView)
from PySide6.QtCore import Qt, Signal, QEvent

class AssetTree(QTreeWidget):
    segment_selected = Signal(str, str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setIndentation(0)
        self.setAcceptDrops(True)
        
        # 滚动设置：必须使用 ScrollPerPixel 才能实现像素级精准对齐
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel) 
        self.setAutoScroll(False)

        self.setStyleSheet("""
            QTreeWidget { 
                background-color: #181825; 
                border: none; 
                border-radius: 12px; 
                outline: none;
                padding: 0px; 
            }
            
            QTreeWidget QWidget { background: transparent; }

            QTreeWidget::item { 
                background: transparent;
                border: none;
                height: 40px;
            }
            QTreeWidget::item:selected { background: transparent; }

            /* --- 父资源行样式 --- */
            QWidget#ParentContainer {
                background-color: transparent;
                border-bottom: 1px solid #313244; /* 底部分割线 */
            }
            QWidget#ParentContainer[selected="true"] {
                background-color: #2d3f5d;
                border-bottom: 1px solid #2d3f5d; /* 选中时隐藏线 */
            }

            /* --- 子片段行样式 --- */
            QWidget#ChildContainer {
                background-color: rgba(255, 255, 255, 0.03); /* 极微弱的白色半透明，产生层级感 */
                margin: 2px 8px; /* 四周留白，看起来像独立的胶囊块 */
                border-radius: 6px; 
            }
            QWidget#ChildContainer[selected="true"] {
                background-color: #3e4451; 
            }

            /* 顶部圆角逻辑：只针对视觉第一行 */
            QWidget#ParentContainer[position="first"][selected="true"] {
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }

            /* 底部圆角逻辑：只有超过6行且到底时触发 */
            QWidget#ParentContainer[position="last"][selected="true"],
            QWidget#ChildContainer[position="last"][selected="true"] {
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }

            /* 文字与输入框样式 */
            QLabel#NameLabel { background: transparent; color: #cdd6f4; font-size: 13px; }
            QWidget[selected="true"] QLabel#NameLabel { color: #89b4fa; }
            
            QLineEdit#NameEditor { 
                background-color: #0f0f17; 
                border: none;
                border-radius: 4px; 
                color: #89b4fa; 
                padding: 0px 6px;
                selection-background-color: rgba(137, 180, 250, 60);
                selection-color:white            
            }

            /* 数字输入框样式 */
            QLineEdit#DigitEdit {
                background: #11111b; 
                border: 1px solid #313244; 
                color: #fab387; 
                border-radius: 4px; 
                padding: 0px;
                font-size: 11px;
            }
        """)

        # 监听交互
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.verticalScrollBar().valueChanged.connect(lambda: self._update_item_states())

    def _get_all_visible_items(self):
        items = []
        def collect(item):
            for i in range(item.childCount()):
                child = item.child(i)
                items.append(child)
                if child.isExpanded(): collect(child)
        for i in range(self.topLevelItemCount()):
            root = self.topLevelItem(i)
            items.append(root)
            if root.isExpanded(): collect(root)
        return items

    def _on_selection_changed(self):
        selected = self.selectedItems()
        if not selected: return
        
        target_item = selected[0]
        all_visible = self._get_all_visible_items()
        
        # 超过6行时的强行吸附逻辑
        if len(all_visible) > 6:
            try:
                current_idx = all_visible.index(target_item)
                # 如果选中的是最后两行，强制滚到底部对齐
                if current_idx >= len(all_visible) - 1:
                    self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
                else:
                    self.scrollToItem(target_item, QAbstractItemView.EnsureVisible)
            except ValueError: pass
        else:
            self.scrollToItem(target_item, QAbstractItemView.EnsureVisible)
        
        self._update_item_states(all_visible)

    def _update_item_states(self, all_visible=None):
        if all_visible is None:
            all_visible = self._get_all_visible_items()
            
        vh = self.viewport().height()
        total = len(all_visible)
        scroll_at_max = self.verticalScrollBar().value() >= self.verticalScrollBar().maximum() - 1
        
        for index, item in enumerate(all_visible):
            widget = self.itemWidget(item, 0)
            if not widget: continue

            widget.setProperty("selected", "true" if item.isSelected() else "false")
            
            rect = self.visualItemRect(item)
            pos = "none"
            if rect.top() <= 0:
                pos = "first"
            elif total > 6:
                if rect.bottom() >= vh - 2 or (scroll_at_max and index == total - 1):
                    pos = "last"
            
            widget.setProperty("position", pos)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _create_name_widget(self, text, width):
        stack = QStackedWidget()
        stack.setFixedWidth(width); stack.setFixedHeight(30)
        label = QLabel(text); label.setObjectName("NameLabel")
        label.setProperty("parent_stack", stack)
        editor = QLineEdit(text); editor.setObjectName("NameEditor")
        editor.setProperty("parent_stack", stack)
        stack.addWidget(label); stack.addWidget(editor)
        label.installEventFilter(self); editor.installEventFilter(self)
        editor.editingFinished.connect(lambda: self._finalize_edit(stack))
        return stack

    def eventFilter(self, obj, event):
        if isinstance(obj, QLabel) and event.type() == QEvent.MouseButtonDblClick:
            stack = obj.property("parent_stack")
            if stack:
                ed = stack.widget(1)
                ed.setText(obj.text())
                stack.setCurrentIndex(1); ed.setFocus(); ed.selectAll()
                return True
        elif isinstance(obj, QLineEdit) and event.type() == QEvent.FocusOut:
            stack = obj.property("parent_stack")
            if stack: self._finalize_edit(stack)
        return super().eventFilter(obj, event)

    def _finalize_edit(self, stack):
        l, e = stack.widget(0), stack.widget(1)
        if stack.currentIndex() == 1:
            l.setText(e.text()); stack.setCurrentIndex(0); self.setFocus()

    def add_asset(self, path):
        name = os.path.splitext(os.path.basename(path))[0]
        ext = os.path.splitext(path)[1].lower()
        dot_color = "#a6e3a1" if ext == ".sprite3" else "#cba6f7"
        if os.path.isdir(path): dot_color = "#89b4fa"
        
        root = QTreeWidgetItem(self)
        container = QWidget(); container.setObjectName("ParentContainer")
        layout = QHBoxLayout(container); layout.setContentsMargins(10, 0, 10, 0)
        
        dot = QLabel("●"); dot.setStyleSheet(f"color: {dot_color}; font-size: 14px;")
        ns = self._create_name_widget(name, 140)
        btn = QPushButton("+"); btn.setFixedSize(22, 22)
        btn.setStyleSheet("QPushButton{background:#313244;color:#a6adc8;border:none;border-radius:4px;} QPushButton:hover{background:#45475a;}")
        btn.clicked.connect(lambda: self.add_segment(root, "新片段", 0, 10))
        
        layout.addWidget(dot); layout.addWidget(ns); layout.addStretch(); layout.addWidget(btn)
        self.setItemWidget(root, 0, container)
        self.add_segment(root, "Default Loop", 0, 10)
        root.setExpanded(True)
        self._update_item_states()

    def add_segment(self, parent, name, start, end):
        child = QTreeWidgetItem(parent)
        container = QWidget(); container.setObjectName("ChildContainer")
        layout = QHBoxLayout(container); layout.setContentsMargins(12, 0, 10, 0)
        
        ns = self._create_name_widget(name, 100)
        
        s_edit = QLineEdit(str(start))
        s_edit.setObjectName("DigitEdit")
        s_edit.setFixedSize(30, 22)
        s_edit.setAlignment(Qt.AlignCenter)
        
        e_edit = QLineEdit(str(end))
        e_edit.setObjectName("DigitEdit")
        e_edit.setFixedSize(30, 22)
        e_edit.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(QLabel("🎬"))
        layout.addWidget(ns)
        layout.addStretch()
        layout.addWidget(s_edit); layout.addWidget(QLabel("-")); layout.addWidget(e_edit)
        
        self.setItemWidget(child, 0, container)
        self._update_item_states()
        return child

    def dragEnterEvent(self, event): event.acceptProposedAction()
    def dragMoveEvent(self, event): event.acceptProposedAction()
    def dropEvent(self, event):
        for url in event.mimeData().urls(): self.add_asset(url.toLocalFile())