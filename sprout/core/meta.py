"""版本元数据：清单拉取、版本 JSON 加载、inheritsFrom 合并、rules 求值。"""
from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

from .. import paths
from . import net


def os_name() -> str:
    s = platform.system().lower()
    if s.startswith("win"):
        return "windows"
    if s == "darwin":
        return "osx"
    return "linux"


def os_arch() -> str:
    m = platform.machine().lower()
    if m in ("amd64", "x86_64"):
        return "x86_64"
    if m in ("arm64", "aarch64"):
        return "arm64"
    if m in ("i386", "i686", "x86"):
        return "x86"
    return m


def _rule_matches(rule: dict[str, Any], features: dict[str, bool]) -> bool:
    os_rule = rule.get("os")
    if os_rule:
        name = os_rule.get("name")
        if name and name != os_name():
            return False
        arch = os_rule.get("arch")
        if arch and arch != os_arch():
            return False
        ver = os_rule.get("version")
        if ver:
            import re

            if not re.search(ver, platform.release()):
                return False
    feat_rule = rule.get("features")
    if feat_rule:
        for k, v in feat_rule.items():
            if bool(features.get(k, False)) != bool(v):
                return False
    return True


def rules_allow(element: dict[str, Any], features: dict[str, bool] | None = None) -> bool:
    """按 rules 判定元素是否可用；无 rules 视为可用。"""
    features = features or {}
    rules = element.get("rules")
    if not rules:
        return True
    allowed = False
    for rule in rules:
        if _rule_matches(rule, features):
            allowed = rule.get("action") == "allow"
    return allowed


class VersionManifest:
    def __init__(self, mirror: str = "auto") -> None:
        self.mirror = mirror
        self.versions: list[dict[str, Any]] = []
        self.latest: dict[str, str] = {}

    def fetch(self) -> "VersionManifest":
        data = net.get_json(net.MANIFEST_URL_OFFICIAL, self.mirror)
        self.versions = data.get("versions", [])
        self.latest = data.get("latest", {})
        try:
            (paths.meta_cache_dir() / "version_manifest.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            pass
        return self

    def find(self, version_id: str) -> dict[str, Any] | None:
        for v in self.versions:
            if v.get("id") == version_id:
                return v
        return None


def fetch_version_json(version_id: str, url: str, mirror: str = "auto", force: bool = False) -> dict[str, Any]:
    """下载（或读缓存）单个版本 JSON。"""
    cache = paths.meta_cache_dir() / f"{version_id}.json"
    if cache.exists() and not force:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    data = net.get_json(url, mirror)
    try:
        cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return data


def _merge(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    """inheritsFrom 合并：libraries/arguments 需拼接，其余子版本覆盖父版本。"""
    out = dict(parent)
    for k, v in child.items():
        if k == "libraries":
            base = list(parent.get("libraries", []))
            index = {(lib.get("name") or ""): i for i, lib in enumerate(base)}
            for lib in v:
                key = lib.get("name") or ""
                if key in index:
                    base[index[key]] = lib
                else:
                    base.append(lib)
            out["libraries"] = base
        elif k == "arguments":
            base = dict(parent.get("arguments", {}))
            for kind in ("game", "jvm"):
                base[kind] = list(base.get(kind, [])) + list(v.get(kind, []))
            out["arguments"] = base
        else:
            out[k] = v
    return out


def load_version(mc_dir: Path, version_id: str, manifest: VersionManifest, force: bool = False) -> dict[str, Any]:
    """读取本地版本 JSON；本地缺失时从远端拉取（不落盘到实例，用于展示）。"""
    local = mc_dir / "versions" / version_id / f"{version_id}.json"
    if local.exists() and not force:
        data = json.loads(local.read_text(encoding="utf-8"))
    else:
        entry = manifest.find(version_id)
        if not entry:
            raise FileNotFoundError(f"版本清单中不存在 {version_id}")
        data = fetch_version_json(version_id, entry["url"], manifest.mirror, force=force)

    parent_id = data.get("inheritsFrom")
    if parent_id:
        parent = load_version(mc_dir, parent_id, manifest, force=force)
        data = _merge(parent, data)
    return data


def artifact_path(lib: dict[str, Any]) -> str | None:
    downloads = lib.get("downloads") or {}
    art = downloads.get("artifact")
    if art and art.get("path"):
        return art["path"]
    name = lib.get("name") or ""
    parts = name.split(":")
    if len(parts) >= 3:
        group, artifact, version = parts[0], parts[1], parts[2]
        classifier = parts[3] if len(parts) > 3 else ""
        fname = f"{artifact}-{version}" + (f"-{classifier}" if classifier else "") + ".jar"
        return f"{group.replace('.', '/')}/{artifact}/{version}/{fname}"
    return None


def library_url(lib: dict[str, Any]) -> str | None:
    downloads = lib.get("downloads") or {}
    art = downloads.get("artifact")
    if art and art.get("url"):
        return art["url"]
    path = artifact_path(lib)
    if path:
        return "https://libraries.minecraft.net/" + path
    return None
