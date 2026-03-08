import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt

class ManualEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # 保持与主窗口 console 一致的圆角深色风格
        self.setStyleSheet("""
            QWidget { background-color: #181825; border: 1px solid #313244; border-radius: 10px; }
            QLabel { color: #89b4fa; font-weight: bold; border: none; }
            QPushButton { background-color: #313244; padding: 5px 10px; border-radius: 4px; }
            QPushButton:hover { background-color: #45475a; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 头部标题
        self.title_label = QLabel("手动裁切编辑器")
        self.title_label.setStyleSheet("font-size: 16px; color: #fab387;")
        layout.addWidget(self.title_label)

        # 这里预留以后放图片列表或参数输入区
        self.work_area = QWidget()
        self.work_area.setStyleSheet("border: 1px dashed #45475a;")
        work_layout = QVBoxLayout(self.work_area)
        
        placeholder = QLabel("请在右侧预览区选择素材进行裁切编辑")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #585b70; border: none;")
        work_layout.addWidget(placeholder)
        
        layout.addWidget(self.work_area)

        # 底部控制区
        ctrl_layout = QHBoxLayout()
        self.btn_save_edit = QPushButton(" 应用改动")
        self.btn_reset = QPushButton(" 重置")
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_reset)
        ctrl_layout.addWidget(self.btn_save_edit)
        layout.addLayout(ctrl_layout)

    def load_asset_data(self, asset_name):
        """以后供主窗口调用：切换编辑器内容"""
        self.title_label.setText(f"正在编辑: {asset_name}")