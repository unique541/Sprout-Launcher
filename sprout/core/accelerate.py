"""网络加速：GitHub 镜像前缀 + Steam 下载线路探测。

作用范围：
  * GitHub：开启后，所有发往 github.com / *.githubusercontent.com 等域名的
    下载请求会在经过 mirror 改写后再套一层镜像前缀（真实作用，见 net.rewrite_url）。
  * Steam：按国区/港区/美区向 Valve 的 Content Server Directory 查询对应
    cell 的 CDN 节点，并实测 TCP 延迟，给出当前最优下载线路与状态。
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

GITHUB_HOSTS: tuple[str, ...] = (
    "github.com",
    "api.github.com",
    "codeload.github.com",
    "objects.githubusercontent.com",
    "raw.githubusercontent.com",
    "gist.githubusercontent.com",
    "github-releases.githubusercontent.com",
    "githubusercontent.com",
)

# 常用 GitHub 加速前缀，{url} 为完整原始地址
GITHUB_MIRRORS: tuple[dict, ...] = (
    {"id": "ghfast", "name": "ghfast.top", "template": "https://ghfast.top/{url}"},
    {"id": "ghproxy", "name": "gh-proxy.com", "template": "https://gh-proxy.com/{url}"},
    {"id": "moeyy", "name": "github.moeyy.xyz", "template": "https://github.moeyy.xyz/{url}"},
    {"id": "gitmirror", "name": "hub.gitmirror.com", "template": "https://hub.gitmirror.com/{url}"},
    {"id": "direct", "name": "不使用镜像（直连）", "template": "{url}"},
)

STEAM_REGIONS: tuple[dict, ...] = (
    {"id": "cn", "name": "国区（China）", "cell": 47, "short": "国区"},
    {"id": "hk", "name": "港区（Hong Kong）", "cell": 33, "short": "港区"},
    {"id": "us", "name": "美区（United States）", "cell": 1, "short": "美区"},
)

STEAM_SERVERS_API = (
    "https://api.steampowered.com/IContentServerDirectoryService/"
    "GetServersForSteamPipe/v1/?cell_id={cell}&max_servers=20"
)

_MIRROR_IDS = {m["id"]: m for m in GITHUB_MIRRORS}
_REGION_IDS = {r["id"]: r for r in STEAM_REGIONS}


def mirror_by_id(mirror_id: str) -> dict:
    return _MIRROR_IDS.get((mirror_id or "").strip(), _MIRROR_IDS["ghfast"])


def region_by_id(region_id: str) -> dict:
    return _REGION_IDS.get((region_id or "").strip(), _REGION_IDS["cn"])


def is_github(url: str) -> bool:
    try:
        host = (url.split("://", 1)[-1].split("/", 1)[0]).split("@")[-1].split(":")[0].lower()
    except Exception:  # noqa: BLE001
        return False
    return any(host == h or host.endswith("." + h) for h in GITHUB_HOSTS)


class Accelerator:
    """加速状态机：配置来自 Config，可单独替换用于测试。"""

    def __init__(self, config=None) -> None:
        self._config = config
        self._steam_cache: dict | None = None
        self._steam_checked: float = 0.0
        self._last_error: str = ""
        self._hit_count: int = 0
        self._last_rewrite: str = ""

    # -------------------------------------------------------------- 配置读写
    def attach(self, config) -> None:
        self._config = config

    def _cfg(self):
        if self._config is None:
            try:
                from ..config import Config

                self._config = Config()
            except Exception:  # noqa: BLE001
                return None
        return self._config

    def _get(self, key: str, default):
        cfg = self._cfg()
        if cfg is None:
            return default
        try:
            return cfg.get(key, default)
        except Exception:  # noqa: BLE001
            return default

    def _set(self, key: str, value) -> None:
        cfg = self._cfg()
        if cfg is None:
            return
        try:
            cfg.set(key, value)
            cfg.save()
        except Exception:  # noqa: BLE001
            pass

    # -------------------------------------------------------------- 属性
    @property
    def github_enabled(self) -> bool:
        return bool(self._get("accel_github", False))

    @property
    def github_mirror(self) -> str:
        v = str(self._get("accel_github_mirror", "ghfast") or "ghfast")
        return v if v in _MIRROR_IDS else "ghfast"

    @property
    def steam_enabled(self) -> bool:
        return bool(self._get("accel_steam", False))

    @property
    def steam_region(self) -> str:
        v = str(self._get("accel_steam_region", "cn") or "cn")
        return v if v in _REGION_IDS else "cn"

    # -------------------------------------------------------------- GitHub
    def set_github(self, enabled: bool, mirror: str | None = None) -> None:
        self._set("accel_github", bool(enabled))
        if mirror is not None:
            self._set("accel_github_mirror", mirror if mirror in _MIRROR_IDS else "ghfast")

    def set_mirror(self, mirror: str) -> None:
        self.set_github(self.github_enabled, mirror)

    def rewrite(self, url: str) -> str:
        """GitHub 地址套镜像前缀；非 GitHub 或未开启时原样返回。"""
        if not url or not self.github_enabled or not is_github(url):
            return url
        tpl = mirror_by_id(self.github_mirror).get("template") or "{url}"
        if tpl == "{url}":
            self._last_rewrite = url
            return url
        out = tpl.replace("{url}", url)
        self._hit_count += 1
        self._last_rewrite = out
        return out

    def probe_mirrors(self) -> list[dict]:
        """逐个镜像请求一次 GitHub 上的小文件，测出可用性与耗时。"""
        results: list[dict] = []
        target = "https://github.com/octocat/Hello-World/raw/master/README"
        for m in GITHUB_MIRRORS:
            entry = {"id": m["id"], "name": m["name"], "ok": False, "ms": 0, "error": ""}
            if m.get("template") == "{url}":
                url = "https://raw.githubusercontent.com/octocat/Hello-World/master/README"
            else:
                url = str(m["template"]).replace("{url}", target)
            started = time.perf_counter()
            try:
                import httpx

                with httpx.Client(timeout=httpx.Timeout(6.0, connect=4.0),
                                  follow_redirects=True,
                                  headers={"User-Agent": "Sprout/0.3.2"}) as c:
                    r = c.get(url)
                entry["ms"] = int((time.perf_counter() - started) * 1000)
                if r.status_code < 400 and r.content:
                    entry["ok"] = True
                else:
                    entry["error"] = f"HTTP {r.status_code}"
            except Exception as exc:  # noqa: BLE001
                entry["ms"] = int((time.perf_counter() - started) * 1000)
                entry["error"] = type(exc).__name__
            results.append(entry)
        return results

    def auto_mirror(self) -> dict:
        """按实测延迟挑最快的可用镜像并启用。"""
        results = self.probe_mirrors()
        usable = [r for r in results if r["ok"] and r["id"] != "direct"]
        usable.sort(key=lambda r: r["ms"])
        pick = usable[0] if usable else {"id": "direct", "name": "不使用镜像（直连）", "ms": 0}
        self.set_github(True, pick["id"])
        return {"picked": pick, "results": results}

    # -------------------------------------------------------------- Steam
    def _tcp_latency(self, host: str, port: int = 443, timeout: float = 2.5) -> int:
        started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return int((time.perf_counter() - started) * 1000)
        except Exception:  # noqa: BLE001
            return -1

    def _tcp_probe(self, host: str, timeout: float = 2.0) -> tuple[int, int]:
        """Steam 内容服务器 443 常被本地网络阻断，按 443→80→27015 逐个试。"""
        for port in (443, 80, 27015):
            ms = self._tcp_latency(host, port, timeout)
            if ms >= 0:
                return ms, port
        return -1, 0

    def steam_route(self, refresh: bool = False, allow_network: bool = True) -> dict:
        region = region_by_id(self.steam_region)
        if not refresh and self._steam_cache and time.time() - self._steam_checked < 300:
            return dict(self._steam_cache)
        if not allow_network and not self._steam_cache:
            return {"ok": False, "region": region["id"], "regionName": region["name"],
                    "regionShort": region["short"], "cell": region["cell"], "servers": [],
                    "best": "", "bestMs": -1, "pending": True, "checkedAt": 0,
                    "message": "正在探测线路…"}

        info: dict = {
            "ok": False,
            "region": region["id"],
            "regionName": region["name"],
            "regionShort": region["short"],
            "cell": region["cell"],
            "servers": [],
            "best": "",
            "bestMs": -1,
            "message": "",
            "checkedAt": 0,
        }
        url = STEAM_SERVERS_API.format(cell=region["cell"])
        payload = None
        try:
            from . import net

            payload = net.get_json(url, mirror="official", timeout=15.0)
        except Exception as exc:  # noqa: BLE001
            self._last_error = str(exc)
            info["message"] = f"无法获取 Steam 线路列表：{exc}"
            self._steam_cache = info
            self._steam_checked = time.time()
            return dict(info)

        servers = ((payload or {}).get("response") or {}).get("servers") or []
        hosts: list[str] = []
        for s in servers:
            if not isinstance(s, dict):
                continue
            # Steam 官方接口字段名是 host（不是 hostname），两个都兼容
            host = str(s.get("host") or s.get("hostname") or "").strip()
            if not host or host in ("0.0.0.0", "127.0.0.1", "localhost"):
                continue
            if host not in hosts:
                hosts.append(host)
        hosts = hosts[:6]

        measured: list[dict] = []
        if hosts:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(6, len(hosts))) as pool:
                results = list(pool.map(self._tcp_probe, hosts))
            measured = [{"host": h, "ms": r[0], "port": r[1]}
                        for h, r in zip(hosts, results)]
        measured.sort(key=lambda x: (x["ms"] < 0, x["ms"]))
        info["servers"] = measured
        if measured and measured[0]["ms"] >= 0:
            info["ok"] = True
            info["best"] = measured[0]["host"]
            info["bestMs"] = measured[0]["ms"]
            info["message"] = (f"已接入 {region['short']}线路，最优节点 "
                               f"{measured[0]['host']}（{measured[0]['ms']} ms / "
                               f"端口 {measured[0].get('port') or 443}）")
        else:
            info["message"] = "线路列表已获取，但节点均未连通（可能被本地网络拦截）"
        info["checkedAt"] = int(time.time())
        self._steam_cache = info
        self._steam_checked = time.time()
        return dict(info)

    def set_steam_state(self, enabled: bool, region: str | None = None) -> None:
        """只写开关与区服，不发起任何网络请求（供 UI 线程即时响应）。"""
        self._set("accel_steam", bool(enabled))
        if region is not None and region in _REGION_IDS:
            changed = str(region) != self.steam_region
            self._set("accel_steam_region", region)
            if changed:
                self._steam_cache = None  # 换区必须重新探测
        if not enabled:
            self._steam_cache = None
            self._steam_checked = 0.0

    def set_steam(self, enabled: bool, region: str | None = None) -> dict:
        self.set_steam_state(enabled, region)
        return self.steam_route(refresh=True)

    # -------------------------------------------------- Steam 客户端区服落地
    def client_cell(self) -> dict:
        return steam_cell_override()

    def apply_client_cell(self, region: str | None = None) -> dict:
        return apply_steam_cell(region or self.steam_region)

    # -------------------------------------------------------------- 汇总
    def state(self, refresh_steam: bool = False, allow_network: bool = True) -> dict:
        mirror = mirror_by_id(self.github_mirror)
        out = {
            "github": self.github_enabled,
            "githubMirror": self.github_mirror,
            "githubMirrorName": mirror["name"],
            "githubHits": self._hit_count,
            "lastRewrite": self._last_rewrite,
            "steam": self.steam_enabled,
            "steamRegion": self.steam_region,
            "steamRegionName": region_by_id(self.steam_region)["name"],
            "steamRoute": {},
            "status": "",
            "error": self._last_error,
        }
        parts: list[str] = []
        if self.github_enabled:
            parts.append(f"GitHub 经 {mirror['name']} 加速（已改写 {self._hit_count} 次）")
        else:
            parts.append("GitHub 直连")
        if self.steam_enabled:
            route = self.steam_route(refresh=refresh_steam, allow_network=allow_network)
            out["steamRoute"] = route
            parts.append(route.get("message") or f"{region_by_id(self.steam_region)['short']}线路已启用")
        else:
            parts.append("Steam 加速未启用")
        out["status"] = "；".join(parts)
        return out


# ------------------------------------------------------------------ Steam 客户端
def steam_config_path() -> Path | None:
    """Steam 客户端 config.vdf 的真实路径（注册表优先，其次默认安装目录）。"""
    cands: list[Path] = []
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            raw = str(winreg.QueryValueEx(key, "SteamPath")[0] or "")
        if raw:
            cands.append(Path(raw) / "config" / "config.vdf")
    except Exception:  # noqa: BLE001
        pass
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env) or ""
        if base:
            cands.append(Path(base) / "Steam" / "config" / "config.vdf")
    for cand in cands:
        try:
            if cand.is_file():
                return cand
        except OSError:
            continue
    return None


def steam_running() -> bool:
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq steam.exe", "/NH"],
            capture_output=True, text=True, timeout=6,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return "steam.exe" in (out.stdout or "").lower()
    except Exception:  # noqa: BLE001
        return False


def steam_cell_override() -> dict:
    """读取 Steam 客户端当前的 CellIDServerOverride。"""
    path = steam_config_path()
    if path is None:
        return {"ok": False, "value": "", "path": "", "running": steam_running(),
                "message": "未找到 Steam 客户端（config.vdf）"}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return {"ok": False, "value": "", "path": str(path), "running": steam_running(),
                "message": "读取 config.vdf 失败：" + str(exc)}
    m = re.search(r'"CellIDServerOverride"\s+"(\d+)"', text)
    return {"ok": True, "value": m.group(1) if m else "", "path": str(path),
            "running": steam_running(), "message": ""}


def apply_steam_cell(region: str = "cn") -> dict:
    """把区服写入 Steam 客户端 config.vdf（CellIDServerOverride）。

    必须完全退出 Steam 后再写，否则启动时会被覆写；写入前自动留一份
    config.vdf.sprout.bak 备份。
    """
    reg = region_by_id(region)
    path = steam_config_path()
    if path is None:
        return {"ok": False, "message": "未找到 Steam 客户端配置（config.vdf），请确认已安装 Steam"}
    if steam_running():
        return {"ok": False, "message": "请先完全退出 Steam 再应用区服（Steam 运行时该配置会被覆写）"}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        return {"ok": False, "message": "读取 config.vdf 失败：" + str(exc)}
    line = '"CellIDServerOverride"\t\t"' + str(reg["cell"]) + '"'
    if re.search(r'"CellIDServerOverride"\s+"\d+"', text):
        new = re.sub(r'"CellIDServerOverride"\s+"\d+"', lambda _m: line, text, count=1)
    else:
        new = re.sub(r'("Steam"\s*\{)', lambda m: m.group(1) + "\n\t\t\t\t" + line, text, count=1)
    if new == text:
        return {"ok": False, "message": "config.vdf 中未找到可写入位置，已放弃修改"}
    try:
        backup = path.with_name("config.vdf.sprout.bak")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(new, encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "message": "写入 config.vdf 失败：" + str(exc)}
    return {"ok": True, "cell": str(reg["cell"]),
            "message": "已把 Steam 区服写为 " + str(reg["name"]) + "（cell " + str(reg["cell"]) + "），重启 Steam 生效"}


ACCEL = Accelerator()


def rewrite(url: str) -> str:
    """供 net 调用：按加速设置改写 GitHub 地址。"""
    try:
        return ACCEL.rewrite(url)
    except Exception:  # noqa: BLE001
        return url
