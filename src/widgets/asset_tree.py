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
        
        # 开启自定义右键菜单策略
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

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
                           QPushButton#AssetActionBtn {
                background: #313244;
                color: #a6adc8;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 10px;
            }
            QPushButton#AssetActionBtn:hover { 
                background: #45475a; 
                color: #f5e0dc; /* 悬停时文字稍微亮一点 */
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
        # 如果点击的是子片段 """统一的信号发射逻辑"""
        self.emit_segment_signal(target_item)      

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
        import json
        import zipfile
        name = os.path.splitext(os.path.basename(path))[0]
        ext = os.path.splitext(path)[1].lower()
        
        # 1. 创建根节点并存储路径
        root = QTreeWidgetItem(self)
        root.setData(0, Qt.UserRole, path) 
        
        # UI 样式处理
        dot_color = "#a6e3a1" if ext == ".sprite3" else "#cba6f7"
        if os.path.isdir(path): dot_color = "#89b4fa"
        
        container = QWidget()
        container.setObjectName("ParentContainer")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 0, 10, 0); layout.setSpacing(4)
        
        dot = QLabel("●"); dot.setStyleSheet(f"color: {dot_color}; font-size: 14px;")
        ns_widget = self._create_name_widget(name, 140)

        # 按钮构建
        btn_s = QPushButton("S"); btn_s.setObjectName("AssetActionBtn")
        btn_s.setFixedSize(22, 22); btn_s.setCursor(Qt.PointingHandCursor)
        btn_s.clicked.connect(lambda: self._sync_asset_to_disk(root, ns_widget))
        
        btn_add = QPushButton("+"); btn_add.setObjectName("AssetActionBtn")
        btn_add.setFixedSize(22, 22); btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self.on_add_new_clicked)
        
        layout.addWidget(dot); layout.addWidget(ns_widget); layout.addStretch()
        layout.addWidget(btn_s); layout.addWidget(btn_add)
        self.setItemWidget(root, 0, container)

        # 2. 核心逻辑：解析 ZIP 内部数据并【持久化到 root】
        real_segments = []
        # 初始化一个默认 data 字典，防止后续 data 变量未定义的错误
        asset_data = {"count": 0} 

        try:
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path, 'r') as zipf:
                    internal_json = "config.json" if ext == ".bgs" else "sprite.json"
                    
                    if internal_json in zipf.namelist():
                        with zipf.open(internal_json) as f:
                            asset_data = json.load(f)
                            
                            # 计算当前资源的总帧数
                            if ext == ".sprite3":
                                count = len(asset_data.get("costumes", []))
                            else: # .bgs
                                count = asset_data.get("count", len(asset_data.get("frames", [])))
                            
                            # 重要：确保字典里一定有 count 字段供校验使用
                            asset_data["count"] = count
                            
                            real_segments = asset_data.get("segments", [])
                            if not real_segments and count > 0:
                                real_segments = [{"name": "Default Loop", "start": 1, "end": count}]
        except Exception as e:
            print(f"解析资源包失败: {e}")

        # 【关键修复点】：将解析出的 data 字典存入 root 节点的 UserRole + 1
        # 只有存了这一步，_sync_and_validate_row 里的 asset_info.get("count") 才能拿到真实数字
        root.setData(0, Qt.UserRole + 1, asset_data)

        # 3. 动态添加子行
        if real_segments:
            for seg in real_segments:
                # 转换数据为 int 确保安全
                s = int(seg.get("start", 1))
                e = int(seg.get("end", 1))
                self.add_segment(root, seg.get("name"), s, e)
        else:
            # 彻底读取不到时：
            # 也要给 root 存一个默认 count，否则以后新建片段校验时会按 1 算
            root.setData(0, Qt.UserRole + 1, {"count": 10})
            self.add_segment(root, "Default Loop", 1, 10)
            
        root.setExpanded(True)
        self._update_item_states()

        if root.childCount() > 0:
            first_segment = root.child(0)
            self.setCurrentItem(first_segment) # 这会触发信号并开始播放

    def add_segment(self, parent, name, start, end):
        child = QTreeWidgetItem(parent)
        container = QWidget()
        container.setObjectName("ChildContainer")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(12, 0, 10, 0)
        
        unique_name = self.get_unique_name(parent, name)
        ns = self._create_name_widget(unique_name, 100)
        name_edit = ns.widget(1)
        
        # 优化 QSS：解决残留线条，增加焦点颜色
        digit_qss = """
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                padding: 0px;
                font-size: 11px;
            }
            QLineEdit:focus {
                background-color: #45475a;
            }
        """

        s_edit = QLineEdit(str(start))
        s_edit.setObjectName("s_edit") # 精准命名
        s_edit.setFixedSize(35, 22)    # 稍微加宽一点点，避免数字挤压
        s_edit.setAlignment(Qt.AlignCenter)
        s_edit.setStyleSheet(digit_qss)
        
        e_edit = QLineEdit(str(end))
        e_edit.setObjectName("e_edit") # 精准命名
        e_edit.setFixedSize(35, 22)
        e_edit.setAlignment(Qt.AlignCenter)
        e_edit.setStyleSheet(digit_qss)
        
        layout.addWidget(QLabel("🎬"))
        layout.addWidget(ns)
        layout.addStretch()
        layout.addWidget(s_edit)
        layout.addWidget(QLabel("-"))
        layout.addWidget(e_edit)
        
        child.setData(0, Qt.UserRole + 1, (unique_name, start, end))
        self.setItemWidget(child, 0, container)
        self._update_item_states()

        # 信号绑定
        name_edit.editingFinished.connect(self.handle_segment_editing_finished)
        s_edit.editingFinished.connect(self.handle_segment_editing_finished)
        e_edit.editingFinished.connect(self.handle_segment_editing_finished)

        return child

    def _on_digit_edited(self, line_edit, child, root):
        """当帧数输入框编辑完成时触发"""
        try:
            # 1. 获取用户输入
            val = int(line_edit.text())
            
            # 2. 获取当前资源的总帧数
            # 假设你在 add_asset 时把 data 存到了 root 的 UserRole + 1
            asset_data = root.data(0, Qt.UserRole + 1)
            max_frames = asset_data.get("count", val) if isinstance(asset_data, dict) else val

            # 3. 核心需求：自动修正
            if val > max_frames:
                val = max_frames
            elif val < 1:
                val = 1
            
            # 4. 回写到 UI
            line_edit.setText(str(val))
            
            # 5. 同步数据到 item 并触发预览刷新
            self._sync_and_validate_row(child, root, self.itemWidget(child, 0))

        except ValueError:
            # 如果用户输入了文字，int() 会报错，这里我们直接回滚到之前的合法值即可
            old_data = child.data(0, Qt.UserRole + 1)
            if old_data:
                # 恢复为旧数据，不让程序崩溃
                line_edit.setText(str(old_data[1] if "start" in line_edit.objectName() else old_data[2]))

    def get_unique_name(self, root, target_name, exclude_item=None):
        """根据当前已有的片段名，生成一个唯一的名称"""
        existing_names = []
        for i in range(root.childCount()):
            child = root.child(i)
            if child == exclude_item:
                continue
            seg_w = self.itemWidget(child, 0)
            if seg_w:
                # 假设你的 _create_name_widget 返回的是 QStackedWidget，第0页是 QLineEdit
                name_edit = seg_w.findChild(QStackedWidget).widget(0)
                existing_names.append(name_edit.text().strip())
        
        if target_name not in existing_names:
            return target_name
        
        counter = 1
        new_name = f"{target_name}_{counter}"
        while new_name in existing_names:
            counter += 1
            new_name = f"{target_name}_{counter}"
        return new_name

    def handle_segment_editing_finished(self):
        """当名字或数字编辑完成后触发"""
        sender = self.sender()
        # 找到当前操作的 child item
        for i in range(self.topLevelItemCount()):
            root = self.topLevelItem(i)
            for j in range(root.childCount()):
                child = root.child(j)
                container = self.itemWidget(child, 0)
                if container and sender in container.findChildren(QLineEdit):
                    # 关键：调用带 root 参数的校验函数
                    self._sync_and_validate_row(child, root, container)
                    return

    

    def _sync_and_validate_row(self, child, root, container):
        # 1. 获取 UI 组件
        stack = container.findChild(QStackedWidget)
        s_edit = container.findChild(QLineEdit, "s_edit")
        e_edit = container.findChild(QLineEdit, "e_edit")
        if not stack or not s_edit or not e_edit: return

        # 2. 获取真实最大索引 (关键：确保 add_asset 时存了 data)
        asset_info = root.data(0, Qt.UserRole + 1)
        # 防御性编程：如果真的拿不到数据，暂时设一个极大值，而不是设为 1 导致所有输入被卡死
        max_limit = 999 
        if isinstance(asset_info, dict) and "count" in asset_info:
            max_limit = int(asset_info["count"])

        # 3. 处理名字 (逻辑不变)
        name_edit = stack.widget(1)
        unique_name = self.get_unique_name(root, name_edit.text().strip(), exclude_item=child)
        name_edit.setText(unique_name)
        stack.widget(0).setText(unique_name)

        # 4. 帧数逻辑：严格区分 Start 和 End
        try:
            s_val = int(s_edit.text()) if s_edit.text() else 1
            e_val = int(e_edit.text()) if e_edit.text() else max_limit

            # --- A. 起始帧 (Start) 处理 ---
            # 如果起始帧小于 1，修正为 1
            if s_val < 1: 
                s_val = 1
            # 如果起始帧大于资源总数，修正为 1 (乱输归位)
            if s_val > max_limit:
                s_val = 1
            
            # --- B. 结束帧 (End) 处理 ---
            # 核心需求：如果结束帧大于最大索引，修正为最大索引
            if e_val > max_limit:
                e_val = max_limit
            # 如果结束帧小于 1，修正为最大索引 (或者 1，根据你喜好)
            if e_val < 1:
                e_val = max_limit

            # --- C. 逻辑保护：Start 不能超过当前的 End ---
            if s_val > e_val:
                s_val = e_val

            # 5. 【重要】将修正后的值强制回写到 UI
            s_edit.setText(str(s_val))
            e_edit.setText(str(e_val))

            # 6. 更新内存并同步预览
            child.setData(0, Qt.UserRole + 1, (unique_name, s_val, e_val))
            self.segment_selected.emit(root.data(0, Qt.UserRole), unique_name, s_val, e_val)

        except ValueError:
            # 输入非数字时的兜底
            s_edit.setText("1")
            e_edit.setText(str(max_limit))
            child.setData(0, Qt.UserRole + 1, (unique_name, 1, max_limit))
            self.segment_selected.emit(root.data(0, Qt.UserRole), unique_name, 1, max_limit)

    def _process_internal_files(self, asset_path, asset_name, segments):
        """深度同步：支持SVG、帧数保护，且片段内序号强制从01开始"""
        import json, zipfile, os, shutil, tempfile

        ext = os.path.splitext(asset_path)[1].lower()
        internal_json_name = "config.json" if ext == ".bgs" else "sprite.json"
        
        temp_fd, temp_path = tempfile.mkstemp()
        os.close(temp_fd)

        try:
            with zipfile.ZipFile(asset_path, 'r') as zin:
                all_files = zin.namelist()
                img_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.svg')
                original_imgs = sorted([f for f in all_files if f.lower().endswith(img_extensions)])
                
                max_frames = len(original_imgs)
                # 预处理：静默修正用户输入的非法帧数
                for seg in segments:
                    if seg["start"] > max_frames: seg["start"] = max_frames
                    if seg["end"] > max_frames: seg["end"] = max_frames
                    if seg["start"] > seg["end"]: seg["start"] = seg["end"]

                with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                    new_frames_list = [] 
                    copied_as_image = set()

                    for seg in segments:
                        seg_name = seg["name"]
                        # --- 核心逻辑优化：引入片段内部计数器 ---
                        local_idx = 1 
                        
                        for i in range(seg["start"], seg["end"] + 1):
                            idx_in_list = i - 1 
                            if 0 <= idx_in_list < max_frames:
                                old_img_name = original_imgs[idx_in_list]
                                img_ext = os.path.splitext(old_img_name)[1]
                                
                                # 使用 local_idx 而不是原始循环变量 i
                                # 这样即使是 6-10 帧，导出的名字也是 走路_01, 走路_02...
                                new_img_name = f"{seg_name}_{local_idx:02d}{img_ext}"
                                
                                zout.writestr(new_img_name, zin.read(old_img_name))
                                copied_as_image.add(old_img_name)
                                new_frames_list.append(new_img_name)
                                
                                local_idx += 1 # 片段内序号递增

                    # 更新 JSON 数据
                    raw_json = zin.read(internal_json_name).decode('utf-8')
                    data = json.loads(raw_json)
                    data["segments"] = segments
                    
                    if ext == ".bgs":
                        data["frames"] = new_frames_list
                        data["count"] = len(new_frames_list)
                    elif ext == ".sprite3":
                        # 同步修改 Scratch 造型列表名称
                        for idx, costume in enumerate(data.get("costumes", [])):
                            if idx < len(new_frames_list):
                                costume["name"] = os.path.splitext(new_frames_list[idx])[0]
                    
                    zout.writestr(internal_json_name, json.dumps(data, indent=4, ensure_ascii=False))

                    # 拷贝非动画资源（如声音）
                    for item in zin.infolist():
                        if item.filename != internal_json_name and item.filename not in copied_as_image:
                            zout.writestr(item, zin.read(item.filename))

            shutil.move(temp_path, asset_path)
            
        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            raise e

    def clear_all(self):
        """彻底清空树节点和逻辑数据"""
        self.clear()
        
        # 如果路径数据存在于 AssetTree 实例中：
        if hasattr(self, 'asset_files'):
            self.asset_files = []
        if hasattr(self, 'selected_folders'):
            self.selected_folders = []
            
        # 如果你是通过主窗口管理数据的，建议在此处也置空（如果逻辑允许）
        self.verticalScrollBar().setValue(0)
    
    def on_add_new_clicked(self,root):
        root = self.topLevelItem(0) # 简单处理：获取第一个资源根节点
    
        new_item = self.add_segment(root, "动画", 1, 10)
        self.setCurrentItem(new_item) 
        
        # 修复：将 self.on_item_clicked 替换为 emit_segment_signal
        self.emit_segment_signal(new_item)
    
    def update_data_and_preview(self):
        # 获取当前选中的 Item
        current_item = self.currentItem()
        if not current_item or not current_item.parent():
            return

        # 从 UI 部件中获取最新的值
        widget = self.itemWidget(current_item, 0)
        edits = widget.findChildren(QLineEdit, "DigitEdit")
        name_label = widget.findChild(QLabel, "NameLabel") # 假设你也要实时更新名字
        
        if len(edits) >= 2:
            new_data = (
                name_label.text(),
                int(edits[0].text() or 0),
                int(edits[1].text() or 0)
            )
            # 更新 Item 存储的数据
            current_item.setData(0, Qt.UserRole + 1, new_data)
            
            # 实时发射信号刷新预览
            self.emit_segment_signal(current_item)

    def emit_segment_signal(self, item):
        """统一的信号发射逻辑，解决报错的核心"""
        if item is None or item.parent() is None: 
            return # 如果 item 为空，直接拦截，不发信号
        
        if item and item.parent():
            # 获取父节点存储的 ZIP 路径
            path = item.parent().data(0, Qt.UserRole)
            # 获取当前行存储的 (name, start, end) 元组
            data = item.data(0, Qt.UserRole + 1)
            
            if path and data:
                name, start, end = data
                # 发射信号给预览面板
                self.segment_selected.emit(path, name, int(start), int(end))
    def show_context_menu(self, pos):
        """显示右键菜单"""
        item = self.itemAt(pos)
        if not item or not item.parent():
            return  # 如果没选中 item 或者选中过的是根节点(资源包)，则不弹出

        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #45475a; }
            QMenu::item:selected { background-color: #45475a; }
        """)
        
        delete_action = menu.addAction("🗑️ 删除当前片段")
        # 执行菜单并获取选中的动作
        action = menu.exec(self.mapToGlobal(pos))
        
        if action == delete_action:
            self.delete_current_segment(item)

    def delete_current_segment(self, item):
        """执行删除逻辑"""
        parent = item.parent()
        if parent:
            # 1. 从树中移除
            parent.removeChild(item)
            
            # 2. 如果删除后该资源没有片段了，自动补一个默认的(可选)
            if parent.childCount() == 0:
                self.add_segment(parent, "Default Loop", 1, 10)
            
            # 3. 更新 UI 状态并停止预览面板（因为当前片段没了）
            self._update_item_states()
            
            # 如果你有全局的预览清空信号，可以在这里发射
            # 或者简单地让预览面板刷新到父节点的第一个孩子
            if parent.childCount() > 0:
                self.setCurrentItem(parent.child(0))
                self.emit_segment_signal(parent.child(0))
    
    

    def dragEnterEvent(self, event): event.acceptProposedAction()
    def dragMoveEvent(self, event): event.acceptProposedAction()
    def dropEvent(self, event):
        for url in event.mimeData().urls(): self.add_asset(url.toLocalFile())