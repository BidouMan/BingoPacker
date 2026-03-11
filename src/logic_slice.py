import os
import cv2
import numpy as np
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF, QBuffer, QIODevice
from PySide6.QtGui import QPixmap, QPainter
from PIL import Image

from .asset_manager import AssetManager
from .asset_model import FrameData

class SliceLogic:
    # ==========================================
    # 1. 业务逻辑层：批量智能裁切 (当前主要使用)
    # ==========================================
    def on_slice_clicked(self):
        manager = AssetManager()
        asset_names = manager.list_assets()
        target_bundles = [manager.get_asset(n) for n in asset_names 
                         if manager.get_asset(n) and len(manager.get_asset(n).frames) == 1 
                         and not manager.get_asset(n).is_memory]

        if not target_bundles:
            self.add_log("⚠️ 仓库中没有符合裁切条件的单帧资源", "#f38ba8")
            return

        total_assets = len(target_bundles)
        # 用于存放任务执行中的日志，最后统一打印
        summary_logs = []
        
        # 1. 打印标题
        self.add_log("-> 智能裁切", "#a6e3a1")
        
        # 2. 初始进度条占位
        self.update_fixed_bar(0, is_init=True)

        for i, bundle in enumerate(target_bundles):
            start_p = (i / total_assets) * 100
            end_p = ((i + 1) / total_assets) * 100
            
            # --- 3. 模拟滑行动画 ---
            steps = 10
            for step in range(1, steps + 1):
                anim_p = start_p + (end_p - start_p) * (step / steps) * 0.9
                self.update_fixed_bar(anim_p, is_init=False)
                QApplication.processEvents()
                time.sleep(0.01)

            try:
                # 执行裁切逻辑
                sliced_pixmaps = self._execute_core_slice_algorithm(bundle.path)
                if sliced_pixmaps:
                    # 物理保存与数据更新
                    output_dir = os.path.join(os.path.dirname(bundle.path), bundle.name)
                    self._physical_save_to_disk(output_dir, bundle.name, sliced_pixmaps)
                    
                    # 关键：暂存日志，不立即打印
                    summary_logs.append((f"-> {bundle.name} 裁切完成: {len(sliced_pixmaps)} 帧", "#89b4fa"))
                
                # 更新当前进度条到阶段满额 (原地替换)
                self.update_fixed_bar(end_p, is_init=False)
                QApplication.processEvents()
                
            except Exception as e:
                summary_logs.append((f"-> 错误 [{bundle.name}]: {str(e)}", "#f38ba8"))
                self.update_fixed_bar(end_p, is_init=False)

        # --- 4. 任务全部结束后的操作 ---
        # 此时进度条已到 100%，且就在“智能裁切”下方
        self.add_log("-> 处理完成", "#a6e3a1")
        
        # 5. 最后统一打印汇总结果
        for msg, color in summary_logs:
            self.add_log(msg, color)

        # 刷新 UI 树
        if hasattr(self.preview_panel.asset_tree, 'refresh_from_manager'):
            self.preview_panel.asset_tree.refresh_from_manager()

    # ==========================================
    # 2. 核心算法层：私有化封装 (共用逻辑)
    # ==========================================
    def _execute_core_slice_algorithm(self, img_path):
        """
        从原 run_actual_slice 提取的 OpenCV 识别核心逻辑
        """
        with open(img_path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            src = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
        if src is None: return []

        alpha = src[:, :, 3] if src.shape[2] == 4 else cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        rects = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 2 or h < 2: continue
            roi = alpha[y:y+h, x:x+w]
            pts = cv2.findNonZero(roi)
            if pts is not None:
                ix, iy, iw, ih = cv2.boundingRect(pts)
                rects.append([x + ix, y + iy, iw, ih])

        if not rects: return []

        # 动态行排序逻辑
        rects.sort(key=lambda r: (r[1] + r[3]/2))
        avg_h = sum(r[3] for r in rects) / len(rects)
        row_limit = avg_h * 0.6
        final_rects, current_row = [], []
        last_y = rects[0][1] + rects[0][3]/2

        for r in rects:
            if abs((r[1] + r[3]/2) - last_y) < row_limit:
                current_row.append(r)
            else:
                current_row.sort(key=lambda x: x[0])
                final_rects.extend(current_row)
                current_row, last_y = [r], (r[1] + r[3]/2)
        current_row.sort(key=lambda x: x[0])
        final_rects.extend(current_row)

        # 画布居中与导出逻辑
        max_dim = max(max(r[2] for r in final_rects), max(r[3] for r in final_rects)) + 20
        side = max_dim + (1 if max_dim % 2 != 0 else 0)
        
        pix_list = []
        full_pix = QPixmap(img_path)
        for x, y, w, h in final_rects:
            canvas = QPixmap(side, side)
            canvas.fill(Qt.GlobalColor.transparent)
            p = QPainter(canvas)
            p.drawPixmap((side - w) // 2, max(0, side - h - 6), full_pix.copy(x, y, w, h))
            p.end()
            pix_list.append(canvas)
        return pix_list

    def _physical_save_to_disk(self, output_dir, name_base, pixmaps):
        os.makedirs(output_dir, exist_ok=True)
        for idx, pix in enumerate(pixmaps):
            pix.save(os.path.join(output_dir, f"{name_base}_{idx:02d}.png"), "PNG")

    # ==========================================
    # 3. 参考保留层：ManualEditor 专用 (暂时保留)
    # ==========================================
    def run_manual_slice(self, bg_item, selection_rects):
        """
        保留参考：根据手动选区进行裁切
        """
        frames_data = []
        full_pixmap = bg_item.pixmap()
        max_w = max(r.width() for r in selection_rects)
        max_h = max(r.height() for r in selection_rects)
        side = max(max_w, max_h) + 20
        if side % 2 != 0: side += 1

        for rect in selection_rects:
            canvas = QPixmap(side, side)
            canvas.fill(Qt.GlobalColor.transparent)
            painter = QPainter(canvas)
            ox, oy = (side - rect.width()) // 2, max(0, side - rect.height() - 6)
            painter.drawPixmap(ox, oy, full_pixmap.copy(rect))
            painter.end()
            frames_data.append({"pixmap": canvas, "rect": rect, "offset": QPointF(ox, oy)})
        return frames_data

    def run_auto_slice_to_preview(self, q_pixmap):
        """
        编辑器内的自动识别预览：将 QPixmap 转为 OpenCV 处理并返回帧数据
        """
        # 1. 将 PySide 的 QPixmap 转换为 OpenCV 格式 (通过临时 buffer)
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        q_pixmap.save(buffer, "PNG")
        file_bytes = np.frombuffer(buffer.data(), dtype=np.uint8)
        src = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
        
        if src is None: return []

        # 2. 调用已有的核心算法识别选区
        # 我们需要临时将这个识别逻辑提取出来，或者直接在这里复写
        # 这里为了演示，直接调用核心算法返回 pixmap 列表
        # 注意：你需要确保 _execute_core_slice_algorithm 的逻辑能处理内存图片
        # 实际上建议直接把 _execute_core_slice_algorithm 里的识别部分抽离出来
        
        # 简单实现逻辑：
        pix_list = self._execute_core_slice_algorithm_from_image(src, q_pixmap)
        
        # 3. 封装为 ManualEditor 需要的格式 [{"pixmap": ..., "rect": ...}]
        frames_data = []
        for pix in pix_list:
            frames_data.append({
                "pixmap": pix,
                "rect": pix.rect() # 自动裁切通常已经处理了 offset
            })
        return frames_data

    def _execute_core_slice_algorithm_from_image(self, src, full_pix):
        """核心算法：输入 opencv 图像，输出裁切后的 QPixmap 列表"""
        # 这里直接复用你 logic_slice.py 中第 90-135 行的逻辑
        # ... (此处省略重复的 contours/rects 排序和 canvas 绘制代码) ...
        # 确保最后返回的是 pix_list
        return pix_list 

    def update_fixed_bar(self, percent, is_init=False):
        bar_width = 20
        filled_count = int(bar_width * (percent / 100))
        bar_content = "━" * filled_count + "─" * (bar_width - filled_count)
        progress_text = f"-> {bar_content} [{percent:>6.1f}%]"
        
        # 只有第一次调用时 replace_last 为 False，之后全部原地替换最后一行
        self.add_log(progress_text, "#74c7ec", replace_last=not is_init)