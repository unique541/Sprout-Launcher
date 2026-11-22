"""CurseForge API 客户端：搜索、文件筛选、依赖解析、下载链接。

与 Modrinth 客户端保持同样的“归一化版本字典”输出，便于上层复用同一套安装流程。
"""
from __future__ import annotations

from typing import Any

import httpx

API = "https://api.curseforge.com"
MIRROR_API = "https://mod.mcimirror.top/curseforge"   # 国内镜像：无需 API Key
MIRROR_CDN = "https://mod.mcimirror.top"              # 文件 CDN（镜像 302 跳到真实 CDN）
FORGECDN_HOST = "edge.forgecdn.net"
_MEDIAFILEZ_HOST = "mediafilez.forgecdn.net"          # 镜像明确不支持该域名
GAME_ID = 432  # Minecraft
UA = "SproutLauncher/0.1"


def to_mirror_cdn(url: str) -> str:
    """把 edge.forgecdn.net 的文件地址换成镜像地址；mediafilez 与非 CDN 地址原样返回。"""
    text = (url or "").strip()
    if not text:
        return text
    low = text.lower()
    if _MEDIAFILEZ_HOST in low or not low.startswith(("http://", "https://")):
        return text
    head, _, rest = text.partition("://")
    host, _, path = rest.partition("/")
    if host.lower() != FORGECDN_HOST or not path:
        return text
    return MIRROR_CDN.rstrip("/") + "/" + path

# 项目类型 -> CurseForge classId
CLASS_IDS = {
    "mod": 6,
    "modpack": 4471,
    "resourcepack": 12,
    "shader": 6552,
    "world": 17,
    "datapack": 6,
}

# 加载器 -> CurseForge modLoaderType
LOADER_TYPES = {"forge": 1, "fabric": 4, "quilt": 5, "neoforge": 6, "liteloader": 3}
LOADER_NAMES = {"forge": "forge", "fabric": "fabric", "quilt": "quilt", "neoforge": "neoforge", "liteloader": "liteloader", "cauldron": "cauldron"}

RELATION_REQUIRED = 3
_HASH_SHA1 = 1
_NON_VERSION = {"client", "server", "forge", "fabric", "quilt", "neoforge", "liteloader", "cauldron", "rift"}


class CurseForgeError(RuntimeError):
    """CurseForge 调用失败。"""


class CurseForgeKeyMissing(CurseForgeError):
    """未配置 API Key（属于配置缺失，不是报错）。"""


def _non_version_tokens() -> set[str]:
    return set(_NON_VERSION)


def _file_games(f: dict) -> list[str]:
    return [str(g) for g in (f.get("gameVersions") or []) if str(g).lower() not in _non_version_tokens()]


def _file_loaders(f: dict) -> list[str]:
    return [str(g).lower() for g in (f.get("gameVersions") or []) if str(g).lower() in _non_version_tokens() and str(g).lower() not in ("client", "server")]


def _file_date_ms(f: dict) -> int:
    """fileDate 兼容：官方站是毫秒时间戳，镜像站返回 ISO 字符串。"""
    raw = f.get("fileDate")
    if isinstance(raw, (int, float)):
        return int(raw)
    text = str(raw or "").strip()
    if not text:
        return 0
    try:
        from datetime import datetime

        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:  # noqa: BLE001
        return 0


def _sha1_of(f: dict) -> str:
    for h in f.get("hashes") or []:
        if int(h.get("algo") or 0) == _HASH_SHA1:
            return str(h.get("value") or "")
    return ""


