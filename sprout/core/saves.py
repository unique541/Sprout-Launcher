"""存档扫描：遍历各游戏目录下的 saves/*/level.dat，解析世界名、版本与最后游玩时间。

用户以前用官方启动器或别的启动器玩过的世界都在 `.minecraft/saves`，
版本隔离的实例则在 `instances/<id>/saves` 或 `versions/<id>/saves`，
所以扫描必须覆盖全部这三类目录，只认启动器自己建的实例会漏掉历史存档。
"""
from __future__ import annotations

import gzip
import struct
import time
from pathlib import Path

_TAG_BYTE = 1
_TAG_SHORT = 2
_TAG_INT = 3
_TAG_LONG = 4
_TAG_FLOAT = 5
_TAG_DOUBLE = 6
_TAG_BYTE_ARRAY = 7
_TAG_STRING = 8
_TAG_LIST = 9
_TAG_COMPOUND = 10
_TAG_INT_ARRAY = 11
_TAG_LONG_ARRAY = 12


class _Reader:
    """按大端序读取 NBT 字节流。"""

    __slots__ = ("data", "pos")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def unpack(self, fmt: str):
        size = struct.calcsize(fmt)
        if self.pos + size > len(self.data):
            raise ValueError("level.dat 截断")
        (value,) = struct.unpack_from(fmt, self.data, self.pos)
        self.pos += size
        return value


def _read_payload(r: _Reader, tag: int):
    if tag == _TAG_BYTE:
        return r.unpack(">b")
    if tag == _TAG_SHORT:
        return r.unpack(">h")
    if tag == _TAG_INT:
        return r.unpack(">i")
    if tag == _TAG_LONG:
        return r.unpack(">q")
    if tag == _TAG_FLOAT:
        return r.unpack(">f")
    if tag == _TAG_DOUBLE:
        return r.unpack(">d")
    if tag == _TAG_BYTE_ARRAY:
        r.take(r.unpack(">i"))
        return b""
    if tag == _TAG_STRING:
        return r.take(r.unpack(">H")).decode("utf-8", "replace")
    if tag == _TAG_LIST:
        item_tag = r.unpack(">b")
        count = r.unpack(">i")
        if item_tag == 0 or count <= 0:
            return []
        return [_read_payload(r, item_tag) for _ in range(max(0, count))]
    if tag == _TAG_COMPOUND:
        out: dict[str, object] = {}
        while True:
            child = r.unpack(">b")
            if child == 0:
                return out
            name = r.take(r.unpack(">H")).decode("utf-8", "replace")
            out[name] = _read_payload(r, child)
    if tag == _TAG_INT_ARRAY:
        r.take(r.unpack(">i") * 4)
        return []
    if tag == _TAG_LONG_ARRAY:
        r.take(r.unpack(">i") * 8)
        return []
    return None


def read_level_dat(path: Path) -> dict:
    """解析 level.dat（gzip 或未压缩的 NBT），返回 Data 复合标签。失败返回空 dict。"""
    try:
        raw = path.read_bytes()
    except OSError:
        return {}
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError):
            return {}
    try:
        r = _Reader(raw)
        root_tag = r.unpack(">b")
        r.take(r.unpack(">H"))  # 根名称，固定为空串
        root = _read_payload(r, root_tag)
    except (ValueError, struct.error):
        return {}
    if not isinstance(root, dict):
        return {}
    data = root.get("Data")
    return data if isinstance(data, dict) else root


def _dir_size(path: Path) -> int:
    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for item in entries:
            try:
                if item.is_dir() and not item.is_symlink():
                    stack.append(item)
                elif item.is_file():
                    total += item.stat().st_size
            except OSError:
                continue
    return total


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit in ("B", "KB") else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def candidate_roots(mc_dir: Path, extra_dirs: list[tuple[str, str, str, str]] | None = None):
    """收集所有可能存放 saves 的游戏目录。

    extra_dirs 由调用方按实例记录拼出，元素为 (游戏目录, 展示名, 版本号, 实例 id)。
    """
    roots: list[tuple[Path, str, str, str]] = []
    seen: set[str] = set()

    def push(directory: Path, label: str, version_id: str = "", instance_id: str = "") -> None:
        try:
            resolved = str(directory.resolve()).lower()
        except OSError:
            resolved = str(directory).lower()
        if resolved in seen:
            return
        seen.add(resolved)
        roots.append((directory, label, version_id, instance_id))

    mc = Path(mc_dir)
    push(mc, mc.name or ".minecraft")

    instances_root = mc / "instances"
    if instances_root.is_dir():
        try:
            for child in sorted(instances_root.iterdir()):
                if child.is_dir():
                    push(child, f"实例 {child.name}")
        except OSError:
            pass

    versions_root = mc / "versions"
    if versions_root.is_dir():
        try:
            for child in sorted(versions_root.iterdir()):
                if child.is_dir() and (child / "saves").is_dir():
                    push(child, f"版本 {child.name}", child.name)
        except OSError:
            pass

    for directory, label, version_id, instance_id in extra_dirs or []:
        if not directory:
            continue
        path = Path(directory)
        if path.is_dir():
            push(path, label or path.name, version_id, instance_id)
    return roots


def scan_saves(mc_dir: Path, extra_dirs: list | None = None) -> list[dict]:
    """扫描所有候选目录，返回存档列表（按最后游玩时间倒序）。"""
    rows: list[dict] = []
    seen_worlds: set[str] = set()
    for root_dir, label, version_id, instance_id in candidate_roots(Path(mc_dir), extra_dirs):
        saves_dir = root_dir / "saves"
        if not saves_dir.is_dir():
            continue
        try:
            worlds = sorted(saves_dir.iterdir())
        except OSError:
            continue
        for world in worlds:
            try:
                if not world.is_dir():
                    continue
            except OSError:
                continue
            level = world / "level.dat"
            if not level.exists() and not (world / "level.dat_old").exists():
                continue
            try:
                key = str(world.resolve()).lower()
            except OSError:
                key = str(world).lower()
            if key in seen_worlds:
                continue
            seen_worlds.add(key)

            data = read_level_dat(level if level.exists() else world / "level.dat_old")
            version_info = data.get("Version") if isinstance(data.get("Version"), dict) else {}
            last_played_ms = data.get("LastPlayed") or 0
            try:
                last_played = float(last_played_ms) / 1000.0
            except (TypeError, ValueError):
                last_played = 0.0
            if last_played <= 0:
                try:
                    last_played = world.stat().st_mtime
                except OSError:
                    last_played = 0.0

            icon = world / "icon.png"
            rows.append({
                "name": str(data.get("LevelName") or world.name),
                "folder": world.name,
                "path": str(world),
                "gameDir": str(root_dir),
                "source": label,
                "versionId": version_id,
                "instanceId": instance_id,
                "versionName": str(version_info.get("Name") or ""),
                "lastPlayed": last_played,
                "lastPlayedText": time.strftime("%Y-%m-%d %H:%M", time.localtime(last_played)) if last_played else "未知",
                "sizeText": _human_size(_dir_size(world)),
                "iconPath": str(icon) if icon.exists() else "",
            })
    rows.sort(key=lambda r: r["lastPlayed"], reverse=True)
    return rows
