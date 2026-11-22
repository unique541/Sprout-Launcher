"""模组管理：本地扫描、启用/禁用、Modrinth/CurseForge 安装与前置依赖补全、更新检查。

两条铁律（与界面行为一致）：
1. 下载落盘统一为「模组名 + 版本号」；
2. 主文件与其前置依赖都必须严格匹配当前所选游戏版本与模组加载器，
   匹配不到的依赖直接跳过并在 skipped 里说明，绝不装成本体温格不一致的文件。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from ..services.curseforge import CurseForgeClient, CurseForgeError
from ..services.modrinth import ModrinthClient
from . import mod_zh, net
from .net import DownloadTask

Progress = Callable[[str, int, int], None]
RECORD_FILE = ".sprout_mods.json"

_BAD_CHARS = '<>:"/\\|?*'


def _noop(stage: str, done: int, total: int) -> None:
    pass


def _safe_name(text: str, fallback: str = "mod") -> str:
    s = "".join("_" if ch in _BAD_CHARS else ch for ch in str(text or ""))
    s = " ".join(s.split()).strip().strip(".")
    return s or fallback


def mod_filename(title: str, version: str, ext: str = ".jar") -> str:
    """统一文件名规则：模组名 + 版本号。"""
    ext = ext if ext.startswith(".") else f".{ext}"
    name = _safe_name(title or "mod", "mod")
    label = _safe_name(version, "").strip()
    if not label:
        return f"{name}{ext}"
    if label.lower().startswith(name.lower()):
        return f"{_safe_name(label, name)}{ext}"
    return f"{_safe_name(f'{name} {label}', name)}{ext}"


def mods_dir(game_dir: Path) -> Path:
    p = Path(game_dir) / "mods"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _record_path(game_dir: Path) -> Path:
    return Path(game_dir) / RECORD_FILE


def load_record(game_dir: Path) -> dict[str, dict]:
    f = _record_path(game_dir)
    if not f.exists():
        return {}
    try:
        raw = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    items = raw.get("mods") if isinstance(raw, dict) else None
    return items if isinstance(items, dict) else {}


def save_record(game_dir: Path, record: dict[str, dict]) -> None:
    try:
        _record_path(game_dir).write_text(
            json.dumps({"mods": record}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def scan(game_dir: Path) -> list[dict]:
    """列出 mods 目录内容，合并安装记录。"""
    root = Path(game_dir) / "mods"
    record = load_record(game_dir)
    rows: list[dict] = []
    if not root.exists():
        return rows
    for f in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not f.is_file():
            continue
        name = f.name
        enabled = True
        if name.endswith(".disabled"):
            enabled = False
            name = name[: -len(".disabled")]
        if not name.lower().endswith((".jar", ".zip", ".litemod")):
            continue
        meta_info = record.get(name, {})
        try:
            size = f.stat().st_size
        except OSError:
            size = 0
        title = meta_info.get("title") or Path(name).stem
        rows.append({
            "file": name,
            "size": size,
            "enabled": enabled,
            "title": title,
            "titleZh": mod_zh.zh_name(meta_info.get("slug", ""), title),
            "projectId": meta_info.get("project_id", ""),
            "versionId": meta_info.get("version_id", ""),
            "iconUrl": meta_info.get("icon_url", ""),
            "source": meta_info.get("source", "local"),
            "hasUpdate": False,
            "latestVersion": "",
        })
    return rows


def toggle(game_dir: Path, filename: str) -> bool:
    """启用/禁用：只改扩展名，不删文件。"""
    root = Path(game_dir) / "mods"
    live = root / filename
    off = root / (filename + ".disabled")
    try:
        if live.exists():
            live.rename(off)
            return False
        if off.exists():
            off.rename(live)
            return True
    except OSError:
        return False
    return False


def remove(game_dir: Path, filename: str) -> bool:
    root = Path(game_dir) / "mods"
    ok = False
    for target in (root / filename, root / (filename + ".disabled")):
        if target.exists():
            try:
                target.unlink()
                ok = True
            except OSError:
                pass
    record = load_record(game_dir)
    if record.pop(filename, None) is not None:
        save_record(game_dir, record)
    return ok


# ---------------------------------------------------------------- 版本匹配
def _match_tags(ver: dict, loader: str, mc_version: str) -> bool:
    """游戏版本与加载器都要对上；项目本身没打标签时视为未知，放行。"""
    loaders = [str(x).lower() for x in (ver.get("loaders") or [])]
    games = [str(x) for x in (ver.get("game_versions") or [])]
    if loader and loaders and loader.lower() not in loaders:
        return False
    if mc_version and games and mc_version not in games:
        return False
    return True


def _pick_version(
    client: ModrinthClient,
    project_id: str,
    loader: str,
    mc_version: str,
    strict: bool = True,
) -> dict | None:
    try:
        vers = client.versions(project_id, loader, mc_version) if (loader or mc_version) else client.versions(project_id)
    except Exception:
        vers = []
    if not vers and not strict:
        try:
            vers = client.versions(project_id)
        except Exception:
            return None
    for v in vers:
        if _match_tags(v, loader, mc_version):
            return v
    if strict:
        return None
    return vers[0] if vers else None


def _bad_version_message(loader: str, mc_version: str) -> str:
    tag = f"{mc_version or '任意版本'} / {loader or '任意加载器'}"
    return f"没有与该版本/加载器匹配的文件（{tag}）"


def _primary_file(ver: dict) -> dict | None:
    files = ver.get("files") or []
    return next((f for f in files if f.get("primary")), files[0] if files else None)


def _project_title(client: ModrinthClient, project_id: str, cache: dict[str, str]) -> str:
    if not project_id:
        return ""
    if project_id in cache:
        return cache[project_id]
    title = ""
    try:
        proj = client.project(project_id)
        title = proj.get("title") or proj.get("slug") or ""
    except Exception:  # noqa: BLE001
        title = ""
    cache[project_id] = title
    return title


def _required_modrinth(
    client: ModrinthClient,
    main: dict,
    loader: str,
    mc_version: str,
    depth: int = 4,
) -> tuple[list[dict], list[str]]:
    """递归解析 required 依赖，且每个依赖都按当前版本/加载器严格筛选。"""
    out: list[dict] = []
    skipped: list[str] = []
    seen: set[str] = {str(main.get("id") or "")}

    def walk(ver: dict, level: int) -> None:
        if level <= 0:
            return
        for dep in ver.get("dependencies") or []:
            if dep.get("dependency_type") != "required":
                continue
            vid = str(dep.get("version_id") or "")
            pid = str(dep.get("project_id") or "")
            key = vid or pid
            if not key or key in seen:
                continue
            seen.add(key)
            sub = None
            if vid:
                try:
                    candidate = client.version(vid)
                except Exception:  # noqa: BLE001
                    candidate = None
                if candidate and _match_tags(candidate, loader, mc_version):
                    sub = candidate
            if sub is None and pid:
                sub = _pick_version(client, pid, loader, mc_version, strict=True)
            if sub is None:
                name = _project_title(client, pid, {}) or (pid or vid)
                skipped.append(f"{name} 没有匹配 {mc_version or '任意版本'}/{loader or '任意加载器'} 的版本")
                continue
            out.append(sub)
            walk(sub, level - 1)

    walk(main, depth)
    return out, skipped


def resolve_install_versions(
    client: ModrinthClient,
    project_id: str,
    loader: str = "",
    mc_version: str = "",
    source: str = "modrinth",
    cf: CurseForgeClient | None = None,
) -> tuple[dict | None, list[dict], list[str]]:
    """解析主文件与前置依赖（严格匹配），返回 (主版本, 依赖版本, 跳过说明)。"""
    if (source or "modrinth") == "curseforge":
        if cf is None:
            raise CurseForgeError("未配置 CurseForge API Key")
        if not str(project_id).isdigit():
            raise CurseForgeError("CurseForge 项目 ID 无效")
        mod = cf.project(int(project_id))
        f = cf.pick_file(int(project_id), loader, mc_version)
        if not f:
            raise RuntimeError(_bad_version_message(loader, mc_version))
        main = cf.version_from(mod, f)
        deps, skipped = cf.resolve_required(int(project_id), int(f.get("id") or 0), loader, mc_version)
        return main, deps, skipped

    main = _pick_version(client, project_id, loader, mc_version, strict=True)
    if not main:
        raise RuntimeError(_bad_version_message(loader, mc_version))
    title = _project_title(client, str(main.get("project_id") or project_id), {})
    if title:
        main = dict(main)
        main["project_title"] = title
    deps, skipped = _required_modrinth(client, main, loader, mc_version)
    return main, deps, skipped


def install_project(
    client: ModrinthClient | None,
    game_dir: Path,
    project_id: str,
    loader: str = "",
    mc_version: str = "",
    mirror: str = "auto",
    with_dependencies: bool = True,
    on_progress: Progress | None = None,
    dest_dir: Path | None = None,
    source: str = "modrinth",
    cf: CurseForgeClient | None = None,
) -> list[dict]:
    """安装一个项目（含 required 前置），返回安装记录列表。

    dest_dir 不为空时下载到用户指定的目录，否则用 game_dir/mods。
    """
    on_progress = on_progress or _noop
    on_progress("解析项目版本", 0, 1)
    main, deps, skipped = resolve_install_versions(
        client, project_id, loader, mc_version, source=source, cf=cf,
    )
    if main is None:
        raise RuntimeError(_bad_version_message(loader, mc_version))
    versions: list[dict] = [main] + (deps if with_dependencies else [])
    root = Path(dest_dir) if dest_dir else mods_dir(game_dir)
    installed = _install_versions(
        root, versions, mirror, on_progress, source=source, cf=cf, game_dir=game_dir,
    )
    if skipped:
        for note in skipped:
            on_progress(f"跳过前置：{note}", 1, 1)
    return installed


def _install_versions(
    root: Path,
    versions: list[dict],
    mirror: str,
    on_progress: Progress,
    source: str = "modrinth",
    cf: CurseForgeClient | None = None,
    game_dir: Path | None = None,
) -> list[dict]:
    """把归一化版本列表落盘，文件名统一为「模组名 + 版本号」。"""
    root.mkdir(parents=True, exist_ok=True)
    tasks: list[DownloadTask] = []
    pending: list[dict] = []
    used: set[str] = set()
    title_cache: dict[str, str] = {}

    for ver in versions:
        primary = _primary_file(ver)
        if not primary:
            continue
        url = primary.get("url") or ""
        if not url and (source or "") == "curseforge" and cf is not None:
            try:
                url = cf.download_url(int(ver.get("mod_id") or 0), int(ver.get("file_id") or 0))
            except Exception:  # noqa: BLE001
                url = ""
        if not url:
            continue
        title = str(ver.get("project_title") or "").strip()
        if not title:
            title = str(ver.get("name") or "").strip()
        label = str(ver.get("version_number") or ver.get("name") or "").strip()
        raw_name = str(primary.get("filename") or "")
        ext = Path(raw_name).suffix or ".jar"
        filename = mod_filename(title or Path(raw_name).stem or "mod", label, ext)
        # 同名冲突（同项目多版本共存）时加序号，绝不覆盖既有文件
        base = filename
        idx = 2
        while filename in used:
            filename = f"{Path(base).stem} ({idx}){Path(base).suffix}"
            idx += 1
        used.add(filename)
        target = root / filename
        if target.exists() and target.stat().st_size > 0:
            if int(primary.get("size") or 0) in (0, target.stat().st_size):
                continue  # 已存在同样文件，跳过下载
        sha1 = (primary.get("hashes") or {}).get("sha1", "")
        tasks.append(DownloadTask(url, target, sha1, int(primary.get("size") or 0)))
        pending.append({
            "file": filename,
            "project_id": str(ver.get("project_id") or ""),
            "version_id": str(ver.get("id") or ""),
            "title": title or Path(filename).stem,
            "slug": str(ver.get("slug") or ver.get("project_slug") or ""),
            "icon_url": str(ver.get("icon_url") or ""),
            "source": str(ver.get("source") or source or "modrinth"),
            "game_versions": ver.get("game_versions") or [],
            "loaders": ver.get("loaders") or [],
            "url": url,
            "installed_at": int(time.time()),
        })

    if not tasks:
        if pending:
            raise RuntimeError("模组文件已存在，无需重复下载")
        raise RuntimeError("该项目没有可下载文件")

    downloader = net.Downloader(mirror)
    on_progress("下载模组文件", 0, len(tasks))
    _total, failures = downloader.run(
        tasks, lambda done, total, name: on_progress(f"下载 {name[:28]}", done, total)
    )

    record_dir = Path(game_dir) if game_dir is not None else root.parent
    record = load_record(record_dir)
    installed: list[dict] = []
    for item in pending:
        if not (root / item["file"]).exists():
            continue
        record[item["file"]] = item
        installed.append(item)
    save_record(record_dir, record)

    if failures and not installed:
        raise RuntimeError(f"{failures[0][1]}")
    on_progress("安装完成", 1, 1)
    return installed


def enrich_icons(client: ModrinthClient, game_dir: Path, rows: list[dict]) -> list[dict]:
    """给已装列表补项目图标（按 project_id 去重查询）。"""
    cache: dict[str, str] = {}
    for row in rows:
        pid = row.get("projectId") or ""
        if not pid:
            continue
        if row.get("iconUrl"):
            continue
        if pid not in cache:
            try:
                proj = client.project(pid)
                cache[pid] = proj.get("icon_url") or ""
            except Exception:
                cache[pid] = ""
        row["iconUrl"] = cache[pid]
    return rows


def check_updates(
    client: ModrinthClient | None,
    game_dir: Path,
    loader: str = "",
    mc_version: str = "",
    cf: CurseForgeClient | None = None,
) -> list[dict]:
    """比对记录里的版本与最新版本，返回有更新的条目。"""
    rows = scan(game_dir)
    out: list[dict] = []
    for row in rows:
        pid = row.get("projectId") or ""
        if not pid:
            continue
        latest: dict | None = None
        if (row.get("source") or "").lower() == "curseforge" and cf is not None and str(pid).isdigit():
            try:
                f = cf.pick_file(int(pid), loader, mc_version)
            except Exception:  # noqa: BLE001
                f = None
            if f:
                latest = {"id": f"cf:{int(pid)}:{int(f.get('id') or 0)}", "version_number": f.get("displayName") or f.get("fileName") or ""}
        elif client is not None:
            latest = _pick_version(client, pid, loader, mc_version)
        if not latest:
            continue
        if latest.get("id") and latest.get("id") != row.get("versionId"):
            row["hasUpdate"] = True
            row["latestVersion"] = latest.get("version_number") or latest.get("name") or ""
            row["latestVersionId"] = latest.get("id")
            out.append(row)
    return out


def import_modpack_files(
    game_dir: Path,
    files: list[dict],
    on_progress: Progress | None = None,
) -> dict:
    """整合包 files 段落下载：files 为 mrpack index 的 files 列表。"""
    on_progress = on_progress or _noop
    root = Path(game_dir)
    tasks: list[DownloadTask] = []
    for f in files:
        path = f.get("path") or ""
        urls = f.get("downloads") or []
        if not path or not urls:
            continue
        sha1 = (f.get("hashes") or {}).get("sha1", "")
        tasks.append(DownloadTask(urls[0], root / path, sha1, f.get("fileSize", 0)))
    if not tasks:
        return {"total": 0, "failures": []}
    downloader = net.Downloader("auto")
    total, failures = downloader.run(
        tasks, lambda done, t, name: on_progress(f"下载 {name[:28]}", done, t)
    )
    return {"total": total, "failures": failures}