class CurseForgeClient:
    def __init__(self, api_key: str = "", timeout: float = 20.0, mirror: bool = True) -> None:
        key = (api_key or "").strip()
        self._mirror = bool(mirror)
        if not self._mirror and not key:
            raise CurseForgeKeyMissing("未配置 CurseForge API Key")
        headers = {"Accept": "application/json", "User-Agent": UA}
        if key and not self._mirror:
            headers["x-api-key"] = key      # 镜像侧不需要（也不支持）API Key
        self._c = httpx.Client(timeout=timeout, headers=headers, follow_redirects=True)
        self._base = MIRROR_API if self._mirror else API
        self._mod_cache: dict[int, dict] = {}

    @property
    def using_mirror(self) -> bool:
        return self._mirror

    def _cdn(self, url: str) -> str:
        return to_mirror_cdn(url) if self._mirror else (url or "")

    def close(self) -> None:
        self._c.close()

    # ------------------------------------------------------------ 基础请求
    def _get(self, path: str, params: dict | None = None) -> Any:
        r = self._c.get(f"{self._base}{path}", params=params or {})
        if r.status_code in (401, 403):
            raise CurseForgeError("CurseForge API Key 无效或无权限")
        r.raise_for_status()
        data = r.json()
        return data.get("data") if isinstance(data, dict) else None

    # ------------------------------------------------------------ 搜索
    def search(
        self,
        query: str,
        project_type: str = "mod",
        loader: str = "",
        mc_version: str = "",
        offset: int = 0,
        limit: int = 20,
        sort_field: int = 2,
    ) -> dict:
        class_id = CLASS_IDS.get(project_type or "mod", 6)
        page_size = max(1, min(50, int(limit)))
        params: dict[str, Any] = {
            "gameId": GAME_ID,
            "classId": class_id,
            "index": int(offset),
            "pageSize": page_size,
            "sortField": sort_field,       # 2 = 热门度
            "sortOrder": "desc",
        }
        text = (query or "").strip()
        if text:
            params["searchFilter"] = text
            params["sortField"] = 1         # 有关键词时按相关度
        if mc_version:
            params["gameVersion"] = mc_version
        loader_type = LOADER_TYPES.get((loader or "").lower())
        if loader_type:
            params["modLoaderType"] = loader_type
        r = self._c.get(f"{self._base}/v1/mods/search", params=params)
        if r.status_code in (401, 403):
            raise CurseForgeError("CurseForge API Key 无效或无权限")
        r.raise_for_status()
        body = r.json()
        hits = body.get("data") or []
        pagination = body.get("pagination") or {}
        return {
            "hits": hits,
            "total": int(pagination.get("totalCount") or 0),
            "index": int(pagination.get("index") or offset),
        }

    # ------------------------------------------------------------ 项目 / 文件
    def project(self, mod_id: int | str) -> dict:
        key = int(mod_id)
        if key in self._mod_cache:
            return self._mod_cache[key]
        data = self._get(f"/v1/mods/{key}")
        if not isinstance(data, dict):
            raise CurseForgeError("项目不存在")
        self._mod_cache[key] = data
        return data

    def files(self, mod_id: int | str, mc_version: str = "", loader: str = "", page_size: int = 50) -> list[dict]:
        params: dict[str, Any] = {"pageSize": max(1, min(50, page_size))}
        if mc_version:
            params["gameVersion"] = mc_version
        loader_type = LOADER_TYPES.get((loader or "").lower())
        if loader_type:
            params["modLoaderType"] = loader_type
        data = self._get(f"/v1/mods/{int(mod_id)}/files", params)
        return data if isinstance(data, list) else []

    def file(self, mod_id: int | str, file_id: int | str) -> dict:
        data = self._get(f"/v1/mods/{int(mod_id)}/files/{int(file_id)}")
        if not isinstance(data, dict):
            raise CurseForgeError("文件不存在")
        return data

    def download_url(self, mod_id: int | str, file_id: int | str) -> str:
        data = self._get(f"/v1/mods/{int(mod_id)}/files/{int(file_id)}/download-url")
        if isinstance(data, str) and data:
            return self._cdn(data)
        if isinstance(data, dict):
            url = data.get("downloadUrl") or ""
            if url:
                return self._cdn(url)
        return ""

    # ------------------------------------------------------------ 版本匹配
    def _candidates(self, files: list[dict], loader: str, mc_version: str) -> list[dict]:
        """严格筛选：游戏版本与加载器都对得上（有标签才校验，无标签视为未知）。"""
        strict = bool(loader or mc_version)
        picked: list[dict] = []
        for f in files:
            games = [g.lower() for g in _file_games(f)]
            lds = _file_loaders(f)
            if mc_version and games and mc_version.lower() not in games:
                continue
            if loader and lds and loader.lower() not in lds:
                continue
            if strict and loader and not lds:
                # 模组类项目没有加载器标签时，无法确认可用，直接排除
                if games:
                    continue
            picked.append(f)

        def rank(item: dict) -> tuple:
            release = int(item.get("releaseType") or 0)
            # release=1 优先，其次 beta/alpha；同优先级按时间倒序
            return (0 if release == 1 else 1, -_file_date_ms(item))

        picked.sort(key=rank)
        return picked

    def pick_file(self, mod_id: int | str, loader: str = "", mc_version: str = "") -> dict | None:
        try:
            files = self.files(mod_id, mc_version, loader)
        except Exception:  # noqa: BLE001
            files = []
        if not files:
            try:
                files = self.files(mod_id)
            except Exception:  # noqa: BLE001
                return None
        cands = self._candidates(files, loader, mc_version)
        return cands[0] if cands else None

    # ------------------------------------------------------------ 归一化
    def version_from(self, mod: dict, f: dict) -> dict:
        mod_id = int(f.get("modId") or mod.get("id") or 0)
        file_id = int(f.get("id") or 0)
        url = self._cdn(f.get("downloadUrl") or "")
        item = {
            "id": f"cf:{mod_id}:{file_id}",
            "source": "curseforge",
            "mod_id": mod_id,
            "file_id": file_id,
            "project_id": str(mod_id),
            "name": f.get("displayName") or f.get("fileName") or "",
            "version_number": f.get("displayName") or f.get("fileName") or "",
            "loaders": _file_loaders(f),
            "game_versions": _file_games(f),
            "downloads": int(mod.get("downloadCount") or 0),
            "date": str(f.get("fileDate") or ""),
            "project_title": mod.get("name") or "",
            "icon_url": ((mod.get("logo") or {}).get("thumbnailUrl") or (mod.get("logo") or {}).get("url") or ""),
            "files": [{
                "url": url,
                "filename": f.get("fileName") or f"{mod_id}-{file_id}.jar",
                "primary": True,
                "size": int(f.get("fileLength") or 0),
                "hashes": {"sha1": _sha1_of(f)},
            }],
            "dependencies": [
                {"mod_id": int(d.get("modId") or 0), "relation": int(d.get("relationType") or 0)}
                for d in (f.get("dependencies") or [])
            ],
        }
        return item

    # ------------------------------------------------------------ 依赖
    def resolve_required(
        self,
        mod_id: int | str,
        file_id: int | str,
        loader: str = "",
        mc_version: str = "",
        depth: int = 4,
    ) -> tuple[list[dict], list[str]]:
        """递归解析 REQUIRED 前置；严格匹配游戏版本与加载器，返回 (依赖版本, 跳过说明)。"""
        out: list[dict] = []
        skipped: list[str] = []
        seen: set[int] = {int(mod_id)}

        def walk(mid: int, fid: int, level: int) -> None:
            if level <= 0:
                return
            try:
                f = self.file(mid, fid)
            except Exception as exc:  # noqa: BLE001
                skipped.append(f"{mid}: 读取依赖信息失败 {exc}")
                return
            for dep in f.get("dependencies") or []:
                if int(dep.get("relationType") or 0) != RELATION_REQUIRED:
                    continue
                did = int(dep.get("modId") or 0)
                if not did or did in seen:
                    continue
                seen.add(did)
                target = self.pick_file(did, loader, mc_version)
                if not target:
                    skipped.append(f"模组 {did} 没有匹配 {mc_version or '任意版本'}/{loader or '任意加载器'} 的文件")
                    continue
                try:
                    mod = self.project(did)
                except Exception:  # noqa: BLE001
                    mod = {"id": did, "name": f"模组 {did}"}
                out.append(self.version_from(mod, target))
                walk(did, int(target.get("id") or 0), level - 1)

        walk(int(mod_id), int(file_id), depth)
        return out, skipped
