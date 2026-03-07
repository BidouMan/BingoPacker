import os
import json
import zipfile
import hashlib

class ExportLogic:
    def on_export_sprite3(self):
        """
        完全还原原始版本的 .sprite3 导出逻辑：
        1. 遍历文件夹。
        2. 计算每张图片的 MD5。
        3. 压缩包内图片以 MD5 命名。
        4. project.json 严格遵循 Scratch 角色对象结构。
        """
        if not self.selected_folders:
            self.add_log("⚠️ 请先导入资源文件夹", "#ff5555")
            return

        for folder_path in self.selected_folders:
            folder_name = os.path.basename(folder_path)
            save_path = f"{folder_path}.sprite3"

            try:
                valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
                files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_exts)]
                files.sort()
                if not files: continue

                with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    costumes = []
                    
                    for f_name in files:
                        file_path = os.path.join(folder_path, f_name)
                        
                        # --- 核心还原点 1: 计算真正的 MD5 ---
                        with open(file_path, 'rb') as f:
                            md5_hash = hashlib.md5(f.read()).hexdigest()
                        
                        ext = os.path.splitext(f_name)[1].lower().replace('.', '')
                        md5_filename = f"{md5_hash}.{ext}"
                        
                        # --- 核心还原点 2: 构建造型数据 ---
                        costumes.append({
                            "name": os.path.splitext(f_name)[0],
                            "bitmapResolution": 2, # 还原为 sprite.json 中的 2
                            "dataFormat": ext,
                            "assetId": md5_hash,
                            "md5ext": md5_filename,
                            "rotationCenterX": 0, # 这里根据需要可还原算法，默认0
                            "rotationCenterY": 0
                        })
                        
                        # --- 核心还原点 3: 压缩包内的文件必须用 MD5 命名 ---
                        zipf.write(file_path, md5_filename)

                    # --- 核心还原点 4: 严格对齐 sprite.json 结构 ---
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
                    
                    # 注意：有些版本的 Scratch 需要 project.json 包裹 targets
                    # 但根据你提供的 sprite.json，它是单角色导出的标准结构
                    zipf.writestr("sprite.json", json.dumps(sprite_data, indent=4))

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
                valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
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