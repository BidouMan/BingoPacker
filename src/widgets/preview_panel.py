import os
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                               QSlider, QPushButton, QWidget,QFileDialog)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from ..utils import get_resource_path
from .asset_tree import AssetTree 

class PreviewPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280) 
        self.init_ui()

    def init_ui(self):
        # 1. 基础面板背景 (最底层颜色)
        self.setStyleSheet("""
            PreviewPanel {
                background-color: #11111b; 
                border-left: 2px solid #313244;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 15, 12, 15)
        layout.setSpacing(10)

        # 2. 标题
        self.title_label = QLabel("ANIMATION 预览")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            color: #89b4fa; 
            font-weight: bold; 
            font-size: 14px;
            background: transparent;
        """)
        layout.addWidget(self.title_label)

        # 3. 预览屏幕 (背景色为 #181825)
        self.preview_screen = QLabel()
        self.preview_screen.setFixedSize(256, 256)
        self.preview_screen.setAlignment(Qt.AlignCenter)
        self.preview_screen.setStyleSheet("""
            background-color: #181825; 
            border-radius: 12px; 
            border: 2px solid #313244;
        """)
        self.preview_screen.setText("<div style='color: #313244; text-align: center;'>"
                                   "<span style='font-size: 20px;'>▶</span><br>"
                                   "等待导入...</div>")
        
        # 4. 速度滑块 (无边框优化)
        self.speed_slider = QSlider(Qt.Horizontal, self.preview_screen)
        self.speed_slider.setRange(10, 300)
        self.speed_slider.setValue(120)
        self.speed_slider.setInvertedAppearance(True) 
        self.speed_slider.setGeometry(64, 230, 128, 20)
        self.speed_slider.setStyleSheet("""
            QSlider { background: transparent; border: none; outline: none; }
            QSlider::groove:horizontal { background: rgba(49, 50, 68, 180); height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #89b4fa; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
        """)
        layout.addWidget(self.preview_screen, 0, Qt.AlignCenter)

        # 5. 控制按钮栏 (Hover 效果)
        playback_layout = QHBoxLayout()
        playback_layout.setSpacing(4)
        playback_layout.addStretch()
        
        self.btns = {}
        for icon_name in ["prev", "play", "next", "btn_scale_mode", "btn_bg_color"]:
            btn = QPushButton()
            btn.setFixedSize(40, 24)
            btn.setCursor(Qt.PointingHandCursor)
            icon_path = get_resource_path(f"assets/icons/{icon_name}.svg")
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(btn.size() * 0.7)
            
            btn.setStyleSheet("""
                QPushButton { background-color: #1e1e2e; border: none; border-radius: 4px; }
                QPushButton:hover { background-color: #313244; }
                QPushButton:pressed { background-color: #45475a; }
            """)
            playback_layout.addWidget(btn)
            self.btns[icon_name] = btn
            
        playback_layout.addStretch()
        layout.addLayout(playback_layout)

        # 6. 资产树容器 (设置为与预览屏幕一致的 #181825)
        self.tree_container = QWidget()
        self.tree_container.setStyleSheet("background: transparent;") # 容器透明，由内部树控制背景
        tree_layout = QVBoxLayout(self.tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)

        self.asset_tree = AssetTree() 
        # 重点修改：统一底色为 #181825，并添加圆角和边框，确保能看见
        self.asset_tree.setStyleSheet("""
            QTreeWidget { 
                background-color: #181825; 
                border: none; 
                border-radius: 12px;
                color: #cdd6f4;
                outline: none;
                font-family: 'Segoe UI', sans-serif;
            }
            QTreeWidget::item { 
                height: 32px; 
                border-bottom: 1px solid #1e1e2e; 
                padding-left: 5px;
            }
            QTreeWidget::item:hover { 
                background-color: #313244; 
            }
            QTreeWidget::item:selected { 
                background-color: #45475a; 
                color: #89b4fa;
            }
        """)
        tree_layout.addWidget(self.asset_tree)

        # 7. 右下角悬浮按钮
        self.float_ctrl = QWidget(self.tree_container)
        self.float_ctrl.setFixedSize(60, 32)
        float_layout = QHBoxLayout(self.float_ctrl)
        float_layout.setContentsMargins(0, 0, 0, 0)
        float_layout.setSpacing(4)

        self.btn_tree_upload = self.make_float_btn("btn_upload")
        self.btn_tree_clear = self.make_float_btn("btn_clear_list")
        
        float_layout.addWidget(self.btn_tree_upload)
        float_layout.addWidget(self.btn_tree_clear)
        
        layout.addWidget(self.tree_container, 1)

        # 绑定信号
        self.button_connect()

    def make_float_btn(self, icon_name):
        btn = QPushButton()
        btn.setFixedSize(24, 24)
        btn.setCursor(Qt.PointingHandCursor)
        icon_path = get_resource_path(f"assets/icons/{icon_name}.svg")
        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
        
        btn.setStyleSheet("""
            QPushButton { background-color: #313244; border-radius: 8px; border: none; }
            QPushButton:hover { background-color: #45475a; }
            QPushButton:pressed { background-color: #585b70; }
        """)
        return btn

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'float_ctrl'):
            self.float_ctrl.move(
                self.tree_container.width() - self.float_ctrl.width() - 8,
                self.tree_container.height() - self.float_ctrl.height() - 8
            )
    
    def button_connect(self):
        self.btn_tree_upload.clicked.connect(self.on_upload_clicked)

    def on_upload_clicked(self):
        # 修改：使用 getOpenFileName 并设置过滤器，支持文件夹和特定文件
        # 注意：Qt 原生对话框选文件和文件夹通常是分开的，
        # 为了体验最好，我们支持选择文件，同时保留拖拽文件夹的功能。
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择动画资源 (.bgs / .sprite3)", 
            "", 
            "Animation Files (*.bgs *.sprite3);;All Files (*)"
        )
        if file_path:
            self.asset_tree.add_asset(file_path)
    
    def handle_upload(self):
        # 允许选择文件夹，或者特定的两种文件格式
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择动画资源", 
            "", 
            "Animation Files (*.bgs *.sprite3);;All Files (*)"
        )
        if file_path:
            self.asset_tree.add_asset(file_path)