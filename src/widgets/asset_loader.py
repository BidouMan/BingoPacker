import os
import zipfile
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import QRect

class AssetLoader:
    @staticmethod
    def load_resource(file_path):
        """
        统一加载入口：自动识别后缀并返回帧列表
        返回格式: [{"pixmap": QPixmap, "rect": QRect, "name": str}, ...]
        """
        if not os.path.exists(file_path):
            return []

        ext = file_path.lower()
        if ext.endswith(('.bgs', '.sprite3')):
            return AssetLoader._load_from_zip(file_path)
        elif ext.endswith(('.png', '.jpg', '.jpeg', '.bmp')):
            return AssetLoader._load_single_image(file_path)
        return []

    @staticmethod
    def _load_from_zip(file_path):
        """处理压缩包格式 (.bgs / .sprite3)"""
        frames = []
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                # 过滤并排序图片
                image_names = [
                    n for n in zf.namelist() 
                    if n.lower().endswith(('.png', '.jpg', '.jpeg')) 
                    and not n.startswith('__MACOSX') # 排除Mac自动生成的垃圾文件
                ]
                # 简单自然排序
                image_names.sort(key=lambda x: len(x)) 
                image_names.sort()

                for name in image_names:
                    with zf.open(name) as f:
                        data = f.read()
                    
                    q_img = QImage.fromData(data)
                    if not q_img.isNull():
                        pix = QPixmap.fromImage(q_img)
                        frames.append({
                            "pixmap": pix,
                            "rect": QRect(0, 0, pix.width(), pix.height()),
                            "name": name
                        })
            return frames
        except Exception as e:
            print(f"AssetLoader: 解压失败 {file_path} -> {e}")
            return []

    @staticmethod
    def _load_single_image(file_path):
        """处理单张常规图片"""
        pix = QPixmap(file_path)
        if not pix.isNull():
            return [{
                "pixmap": pix,
                "rect": QRect(0, 0, pix.width(), pix.height()),
                "name": os.path.basename(file_path)
            }]
        return []