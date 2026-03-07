import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QSlider, QPushButton, QFrame, QSpacerItem, QSizePolicy)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from ..utils import get_resource_path

class PreviewPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 必须固定宽度为 280，这是原版动画计算的基础
        self.setFixedWidth(280) 
        self.init_ui()

    def init_ui(self):
        # 1. 完全复刻原版背景和左边框样式
        self.setStyleSheet("""
            PreviewPanel {
                background-color: #11111b; 
                border-left: 2px solid #313244;
            }
        """)
        
        # 原版布局：Margins 为 (12, 15, 12, 15)，Spacing 为 10
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 15, 12, 15)
        layout.setSpacing(10)

        # 2. 标题复刻：原版是加粗、特定蓝色、14px
        self.title_label = QLabel("ANIMATION 预览")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            color: #89b4fa; 
            font-weight: bold; 
            font-size: 14px;
            border: none;
            background: transparent;
        """)
        layout.addWidget(self.title_label)

        # 3. 预览屏幕：256x256 严格固定
        self.preview_screen = QLabel()
        self.preview_screen.setFixedSize(256, 256)
        self.preview_screen.setAlignment(Qt.AlignCenter)
        self.preview_screen.setStyleSheet("""
            background-color: #181825; 
            border-radius: 12px; 
            border: 2px solid #313244;
        """)
        # 原版初始文字
        self.preview_screen.setText("<div style='color: #313244; text-align: center;'>"
                                   "<span style='font-size: 20px;'>▶</span><br>"
                                   "<span style='font-size: 14px; letter-spacing: 2px;'>等待导入中...</span></div>")
        
        # 4. 悬浮滑块：它是 preview_screen 的子对象，位置在 (64, 230)
        self.speed_slider = QSlider(Qt.Horizontal, self.preview_screen)
        self.speed_slider.setRange(10, 300)
        self.speed_slider.setValue(120)
        self.speed_slider.setInvertedAppearance(True) # 原版是反向滑块
        self.speed_slider.setGeometry(64, 230, 128, 20)
        self.speed_slider.setStyleSheet("""
            QSlider { background: transparent; border:none;}
            QSlider::groove:horizontal { background: rgba(49, 50, 68, 180); height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #89b4fa; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
        """)
        
        layout.addWidget(self.preview_screen, 0, Qt.AlignCenter)

        # 5. 控制按钮栏：原版是 QHBoxLayout，两端加了 Stretch 居中
        playback_layout = QHBoxLayout()
        playback_layout.setSpacing(4)
        playback_layout.addStretch()
        
        # 按钮顺序：prev, play, next, scale, bg
        self.btns = {}
        for icon_name in ["prev", "play", "next", "btn_scale_mode", "btn_bg_color"]:
            btn = QPushButton()
            btn.setFixedSize(40, 24)
            icon_path = get_resource_path(f"assets/icons/{icon_name}.svg")
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(btn.size() * 0.7)
            btn.setStyleSheet("""
                QPushButton { background-color: #1e1e2e; border: none; border-radius: 4px; }
                QPushButton:hover { background-color: #313244; }
            """)
            playback_layout.addWidget(btn)
            self.btns[icon_name] = btn
            
        playback_layout.addStretch()
        layout.addLayout(playback_layout)

        # 6. 底部占比修正：原版这里是一个充满剩余空间的资源列表区域
        self.res_placeholder = QFrame()
        self.res_placeholder.setStyleSheet("""
            background-color: #181825; 
            border-radius: 12px; 
            border: none;
        """)
        # 关键点：设置伸展因子，让这个区域占据剩余所有空间
        layout.addWidget(self.res_placeholder, 1) 

    def load_segment(self, path, start, end):
        pass