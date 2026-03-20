import os
import re
import json
import zipfile
from PySide6.QtGui import QPixmap


# 这里的导入根据你的项目结构微调，建议使用绝对导入
from .asset_model import AssetBundle, FrameData


class AssetManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AssetManager, cls).__new__(cls)
            cls._instance._storage = {}
        return cls._instance

    # --- 基础管理功能 ---
    def register_asset(self, bundle: AssetBundle, auto_rename=True):
        """
        将资源注册到仓库中。
        :param auto_rename: 如果名字冲突，是否自动重命名 (例如: 马里奥 -> 马里奥_2)
        """
        if not bundle:
            return

        if auto_rename:
            unique_name = self.get_unique_name(bundle.name)
            if unique_name != bundle.name:
                bundle.name = unique_name

        self._storage[bundle.name] = bundle
        return bundle.name

    def get_asset(self, name) -> AssetBundle:
        """根据名字获取资源对象"""
        return self._storage.get(name)

    def list_assets(self):
        """返回当前仓库所有资源的名字列表"""
        return list(self._storage.keys())

    def get_unique_name(self, base_name):
        """查重逻辑：生成唯一的资源名"""
        name = base_name
        counter = 1
        while name in self._storage:
            counter += 1
            name = f"{base_name}_{counter}"
        return name

    def clear_all(self):
        """全量清空"""
        self._storage.clear()

    def remove_asset(self, name):
        """从仓库中移除特定的资源项"""
        if name in self._storage:
            del self._storage[name]
            return True
        return False

    # --- 核心导入方法 (入口) ---

    def load_from_file(self, file_path):
        """
        入口：自动识别并加载文件 (.bgs, .sprite3, 或单张图片)
        场景B：用户拖入10张图时，循环调用此方法即可
        """
        if not os.path.exists(file_path):
                return None

        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext == ".bgs":
                return self._parse_bgs(file_path)
            elif ext == ".sprite3":
                return self._parse_sprite3(file_path)
            elif ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
                return self._parse_single_image(file_path)
        except Exception:
            return None

    def load_from_folder(self, folder_path):
        """
        工具：扫描文件夹内的序列帧并封装为 Bundle
        """
        if not os.path.isdir(folder_path):
            return None

        folder_name = os.path.basename(folder_path.rstrip(os.sep))
        bundle = AssetBundle(folder_name)
        bundle.path = folder_path
        bundle.is_memory = False

        valid_exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
        files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_exts)]

        # 自然排序逻辑
        files.sort(
            key=lambda x: [
                int(c) if c.isdigit() else c for c in re.split("([0-9]+)", x)
            ]
        )

        if not files:
            return None

        for f_name in files:
            full_path = os.path.join(folder_path, f_name)
            pix = QPixmap(full_path)
            if not pix.isNull():
                bundle.frames.append(FrameData(pix, pix.rect(), f_name))

        if bundle.frames:
            bundle.segments = [
                {"name": "All Frames", "start": 1, "end": len(bundle.frames)}
            ]

        return bundle

    def create_bundle_from_memory(
        self, name, pixmap_list, frame_names=None, original_pix=None
    ):
        """
        适配器：处理内存数据（如裁切后的结果或编辑器生成的数据）
        """
        bundle = AssetBundle(name)
        bundle.is_memory = True
        bundle.original_pixmap = original_pix

        for i, pix in enumerate(pixmap_list, start=1):
            f_name = (
                frame_names[i - 1]
                if frame_names and i - 1 < len(frame_names)
                else f"{name}_{i:02d}"
            )
            bundle.frames.append(FrameData(pix, pix.rect(), f_name))

        bundle.segments = [{"name": "Sequence", "start": 1, "end": len(bundle.frames)}]
        return bundle

    def load_asset(self, path):
        """统一入口：根据后缀名决定解析方式"""
        if not os.path.exists(path):
            return None

        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".bgs":
                bundle = self._parse_bgs(path)
            elif ext == ".sprite3":
                bundle = self._parse_sprite3(path)
            elif ext in [".png", ".jpg", ".jpeg"]:
                bundle = self._parse_single_image(path)
            else:
                return None

            # 注册到管理仓库中，确保名字唯一
            if bundle:
                self.register_asset(bundle)
                return bundle
        except Exception as e:
            # 加载失败时暂不打印调试信息
            return None

    # --- 内部私有适配器 ---

    def _parse_bgs(self, path):
        """解析导出的 .bgs 工程文件 (ZIP格式)"""
        with zipfile.ZipFile(path, "r") as z:
            # 1. 读取配置文件
            if "config.json" not in z.namelist():
                raise Exception("无效的 .bgs 文件：缺少 config.json")

            with z.open("config.json") as f:
                data = json.loads(f.read().decode("utf-8"))

            # 2. 初始化 Bundle
            bundle = AssetBundle(data["name"])
            bundle.path = path
            bundle.is_memory = False  # 标记为磁盘导入

            # 3. 按顺序还原帧数据 (必须对应 frames 列表中的顺序)
            for f_name in data.get("frames", []):
                if f_name in z.namelist():
                    img_data = z.read(f_name)
                    pix = QPixmap()
                    pix.loadFromData(img_data)
                    # 还原帧模型，这里 rect 可以设为 pix.rect()，因为导出时已经是裁切好的
                    bundle.frames.append(FrameData(pix, pix.rect(), f_name))

            # 4. 还原片段定义
            bundle.segments = data.get("segments", [])

            return bundle

    def _parse_sprite3(self, path):
        """处理 Scratch 的 .sprite3 压缩包"""
        with zipfile.ZipFile(path, "r") as z:
            with z.open("sprite.json") as f:
                content = f.read().decode("utf-8")
                data = json.loads(content)

                bundle = AssetBundle(data["name"])
                bundle.path = path

                for cos in data.get("costumes", []):
                    img_data = z.read(cos["md5ext"])
                    pix = QPixmap()
                    pix.loadFromData(img_data)
                    bundle.frames.append(FrameData(pix, pix.rect(), cos["name"]))

                # sprite3 默认没片段，创建一个全集的
                bundle.segments = [
                    {"name": "Default", "start": 1, "end": len(bundle.frames)}
                ]
                return bundle

    def _parse_single_image(self, path):
        """处理单张散图导入 (场景B的核心入口)"""
        file_name = os.path.basename(path)
        name_without_ext = os.path.splitext(file_name)[0]

        bundle = AssetBundle(name_without_ext)
        bundle.path = path
        bundle.is_memory = False

        pix = QPixmap(path)
        if pix.isNull():
            raise Exception("图片损坏")

        # 封装为标准一帧
        frame = FrameData(pix, pix.rect(), file_name)
        bundle.frames.append(frame)
        bundle.segments = [{"name": "Default", "start": 1, "end": 1}]

        return bundle
