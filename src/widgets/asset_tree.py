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
        # 如果点击的是子片段
        if target_item.parent():
            path = target_item.parent().data(0, Qt.UserRole)
            data = target_item.data(0, Qt.UserRole + 1)
            if data:
                name, start, end = data
                self.segment_selected.emit(path, name, start, end)



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

        # 按钮构建 (S 和 +)
        btn_s = QPushButton("S"); btn_s.setObjectName("AssetActionBtn")
        btn_s.setFixedSize(22, 22); btn_s.setCursor(Qt.PointingHandCursor)
        btn_s.clicked.connect(lambda: self._sync_asset_to_disk(root, ns_widget))
        
        btn_add = QPushButton("+"); btn_add.setObjectName("AssetActionBtn")
        btn_add.setFixedSize(22, 22); btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(lambda: self.add_segment(root, "新片段", 0, 10))
        
        layout.addWidget(dot); layout.addWidget(ns_widget); layout.addStretch()
        layout.addWidget(btn_s); layout.addWidget(btn_add)
        self.setItemWidget(root, 0, container)

        # 2. 核心逻辑：解析 ZIP 内部的真实数据
        real_segments = []
        try:
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path, 'r') as zipf:
                    # .bgs 读取 config.json，.sprite3 读取 sprite.json
                    internal_json = "config.json" if ext == ".bgs" else "sprite.json"
                    
                    if internal_json in zipf.namelist():
                        with zipf.open(internal_json) as f:
                            data = json.load(f)
                            real_segments = data.get("segments", [])
                            
                            if not real_segments:
                                # 关键：.sprite3 读 costumes 长度，.bgs 读 count 或 frames 长度
                                if ext == ".sprite3":
                                    count = len(data.get("costumes", []))
                                else: # .bgs
                                    count = data.get("count", len(data.get("frames", [])))
                                
                                if count > 0:
                                    real_segments = [{"name": "Default Loop", "start": 1, "end": count}]
        except Exception as e:
            print(f"解析资源包失败: {e}")

        # 3. 动态添加子行
        if real_segments:
            for seg in real_segments:
                self.add_segment(root, seg.get("name"), int(seg.get("start")), int(seg.get("end")))
        else:
            # 彻底读取不到才显示默认
            self.add_segment(root, "Default Loop", 0, 10)
            
        root.setExpanded(True)
        self._update_item_states()

        # 导入完成后，默认选中第一个片段
        if root.childCount() > 0:
            first_segment = root.child(0)
            self.setCurrentItem(first_segment) # 这会触发信号并开始播放

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
        
        # 记录数据到 item，方便获取
        child.setData(0, Qt.UserRole + 1, (name, start, end))

        self.setItemWidget(child, 0, container)
        self._update_item_states()
        return child


    def _sync_asset_to_disk(self, item, ns_widget):
        """点击 S 按钮执行：重命名、修改 JSON、重命名序列帧图片"""
        old_path = item.data(0, Qt.UserRole)
        new_name = ns_widget.widget(0).text() 
        
        dir_name = os.path.dirname(old_path)
        ext = os.path.splitext(old_path)[1]
        new_path = os.path.join(dir_name, f"{new_name}{ext}")
        
        # 提取当前 UI 上所有的片段数据
        segments_data = []
        for i in range(item.childCount()):
            child = item.child(i)
            seg_w = self.itemWidget(child, 0)
            if seg_w:
                # 获取片段名
                s_name = seg_w.findChild(QStackedWidget).widget(0).text()
                # 获取帧范围
                edits = seg_w.findChildren(QLineEdit, "DigitEdit")
                if len(edits) >= 2:
                    segments_data.append({
                        "name": s_name, 
                        "start": int(edits[0].text()), 
                        "end": int(edits[1].text())
                    })

        try:
            # 1. 如果名字变了，先物理重命名主文件/文件夹
            if old_path != new_path and os.path.exists(old_path):
                os.rename(old_path, new_path)
                item.setData(0, Qt.UserRole, new_path)
            
            # 2. 修改内部数据和图片名
            self._process_internal_files(new_path, new_name, segments_data)
        except Exception as e:
            print(f"同步异常: {e}")

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
    

    

    def dragEnterEvent(self, event): event.acceptProposedAction()
    def dragMoveEvent(self, event): event.acceptProposedAction()
    def dropEvent(self, event):
        for url in event.mimeData().urls(): self.add_asset(url.toLocalFile())