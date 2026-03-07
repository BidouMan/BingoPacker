import os
import json
import zipfile
import hashlib
from PIL import Image

class ExportLogic:
    def on_export_sprite3(self):
        """
        修正版：增加 SVG 兼容支持，动态计算 Scratch 锚点
        """
        if not self.selected_folders:
            self.add_log("⚠️ 请先导入资源文件夹", "#ff5555")
            return

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
                        ext = os.path.splitext(f_name)[1].lower().replace('.', '')
                        
                        # --- 核心修复：分流处理 SVG 和位图 ---
                        if ext == 'svg':
                            # SVG 默认分辨率为 1，锚点通常设为 0 (Scratch 自动处理矢量中心)
                            bitmap_res = 1
                            center_x, center_y = 0, 0
                        else:
                            # 位图分辨率通常为 2，使用 PIL 获取宽高计算中心
                            bitmap_res = 2
                            with Image.open(file_path) as img:
                                width, height = img.size
                            center_x = width / 2
                            center_y = height / 2

                        # 计算 MD5
                        with open(file_path, 'rb') as f:
                            file_data = f.read()
                            md5_hash = hashlib.md5(file_data).hexdigest()
                        
                        md5_filename = f"{md5_hash}.{ext}"
                        
                        costumes.append({
                            "name": os.path.splitext(f_name)[0],
                            "bitmapResolution": bitmap_res, 
                            "dataFormat": ext,
                            "assetId": md5_hash,
                            "md5ext": md5_filename,
                            "rotationCenterX": center_x, 
                            "rotationCenterY": center_y
                        })
                        
                        # 将文件存入压缩包，名字改为 MD5 名
                        zipf.write(file_path, md5_filename)

                    # 构造 sprite.json
                    sprite_data = {
                        "isStage": False,
                        "name": folder_name,
                        # 增加 segments 字段，确保导入 AssetTree 时显示“动画”而非 0-10
                        "segments": [{"name": "动画", "start": 1, "end": len(files)}], 
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
                    
                    zipf.writestr("sprite.json", json.dumps(sprite_data, indent=4, ensure_ascii=False))

                self.add_log(f"-> 成功导出 .sprite3: {folder_name}", "#E48E51")
            except Exception as e:
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
                    config = {
                            "name": folder_name, 
                            "count": len(files), 
                            "frames": files,
                            "segments": [{"name": "动画", "start": 1, "end": len(files)}] # 新增：默认片段
                        }
                    
                    zipf.writestr("config.json", json.dumps(config, indent=4))
                    for f_name in files:
                        zipf.write(os.path.join(folder_path, f_name), f_name)
                self.add_log(f"-> 成功导出 .bgs: {folder_name}", "#5CD59B")
            except Exception as e:
                self.add_log(f"⚠️ 导出失败: {str(e)}", "#ff5555")