"""Sprout Launcher 入口。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from sprout.ui.bridge import Bridge


def _asset(name: str) -> Path:
    """图标等静态资源：冻结后位于 _MEIPASS，源码运行位于工程 assets。"""
    here = Path(__file__).resolve().parent
    for cand in (here.parent / "assets" / name, here / "assets" / name):
        if cand.exists():
            return cand
    return here.parent / "assets" / name


def _debug_snapshot(app: QApplication, engine: QQmlApplicationEngine, bridge: Bridge) -> None:
    """自检钩子：设置 SPROUT_SHOT=<png 绝对路径> 时，启动后自动截屏写盘并退出。"""
    target = os.environ.get("SPROUT_SHOT", "").strip()
    if not target:
        return
    out = Path(target)

    def _snap() -> None:
        win = engine.rootObjects()[0] if engine.rootObjects() else None
        lines = []
        try:
            installed = list(bridge.installedList or [])
            lines.append("installed=%d" % len(installed))
            lines.append("ids=" + ",".join(str(r.get("id", "")) for r in installed[:6]))
        except Exception as exc:  # noqa: BLE001
            lines.append("installed_err=%r" % (exc,))
        if win is not None:
            lines.append("page=" + str(win.property("currentPage")))
            lines.append("visible=%s" % win.isVisible())
            img = None
            try:
                img = win.grabWindow()
            except Exception:  # noqa: BLE001
                img = None
            if img is None:
                scr = QGuiApplication.primaryScreen()
                if scr is not None:
                    img = scr.grabWindow(int(win.winId()))
            if img is not None:
                out.parent.mkdir(parents=True, exist_ok=True)
                img.save(str(out))
                lines.append("shot=%s %dx%d" % (out.name, img.width(), img.height()))
        try:
            out.with_suffix(".txt").write_text("\n".join(lines), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        print("\n".join(lines), flush=True)
        app.quit()

    QTimer.singleShot(3500, _snap)


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    QQuickStyle.setStyle("Basic")
    app = QApplication(sys.argv)
    app.setApplicationName("Sprout Launcher")
    app.setOrganizationName("Sprout")
    app.setApplicationDisplayName("Sprout Launcher")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    ico = _asset("sprout.ico")
    if ico.exists():
        app.setWindowIcon(QIcon(str(ico)))

    engine = QQmlApplicationEngine()
    bridge = Bridge()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.rootContext().setContextProperty("theme", bridge.theme)

    qml_file = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(str(qml_file))
    if not engine.rootObjects():
        return 1

    bridge.detectJava()
    bridge.refreshVersions()
    # 启动 3 秒后静默检查 GitHub 新版本，有更新才弹窗（不阻塞首屏）
    QTimer.singleShot(3000, bridge.autoCheckUpdate)
    _debug_snapshot(app, engine, bridge)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
