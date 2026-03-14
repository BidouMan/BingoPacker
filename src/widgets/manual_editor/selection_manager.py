from PySide6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsView,
    QGraphicsPixmapItem,
)
from PySide6.QtCore import Qt, QRectF, QPointF, QRect
from PySide6.QtGui import (
    QPen,
    QColor,
    QPainterPath,
    QPainter,
    QBitmap,
    QPixmap,
    QRegion,
    QIcon,
)  # 确保 QPainter 在这里


class SelectionManager:
    def __init__(self, scene):
        self.scene = scene
        self.selections = []
        self.temp_rect = None
        self.start_point = None
        self.active = False

        # --- 必须在这里初始化新添加的变量 ---
        self.moving_item = None  # 当前正在移动的选区项
        self.last_move_pos = None  # 上一次移动时的鼠标位置
        self.bg_mask = None

        # 1. 定义填充颜色 (之前遗漏的部分)
        self.add_color = QColor(137, 180, 250, 80)
        self.remove_color = QColor(243, 139, 168, 80)

        # 2. 定义画笔样式
        self.add_pen = QPen(QColor(137, 180, 250), 1)
        self.add_pen.setCosmetic(True)

        self.dash_pen_add = QPen(QColor(137, 180, 250), 1, Qt.DashLine)
        self.dash_pen_add.setCosmetic(True)

        self.dash_pen_remove = QPen(QColor(243, 139, 168), 1, Qt.DashLine)
        self.dash_pen_remove.setCosmetic(True)

    def set_active(self, active):
        self.active = active

        # 强制更新光标
        if self.scene.views():
            view = self.scene.views()[0]
            if active:
                # 使用 QGraphicsView.NoDrag
                view.setDragMode(QGraphicsView.NoDrag)
                view.setCursor(Qt.CrossCursor)  # 变成十字光标
            else:
                # 使用 QGraphicsView.ScrollHandDrag
                view.setDragMode(QGraphicsView.ScrollHandDrag)
                view.unsetCursor()

        # 如果不开启，清除临时的拉框残留
        if not active:
            self.start_point = None
            if self.temp_rect:
                self.scene.removeItem(self.temp_rect)
                self.temp_rect = None

    def _snap_to_pixel(self, pos):
        return QPointF(round(pos.x()), round(pos.y()))

    def _update_background_mask(self, bg_item):
        """
        实时计算所有已移动选区的原始位置，并让背景图在那块区域变透明
        """
        full_pix_size = bg_item.pixmap().size()
        # 创建一个全显的 Region
        mask_region = QRegion(
            QRect(0, 0, full_pix_size.width(), full_pix_size.height())
        )

        # 遍历所有选区，如果该选区已经被“移动”了（即有了 pix_overlay）
        # 我们就把它的“原始坑位”从遮罩里减去
        for item in self.selections:
            orig_pos = item.data(10)  # 存储的是 QRect
            if orig_pos and hasattr(item, "pix_overlay"):
                mask_region -= QRegion(orig_pos)

        # 生成遮罩位图
        mask_bitmap = QBitmap(full_pix_size)
        mask_bitmap.fill(Qt.GlobalColor.white)  # 默认全白（显示）

        p = QPainter(mask_bitmap)
        # 只在非遮罩区（被剪切走的地方）画黑，黑色在 Mask 中代表透明
        p.setClipRegion(
            QRegion(QRect(0, 0, full_pix_size.width(), full_pix_size.height()))
            - mask_region
        )
        p.fillRect(
            QRect(0, 0, full_pix_size.width(), full_pix_size.height()),
            Qt.GlobalColor.black,
        )
        p.end()

        bg_item.setMask(mask_bitmap)

    def _get_valid_selections(self):
        valid = []
        for item in self.selections:
            try:
                _ = item.scene()
                valid.append(item)
            except RuntimeError:
                continue
        self.selections = valid
        return self.selections

    def _get_item_path(self, item):
        if isinstance(item, QGraphicsRectItem):
            path = QPainterPath()
            path.addRect(item.rect())
            return path
        return item.path()

    def _update_item_shape(self, item, path):
        if isinstance(item, QGraphicsRectItem):
            new_item = QGraphicsPathItem(path)
            new_item.setPen(self.add_pen)
            new_item.setBrush(self.add_color)
            new_item.setZValue(10)
            idx = self.selections.index(item)
            self.selections[idx] = new_item
            self.scene.removeItem(item)
            self.scene.addItem(new_item)
        else:
            item.setPath(path)

    def _create_new_rect(self, rect):
        item = QGraphicsRectItem(rect)
        item.setPen(self.add_pen)
        item.setBrush(self.add_color)
        item.setZValue(10)
        self.scene.addItem(item)
        self.selections.append(item)

    def handle_double_click(self, scene_pos):
        print(1)
        if not self.active:
            return
        valid_items = self._get_valid_selections()
        items = self.scene.items(scene_pos)
        clicked = [i for i in items if i in valid_items]
        if clicked:
            print(2)
            self._remove_item(clicked[0])
        else:
            self.clear_selections()
            print(3)

    def clear_selections(self, target_frame_data=None):
        """
        物理清理所有选区。
        target_frame_data: 如果传入，则强制合并到这个数据对象中，解决切换帧时的“时差”问题。
        """
        if not self.selections:
            return

        for item in self.selections[:]:
            # 执行合并逻辑
            # 注意：如果 target_frame_data 为空，它内部会去猜 currentRow，所以我们建议在 editor 切换时必传
            self._merge_back_to_bg(item, target_frame_data=target_frame_data)

            # 从场景物理移除
            if item.scene():
                self.scene.removeItem(item)

        self.selections.clear()
        self.moving_item = None
        self.active = False

    def _apply_transparent_holes(self, bg_item):
        """
        通过 QPainter 混合模式，真正地擦除背景图上的像素
        """
        # 获取最原始的图片（建议在 SelectionManager 初始化或加载图时存一份原始 self.full_original_pixmap）
        # 这里我们假设 bg_item.data(99) 存储了未经修改的原始全图
        if not bg_item.data(99):
            bg_item.setData(99, bg_item.pixmap().copy())

        original_pixmap = bg_item.data(99)

        # 创建一个带有 Alpha 通道的画布
        result_pixmap = QPixmap(original_pixmap.size())
        result_pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(result_pixmap)
        # 1. 先画上原图
        painter.drawPixmap(0, 0, original_pixmap)

        # 2. 设置组合模式为 DestinationOut (擦除模式：画上去的地方会变透明)
        painter.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        painter.setBrush(Qt.GlobalColor.black)  # 颜色不重要，Alpha 才是关键
        painter.setPen(Qt.PenStyle.NoPen)

        # 3. 遍历所有移动过的选区，把它们的原始位置抠掉
        for item in self.selections:
            orig_rect = item.data(10)
            if orig_rect and hasattr(item, "pix_overlay"):
                painter.drawRect(orig_rect)

        painter.end()

        # 4. 更新显示
        bg_item.setPixmap(result_pixmap)

    def _permanently_erase_pixels(self, bg_item, rect):
        """
        物理擦除：直接在背景图上把选中区域‘挖空’，保留原有的透明度
        """
        pix = bg_item.pixmap()
        # 确保图片格式支持 Alpha 通道
        new_pix = QPixmap(pix.size())
        new_pix.fill(Qt.GlobalColor.transparent)

        p = QPainter(new_pix)
        p.drawPixmap(0, 0, pix)  # 先画原图

        # 使用 DestinationOut：在已有的图像上，把画上去的形状区域‘扣掉’变成透明
        p.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        p.setBrush(Qt.GlobalColor.black)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(rect)
        p.end()

        bg_item.setPixmap(new_pix)

    def _remove_item(self, item):
        """
        删除单个选区：确保在删除框之前，像素已经稳固地写回底图
        """
        if item in self.selections:
            # 1. 检查是否有移动过的像素贴图层
            if hasattr(item, "pix_overlay") and item.pix_overlay:
                self._merge_back_to_bg(item)

            # 2. 从管理列表移除
            self.selections.remove(item)

            # 3. 从场景中彻底删除选区及其所有子元素
            if item.scene():
                self.scene.removeItem(item)

    def handle_key_nudge(self, key, is_boost=False):
        """键盘位移：仅操作图元，不触发物理合并"""
        if not self.active:
            return

        target = self.moving_item
        if not target:
            valid_selections = [s for s in self.selections if s.scene()]
            if valid_selections:
                target = valid_selections[-1]
        if not target:
            return

        # 1. 只有第一次位移时，执行抠图 (Data 10 记录了原始区域)
        if not hasattr(target, "pix_overlay") or target.pix_overlay is None:
            bg_item = next(
                (
                    i
                    for i in self.scene.items()
                    if isinstance(i, QGraphicsPixmapItem) and not hasattr(i, "is_clone")
                ),
                None,
            )
            if bg_item:
                scene_rect = target.sceneBoundingRect()
                local_top_left = bg_item.mapFromScene(scene_rect.topLeft()).toPoint()
                local_rect = QRect(local_top_left, scene_rect.size().toSize())

                target.setData(10, local_rect)
                crop_pix = bg_item.pixmap().copy(local_rect)
                self._permanently_erase_pixels(bg_item, local_rect)  # 挖空底图

                overlay = QGraphicsPixmapItem(crop_pix)
                overlay.is_clone = True
                overlay.setParentItem(target)
                overlay.setZValue(-1)
                overlay.setPos(target.boundingRect().topLeft())
                target.pix_overlay = overlay

        # 2. 执行物理位移 (dx, dy)
        step = 10 if is_boost else 1
        dx, dy = 0, 0
        if key == Qt.Key_Left:
            dx = -step
        elif key == Qt.Key_Right:
            dx = step
        elif key == Qt.Key_Up:
            dy = -step
        elif key == Qt.Key_Down:
            dy = step

        target.moveBy(dx, dy)

        # 3. 更新 Data(1) 累计位移量
        curr_offset = target.data(1) or QPointF(0, 0)
        target.setData(1, curr_offset + QPointF(dx, dy))

        self.scene.update()
        # 注意：绝对不要在这里调用 self._merge_back_to_bg(target) !!

    def _merge_back_to_bg(self, item, target_frame_data=None):
        """
        物理合并：将悬浮像素焊死到底图。
        修正：严格限制底图查找范围，防止抓取到已隐藏的原始素材。
        """
        # 1. 寻找场景中的底图图元
        # 增加条件：必须是可见的 (isVisible)！这样就不会抓到裁切后隐藏的原始大图
        bg_item = next(
            (
                i
                for i in self.scene.items()
                if isinstance(i, QGraphicsPixmapItem)
                and not hasattr(i, "is_clone")
                and i.isVisible()
            ),
            None,
        )

        if not bg_item:
            return

        if not hasattr(item, "pix_overlay") or not item.pix_overlay:
            return

        # 2. 获取位置和图像信息
        overlay = item.pix_overlay
        overlay_pix = overlay.pixmap()
        scene_pos = overlay.scenePos()
        local_pos = bg_item.mapFromScene(scene_pos).toPoint()

        current_bg_pix = bg_item.pixmap()
        bg_rect = current_bg_pix.rect()
        overlay_rect = QRect(local_pos, overlay_pix.size())

        # 3. 计算并集区域（处理越界）
        combined_rect = bg_rect.united(overlay_rect)

        # 4. 绘制新画布
        new_bg_pix = QPixmap(combined_rect.size())
        new_bg_pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(new_bg_pix)
        offset = -combined_rect.topLeft()

        painter.drawPixmap(offset, current_bg_pix)
        painter.drawPixmap(local_pos + offset, overlay_pix)
        painter.end()

        # 5. 更新显示
        new_scene_pos = bg_item.mapToScene(combined_rect.topLeft())
        bg_item.setPixmap(new_bg_pix)
        bg_item.setPos(new_scene_pos)
        bg_item.setData(99, new_bg_pix.copy())

        # --- 6. 寻找 Editor 实例进行数据同步 ---
        view = self.scene.views()[0]
        editor = view.parent()
        while editor and not hasattr(editor, "bundle_updated"):
            editor = editor.parent()

        if editor:
            # 优先使用显式传入的 target_frame_data
            if target_frame_data is not None:
                target_frame_data["pixmap"] = new_bg_pix
            else:
                # 否则使用当前选中的索引（注意：这里要确保 index 是切换前的 index）
                idx = editor.frame_list.currentRow()
                if 0 <= idx < len(editor.current_frames):
                    editor.current_frames[idx]["pixmap"] = new_bg_pix

            # 触发编辑器同步到 AssetBundle 并通知预览面板
            editor.sync_and_notify()

    def _sync_to_editor_model(self, new_pix):
        try:
            view = self.scene.views()[0]
            parent_widget = view.parent()
            while parent_widget:
                if parent_widget.__class__.__name__ == "ManualEditor":
                    # --- 修复点：确保我们更新的是“合并前”的那一帧 ---
                    # 如果有 selection_manager 在工作，我们应该相信此时场景里对应的那个 bundle 数据
                    if parent_widget.current_bundle:
                        # 找到当前正在预览的那个 index
                        idx = parent_widget.frame_list.currentRow()
                        if 0 <= idx < len(parent_widget.current_frames):
                            parent_widget.current_frames[idx]["pixmap"] = new_pix

                            # 更新列表左侧的缩略图 (解决预览不同步)
                            icon_pix = new_pix.scaled(
                                45, 45, Qt.AspectRatioMode.KeepAspectRatio
                            )
                            parent_widget.frame_list.item(idx).setIcon(QIcon(icon_pix))

                            # 通知外部（预览窗口等）数据已变
                            parent_widget.bundle_updated.emit(
                                parent_widget.current_bundle
                            )
                    break
                parent_widget = parent_widget.parent()
        except Exception as e:
            print(f"Sync error: {e}")

    def get_sorted_selections(self):
        """
        按照“从上到下，从左到右”的逻辑返回相对于底图的矩形区域
        """
        valid_items = self._get_valid_selections()
        if not valid_items:
            return []

        # 获取底图对象，用于坐标转换
        bg_item = next(
            (
                i
                for i in self.scene.items()
                if isinstance(i, QGraphicsPixmapItem) and not hasattr(i, "is_clone")
            ),
            None,
        )

        data = []
        for item in valid_items:
            # 1. 获取场景矩形并转为底图局部矩形
            scene_rect = item.sceneBoundingRect()
            if bg_item:
                local_top_left = bg_item.mapFromScene(scene_rect.topLeft()).toPoint()
                # 转换成整数像素矩形，方便直接用于裁切
                rect = QRect(local_top_left, scene_rect.size().toSize())
            else:
                rect = scene_rect.toRect()

            data.append(
                {
                    "rect": rect,
                    "center_y": rect.center().y(),
                    "center_x": rect.center().x(),
                    "height": rect.height(),
                }
            )

        # 2. 计算平均高度作为分行阈值
        avg_height = sum(d["height"] for d in data) / len(data)
        row_threshold = avg_height * 0.7  # 稍微调高阈值到 0.7，容错性更高

        # 3. 排序逻辑
        data.sort(key=lambda d: d["center_y"])

        final_sorted = []
        current_row = []

        if data:
            # 使用当前行的起始 Y 值
            row_y_reference = data[0]["center_y"]
            for d in data:
                # 判断是否属于同一行
                if abs(d["center_y"] - row_y_reference) < row_threshold:
                    current_row.append(d)
                else:
                    # 处理旧行：行内按 X 排序
                    current_row.sort(key=lambda x: x["center_x"])
                    final_sorted.extend([r["rect"] for r in current_row])
                    # 开启新行
                    current_row = [d]
                    row_y_reference = d["center_y"]

            # 处理最后一行
            current_row.sort(key=lambda x: x["center_x"])
            final_sorted.extend([r["rect"] for r in current_row])

        return final_sorted

    def _get_valid_selections(self):
        """
        寻找场景中所有的选区框（兼容矩形和路径项）。
        """
        from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsRectItem

        valid = []

        # 获取场景中所有项
        all_items = self.scene.items()
        for item in all_items:
            # 同时检查 PathItem 和 RectItem
            is_selection_type = isinstance(item, (QGraphicsPathItem, QGraphicsRectItem))

            if is_selection_type and item.isVisible():
                # 排除掉掉那些被标记为像素层 (is_clone) 的对象
                if not hasattr(item, "is_clone"):
                    # 额外检查：确保它属于我们管理的 selections 列表，或者是我们画的框
                    if item in self.selections:
                        valid.append(item)

        # 为了键盘操作能抓到“最新”的一个，我们按创建顺序倒序排列（selections 列表末尾是最新的）
        # 或者直接返回 self.selections 中仍然在场景里的项
        return [s for s in self.selections if s.scene()]

    def abort_selection(self):
        """【新增】强行中止选区工具，清理所有临时和正式选区"""
        # 1. 清理正在拖拽的临时框
        if self.temp_rect:
            if self.temp_rect.scene() == self.scene:
                self.scene.removeItem(self.temp_rect)
            self.temp_rect = None

        # 2. 清理所有已经画好的选区
        self.clear_selections()

        # 3. 重置状态位
        self.start_point = None
        self.active = False
        self.moving_item = None

    # selection_manager.py

    def handle_mouse_press(self, event, scene_pos):
        print("!!! HIT MANAGER PRESS !!!")
        """由 ScalableView 转发过来，确保只接两个参数"""
        # 强制清除之前的状态
        if self.temp_rect:
            if self.temp_rect.scene():
                self.scene.removeItem(self.temp_rect)
            self.temp_rect = None

        self.start_point = scene_pos
        self.active = True

        if event.button() == Qt.LeftButton:
            from PySide6.QtWidgets import QGraphicsRectItem

            self.temp_rect = QGraphicsRectItem()
            self.temp_rect.setPen(self.add_pen)
            self.temp_rect.setBrush(self.add_color)
            self.temp_rect.setZValue(1000)  # 置顶
            self.scene.addItem(self.temp_rect)
            # 这行如果没印出来，说明 ScalableView 根本没能成功调用到这个版本的函数
            print(f"DEBUG: Manager received Press at {scene_pos}")

    def handle_mouse_move(self, event, scene_pos):
        if not self.active or self.start_point is None or self.temp_rect is None:
            return

        # 更新矩形大小
        rect = QRectF(self.start_point, scene_pos).normalized()
        self.temp_rect.setRect(rect)
        # 强制刷新视图
        self.scene.update()

    def handle_mouse_release(self, event, scene_pos):
        if not self.active or self.temp_rect is None:
            return

        final_rect = self.temp_rect.rect()
        if final_rect.width() > 2 and final_rect.height() > 2:
            self.selections.append(self.temp_rect)
            print(f"DEBUG: Selection created: {final_rect}")
            self.temp_rect = None
        else:
            if self.temp_rect.scene():
                self.scene.removeItem(self.temp_rect)
            self.temp_rect = None

        self.active = False
        self.start_point = None
