import os
import cv2
import numpy as np
import time
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt,QPointF
from PySide6.QtGui import QPixmap,QPainter

class SliceLogic:
    def on_slice_clicked(self):
        """
        最终优化版：
        1. 无论图片多少，全过程共用一个全局进度条。
        2. 进度条位置绝对固定，不抖动，不换行。
        3. 还原完整的打印信息流。
        """
        if not self.asset_files:
            self.add_log("⚠️ 待处理列表为空", "#f38ba8")
            return

        target_files = []
        for f in self.asset_files:
            # 1. 必须是文件且后缀正确
            if os.path.isfile(f) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                # 2. 关键：判断该文件的父目录是否已经是“已导入的文件夹”
                # 如果父目录在 selected_folders 中，说明它是文件夹的一部分，不应该被单独裁切
                parent_dir = os.path.dirname(f)
                if parent_dir in self.selected_folders:
                    continue 
                target_files.append(f)
        
        if not target_files:
            self.add_log("⚠️ 列表中没有可裁切的单帧图片", "#f38ba8")
            return

        total_imgs = len(target_files)
        new_folders_summary = [] 

        
        # --- 2. 打印总进度标题 ---
        self.add_log("-> 智能裁切", "#a6e3a1")

        # --- 3. 初始进度条占位 (0.0%) ---
        self.update_fixed_bar(0, is_init=True)

        for i, img_path in enumerate(target_files):
            img_name = os.path.basename(img_path)
            name_base = os.path.splitext(img_name)[0]
            output_dir = os.path.join(os.path.dirname(img_path), name_base)

            # 计算本阶段进度范围
            start_p = (i / total_imgs) * 100
            end_p = ((i + 1) / total_imgs) * 100
            
            # 模拟处理前的“滑行”动画，增强视觉反馈
            steps = 10
            for step in range(1, steps + 1):
                anim_p = start_p + (end_p - start_p) * (step / steps) * 0.9
                self.update_fixed_bar(anim_p, is_init=False)
                QApplication.processEvents()
                time.sleep(0.01)

            # 执行实际 OpenCV 逻辑
            try:
                self.run_actual_slice(img_path, output_dir, name_base)
                
                # 每张图处理完，将进度推到该阶段的满额
                self.update_fixed_bar(end_p, is_init=False)
                
                if output_dir not in self.selected_folders:
                    self.selected_folders.append(output_dir)
                    new_folders_summary.append(name_base)
            except Exception as e:
                self.add_log(f"-> 错误: {img_name}", "#f38ba8")

        # --- 4. 最终打印汇总信息 ---
        self.add_log("-> 处理完成", "#a6e3a1")
        for folder_name in new_folders_summary:
            self.add_log(f"-> 文件夹: {folder_name}", "#89b4fa")

    def update_fixed_bar(self, percent, is_init=False):
        """
        绝对静止进度条函数（你认可的逻辑）
        """
        bar_width = 20  # 稍微拉长一点更美观
        filled_count = int(bar_width * (percent / 100))
        empty_count = bar_width - filled_count
        
        # 使用 ■ 和 □ 确保视觉等宽
        # bar_content = "■" * filled_count + "□" * empty_count
        # bar_content = "■" * filled_count + "━" * empty_count
        bar_content = "━" * filled_count + "─" * empty_count
        # bar_content = "█" * filled_count + "░" * empty_count
        # bar_content = "■" * filled_count + "·" * empty_count
        
        # 强制百分比占据固定 6 位宽度
        progress_text = f"-> {bar_content} [{percent:>6.1f}%]"
        
        # 只有第一次调用时 replace_last 为 False，之后全部原地替换
        self.add_log(progress_text, "#74c7ec", replace_last=not is_init)

    def run_actual_slice(self, img_path, output_dir, name_base):
        import cv2, os
        import numpy as np
        from PIL import Image

        # 1. 读取
        with open(img_path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            src = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
        if src is None: return
        alpha = src[:, :, 3] if src.shape[2] == 4 else cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)

        # 2. 闭运算：连接组件
        gap_threshold = 3 
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (gap_threshold, gap_threshold))
        closed_alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel)

        # 3. 寻找轮廓
        contours, _ = cv2.findContours(closed_alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: return

        raw_rects = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 2 or h < 2: continue
            roi_alpha = alpha[y:y+h, x:x+w]
            coords = cv2.findNonZero(roi_alpha)
            if coords is not None:
                ix, iy, iw, ih = cv2.boundingRect(coords)
                raw_rects.append([x + ix, y + iy, iw, ih])

        if not raw_rects: return

        # --- 4. 【核心改进】动态行识别排序逻辑 ---
        # 首先，按垂直中心点 center_y 绝对排序
        raw_rects.sort(key=lambda r: (r[1] + r[3]/2))

        final_sorted_rects = []
        current_row = []
        if raw_rects:
            # 取第一个元素的中心 Y 作为起始行的基准
            last_center_y = raw_rects[0][1] + raw_rects[0][3]/2
            # 动态行高阈值：取该序列平均高度的 60%
            avg_h = sum(r[3] for r in raw_rects) / len(raw_rects)
            row_threshold = avg_h * 0.6

            for rect in raw_rects:
                curr_center_y = rect[1] + rect[3]/2
                # 如果当前块的中心与上一行的中心距离在阈值内，归为同一行
                if abs(curr_center_y - last_center_y) < row_threshold:
                    current_row.append(rect)
                else:
                    # 距离太远，开启新的一行。开启前，对旧行按 X 轴排序
                    current_row.sort(key=lambda r: r[0])
                    final_sorted_rects.extend(current_row)
                    # 重置行信息
                    current_row = [rect]
                    last_center_y = curr_center_y
            
            # 处理最后一行
            current_row.sort(key=lambda r: r[0])
            final_sorted_rects.extend(current_row)

        # 5. 画布与保存逻辑
        max_w = max(r[2] for r in final_sorted_rects)
        max_h = max(r[3] for r in final_sorted_rects)
        padding = 10
        side = max(max_w, max_h) + padding * 2
        if side % 2 != 0: side += 1
        fixed_bottom_gap = 6 

        os.makedirs(output_dir, exist_ok=True)
        pil_img = Image.open(img_path).convert("RGBA")

        for idx, (x, y, w, h) in enumerate(final_sorted_rects):
            crop = pil_img.crop((x, y, x + w, y + h))
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            offset_x = (side - w) // 2
            offset_y = side - h - fixed_bottom_gap
            offset_y = max(0, offset_y)
            canvas.paste(crop, (offset_x, offset_y), crop)
            canvas.save(os.path.join(output_dir, f"{name_base}_{idx:02d}.png"))
    
    def run_manual_slice(self, bg_item, selection_rects):
        """
        根据手动选区进行裁切，但不保存文件，只返回图像数据
        """
        frames_data = []
        full_pixmap = bg_item.pixmap()
        
        # 1. 确定统一的画布大小 (参考你之前的 side 计算逻辑)
        max_w = max(r.width() for r in selection_rects)
        max_h = max(r.height() for r in selection_rects)
        padding = 10
        side = max(max_w, max_h) + padding * 2
        if side % 2 != 0: side += 1
        fixed_bottom_gap = 6

        for rect in selection_rects:
            # 从底图抠图
            crop = full_pixmap.copy(rect)
            
            # 创建标准帧画布 (居中对齐)
            canvas = QPixmap(side, side)
            canvas.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(canvas)
            offset_x = (side - rect.width()) // 2
            offset_y = side - rect.height() - fixed_bottom_gap
            painter.drawPixmap(offset_x, max(0, offset_y), crop)
            painter.end()
            
            frames_data.append({
                "pixmap": canvas,
                "rect": rect, # 记录原始位置，方便以后微调
                "offset": QPointF(offset_x, offset_y)
            })
            
        return frames_data

    def run_auto_slice_to_preview(self, q_pixmap):
        """
        自动识别算法：将 QPixmap 转换为 OpenCV 处理，返回预览用的帧数据列表
        """
        # 1. QPixmap 转 OpenCV (通过 bytes 中转最稳健)
        from PySide6.QtCore import QBuffer, QIODevice
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        q_pixmap.save(buffer, "PNG")
        file_bytes = np.frombuffer(buffer.data(), dtype=np.uint8)
        src = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
        
        if src is None: return []
        
        # 2. 复用你之前的 OpenCV 识别逻辑 (闭运算 + 轮廓提取)
        alpha = src[:, :, 3] if src.shape[2] == 4 else cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
        gap_threshold = 3 
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (gap_threshold, gap_threshold))
        closed_alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed_alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        raw_rects = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 2 or h < 2: continue
            roi_alpha = alpha[y:y+h, x:x+w]
            coords = cv2.findNonZero(roi_alpha)
            if coords is not None:
                ix, iy, iw, ih = cv2.boundingRect(coords)
                # 存为 QRect 格式方便后续统一处理
                from PySide6.QtCore import QRect
                raw_rects.append(QRect(x + ix, y + iy, iw, ih))

        if not raw_rects: return []

        # 3. 复用你之前的行排序逻辑
        # 注意：这里 raw_rects 已经是 QRect 对象，访问属性用 .y() .height() 等
        raw_rects.sort(key=lambda r: (r.y() + r.height()/2))
        
        final_sorted_rects = []
        current_row = []
        avg_h = sum(r.height() for r in raw_rects) / len(raw_rects)
        row_threshold = avg_h * 0.6
        
        last_center_y = raw_rects[0].y() + raw_rects[0].height()/2
        for r in raw_rects:
            curr_center_y = r.y() + r.height()/2
            if abs(curr_center_y - last_center_y) < row_threshold:
                current_row.append(r)
            else:
                current_row.sort(key=lambda rect: rect.x())
                final_sorted_rects.extend(current_row)
                current_row = [r]
                last_center_y = curr_center_y
        current_row.sort(key=lambda rect: rect.x())
        final_sorted_rects.extend(current_row)

        # 4. 生成统一格式的预览数据 (复用 manual_slice 的画布逻辑)
        return self.run_manual_slice(type('obj', (object,), {'pixmap': lambda: q_pixmap}), final_sorted_rects)
    
    def save_sliced_sprites(self, source_path, pixmaps):
        """
        将编辑器切好的 QPixmap 列表物理保存到磁盘
        """
        if not source_path or not pixmaps:
            return None

        # 1. 构造输出文件夹 (原文件名 + _sliced)
        img_name = os.path.basename(source_path)
        name_base = os.path.splitext(img_name)[0]
        output_dir = os.path.join(os.path.dirname(source_path), f"{name_base}")
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 2. 遍历保存
        for idx, pixmap in enumerate(pixmaps):
            save_name = f"{name_base}_{idx:02d}.png"
            save_path = os.path.join(output_dir, save_name)
            pixmap.save(save_path, "PNG")
            
        return output_dir