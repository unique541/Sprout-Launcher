"""应用目录定位与创建。"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Sprout"


def app_dir() -> Path:
    """应用数据目录：%APPDATA%\\Sprout"""
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME") or str(Path.home())
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def runtimes_dir() -> Path:
    p = app_dir() / "runtimes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    p = app_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def meta_cache_dir() -> Path:
    p = cache_dir() / "meta"
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_dir() -> Path:
    p = app_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def config_file() -> Path:
    return app_dir() / "config.json"


def default_minecraft_dir() -> Path:
    return Path(os.environ.get("APPDATA", str(Path.home()))) / ".minecraft"


def minecraft_candidates() -> list[Path]:
    """枚举可能的 .minecraft 目录，用于「多份目录」场景下的智能探测。"""
    cands: list[Path] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        cands.append(Path(appdata) / ".minecraft")
    cands.append(Path.home() / ".minecraft")
    for drive in ("C:", "D:", "E:"):
        p = Path(drive + "\\") / "minecraft"
        if p.exists():
            cands.append(p)
    seen: set[str] = set()
    uniq: list[Path] = []
    for c in cands:
        key = str(c).lower()
        if key not in seen and c.exists():
            seen.add(key)
            uniq.append(c)
    return uniq


def score_minecraft_dir(path: Path) -> int:
    """给候选目录打分：完整性越高分越高。

    判定依据：launcher_profiles.json 归属、libraries 体积、versions 数量。
    这是为了避免「多份 .minecraft 导致误报某加载器未安装」的老问题。
    """
    score = 0
    if (path / "launcher_profiles.json").exists():
        score += 40
    if (path / "versions").is_dir():
        try:
            score += min(len([d for d in (path / "versions").iterdir() if d.is_dir()]), 10)
        except OSError:
            pass
    libs = path / "libraries"
    if libs.is_dir():
        total = 0
        for root, _dirs, files in os.walk(libs):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
            if total > 800 * 1024 * 1024:
                break
        score += min(total // (50 * 1024 * 1024), 40)
    return score
