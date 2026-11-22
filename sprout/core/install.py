"""版本安装：客户端、依赖库、资源文件、natives 解压。"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Callable

from . import meta, net
from .net import DownloadTask

Progress = Callable[[str, int, int], None]


def _noop(stage: str, done: int, total: int) -> None:
    pass


def _natives_dirname(lib: dict) -> str | None:
    """旧式 natives 字段：{windows: 'natives-windows-${arch}'}"""
    natives = lib.get("natives") or {}
    key = natives.get("windows") if meta.os_name() == "windows" else natives.get(meta.os_name())
    if not key:
        return None
    arch = "64" if meta.os_arch() == "x86_64" else "32"
    return key.replace("${arch}", arch)


def extract_natives(jar: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(jar) as zf:
            for info in zf.infolist():
                if info.is_dir() or info.filename.startswith("META-INF/"):
                    continue
                target = dest / Path(info.filename).name
                with zf.open(info) as src, target.open("wb") as dst:
                    dst.write(src.read())
    except (OSError, zipfile.BadZipFile):
        pass


def plan(
    mc_dir: Path,
    version_id: str,
    version_data: dict,
    mirror: str,
) -> tuple[list[DownloadTask], list[dict], dict]:
    """生成下载任务：客户端 jar + libraries + assets。"""
    tasks: list[DownloadTask] = []
    libs = list(version_data.get("libraries", []))

    # 版本 JSON 落盘
    vdir = mc_dir / "versions" / version_id
    vdir.mkdir(parents=True, exist_ok=True)

    client = (version_data.get("downloads") or {}).get("client") or {}
    if client.get("url"):
        tasks.append(DownloadTask(client["url"], vdir / f"{version_id}.jar", client.get("sha1", ""), client.get("size", 0)))

    selected: list[dict] = []
    for lib in libs:
        if not meta.rules_allow(lib, {}):
            continue
        selected.append(lib)
        art = (lib.get("downloads") or {}).get("artifact")
        if art and art.get("url"):
            tasks.append(DownloadTask(
                art["url"], mc_dir / "libraries" / art["path"], art.get("sha1", ""), art.get("size", 0)
            ))
            continue
        nkey = _natives_dirname(lib)
        if nkey:
            cls = (lib.get("downloads") or {}).get("classifiers") or {}
            art2 = cls.get(nkey)
            if art2 and art2.get("url"):
                tasks.append(DownloadTask(
                    art2["url"], mc_dir / "libraries" / art2["path"], art2.get("sha1", ""), art2.get("size", 0)
                ))
                continue
        path = meta.artifact_path(lib)
        url = meta.library_url(lib)
        if path and url and not art:
            tasks.append(DownloadTask(url, mc_dir / "libraries" / path))

    # 资源索引
    index = version_data.get("assetIndex") or {}
    index_id = index.get("id") or "legacy"
    index_file = mc_dir / "assets" / "indexes" / f"{index_id}.json"
    if index.get("url"):
        tasks.append(DownloadTask(index["url"], index_file, index.get("sha1", ""), index.get("size", 0)))

    return tasks, selected, index


def install(
    mc_dir: Path,
    version_id: str,
    manifest: meta.VersionManifest,
    mirror: str = "auto",
    concurrency: int = 16,
    on_progress: Progress | None = None,
) -> dict:
    """完整安装一个版本。返回统计信息。"""
    on_progress = on_progress or _noop
    entry = manifest.find(version_id)
    if not entry:
        raise ValueError(f"版本清单中不存在 {version_id}")
    on_progress("解析版本元数据", 0, 1)
    version_data = meta.fetch_version_json(version_id, entry["url"], mirror, force=True)

    tasks, libs, index = plan(mc_dir, version_id, version_data, mirror)

    # 写入版本 JSON（含客户端清单，供后续启动复用）
    vdir = mc_dir / "versions" / version_id
    (vdir / f"{version_id}.json").write_text(
        json.dumps(version_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    downloader = net.Downloader(mirror, concurrency)

    def stage(name: str):
        def cb(done: int, total: int, _current: str) -> None:
            on_progress(name, done, total)
        return cb

    on_progress("下载游戏文件", 0, len(tasks))
    _total, failures = downloader.run(tasks, stage("下载游戏文件"))

    # 资源对象
    index_file = mc_dir / "assets" / "indexes" / f"{index.get('id', 'legacy')}.json"
    asset_tasks: list[DownloadTask] = []
    if index_file.exists():
        try:
            assets = json.loads(index_file.read_text(encoding="utf-8")).get("objects", {})
        except (OSError, ValueError):
            assets = {}
        for _name, obj in assets.items():
            h = obj.get("hash", "")
            if len(h) < 2:
                continue
            asset_tasks.append(DownloadTask(
                f"https://resources.download.minecraft.net/{h[:2]}/{h}",
                mc_dir / "assets" / "objects" / h[:2] / h,
                h,
                obj.get("size", 0),
            ))
    if asset_tasks:
        on_progress("下载资源文件", 0, len(asset_tasks))
        _t2, f2 = downloader.run(asset_tasks, stage("下载资源文件"))
        failures += f2

    # natives 解压
    on_progress("解压运行库", 0, 1)
    natives_dir = vdir / "natives"
    natives_dir.mkdir(parents=True, exist_ok=True)
    for lib in libs:
        art = (lib.get("downloads") or {}).get("artifact")
        nkey = _natives_dirname(lib)
        jar_path: Path | None = None
        if nkey:
            cls = (lib.get("downloads") or {}).get("classifiers") or {}
            a = cls.get(nkey) or {}
            if a.get("path"):
                jar_path = mc_dir / "libraries" / a["path"]
        elif art and "natives-" in (lib.get("name") or ""):
            jar_path = mc_dir / "libraries" / art["path"]
        if jar_path and jar_path.exists():
            extract_natives(jar_path, natives_dir)

    # legacy 资源目录
    if (version_data.get("assetIndex") or {}).get("virtual") or version_data.get("assets") == "pre-1.6":
        virtual = mc_dir / "assets" / "virtual" / (index.get("id") or "legacy")
        if assets and not virtual.exists():
            on_progress("整理旧版资源", 0, 1)
            for name, obj in assets.items():
                h = obj.get("hash", "")
                src = mc_dir / "assets" / "objects" / h[:2] / h
                dst = virtual / name
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        dst.write_bytes(src.read_bytes())
                    except OSError:
                        pass

    on_progress("安装完成", 1, 1)
    return {
        "version": version_id,
        "files": len(tasks),
        "assets": len(asset_tasks),
        "failures": failures[:20],
        "failed_count": len(failures),
    }
