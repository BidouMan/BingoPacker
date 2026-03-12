import os
from PySide6.QtWidgets import QWidget, QGraphicsScene, QGraphicsPixmapItem, QListWidgetItem
from PySide6.QtCore import Qt, QRectF, Signal, QSize,QPoint
from PySide6.QtGui import QPixmap, QIcon, QPainter,QPainterPath,QColor,QPen,QRegion,QShortcut, QKeySequence,QCursor

from .editor_ui import EditorUI
from .scalable_view import ScalableView, CheckerboardItem
from .selection_manager import SelectionManager
from ...logic_slice import SliceLogic
from ...asset_manager import AssetManager
from ...asset_model import AssetBundle, FrameData
from .magic_wand import MagicWandTool

class ManualEditor(QWidget, EditorUI):
    slice_completed = Signal(str, list)
    bundle_updated = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.asset_manager = AssetManager()
        self.current_bundle = None
        self.slice_logic = SliceLogic()
        self.current_frames = []
        self.current_source_path = None
        self.preview_item = None
        self.magic_wand = MagicWandTool(tolerance=15)
        self.selection_mask = None # 存储当前的选区
        
        # 初始化 UI
        self.setup_ui(self)
        self.scene = QGraphicsScene()
        self.view = ScalableView(self.scene)
        self.canvas_layout.addWidget(self.view)
        
        self.selection_manager = SelectionManager(self.scene)
        # self.selection_manager = SelectionManager(self.scene)
        # 把 manager 引用塞进 view 里面，否则 view 里的 hasattr(self, 'selection_manager') 永远是 False
        self.view.selection_manager = self.selection_manager
        self.setAcceptDrops(True)

        # 增加快捷键
        self.shortcut_deselect = QShortcut(QKeySequence("Ctrl+D"), self)
        self.shortcut_deselect.activated.connect(self.deselect_all)
        self.shortcut_delete = QShortcut(QKeySequence(Qt.Key_Delete), self)
        self.shortcut_delete.activated.connect(self.delete_selected_pixels)
        
        # 为了兼容 Mac 键盘，建议同时绑定 Backspace
        self.shortcut_backspace = QShortcut(QKeySequence(Qt.Key_Backspace), self)
        self.shortcut_backspace.activated.connect(self.delete_selected_pixels)

        self.connect_signals()

    # --- 核心：数据驱动的属性拦截 ---
    @property
    def current_bundle(self):
        return self._current_bundle

    @current_bundle.setter
    def current_bundle(self, bundle):
        self._current_bundle = bundle
        # 只要 bundle 对象被重新赋值，立刻通知 AssetTree
        if bundle:
            self.bundle_updated.emit(bundle)

    def connect_signals(self):
        # 确保 UI 中的所有按钮都正确绑定
        self.btn_new_file.clicked.connect(self.clear_all)
        self.btn_magic_wand.toggled.connect(self.on_magic_wand_toggled)
        self.btn_pick.toggled.connect(self.selection_manager.set_active)
        self.btn_slice.clicked.connect(self.on_do_slice)
        self.frame_list.currentRowChanged.connect(self.switch_frame_preview)
        self.btn_save.clicked.connect(self.on_save_clicked)
        self.btn_clear.clicked.connect(self.clear_all)

    def display_image(self, file_path):
        if not os.path.exists(file_path): return
        self.update_selection_display(QRegion())

        pixmap = QPixmap(file_path)
        if pixmap.isNull(): return

        # 1. 模型层处理
        asset_name = os.path.splitext(os.path.basename(file_path))[0]
        self.current_bundle = AssetBundle(asset_name) 
        self.current_bundle.path = file_path
        self.current_bundle.original_pixmap = pixmap
        self.asset_manager.register_asset(self.current_bundle)

        # 2. UI 状态重置
        self.current_source_path = file_path
        self.frame_list.blockSignals(True)
        self.scene.clear()

        self.preview_item = None 
        self.pixmap_item = None

        self.frame_list.clear()
        self.current_frames = []

        # 3. 画布渲染
        rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        self.view.checker_item = CheckerboardItem(rect)
        self.scene.addItem(self.view.checker_item)
        
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.pixmap_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        self.scene.addItem(self.pixmap_item)
        
        self.scene.setSceneRect(rect)
        self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

        # 4. 左侧列表：原图卡片 (完全还原原始视觉)
        icon_area = 45 
        canvas = QPixmap(icon_area, icon_area) 
        canvas.fill(Qt.GlobalColor.transparent)
        thumb = pixmap.scaled(icon_area, icon_area, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        painter = QPainter(canvas)
        painter.drawPixmap((icon_area - thumb.width()) // 2, (icon_area - thumb.height()) // 2, thumb)
        painter.end()
        
        item = QListWidgetItem()
        item.setIcon(QIcon(canvas)) 
        item.setText(os.path.basename(file_path))
        # --- 核心修复：强制卡片尺寸，解决不是正方形的问题 ---
        item.setSizeHint(QSize(78, 80)) 
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self.frame_list.addItem(item)
        
        self.frame_list.blockSignals(False)
        self.frame_list.setCurrentRow(0)
        self._sync_to_global_preview(file_path, pixmap)

    def _sync_to_global_preview(self, file_path, pixmap):
        """将当前编辑器加载的单图同步到全局 AssetTree 和 PreviewPanel"""        
        # 1. 构造 FrameData 时传入 rect
        # 对于初次加载的整图，rect 就是 (0, 0, width, height)
        full_rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        
        if not self.current_bundle.frames:
            # 传入 pixmap 和对应的 rect
            self.current_bundle.frames = [FrameData(pixmap=pixmap, rect=full_rect)]
        
        # 2. 确保有默认片段
        if not self.current_bundle.segments:
            self.current_bundle.segments = [{"name": "Default", "start": 1, "end": 1}]

        # 3. 寻找主窗口并同步
        target = self.parent()
        while target and target.__class__.__name__ != "BingoPacker":
            target = target.parent()

        if target:
            target.on_editor_bundle_changed(self.current_bundle)
            print(f"DEBUG [Editor]: 已同步素材 '{self.current_bundle.name}' (1帧, {pixmap.width()}x{pixmap.height()})")

    def on_do_slice(self):
        """
        执行裁切并同步到预览
        核心逻辑：原地更新模型数据，确保 AssetTree 和 PreviewPanel 的引用不丢失
        """
        # 1. 寻找画布上的底图（排除克隆体）
        bg_item = next((i for i in self.scene.items() 
                    if isinstance(i, QGraphicsPixmapItem) and not hasattr(i, 'is_clone')), None)
        if not bg_item: 
            return

        # 2. 执行裁切逻辑（手动或自动）
        rects = self.selection_manager.get_sorted_selections()
        if rects:
            # 手动裁切：根据用户画的框
            self.current_frames = self.slice_logic.run_manual_slice(bg_item, rects)
        else:
            # 自动裁切：识别透明像素
            self.current_frames = self.slice_logic.run_auto_slice_to_preview(bg_item.pixmap())

        # 3. 如果裁切出了结果，开始同步数据模型
        if self.current_frames:
            if self.current_bundle:
                # from ...asset_model import FrameData
                new_max = len(self.current_frames)
                
                # A. 更新帧数据列表
                self.current_bundle.frames = [
                    FrameData(f["pixmap"], f["rect"], f"{self.current_bundle.name}_{i}") 
                    for i, f in enumerate(self.current_frames)
                ]
                
                if not self.current_bundle.segments:
                    self.current_bundle.segments.clear()
                    self.current_bundle.segments.append({"name": "Default", "start": 1, "end": new_max})
                else:
                    # 必须强制更新 Default 片段的值
                    for s in self.current_bundle.segments:
                        if s['name'] == "Default":
                            s['start'] = 1
                            s['end'] = new_max
                            print(f"DEBUG [Editor]: 已强制重置 Default 片段为 1-{new_max}")

                # C. 同步给全局
                self.bundle_updated.emit(self.current_bundle)
                
                # D. 通知全局预览窗口 (MainWindow 会调用 preview_panel.start_segment_preview)
                self._sync_after_slice()

            # --- 4. UI 状态重置与画布渲染 ---
            # 清理旧的预览 Item
            if self.preview_item:        
                try:
                    self.scene.removeItem(self.preview_item)
                except (RuntimeError, Exception):
                    pass
                self.preview_item = None
            
            # 隐藏原始底图，清理选择框
            bg_item.setVisible(False)
            self.selection_manager.clear_selections()
            self.selection_manager.set_active(False)

            # 强制刷新场景尺寸为第一帧的大小
            first_pix = self.current_frames[0]["pixmap"]
            new_rect = QRectF(0, 0, first_pix.width(), first_pix.height())
            self.scene.setSceneRect(new_rect)
            
            if hasattr(self.view, 'checker_item'):
                self.view.checker_item.set_rect(new_rect)

            # 刷新左侧帧列表 UI
            self.update_frame_list_ui()

            # 默认选中第一帧进行单帧预览
            self.frame_list.setCurrentRow(0)
            self.switch_frame_preview(0)
            


    def _sync_after_slice(self):
        """专门用于裁切后的同步"""
        target = self.parent()
        while target and target.__class__.__name__ != "BingoPacker":
            target = target.parent()

        if target and hasattr(target, 'on_editor_bundle_changed'):
            target.on_editor_bundle_changed(self.current_bundle)


    def update_frame_list_ui(self):
        """将裁切后的每一帧存入左侧列表，并强制正方形尺寸"""
        self.frame_list.clear()
        for i, frame in enumerate(self.current_frames):
            pix = frame["pixmap"]
            
            # --- 核心修改：i + 1 让显示从 "帧 01" 开始 ---
            display_index = i + 1
            item = QListWidgetItem(f"帧 {display_index:02d}")
            
            # 强制卡片为正方形尺寸，对应 UI 中的 list 宽度
            item.setSizeHint(QSize(78, 80)) 
            
            # 列表内的缩略图处理
            icon_pix = pix.scaled(45, 45, Qt.AspectRatioMode.KeepAspectRatio, 
                                Qt.TransformationMode.FastTransformation)
            item.setIcon(QIcon(icon_pix))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.frame_list.addItem(item)

    def switch_frame_preview(self, index):
        """点击列表项时，在画布中间显示该帧"""
        if index < 0 or index >= len(self.current_frames): return
        
        pix = self.current_frames[index]["pixmap"]
        new_rect = QRectF(0, 0, pix.width(), pix.height())

        # 调整场景大小以适应当前帧
        self.scene.setSceneRect(new_rect)
        if hasattr(self.view, 'checker_item'):
            self.view.checker_item.set_rect(new_rect)

        # 管理预览 Item
        if self.preview_item is None:
            self.preview_item = QGraphicsPixmapItem()
            self.scene.addItem(self.preview_item)
        
        self.preview_item.setPixmap(pix)
        self.preview_item.setVisible(True)
        # 保持像素清晰
        self.preview_item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        
        # 自动缩放画布查看该帧
        self.view.fitInView(new_rect, Qt.AspectRatioMode.KeepAspectRatio)

    def on_save_clicked(self):
        """保存逻辑：集成 SliceLogic"""
        if not self.current_frames: return
        pixmaps = [f["pixmap"] for f in self.current_frames]
        save_dir = self.slice_logic.save_sliced_sprites(self.current_source_path, pixmaps)
        print(f"已保存至: {save_dir}")

    def clear_all(self):
        """完全清空编辑器状态并重置全局环境"""
        # 1. 清理数据管理层 (核心：防止 AssetTree 残留)
        self.update_selection_display(QRegion())
        self.asset_manager.clear_all()
        
        # 2. 清理编辑器内部变量
        self.current_bundle = None
        self.current_frames = []
        self.current_source_path = None
        
        # 3. 清理 UI 组件
        self.frame_list.blockSignals(True)
        self.frame_list.clear()
        self.frame_list.blockSignals(False)
        
        self.scene.clear()
        self.preview_item = None
        if hasattr(self.view, 'checker_item'):
            self.view.checker_item = None
            
        # 4. --- 关键步骤：通知全局 UI ---
        # 发射 bundle_updated 信号，但传递 None，表示“当前已无活动资源”
        self.bundle_updated.emit(None)
        
        print("DEBUG [Editor]: 场景已完全重置，已发送全局清理信号")
    
    def import_project_file(self, file_path):
        """导入并还原工程文件数据到编辑器 UI"""
        self.update_selection_display(QRegion())
        self.asset_manager.clear_all()

        # 1. 使用 AssetManager 解析模型
        new_bundle = self.asset_manager.load_from_file(file_path)
        if not new_bundle: return

        # 2. 更新当前编辑对象并记录路径
        self.current_bundle = new_bundle
        self.current_source_path = file_path

        # 3. 还原 current_frames 数据供编辑器内部渲染
        self.current_frames = [
            {"pixmap": f.pixmap, "rect": f.rect} 
            for f in new_bundle.frames
        ]

        # 4. UI 深度重置
        self.frame_list.blockSignals(True)
        self.scene.clear()
        self.preview_item = None
        
        # 5. 重建左侧缩略图 UI
        self.update_frame_list_ui()

        # 6. 还原画布状态
        if self.current_frames:
            first_pix = self.current_frames[0]["pixmap"]
            new_rect = QRectF(0, 0, first_pix.width(), first_pix.height())
            self.scene.setSceneRect(new_rect)
            # 这里的 checker_item 处理逻辑参考 scalable_view.py
            self.view.checker_item = CheckerboardItem(new_rect)
            self.scene.addItem(self.view.checker_item)
            
            self.frame_list.blockSignals(False)
            self.frame_list.setCurrentRow(0)
            self.switch_frame_preview(0) 

        # 7. 触发全局同步信号，通知 AssetTree 刷新片段
        self.bundle_updated.emit(self.current_bundle)
    
    def get_canvas_coordinates(self, pos):
        """将视图坐标转换为场景(图片)坐标"""
        # 这里的 self.view 是 ScalableView 实例
        scene_pos = self.view.mapToScene(pos)
        return QPoint(int(scene_pos.x()), int(scene_pos.y()))

    def handle_magic_wand_click(self, scene_pos):
        """
        处理来自 ScalableView 的点击 (传进来的是场景坐标)
        """
        # 1. 确定当前操作的图元 (优先预览图元，其次是原始图元)
        target_item = self.preview_item if (self.preview_item and self.preview_item.isVisible()) else None
        if not target_item and hasattr(self, 'pixmap_item'):
            target_item = self.pixmap_item

        if not target_item or not target_item.pixmap():
            return

        # 2. 【核心修复】将场景坐标转换为图元内部的像素坐标
        # 这是为了解决图片在场景中被移动（Pos不为0）或缩放后的坐标偏移问题
        local_pos_f = target_item.mapFromScene(scene_pos)
        item_pos = local_pos_f.toPoint()

        # 3. 获取 QImage 进行边界检查
        img = target_item.pixmap().toImage()
        if not img.rect().contains(item_pos):
            print(f"DEBUG [Editor]: 点击位置 {item_pos.x()},{item_pos.y()} 越界，不在图片范围内")
            return

        # 打印调试信息，确认点击的颜色是否符合预期
        pixel_color = img.pixelColor(item_pos)
        print(f"DEBUG [Editor]: 点击像素点({item_pos.x()}, {item_pos.y()}) "
              f"颜色为: RGBA({pixel_color.red()}, {pixel_color.green()}, "
              f"{pixel_color.blue()}, {pixel_color.alpha()})")

        # 如果点到了几乎透明的地方，通常泛洪会填满整个背景，这里可以做个预防
        if pixel_color.alpha() < 5:
            print("DEBUG [Editor]: 警告：点击了透明区域，可能会选中整个背景。")

        # 4. 执行魔棒算法
        # 建议：如果之前红橙不分，可以将 tolerance 调低到 10-20
        self.magic_wand.tolerance = 20 
        
        # 传入 img 和精准的 item_pos
        selection_region = self.magic_wand.get_selection_region(img, item_pos)
        
        # 5. 存储并渲染
        # 这里存储的是相对于图片坐标系的 QRegion
        self.selection_mask = selection_region
        self.update_selection_display(selection_region)

    def update_selection_display(self, region):
        """专业版：带安全生命周期管理的动态蚂蚁线"""
        
        # 定义内部清理函数，防止代码重复
        def clear_ants():
            if hasattr(self, 'ants_timer') and self.ants_timer:
                self.ants_timer.stop()
                self.ants_timer.deleteLater()
                self.ants_timer = None
            if hasattr(self, 'temp_mask_item') and self.temp_mask_item:
                try:
                    self.scene.removeItem(self.temp_mask_item)
                except: pass
                self.temp_mask_item = None
                self.ants_layer = None

        if region.isEmpty():
            clear_ants()
            return

        # 1. 路径处理
        path = QPainterPath()
        path.addRegion(region)
        simplified_path = path.simplified()

        # 2. 初始化或重置 Item
        # 注意：如果已经报错了，我们强制重新创建
        is_deleted = False
        if hasattr(self, 'ants_layer') and self.ants_layer:
            try:
                # 测试 C++ 对象是否还活着
                _ = self.ants_layer.scene()
            except RuntimeError:
                is_deleted = True

        if not hasattr(self, 'temp_mask_item') or not self.temp_mask_item or is_deleted:
            clear_ants() # 确保旧的完全清理
            
            from PySide6.QtWidgets import QGraphicsPathItem
            from PySide6.QtCore import QTimer
            
            self.temp_mask_item = QGraphicsPathItem() 
            self.ants_layer = QGraphicsPathItem(self.temp_mask_item) 
            self.scene.addItem(self.temp_mask_item)
            
            self.ants_timer = QTimer(self)
            self.ants_offset = 0
            
            def animate():
                # 安全检查：如果对象被销毁了，立即停止定时器
                try:
                    if self.ants_layer:
                        self.ants_offset = (self.ants_offset + 1) % 20
                        p = self.ants_layer.pen()
                        p.setDashOffset(self.ants_offset)
                        self.ants_layer.setPen(p)
                except (RuntimeError, AttributeError):
                    if hasattr(self, 'ants_timer') and self.ants_timer:
                        self.ants_timer.stop()

            self.ants_timer.timeout.connect(animate)
            self.ants_timer.start(60)

        # 3. 设置样式 (保持之前的 2 像素加粗)
        line_width = 2
        w_pen = QPen(QColor(255, 255, 255), line_width)
        w_pen.setCosmetic(True)
        self.temp_mask_item.setPath(simplified_path)
        self.temp_mask_item.setPen(w_pen)

        b_pen = QPen(QColor(0, 0, 0), line_width)
        b_pen.setDashPattern([6, 6])
        b_pen.setCosmetic(True)
        self.ants_layer.setPath(simplified_path)
        self.ants_layer.setPen(b_pen)

        self.temp_mask_item.setZValue(9999)

        # 4. 坐标同步
        target = self.preview_item if (self.preview_item and self.preview_item.isVisible()) else self.pixmap_item
        if target:
            self.temp_mask_item.setPos(target.pos())
            self.temp_mask_item.setTransform(target.transform())
    
    def on_magic_wand_toggled(self, checked):
        """当魔棒按钮状态切换时触发"""
        # 只需要让视图重绘光标即可，不需要手动 setDragMode 了
        # 因为我们已经在视图内部通过状态机决定了鼠标样式
        if checked:
            # 互斥逻辑：开启魔棒时，关闭矩形选取模式
            self.btn_pick.setChecked(False) 
            self.selection_manager.set_active(False)
        
        # 核心：通知视图根据最新状态更新光标
        self.view.update_cursor_style()
        print(f"DEBUG [Editor]: 魔棒模式切换为: {checked}")
    
    def deselect_all(self):
        """取消选择：同时清理魔棒选区和手动矩形选区"""
        # 1. 清理魔棒选区
        if self.selection_mask:
            from PySide6.QtGui import QRegion
            self.selection_mask = None
            self.update_selection_display(QRegion()) # 传入空选区会触发我们写好的清理逻辑
            print("DEBUG [Editor]: 已通过快捷键清空魔棒选区")

        # 2. 清理手动绘制的矩形选区 (SelectionManager)
        if hasattr(self, 'selection_manager'):
            self.selection_manager.clear_selections()
            print("DEBUG [Editor]: 已通过快捷键清空矩形选区")
    
    def delete_selected_pixels(self):
        """核心功能：将选区内的像素变为透明"""
        # 1. 确定我们要操作的底图图元
        target_item = self.preview_item if (self.preview_item and self.preview_item.isVisible()) else None
        if not target_item and hasattr(self, 'pixmap_item'):
            target_item = self.pixmap_item

        if not target_item or not target_item.pixmap():
            return

        # 2. 构造最终的像素级选区 (QRegion)
        final_region = QRegion()
        
        # 叠加魔棒选区 (魔棒选区已经是基于图片像素坐标的)
        if self.selection_mask and not self.selection_mask.isEmpty():
            final_region += self.selection_mask
            
        # 叠加矩形选区 (需要从场景坐标转为图元本地像素坐标)
        if hasattr(self, 'selection_manager'):
            for item in self.selection_manager.selections:
                # 转换场景矩形到图元本地坐标
                local_rect_f = target_item.mapFromScene(item.rect()).boundingRect()
                final_region += QRegion(local_rect_f.toRect())

        if final_region.isEmpty():
            print("DEBUG [Editor]: 选区为空，跳过删除")
            return

        # 3. 执行像素擦除
        original_pixmap = target_item.pixmap()
        new_pixmap = QPixmap(original_pixmap.size())
        new_pixmap.fill(Qt.GlobalColor.transparent) # 先填透明
        
        painter = QPainter(new_pixmap)
        # 先把原图画上去
        painter.drawPixmap(0, 0, original_pixmap)
        
        # 设置模式为 Clear (擦除模式)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        
        # 【关键修复】使用正确的迭代方式遍历 QRegion
        for rect in final_region:
            painter.fillRect(rect, Qt.GlobalColor.transparent)
        
        painter.end()

        # 4. 更新 UI 显示
        target_item.setPixmap(new_pixmap)
        
        # 5. 如果是初次加载的底图，同步更新到 Bundle 数据模型
        if target_item == getattr(self, 'pixmap_item', None):
            if self.current_bundle:
                self.current_bundle.original_pixmap = new_pixmap
                if self.current_bundle.frames:
                    self.current_bundle.frames[0].pixmap = new_pixmap

        # 6. 清理选区和蚂蚁线
        self.deselect_all()
        print("DEBUG [Editor]: 像素删除成功，已刷新显示")
    
