import os
import json
import zipfile
import hashlib
from PySide6.QtCore import QBuffer, QIODevice
from .asset_manager import AssetManager


class ExportLogic:
    def _get_export_save_path(self, bundle, extension):
        """
        核心路径逻辑：确保导出文件与原始资源在同级目录
        """
        if bundle.path:
            # 无论 path 是文件夹还是文件，os.path.dirname 都会指向它的父目录
            # rstrip(os.sep) 是为了防止路径末尾带有斜杠导致 dirname 返回错误
            parent_dir = os.path.dirname(bundle.path.rstrip(os.sep))
            save_path = os.path.join(parent_dir, f"{bundle.name}{extension}")
        else:
            # 如果是纯内存创建的，放在程序运行目录
            save_path = os.path.join(os.getcwd(), f"{bundle.name}{extension}")

        return os.path.abspath(save_path)

    def on_export_sprite3(self, target_name=None):
        manager = AssetManager()

        if target_name is None:
            # 判定当前是否在编辑器页面 (Index 1)
            if hasattr(self, "left_stack") and self.left_stack.currentIndex() == 1:
                # 只获取当前编辑器里的资产包名字
                if hasattr(self, "editor_page") and self.editor_page.current_bundle:
                    target_name = self.editor_page.current_bundle.name

        if target_name:
            asset_names = [target_name]
        else:
            asset_names = manager.list_assets()

        if not asset_names:
            self.add_log("⚠️ 没有可导出的资源", "#ff5555")
            return

        for name in asset_names:
            bundle = manager.get_asset(name)
            # 使用新的路径算法
            save_path = self._get_export_save_path(bundle, ".sprite3")

            try:
                with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    costumes = []
                    for frame in bundle.frames:
                        pix_data = self._pixmap_to_bytes(frame.pixmap)
                        md5_hash = hashlib.md5(pix_data).hexdigest()
                        ext = "png"
                        md5_filename = f"{md5_hash}.{ext}"

                        costumes.append(
                            {
                                "name": frame.name if frame.name else bundle.name,
                                "bitmapResolution": 2,
                                "dataFormat": ext,
                                "assetId": md5_hash,
                                "md5ext": md5_filename,
                                "rotationCenterX": frame.pixmap.width() / 2,
                                "rotationCenterY": frame.pixmap.height() / 2,
                            }
                        )
                        zipf.writestr(md5_filename, pix_data)

                    sprite_data = {
                        "isStage": False,
                        "name": bundle.name,
                        "segments": bundle.segments,
                        "costumes": costumes,
                        "currentCostume": 0,
                        "sounds": [],
                        "variables": {},
                        "lists": {},
                        "broadcasts": {},
                        "blocks": {},
                        "comments": {},
                        "volume": 100,
                        "visible": True,
                        "x": 0,
                        "y": 0,
                        "size": 100,
                        "direction": 90,
                        "draggable": False,
                        "rotationStyle": "all around",
                    }
                    zipf.writestr(
                        "sprite.json",
                        json.dumps(sprite_data, indent=4, ensure_ascii=False),
                    )

                self.add_log(f"-> 导出成功: {os.path.basename(save_path)}", "#E48E51")
            except Exception as e:
                self.add_log(f"⚠️ 导出失败 [{bundle.name}]: {str(e)}", "#ff5555")

    def on_export_bgs(self, target_name=None):
        manager = AssetManager()

        # --- 逻辑分流 ---
        if target_name:
            asset_names = [target_name]
        else:
            asset_names = manager.list_assets()

        if not asset_names:
            self.add_log("⚠️ 没有可导出的资源", "#ff5555")
            return

        for name in asset_names:
            bundle = manager.get_asset(name)
            # 使用新的路径算法
            save_path = self._get_export_save_path(bundle, ".bgs")

            try:
                with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    frame_files = []
                    for i, frame in enumerate(bundle.frames, start=1):
                        f_name = f"{bundle.name}_{i:02d}.png"
                        pix_data = self._pixmap_to_bytes(frame.pixmap)
                        zipf.writestr(f_name, pix_data)
                        frame_files.append(f_name)

                    config = {
                        "name": bundle.name,
                        "count": len(bundle.frames),
                        "frames": frame_files,
                        "segments": bundle.segments,
                    }
                    zipf.writestr("config.json", json.dumps(config, indent=4))

                self.add_log(f"-> 导出成功: {os.path.basename(save_path)}", "#5CD59B")
            except Exception as e:
                self.add_log(f"⚠️ 导出失败 [{bundle.name}]: {str(e)}", "#ff5555")

        if target_name is None:
            manager.clear_all()

    def _pixmap_to_bytes(self, pixmap):
        byte_array = QBuffer()
        byte_array.open(QIODevice.WriteOnly)
        pixmap.save(byte_array, "PNG")
        return byte_array.data().data()
