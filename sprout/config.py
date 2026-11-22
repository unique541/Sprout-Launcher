"""配置读写（JSON 平铺，带默认值合并）。"""
from __future__ import annotations

import json
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    "mc_dir": "",              # 游戏根目录，空表示使用默认
    "mirror": "auto",          # auto / official / bmclapi / fastmc
    "theme": "sprout",         # morning / sprout / kite / sakura / dusk / auto
    "layout": "sidebar",       # sidebar / topbar / minimal
    "concurrency": 16,         # 下载线程数（10~64，默认 16）
    "mod_source": "modrinth",  # 模组来源：modrinth / curseforge
    "cf_api_key": "",          # CurseForge API Key（Core 版需自备）
    "java_path": "",           # 手动指定 Java，空表示自动
    "memory_mb": 0,            # 0 表示自动推荐
    "jvm_args": "",
    "fullscreen": False,
    "animate": True,
    "extra_dirs": [],          # 用户手动添加的额外游戏目录（.minecraft 根）
    "accel_github": False,     # 工具箱：GitHub 加速开关
    "accel_github_mirror": "ghfast",  # 使用的 GitHub 镜像
    "accel_steam": False,      # 工具箱：Steam 加速开关
    "accel_steam_region": "cn",  # Steam 加速区域：cn / hk / us
    "mem_scope": "player",     # 内存优化范围：player / all-user
}


class Config:
    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        f = paths.config_file()
        if f.exists():
            try:
                loaded = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data.update(loaded)
            except (OSError, ValueError):
                pass

    def save(self) -> None:
        try:
            paths.config_file().write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    @property
    def mc_dir(self) -> str:
        v = str(self.get("mc_dir") or "").strip()
        if v:
            return v
        return str(paths.default_minecraft_dir())
