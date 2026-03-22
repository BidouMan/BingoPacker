from PySide6.QtCore import QPoint
from PySide6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsView,
    QGraphicsPixmapItem,
    QGraphicsItem,
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


class ClippedPixmapItem(QGraphicsPixmapItem):
    """自定义的裁剪图像项，实现实时裁剪效果"""

    def __init__(self, pixmap, parent=None):
        super().__init__(pixmap, parent)
        self.bg_item = None  # 背景图项，用于获取画布边界

    def set_bg_item(self, bg_item):
        """设置背景图项，用于获取画布边界"""
        self.bg_item = bg_item

    def paint(self, painter, option, widget):
        """重写paint方法，实现实时裁剪"""
        if not self.bg_item:
            super().paint(painter, option, widget)
            return

        # 获取背景图的边界（画布范围）
        bg_rect = QRectF(self.bg_item.pos(), self.bg_item.pixmap().size())

        # 获取当前项在场景中的边界
        item_rect = self.sceneBoundingRect()

        # 计算交集区域（只绘制画布范围内的部分）
        intersection_rect = bg_rect.intersected(item_rect)

        if intersection_rect.isNull():
            # 如果没有交集，不绘制任何内容
            return

        # 计算绘制区域在pixmap中的位置
        pixmap_rect = self.boundingRect()
        draw_pos = QPointF(
            intersection_rect.left() - item_rect.left(),
            intersection_rect.top() - item_rect.top(),
        )

        # 只绘制交集区域
        painter.drawPixmap(
            intersection_rect.topLeft() - self.scenePos(),  # 使用scenePos()获取场景位置
            self.pixmap(),
            QRectF(draw_pos, intersection_rect.size()),
        )


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
        original_pixmap = bg_item.pixmap()
        if original_pixmap.isNull():
            return

        full_pix_size = original_pixmap.size()

        # 创建一个新的pixmap作为结果
        result_pixmap = QPixmap(full_pix_size)
        result_pixmap.fill(Qt.transparent)

        # 创建一个画家来绘制
        p = QPainter(result_pixmap)

        # 绘制原始图片
        p.drawPixmap(0, 0, original_pixmap)

        # 遍历所有选区，如果该选区已经被"移动"了（即有了 pix_overlay）
        # 我们就在原始位置绘制透明区域
        for item in self.selections:
            orig_pos = item.data(10)  # 存储的是 QRect
            if orig_pos and hasattr(item, "pix_overlay"):
                # 在原始位置绘制透明区域
                p.setCompositionMode(QPainter.CompositionMode_Clear)
                p.fillRect(orig_pos, Qt.transparent)
                p.setCompositionMode(QPainter.CompositionMode_SourceOver)

        p.end()

        # 更新背景图
        bg_item.setPixmap(result_pixmap)

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
        """核心：确保形状更新的同时，保留所有绑定的逻辑数据"""
        new_item = QGraphicsPathItem(path)
        new_item.setPen(self.add_pen)
        new_item.setBrush(self.add_color)
        new_item.setZValue(10)

        # 复制关键数据：坐标偏移、原始位置等
        new_item.setData(1, item.data(1))  # 位移量
        new_item.setData(10, item.data(10))  # 原始坑位

        if hasattr(item, "pix_overlay"):
            new_item.pix_overlay = item.pix_overlay
            new_item.pix_overlay.setParentItem(new_item)

        # 物理替换
        if item in self.selections:
            idx = self.selections.index(item)
            self.selections[idx] = new_item

        self.scene.removeItem(item)
        self.scene.addItem(new_item)

    def _create_new_rect(self, rect):
        item = QGraphicsRectItem(rect)
        item.setPen(self.add_pen)
        item.setBrush(self.add_color)
        item.setZValue(10)
        self.scene.addItem(item)
        self.selections.append(item)

    def handle_double_click(self, scene_pos, frame_index=None):
        if not self.active:
            return

        # 2. 获取该点下所有的物体
        items_at_point = self.scene.items(scene_pos)

        # 3. 过滤出真正的选区对象
        # 排除 temp_rect，且必须是 selections 列表中的成员
        clicked_selections = [
            i for i in items_at_point if i in self.selections and i != self.temp_rect
        ]

        if clicked_selections:
            self._remove_item(clicked_selections[0], frame_index=frame_index)
        else:
            self.clear_selections(frame_index=frame_index)

            # 关键：手动清理双击产生的那个微小残留
            if self.temp_rect:
                if self.temp_rect.scene():
                    self.scene.removeItem(self.temp_rect)
                self.temp_rect = None

    def clear_selections(
        self, target_frame_data=None, merge_to_bg=True, frame_index=None
    ):
        """清空选区，可选是否合并到背景，可选目标帧索引"""
        if not self.selections:
            return

        for item in self.selections[:]:
            # --- 关键：只有提供了frame_index才合并到背景 ---
            if (
                merge_to_bg
                and hasattr(item, "pix_overlay")
                and item.pix_overlay
                and frame_index is not None
            ):
                # 调用你已有的合并函数，把像素贴回底图的新位置
                self._merge_back_to_bg(
                    item, target_frame_data=target_frame_data, frame_index=frame_index
                )

            if item.scene():
                self.scene.removeItem(item)

        self.selections.clear()
        self.moving_item = None

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

    def _remove_item(self, item, frame_index=None):
        """
        删除单个选区：确保在删除框之前，像素已经稳固地写回底图
        """
        if item in self.selections:
            # 1. 检查是否有移动过的像素贴图层
            if hasattr(item, "pix_overlay") and item.pix_overlay:
                self._merge_back_to_bg(item, frame_index=frame_index)

            # 2. 从管理列表移除
            self.selections.remove(item)

            # 3. 从场景中彻底删除选区及其所有子元素
            if item.scene():
                self.scene.removeItem(item)

    def handle_key_nudge(self, key, is_boost=False):
        """键盘位移：仅操作图元，不触发物理合并"""
        if not self.active:
            return

        # 1. 确定操作对象
        target = self.moving_item
        if not target:
            valid_selections = [s for s in self.selections if s.scene()]
            if valid_selections:
                target = valid_selections[-1]
                # --- 细节：锁定移动目标，防止切换 ---
                self.moving_item = target

        if not target:
            return

        # 2. 【核心修改】确保像素被抠出
        # 注意：_prepare_moving_pixels 内部必须处理好 bg_item 的查找
        if not hasattr(target, "pix_overlay") or target.pix_overlay is None:
            # 第一次移动时保存undo状态
            # 寻找Editor实例并调用save_undo_state
            view = self.scene.views()[0]
            editor = view.parent()
            while editor and not hasattr(editor, "save_undo_state"):
                editor = editor.parent()
            if editor:
                editor.save_undo_state()
            self._prepare_moving_pixels(target)

        # 3. 计算步长
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

        # 计算移动后的位置
        current_pos = target.pos()
        new_x = current_pos.x() + dx
        new_y = current_pos.y() + dy

        # 获取目标对象的边界矩形
        item_rect = target.boundingRect()

        # 计算目标对象在场景中的边界
        # 注意：boundingRect()返回的是相对于对象自身坐标系的矩形
        # 所以需要加上对象的位置来得到场景坐标系中的实际边界
        item_left = new_x + item_rect.left()
        item_top = new_y + item_rect.top()
        item_right = new_x + item_rect.right()
        item_bottom = new_y + item_rect.bottom()

        # 获取背景图作为画布边界（可选）
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

        if bg_item:
            bg_pos = bg_item.pos()
            bg_width = bg_item.pixmap().width()
            bg_height = bg_item.pixmap().height()
            bg_left = bg_pos.x()
            bg_top = bg_pos.y()
            bg_right = bg_pos.x() + bg_width
            bg_bottom = bg_pos.y() + bg_height

        # 计算实际移动距离
        actual_dx = new_x - current_pos.x()
        actual_dy = new_y - current_pos.y()

        if actual_dx != 0 or actual_dy != 0:
            # 执行位移
            target.moveBy(actual_dx, actual_dy)

            # 5. 更新 Data(1) 累计位移量 (这对后续焊死/撤销逻辑很重要)
            curr_offset = target.data(1) or QPointF(0, 0)
            target.setData(1, curr_offset + QPointF(actual_dx, actual_dy))

            # 6. 更新背景遮罩，确保底图上的空洞位置正确
            if bg_item:
                self._update_background_mask(bg_item)

            # 7. 强制刷新，解决部分机器上的残影问题
            self.scene.update()

    def _merge_back_to_bg(self, item, target_frame_data=None, frame_index=None):
        """
        物理合并：将悬浮像素焊死到底图。
        修正：严格限制底图查找范围，防止抓取到已隐藏的原始素材。
        """
        try:
            # 1. 检查 item 是否有效
            if not item or not hasattr(item, "scene"):
                return

            # 2. 检查 item 是否还在场景中
            try:
                if item.scene() is None:
                    return
            except RuntimeError:
                return

            # 3. 寻找场景中的底图图元
            # 增加条件：必须是可见的 (isVisible)！这样就不会抓到裁切后隐藏的原始大图
            bg_item = None
            try:
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
            except RuntimeError:
                return

            if not bg_item:
                return

            # 4. 检查 pix_overlay 是否存在
            if not hasattr(item, "pix_overlay") or not item.pix_overlay:
                return

            # 5. 获取位置和图像信息
            overlay = item.pix_overlay
            try:
                overlay_pix = overlay.pixmap()

                # 获取选区的原始位置和位移量
                orig_rect = item.data(10)  # 原始位置（QRect）
                offset = item.data(1) or QPointF(0, 0)  # 累计位移量

                # 计算最终绘制位置：原始位置 + 位移量
                final_x = orig_rect.left() + offset.x()
                final_y = orig_rect.top() + offset.y()
                local_pos = QPoint(int(final_x), int(final_y))

                current_bg_pix = bg_item.pixmap()
                bg_rect = current_bg_pix.rect()
                overlay_rect = QRect(local_pos, overlay_pix.size())

                # 6. 计算交集区域（只保留画布范围内的部分）
                # 模拟PS效果：结束移动后，超出画布的部分删除
                intersection_rect = bg_rect.intersected(overlay_rect)

                if intersection_rect.isNull():
                    # 如果没有交集，说明完全在画布外，不绘制任何内容
                    return

                # 7. 创建新画布（保持原始画布大小）
                new_bg_pix = QPixmap(current_bg_pix.size())
                new_bg_pix.fill(Qt.GlobalColor.transparent)

                painter = QPainter(new_bg_pix)

                # 绘制原始背景图
                painter.drawPixmap(0, 0, current_bg_pix)

                # 计算覆盖图在背景图上的绘制位置
                draw_pos = QPoint(
                    intersection_rect.left() - overlay_rect.left(),
                    intersection_rect.top() - overlay_rect.top(),
                )

                # 只绘制交集区域的内容（超出画布的部分被裁剪）
                painter.drawPixmap(
                    intersection_rect.topLeft(),
                    overlay_pix,
                    QRect(draw_pos, intersection_rect.size()),
                )
                painter.end()

                # 8. 更新显示（保持原始位置）
                bg_item.setPixmap(new_bg_pix)
                bg_item.setData(99, new_bg_pix.copy())

                # --- 9. 寻找 Editor 实例进行数据同步 ---
                try:
                    view = self.scene.views()[0]
                    editor = view.parent()
                    while editor and not hasattr(editor, "bundle_updated"):
                        editor = editor.parent()

                    if editor:
                        # 确定要更新的帧索引
                        idx = (
                            frame_index
                            if frame_index is not None
                            else editor.frame_list.currentRow()
                        )

                        # 更新 target_frame_data（如果提供）
                        if target_frame_data is not None:
                            if isinstance(target_frame_data, dict):
                                target_frame_data["pixmap"] = new_bg_pix
                            elif hasattr(target_frame_data, "pixmap"):
                                target_frame_data.pixmap = new_bg_pix

                        # 更新 editor.current_frames 中的对应帧
                        if 0 <= idx < len(editor.current_frames):
                            if isinstance(editor.current_frames[idx], dict):
                                editor.current_frames[idx]["pixmap"] = new_bg_pix
                            elif hasattr(editor.current_frames[idx], "pixmap"):
                                editor.current_frames[idx].pixmap = new_bg_pix

                        # 同步更新 AssetBundle 数据
                        if editor.current_bundle and 0 <= idx < len(
                            editor.current_bundle.frames
                        ):
                            editor.current_bundle.frames[idx].pixmap = new_bg_pix

                        # 触发编辑器同步到 AssetBundle 并通知预览面板
                        editor.sync_and_notify()
                except Exception as e:
                    pass

            except Exception as e:
                pass

        except Exception as e:
            pass

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
        except Exception:
            pass

    def _get_valid_selections(self):
        """寻找场景中所有的选区框，增加极致防御，防止 Internal C++ object deleted"""
        valid = []
        new_selections = []

        for item in self.selections:
            try:
                # 尝试调用一个最基础的 C++ 方法，如果对象已删，这里会报 RuntimeError
                if item.scene() is not None:
                    # 如果能走到这，说明对象还活着
                    if not hasattr(item, "is_clone") and item.isVisible():
                        valid.append(item)
                    new_selections.append(item)
            except (RuntimeError, AttributeError):
                # 抓到僵尸对象，直接跳过，这样它就不会出现在 new_selections 里
                continue

        self.selections = new_selections
        return valid

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
        self.active = True
        self.start_point = scene_pos

        modifiers = event.modifiers()
        is_shift = bool(modifiers & Qt.ShiftModifier)
        is_alt_option = bool(modifiers & Qt.AltModifier)

        # 1. 检查是否点击了已有的选区 (仅在无修饰键时进入移动模式)
        valid_items = self._get_valid_selections()
        items_at_point = self.scene.items(scene_pos)
        clicked_selection = next((i for i in items_at_point if i in valid_items), None)

        if clicked_selection and not is_shift and not is_alt_option:
            self.moving_item = clicked_selection
            self.last_move_pos = scene_pos
            return

        # 2. 开始拉新选区
        if event.button() == Qt.LeftButton:
            from PySide6.QtWidgets import QGraphicsRectItem

            self.temp_rect = QGraphicsRectItem()

            if is_alt_option:
                # --- 减选模式 (红色) ---
                self.temp_rect.setPen(self.dash_pen_remove)
                self.temp_rect.setBrush(self.remove_color)
                self.temp_rect.setData(0, "SUBTRACT")
            elif is_shift:
                # --- Shift 加选合并模式 (蓝色 + 标记) ---
                self.temp_rect.setPen(self.add_pen)
                self.temp_rect.setBrush(self.add_color)
                self.temp_rect.setData(0, "MERGE")  # 特殊标记：需要合并
            else:
                # --- 默认创建模式 (蓝色) ---
                self.temp_rect.setPen(self.add_pen)
                self.temp_rect.setBrush(self.add_color)
                self.temp_rect.setData(0, "CREATE")  # 标记：直接创建

            self.temp_rect.setZValue(1000)
            self.scene.addItem(self.temp_rect)

    # def handle_mouse_move(self, event, scene_pos):
    #     if not self.active or self.start_point is None or self.temp_rect is None:
    #         return

    #     # 更新矩形大小
    #     rect = QRectF(self.start_point, scene_pos).normalized()
    #     self.temp_rect.setRect(rect)
    #     # 强制刷新视图
    #     self.scene.update()

    def handle_mouse_release(self, event, scene_pos):
        # 处理移动模式的释放事件
        if self.moving_item and self.last_move_pos is not None:
            # 注意：不再在移动完成后立即合并像素到底图
            # 只在用户明确清除选区时才合并
            self.moving_item = None
            self.last_move_pos = None
            return

        if self.temp_rect is None:
            return

        final_rect = self.temp_rect.rect()
        # 过滤掉过小的点击误触
        if final_rect.width() > 2 and final_rect.height() > 2:
            mode = self.temp_rect.data(0)
            new_path = QPainterPath()
            new_path.addRect(final_rect)

            if mode == "SUBTRACT":
                # --- 减选逻辑 ---
                for item in self.selections[:]:
                    item_path = self._get_item_path(item)
                    if item_path.intersects(new_path):
                        res_path = item_path.subtracted(new_path)
                        if res_path.isEmpty():
                            self._remove_item(item)
                        else:
                            self._update_item_shape(item, res_path)
                # 减选框本身不保留
                self.scene.removeItem(self.temp_rect)

            elif mode == "MERGE":
                # --- 合并逻辑 ---
                merged = False
                for item in self.selections[:]:
                    item_path = self._get_item_path(item)
                    if item_path.intersects(new_path):
                        union_path = item_path.united(new_path)
                        self._update_item_shape(item, union_path)
                        merged = True
                        break

                if not merged:
                    # 如果没合并到旧的，就把这个临时框转正
                    self.selections.append(self.temp_rect)
                    # 关键：不要在这里销毁它，因为它已经是列表的一员了
                else:
                    self.scene.removeItem(self.temp_rect)

            else:  # mode == "CREATE"
                # --- 正常创建：转正临时框 ---
                self.selections.append(self.temp_rect)
                # 注意：此时 temp_rect 已经在场景里了，直接存入列表即可

            # 重要：在存入列表后，我们要切断 temp_rect 的引用，但不能 removeItem
            # 只有那些没被存入 selections 的才需要被 removeItem
            self.temp_rect = None
        else:
            # 太小的框直接删除
            if self.temp_rect.scene():
                self.scene.removeItem(self.temp_rect)
            self.temp_rect = None

        self.start_point = None

    # selection_manager.py 内部

    def _prepare_moving_pixels(self, target_item):
        """将选区内的像素抠出来，变成可移动的贴层，并挖空底图"""
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

        # 1. 取得选区在场景中的对齐矩形
        if isinstance(target_item, QGraphicsRectItem):
            scene_rect = (
                target_item.mapToScene(target_item.rect())
                .boundingRect()
                .toAlignedRect()
            )
        else:
            scene_rect = target_item.sceneBoundingRect().toAlignedRect()

        # 2. 映射到底图局部并抠图
        local_pos = bg_item.mapFromScene(scene_rect.topLeft()).toPoint()
        local_rect = QRect(local_pos, scene_rect.size())
        target_item.setData(10, local_rect)

        crop_pix = bg_item.pixmap().copy(local_rect)
        self._permanently_erase_pixels(bg_item, local_rect)

        # 3. 创建贴层并配置层级
        overlay = ClippedPixmapItem(crop_pix)
        overlay.is_clone = True
        overlay.setParentItem(target_item)
        overlay.set_bg_item(bg_item)  # 设置背景图项，用于实时裁剪

        # --- 核心修复开始 ---
        # 标记子物体强制在父物体（选框）之后（即下方）绘制
        overlay.setFlag(QGraphicsItem.ItemStacksBehindParent, True)

        # 双重保险：设置 ZValue 为负
        overlay.setZValue(-1)
        # 确保父物体（选框）Z值足够高
        target_item.setZValue(2000)
        # --- 核心修复结束 ---

        overlay.setTransformationMode(Qt.FastTransformation)

        if isinstance(target_item, QGraphicsRectItem):
            overlay.setPos(target_item.rect().topLeft())
        else:
            overlay.setPos(target_item.boundingRect().topLeft())

        target_item.pix_overlay = overlay

    def handle_mouse_move(self, event, scene_pos):
        if not self.active or self.start_point is None:
            return

        is_left_button = bool(event.buttons() & Qt.LeftButton)
        modifiers = event.modifiers()
        is_move_cmd = bool(modifiers & (Qt.ControlModifier | Qt.MetaModifier))

        # --- 情况 A: 移动模式 (Command + 鼠标左键拖拽) ---
        if is_left_button and is_move_cmd and self.moving_item:
            if self.last_move_pos is not None:
                if (
                    not hasattr(self.moving_item, "pix_overlay")
                    or self.moving_item.pix_overlay is None
                ):
                    # 第一次移动时保存undo状态
                    # 寻找Editor实例并调用save_undo_state
                    view = self.scene.views()[0]
                    editor = view.parent()
                    while editor and not hasattr(editor, "save_undo_state"):
                        editor = editor.parent()
                    if editor:
                        editor.save_undo_state()
                    self._prepare_moving_pixels(self.moving_item)

                # 核心：计算鼠标在场景中移动的绝对像素差
                delta = scene_pos - self.last_move_pos
                dx, dy = round(delta.x()), round(delta.y())

                if dx != 0 or dy != 0:
                    # 计算移动后的位置
                    current_pos = self.moving_item.pos()
                    new_x = current_pos.x() + dx
                    new_y = current_pos.y() + dy

                    # 获取目标对象的边界矩形
                    item_rect = self.moving_item.boundingRect()

                    # 计算目标对象在场景中的边界
                    # 注意：boundingRect()返回的是相对于对象自身坐标系的矩形
                    # 所以需要加上对象的位置来得到场景坐标系中的实际边界
                    item_left = new_x + item_rect.left()
                    item_top = new_y + item_rect.top()
                    item_right = new_x + item_rect.right()
                    item_bottom = new_y + item_rect.bottom()

                    # 获取背景图作为画布边界（可选）
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

                    if bg_item:
                        bg_pos = bg_item.pos()
                        bg_width = bg_item.pixmap().width()
                        bg_height = bg_item.pixmap().height()
                        bg_left = bg_pos.x()
                        bg_top = bg_pos.y()
                        bg_right = bg_pos.x() + bg_width
                        bg_bottom = bg_pos.y() + bg_height

                    # 计算实际移动距离
                    actual_dx = new_x - current_pos.x()
                    actual_dy = new_y - current_pos.y()

                    if actual_dx != 0 or actual_dy != 0:
                        # 执行位移
                        self.moving_item.moveBy(actual_dx, actual_dy)

                        # 记录累计位移量，用于后期焊死到底图
                        old_off = self.moving_item.data(1) or QPointF(0, 0)
                        self.moving_item.setData(
                            1, old_off + QPointF(actual_dx, actual_dy)
                        )

                        # 更新背景遮罩，确保底图上的空洞位置正确
                        if bg_item:
                            self._update_background_mask(bg_item)

                        # 关键：更新 last_move_pos 时要减去舍入误差，确保下一次计算精准
                        self.last_move_pos += QPointF(actual_dx, actual_dy)
                        self.scene.update()

        # --- 情况 B: 默认拉框模式 ---
        if self.temp_rect and is_left_button:
            rect = QRectF(self.start_point, scene_pos).normalized()
            # 同样对拉框进行像素对齐
            self.temp_rect.setRect(rect.toAlignedRect())
            self.scene.update()

    # selection_manager.py 内部
    def force_reset_internal(self):
        """
        极致安全的重置：只清空引用，不访问任何可能已销毁的 C++ 对象。
        专门用于场景切换或资源重新加载时。
        """
        self.selections = []
        self.moving_item = None
        self.temp_rect = None
        self.start_point = None
        self.last_move_pos = None
