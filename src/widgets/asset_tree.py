import os
from PySide6.QtWidgets import (
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QHBoxLayout,
    QWidget,
    QLineEdit,
    QLabel,
    QStackedWidget,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from ..utils import get_resource_path


class AssetTree(QTreeWidget):
    segment_changed = Signal(object, dict)

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
        root = self._find_root_by_bundle(bundle)
        if not root:
            return
        # 必须清空，否则每次裁切都会重复堆叠旧节点
        root.takeChildren()
        for seg in bundle.segments:
            self._add_segment_node(root, seg)

    # --- 节点创建 ---
    def add_bundle(self, bundle):
        root = QTreeWidgetItem(self)
        root.setData(0, Qt.UserRole, bundle)
        self.setItemWidget(root, 0, self._create_root_widget(root, bundle))

        # 确保初始帧数至少为 1
        total_frames = max(1, len(bundle.frames))

        if not bundle.segments:
            # 初始时 start=1, end=总帧数
            bundle.segments = [{"name": "动画", "start": 1, "end": total_frames}]

        for seg in bundle.segments:
            self._add_segment_node(root, seg)

        root.setExpanded(True)
        self._update_ui_states()

    def _create_root_widget(self, item, bundle):
        w = QWidget()
        w.setObjectName("ParentContainer")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)

        dot_color = "#89b4fa" if bundle.is_memory or not bundle.path else "#14B977"
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {dot_color}; font-size: 14px;")

        # 导入AssetManager
        from ..asset_manager import AssetManager
        
        # 名称修改回调：更新bundle.name并同步到AssetManager
        def update_bundle_name(new_name):
            old_name = bundle.name
            # 更新bundle.name
            bundle.name = new_name
            # 更新AssetManager中的存储键
            manager = AssetManager()
            if old_name in manager._storage:
                # 移除旧键
                del manager._storage[old_name]
                # 使用新键重新注册
                # 先确保bundle.name确实是新名称
                bundle.name = new_name
                # 注册到AssetManager
                manager._storage[new_name] = bundle
            return new_name
        
        name_stack = self._create_name_editor(
            bundle.name, 140, update_bundle_name
        )

        btn_add = QPushButton()
        btn_add.setObjectName("AssetActionBtn")
        btn_add.setFixedSize(22, 22)
        btn_add.setCursor(Qt.PointingHandCursor)
        icon_path = get_resource_path(os.path.join("assets", "icons", "btn_add.svg"))
        btn_add.setIcon(QIcon(icon_path))
        btn_add.clicked.connect(lambda: self.on_add_segment_clicked(item))

        layout.addWidget(dot)
        layout.addWidget(name_stack)
        layout.addStretch()
        layout.addWidget(btn_add)
        return w

    def _add_segment_node(self, parent_item, seg_dict):
        # 获取 bundle 引用
        bundle = parent_item.data(0, Qt.UserRole)
        child = QTreeWidgetItem(parent_item)
        # 核心：将模型字典引用存储在 UserRole 中
        child.setData(0, Qt.UserRole, seg_dict)

        # 名字修改回调：闭包内捕获 bundle 和 seg_dict
        def update_name_callback(requested_name):
            base = requested_name
            final = base
            counter = 1
            # 查重：必须排除掉当前这个内存对象本身，否则改名会由于自己占用了名字而导致自动加后缀
            others = [s["name"] for s in bundle.segments if s is not seg_dict]
            while final in others:
                final = f"{base}_{counter}"
                counter += 1

            # 同步回原始字典
            seg_dict["name"] = final
            return final

        w = QWidget()
        w.setObjectName("ChildContainer")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(24, 0, 10, 0)
        layout.setSpacing(6)

        name_stack = self._create_name_editor(
            seg_dict["name"], 100, update_name_callback
        )

        digit_style = (
            "background:#313244; color:#cdd6f4; border-radius:3px; font-size:11px;"
        )

        # 核心改进：读取时使用 .get() 并设置默认值，增加鲁棒性
        s_edit = QLineEdit(str(seg_dict.get("start", 1)))
        s_edit.setObjectName("f_start")
        s_edit.setFixedSize(32, 20)
        s_edit.setAlignment(Qt.AlignCenter)
        s_edit.setStyleSheet(digit_style)

        e_edit = QLineEdit(str(seg_dict.get("end", 1)))
        e_edit.setObjectName("f_end")
        e_edit.setFixedSize(32, 20)
        e_edit.setAlignment(Qt.AlignCenter)
        e_edit.setStyleSheet(digit_style)

        # 信号绑定：使用默认参数防止 Lambda 延迟绑定 Bug
        s_edit.editingFinished.connect(
            lambda c=child, s=s_edit, e=e_edit: self._sync_fields(c, s, e)
        )
        e_edit.editingFinished.connect(
            lambda c=child, s=s_edit, e=e_edit: self._sync_fields(c, s, e)
        )

        layout.addWidget(QLabel("🎬"))
        layout.addWidget(name_stack)
        layout.addStretch()
        layout.addWidget(s_edit)
        layout.addWidget(QLabel("-"))
        layout.addWidget(e_edit)

        self.setItemWidget(child, 0, w)
        return child

    # --- 内部逻辑 ---
    def _sync_fields(self, item, s_edit, e_edit):
        parent = item.parent()
        if not parent:
            return
        bundle = parent.data(0, Qt.UserRole)
        seg = item.data(0, Qt.UserRole)  # 获取 UI 节点绑定的字典对象
        max_f = len(bundle.frames)

        try:
            # 1. 读取并校验数值
            s = int(s_edit.text() if s_edit.text() else 1)
            e = int(e_edit.text() if e_edit.text() else 1)

            s = max(1, min(s, max_f))
            e = max(1, min(e, max_f))
            if s > e:
                s = e

            # 2. 【核心同步】原地修改字典引用
            # 由于 seg 指向的就是 bundle.segments 里的某个字典，修改 seg 实际上就在改模型
            seg["start"] = s
            seg["end"] = e

            # --- 强制安全检查：确保该对象确实在模型列表中 ---
            # 如果 id 对不上，说明这是一个副本，我们需要把它同步回模型
            if not any(x is seg for x in bundle.segments):

                # 这种情况通常发生在 bundle.segments 被整体替换时
                # 我们可以尝试通过 item 的 index 来寻找在模型中的对应位置
                idx = parent.indexOfChild(item)
                if 0 <= idx < len(bundle.segments):
                    bundle.segments[idx]["start"] = s
                    bundle.segments[idx]["end"] = e

            # 4. 反馈回 UI (阻塞信号防止重复触发)
            s_edit.blockSignals(True)
            e_edit.blockSignals(True)
            s_edit.setText(str(s))
            e_edit.setText(str(e))
            s_edit.blockSignals(False)
            e_edit.blockSignals(False)

            # 5. 通知预览面板
            # 只要数据改了，就发信号，让 PreviewPanel 自己判断是否需要重置播放进度
            self.segment_changed.emit(bundle, seg)

        except ValueError:
            # 输入非法字符时还原
            s_edit.setText(str(seg.get("start", 1)))
            e_edit.setText(str(seg.get("end", 1)))

    def _update_seg_data(self, item, key, val):
        seg = item.data(0, Qt.UserRole)
        seg[key] = val
        self.segment_changed.emit(item.parent().data(0, Qt.UserRole), seg)

    def on_add_segment_clicked(self, parent_item):
        bundle = parent_item.data(0, Qt.UserRole)
        if not bundle:
            return

        # --- 核心修复：自动查重并添加后缀 ---
        base_name = "新动画"
        final_name = base_name
        counter = 1

        # 获取当前 bundle 中所有已存在的片段名称
        existing_names = [s["name"] for s in bundle.segments]

        # 循环检查，如果重名则加后缀 _1, _2...
        while final_name in existing_names:
            final_name = f"{base_name}_{counter}"
            counter += 1

        # 1. 确保每次都是创建一个全新的 dict 对象，且名称唯一
        new_data = {"name": final_name, "start": 1, "end": len(bundle.frames)}

        # 2. 存入模型（这是真值源）
        bundle.segments.append(new_data)

        # 3. 关键：必须传入刚刚 append 进去的那个唯一对象引用
        seg_ref = bundle.segments[-1]
        child = self._add_segment_node(parent_item, seg_ref)

        # 4. UI 自动展开并选中新节点
        parent_item.setExpanded(True)
        self.setCurrentItem(child)

    def _handle_selection_event(self):
        """处理树节点选中事件，实现点击即预览"""
        item = self.currentItem()
        if not item:
            return

        self._update_ui_states()

        bundle = None
        seg = None

        if item.parent() is None:
            bundle = item.data(0, Qt.UserRole)
            if item.childCount() > 0:
                item = item.child(0)  # 自动重定向到第一个子片段
                seg = item.data(0, Qt.UserRole)
        else:
            bundle = item.parent().data(0, Qt.UserRole)
            seg = item.data(0, Qt.UserRole)

        if bundle and seg:
            # --- 核心改进：在发送信号前，强制从 UI 的 LineEdit 同步一次数据到字典 ---
            # 这样即使用户没按回车直接点选了这一行，也能保证发送的是 UI 上的数字
            widget = self.itemWidget(item, 0)
            if widget:
                s_edit = widget.findChild(QLineEdit, "f_start")
                e_edit = widget.findChild(QLineEdit, "f_end")
                if s_edit and e_edit:
                    try:
                        # 强制把 UI 上的值刷进字典
                        seg["start"] = int(s_edit.text())
                        seg["end"] = int(e_edit.text())
                    except:  # noqa: E722
                        pass

            # 发送信号给 PreviewPanel
            self.segment_changed.emit(bundle, seg)

    def _update_ui_states(self):
        """递归刷新所有节点的选中样式"""

        def update_node(it):
            widget = self.itemWidget(it, 0)
            if widget:
                widget.setProperty("selected", "true" if it.isSelected() else "false")
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            for i in range(it.childCount()):
                update_node(it.child(i))

        for i in range(self.topLevelItemCount()):
            update_node(self.topLevelItem(i))

    def _create_name_editor(self, text, width, callback):
        """带查重逻辑和实时模型同步的名称编辑器"""
        stack = QStackedWidget()
        stack.setFixedSize(width, 30)

        lbl = QLabel(text)
        lbl.setObjectName("NameLabel")

        edit = QLineEdit(text)
        stack.addWidget(lbl)
        stack.addWidget(edit)

        # 双击进入编辑模式
        lbl.mouseDoubleClickEvent = lambda e: (
            edit.setText(lbl.text()),
            stack.setCurrentIndex(1),
            edit.setFocus(),
        )

        def on_finished():
            # 1. 获取新名称并清理空格
            new_name = edit.text().strip()
            old_name = lbl.text()

            # 2. 如果名字没变，直接切回
            if not new_name or new_name == old_name:
                stack.setCurrentIndex(0)
                return

            # 3. 切回显示模式
            stack.setCurrentIndex(0)

            # 4. 执行回调（该回调会负责查重并写入模型）
            # callback 内部会修改字典的 'name' 键，并可能返回最终唯一化的名字
            final_name = callback(new_name)
            if final_name is None:
                final_name = new_name

            # 5. 更新 label 显示
            lbl.setText(final_name)

        # 确保按回车也能触发确认（有些平台回车不会触发 editingFinished）
        edit.editingFinished.connect(on_finished)
        edit.returnPressed.connect(on_finished)

        return stack

    def _show_context_menu(self, pos):
        """右键菜单：删除片段"""
        item = self.itemAt(pos)
        if not item or not item.parent():
            return

        from PySide6.QtWidgets import QMenu

        menu = QMenu()
        # 设置one dark风格的QSS
        menu.setStyleSheet("""
            QMenu {
                background-color: #21252b;
                border: 1px solid #181a1f;
                color: #abb2bf;
                padding: 2px;
            }
            QMenu::item {
                padding: 4px 16px;
                margin: 1px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #2c313a;
                color: #abb2bf;
            }
        """)
        
        action = menu.addAction("删除片段")
        # 显示菜单并获取返回值
        selected_action = menu.exec(self.mapToGlobal(pos))
        # 只有左键点击才会返回action，右键点击会返回None
        if selected_action == action:
            bundle = item.parent().data(0, Qt.UserRole)
            bundle.segments.remove(item.data(0, Qt.UserRole))
            item.parent().removeChild(item)

    def reset_with_bundle(self, bundle):
        """先完全清空，再根据 bundle 决定是否重建节点"""
        self.clear()  # QTreeWidget 提供的清空所有项的方法

        # 增加判空保护
        if bundle is not None:
            self.add_bundle(bundle)
        else:
            # bundle is None: nothing to add (cleared state)
            pass
