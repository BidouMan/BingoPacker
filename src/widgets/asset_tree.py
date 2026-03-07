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

            QWidget#ItemContainer {
                background-color: transparent;
                border-radius: 0px;
            }

            QWidget#ItemContainer[selected="true"] {
                background-color: #2d3f5d;
            }

            /* 第一行：顶部圆角 */
            QWidget#ItemContainer[position="first"][selected="true"] {
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }

            /* 视觉最后一行：底部圆角 */
            QWidget#ItemContainer[position="last"][selected="true"] {
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }

            QLabel#NameLabel { background: transparent; color: #cdd6f4; font-size: 13px; }
            QWidget#ItemContainer[selected="true"] QLabel#NameLabel { color: #89b4fa; }
            QLineEdit#NameEditor { 
                background-color: #0f0f17; 
                border: none;
                border-radius: 4px; 
                /* 文字改为亮蓝色，提示处于编辑模式 */
                color: #89b4fa; 
                padding: 0px 6px;
                /* 选中文本时的底色，使用半透明蓝色增加高级感 */
                selection-background-color: rgba(137, 180, 250, 60);
                selection-color: #ffffff;
            }
        """)

        # 监听选中变化
        self.itemSelectionChanged.connect(self._on_selection_changed)
        # 监听滚动条变化：滚动时也要实时更新谁是“视觉最后一行”
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
        
        # 1. 检查选中的项是否在“视觉底部区域”
        # 如果当前总行数超过 6 行，且选中的是最后几行之一
        if len(all_visible) > 6:
            # 找到当前选中项在所有可见项中的索引
            try:
                current_idx = all_visible.index(target_item)
                # 如果选中的是最后一行，或者已经是倒数第二行且用户在向下点
                if current_idx >= len(all_visible) - 1:
                    # 强制滚动条到底部，确保像素级对齐
                    self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
                else:
                    # 否则正常确保可见即可
                    self.scrollToItem(target_item, QAbstractItemView.EnsureVisible)
            except ValueError:
                pass
        else:
            self.scrollToItem(target_item, QAbstractItemView.EnsureVisible)
        
        # 2. 立即更新视觉状态（谁是视觉第一行/最后一行）
        self._update_item_states(all_visible)

    def _update_item_states(self, all_visible=None):
        if all_visible is None:
            all_visible = self._get_all_visible_items()
            
        viewport_height = self.viewport().height()
        total_count = len(all_visible)
        # 判定滚动条是否已经触底
        scroll_at_max = self.verticalScrollBar().value() >= self.verticalScrollBar().maximum() - 1
        
        for index, item in enumerate(all_visible):
            widget = self.itemWidget(item, 0)
            if not widget: continue

            # 1. 设置选中状态属性
            widget.setProperty("selected", "true" if item.isSelected() else "false")
            
            # 2. 视觉位置计算
            visual_rect = self.visualItemRect(item)
            item_top = visual_rect.top()
            item_bottom = visual_rect.bottom()
            
            pos = "none"
            
            # --- 第一行判定 ---
            if item_top <= 0:
                pos = "first"
            
            # --- 最后一行判定 (增加 6 行门槛) ---
            # 只有当总行数超过 6 行时，才去触发视觉底部的圆角逻辑
            elif total_count > 6:
                # 视觉最后一行：底部触达视口边缘，或者滚动条已置底且它是最后一个 item
                if item_bottom >= viewport_height - 2 or (scroll_at_max and index == total_count - 1):
                    pos = "last"
            
            # 3. 应用并刷新样式
            widget.setProperty("position", pos)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    # --- 后续方法（add_asset等）保持不变 ---
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
        container = QWidget(); container.setObjectName("ItemContainer")
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
        container = QWidget(); container.setObjectName("ItemContainer")
        layout = QHBoxLayout(container); layout.setContentsMargins(28, 0, 10, 0)
        ns = self._create_name_widget(name, 100)
        
        # 在 QSS 样式中添加 padding:0 确保不偏移
        f_style = "background:#11111b; border:1px solid #313244; color:#fab387; border-radius:4px; padding:0px;"
        
        s_edit = QLineEdit(str(start))
        s_edit.setFixedWidth(30)
        s_edit.setStyleSheet(f_style)
        # 核心修改：设置文字居中
        s_edit.setAlignment(Qt.AlignCenter) 
        
        e_edit = QLineEdit(str(end))
        e_edit.setFixedWidth(30)
        e_edit.setStyleSheet(f_style)
        # 核心修改：设置文字居中
        e_edit.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(QLabel("🎬"))
        layout.addWidget(ns)
        layout.addStretch()
        layout.addWidget(s_edit)
        layout.addWidget(QLabel("-"))
        layout.addWidget(e_edit)
        
        self.setItemWidget(child, 0, container)
        self._update_item_states()
        return child
    def dragEnterEvent(self, event): event.acceptProposedAction()
    def dragMoveEvent(self, event): event.acceptProposedAction()
    def dropEvent(self, event):
        for url in event.mimeData().urls(): self.add_asset(url.toLocalFile())