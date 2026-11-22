"""加载器安装：Fabric / Quilt / NeoForge / Forge。

Fabric、Quilt 走官方 meta 直接拿 profile JSON，天然带 inheritsFrom，落盘即可启动；
NeoForge、Forge 必须跑官方 installer，安装完成后回读 versions 目录确认产出。
"""
from __future__ import annotations

import json
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Callable

from . import install as installer
from . import java as javacore
from . import meta, net

Progress = Callable[[str, int, int], None]

FABRIC_META = "https://meta.fabricmc.net/v2"
QUILT_META = "https://meta.quiltmc.org/v3"
NEOFORGE_MAVEN = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
NEOFORGE_FORGE_MAVEN = "https://maven.neoforged.net/releases/net/neoforged/forge/maven-metadata.xml"
FORGE_MAVEN = "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"

LOADER_LABEL = {
    "vanilla": "原版",
    "fabric": "Fabric",
    "quilt": "Quilt",
    "neoforge": "NeoForge",
    "forge": "Forge",
}


def _noop(stage: str, done: int, total: int) -> None:
    pass


def _get_json(url: str, timeout: float = 40.0) -> Any:
    with net.client(timeout) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.json()


def _get_text(url: str, timeout: float = 40.0) -> str:
    with net.client(timeout) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.text


