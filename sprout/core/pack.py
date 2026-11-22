"""整合包：.mrpack 导入（建实例 + 装加载器 + 拉文件 + 铺 overrides）与导出。"""
from __future__ import annotations

import json
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Callable

from . import instances, loaders, meta, mods

Progress = Callable[[str, int, int], None]


def _noop(stage: str, done: int, total: int) -> None:
    pass


def _slug(text: str) -> str:
    safe = re.sub(r"[^\w\-.]+", "-", text or "instance", flags=re.UNICODE).strip("-.")
    return (safe or "instance")[:48].lower()


def read_pack(pack_path: Path) -> dict:
    with zipfile.ZipFile(pack_path) as zf:
        if "modrinth.index.json" not in zf.namelist():
            raise RuntimeError("不是有效的 Modrinth 整合包（缺少 modrinth.index.json）")
        raw = zf.read("modrinth.index.json").decode("utf-8", errors="replace")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise RuntimeError("整合包索引格式异常")
    return data


def _pack_loader(deps: dict) -> tuple[str, str]:
    mapping = (
        ("fabric-loader", "fabric"),
        ("quilt-loader", "quilt"),
        ("neoforge", "neoforge"),
        ("forge", "forge"),
    )
    for key, loader in mapping:
        if deps.get(key):
            return loader, str(deps[key])
    return "vanilla", ""


def install_pack(
    pack_path: Path,
    mc_dir: Path,
    manifest: meta.VersionManifest,
    store: instances.InstanceStore,
    mirror: str = "auto",
    on_progress: Progress | None = None,
) -> dict:
    on_progress = on_progress or _noop
    pack_path = Path(pack_path)
    on_progress("读取整合包索引", 0, 1)
    index = read_pack(pack_path)
    deps = index.get("dependencies") or {}
    game_version = str(deps.get("minecraft") or "")
    if not game_version:
        raise RuntimeError("整合包未声明 Minecraft 版本")
    loader, loader_version = _pack_loader(deps)
    title = index.get("name") or pack_path.stem

    on_progress(f"安装 {game_version} {loaders.LOADER_LABEL.get(loader, loader)}", 0, 1)
    version_id = loaders.install_loader(
        mc_dir, game_version, loader, manifest, loader_version, mirror, on_progress
    )

    slug = _slug(title)
    inst_id = slug
    existing = store.get(inst_id)
    if existing:
        inst_id = f"{slug}-{int(time.time())}"
    game_dir = mc_dir / "instances" / inst_id
    game_dir.mkdir(parents=True, exist_ok=True)

    files = index.get("files") or []
    on_progress(f"下载整合包文件（{len(files)} 个）", 0, max(1, len(files)))
    result = mods.import_modpack_files(game_dir, files, on_progress)

    on_progress("解压覆盖文件", 0, 1)
    _extract_overrides(pack_path, game_dir)

    # 把下载下来的 mods 记进台账，便于后续更新检测
    record = mods.load_record(game_dir)
    for f in files:
        path = f.get("path") or ""
        if not path.lower().startswith("mods/"):
            continue
        name = Path(path).name
        target = game_dir / path
        if not target.exists():
            continue
        record.setdefault(name, {
            "file": name,
            "project_id": "",
            "version_id": "",
            "title": Path(name).stem,
            "icon_url": "",
            "source": "modpack",
            "url": (f.get("downloads") or [""])[0],
        })
    mods.save_record(game_dir, record)

    instance = instances.Instance(
        id=inst_id,
        name=title,
        version_id=version_id,
        loader=loader,
        game_dir=str(game_dir),
        icon=index.get("icon") or "",
    )
    store.add(instance)
    on_progress("整合包导入完成", 1, 1)
    return {
        "instance_id": inst_id,
        "name": title,
        "version_id": version_id,
        "loader": loader,
        "files": result.get("total", 0),
        "failures": len(result.get("failures") or []),
    }


def _extract_overrides(pack_path: Path, game_dir: Path) -> None:
    with zipfile.ZipFile(pack_path) as zf:
        for name in zf.namelist():
            for prefix in ("overrides/", "client-overrides/"):
                if name.startswith(prefix) and not name.endswith("/"):
                    rel = name[len(prefix):]
                    if not rel:
                        continue
                    target = game_dir / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, target.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    break


def export_pack(game_dir: Path, out_path: Path, name: str = "", version_id: str = "") -> Path:
    """把实例里的 Modrinth 模组打成一个可再分发的 .mrpack。"""
    game_dir = Path(game_dir)
    out_path = Path(out_path)
    record = mods.load_record(game_dir)
    mod_root = game_dir / "mods"

    files: list[dict] = []
    if mod_root.exists():
        for f in sorted(mod_root.glob("*.jar")):
            info = record.get(f.name) or {}
            url = info.get("url") or ""
            if not url:
                continue
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            files.append({
                "path": f"mods/{f.name}",
                "hashes": {},
                "env": {"client": "required", "server": "required"},
                "downloads": [url],
                "fileSize": size,
            })

    loader = loaders.detect_loader(version_id)[0] if version_id else "vanilla"
    loader_name = {"fabric": "fabric-loader", "quilt": "quilt-loader", "forge": "forge", "neoforge": "neoforge"}.get(loader, "")
    deps: dict[str, str] = {}
    if version_id:
        _kind, vanilla = loaders.detect_loader(version_id)
        deps["minecraft"] = vanilla
        if loader_name:
            m = re.search(r"-([\d.]+)-", version_id) or re.search(r"-(\d+\.\d+\.\d+)", version_id)
            deps[loader_name] = m.group(1) if m else ""

    index = {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": "1.0.0",
        "name": name or game_dir.name,
        "summary": "由 Sprout Launcher 导出",
        "files": files,
        "dependencies": deps,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modrinth.index.json", json.dumps(index, ensure_ascii=False, indent=2))
        for entry in files:
            src = game_dir / entry["path"]
            if src.exists():
                zf.write(src, entry["path"])
    return out_path
