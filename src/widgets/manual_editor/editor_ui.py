from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QFrame,
    QPushButton,
    QButtonGroup,
    QLabel,
    QSlider,
    QCheckBox,
    QToolTip,
)
from PySide6.QtCore import Qt, QSize, QEvent, QPoint, QObject
from PySide6.QtGui import QIcon
import os
from ...utils import get_resource_path


import platform


class _ToolTipEventFilter(QObject):
    def eventFilter(self, watched, event):
        if event.type() == QEvent.ToolTip:
            tip = watched.toolTip()
            if tip:
                # 1. 基础偏移：y_offset 在 Mac 上 4 像素就够了
                # 2. Windows 补偿：Windows 的 QToolTip 渲染逻辑和高 DPI 经常导致重叠或偏高
                y_offset = 4
                if platform.system() == "Windows":
                    y_offset = 12  # 增加 Windows 下的垂直间距

                # 获取按钮正下方的全局坐标
                # 建议使用 rect().bottomCenter() 来获取更稳定的基准点
                local_pos = QPoint(watched.width() // 2, watched.height() + y_offset)
                pos = watched.mapToGlobal(local_pos)

                QToolTip.showText(pos, tip, watched)
            return True
        return super().eventFilter(watched, event)


class EditorUI:
    def setup_ui(self, widget: QWidget):
        # 获取魔法棒选择图标的绝对路径
        magic_wand_select_path = get_resource_path("assets/icons/magic_wand_select.svg")
        # 确保路径中的反斜杠被正确转义
        magic_wand_select_path = magic_wand_select_path.replace('\\', '/')
        
        widget.setStyleSheet(f"""
            QWidget {{ background-color: #282c34; color: #abb2bf; border: none; }}
            
            QListWidget {{ 
                background-color: #21252b; 
                border-right: 1px solid #181a1f; 
                outline: none; 
                padding: 0px; 
            }}
            /* 强制 Item 内部边距 and 间距 */
            QListWidget::item {{ 
                background-color: #2c313a; 
                border-radius: 4px; 
                margin: 4px;
                color: #ffffff;
                /* 确保文字和图片有足够的间距 */
                padding: 2px; 
                /* 强制内容居中 */
                text-align: center;
            }}
            QListWidget::item:selected {{ 
                background-color: #3e4451; 
                border: 1px solid rgb(137, 180, 250); 
            }}
            QPushButton {{ background-color: #353b45; border: 1px solid #181a1f; border-radius: 4px; padding: 6px; font-weight: bold; }}
            QPushButton:hover {{ background-color: #3e4451; }}

            /* --- 仅为新组件添加必要的样式，不触碰原有组件 --- */
            QSlider::groove:horizontal {{ border: 1px solid #181a1f; height: 4px; background: #353b45; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: rgb(137, 180, 250); width: 10px; height: 10px; margin: -3px 0; border-radius: 5px; }}
            
            QCheckBox::indicator {{ 
                width: 14; 
                height: 14; 
                background-color: #353b45; 
                border: 1px solid #181a1f; 
                border-radius: 3px; 
                /* 核心：在默认状态就预留好 padding，防止切换时尺寸抖动 */
                padding: 2px; 
            }}

            QCheckBox::indicator:hover {{ 
                background-color: #3e4451; 
            }}

            /* 2. 选中状态只改背景和图片，不改尺寸相关属性 */
            QCheckBox::indicator:checked {{ 
                background-color: rgb(137, 180, 250); 
                /* 引用你的 SVG */
                image: url({magic_wand_select_path});
            }}
            QToolTip {{
                background-color: #21252b;
                color: #abb2bf;
                border: 1px solid rgb(137, 180, 250);
                padding: 3px 5px;

                /* 保证 tooltip 永远在最前面 */
            
            }}
        """)

        tips = self.get_tool_configs()

        # 检查widget是否已经有布局
        if widget.layout() is None:
            layout = QVBoxLayout(widget)
        else:
            layout = widget.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部工具栏
        self.toolbar = QFrame()
        self.toolbar.setFixedHeight(35)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(5, 0, 5, 0)
        toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # 基础按钮 - 严格保持你的原始定义（不限制 size，不改文字）
        self.btn_new_file = self._create_tool_btn(
            "btn_new_file", "新建", tip_config=tips["new_file"]
        )
        self.btn_save = self._create_tool_btn(
            "btn_save", "保存", tip_config=tips["save"]
        )
        self.btn_magic_wand = self._create_tool_btn(
            "btn_magic_wand", "魔棒", True, tip_config=tips["magic_wand"]
        )
        self.btn_pick = self._create_tool_btn(
            "btn_pick", "选取", True, tip_config=tips["pick"]
        )
        self.btn_transform = self._create_tool_btn(
            "btn_transform", "变换", True, tip_config=tips["transform"]
        )
        self.btn_cut = self._create_tool_btn(
            "btn_cut", "裁切画布", True, tip_config=tips["cut"]
        )
        self.btn_slice = self._create_tool_btn(
            "btn_slice", "裁切序列帧", True, tip_config=tips["slice"]
        )

        self.tool_group = QButtonGroup(widget)
        self.tool_group.addButton(self.btn_magic_wand)
        self.tool_group.addButton(self.btn_pick)
        self.tool_group.addButton(self.btn_transform)
        self.tool_group.addButton(self.btn_slice)

        toolbar_layout.addWidget(self.btn_new_file)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addWidget(self.btn_magic_wand)
        toolbar_layout.addWidget(self.btn_pick)
        toolbar_layout.addWidget(self.btn_transform)
        toolbar_layout.addWidget(self.btn_cut)
        toolbar_layout.addWidget(self.btn_slice)

        # --- 插入弹簧实现右对齐 ---
        # toolbar_layout.addStretch()

        # --- 魔棒工具选项面板 ---
        self.magic_wand_panel = QWidget()
        self.magic_wand_panel.setVisible(False)
        mw_layout = QHBoxLayout(self.magic_wand_panel)
        mw_layout.setContentsMargins(0, 0, 0, 0)
        mw_layout.setSpacing(4)

        # 新增按钮也遵循全局 QPushButton 样式（自动撑开尺寸） 3/2
        self.btn_expand = self._create_tool_btn(
            "btn_expand", "保存", tip_config=tips["expand"]
        )
        self.btn_shrink = self._create_tool_btn(
            "btn_shrink", "保存", tip_config=tips["shrink"]
        )
        self.btn_invert = self._create_tool_btn(
            "btn_invert", "保存", tip_config=tips["invert"]
        )

        # 容差滑动条与百分比
        mw_layout.addWidget(QLabel("容差"))

        self.slider_tolerance = QSlider(Qt.Orientation.Horizontal)
        self.slider_tolerance.setRange(0, 255)
        self.slider_tolerance.setValue(25)
        self.slider_tolerance.setFixedWidth(80)
        mw_layout.addWidget(self.slider_tolerance)

        self.lbl_tolerance_val = QLabel("10%")
        self.lbl_tolerance_val.setFixedWidth(35)
        mw_layout.addWidget(self.lbl_tolerance_val)

        self.check_contiguous = QCheckBox("连续")
        mw_layout.addWidget(self.check_contiguous)

        mw_layout.addSpacing(20)
        mw_layout.addWidget(self.btn_expand)
        mw_layout.addWidget(self.btn_shrink)
        mw_layout.addWidget(self.btn_invert)
        mw_layout.addStretch()

        toolbar_layout.addWidget(self.magic_wand_panel)
        layout.addWidget(self.toolbar)

        # 内容区 (严格保持你提供的代码，不改动任何尺寸)
        content_layout = QHBoxLayout()
        self.frame_list = QListWidget()
        self.frame_list.setFixedWidth(82)
        self.frame_list.setViewMode(QListWidget.IconMode)
        self.frame_list.setResizeMode(QListWidget.Adjust)
        self.frame_list.setMovement(QListWidget.Static)
        self.frame_list.setIconSize(QSize(48, 48))
        # 使 Item 占满整个列表宽度，消除右侧留白（隐藏滚动条后会看到空白）
        self.frame_list.setGridSize(QSize(82, 80))
        self.frame_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frame_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.frame_list.verticalScrollBar().setFixedWidth(0)
        self.frame_list.verticalScrollBar().setStyleSheet("width: 0px; height: 0px;")

        # 2. 右侧垂直容器
        right_main_layout = QVBoxLayout()
        right_main_layout.setSpacing(0)
        right_main_layout.setContentsMargins(0, 0, 0, 0)

        content_layout.addWidget(self.frame_list, 0)
        # 3. 画布布局
        self.canvas_layout = QVBoxLayout()
        self.canvas_layout.setSpacing(0)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        right_main_layout.addLayout(self.canvas_layout)
        content_layout.addLayout(self.canvas_layout, 1)
        # 4. 底部状态栏容器 (解决黑线的关键样式)
        self.status_bar = QFrame()
        self.status_bar.setFixedHeight(26)
        # 使用 border-top 代替 border，且强制设为 0px 或指定颜色，消除系统自动生成的黑边
        self.status_bar.setStyleSheet("""
            QFrame {
                background-color: #21252b; 
                border: none;
                border-top: 1px solid #181a1f; /* 这里的颜色要比背景深，模拟刻痕感而非脏黑线 */
            }
            QLabel {
                color: #5c6370; /* 灰蓝色文字，不刺眼 */
                font-size: 11px;
                font-family: 'Consolas', 'Monaco', monospace;
                padding: 0 8px;
                border: none; /* 确保 Label 内部没边框 */
            }
        """)

        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(10, 0, 10, 0)
        status_layout.setSpacing(0)

        # --- 添加多个资源信息 Label ---
        self.lbl_frame_index = QLabel("帧: 0/0")
        self.lbl_frame_size = QLabel("尺寸: 0 x 0")
        self.lbl_res_name = QLabel("资源: --")  # 显示当前文件名
        self.lbl_zoom = QLabel("100%")  # 缩放比例

        # 依次排列
        status_layout.addWidget(self.lbl_frame_index)
        status_layout.addWidget(self._create_v_line())  # 添加竖向分割线
        status_layout.addWidget(self.lbl_frame_size)
        status_layout.addWidget(self._create_v_line())
        status_layout.addWidget(self.lbl_res_name)

        status_layout.addStretch()  # 弹簧

        right_main_layout.addWidget(self.status_bar)
        content_layout.addLayout(right_main_layout)
        layout.addLayout(content_layout)

    def _create_v_line(self):
        """创建一个精致的垂直分割线"""
        line = QFrame()
        line.setFixedWidth(1)
        line.setFixedHeight(12)
        line.setStyleSheet("background-color: #3e4451;")
        return line

    # def _create_tool_btn(self, icon_name, tip, checkable=False):
    #     btn = QPushButton()
    #     btn.setToolTip(tip)
    #     # 注意图标路径可能需要调整
    #     icon_path = os.path.join("assets", "icons", f"{icon_name}.svg")
    #     if os.path.exists(icon_path):
    #         btn.setIcon(QIcon(icon_path))
    #     btn.setIconSize(QSize(16, 16))
    #     btn.setCheckable(checkable)
    #     return btn

    def _create_tool_btn(self, name, text, checkable=False, tip_config=None):
        """
        通用的工具栏按钮工厂：优先加载图标，无图标则显示文字
        """
        btn = QPushButton()
        btn.setObjectName(name)

        # --- 核心逻辑：加载图标 ---
        # 假设你的图标文件名和传入的 name 一致 (比如 btn_save 对应 btn_save.svg)
        # 或者你也可以根据需要修改这里的映射关系
        icon_rel_path = f"assets/icons/{name}.svg"
        icon_path = get_resource_path(icon_rel_path)

        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
            btn.setIconSize(QSize(18, 18))  # 稍微大一点点，看起来更清晰
        else:
            # 如果没找到图标，才显示文字作为备选
            btn.setText(text)

        if checkable:
            btn.setCheckable(True)

        # 绑定富文本 ToolTip
        if tip_config:
            title = tip_config.get("title", "")
            desc = tip_config.get("desc", "")
            shortcuts = tip_config.get("shortcuts", [])
            rich_tooltip = self._make_rich_tip(title, desc, shortcuts)
            btn.setToolTip(rich_tooltip)

        btn.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)

        # 让 tooltip 更友好地跟随按钮位置
        if not hasattr(self, "_tooltip_filter"):
            self._tooltip_filter = _ToolTipEventFilter()
        btn.installEventFilter(self._tooltip_filter)

        return btn

    def _make_rich_tip(self, title, desc, shortcuts=None):
        """
        最终修正版：确保背景完全连贯，消除空隙
        """
        # 这里的 background-color 和 border 决定了整个提示框的外观
        html = f"""
        <div style="background-color: #21252b; 
                    border: 1px solid #61afef; 
                    border-radius: 4px; 
                    padding: 8px;
                    min-width: 160px;">
            <div style="color: #61afef; font-size: 13px; font-weight: bold; margin-bottom: 4px;">
                {title}
            </div>
            <div style="color: #abb2bf; font-size: 11px; margin-bottom: 0px;">
                {desc}
            </div>
        """

        if shortcuts and len(shortcuts) > 0:
            # 这里的分割线和表格也会包含在上面的背景 div 中，不会产生断层
            html += '<div style="margin-top: 8px; border-top: 1px solid #3e4451; padding-top: 6px;">'
            html += '<table border="0" cellpadding="0" cellspacing="2" style="width: 100%;">'
            for key, action in shortcuts:
                html += f"""
                <tr>
                    <td style="color: #e5c07b; font-weight: bold; font-size: 11px; padding-right: 12px; white-space: nowrap;">{key}</td>
                    <td style="color: #98c379; font-size: 11px;">{action}</td>
                </tr>
                """
            html += "</table></div>"

        html += "</div>"
        return html

    def get_tool_configs(self):
        return {
            "new_file": {
                "title": "新建资源",
                "desc": "清空当前工作区并开始新项目",
                # 这里不写 shortcuts，逻辑会自动处理
            },
            "save": {
                "title": "保存资源",
                "desc": "将当前编辑的帧保存到资源库",
                "shortcuts": [("Ctrl+S", "快速保存")],  # 只有保存有快捷键
            },
            "magic_wand": {
                "title": "魔术棒工具",
                "desc": "快速选取相似颜色的像素",
                "shortcuts": [
                    ("单击", "选取相似像素"),
                    ("容差", "控制颜色识别范围 (0-255)"),
                    ("连续", "开启仅选取相邻的同色区域"),
                ],
            },
            "pick": {
                "title": "矩形选取框工具",
                "desc": "绘制矩形像素选择",
                "shortcuts": [
                    ("左键拖动", "创建新的矩形选区"),
                    ("Ctrl+拖动", "移动当前选区位置"),
                    ("Shift+拖动", "增加选区范围 (并集)"),
                    ("Alt+拖动", "减去选区范围 (差集)"),
                    ("双击", "取消选区"),
                ],
            },
            "cut": {
                "title": "裁切画布",
                "desc": "裁切当前画布内容",
                "shortcuts": [
                    ("拉伸边框", "调整裁切范围"),
                    ("回车", "确认并应用裁切"),
                    ("Esc", "取消当前裁切操作"),
                ],
            },
            "slice": {
                "title": "智能裁切",
                "desc": "将当前资源自动裁切成序列帧",
                # "shortcuts": [("拖动", "创建裁切框"), ("Ctrl+拖动", "移动裁切框")],
            },
            "transform": {
                "title": "变换工具",
                "desc": "对图像进行变换操作",
                "shortcuts": [("点击", "打开变换面板")],
            },
            "expand": {
                "title": "扩展选区",
                "desc": "将选区向外扩展一个像素",
                "shortcuts": [("点击", "扩展选区")],
            },
            "shrink": {
                "title": "收缩选区",
                "desc": "将选区向内收缩一个像素",
                "shortcuts": [("点击", "收缩选区")],
            },
            "invert": {
                "title": "反转选区",
                "desc": "将当前选区反转，选中未选中的像素，取消选中已选中的像素",
                "shortcuts": [("点击", "反转选区")],
            },
        }
