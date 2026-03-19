import os
import uuid
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QRect

class FrameData:
    """标准单帧模型"""
    def __init__(self, pixmap: QPixmap, rect: QRect, name: str = ""):
        self.pixmap = pixmap  # 裁切后的图像
        self.rect = rect      # 原始坐标信息 (x, y, w, h)
        self.name = name

class AssetBundle:
    """标准资源包模型"""
    def __init__(self, name: str):
        self.name = name
        self.path = ""               # 磁盘来源路径
        self.is_memory = False       # 标记是否为编辑器直接生成的内存数据
        self.original_pixmap = None  # 原始未裁切大图
        
        self.frames = []             # 存储 FrameData 对象列表
        self.segments = []           # 片段定义: [{"name": "loop", "start": 1, "end": 8}]

    @property
    def frame_count(self):
        return len(self.frames)

    def get_preview_list(self, start=1, end=None):
        """工具方法：获取用于播放的 Pixmap 序列"""
        if end is None: end = self.frame_count
        # 内部处理 1-base 索引到 list 0-base 的转换
        return [f.pixmap for f in self.frames[start-1:end]]

    def __repr__(self):
        return f"<AssetBundle: {self.name} | Frames: {self.frame_count} | Memory: {self.is_memory}>"