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
        # 让 item 占满列表宽度，以避免列表右侧出现空白
        item.setSizeHint(QSize(self.frame_list.width(), 80))
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
        )
        self.frame_list.addItem(item)

        self.frame_list.blockSignals(False)
        self.frame_list.setCurrentRow(0)
        self._sync_to_global_preview(file_path, pixmap)

        self.update_status_bar()  # 刷新状态栏显示

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
            for i, f in enumerate(new_frames_data, start=1):
                # 将字典数据包装回 FrameData 对象
                frame_obj = FrameData(
                    pixmap=f["pixmap"],
                    rect=f.get("rect", QRectF()),
                    name=f"{self.current_bundle.name}_{i:02d}",
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

        self.update_status_bar()  # 刷新状态栏显示

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

    def switch_frame_preview(self, index):
        """切换显示指定索引的帧数据"""
        if index < 0 or index >= len(self.current_frames):
            return

        data_item = self.current_frames[index]
        # 确保拿到 Pixmap
        pix = (
            data_item.pixmap
            if hasattr(data_item, "pixmap")
            else data_item.get("pixmap")
        )

        if pix is None or pix.isNull():
            return

        # 确保预览 Item 存在
        if self.preview_item is None:
            self.preview_item = QGraphicsPixmapItem(pix)
            self.preview_item.setTransformationMode(
                Qt.TransformationMode.FastTransformation
            )
            self.scene.addItem(self.preview_item)
            self.preview_item.setZValue(0)
        else:
            self.preview_item.setPixmap(pix)

        # --- 核心修复：重置场景和视图范围 ---
        rect = QRectF(pix.rect())
        self.scene.setSceneRect(rect)  # 强制场景大小等于当前帧

        # 如果有棋盘格，同步它的大小
        if hasattr(self.view, "checker_item") and self.view.checker_item:
            self.view.checker_item.rect = rect
            self.view.checker_item.update()

        # 确保图像始终在 (0,0) 位置显示
        self.preview_item.setPos(0, 0)

        # 刷新视图，防止旧残影
        self.view.update()
        self.update_status_bar()  # 刷新状态栏显示

    def on_save_clicked(self):
        """保存按钮：精准抓取像素，排除棋盘格"""
        if not self.current_bundle or not self.preview_item:
            return

        curr_idx = self.frame_list.currentRow()
        if curr_idx == -1:
            return
        frame_data = self.current_bundle.frames[curr_idx]

        # 1. 准备画布
        rect = self.preview_item.pixmap().rect()
        final_pixmap = QPixmap(rect.size())
        # 关键：填充完全透明，确保没有背景色
        final_pixmap.fill(Qt.transparent)

        painter = QPainter(final_pixmap)

        # 2. 【核心修复】：手动控制绘制顺序，避开棋盘格
        # 第一步：画底图 (self.preview_item)
        painter.drawPixmap(0, 0, self.preview_item.pixmap())

        # 第二步：画悬浮选区 (如果有的话)
        if hasattr(self, "selection_manager"):
            for item in self.selection_manager.selections:
                if hasattr(item, "pix_overlay") and item.pix_overlay:
                    # 计算悬浮层相对于底图左上角的偏移量
                    # 场景坐标 - 底图场景坐标 = 相对坐标
                    offset = item.pix_overlay.scenePos() - self.preview_item.scenePos()
                    painter.drawPixmap(offset.toPoint(), item.pix_overlay.pixmap())

        painter.end()

        # 3. 更新内存并写盘
        frame_data.pixmap = final_pixmap
        self._execute_final_physical_save()

        # 4. 清理 UI 选区并同步
        if hasattr(self, "selection_manager"):
            self.selection_manager.clear_selections()

        self.sync_and_notify()

    def _execute_final_physical_save(self):
        """物理写入磁盘逻辑"""
        bundle = self.current_bundle
        if not bundle.path:
            return

        try:
            # 单帧模式：直接覆盖
            if len(bundle.frames) == 1:
                bundle.frames[0].pixmap.save(bundle.path, "PNG")
                print(f"DEBUG [Save]: 单帧原图已物理覆盖: {bundle.path}")
            else:
                # 多帧模式：创建同名文件夹
                parent_dir = os.path.dirname(bundle.path)
                target_folder = os.path.join(parent_dir, bundle.name)
                os.makedirs(target_folder, exist_ok=True)

                # 先清理旧的序列帧文件，避免残留旧的 frame_000 / 旧的命名格式
                for old in os.listdir(target_folder):
                    if (
                        old.startswith("frame_") or old.startswith(f"{bundle.name}_")
                    ) and old.lower().endswith(".png"):
                        try:
                            os.remove(os.path.join(target_folder, old))
                        except Exception:
                            pass

                for i, f in enumerate(bundle.frames, start=1):
                    save_path = os.path.join(
                        target_folder, f"{bundle.name}_{i:02d}.png"
                    )
                    f.pixmap.save(save_path, "PNG")
                print(f"DEBUG [Save]: 序列帧已更新至目录: {target_folder}")
        except Exception as e:
            print(f"DEBUG [Save]: 磁盘保存崩溃: {e}")

    def clear_all(self):
        """完全清空编辑器状态并重置全局环境"""

        # 先让所有工具管理器松手，防止后续事件触发 RuntimeError
        if hasattr(self, "selection_manager"):
            self.selection_manager.force_reset_internal()

        if hasattr(self, "magic_wand_tool") and self.magic_wand_tool:
            self.magic_wand_tool.reset()

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
        self.bundle_updated.emit(None, {})

    def import_project_file(self, file_path):
        """导入并还原工程文件数据到编辑器 UI"""
        # 1. 彻底清理旧状态，防止僵尸对象干扰
        self.update_selection_display(QRegion())
        if hasattr(self, "selection_manager"):
            self.selection_manager.force_reset_internal()

        self.asset_manager.clear_all()

        # 2. 解析模型
        new_bundle = self.asset_manager.load_from_file(file_path)
        if not new_bundle:
            return

        # 3. 同步基础数据
        self.current_bundle = new_bundle
        self.current_source_path = file_path

        # 4. 【关键修复】还原 current_frames：必须确保它是 FrameData 对象列表
        # 这样 switch_frame_preview 才能通过 .pixmap 访问
        self.current_frames = []
        for f in new_bundle.frames:
            # 这里的 f 已经是 AssetManager 加载好的 FrameData 实例了
            # 我们直接引用它即可，确保对象属性完整
            self.current_frames.append(f)

        # 5. UI 深度重置：先清空场景和列表
        self.frame_list.blockSignals(True)
        self.scene.clear()
        self.preview_item = None
        self.frame_list.clear()  # 显式清空左侧列表

        # 6. 【核心修复】重建左侧缩略图 UI
        # 必须在 clear 之后立即填充新数据
        self.update_frame_list_ui()

        # 7. 还原画布渲染
        if self.current_frames:
            # 取第一帧数据用于初始化画布尺寸
            first_frame = self.current_frames[0]
            first_pix = first_frame.pixmap

            if not first_pix.isNull():
                new_rect = QRectF(0, 0, first_pix.width(), first_pix.height())
                self.scene.setSceneRect(new_rect)

                # 初始化棋盘格背景
                self.view.checker_item = CheckerboardItem(new_rect)
                self.scene.addItem(self.view.checker_item)
                self.view.checker_item.setZValue(-10)  # 确保在最底层

                # 恢复信号处理
                self.frame_list.blockSignals(False)

                # 选中第一行，这会触发渲染
                if self.frame_list.count() > 0:
                    self.frame_list.setCurrentRow(0)
                    # 显式调用一次渲染，确保画布出现图像
                    self.switch_frame_preview(0)

                # 自动缩放以适应视口
                self.view.fitInView(new_rect, Qt.AspectRatioMode.KeepAspectRatio)

        # 8. 同步外部面板（AssetTree 等）
        self.bundle_updated.emit(self.current_bundle, {})

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

    def update_selection_display(self, region):
        """
        更新并显示魔棒选区。
        """
        # 1. 彻底清理旧选区，防止残留
        if hasattr(self, "temp_mask_item") and self.temp_mask_item:
            if self.temp_mask_item.scene():
                self.scene.removeItem(self.temp_mask_item)
            self.temp_mask_item = None

        if region is None or region.isEmpty():
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

        # 3. 创建全新蚂蚁线图元
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

        self.temp_mask_item.update()  # 确保在最上层

    def _animate_ants(self):
        if hasattr(self, "temp_mask_item") and self.temp_mask_item:
            self.temp_mask_item.offset += 1
            if self.temp_mask_item.offset > 8:  # 虚线周期长度
                self.temp_mask_item.offset = 0
            self.temp_mask_item.update()

    def deselect_all(self):
        """取消选择：同时清理魔棒选区和手动矩形选区"""
        # 1. 清理魔棒选区
        if self.selection_mask:
            from PySide6.QtGui import QRegion

            self.selection_mask = None
            self.update_selection_display(
                QRegion()
            )  # 传入空选区会触发我们写好的清理逻辑

        # 2. 清理手动绘制的矩形选区 (SelectionManager)
        if hasattr(self, "selection_manager"):
            self.selection_manager.clear_selections()

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

    def on_expand_selection(self):
        if self.selection_mask:
            r = self.selection_mask
            # 8 方向扩张：上下左右 + 四个对角线
            self.selection_mask = (
                r
                | r.translated(1, 0)  # 右
                | r.translated(-1, 0)  # 左
                | r.translated(0, 1)  # 下
                | r.translated(0, -1)  # 上
                | r.translated(1, 1)  # 右下
                | r.translated(-1, -1)  # 左上
                | r.translated(1, -1)  # 右上
                | r.translated(-1, 1)  # 左下
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

    def undo(self):
        """回退到上一个状态"""
        if not self.undo_stack:
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
            # 如果是选择模式，调用选区微调
            if self.btn_pick.isChecked():
                self.selection_manager.handle_key_nudge(key, is_shift)
            else:
                # 否则可以保留原有的 handle_pixel_nudge 或者不执行
                self.selection_manager.handle_pixel_nudge(key, is_shift)
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
                self.apply_crop()
                event.accept()
                return
            elif key == Qt.Key_Escape:
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
                is_shift = bool(modifiers & Qt.ShiftModifier)

                if self.current_tool_mode == ToolMode.RECT_SELECT:
                    self.selection_manager.handle_key_nudge(key, is_shift)
                else:
                    self.selection_manager.handle_pixel_nudge(key, is_shift)
                return True

        return super().eventFilter(source, event)

    def sync_and_notify(self):
        """这个函数是全程序的刷新总闸"""
        if not self.current_bundle:
            return

        # 1. 强制发射信号，带上最新的数据
        # 只要这一行执行了，你的右侧预览面板、动画播放就一定会变
        self.bundle_updated.emit(self.current_bundle, {})

        # 2. 刷新左侧列表的图标
        curr_idx = self.frame_list.currentRow()
        if 0 <= curr_idx < len(self.current_bundle.frames):
            f_data = self.current_bundle.frames[curr_idx]
            pix = f_data.pixmap if hasattr(f_data, "pixmap") else f_data.get("pixmap")
            if pix:
                icon_pix = pix.scaled(
                    48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                item = self.frame_list.item(curr_idx)
                if item:
                    item.setIcon(QIcon(icon_pix))

        self.view.update()
        print("DEBUG [Sync]: UI 已全局刷新")

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

        self.update_status_bar()  # 刷新状态栏显示

    def _reset_tool_buttons(self):
        """将所有工具按钮恢复到未选中状态"""
        self.btn_pick.blockSignals(True)
        self.btn_pick.setChecked(False)
        self.btn_magic_wand.blockSignals(True)
        self.btn_magic_wand.setChecked(False)
        self.btn_cut.blockSignals(True)
        self.btn_cut.setChecked(False)
        # ... 如果还有其他工具按钮，也写在这里 ...
        self.btn_pick.blockSignals(False)
        self.btn_magic_wand.blockSignals(False)
        self.btn_cut.blockSignals(False)

    def update_status_bar(self):
        """同步底部所有标签的信息"""
        if not self.current_bundle:
            return

        # 1. 更新帧序号
        total_frames = len(self.current_bundle.frames)
        curr_idx = self.frame_list.currentRow() + 1
        self.lbl_frame_index.setText(
            f"帧: {curr_idx if curr_idx > 0 else 0} / {total_frames}"
        )

        # 2. 更新尺寸
        if self.preview_item and self.preview_item.pixmap():
            pix = self.preview_item.pixmap()
            self.lbl_frame_size.setText(f"尺寸: {pix.width()} x {pix.height()} PX")

        # # 3. 更新缩放 (如果你的 ScalableView 有这个属性)
        # if hasattr(self.view, "current_zoom"):
        #     zoom = int(self.view.current_zoom * 100)
        #     self.lbl_zoom_level.setText(f"缩放: {zoom}%")

        # 4. 【新增】更新资源名
        if hasattr(self, "lbl_res_name"):
            # 假设 bundle.name 存储了文件名，如果没有，可以用 os.path.basename(self.current_bundle.path)
            res_name = getattr(self.current_bundle, "name", "未知资源")
            self.lbl_res_name.setText(f"资源: {res_name}")

    def set_tool_mode(self, mode):
        """
        切换工具模式的唯一入口，负责清理旧状态和初始化新状态
        """
        # 如果不是切换到 IDLE，且当前没有任何底图，则拦截
        if mode != ToolMode.IDLE:
            target = self.get_active_preview_item()
            if not target or not target.pixmap() or target.pixmap().isNull():
                # 强制弹回所有工具按钮的状态（取消选中）
                self._reset_tool_buttons()
                return

        if self.current_tool_mode == mode:
            return

        # --- 第一阶段：清理旧工具 (Deactivate) ---
        self._cleanup_current_tool()

        # --- 第二阶段：更新模式 ---
        self.current_tool_mode = mode
        # print(f"Tool changed to: {mode}")

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
                self.set_tool_mode(ToolMode.IDLE)
                return

            # 1. 搬家后的写法：直接将裁切框设为底图的子项 (parent_item=target)
            # 初始矩形直接使用底图的范围
            self.crop_box = CropBoxItem(target.boundingRect(), parent_item=target)

            # 2. 视觉配置
            self.view.setDragMode(QGraphicsView.NoDrag)
