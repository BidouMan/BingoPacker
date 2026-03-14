import os
from PySide6.QtWidgets import (
    QWidget,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QListWidgetItem,
    QGraphicsView,
)
from PySide6.QtCore import Qt, QRectF, Signal, QSize, QPoint, QEvent
from PySide6.QtGui import (
    QPixmap,
    QIcon,
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QRegion,
    QShortcut,
    QKeySequence,
)

from .editor_ui import EditorUI
from .scalable_view import ScalableView, CheckerboardItem
from .selection_manager import SelectionManager
from ...logic_slice import SliceLogic
from ...asset_manager import AssetManager
from ...asset_model import AssetBundle, FrameData
from .magic_wand import MagicWandTool
from .crop_tool import CropBoxItem
from .constants import ToolMode


class ManualEditor(QWidget, EditorUI):
    slice_completed = Signal(str, list)
    bundle_updated = Signal(object, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui(self)
        # 初始化 UI

        self.scene = QGraphicsScene()
        self.view = ScalableView(self.scene)
        self.canvas_layout.addWidget(self.view)
        self.current_tool_mode = ToolMode.IDLE  # 鼠标状态
        self.view.viewport().installEventFilter(self)
        self.asset_manager = AssetManager()
        self.current_bundle = None
        self.slice_logic = SliceLogic()
        self.current_frames = []
        self.current_source_path = None
        self.preview_item = None
        self.magic_wand = MagicWandTool(tolerance=15)
        self.selection_mask = None  # 存储当前的选区
        # 撤销栈，存储 QPixmap 对象
        self.undo_stack = []
        self.max_undo_steps = 20
        self.last_index = -1

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

        self.frame_list.installEventFilter(self)
        # 同时也给视图加上，确保点击画布后也能响应
        self.view.installEventFilter(self)

    # --- 核心：数据驱动的属性拦截 ---
    @property
    def current_bundle(self):
        return self._current_bundle

    @current_bundle.setter
    def current_bundle(self, bundle):
        self._current_bundle = bundle
        if hasattr(self, "bundle_updated"):
            # 修复点：发射两个参数。
            # 如果没有 segment，传一个空字典 {}，防止报错
            curr_seg = getattr(self, "current_segment", {})
            self.bundle_updated.emit(bundle, curr_seg)

    def connect_signals(self):
        self.frame_list.currentRowChanged.connect(self.switch_frame_preview)

        # 确保 UI 中的所有按钮都正确绑定
        self.btn_new_file.clicked.connect(self.clear_all)
        self.btn_save.clicked.connect(self.on_save_clicked)

        # self.btn_magic_wand.toggled.connect(self.on_magic_wand_toggled) # 切换魔棒工具
        # self.btn_pick.toggled.connect(self.selection_manager.set_active)#切换选区工具(框选图像)
        # self.btn_slice.clicked.connect(self.on_do_slice)                # 切换只能裁切工具(自动将当前精灵表裁切成序列帧)
        # self.btn_cut.clicked.connect(self.on_cut_mode_toggled)          # 切换调整画布尺寸(类似PS中的裁切工具)

        self.btn_magic_wand.clicked.connect(
            lambda: self.set_tool_mode(ToolMode.MAGIC_WAND)
        )
        self.btn_pick.clicked.connect(lambda: self.set_tool_mode(ToolMode.RECT_SELECT))
        self.btn_cut.clicked.connect(lambda: self.set_tool_mode(ToolMode.CROP))
        self.btn_slice.clicked.connect(self.on_do_slice)

        # 魔棒工具按钮功能
        self.slider_tolerance.valueChanged.connect(self._on_tolerance_changed)
        self.btn_expand.clicked.connect(self.on_expand_selection)
        self.btn_shrink.clicked.connect(self.on_shrink_selection)
        self.btn_invert.clicked.connect(self.on_invert_selection)

        # 其他工具
        self.frame_list.currentRowChanged.connect(self.before_frame_changed)

    def before_frame_changed(self, new_row):
        """
        在真正切换显示之前，强制把旧帧的选区合并掉。
        """
        if hasattr(self, "selection_manager") and self.selection_manager.selections:
            # 此时 self.frame_list.currentRow() 还是旧的索引
            self.selection_manager.clear_selections()

    def _on_tolerance_changed(self, value):
        """同步显示百分比并更新魔棒工具的内部容差值"""
        percent = int((value / 255) * 100)
        self.lbl_tolerance_val.setText(f"{percent}%")
        # 同步更新魔棒工具类里的 tolerance
        self.magic_wand.tolerance = value

    def display_image(self, file_path):
        self.undo_stack.clear()
        if hasattr(self, "crop_box") and self.crop_box:
            try:
                if self.crop_box.scene():
                    self.scene.removeItem(self.crop_box)
            except RuntimeError:
                pass
            self.crop_box = None

            # 同步更新按钮状态
            self.btn_cut.blockSignals(True)
            self.btn_cut.setChecked(False)
            self.btn_cut.blockSignals(False)

        if not os.path.exists(file_path):
            return
        self.update_selection_display(QRegion())

        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            return

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
        thumb = pixmap.scaled(
            icon_area,
            icon_area,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        painter = QPainter(canvas)
        painter.drawPixmap(
            (icon_area - thumb.width()) // 2, (icon_area - thumb.height()) // 2, thumb
        )
        painter.end()

        item = QListWidgetItem()
        item.setIcon(QIcon(canvas))
        item.setText(os.path.basename(file_path))
        # --- 核心修复：强制卡片尺寸，解决不是正方形的问题 ---
        item.setSizeHint(QSize(78, 80))
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
        )
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
            print(
                f"DEBUG [Editor]: 已同步素材 '{self.current_bundle.name}' (1帧, {pixmap.width()}x{pixmap.height()})"
            )

    def on_do_slice(self):
        """
        最终版：执行裁切并同步到预览
        解决：物理删除底图、重置按钮状态、重置选区状态
        """
        # 1. 寻找画布上的底图（排除选区克隆体）
        bg_item = next(
            (
                i
                for i in self.scene.items()
                if isinstance(i, QGraphicsPixmapItem) and not hasattr(i, "is_clone")
            ),
            None,
        )
        if not bg_item:
            return

        # 2. 执行裁切逻辑（获取矩形并生成新帧）
        rects = self.selection_manager.get_sorted_selections()
        source_pixmap = bg_item.pixmap()

        if rects:
            self.current_frames = self.slice_logic.run_manual_slice(bg_item, rects)
        else:
            self.current_frames = self.slice_logic.run_auto_slice_to_preview(
                source_pixmap
            )

        if self.current_frames:
            # --- 核心清理 A：彻底物理移除原始底图和选区管理器残留 ---
            if bg_item.scene():
                self.scene.removeItem(bg_item)

            # 这里调用的是强制重置，不涉及合并逻辑，因为底图都换了
            self.selection_manager.selections.clear()
            self.selection_manager.active = False
            self.selection_manager.moving_item = None

            # 3. 更新数据模型 (AssetBundle)
            if self.current_bundle:
                new_max = len(self.current_frames)
                self.current_bundle.frames = [
                    FrameData(f["pixmap"], f["rect"], f"{self.current_bundle.name}_{i}")
                    for i, f in enumerate(self.current_frames)
                ]
                # 更新片段范围
                for s in self.current_bundle.segments:
                    if s.get("name") == "Default":
                        s["start"] = 1
                        s["end"] = new_max

            # 4. 重置 UI 状态
            self.update_frame_list_ui()

            # 彻底销毁预览 Item 缓存
            if self.preview_item and self.preview_item.scene():
                self.scene.removeItem(self.preview_item)
            self.preview_item = None

            # 5. --- 核心修复：重置裁切按钮状态，使其可以再次点击 ---
            self.btn_slice.setChecked(False)
            # 如果有状态栏更新，在这里调用一次
            if hasattr(self, "update_tool_status"):
                self.update_tool_status()

            # 6. 激活第一帧显示
            self.last_index = -1  # 强制重置索引记录
            self.frame_list.setCurrentRow(0)
            self.switch_frame_preview(0)

            # 全局同步一次数据
            self.sync_and_notify()

    def _sync_after_slice(self):
        """专门用于裁切后的同步"""
        target = self.parent()
        while target and target.__class__.__name__ != "BingoPacker":
            target = target.parent()

        if target and hasattr(target, "on_editor_bundle_changed"):
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
            icon_pix = pix.scaled(
                45,
                45,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            item.setIcon(QIcon(icon_pix))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.frame_list.addItem(item)

    # editor_main.py

    def switch_frame_preview(self, index):
        """点击列表项时，在画布中间显示该帧"""
        if index < 0 or index >= len(self.current_frames):
            return
        # 如果点击的是当前正在显示的帧，不做任何操作
        if index == self.last_index and self.last_index != -1:
            return

        # --- 核心修复 A：在切换 index 之前，强制把旧帧的选区“焊死”在旧帧数据里 ---
        if hasattr(self, "selection_manager") and self.last_index != -1:
            # 【关键点】我们显式告诉管理器：请把当前的选区合并到 last_index 对应的那个数据块里
            # 而不是让它自己去猜当前是哪一帧
            old_frame_data = self.current_frames[self.last_index]
            self.selection_manager.clear_selections(target_frame_data=old_frame_data)
            print(f"DEBUG: 切换前已将选区强制合并至旧帧索引: {self.last_index}")

        # 更新当前索引记录
        self.last_index = index

        # --- 核心修复 B：物理清理场景，确保没有任何“脏 Item”残留到新场景 ---
        for item in self.scene.items():
            if item != self.view.checker_item:
                self.scene.removeItem(item)
        self.preview_item = None  # 强制重建底图对象

        # --- 正常的显示逻辑 ---
        pix = self.current_frames[index]["pixmap"]
        new_rect = QRectF(0, 0, pix.width(), pix.height())
        self.scene.setSceneRect(new_rect)
        if hasattr(self.view, "checker_item"):
            self.view.checker_item.set_rect(new_rect)

        if self.preview_item is None:
            self.preview_item = QGraphicsPixmapItem()
            self.scene.addItem(self.preview_item)

        self.preview_item.setPixmap(pix)
        self.preview_item.setVisible(True)
        self.preview_item.setPos(0, 0)

        self.view.fitInView(new_rect, Qt.AspectRatioMode.KeepAspectRatio)

        if self.btn_pick.isChecked():
            self.selection_manager.set_active(True)
            # 确保光标也对齐
            self.view.setCursor(Qt.CrossCursor)

        self.view.fitInView(new_rect, Qt.AspectRatioMode.KeepAspectRatio)
        self.sync_and_notify()

    def on_save_clicked(self):
        """保存逻辑：集成 SliceLogic"""
        if not self.current_frames:
            return
        pixmaps = [f["pixmap"] for f in self.current_frames]
        save_dir = self.slice_logic.save_sliced_sprites(
            self.current_source_path, pixmaps
        )
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
        if hasattr(self.view, "checker_item"):
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
        if not new_bundle:
            return

        # 2. 更新当前编辑对象并记录路径
        self.current_bundle = new_bundle
        self.current_source_path = file_path

        # 3. 还原 current_frames 数据供编辑器内部渲染
        self.current_frames = [
            {"pixmap": f.pixmap, "rect": f.rect} for f in new_bundle.frames
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
        处理魔棒点击：
        勾选连续 (isChecked) -> 只选相连的一坨
        不勾选连续 -> 全图选所有颜色相近的点
        """
        # 1. 确定当前操作的图元
        target_item = (
            self.preview_item
            if (self.preview_item and self.preview_item.isVisible())
            else None
        )
        if not target_item and hasattr(self, "pixmap_item"):
            target_item = self.pixmap_item

        if not target_item or not target_item.pixmap():
            return

        # 2. 坐标转换：将场景坐标映射到图元内部像素坐标
        local_pos_f = target_item.mapFromScene(scene_pos)
        item_pos = local_pos_f.toPoint()

        # 3. 边界检查与图像准备
        img = target_item.pixmap().toImage()
        if not img.rect().contains(item_pos):
            return

        # 4. 【关键步骤】读取 UI 状态
        # 你的需求：勾选了“连续” -> 选一坨 (contiguous=True)
        #           没勾选“连续” -> 选全图 (contiguous=False)
        is_contiguous_mode = self.check_contiguous.isChecked()

        # 读取滑动条的实时容差值
        current_tolerance = self.slider_tolerance.value()

        # 5. 配置并执行魔棒算法
        self.magic_wand.tolerance = current_tolerance

        # 显式传入 is_contiguous_mode
        # 注意：请确保 magic_wand.py 中的 get_selection_region 函数签名已更新为接收这个参数
        selection_region = self.magic_wand.get_selection_region(
            img, item_pos, contiguous=is_contiguous_mode
        )

        # 6. 存储选区并触发蚂蚁线渲染
        self.selection_mask = selection_region
        self.update_selection_display(selection_region)

    def update_selection_display(self, region):
        """专业版：带安全生命周期管理的动态蚂蚁线"""

        # 定义内部清理函数，防止代码重复
        def clear_ants():
            if hasattr(self, "ants_timer") and self.ants_timer:
                self.ants_timer.stop()
                self.ants_timer.deleteLater()
                self.ants_timer = None
            if hasattr(self, "temp_mask_item") and self.temp_mask_item:
                try:
                    self.scene.removeItem(self.temp_mask_item)
                except:  # noqa: E722
                    pass
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
        if hasattr(self, "ants_layer") and self.ants_layer:
            try:
                # 测试 C++ 对象是否还活着
                _ = self.ants_layer.scene()
            except RuntimeError:
                is_deleted = True

        if not hasattr(self, "temp_mask_item") or not self.temp_mask_item or is_deleted:
            clear_ants()  # 确保旧的完全清理

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
                    if hasattr(self, "ants_timer") and self.ants_timer:
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
        target = (
            self.preview_item
            if (self.preview_item and self.preview_item.isVisible())
            else self.pixmap_item
        )
        if target:
            self.temp_mask_item.setPos(target.pos())
            self.temp_mask_item.setTransform(target.transform())

    def on_magic_wand_toggled(self, checked):
        """当魔棒按钮状态切换时触发"""
        if hasattr(self, "magic_wand_panel"):
            self.magic_wand_panel.setVisible(checked)

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
            self.update_selection_display(
                QRegion()
            )  # 传入空选区会触发我们写好的清理逻辑
            print("DEBUG [Editor]: 已通过快捷键清空魔棒选区")

        # 2. 清理手动绘制的矩形选区 (SelectionManager)
        if hasattr(self, "selection_manager"):
            self.selection_manager.clear_selections()
            print("DEBUG [Editor]: 已通过快捷键清空矩形选区")

    def delete_selected_pixels(self):
        """核心功能：将选区内的像素变为透明"""
        # 1. 确定我们要操作的底图图元
        target_item = (
            self.preview_item
            if (self.preview_item and self.preview_item.isVisible())
            else None
        )
        if not target_item and hasattr(self, "pixmap_item"):
            target_item = self.pixmap_item

        if not target_item or not target_item.pixmap():
            return

        self.save_undo_state()  # 存档

        # 2. 构造最终的像素级选区 (QRegion)
        final_region = QRegion()

        # 叠加魔棒选区 (魔棒选区已经是基于图片像素坐标的)
        if self.selection_mask and not self.selection_mask.isEmpty():
            final_region += self.selection_mask

        # 叠加矩形选区 (需要从场景坐标转为图元本地像素坐标)
        if hasattr(self, "selection_manager"):
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
        new_pixmap.fill(Qt.GlobalColor.transparent)  # 先填透明

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
        if target_item == getattr(self, "pixmap_item", None):
            if self.current_bundle:
                self.current_bundle.original_pixmap = new_pixmap
                if self.current_bundle.frames:
                    self.current_bundle.frames[0].pixmap = new_pixmap

        # 6. 清理选区和蚂蚁线
        self.deselect_all()
        print("DEBUG [Editor]: 像素删除成功，已刷新显示")

    def on_expand_selection(self):
        if self.selection_mask:
            r = self.selection_mask
            # 向四周位移 1 像素并合并，实现外扩
            self.selection_mask = (
                r
                | r.translated(1, 0)
                | r.translated(-1, 0)
                | r.translated(0, 1)
                | r.translated(0, -1)
            )
            self.update_selection_display(self.selection_mask)

    def on_shrink_selection(self):
        if self.selection_mask:
            r = self.selection_mask
            # 只有上下左右都在原选区内的像素才保留，实现向内塌陷
            self.selection_mask = (
                r.intersected(r.translated(1, 0))
                .intersected(r.translated(-1, 0))
                .intersected(r.translated(0, 1))
                .intersected(r.translated(0, -1))
            )
            self.update_selection_display(self.selection_mask)

    def on_invert_selection(self):
        # 反选逻辑
        target_item = (
            self.preview_item
            if (self.preview_item and self.preview_item.isVisible())
            else self.pixmap_item
        )
        if target_item:
            full_rect = QRegion(target_item.pixmap().rect())
            self.selection_mask = (
                full_rect.subtracted(self.selection_mask)
                if self.selection_mask
                else full_rect
            )
            self.update_selection_display(self.selection_mask)

    def on_cut_mode_toggled(self, checked):
        if checked:
            # 进入裁切模式
            self.view.setDragMode(
                QGraphicsView.NoDrag
            )  # 禁用视图平移，让鼠标处理裁切框
            self.start_crop_session()
        else:
            # 退出裁切模式
            self.finish_crop_session()

    def start_crop_session(self):
        """进入裁切模式"""
        # 1. 核心修复：检查 pixmap_item 是否存在且是否有图片
        if not hasattr(self, "pixmap_item") or self.pixmap_item is None:
            print("DEBUG: 画布为空，无法启动裁切")
            # 强行把按钮弹回去
            self.btn_cut.blockSignals(True)
            self.btn_cut.setChecked(False)
            self.btn_cut.blockSignals(False)
            return

        target_item = self.pixmap_item
        if not target_item.pixmap() or target_item.pixmap().isNull():
            return

        # 2. 正常启动逻辑
        image_rect = target_item.boundingRect()
        # 传入当前场景范围和初始矩形
        self.crop_box = CropBoxItem(self.scene.sceneRect(), image_rect)
        self.scene.addItem(self.crop_box)

        self.view.setDragMode(ScalableView.NoDrag)

    def finish_crop_session(self):
        """应用裁切逻辑并退出"""
        # 1. 变量存在性检查
        if not hasattr(self, "crop_box") or self.crop_box is None:
            return

        try:
            # 2. 检查内部 C++ 对象是否还活着
            # 如果 scene() 返回 None 或抛出 RuntimeError，说明对象已销毁
            if not self.crop_box.scene():
                self.crop_box = None
                return

            self.save_undo_state()  # 存档

            crop_rect = self.crop_box.rect().normalized().toRect()

            # ... (中间的裁切逻辑保持不变) ...
            original_pixmap = self.pixmap_item.pixmap()
            if not original_pixmap.isNull():
                new_pixmap = QPixmap(crop_rect.width(), crop_rect.height())
                new_pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(new_pixmap)
                target_pos = QPoint(-crop_rect.x(), -crop_rect.y())
                painter.drawPixmap(target_pos, original_pixmap)
                painter.end()
                self.pixmap_item.setPixmap(new_pixmap)
                self.pixmap_item.setPos(0, 0)
                new_rect = QRectF(0, 0, new_pixmap.width(), new_pixmap.height())
                self.scene.setSceneRect(new_rect)
                if hasattr(self.view, "checker_item") and self.view.checker_item:
                    self.view.checker_item.set_rect(new_rect)

        except RuntimeError:
            # 捕获 "Internal C++ object already deleted"
            pass
        finally:
            # 3. 彻底清理引用
            if hasattr(self, "crop_box") and self.crop_box:
                # 再次检查 scene 确保可以安全 remove
                try:
                    if self.crop_box.scene():
                        self.scene.removeItem(self.crop_box)
                except RuntimeError:
                    pass
                self.crop_box = None

            # 4. 恢复 UI 状态
            # 暂时阻塞信号，防止按钮状态改变再次触发此函数导致死循环
            self.btn_cut.blockSignals(True)
            self.btn_cut.setChecked(False)
            self.btn_cut.blockSignals(False)
            self.view.setDragMode(ScalableView.ScrollHandDrag)

    def abort_crop_session(self):
        """完全放弃裁切，不保存任何改动并清理 UI"""
        if hasattr(self, "crop_box") and self.crop_box:
            try:
                if self.crop_box.scene():
                    self.scene.removeItem(self.crop_box)
            except RuntimeError:
                pass
            self.crop_box = None

        self.btn_cut.blockSignals(True)
        self.btn_cut.setChecked(False)
        self.btn_cut.blockSignals(False)
        self.view.setDragMode(ScalableView.ScrollHandDrag)

    def save_undo_state(self):
        """在任何修改操作（裁切、魔棒删除等）之前调用"""
        if not hasattr(self, "pixmap_item") or self.pixmap_item is None:
            return

        current_pixmap = self.pixmap_item.pixmap()
        if current_pixmap.isNull():
            return

        # 将当前图元的副本加入栈（必须用副本，防止引用干扰）
        self.undo_stack.append(current_pixmap.copy())

        # 如果超过 20 次，弹出最旧的一个
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)

        print(f"DEBUG: 已保存撤销点，当前步数: {len(self.undo_stack)}")

    def undo(self):
        """回退到上一个状态"""
        if not self.undo_stack:
            print("DEBUG: 没有可撤销的操作")
            return

        # 弹出最后一张图
        last_pixmap = self.undo_stack.pop()

        # 恢复图片
        self.pixmap_item.setPixmap(last_pixmap)
        self.pixmap_item.setPos(0, 0)

        # 同步更新场景和棋盘格（防止撤销的是裁切操作导致尺寸不对）
        new_rect = QRectF(0, 0, last_pixmap.width(), last_pixmap.height())
        self.scene.setSceneRect(new_rect)
        if hasattr(self.view, "checker_item") and self.view.checker_item:
            self.view.checker_item.set_rect(new_rect)

        print(f"DEBUG: 已撤销，剩余步数: {len(self.undo_stack)}")

    # selection_manager.py 中添加

    # selection_manager.py 中添加

    # def handle_key_nudge(self, key, is_boost=False):
    #     if not self.active: return

    #     # 1. 寻找目标：优先用鼠标正在拽的，没有就抓场景里最新的
    #     target = self.moving_item
    #     if not target:
    #         selections = self._get_valid_selections()
    #         if selections:
    #             target = selections[0] # 抓取最顶层的选区

    #     if not target:
    #         print("DEBUG: 场景中未发现选区框，请确保已点击 btn_pick 并画了一个框")
    #         return

    #     # 2. 执行抠图初始化 (只需执行一次)
    #     # 检查是否已经有了悬浮像素层
    #     if not hasattr(target, 'pix_overlay') or target.pix_overlay is None:
    #         # 找到主图层 (排除掉那些 clone 出来的)
    #         bg_item = next((i for i in self.scene.items()
    #                        if isinstance(i, QGraphicsPixmapItem) and not hasattr(i, 'is_clone')), None)

    #         if bg_item:
    #             print(f"DEBUG: 选区 {target} 首次移动，开始执行抠图...")
    #             # 获取选区在场景中的位置
    #             scene_rect = target.sceneBoundingRect()
    #             # 转换到主图的本地坐标
    #             local_top_left = bg_item.mapFromScene(scene_rect.topLeft()).toPoint()
    #             local_rect = QRect(local_top_left, scene_rect.size().toSize())

    #             # 保存原始区域信息，用于后续合并
    #             target.setData(10, local_rect)

    #             # 抠图并擦除原图对应区域
    #             crop_pix = bg_item.pixmap().copy(local_rect)
    #             self._permanently_erase_pixels(bg_item, local_rect)

    #             # 创建随框移动的像素层
    #             overlay = QGraphicsPixmapItem(crop_pix)
    #             overlay.is_clone = True
    #             overlay.setParentItem(target) # 关键：让像素层成为框的子元素
    #             overlay.setZValue(-1)
    #             overlay.setPos(target.boundingRect().topLeft())
    #             target.pix_overlay = overlay
    #             target.setBrush(self.add_color)

    #     # 3. 计算并位移
    #     step = 10 if is_boost else 1
    #     dx, dy = 0, 0
    #     if key == Qt.Key_Left: dx = -step
    #     elif key == Qt.Key_Right: dx = step
    #     elif key == Qt.Key_Up: dy = -step
    #     elif key == Qt.Key_Down: dy = step

    #     # 移动选区框，子项 pix_overlay 会自动同步移动
    #     target.moveBy(dx, dy)

    #     # 更新记录的位移差 (data(1))，确保 clear_selections 合并时位置正确
    #     curr_offset = target.data(1) or QPointF(0, 0)
    #     target.setData(1, curr_offset + QPointF(dx, dy))

    #     self.scene.update()
    #     print(f"DEBUG: 选区已移动 {dx}, {dy}")

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        is_ctrl = bool(
            modifiers
            & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        )
        is_shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        key = event.key()

        # --- 修改点：统一使用 selection_manager 的逻辑 ---
        if is_ctrl and key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            print(222)
            # 如果是选择模式，调用选区微调
            if self.btn_pick.isChecked():
                print(111)
                self.selection_manager.handle_key_nudge(key, is_shift)
            else:
                # 否则可以保留原有的 handle_pixel_nudge 或者不执行
                self.handle_pixel_nudge(key, is_shift)
                print(333)
            event.accept()
            return

        # 2. 撤销逻辑
        if is_ctrl and key == Qt.Key_Z:
            self.undo()
            event.accept()
            return

        # 3. 裁切模式
        if hasattr(self, "crop_box") and self.crop_box:
            # ... 保持原样 ...
            if key == Qt.Key_Escape:
                self.abort_crop_session()
                return
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self.finish_crop_session()
                return

        # 4. 只有不按 Ctrl 的纯方向键，才用来切换帧
        if not is_ctrl and key in (Qt.Key_Up, Qt.Key_Down):
            # 如果焦点不在列表，手动帮它切换
            if not self.frame_list.hasFocus():
                row = self.frame_list.currentRow()
                new_row = row - 1 if key == Qt.Key_Up else row + 1
                if 0 <= new_row < self.frame_list.count():
                    self.frame_list.setCurrentRow(new_row)
                event.accept()
                return

        super().keyPressEvent(event)

    def eventFilter(self, source, event):
        # --- 1. 处理鼠标事件 (解决选区不触发的核心) ---
        if source == self.view.viewport():
            mode = self.current_tool_mode

            # 只在选区模式下接管鼠标
            if mode == ToolMode.RECT_SELECT:
                # 获取场景坐标 (在过滤器里我们需要手动转换)
                if hasattr(event, "pos"):
                    scene_pos = self.view.mapToScene(event.pos())

                if event.type() == QEvent.MouseButtonPress:
                    print(f"DEBUG Filter: Mouse Press at {scene_pos}")
                    self.selection_manager.handle_mouse_press(event, scene_pos)
                    return True  # 拦截，不给 View 内部平移逻辑机会

                # --- 处理双击清空 ---
                elif event.type() == QEvent.MouseButtonDblClick:
                    print("DEBUG Filter: Double Click detected")
                    self.selection_manager.handle_double_click(scene_pos)
                    return True

                elif event.type() == QEvent.MouseMove:
                    self.selection_manager.handle_mouse_move(event, scene_pos)
                    return True

                elif event.type() == QEvent.MouseButtonRelease:
                    self.selection_manager.handle_mouse_release(event, scene_pos)
                    return True

        # --- 2. 处理键盘事件 (你原有的逻辑) ---
        if event.type() == QEvent.KeyPress:
            modifiers = event.modifiers()
            is_ctrl = bool(modifiers & (Qt.ControlModifier | Qt.MetaModifier))
            key = event.key()

            if is_ctrl and key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
                print(f"DEBUG Filter: Key Nudge {key}")
                is_shift = bool(modifiers & Qt.ShiftModifier)

                if self.current_tool_mode == ToolMode.RECT_SELECT:
                    self.selection_manager.handle_key_nudge(key, is_shift)
                else:
                    self.handle_pixel_nudge(key, is_shift)
                return True

        return super().eventFilter(source, event)

    def sync_and_notify(self):
        """核心：强制将编辑器内的 Pixmap 覆盖到 Bundle 模型对象中"""
        if not self.current_bundle or not self.current_frames:
            return

        # 1. 物理同步：遍历编辑器里的帧，强行覆盖 Bundle 里的 FrameData 对象
        for i, frame_info in enumerate(self.current_frames):
            # frame_info 是编辑器里的字典 {"pixmap": pix, "item": item}
            if i < len(self.current_bundle.frames):
                # 获取底层的 FrameData 实例
                target_frame_obj = self.current_bundle.frames[i]
                # 关键：更新该对象的 pixmap 引用
                target_frame_obj.pixmap = frame_info["pixmap"]

                # 可选：同步更新列表左侧的缩略图 (Icon)
                list_item = self.frame_list.item(i)
                if list_item:
                    icon_pix = frame_info["pixmap"].scaled(
                        45, 45, Qt.AspectRatioMode.KeepAspectRatio
                    )
                    list_item.setIcon(QIcon(icon_pix))

        # 2. 信号通知：确保预览面板收到两个参数
        curr_seg = getattr(self, "current_segment", {})
        # 兼容处理：如果 curr_seg 为空，构造一个临时的
        if not curr_seg and len(self.current_bundle.frames) > 0:
            curr_seg = {"start": 1, "end": len(self.current_bundle.frames)}

        self.bundle_updated.emit(self.current_bundle, curr_seg)
        print(f"DEBUG: [Sync Success] {self.current_bundle.name} 数据已入库")

    # -----------------------------------------------------------------

    def set_tool_mode(self, mode):
        """
        切换工具模式的唯一入口，负责清理旧状态和初始化新状态
        """
        # 如果重复点击当前已经激活的工具，可以选择跳过或触发取消行为
        # if self.current_tool_mode == mode: return

        # --- 第一阶段：清理旧工具 (Deactivate) ---
        self._cleanup_current_tool()

        # --- 第二阶段：更新模式 ---
        self.current_tool_mode = mode
        print(f"Tool changed to: {mode}")

        # --- 第三阶段：初始化新工具 (Activate) ---
        self._activate_new_tool(mode)

    def _cleanup_current_tool(self):
        old_mode = self.current_tool_mode

        if old_mode == ToolMode.RECT_SELECT:
            self.selection_manager.active = False
            self.selection_manager.abort_selection()  # 确保临时虚线框消失

        elif old_mode == ToolMode.MAGIC_WAND:
            self.magic_wand.clear_ants()
            # 如果有魔棒选区遮罩，看需求决定是否清理

        elif old_mode == ToolMode.CROP:
            # 如果用户正在裁切时点别的工具，视为取消裁切
            if hasattr(self, "crop_box") and self.crop_box:
                self.scene.removeItem(self.crop_box)
                self.crop_box = None

    def _activate_new_tool(self, mode):
        if mode == ToolMode.RECT_SELECT:
            # 强制禁用 View 自身的拖拽模式，不让它跟我们的过滤器抢左键
            self.view.setDragMode(QGraphicsView.NoDrag)
            self.view.viewport().setCursor(Qt.CrossCursor)
            self.selection_manager.active = True
