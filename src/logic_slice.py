import os
import cv2
import numpy as np
from PIL import Image
from PySide6.QtWidgets import QApplication

class SliceLogic:
    def on_slice_clicked(self):
        """
        100% 还原原版打印顺序：
        - 先打印一个总的 '智能裁切 ->'
        - 循环内只更新进度条
        """
        if not self.asset_files:
            self.add_log("- ⚠️ 待处理列表为空，请先导入图片素材", "#f38ba8")
            return

        target_files = [f for f in self.asset_files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))]
        if not target_files:
            return

        total_imgs = len(target_files)
        new_folders_summary = [] 

        # --- 核心还原 1: 标题只打印一次 ---
        self.add_log("- 智能裁切 ->", "#89b4fa")

        for i, img_path in enumerate(target_files):
            try:
                img_name = os.path.basename(img_path)
                name_base = os.path.splitext(img_name)[0]
                output_dir = os.path.join(os.path.dirname(img_path), name_base)

                # --- 图像处理逻辑开始 ---
                with open(img_path, "rb") as f:
                    file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
                    src = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)

                if src is None: continue
                
                alpha = src[:, :, 3] if src.shape[2] == 4 else cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
                contours, _ = cv2.findContours(alpha, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if not contours: continue

                max_w, max_h = 0, 0
                valid_rects = []
                for cnt in contours:
                    x, y, w, h = cv2.boundingRect(cnt)
                    if w < 2 or h < 2: continue 
                    max_w, max_h = max(max_w, w), max(max_h, h)
                    valid_rects.append((x, y, w, h))

                if not valid_rects: continue

                padding = 8 
                side_length = max(max_w, max_h) + padding
                if side_length % 2 != 0: side_length += 1
                target_size = (side_length, side_length)

                valid_rects.sort(key=lambda r: (r[1], r[0]))
                os.makedirs(output_dir, exist_ok=True)
                pil_img = Image.open(img_path).convert("RGBA")
                
                for idx, (x, y, w, h) in enumerate(valid_rects):
                    sprite_crop = pil_img.crop((x, y, x + w, y + h))
                    final_canvas = Image.new("RGBA", target_size, (0, 0, 0, 0))
                    offset_x, offset_y = (side_length - w) // 2, (side_length - h) // 2
                    final_canvas.paste(sprite_crop, (offset_x, offset_y), sprite_crop)
                    final_canvas.save(os.path.join(output_dir, f"{name_base}_{idx:02d}.png"))
                # --- 图像处理逻辑结束 ---

                # --- 核心还原 2: 进度条 (仅输出进度) ---
                current_idx = i + 1
                percent = current_idx / total_imgs
                bar_width = 20 
                filled = int(bar_width * percent)
                # 使用原版字符：■ 和 ∙
                bar_content = "■" * filled + "∙" * (bar_width - filled)
                # 严格匹配空格: - [bar] [ percent]
                progress_info = f"- {bar_content} [{percent*100:>5.1f}%]"
                self.add_log(progress_info, "#74c7ec") 

                if output_dir not in self.selected_folders:
                    self.selected_folders.append(output_dir)
                    new_folders_summary.append(name_base)

                QApplication.processEvents()

            except Exception as e:
                self.add_log(f"- 错误: {os.path.basename(img_path)}", "#f38ba8")

        # --- 汇总输出 ---
        self.add_log("- 处理完成", "#a6e3a1")
        for folder_name in new_folders_summary:
            self.add_log(f"- 文件夹 : {folder_name}", "#89b4fa")