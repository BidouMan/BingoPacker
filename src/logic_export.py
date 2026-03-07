import os
import json
import zipfile
import hashlib
from PIL import Image

class ExportLogic:
    def on_export_sprite3(self):
        """
        修正版：增加 Image 导入支持，动态计算 Scratch 锚点
        """
        if not self.selected_folders:
            self.add_log("⚠️ 请先导入资源文件夹", "#ff5555")
            return

        # 这里的 margin 必须和 logic_slice.py 中的保持一致，确保脚着地
        bottom_margin = 4 

        for folder_path in self.selected_folders:
            folder_name = os.path.basename(folder_path)
            save_path = f"{folder_path}.sprite3"

            try:
                valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.svg')
                files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_exts)]
                files.sort()
                if not files: continue

                with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    costumes = []
                    
                    for f_name in files:
                        file_path = os.path.join(folder_path, f_name)
                        
                        # --- 修复点：通过 PIL 获取图片真实宽高 ---
                        with Image.open(file_path) as img:
                            width, height = img.size
                        
                        # 计算锚点：水平中心，垂直脚底
                        center_x = width / 2
                        center_y = height/ 2

                        with open(file_path, 'rb') as f:
                            md5_hash = hashlib.md5(f.read()).hexdigest()
                        
                        ext = os.path.splitext(f_name)[1].lower().replace('.', '')
                        md5_filename = f"{md5_hash}.{ext}"
                        
                        costumes.append({
                            "name": os.path.splitext(f_name)[0],
                            "bitmapResolution": 2, 
                            "dataFormat": ext,
                            "assetId": md5_hash,
                            "md5ext": md5_filename,
                            # 动态写入计算出的锚点
                            "rotationCenterX": center_x, 
                            "rotationCenterY": center_y
                        })
                        
                        zipf.write(file_path, md5_filename)

                    sprite_data = {
                        "isStage": False,
                        "name": folder_name,
                        "variables": {},
                        "lists": {},
                        "broadcasts": {},
                        "blocks": {},
                        "comments": {},
                        "currentCostume": 0,
                        "costumes": costumes,
                        "sounds": [],
                        "volume": 100,
                        "visible": True,
                        "x": 0,
                        "y": 0,
                        "size": 100,
                        "direction": 90,
                        "draggable": False,
                        "rotationStyle": "all around"
                    }
                    
                    zipf.writestr("sprite.json", json.dumps(sprite_data, indent=4))

                self.add_log(f"-> 成功导出 .sprite3: {folder_name}", "#E48E51")
            except Exception as e:
                # 捕获异常并在控制台输出
                self.add_log(f"⚠️ 导出失败: {str(e)}", "#ff5555")

    def on_export_bgs(self):
        """BGS 保持原样，因为它不需要 MD5 转换"""
        if not self.selected_folders:
            self.add_log("⚠️ 请先导入资源文件夹", "#ff5555")
            return

        for folder_path in self.selected_folders:
            folder_name = os.path.basename(folder_path)
            save_path = f"{folder_path}.bgs"
            try:
                valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.webp','.svg')
                files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_exts)]
                files.sort()
                with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    config = {"name": folder_name, 
                              "count": len(files), 
                              "frames": files}
                    
                    zipf.writestr("config.json", json.dumps(config, indent=4))
                    for f_name in files:
                        zipf.write(os.path.join(folder_path, f_name), f_name)
                self.add_log(f"-> 成功导出 .bgs: {folder_name}", "#5CD59B")
            except Exception as e:
                self.add_log(f"⚠️ 导出失败: {str(e)}", "#ff5555")