import os
from PySide6.QtWidgets import (
    QWidget,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QListWidgetItem,
    QGraphicsView,
)
from PySide6.QtCore import Qt, QRectF, Signal, QSize, QPoint, QEvent, QTimer
from PySide6.QtGui import (
    QPixmap,
    QIcon,
    QPainter,
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
from .magic_wand import MagicWandTool, SelectionAntsItem
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
        """加载新资源并重置所有编辑器状态"""
        self.undo_stack.clear()

        # --- 核心修复：在清理场景前，强制所有工具放弃对旧 Item 的引用 ---
        # 这样可以防止 C++ 对象被销毁后，Python 这边还留着“僵尸指针”
        if hasattr(self, "selection_manager"):
            self.selection_manager.force_reset_internal()

        if hasattr(self, "magic_wand_tool") and self.magic_wand_tool:
            # 假设你的魔棒工具也维护了一个选区列表，需要强行置空
            # 这里调用它的重置方法（如果没有请在 magic_wand.py 中添加）
            if hasattr(self.magic_wand_tool, "reset"):
                self.magic_wand_tool.reset()

        # 处理裁切框状态
        if hasattr(self, "crop_box") and self.crop_box:
            # 此处不需要 removeItem，因为后面的 scene.clear() 会搞定
            self.crop_box = None
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

        # --- 关键点：现在清理场景是安全的 ---
        self.scene.clear()

        self.preview_item = None
        self.frame_list.clear()
        self.current_frames = []

        # 3. 画布渲染
        rect = QRectF(0, 0, pixmap.width(), pixmap.height())
        self.view.checker_item = CheckerboardItem(rect)
        self.scene.addItem(self.view.checker_item)

        self.preview_item = QGraphicsPixmapItem(pixmap)
        self.preview_item.setTransformationMode(
            Qt.TransformationMode.FastTransformation
        )
        self.scene.addItem(self.preview_item)

        self.scene.setSceneRect(rect)
        self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

        # 4. 左侧列表：原图卡片渲染
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
        智能裁切逻辑：确保数据物理同步到 Bundle，并刷新 UI
        """
        # 1. 寻找画布上的底图
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

        # 2. 获取裁切后的结果
        rects = self.selection_manager.get_sorted_selections()
        source_pixmap = bg_item.pixmap()

        if rects:
            # 手动框选裁切
            new_frames_data = self.slice_logic.run_manual_slice(bg_item, rects)
        else:
            # 自动识别裁切
            new_frames_data = self.slice_logic.run_auto_slice_to_preview(source_pixmap)

        if not new_frames_data:
            return

        self.save_undo_state()

        # 3. 【核心同步】将结果写回 Bundle（这是 update_frame_list_ui 的数据源）
        if self.current_bundle:
            # 物理清空并重新填充 Bundle 的 frames
            self.current_bundle.frames = []
            for i, f in enumerate(new_frames_data):
                # 将字典数据包装回 FrameData 对象
                frame_obj = FrameData(
                    pixmap=f["pixmap"],
                    rect=f.get("rect", QRectF()),
                    name=f"{self.current_bundle.name}_{i}",
                )
                self.current_bundle.frames.append(frame_obj)

            # 同步更新 current_frames 变量，保持内存中引用一致
            self.current_frames = new_frames_data

            # 更新片段范围（Default 段落涵盖所有新帧）
            new_count = len(self.current_bundle.frames)
            for s in self.current_bundle.segments:
                if s.get("name") == "Default":
                    s["start"] = 1
                    s["end"] = new_count

        # 4. 清理选区残留
        self.selection_manager.clear_selections()  # 建议调用 manager 自带的清理
        self.selection_manager.active = False

        # 5. 【关键】不要完全删除 preview_item 导致丢失，而是重置它
        # 我们保留一个干净的画布，由 switch_frame_preview 去填充内容
        self.frame_list.clear()  # 先清空旧列表 UI
        self.update_frame_list_ui()  # 重新从 Bundle 读取并填充

        # 6. 重置按钮和索引
        self.btn_slice.setChecked(False)
        self.last_index = -1

        # 7. 切换到第一帧（这会自动设置 preview_item 的 Pixmap 和位置）
        if self.current_bundle.frames:
            self.frame_list.setCurrentRow(0)
            self.switch_frame_preview(0)

        self.sync_and_notify()

        if hasattr(self, "preview_panel"):
            # 强制先停一下，防止裁切瞬间逻辑抖动导致的计时器加速
            self.preview_panel.play_timer.stop()
            # 重新启动预览
            self.preview_panel.start_segment_preview(
                self.current_bundle, self.current_bundle.segments[0]
            )
        print(f"DEBUG [Slice]: 裁切完成，已识别 {len(new_frames_data)} 帧")

    def _sync_after_slice(self):
        """专门用于裁切后的同步"""
        target = self.parent()
        while target and target.__class__.__name__ != "BingoPacker":
            target = target.parent()

        if target and hasattr(target, "on_editor_bundle_changed"):
            target.on_editor_bundle_changed(self.current_bundle)

    def update_frame_list_ui(self):
        """强制从 Bundle 数据源刷新左侧列表，确保不为空"""
        if not self.current_bundle or not self.current_bundle.frames:
            print("DEBUG [UI]: Bundle 为空，清空列表")
            self.frame_list.clear()
            return

        self.frame_list.clear()
        # 核心：直接遍历 bundle 里的真实帧数据
        for i, frame_data in enumerate(self.current_bundle.frames):
            pix = frame_data.pixmap  # 注意这里是 frame_data.pixmap

            display_index = i + 1
            item = QListWidgetItem(f"帧 {display_index:02d}")
            item.setSizeHint(QSize(78, 80))

            # 生成缩略图
            icon_pix = pix.scaled(
                45,
                45,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            item.setIcon(QIcon(icon_pix))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.frame_list.addItem(item)

        print(f"DEBUG [UI]: 列表已刷新，共 {len(self.current_bundle.frames)} 帧")

    def switch_frame_preview(self, index):
        if index < 0 or index >= len(self.current_frames):
            return

        # 1. 正常清理选区状态 (保持你原有的逻辑)
        if hasattr(self, "selection_manager") and self.last_index != -1:
            old_frame_data = self.current_frames[self.last_index]
            self.selection_manager.clear_selections(target_frame_data=old_frame_data)

        self.last_index = index

        # 2. 不要重建对象！只需换图
        pix = self.current_frames[index]["pixmap"]
        self.preview_item.setPixmap(pix)

        # 3. 适配场景大小
        new_rect = QRectF(0, 0, pix.width(), pix.height())
        self.scene.setSceneRect(new_rect)
        if hasattr(self.view, "checker_item"):
            self.view.checker_item.set_rect(new_rect)

        self.view.fitInView(new_rect, Qt.AspectRatioMode.KeepAspectRatio)

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
        target_item = (
            self.preview_item
            if (self.preview_item and self.preview_item.isVisible())
            else self.preview_item
        )
        if not target_item or not target_item.pixmap():
            return

        # 获取本地坐标
        local_pos = target_item.mapFromScene(scene_pos).toPoint()
        print(f"DEBUG [Editor]: 场景坐标{scene_pos} -> 本地像素坐标{local_pos}")

        img = target_item.pixmap().toImage()
        self.magic_wand.tolerance = self.slider_tolerance.value()

        # 计算选区
        region = self.magic_wand.get_selection_region(
            img, local_pos, contiguous=self.check_contiguous.isChecked()
        )

        # 关键：更新选区并同步变换
        self.selection_mask = region
        self.update_selection_display(region)

        # 视觉同步：解决“看起来像全选”的视觉误差
        if hasattr(self, "temp_mask_item") and self.temp_mask_item:
            # 蚂蚁线图元必须和底图在坐标空间上完全对等
            self.temp_mask_item.setParentItem(target_item)  # 设置为底图的子项
            self.temp_mask_item.setPos(0, 0)  # 相对位置归零
            self.temp_mask_item.setTransform(
                target_item.transform()
            )  # 确保变换矩阵一致
            print(f"DEBUG [Editor]: 选区矩形数量: {region.rectCount()}")

    def update_selection_display(self, region):
        """
        更新并显示魔棒选区。
        """
        # 1. 彻底清理旧选区，防止残留
        if hasattr(self, "temp_mask_item") and self.temp_mask_item:
            print("DEBUG [Editor]: 移除旧选区图元")
            if self.temp_mask_item.scene():
                self.scene.removeItem(self.temp_mask_item)
            self.temp_mask_item = None

        if region is None or region.isEmpty():
            print("DEBUG [Editor]: 传入选区为空，停止动画")
            if hasattr(self, "ants_timer") and self.ants_timer:
                self.ants_timer.stop()
                self.ants_timer = None
            return

        # 2. 核心修复：安全地获取目标底图
        # 使用 getattr 防御 NoneType 错误
        preview_item = getattr(self, "preview_item", None)
        preview_item = getattr(self, "preview_item", None)

        target = None
        if preview_item is not None:
            try:
                if preview_item.isVisible():
                    target = preview_item
            except (RuntimeError, AttributeError):
                pass

        if target is None:
            target = preview_item

        if target is None:
            print("DEBUG [Editor]: 关键错误 - 找不到任何可用的底图 target")
            return

        # 3. 创建全新蚂蚁线图元
        print(f"DEBUG [Editor]: 创建新选区图元，精准边界: {region.boundingRect()}")
        self.temp_mask_item = SelectionAntsItem(region)
        self.scene.addItem(self.temp_mask_item)

        # 将选区挂载到图片图元上，使其跟随图片缩放/移动
        self.temp_mask_item.setParentItem(target)
        self.temp_mask_item.setPos(0, 0)
        self.temp_mask_item.setZValue(target.zValue() + 100)

        # 4. 动画控制
        if not hasattr(self, "ants_timer") or self.ants_timer is None:
            self.ants_timer = QTimer(self)
            self.ants_timer.timeout.connect(self._animate_ants)
            self.ants_timer.start(150)
            print("DEBUG [Editor]: 启动动画计时器")

        self.temp_mask_item.update()  # 确保在最上层

    def _animate_ants(self):
        if hasattr(self, "temp_mask_item") and self.temp_mask_item:
            self.temp_mask_item.offset += 1
            if self.temp_mask_item.offset > 8:  # 虚线周期长度
                self.temp_mask_item.offset = 0
            self.temp_mask_item.update()

    # def on_magic_wand_toggled(self, checked):
    #     """当魔棒按钮状态切换时触发"""
    #     if hasattr(self, "magic_wand_panel"):
    #         self.magic_wand_panel.setVisible(checked)

    #     # 只需要让视图重绘光标即可，不需要手动 setDragMode 了
    #     # 因为我们已经在视图内部通过状态机决定了鼠标样式
    #     if checked:
    #         # 互斥逻辑：开启魔棒时，关闭矩形选取模式
    #         self.btn_pick.setChecked(False)
    #         self.selection_manager.set_active(False)

    #     # 核心：通知视图根据最新状态更新光标
    #     self.view.update_cursor_style()
    #     print(f"DEBUG [Editor]: 魔棒模式切换为: {checked}")

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
        if not target_item and hasattr(self, "preview_item"):
            target_item = self.preview_item

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
        if target_item == getattr(self, "preview_item", None):
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
            else self.preview_item
        )
        if target_item:
            full_rect = QRegion(target_item.pixmap().rect())
            self.selection_mask = (
                full_rect.subtracted(self.selection_mask)
                if self.selection_mask
                else full_rect
            )
            self.update_selection_display(self.selection_mask)

    def save_undo_state(self):
        """在任何修改操作（裁切、魔棒删除等）之前调用"""
        if not hasattr(self, "preview_item") or self.preview_item is None:
            return

        current_pixmap = self.preview_item.pixmap()
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
        self.preview_item.setPixmap(last_pixmap)
        self.preview_item.setPos(0, 0)

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

        # --- 核心：裁切工具的键盘监听 ---
        if self.current_tool_mode == ToolMode.CROP:
            if key in (Qt.Key_Return, Qt.Key_Enter):
                print("DEBUG [Editor]: 键盘回车触发裁切")
                self.apply_crop()
                event.accept()
                return
            elif key == Qt.Key_Escape:
                print("DEBUG [Editor]: ESC 取消裁切")
                self.set_tool_mode(ToolMode.IDLE)
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
            # 获取场景坐标 (在过滤器里我们需要手动转换)
            if hasattr(event, "pos"):
                scene_pos = self.view.mapToScene(event.pos())

            if mode == ToolMode.MAGIC_WAND:
                if event.type() == QEvent.MouseButtonPress:
                    self.handle_magic_wand_click(scene_pos)
                    return True

            # 只在选区模式下接管鼠标
            if mode == ToolMode.RECT_SELECT:
                # 鼠标单击事件：交给 SelectionManager 处理，并且拦截掉让 View 自己处理
                if event.type() == QEvent.MouseButtonPress:
                    self.selection_manager.handle_mouse_press(event, scene_pos)
                    return True  # 拦截，不给 View 内部平移逻辑机会

                # --- 处理双击清空 ---
                elif event.type() == QEvent.MouseButtonDblClick:
                    scene_pos = self.view.mapToScene(event.pos())
                    self.selection_manager.handle_double_click(scene_pos)
                    return True

                elif event.type() == QEvent.MouseMove:
                    self.selection_manager.handle_mouse_move(event, scene_pos)
                    return True

                elif event.type() == QEvent.MouseButtonRelease:
                    self.selection_manager.handle_mouse_release(event, scene_pos)
                    return True
            if mode == ToolMode.CROP:
                # 只有双击时我们才主动拦截并执行 apply_crop
                # 正常的拖拽手柄逻辑由 CropBoxItem 内部的 mousePress/Move 实现
                # 因为它们是 QGraphicsItem，Scene 会自动分发事件给它们
                if event.type() == QEvent.MouseButtonDblClick:
                    # 如果双击的是裁切框内部，则确认裁切
                    if hasattr(self, "crop_box") and self.crop_box:
                        # 将场景坐标转为裁切框本地坐标判断是否点在框内
                        local_pos = self.crop_box.mapFromScene(scene_pos)
                        if self.crop_box.rect().contains(local_pos):
                            print("DEBUG [Filter]: 双击确认裁切")
                            self.apply_crop()
                            return True
                # 其他鼠标事件返回 False，让 Scene 正常传递给 CropBoxItem 的手柄
                return False

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
    # 在 editor_main.py 的 ManualEditor 类中添加
    def get_active_preview_item(self):
        """统一获取当前操作的目标图元"""
        if (
            hasattr(self, "preview_item")
            and self.preview_item
            and self.preview_item.isVisible()
        ):
            return self.preview_item
        return getattr(self, "preview_item", None)

    def apply_crop(self):
        """干净、彻底的裁切与同步逻辑"""
        if not hasattr(self, "crop_box") or not self.crop_box:
            return

        # 1. 提取像素 (这步你现在是正常的)
        new_pixmap = self.crop_box.get_cropped_pixmap()
        if not new_pixmap or new_pixmap.isNull():
            return

        # 2. 记录撤销并更新当前唯一的画布显示
        self.save_undo_state()
        self.preview_item.setPixmap(new_pixmap)
        self.preview_item.setPos(0, 0)

        # 3. 强制同步所有数据源，消除“数据孤岛”
        # 获取当前索引，默认为最后一次点击的索引
        idx = getattr(self, "last_index", 0)
        if idx == -1:
            idx = 0

        # A. 同步到 Bundle (持久层)
        if self.current_bundle and self.current_bundle.frames:
            if idx < len(self.current_bundle.frames):
                self.current_bundle.frames[idx].pixmap = new_pixmap
                self.current_bundle.original_pixmap = new_pixmap

        # B. 同步到 current_frames (UI 绑定层) - 解决列表清空的关键
        if hasattr(self, "current_frames") and self.current_frames:
            if idx < len(self.current_frames):
                # 必须直接修改字典里的 pixmap 引用
                self.current_frames[idx]["pixmap"] = new_pixmap

        # 4. 更新画布范围和棋盘格
        new_rect = QRectF(new_pixmap.rect())
        self.scene.setSceneRect(new_rect)
        if hasattr(self.view, "checker_item"):
            self.view.checker_item.set_rect(new_rect)

        # 5. 刷新 UI 列表：只要第 3-B 步同步了，这里就不会变空
        self.update_frame_list_ui()

        # 6. 恢复选中状态，防止用户迷失
        if self.frame_list.count() > idx:
            self.frame_list.setCurrentRow(idx)

        # 7. 退出工具模式
        self.set_tool_mode(ToolMode.IDLE)
        print(f"DEBUG [Apply]: 裁切完成，同步帧索引: {idx}")

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

        is_wand = mode == ToolMode.MAGIC_WAND
        self.magic_wand_panel.setVisible(is_wand)

        # --- 第三阶段：初始化新工具 (Activate) ---
        self._activate_new_tool(mode)

    def _cleanup_current_tool(self):
        old_mode = self.current_tool_mode

        if old_mode == ToolMode.RECT_SELECT:
            self.selection_manager.active = False
            self.selection_manager.abort_selection()  # 确保临时虚线框消失

        elif old_mode == ToolMode.MAGIC_WAND:
            self.deselect_all()
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

        elif mode == ToolMode.CROP:
            target = self.get_active_preview_item()
            if not target or not target.pixmap() or target.pixmap().isNull():
                print("DEBUG [Editor]: 无效底图，无法开启裁切")
                self.set_tool_mode(ToolMode.IDLE)
                return

            # 1. 搬家后的写法：直接将裁切框设为底图的子项 (parent_item=target)
            # 初始矩形直接使用底图的范围
            self.crop_box = CropBoxItem(target.boundingRect(), parent_item=target)

            # 2. 视觉配置
            self.view.setDragMode(QGraphicsView.NoDrag)
            print(f"DEBUG [Editor]: 裁切模式已激活，绑定到底图 {target}")