def _download(url: str, dest: Path) -> Path:
    """统一走并发下载内核（多线程 + 断点续传）。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    downloader = net.Downloader("auto")
    _total, failures = downloader.run([net.DownloadTask(url, dest)])
    if failures and not dest.exists():
        raise RuntimeError(failures[0][1])
    return dest


def _maven_versions(xml: str) -> list[str]:
    return re.findall(r"<version>([^<]+)</version>", xml)


def _write_version_json(mc_dir: Path, version_id: str, data: dict) -> Path:
    vdir = mc_dir / "versions" / version_id
    vdir.mkdir(parents=True, exist_ok=True)
    target = vdir / f"{version_id}.json"
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _version_ids(mc_dir: Path) -> set[str]:
    root = mc_dir / "versions"
    if not root.exists():
        return set()
    return {d.name for d in root.iterdir() if d.is_dir()}


def ensure_vanilla(
    mc_dir: Path,
    game_version: str,
    manifest: meta.VersionManifest,
    mirror: str = "auto",
    on_progress: Progress | None = None,
) -> bool:
    """父版本必须完整装好，否则加载器启动了也会缺资源。"""
    on_progress = on_progress or _noop
    vdir = mc_dir / "versions" / game_version
    if (vdir / f"{game_version}.json").exists() and (vdir / f"{game_version}.jar").exists():
        return True
    on_progress(f"安装原版 {game_version}", 0, 1)
    try:
        installer.install(mc_dir, game_version, manifest, mirror=mirror, on_progress=on_progress)
    except Exception:
        return False
    return (vdir / f"{game_version}.jar").exists()


# --------------------------------------------------------------- Fabric / Quilt
def fabric_loaders(game_version: str) -> list[dict]:
    data = _get_json(f"{FABRIC_META}/versions/loader/{game_version}")
    out = []
    for item in data or []:
        loader = item.get("loader") or {}
        out.append({
            "version": loader.get("version", ""),
            "stable": bool(loader.get("stable")),
            "intermediary": (item.get("intermediary") or {}).get("version", ""),
        })
    return out


def quilt_loaders(game_version: str) -> list[dict]:
    data = _get_json(f"{QUILT_META}/versions/loader/{game_version}")
    out = []
    for item in data or []:
        loader = item.get("loader") or {}
        out.append({"version": loader.get("version", ""), "stable": True})
    return out


def install_fabric(
    mc_dir: Path,
    game_version: str,
    manifest: meta.VersionManifest,
    loader_version: str = "",
    mirror: str = "auto",
    on_progress: Progress | None = None,
) -> str:
    on_progress = on_progress or _noop
    on_progress("获取 Fabric 元数据", 0, 1)
    if not loader_version:
        versions = fabric_loaders(game_version)
        stable = [v for v in versions if v["stable"]]
        pick = (stable or versions)[0] if (stable or versions) else None
        if not pick:
            raise RuntimeError(f"Fabric 未提供 {game_version} 的加载器")
        loader_version = pick["version"]
    url = f"{FABRIC_META}/versions/loader/{game_version}/{loader_version}/profile/json"
    data = _get_json(url)
    version_id = data.get("id") or f"fabric-loader-{loader_version}-{game_version}"
    data["id"] = version_id
    data.setdefault("inheritsFrom", game_version)

    ensure_vanilla(mc_dir, game_version, manifest, mirror, on_progress)
    _write_version_json(mc_dir, version_id, data)

    # profile 里的库仍要下载
    on_progress("下载 Fabric 依赖库", 0, 1)
    tasks, _libs, _index = installer.plan(mc_dir, version_id, data, mirror)
    if tasks:
        downloader = net.Downloader(mirror, 16)
        downloader.run(tasks, lambda done, total, _n: on_progress("下载 Fabric 依赖库", done, total))
    on_progress("Fabric 安装完成", 1, 1)
    return version_id


def install_quilt(
    mc_dir: Path,
    game_version: str,
    manifest: meta.VersionManifest,
    loader_version: str = "",
    mirror: str = "auto",
    on_progress: Progress | None = None,
) -> str:
    on_progress = on_progress or _noop
    on_progress("获取 Quilt 元数据", 0, 1)
    if not loader_version:
        versions = quilt_loaders(game_version)
        if not versions:
            raise RuntimeError(f"Quilt 未提供 {game_version} 的加载器")
        loader_version = versions[0]["version"]
    url = f"{QUILT_META}/versions/loader/{game_version}/{loader_version}/profile/json"
    data = _get_json(url)
    version_id = data.get("id") or f"quilt-loader-{loader_version}-{game_version}"
    data["id"] = version_id
    data.setdefault("inheritsFrom", game_version)

    ensure_vanilla(mc_dir, game_version, manifest, mirror, on_progress)
    _write_version_json(mc_dir, version_id, data)

    on_progress("下载 Quilt 依赖库", 0, 1)
    tasks, _libs, _index = installer.plan(mc_dir, version_id, data, mirror)
    if tasks:
        downloader = net.Downloader(mirror, 16)
        downloader.run(tasks, lambda done, total, _n: on_progress("下载 Quilt 依赖库", done, total))
    on_progress("Quilt 安装完成", 1, 1)
    return version_id


# --------------------------------------------------------------- NeoForge / Forge
def neoforge_prefix(game_version: str) -> str | None:
    m = re.match(r"1\.(\d+)(?:\.(\d+))?", game_version)
    if not m:
        return None
    minor = int(m.group(1))
    patch = int(m.group(2) or 0)
    if minor < 20:
        return None
    return f"{minor}.{patch}."


def neoforge_versions(game_version: str) -> list[str]:
    prefix = neoforge_prefix(game_version)
    if not prefix:
        return []
    for url in (NEOFORGE_MAVEN, NEOFORGE_FORGE_MAVEN):
        try:
            allv = _maven_versions(_get_text(url))
        except Exception:
            continue
        hits = [v for v in allv if v.startswith(prefix)]
        if hits:
            hits.sort(key=lambda s: [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", s) if x])
            return hits
    return []


def forge_versions(game_version: str) -> list[str]:
    try:
        allv = _maven_versions(_get_text(FORGE_MAVEN))
    except Exception:
        return []
    hits = [v for v in allv if v.startswith(game_version + "-")]
    hits.sort(key=lambda s: [int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", s) if x])
    return hits


def _pick_java(major: int) -> str | None:
    runtimes = javacore.discover()
    rt = javacore.pick(runtimes, major)
    return rt.path if rt else None


def _run_installer(jar: Path, mc_dir: Path, java_path: str, on_progress: Progress) -> bool:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    cmd = [java_path, "-jar", str(jar), "--installClient", str(mc_dir)]
    tail: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
            cwd=str(mc_dir),
        )
    except OSError:
        return False
    if proc.stdout is not None:
        for line in proc.stdout:
            text = line.strip()
            if not text:
                continue
            tail.append(text)
            if len(tail) > 4:
                tail.pop(0)
            on_progress("运行 " + " / ".join(tail[-2:])[:120], 0, 1)
    proc.wait()
    return proc.returncode == 0


def install_neoforge(
    mc_dir: Path,
    game_version: str,
    manifest: meta.VersionManifest,
    loader_version: str = "",
    mirror: str = "auto",
    on_progress: Progress | None = None,
) -> str:
    on_progress = on_progress or _noop
    on_progress("查询 NeoForge 版本", 0, 1)
    versions = neoforge_versions(game_version)
    if not versions:
        raise RuntimeError(f"NeoForge 未提供 {game_version} 的构建")
    if not loader_version:
        loader_version = versions[-1]

    major = javacore.fallback_major(game_version)
    java_path = _pick_java(major)
    if not java_path:
        raise RuntimeError(f"运行 NeoForge 安装器需要 Java {major}，请先在设置中获取")

    ensure_vanilla(mc_dir, game_version, manifest, mirror, on_progress)

    prefix = neoforge_prefix(game_version) or ""
    group = "net/neoforged/neoforge" if versions and versions[0].startswith(prefix) else "net/neoforged/forge"
    base = "https://maven.neoforged.net/releases"
    jar_name = f"neoforge-{loader_version}-installer.jar" if group.endswith("neoforge") else f"forge-{loader_version}-installer.jar"
    url = f"{base}/{group}/{loader_version}/{jar_name}"
    dest = net_path_cache(jar_name)

    before = _version_ids(mc_dir)
    on_progress("下载 NeoForge 安装器", 0, 1)
    _download(url, dest)
    on_progress("执行 NeoForge 安装器", 0, 1)
    ok = _run_installer(dest, mc_dir, java_path, on_progress)
    added = _version_ids(mc_dir) - before
    if not ok and not added:
        raise RuntimeError("NeoForge 安装器执行失败，详见运行日志")
    target = ""
    for name in added:
        if "neoforge" in name.lower():
            target = name
            break
    if not target:
        for name in added:
            target = name
            break
    if not target:
        raise RuntimeError("NeoForge 安装器未产出新版本")
    on_progress("NeoForge 安装完成", 1, 1)
    return target


def install_forge(
    mc_dir: Path,
    game_version: str,
    manifest: meta.VersionManifest,
    loader_version: str = "",
    mirror: str = "auto",
    on_progress: Progress | None = None,
) -> str:
    on_progress = on_progress or _noop
    on_progress("查询 Forge 版本", 0, 1)
    versions = forge_versions(game_version)
    if not versions:
        raise RuntimeError(f"Forge 未提供 {game_version} 的构建")
    if not loader_version:
        loader_version = versions[-1]
    if not loader_version.startswith(game_version + "-"):
        loader_version = f"{game_version}-{loader_version}"

    major = 8 if game_version.startswith("1.12") or game_version.startswith("1.8") else javacore.fallback_major(game_version)
    java_path = _pick_java(major)
    if not java_path:
        raise RuntimeError(f"运行 Forge 安装器需要 Java {major}，请先在设置中获取")

    ensure_vanilla(mc_dir, game_version, manifest, mirror, on_progress)

    url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{loader_version}/forge-{loader_version}-installer.jar"
    dest = net_path_cache(f"forge-{loader_version}-installer.jar")

    before = _version_ids(mc_dir)
    on_progress("下载 Forge 安装器", 0, 1)
    _download(url, dest)
    on_progress("执行 Forge 安装器", 0, 1)
    ok = _run_installer(dest, mc_dir, java_path, on_progress)
    added = _version_ids(mc_dir) - before
    if not ok and not added:
        raise RuntimeError("Forge 安装器执行失败，详见运行日志")
    target = next((n for n in added if "forge" in n.lower()), "")
    if not target and added:
        target = next(iter(added))
    if not target:
        target = loader_version
    on_progress("Forge 安装完成", 1, 1)
    return target


def net_path_cache(name: str) -> Path:
    from .. import paths

    return paths.cache_dir() / name


# ------------------------------------------------------------------ 统一入口
def list_versions(loader: str, game_version: str) -> list[str]:
    if loader == "fabric":
        return [v["version"] for v in fabric_loaders(game_version)]
    if loader == "quilt":
        return [v["version"] for v in quilt_loaders(game_version)]
    if loader == "neoforge":
        return neoforge_versions(game_version)
    if loader == "forge":
        return [v[len(game_version) + 1:] for v in forge_versions(game_version)]
    return []


def install_loader(
    mc_dir: Path,
    game_version: str,
    loader: str,
    manifest: meta.VersionManifest,
    loader_version: str = "",
    mirror: str = "auto",
    on_progress: Progress | None = None,
) -> str:
    """安装加载器，返回可启动的版本 id；vanilla 直接装原版。"""
    on_progress = on_progress or _noop
    if loader in ("", "vanilla"):
        if not ensure_vanilla(mc_dir, game_version, manifest, mirror, on_progress):
            raise RuntimeError(f"{game_version} 原版安装未完成")
        return game_version
    if loader == "fabric":
        return install_fabric(mc_dir, game_version, manifest, loader_version, mirror, on_progress)
    if loader == "quilt":
        return install_quilt(mc_dir, game_version, manifest, loader_version, mirror, on_progress)
    if loader == "neoforge":
        return install_neoforge(mc_dir, game_version, manifest, loader_version, mirror, on_progress)
    if loader == "forge":
        return install_forge(mc_dir, game_version, manifest, loader_version, mirror, on_progress)
    raise RuntimeError(f"未知加载器：{loader}")


def detect_loader(version_id: str) -> tuple[str, str]:
    """从版本 id 反推 (加载器, 原版版本号)。"""
    low = version_id.lower()
    m = re.match(r"fabric-loader-([^-]+)-(.+)", version_id)
    if m:
        return "fabric", m.group(2)
    m = re.match(r"quilt-loader-([^-]+)-(.+)", version_id)
    if m:
        return "quilt", m.group(2)
    m = re.match(r"neoforge-([\d.]+)", version_id)
    if m:
        ver = m.group(1).split("-")[0]
        parts = ver.split(".")
        if len(parts) >= 2 and parts[0].isdigit():
            return "neoforge", f"1.{parts[0]}.{parts[1]}"
    if "forge" in low:
        m = re.match(r"(\d+\.\d+(?:\.\d+)?)-", version_id)
        if m:
            return "forge", m.group(1)
    return "vanilla", version_id
