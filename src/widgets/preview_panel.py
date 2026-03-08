import os
import zipfile
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
                               QSlider, QPushButton, QWidget,QFileDialog)
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QIcon,QImage, QPixmap

from ..utils import get_resource_path
from .asset_tree import AssetTree 

class PreviewPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280) 

        # --- 播放器状态变量 ---
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.auto_next_frame)
        
        self.current_asset_path = None
        self.frame_names = []      # 当前 ZIP 内所有图片名列表
        self.current_range = (1, 1) # (start, end) 来自 JSON
        self.current_frame_relative_idx = 0 # 相对当前片段起始点的偏移

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
        tree_layout.addWidget(self.asset_tree)

        # 7. 右下角悬浮按钮
        self.float_ctrl = QWidget(self.tree_container)
        self.float_ctrl.setFixedSize(60, 32)
        float_layout = QHBoxLayout(self.float_ctrl)
        float_layout.setContentsMargins(0, 0, 0, 0)
        float_layout.setSpacing(4)

        self.btn_tree_upload = self.make_float_btn("btn_upload")
        self.btn_clear_list = self.make_float_btn("btn_clear_list")
        
        float_layout.addWidget(self.btn_tree_upload)
        float_layout.addWidget(self.btn_clear_list)
        
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
        # 1. 播放控制
        self.btns["play"].clicked.connect(self.toggle_play)
        self.btns["prev"].clicked.connect(self.prev_frame_manual)
        self.btns["next"].clicked.connect(self.next_frame_manual)
        
        # 2. 点击资源列表切换预览
        self.asset_tree.segment_selected.connect(self.start_preview_animation)
        
        # 3. 原有功能
        self.btn_tree_upload.clicked.connect(self.on_upload_clicked)
        self.btn_clear_list.clicked.connect(self.on_clear_clicked)

    
    def on_clear_clicked(self):
        """点击垃圾桶按钮的回调"""
        self.clear_preview()
        self.asset_tree.clear_all()
        
        
        # 如果需要同步清空主窗口的数据
        if self.window() and hasattr(self.window(), 'asset_files'):
            self.window().asset_files = [] # 或者保持空白
    
    def clear_preview(self):
        """彻底清除预览状态，防止残留"""
        # 1. 停止定时器，防止它在后台继续跑渲染逻辑
        self.play_timer.stop()
        
        # 2. 重置所有数据路径和索引
        self.current_asset_path = None
        self.frame_names = []
        self.current_range = (1, 1)
        self.current_frame_relative_idx = 0
        
        # 3. 彻底抹除画面
        self.preview_screen.clear()
        self.preview_screen.setText("<div style='color: #313244; text-align: center;'>"
                                   "<span style='font-size: 20px;'>▶</span><br>"
                                   "等待导入...</div>")
        
        # 4. 重置标题
        self.title_label.setText("ANIMATION 预览")
        
        # 5. 重置播放按钮图标为 play 造型
        self.update_play_button_icon(is_playing=False)

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
        
    def start_preview_animation(self, asset_path, segment_name, start, end):
        """响应 AssetTree 信号：开始播放指定片段"""
        self.current_asset_path = asset_path
        self.current_range = (start, end)
        self.current_frame_relative_idx = 0
        
        # 提取 ZIP 里的图片列表
        try:
            with zipfile.ZipFile(asset_path, 'r') as z:
                exts = ('.png', '.jpg', '.jpeg', '.webp', '.svg')
                # 必须排序，确保与 JSON 里的 start/end 对应
                self.frame_names = sorted([f for f in z.namelist() if f.lower().endswith(exts)])
        except:
            self.frame_names = []

        self.title_label.setText(f"PREVIEW: {segment_name}")
        self.play_timer.start(100) # 默认 10 FPS
        self.update_play_button_icon(is_playing=True)
        self.render_current_frame()

    def toggle_play(self):
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.update_play_button_icon(is_playing=False)
        else:
            if self.current_asset_path:
                self.play_timer.start(100)
                self.update_play_button_icon(is_playing=True)

    def auto_next_frame(self):
        """自动播放：循环步进"""
        start, end = self.current_range
        total = end - start + 1
        if total <= 0: return
        
        self.current_frame_relative_idx = (self.current_frame_relative_idx + 1) % total
        self.render_current_frame()

    def next_frame_manual(self):
        """逐帧下一帧：停止播放并步进"""
        self.play_timer.stop()
        self.update_play_button_icon(is_playing=False)
        
        start, end = self.current_range
        total = end - start + 1
        if total > 0:
            self.current_frame_relative_idx = (self.current_frame_relative_idx + 1) % total
            self.render_current_frame()

    def prev_frame_manual(self):
        """逐帧上一帧：停止播放并回退"""
        self.play_timer.stop()
        self.update_play_button_icon(is_playing=False)
        
        start, end = self.current_range
        total = end - start + 1
        if total > 0:
            self.current_frame_relative_idx = (self.current_frame_relative_idx - 1) % total
            self.render_current_frame()

    def render_current_frame(self):
        if not self.current_asset_path or not self.frame_names:
            return

        total_files = len(self.frame_names)
        start_val, end_val = self.current_range
        
        # --- 核心修复：越界保护 ---
        # 1. 确保起始点不越界
        base_idx = max(0, min(start_val - 1, total_files - 1))
        
        # 2. 计算片段长度（用户定义的长度）
        segment_len = max(1, end_val - start_val + 1)
        
        # 3. 计算当前要播哪一帧（相对偏移）
        # 4. 核心：如果绝对索引越界，强制回滚到 0
        real_idx = base_idx + self.current_frame_relative_idx
        
        if real_idx >= total_files:
            # 如果越界了，说明 1-10 的 8,9,10 没图，直接从头循环
            self.current_frame_relative_idx = 0
            real_idx = base_idx

        # --- 执行渲染 ---
        try:
            with zipfile.ZipFile(self.current_asset_path, 'r') as z:
                img_data = z.read(self.frame_names[real_idx])
                img = QImage.fromData(img_data)
                if not img.isNull():
                    pixmap = QPixmap.fromImage(img)
                    self.preview_screen.setPixmap(pixmap.scaled(
                        self.preview_screen.size(), 
                        Qt.KeepAspectRatio, 
                        Qt.FastTransformation
                    ))
        except Exception as e:
            # 即使单帧读取失败，也不要停止 timer，跳过这一帧即可
            print(f"帧渲染跳过: {e}")
            self.current_frame_relative_idx = 0

    def update_play_button_icon(self, is_playing):
        icon_name = "pause" if is_playing else "play"
        icon_path = get_resource_path(f"assets/icons/{icon_name}.svg")
        if os.path.exists(icon_path):
            self.btns["play"].setIcon(QIcon(icon_path))