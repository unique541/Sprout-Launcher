# -*- mode: python ; coding: utf-8 -*-
"""Sprout Launcher PyInstaller 配置（onedir / onefile 共用，由 BUILDMODE 控制）。"""
import os
from pathlib import Path

PROJECT = Path(r"C:\Users\1107\AppData\Roaming\Tencent\Marvis\User\4F2AB6C34C0CFCD5E956FF8D4F72A675\workspace\conv_328dc4c900ab41d0a12e1a9a3ccc0115\output\SproutLauncher")
PY_ROOT = Path(r"C:\Users\1107\AppData\Local\Programs\Python\Python314")
QML_ROOT = PY_ROOT / "Lib" / "site-packages" / "PySide6" / "qml"
TRANS = PY_ROOT / "Lib" / "site-packages" / "PySide6" / "translations"
ICON = PROJECT / "assets" / "sprout.ico"
VERSION_FILE = PROJECT / "packaging" / "version_info.txt"

ONEFILE = os.environ.get("SPROUT_ONEFILE", "0") == "1"
CONSOLE = os.environ.get("SPROUT_CONSOLE", "0") == "1"

# QML 同时落两份：源码运行取 sprout/qml；frozen 下 __file__ 指向 _MEIPASS 根，取 qml
datas = [
    (str(PROJECT / "sprout" / "qml"), "sprout/qml"),
    (str(PROJECT / "sprout" / "qml"), "qml"),
    (str(PROJECT / "assets"), "assets"),
]
for mod in ("QtQuick", "QtQml", "QtCore"):
    src = QML_ROOT / mod
    if src.exists():
        datas.append((str(src), "PySide6/qml/" + mod))
for qm in ("qtbase_zh_CN.qm", "qt_zh_CN.qm"):
    p = TRANS / qm
    if p.exists():
        datas.append((str(p), "PySide6/translations"))

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    "PySide6.QtWidgets",
    "sprout",
    "sprout.config",
    "sprout.paths",
    "sprout.core",
    "sprout.core.accounts",
    "sprout.core.diagnose",
    "sprout.core.install",
    "sprout.core.instances",
    "sprout.core.java",
    "sprout.core.launch",
    "sprout.core.loaders",
    "sprout.core.meta",
    "sprout.core.mods",
    "sprout.core.net",
    "sprout.core.p2p",
    "sprout.core.pack",
    "sprout.core.saves",
    "sprout.core.updater",
    "sprout.ui",
    "sprout.ui.bridge",
    "sprout.ui.models",
    "sprout.ui.theme",
    "sprout.services",
    "sprout.services.modrinth",
]

EXCLUDES = [
    "tkinter",
    "PIL",
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick",
    "PySide6.Qt3DCore",
    "PySide6.QtMultimedia",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtBluetooth",
    "PySide6.QtSerialPort",
    "PySide6.QtSql",
    "PySide6.QtTest",
]

a = Analysis(
    [str(PROJECT / "sprout" / "main.py")],
    pathex=[str(PROJECT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=("SproutLauncher_dbg" if CONSOLE else "SproutLauncher"),
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=CONSOLE,
        disable_windowed_traceback=False,
        icon=str(ICON) if ICON.exists() else None,
        version=str(VERSION_FILE) if VERSION_FILE.exists() else None,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=("SproutLauncher_dbg" if CONSOLE else "SproutLauncher"),
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=CONSOLE,
        disable_windowed_traceback=False,
        icon=str(ICON) if ICON.exists() else None,
        version=str(VERSION_FILE) if VERSION_FILE.exists() else None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name=("SproutLauncher_dbg" if CONSOLE else "SproutLauncher"),
    )
