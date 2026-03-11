import os
from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QPushButton, 
                               QHBoxLayout, QWidget, QLineEdit, QLabel, QStackedWidget, QAbstractItemView)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon

class AssetTree(QTreeWidget):
    segment_changed = Signal(object, dict) # (AssetBundle, segment_dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_settings()
        self._init_style()
        self.itemSelectionChanged.connect(self._handle_selection_event)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _init_settings(self):
        self.setColumnCount(1)
        self.setHeaderHidden(True)
        self.setIndentation(0)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setAcceptDrops(True)

    def _init_style(self):
        self.setStyleSheet("""
            QTreeWidget { background-color: #21252b; border: 1px solid #181a1f; outline: none; }
            QTreeWidget::item { height: 32px; }
            QWidget#ParentContainer { border-bottom: 1px solid #181a1f; }
            QWidget#ParentContainer[selected="true"], QWidget#ChildContainer[selected="true"] { background-color: #2c313a; }
            QLabel#NameLabel { color: #abb2bf; font-size: 13px; }
            QWidget[selected="true"] QLabel#NameLabel { color: #61afef; font-weight: bold; }
            QPushButton#AssetActionBtn { background-color: #353b45; border-radius: 4px; }
            QPushButton#AssetActionBtn:hover { border: 1px solid #61afef; }
        """)

    # --- 数据同步核心 ---
    def update_bundle_data(self, bundle):
        """当编辑器裁切导致帧数变化时，强制刷新UI上的数字"""
        root = self._find_root_by_bundle(bundle)
        if not root: return

        max_f = len(bundle.frames)
        
        # 遍历所有片段行
        for i in range(root.childCount()):
            child = root.child(i)
            seg = child.data(0, Qt.UserRole)
            
            # --- 核心修正：确保结束帧正确且起始帧不越界 ---
            # 如果是单图导入，max_f 为 1，则 end 应为 1
            if seg['end'] < 1 or seg['end'] > max_f or (max_f > 1 and seg['end'] == 1):
                seg['end'] = max_f
            
            # 确保 start 永远不大于 end
            seg['start'] = max(1, min(seg['start'], seg['end']))
            
            # 获取该行挂载的自定义 Widget
            widget = self.itemWidget(child, 0)
            if widget:
                # 通过 ObjectName 精确查找赋值
                edit_s = widget.findChild(QLineEdit, "f_start")
                edit_e = widget.findChild(QLineEdit, "f_end")
                if edit_s and edit_e:
                    edit_s.setText(str(seg['start']))
                    edit_e.setText(str(seg['end']))

        # 触发预览更新
        if root.childCount() > 0:
            first_child = root.child(0)
            self.setCurrentItem(first_child)
            self.segment_changed.emit(bundle, first_child.data(0, Qt.UserRole))

    # --- 节点创建 ---
    def add_bundle(self, bundle):
        root = QTreeWidgetItem(self)
        root.setData(0, Qt.UserRole, bundle)
        self.setItemWidget(root, 0, self._create_root_widget(root, bundle))

        # 确保初始帧数至少为 1
        total_frames = max(1, len(bundle.frames))

        if not bundle.segments:
            # 初始时 start=1, end=总帧数
            bundle.segments = [{"name": "Default", "start": 1, "end": total_frames}]
        
        for seg in bundle.segments:
            self._add_segment_node(root, seg)

        root.setExpanded(True)
        self._update_ui_states()

    def _create_root_widget(self, item, bundle):
        w = QWidget(); w.setObjectName("ParentContainer")
        layout = QHBoxLayout(w); layout.setContentsMargins(10,0,10,0); layout.setSpacing(6)
        
        dot_color = "#89b4fa" if bundle.is_memory or not bundle.path else "#14B977"
        dot = QLabel("●"); dot.setStyleSheet(f"color: {dot_color}; font-size: 14px;")
        
        name_stack = self._create_name_editor(bundle.name, 140, lambda n: setattr(bundle, 'name', n))
        
        btn_add = QPushButton(); btn_add.setObjectName("AssetActionBtn")
        btn_add.setFixedSize(22, 22); btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setIcon(QIcon(os.path.join('assets','icons','btn_add.svg')))
        btn_add.clicked.connect(lambda: self.on_add_segment_clicked(item))

        layout.addWidget(dot); layout.addWidget(name_stack); layout.addStretch(); layout.addWidget(btn_add)
        return w

    def _add_segment_node(self, parent_item, seg_dict):
        child = QTreeWidgetItem(parent_item)
        child.setData(0, Qt.UserRole, seg_dict)

        w = QWidget(); w.setObjectName("ChildContainer")
        layout = QHBoxLayout(w); layout.setContentsMargins(24,0,10,0); layout.setSpacing(6)
        
        name_stack = self._create_name_editor(seg_dict['name'], 90, lambda n: self._update_seg_data(child, 'name', n))
        
        digit_style = "background:#313244; color:#cdd6f4; border-radius:3px; font-size:11px;"
        s_edit = QLineEdit(str(seg_dict['start']))
        s_edit.setObjectName('f_start')
        s_edit.setFixedSize(32, 20); s_edit.setAlignment(Qt.AlignCenter); s_edit.setStyleSheet(digit_style)
        
        e_edit = QLineEdit(str(seg_dict['end']))
        e_edit.setObjectName('f_end')
        e_edit.setFixedSize(32, 20); e_edit.setAlignment(Qt.AlignCenter); e_edit.setStyleSheet(digit_style)

        # 动态校验：直接在信号里读取 bundle.frames 长度，不再传递固定的 max_f
        s_edit.editingFinished.connect(lambda: self._sync_fields(child, s_edit, e_edit))
        e_edit.editingFinished.connect(lambda: self._sync_fields(child, s_edit, e_edit))

        layout.addWidget(QLabel("🎬")); layout.addWidget(name_stack); layout.addStretch()
        layout.addWidget(s_edit); layout.addWidget(QLabel("-")); layout.addWidget(e_edit)
        
        self.setItemWidget(child, 0, w)
        return child

    # --- 内部逻辑 ---
    def _sync_fields(self, item, s_edit, e_edit):
        """动态获取当前 Bundle 的总帧数进行校验"""
        # 1. 获取当前节点所属的 Bundle
        bundle = item.parent().data(0, Qt.UserRole)
        if not bundle: return
        
        seg = item.data(0, Qt.UserRole)
        max_f = len(bundle.frames) # 关键：每次校验都读取最新的帧数

        try:
            s = int(s_edit.text())
            e = int(e_edit.text())
            
            # 2. 严格限制范围
            s = max(1, min(s, max_f))
            e = max(1, min(e, max_f))
            if s > e: s = e # 起始不能大于结束
            
            # 3. 写回数据模型
            seg['start'], seg['end'] = s, e
            
            # 4. 反馈回 UI 界面，确保数字整洁
            s_edit.setText(str(s))
            e_edit.setText(str(e))
            
            # 5. 发射信号通知预览面板刷新
            self.segment_changed.emit(bundle, seg)
        except ValueError:
            # 如果输入了非数字，恢复成模型里的旧值
            s_edit.setText(str(seg['start']))
            e_edit.setText(str(seg['end']))

    def _update_seg_data(self, item, key, val):
        seg = item.data(0, Qt.UserRole)
        seg[key] = val
        self.segment_changed.emit(item.parent().data(0, Qt.UserRole), seg)

    def on_add_segment_clicked(self, parent_item):
        bundle = parent_item.data(0, Qt.UserRole)
        new_seg = {"name": "新动画", "start": 1, "end": len(bundle.frames)}
        bundle.segments.append(new_seg)
        child = self._add_segment_node(parent_item, new_seg)
        parent_item.setExpanded(True)
        self.setCurrentItem(child)

    def _handle_selection_event(self):
        item = self.currentItem()
        if not item: return
        self._update_ui_states()
        bundle = item.data(0, Qt.UserRole) if not item.parent() else item.parent().data(0, Qt.UserRole)
        seg = item.data(0, Qt.UserRole) if item.parent() else item.child(0).data(0, Qt.UserRole)
        if bundle and seg: self.segment_changed.emit(bundle, seg)

    def _update_ui_states(self):
        """递归刷新所有节点的选中样式"""
        def update_node(it):
            widget = self.itemWidget(it, 0)
            if widget:
                widget.setProperty("selected", "true" if it.isSelected() else "false")
                widget.style().unpolish(widget); widget.style().polish(widget)
            for i in range(it.childCount()): update_node(it.child(i))
        for i in range(self.topLevelItemCount()): update_node(self.topLevelItem(i))

    def _create_name_editor(self, text, width, callback):
        stack = QStackedWidget(); stack.setFixedSize(width, 30)
        lbl = QLabel(text); lbl.setObjectName("NameLabel")
        edit = QLineEdit(text)
        stack.addWidget(lbl); stack.addWidget(edit)
        lbl.mouseDoubleClickEvent = lambda e: (edit.setText(lbl.text()), stack.setCurrentIndex(1), edit.setFocus())
        edit.editingFinished.connect(lambda: (lbl.setText(edit.text()), stack.setCurrentIndex(0), callback(edit.text())))
        return stack

    def _find_root_by_bundle(self, bundle):
        for i in range(self.topLevelItemCount()):
            if self.topLevelItem(i).data(0, Qt.UserRole) == bundle: return self.topLevelItem(i)
        return None

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item or not item.parent(): return
        from PySide6.QtWidgets import QMenu
        menu = QMenu()
        if menu.addAction("删除片段") == menu.exec(self.mapToGlobal(pos)):
            bundle = item.parent().data(0, Qt.UserRole)
            bundle.segments.remove(item.data(0, Qt.UserRole))
            item.parent().removeChild(item)