import sys
from PySide6.QtWidgets import QApplication
from PySide6 import QtSvg  # noqa: F401
from PySide6 import QtSvgWidgets  # noqa: F401
import os

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTOSCREENSCALEFACTOR"] = "1"


# 导入我们 src 里的逻辑
from src.utils import lock_environment
from src.main_window import BingoPacker


def main():
    # 1. 锁定环境，解决打包后的路径偏差
    lock_environment()

    # 2. 初始化 App
    app = QApplication(sys.argv)

    # 设置全局样式（推荐使用 Fusion 样式，跨平台效果统一）
    app.setStyle("Fusion")

    # 3. 启动主窗口
    window = BingoPacker()
    window.show()

    # 4. 进入程序循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
