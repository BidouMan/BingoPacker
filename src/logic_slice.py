import os
import cv2
import numpy as np
import time
from PIL import Image
from PySide6.QtWidgets import QApplication

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

        target_files = [f for f in self.asset_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
        if not target_files:
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
        """保持原有的 OpenCV 逻辑"""
        with open(img_path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            src = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
        if src is None: return
        alpha = src[:, :, 3] if src.shape[2] == 4 else cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
        contours, _ = cv2.findContours(alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours: return
        valid_rects = []
        max_w, max_h = 0, 0
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 2 or h < 2: continue
            max_w, max_h = max(max_w, w), max(max_h, h)
            valid_rects.append((x, y, w, h))
        side = max(max_w, max_h) + 8
        if side % 2 != 0: side += 1
        valid_rects.sort(key=lambda r: (r[1], r[0]))
        os.makedirs(output_dir, exist_ok=True)
        pil_img = Image.open(img_path).convert("RGBA")
        for idx, (x, y, w, h) in enumerate(valid_rects):
            crop = pil_img.crop((x, y, x + w, y + h))
            canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            canvas.paste(crop, ((side - w) // 2, (side - h) // 2), crop)
            canvas.save(os.path.join(output_dir, f"{name_base}_{idx:02d}.png"))