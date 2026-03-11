import sys
import os
from PySide6.QtWidgets import QApplication

# 确保导入路径
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
from src.asset_manager import AssetManager

def test_folder_logic(folder_path):
    app = QApplication(sys.argv)
    manager = AssetManager()
    
    print(f"--- 开始测试文件夹导入: {folder_path} ---")
    
    bundle = manager.load_from_folder(folder_path)
    
    if bundle:
        print(f"✅ 文件夹加载成功!")
        print(f"   资源名称: {bundle.name}")
        print(f"   总帧数: {len(bundle.frames)}")
        
        # 验证排序是否正确
        if len(bundle.frames) >= 2:
            print(f"   顺序核对: 第一帧={bundle.frames[0].name}, 第二帧={bundle.frames[1].name}")
        
        # 注册并尝试取回
        manager.register_asset(bundle)
        if manager.get_asset(bundle.name):
            print(f"✅ Manager 注册验证通过")
    else:
        print("❌ 加载失败。")

if __name__ == "__main__":
    # 填入你本地存放序列帧图片的文件夹路径
    test_path = "/Users/amixc/Desktop/packer_test/洛克人"
    test_folder_logic(test_path)