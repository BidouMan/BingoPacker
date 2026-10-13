# -*- mode: python ; coding: utf-8 -*-
"""跨平台 PyInstaller 打包配置（macOS / Windows 共用）。

用法：
    BINGO_APP_NAME=BingoPacker BINGO_APP_VERSION=1.0.1 pyinstaller --noconfirm --clean BingoPacker.spec

环境变量（都有默认值，便于本地直接跑）：
    BINGO_APP_NAME       产物名，默认 BingoPacker
    BINGO_APP_VERSION    macOS 包里的 CFBundleShortVersionString，默认 0.0.0
    BINGO_BUNDLE_ID      macOS bundle identifier，默认 com.bingopacker.app
"""

import os
import sys

APP_NAME = os.environ.get("BINGO_APP_NAME", "BingoPacker")
APP_VERSION = os.environ.get("BINGO_APP_VERSION", "0.0.0")
BUNDLE_ID = os.environ.get("BINGO_BUNDLE_ID", "com.bingopacker.app")

# PyInstaller 会把本 spec 所在目录暴露为 SPECPATH（见 build_main.py 的 spec_namespace）
ROOT = SPECPATH

# 各平台的应用图标：Windows 必须是 .ico，macOS 用 .icns
if sys.platform == "win32":
    ICON = os.path.join(ROOT, "assets", "icons", "logo_win.ico")
elif sys.platform == "darwin":
    ICON = os.path.join(ROOT, "assets", "icons", "logo.icns")
else:
    ICON = os.path.join(ROOT, "assets", "icons", "logo.png")

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    # src/utils.py 的 get_resource_path() 通过 sys._MEIPASS 定位 assets，
    # 所以这里必须把 assets/ 原样放进包的根，不能改名或换层级。
    datas=[(os.path.join(ROOT, "assets"), "assets")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # CI runner 上没有 UPX，且 UPX 压缩 Qt 动态库偶发崩溃，这里关掉更稳
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ICON],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

# BUNDLE 只在 macOS 上生效（生成 dist/BingoPacker.app）
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=ICON,
        bundle_identifier=BUNDLE_ID,
        info_plist={
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
            "LSApplicationCategoryType": "public.app-category.graphics-design",
        },
    )
