"""实例模型：一个实例 = 一个版本 + 独立的游戏目录（版本隔离）。"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .. import paths

INSTANCES_FILE = "instances.json"


@dataclass
class Instance:
    id: str
    name: str
    version_id: str
    loader: str = "vanilla"
    game_dir: str = ""
    created: float = field(default_factory=time.time)
    last_played: float = 0.0
    playtime: int = 0
    icon: str = ""

    @property
    def path(self) -> Path:
        return Path(self.game_dir) if self.game_dir else Path(".")

    def mods_dir(self) -> Path:
        p = self.path / "mods"
        p.mkdir(parents=True, exist_ok=True)
        return p


class InstanceStore:
    def __init__(self) -> None:
        self._file = paths.app_dir() / INSTANCES_FILE
        self.items: list[Instance] = []
        self.load()

    def load(self) -> None:
        self.items = []
        if not self._file.exists():
            return
        try:
            raw = json.loads(self._file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for item in raw if isinstance(raw, list) else []:
            try:
                self.items.append(Instance(**item))
            except TypeError:
                continue

    def save(self) -> None:
        try:
            self._file.write_text(
                json.dumps([asdict(i) for i in self.items], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def get(self, instance_id: str) -> Instance | None:
        for i in self.items:
            if i.id == instance_id:
                return i
        return None

    def add(self, instance: Instance) -> Instance:
        if self.get(instance.id):
            instance.id = f"{instance.id}-{int(time.time())}"
        self.items.append(instance)
        self.save()
        return instance

    def remove(self, instance_id: str) -> None:
        self.items = [i for i in self.items if i.id != instance_id]
        self.save()

    def touch(self, instance_id: str, playtime: int = 0) -> None:
        inst = self.get(instance_id)
        if inst:
            inst.last_played = time.time()
            inst.playtime += playtime
            self.save()

    def for_version(self, version_id: str) -> Instance | None:
        for i in self.items:
            if i.version_id == version_id:
                return i
        return None
