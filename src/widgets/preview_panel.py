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
        self.current_frames_cache = []
        self.current_range = (1, 1) # (start, end) 来自 JSON
        self.current_frame_relative_idx = 0 # 相对当前片段起始点的偏移

        # 新增：记录是否为白色背景
        self.is_white_bg = False
        self.is_original_size = False
        self.init_ui()

        

    def init_ui(self):
        # 1. 基础面板背景 (最底层颜色)
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
            background-color: #1F2125; 
            border: 1px solid #3e4451; 
            border-radius: 8px;
        """)
        self.preview_screen.setText("<div style='color: #313244; text-align: center;'>"
                                   "<span style='font-size: 20px;'>▶</span><br>"
                                   "等待导入</div>")
        
        # 4. 速度滑块 (无边框优化)
        self.speed_slider = QSlider(Qt.Horizontal, self.preview_screen)
        self.speed_slider.setRange(1, 60)
        self.speed_slider.setValue(12)
        # self.speed_slider.setInvertedAppearance(True) 
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
        for icon_name in ["prev", "play", "next", "btn_scale_mode", "btn_bg_color","btn_editor"]:
            btn = QPushButton()
            btn.setFixedSize(40, 24)
            btn.setCursor(Qt.PointingHandCursor)
            icon_path = get_resource_path(f"assets/icons/{icon_name}.svg")
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
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

        # 绑定slider控制播放速度
        self.speed_slider.valueChanged.connect(self.update_play_speed)

        # 切换预览背景
        self.btns["btn_bg_color"].clicked.connect(self.toggle_bg_color)
        # 点击缩放精灵
        self.btns["btn_scale_mode"].clicked.connect(self.toggle_scale_mode)

        # 点击打开编辑模式
        # self.btns["btn_editor"].clicked.connect(self.on_editor_toggle_clicked)

    def on_editor_toggle_clicked(self):
        # 获取主窗口实例并调用切换逻辑
        main_win = self.window()
        if hasattr(main_win, 'toggle_editor_view'):
            is_edit_mode = main_win.toggle_editor_view()
            
            # 按钮样式反馈
            if is_edit_mode:
                # 切换到编辑器模式时，按钮高亮（One Dark 蓝）
                self.btns["btn_editor"].setStyleSheet("background-color: #61afef; border-radius: 4px;")
            else:
                # 恢复默认样式
                self.btns["btn_editor"].setStyleSheet("""
                    QPushButton { background-color: #1e1e2e; border: none; border-radius: 4px; }
                    QPushButton:hover { background-color: #313244; }
                """)

    def toggle_scale_mode(self):
        """切换自适应和原始尺寸模式"""
        self.is_original_size = not self.is_original_size        
            
        # 1. 磁盘模式刷新
        if self.current_asset_path:
            self.render_current_frame()
        # 2. 内存模式刷新（针对 add_editor_source 的 item）
        elif self.current_frames_cache:
            if 0 <= self.current_frame_relative_idx < len(self.current_frames_cache):
                curr_pix = self.current_frames_cache[self.current_frame_relative_idx]
                self._display_pixmap(curr_pix)

    def toggle_bg_color(self):
        """在深色和白色背景之间切换，并适配 Slider 样式"""
        self.is_white_bg = not self.is_white_bg
        
        # 1. 定义不同模式下的颜色配置
        if self.is_white_bg:
            bg_color = "#ffffff"
            slider_groove = "rgba(200, 200, 200, 180)" # 浅灰色条
            slider_handle = "#89b4fa"                 # 深色滑块点，形成对比
            text_color = "#313244"
        else:
            bg_color = "#1F2125"
            slider_groove = "rgba(49, 50, 68, 180)"  # 原有的深色条
            slider_handle = "#89b4fa"                # 原有的蓝色滑块点
            text_color = "#45475a"
        
        # 2. 更新预览区域背景
        self.preview_screen.setStyleSheet(f"""
            background-color: {bg_color}; 
            border-radius: 8px; 
            border: 1px solid #3e4451;
        """)
        
        # 3. 适配 Slider 背景条颜色
        self.speed_slider.setStyleSheet(f"""
            QSlider {{ background: transparent; border: none; outline: none; }}
            QSlider::groove:horizontal {{ 
                background: {slider_groove}; 
                height: 4px; 
                border-radius: 2px; 
            }}
            QSlider::handle:horizontal {{ 
                background: {slider_handle}; 
                width: 12px; 
                height: 12px; 
                margin: -4px 0; 
                border-radius: 6px; 
            }}
        """)
        
        # 4. 如果没有图片，同步更新提示文字颜色
        if not self.preview_screen.pixmap():
            self.preview_screen.setText(f"<div style='color: {text_color}; text-align: center;'>"
                                       "<span style='font-size: 20px;'>▶</span><br>"
                                       "等待导入...</div>")

    def update_play_speed(self):
        """将 FPS 数值转换为定时器需要的毫秒间隔"""
        fps = self.speed_slider.value()
        
        # 防止除以 0，虽然 setRange(1, 60) 已经规避了
        if fps < 1: fps = 1
        
        # 计算毫秒间隔 (例如 24 FPS 约为 41ms)
        interval = int(1000 / fps)
        
        # 如果正在播放，实时更新定时器频率
        if self.play_timer.isActive():
            self.play_timer.setInterval(interval)
        
        # 可选：更新标题或 Label 显示当前 FPS
        # self.title_label.setText(f"速度: {fps} FPS")
    
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
        """处理来自 .bgs / .sprite3 的 ZIP 动画"""
        # 如果路径是特殊的标识符，直接跳过 ZIP 逻辑
        if asset_path == "EDITOR_SOURCE":
            return 

        self.current_frames_cache = [] # 清空内存缓存
        self.current_asset_path = asset_path
        self.current_range = (start, end)
        self.current_frame_relative_idx = 0

        try:
            # 增加路径有效性检查
            if os.path.exists(asset_path):
                with zipfile.ZipFile(asset_path, 'r') as z:
                    exts = ('.png', '.jpg', '.jpeg', '.webp', '.svg')
                    self.frame_names = sorted([f for f in z.namelist() if f.lower().endswith(exts)])
            else:
                print(f"ZIP 文件不存在: {asset_path}")
                return
        except Exception as e:
            print(f"ZIP 加载失败: {e}")
            return

        self.title_label.setText(f"PREVIEW: {segment_name}")
        self.update_preview()
        self.play_timer.start(1000 // max(1, self.speed_slider.value()))
        self.update_play_button_icon(True)

    def toggle_play(self):
        """切换播放/暂停状态：兼容磁盘路径和内存缓存模式，保留速度设置"""
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.update_play_button_icon(is_playing=False)
        else:
            # 修改点：只要有磁盘资源 OR 有内存缓存，就允许播放
            if self.current_asset_path or self.current_frames_cache:
                # 保持你原有的速度换算逻辑不变
                interval = int(1000 / max(1, self.speed_slider.value()))
                self.play_timer.start(interval)
                self.update_play_button_icon(is_playing=True)

    def auto_next_frame(self):
        """自动播放逻辑：必须兼容磁盘和内存两种模式"""
        
        # 模式 A: 磁盘 ZIP 模式
        if self.current_asset_path:
            total_frames = self.current_range[1] - self.current_range[0] + 1
            if total_frames > 0:
                self.current_frame_relative_idx = (self.current_frame_relative_idx + 1) % total_frames
                self.render_current_frame()
            else:
                self.play_timer.stop()

        # 模式 B: 内存模式 (裁切后的动画)
        elif self.current_frames_cache:
            total_frames = len(self.current_frames_cache)
            if total_frames > 0:
                self.current_frame_relative_idx = (self.current_frame_relative_idx + 1) % total_frames
                # 直接从缓存渲染，不要去调用 render_current_frame (那是读磁盘的)
                self._display_pixmap(self.current_frames_cache[self.current_frame_relative_idx])
            else:
                self.play_timer.stop()
        
        # 没有任何数据时停止
        else:
            self.play_timer.stop()
            self.btns["play"].setIcon(QIcon(get_resource_path("assets/icons/play.svg")))

    def next_frame_manual(self):
        """手动下一帧：支持 ZIP 模式和内存裁切模式"""
        # 1. 停止自动播放
        self.play_timer.stop()


        # 2. 核心逻辑判断
        if self.current_asset_path:
            # 传统的 .bgs/.sprite3 模式
            total_frames = self.current_range[1] - self.current_range[0] + 1
            if total_frames > 0:
                self.current_frame_relative_idx = (self.current_frame_relative_idx + 1) % total_frames
                self.render_current_frame()
        elif self.current_frames_cache:
            # 新增：add_editor_source 内存模式
            total_frames = len(self.current_frames_cache)
            if total_frames > 0:
                self.current_frame_relative_idx = (self.current_frame_relative_idx + 1) % total_frames
                # 直接显示内存中的 Pixmap
                self._display_pixmap(self.current_frames_cache[self.current_frame_relative_idx])
        
        # self._update_progress_ui()

    def prev_frame_manual(self):
        """手动上一帧：支持 ZIP 模式和内存裁切模式"""
        self.play_timer.stop()


        if self.current_asset_path:
            # 传统的 .bgs/.sprite3 模式
            total_frames = self.current_range[1] - self.current_range[0] + 1
            if total_frames > 0:
                self.current_frame_relative_idx = (self.current_frame_relative_idx - 1 + total_frames) % total_frames
                self.render_current_frame()
        elif self.current_frames_cache:
            # 新增：add_editor_source 内存模式
            total_frames = len(self.current_frames_cache)
            if total_frames > 0:
                self.current_frame_relative_idx = (self.current_frame_relative_idx - 1 + total_frames) % total_frames
                self._display_pixmap(self.current_frames_cache[self.current_frame_relative_idx])

        # self._update_progress_ui()

    def render_current_frame(self):
        """核心渲染：针对像素风格优化的渲染逻辑"""
        total_files = len(self.frame_names)
        if total_files == 0 or not self.current_asset_path:
            return

        start_val, end_val = self.current_range
        base_idx = max(0, min(start_val - 1, total_files - 1))
        real_idx = base_idx + self.current_frame_relative_idx
        
        if real_idx >= total_files:
            self.current_frame_relative_idx = 0
            real_idx = base_idx

        try:
            with zipfile.ZipFile(self.current_asset_path, 'r') as z:
                img_data = z.read(self.frame_names[real_idx])
                img = QImage.fromData(img_data)
                if not img.isNull():
                    pixmap = QPixmap.fromImage(img)
                    
                    if hasattr(self, 'is_original_size') and self.is_original_size:
                        # 模式 A：原始尺寸 (居中)
                        self.preview_screen.setPixmap(pixmap)
                    else:
                        # 模式 B：黄金比例自适应 (解决“太满”和“偏下”的问题)
                        container_size = self.preview_screen.size()
                        
                        # 设置安全边距，取 85% 为黄金比例
                        # 这样在 256 尺寸下，最大只会放大到 218 像素左右
                        margin_factor = 0.85 
                        target_w = container_size.width() * margin_factor
                        target_h = container_size.height() * margin_factor
                        
                        scaled_pixmap = pixmap.scaled(
                            target_w, target_h,
                            Qt.KeepAspectRatio, 
                            Qt.FastTransformation  # 保持像素风格
                        )
                        self.preview_screen.setPixmap(scaled_pixmap)
                    
                    # 强制垂直居中对齐，修正视觉偏下的错觉
                    self.preview_screen.setAlignment(Qt.AlignCenter)
        except Exception as e:
            print(f"渲染失败: {e}")

    def update_play_button_icon(self, is_playing):
        icon_name = "pause" if is_playing else "play"
        icon_path = get_resource_path(f"assets/icons/{icon_name}.svg")
        if os.path.exists(icon_path):
            self.btns["play"].setIcon(QIcon(icon_path))
    
    

    def update_preview(self):
        """统一渲染：内存优先，文件靠后"""
        # 1. 内存模式（编辑器裁切）
        if self.current_frames_cache:
            try:
                abs_idx = (self.current_range[0] + self.current_frame_relative_idx) % len(self.current_frames_cache)
                pixmap = self.current_frames_cache[abs_idx]
                self._display_pixmap(pixmap)
                return # <--- 关键：渲染完内存图片直接结束，不要往下走！
            except Exception as e:
                print(f"内存渲染失败: {e}")
                return

        # 2. 文件模式（ZIP）
        # 只有路径不是编辑器标识且真实存在时才渲染
        if self.current_asset_path and self.current_asset_path != "EDITOR_SOURCE":
            self.render_current_frame()

    def _display_pixmap(self, pixmap):
        """内部工具：负责最终把 pixmap 贴到标签上"""
        if pixmap is None or pixmap.isNull():
            return
            
        container_size = self.preview_screen.size()
        
        # --- 修复点：使用 if-else 明确区分两种模式 ---
        if self.is_original_size:
            # 原始尺寸模式
            self.preview_screen.setPixmap(pixmap)
        else:
            # 自适应缩放模式
            margin_factor = 0.85 
            scaled_pixmap = pixmap.scaled(
                container_size.width() * margin_factor, 
                container_size.height() * margin_factor,
                Qt.KeepAspectRatio, 
                Qt.FastTransformation # 保持像素锐利
            )
            self.preview_screen.setPixmap(scaled_pixmap)
            
        self.preview_screen.setAlignment(Qt.AlignCenter)

    # --------------------------------------------
    def load_frames_to_preview(self, pixmaps):
        """[唯一接口] 接收内存图片并立即播放"""
        # 1. 强制重置所有状态，防止 ZIP 模式干扰
        self.play_timer.stop()
        self.current_asset_path = None
        self.frame_names = []
        
        # 2. 载入新数据
        self.current_frames_cache = pixmaps
        
        # 3. 关键：裁切模式的 range 必须从 0 开始
        # 之前的 bug 可能出现在这里，如果点击树节点后传了 1-10，这里会索引越界
        self.current_range = (0, len(pixmaps) - 1)
        self.current_frame_relative_idx = 0
        
        # 4. 立即渲染第一帧并重新开启计时器
        self.update_preview()
        
        fps = self.speed_slider.value() if hasattr(self, 'speed_slider') else 12
        self.play_timer.start(1000 // fps)
        
        self.update_play_button_icon(True)

    def on_asset_segment_selected(self, asset_name, action_name, start, end):
        """
        [核心逻辑] 当 AssetTree 选中某个动作项时触发播放
        asset_name: 资源名
        action_name: 动作名 (如 "Sequence")
        start: 开始帧 (从 1 开始)
        end: 结束帧 (从 1 开始)
        """
        print(f"DEBUG: PreviewPanel 收到信号 -> {asset_name}, 范围: {start}-{end}")
        
        # 1. 获取发送者 (AssetTree)
        tree = self.sender()
        if not tree: 
            return
            
        # 2. 获取当前选中的 Item
        current_item = tree.currentItem()
        
        # 3. 寻找存储数据的节点 (如果是子节点，找它的 parent；如果是顶级节点，就是它自己)
        target_item = None
        if current_item:
            target_item = current_item.parent() if current_item.parent() else current_item
        else:
            # 防御性编程：如果当前没有选中项，尝试根据名字搜寻顶级节点
            items = tree.findItems(asset_name, Qt.MatchExactly)
            if items: target_item = items[0]
            
        if not target_item:
            print("DEBUG: 找不到携带数据的 TreeItem")
            return

        # 4. 提取存在 UserRole 里的内存数据 (frames 列表)
        memory_data = target_item.data(0, Qt.UserRole)
        
        if memory_data:
            # --- 情况 A: 内存模式 (裁切或 .bgs 导入) ---
            print(f"DEBUG: 正在从内存播放 {len(memory_data)} 帧数据")
            
            # 停止当前播放，清理状态
            self.play_timer.stop()
            self.current_asset_path = None
            self.frame_names = []
            
            # 提取 QPixmap 对象列表
            pixmaps = [f["pixmap"] for f in memory_data]
            self.current_frames_cache = pixmaps
            
            # 核心修复：将 1-Base 转换为 0-Base 索引
            # 例如用户输入 1-10，我们要取索引 0-9
            self.current_range = (start - 1, end - 1)
            
            # 重置播放指针到起始位置
            self.current_frame_relative_idx = 0
            
            # 开始播放
            self.play_timer.start(100) # 10FPS
            self.auto_next_frame()
        else:
            # --- 情况 B: 磁盘模式 (旧有的 zip 逻辑) ---
            print("DEBUG: 未发现内存数据，尝试走磁盘加载逻辑")
            # 这里调用你原有的 load_animation_frames 逻辑
            self.load_animation_frames(asset_name, start, end)