import os
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
    QWidget,
    QFileDialog,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap

from ..utils import get_resource_path
from .asset_tree import AssetTree


class PreviewPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)

        # --- 状态变量 (逻辑优化) ---
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.auto_next_frame)

        self.current_bundle = None  # 核心数据对象
        self.current_segment = None  # 当前片段信息
        self.current_frame_relative_idx = 0

        # 原始状态变量
        self.is_white_bg = False
        self.is_original_size = False

        # 兼容旧逻辑的变量 (保留以防万一)
        self.current_asset_path = None
        self.frame_names = []

        self.init_ui()
        self.button_connect()

    def init_ui(self):
        # --- 1. 基础面板背景 (完全还原) ---
        self.setStyleSheet("""
            PreviewPanel {
                background-color: #21252b; 
                border-left: 1px solid #181a1f;
            }
            QLabel {
                color: #abb2bf;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 4)
        layout.setSpacing(10)

        # --- 2. 标题 (完全还原) ---
        self.title_label = QLabel("ANIMATION 预览")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            color: #89b4fa; 
            font-weight: bold; 
            font-size: 14px;
            background: transparent;
        """)
        layout.addWidget(self.title_label)

        # --- 3. 预览屏幕 (完全还原) ---
        self.preview_screen = QLabel()
        self.preview_screen.setFixedSize(256, 256)
        self.preview_screen.setAlignment(Qt.AlignCenter)
        self.preview_screen.setStyleSheet("""
            background-color: #1F2125; 
            border: 1px solid #3e4451; 
            border-radius: 8px;
        """)
        self.preview_screen.setText(
            "<div style='color: #313244; text-align: center;'>"
            "<span style='font-size: 20px;'>▶</span><br>"
            "等待导入</div>"
        )

        # --- 4. 速度滑块 (完全还原) ---
        self.speed_slider = QSlider(Qt.Horizontal, self.preview_screen)
        self.speed_slider.setRange(1, 60)
        self.speed_slider.setValue(12)
        self.speed_slider.setGeometry(64, 230, 128, 20)
        self.speed_slider.setStyleSheet("""
            QSlider { background: transparent; border: none; outline: none; }
            QSlider::groove:horizontal { background: rgba(49, 50, 68, 180); height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #89b4fa; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }
        """)
        layout.addWidget(self.preview_screen, 0, Qt.AlignCenter)

        # --- 5. 控制按钮栏 (完全还原) ---
        playback_layout = QHBoxLayout()
        playback_layout.setSpacing(4)
        playback_layout.addStretch()

        self.btns = {}
        for icon_name in [
            "prev",
            "play",
            "next",
            "btn_scale_mode",
            "btn_bg_color",
            "btn_editor",
        ]:
            btn = QPushButton()
            btn.setFixedSize(40, 24)
            btn.setCursor(Qt.PointingHandCursor)
            icon_path = get_resource_path(f"assets/icons/{icon_name}.svg")
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                # 还原 0.7 比例
                btn.setIconSize(btn.size() * 0.7)

            btn.setStyleSheet("""
                QPushButton { background-color: #2F3244; border: none; border-radius: 4px; }
                QPushButton:hover { background-color: #484B59; }
                QPushButton:pressed { background-color: #45475a; }
            """)
            playback_layout.addWidget(btn)
            self.btns[icon_name] = btn

        playback_layout.addStretch()
        layout.addLayout(playback_layout)

        # --- 6. 资产树容器 (完全还原) ---
        self.tree_container = QWidget()
        self.tree_container.setStyleSheet("background: transparent;")
        tree_layout = QVBoxLayout(self.tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)

        self.asset_tree = AssetTree()
        tree_layout.addWidget(self.asset_tree)

        # --- 7. 右下角悬浮按钮 (完全还原) ---
        # self.float_ctrl = QWidget(self.tree_container)
        # self.float_ctrl.setFixedSize(60, 32)
        # float_layout = QHBoxLayout(self.float_ctrl)
        # float_layout.setContentsMargins(0, 0, 0, 0)
        # float_layout.setSpacing(4)

        # self.btn_tree_upload = self.make_float_btn("btn_upload")
        # self.btn_clear_list = self.make_float_btn("btn_clear_list")

        # float_layout.addWidget(self.btn_tree_upload)
        # float_layout.addWidget(self.btn_clear_list)

        layout.addWidget(self.tree_container, 1)

    # --- 逻辑接口 (重构部分，对接新数据结构) ---

    # preview_panel.py

    def start_segment_preview(self, bundle, segment):
        # 1. 无论如何，先停止旧的计时器，防止频率叠加
        if self.play_timer.isActive():
            self.play_timer.stop()

        is_same_seg = self.current_bundle == bundle and self.current_segment == segment
        self.current_bundle = bundle
        self.current_segment = segment

        if not is_same_seg:
            self.current_frame_relative_idx = 0

        # 2. 重新计算并设置间隔
        fps = self.speed_slider.value()
        interval = int(1000 / max(1, fps))
        self.play_timer.setInterval(interval)  # 显式设置，不依赖 update_play_speed

        self.render_current_frame()

        # 3. 只有帧数大于 1 且用户没有手动暂停时才开启
        if len(bundle.frames) > 1:
            self.play_timer.start()
            self.update_play_button_icon(True)
        else:
            self.update_play_button_icon(False)

    def render_current_frame(self):
        if not self.current_bundle or not self.current_bundle.frames:
            return

        start_val = self.current_segment.get("start", 1)
        abs_idx = (start_val - 1) + self.current_frame_relative_idx

        if 0 <= abs_idx < len(self.current_bundle.frames):
            # 核心：直接访问 FrameData 对象中的 pixmap 属性
            # 之前可能是通过某种转换，现在确保它是实时的
            frame_obj = self.current_bundle.frames[abs_idx]
            pixmap = frame_obj.pixmap
            self._display_pixmap(pixmap)

    def _display_pixmap(self, pixmap):
        """完全还原原始的缩放和对齐逻辑"""
        if pixmap is None or pixmap.isNull():
            return

        container_size = self.preview_screen.size()
        if self.is_original_size:
            self.preview_screen.setPixmap(pixmap)
        else:
            margin_factor = 0.85
            scaled_pixmap = pixmap.scaled(
                container_size.width() * margin_factor,
                container_size.height() * margin_factor,
                Qt.KeepAspectRatio,
                Qt.FastTransformation,
            )
            self.preview_screen.setPixmap(scaled_pixmap)

        self.preview_screen.setAlignment(Qt.AlignCenter)

    # --- 按钮回调 (完全还原源码逻辑) ---

    def auto_next_frame(self):
        if not self.current_segment:
            return

        # 直接从字典实时读取，这样你在 AssetTree 里改了 QLineEdit，这里下一秒就能读到
        start = self.current_segment.get("start", 1)
        end = self.current_segment.get("end", 1)

        total = end - start + 1
        if total > 1:
            # 实时计算索引
            self.current_frame_relative_idx = (
                self.current_frame_relative_idx + 1
            ) % total
            self.render_current_frame()
        else:
            # 单帧情况
            self.current_frame_relative_idx = 0
            self.render_current_frame()
            self.play_timer.stop()
            self.update_play_button_icon(False)

    def button_connect(self):
        self.btns["play"].clicked.connect(self.toggle_play)
        self.btns["prev"].clicked.connect(lambda: self.manual_step(-1))
        self.btns["next"].clicked.connect(lambda: self.manual_step(1))
        # self.btn_tree_upload.clicked.connect(self.on_upload_clicked)
        # self.btn_clear_list.clicked.connect(self.on_clear_clicked)
        self.speed_slider.valueChanged.connect(self.update_play_speed)
        self.btns["btn_bg_color"].clicked.connect(self.toggle_bg_color)
        self.btns["btn_scale_mode"].clicked.connect(self.toggle_scale_mode)

    def manual_step(self, step):
        self.play_timer.stop()
        self.update_play_button_icon(False)
        if not self.current_segment:
            return
        total = (
            self.current_segment.get("end", 1)
            - self.current_segment.get("start", 1)
            + 1
        )
        if total > 0:
            self.current_frame_relative_idx = (
                self.current_frame_relative_idx + step
            ) % total
            self.render_current_frame()

    # --- 其他辅助函数 (完全照抄源码) ---

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
        if hasattr(self, "float_ctrl"):
            # 还原 -8 边距
            self.float_ctrl.move(
                self.tree_container.width() - self.float_ctrl.width() - 8,
                self.tree_container.height() - self.float_ctrl.height() - 8,
            )

    def toggle_play(self):
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.update_play_button_icon(False)
        else:
            if self.current_bundle and len(self.current_bundle.frames) > 1:
                self.play_timer.start(1000 // max(1, self.speed_slider.value()))
                self.update_play_button_icon(True)

    def update_play_button_icon(self, is_playing):
        name = "pause" if is_playing else "play"
        path = get_resource_path(f"assets/icons/{name}.svg")
        if os.path.exists(path):
            self.btns["play"].setIcon(QIcon(path))

    def toggle_bg_color(self):
        """仅切换预览区域和滑块槽的背景颜色"""
        self.is_white_bg = not self.is_white_bg

        if self.is_white_bg:
            # 白色模式：屏幕变白，滑块槽变浅色半透明以保持可见
            bg_color = "#FFFFFF"
            slider_groove = "rgba(0, 0, 0, 40)"
        else:
            # 深色模式：恢复初始颜色
            bg_color = "#1F2125"
            slider_groove = "rgba(49, 50, 68, 180)"

        # 1. 只改预览屏幕的背景色 (使用你代码中的 preview_screen)
        self.preview_screen.setStyleSheet(f"""
            background-color: {bg_color}; 
            border: 1px solid #3e4451; 
            border-radius: 8px;
        """)

        # 2. 只改滑块的槽背景 (否则白底上看不见原来的深色槽)
        self.speed_slider.setStyleSheet(f"""
            QSlider {{ background: transparent; border: none; }}
            QSlider::groove:horizontal {{ 
                background: {slider_groove}; 
                height: 4px; 
                border-radius: 2px; 
            }}
            QSlider::handle:horizontal {{ 
                background: #89b4fa; 
                width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; 
            }}
        """)

        # 3. 立即重绘当前帧
        self.render_current_frame()

    def toggle_scale_mode(self):
        self.is_original_size = not self.is_original_size
        self.render_current_frame()

    def update_play_speed(self):
        fps = self.speed_slider.value()
        interval = int(1000 / max(1, fps))
        if self.play_timer.isActive():
            self.play_timer.setInterval(interval)

    def on_upload_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择动画资源", "", "Animation Files (*.bgs *.sprite3);;All Files (*)"
        )
        if file_path:
            self.asset_tree.add_asset(file_path)

    def on_clear_clicked(self):
        self.play_timer.stop()
        self.preview_screen.clear()
        self.preview_screen.setText(
            "<div style='color: #313244; text-align: center;'>▶<br>等待导入</div>"
        )
        self.asset_tree.clear_all()
        self.update_play_button_icon(False)

    def update_segment_range(self, bundle, segment):
        """当用户在树中修改起始/结束帧数字时，实时同步播放范围"""
        # 如果是同一个片段，我们只更新范围，不重置当前帧索引
        if self.current_bundle == bundle and self.current_segment == segment:
            # 直接从 segment 字典读，因为 AssetTree 已经把新数字写进这个字典了
            start = segment.get("start", 1)
            end = segment.get("end", 1)
            total = end - start + 1
            if self.current_frame_relative_idx >= total:
                self.current_frame_relative_idx = 0

            # 根据新范围决定是否开启播放
            if total > 1 and not self.play_timer.isActive():
                self.play_timer.start(1000 // max(1, self.speed_slider.value()))
                self.update_play_button_icon(True)
            elif total <= 1:
                self.play_timer.stop()
                self.update_play_button_icon(False)

            self.render_current_frame()
        else:
            # 如果切了不同的片段，走完整的初始化流程
            self.start_segment_preview(bundle, segment)

    # preview_panel.py

    def stop_and_clear(self):
        """停止播放并彻底擦除画面"""

        # 1. 停止定时器
        if self.play_timer.isActive():
            self.play_timer.stop()

        # 2. 清空逻辑变量
        self.current_bundle = None
        self.current_segment = None
        self.current_frame_relative_idx = 0

        # 3. --- 强制清空显示 (使用正确的变量名 preview_screen) ---
        if hasattr(self, "preview_screen"):
            # 先清空文字
            self.preview_screen.clear()
            # 加上你想要的强制缓冲区刷新
            # 创建一个 1x1 的透明图来覆盖旧的显存内容
            empty_pix = QPixmap(1, 1)
            empty_pix.fill(Qt.GlobalColor.transparent)
            self.preview_screen.setPixmap(empty_pix)

            # 设置占位文字并强制重绘
            self.preview_screen.setText("暂无预览")
            self.preview_screen.repaint()

        # 4. 更新按钮状态
        self.update_play_button_icon(False)
        
        # 5. 清空资源树
        if hasattr(self, "asset_tree"):
            self.asset_tree.clear()
