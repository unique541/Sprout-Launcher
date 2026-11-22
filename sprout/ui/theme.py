"""主题：语义化 design token，供 QML 通过 theme.xxx 绑定，切换即时生效。"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal
from PySide6.QtGui import QColor

# 语义 token：backgroundColor / surface / accent ... 每套主题只改值不改语义
THEMES: dict[str, dict[str, str]] = {
    "sprout": {
        "label": "嫩芽",
        "bg": "#F4F9F3",
        "surface": "#FFFFFF",
        "surfaceAlt": "#EAF3E7",
        "card": "#FFFFFF",
        "border": "#DCE8D8",
        "accent": "#5FA85C",
        "accentSoft": "#CFE9CB",
        "text1": "#1B2A1A",
        "text2": "#4C5F4A",
        "text3": "#8CA089",
        "glow1": "#B7E3AE",
        "glow2": "#CFE8F5",
        "onAccent": "#FFFFFF",
    },
    "morning": {
        "label": "晨雾",
        "bg": "#F3F6F6",
        "surface": "#FFFFFF",
        "surfaceAlt": "#E8EEEE",
        "card": "#FFFFFF",
        "border": "#DAE3E3",
        "accent": "#4F9C8C",
        "accentSoft": "#CDE7E1",
        "text1": "#17272A",
        "text2": "#4A5D61",
        "text3": "#87999C",
        "glow1": "#BFE3DC",
        "glow2": "#D6E4F2",
        "onAccent": "#FFFFFF",
    },
    "kite": {
        "label": "纸鸢",
        "bg": "#F1F6FA",
        "surface": "#FFFFFF",
        "surfaceAlt": "#E5EFF7",
        "card": "#FFFFFF",
        "border": "#D6E3EF",
        "accent": "#3D8CB5",
        "accentSoft": "#CBE3F1",
        "text1": "#16232E",
        "text2": "#465A6B",
        "text3": "#8698A8",
        "glow1": "#B7DAF0",
        "glow2": "#CDE7E0",
        "onAccent": "#FFFFFF",
    },
    "sakura": {
        "label": "樱",
        "bg": "#FAF5F6",
        "surface": "#FFFFFF",
        "surfaceAlt": "#F5E8EC",
        "card": "#FFFFFF",
        "border": "#EEDAE1",
        "accent": "#C97E96",
        "accentSoft": "#F2D7DF",
        "text1": "#2A1B21",
        "text2": "#5E4A52",
        "text3": "#A08D94",
        "glow1": "#F2CDD9",
        "glow2": "#E4DCF2",
        "onAccent": "#FFFFFF",
    },
    "dusk": {
        "label": "暮色",
        "bg": "#0F1418",
        "surface": "#161D23",
        "surfaceAlt": "#1E272E",
        "card": "#182027",
        "border": "#26333C",
        "accent": "#5FC8A6",
        "accentSoft": "#1F3A34",
        "text1": "#E8F0F2",
        "text2": "#A7B8BF",
        "text3": "#6C7F87",
        "glow1": "#1B4A43",
        "glow2": "#1B3348",
        "onAccent": "#06201A",
    },
}

TOKENS = (
    "bg", "surface", "surfaceAlt", "card", "border",
    "accent", "accentSoft", "text1", "text2", "text3",
    "glow1", "glow2", "onAccent",
)


class ThemeManager(QObject):
    changed = Signal()

    def __init__(self, current: str = "sprout") -> None:
        super().__init__()
        self._name = current if current in THEMES else "sprout"

    # --- 通用访问 ---
    def _color(self, token: str) -> QColor:
        return QColor(THEMES[self._name][token])

    @Property(str, notify=changed)
    def name(self) -> str:
        return self._name

    @Property(str, notify=changed)
    def label(self) -> str:
        return THEMES[self._name]["label"]

    @Property(bool, notify=changed)
    def dark(self) -> bool:
        return self._name == "dusk"

    @Property("QVariantList", notify=changed)
    def available(self) -> list[dict]:
        return [{"id": k, "label": v["label"], "accent": v["accent"]} for k, v in THEMES.items()]

    def set_theme(self, name: str) -> None:
        if name in THEMES and name != self._name:
            self._name = name
            self.changed.emit()

    # --- 颜色 token（必须显式声明，QML 才能绑定） ---
    @Property(QColor, notify=changed)
    def bg(self) -> QColor:
        return self._color("bg")

    @Property(QColor, notify=changed)
    def surface(self) -> QColor:
        return self._color("surface")

    @Property(QColor, notify=changed)
    def surfaceAlt(self) -> QColor:
        return self._color("surfaceAlt")

    @Property(QColor, notify=changed)
    def card(self) -> QColor:
        return self._color("card")

    @Property(QColor, notify=changed)
    def border(self) -> QColor:
        return self._color("border")

    @Property(QColor, notify=changed)
    def accent(self) -> QColor:
        return self._color("accent")

    @Property(QColor, notify=changed)
    def accentSoft(self) -> QColor:
        return self._color("accentSoft")

    @Property(QColor, notify=changed)
    def text1(self) -> QColor:
        return self._color("text1")

    @Property(QColor, notify=changed)
    def text2(self) -> QColor:
        return self._color("text2")

    @Property(QColor, notify=changed)
    def text3(self) -> QColor:
        return self._color("text3")

    @Property(QColor, notify=changed)
    def glow1(self) -> QColor:
        return self._color("glow1")

    @Property(QColor, notify=changed)
    def glow2(self) -> QColor:
        return self._color("glow2")

    @Property(QColor, notify=changed)
    def onAccent(self) -> QColor:
        return self._color("onAccent")
