BingoPacker/
├── main.py                  # 程序唯一启动入口
├── assets/                  # 静态资源存放处 (手动把图标存入此文件夹)
│   └── icons/               # 存放所有的 .svg 或 .png 图标
│       ├── pick_folders.svg
│       ├── clear_all.svg
│       ├── play.svg
│       ├── pause.svg
│       └── ... (其他原有图标)
├── src/                     # 核心源代码包
│   ├── __init__.py          # 标识 src 为 Python 包
│   ├── utils.py             # 通用工具：路径获取(get_resource_path)、环境锁定
│   ├── core.py              # 业务逻辑：OpenCV裁切算法、BGS/Sprite3 打包逻辑
│   ├── models.py            # 数据模型：AnimationClip 类、SpriteAsset 类
│   ├── main_window.py       # 主窗口：负责布局组装、信号分发（中转站）
│   └── widgets/             # UI 自定义组件包
│       ├── __init__.py      # 标识 widgets 为 Python 包
│       ├── asset_tree.py    # 资源列表组件：处理折叠、加号、双击编辑
│       └── preview_panel.py # 预览控制组件：处理播放、停止、滑块、背景切换
└── requirements.txt         # (可选) 记录依赖：PySide6, opencv-python, numpy, Pillow