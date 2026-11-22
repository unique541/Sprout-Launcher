"""Modrinth API 客户端：搜索、版本筛选、依赖解析、下载安装。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

API = "https://api.modrinth.com/v2"
UA = "SproutLauncher/0.1"

# Modrinth 的 game_versions 字段会把加载器标签混进版本号里，必须显式区分
LOADER_TAGS = {
    "fabric", "forge", "neoforge", "quilt", "liteloader", "rift",
    "datapack", "canvas", "iris", "optifine",
}


def split_game_versions(values: list[str]) -> tuple[list[str], list[str]]:
    """拆成 (纯游戏版本, 加载器标签)。"""
    versions, loaders = [], []
    for v in values or []:
        if v.lower() in LOADER_TAGS:
            loaders.append(v.lower())
        else:
            versions.append(v)
    return versions, loaders


class ModrinthClient:
    def __init__(self, timeout: float = 20.0) -> None:
        self._c = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": UA},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._c.close()

    def search(
        self,
        query: str,
        project_type: str = "mod",
        loader: str = "",
        mc_version: str = "",
        offset: int = 0,
        limit: int = 20,
        index: str = "",
    ) -> dict[str, Any]:
        facets: list[list[str]] = [[f"project_type:{project_type}"]]
        if loader:
            facets.append([f"categories:{loader}"])
        if mc_version:
            facets.append([f"versions:{mc_version}"])
        # 空搜索词时 relevance 无意义，默认按下载量（热度）排序
        if not index:
            index = "relevance" if (query or "").strip() else "downloads"
        params = {
            "query": query,
            "limit": str(limit),
            "offset": str(offset),
            "index": index,
            "facets": json.dumps(facets),
        }
        r = self._c.get(f"{API}/search", params=params)
        r.raise_for_status()
        return r.json()

    def project(self, slug_or_id: str) -> dict[str, Any]:
        r = self._c.get(f"{API}/project/{slug_or_id}")
        r.raise_for_status()
        return r.json()

    def versions(self, project_id: str, loader: str = "", mc_version: str = "") -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if loader:
            params["loaders"] = json.dumps([loader])
        if mc_version:
            params["game_versions"] = json.dumps([mc_version])
        r = self._c.get(f"{API}/project/{project_id}/version", params=params)
        r.raise_for_status()
        return r.json()

    def version(self, version_id: str) -> dict[str, Any]:
        r = self._c.get(f"{API}/version/{version_id}")
        r.raise_for_status()
        return r.json()

    def resolve_required(self, version: dict[str, Any], depth: int = 3) -> list[dict[str, Any]]:
        """递归解析 required 依赖，返回需要一并安装的版本列表。"""
        result: list[dict[str, Any]] = []
        seen: set[str] = {version.get("id", "")}

        def walk(ver: dict[str, Any], level: int) -> None:
            if level <= 0:
                return
            for dep in ver.get("dependencies") or []:
                if dep.get("dependency_type") != "required":
                    continue
                vid = dep.get("version_id")
                try:
                    if vid:
                        if vid in seen:
                            continue
                        seen.add(vid)
                        sub = self.version(vid)
                    elif dep.get("project_id"):
                        if dep["project_id"] in seen:
                            continue
                        seen.add(dep["project_id"])
                        subs = self.versions(dep["project_id"])
                        if not subs:
                            continue
                        sub = subs[0]
                        if sub.get("id") in seen:
                            continue
                        seen.add(sub.get("id", ""))
                    else:
                        continue
                    result.append(sub)
                    walk(sub, level - 1)
                except httpx.HTTPError:
                    continue

        walk(version, depth)
        return result

    def download(self, version: dict[str, Any], target_dir: Path) -> Path | None:
        """下载版本主文件（走统一并发下载内核）。"""
        from ..core import net

        files = version.get("files") or []
        primary = next((f for f in files if f.get("primary")), files[0] if files else None)
        if not primary:
            return None
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / primary["filename"]
        task = net.DownloadTask(
            primary["url"],
            dest,
            (primary.get("hashes") or {}).get("sha1", ""),
            int(primary.get("size") or 0),
        )
        _total, failures = net.Downloader("auto").run([task])
        if failures and not dest.exists():
            return None
        return dest
