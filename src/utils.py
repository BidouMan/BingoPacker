""" 
动态获取资源路径：
自动识别是【开发环境】、【Windows打包】还是【macOS .app】
锁定工作目录，确保文件 IO 路径不出错 
"""

import sys
import os
import platform

def get_resource_path(relative_path):
    """ 
    终极兼容版路径获取：
    1. 优先检查 PyInstaller 释放目录
    2. 针对 src/ 目录下的调用，自动定位到根目录的 assets
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    
    # 因为 utils.py 在 src 文件夹里，我们需要获取 src 的父目录（项目根目录）
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    if platform.system() == "Darwin" and getattr(sys, 'frozen', False):
        mac_res_path = os.path.join(base_path, '..', 'Resources', relative_path)
        if os.path.exists(mac_res_path):
            return os.path.normpath(mac_res_path)
            
    return os.path.normpath(os.path.join(base_path, relative_path))

def lock_environment():
    """ 锁定工作目录，确保打包后路径不出错 """
    if getattr(sys, 'frozen', False):
        executable_dir = os.path.dirname(sys.executable)
        if platform.system() == "Darwin" and ".app/Contents/MacOS" in executable_dir:
            executable_dir = os.path.abspath(os.path.join(executable_dir, "../../../"))
        os.chdir(executable_dir)
    else:
        # 开发时锁定在 main.py 所在的根目录
        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))