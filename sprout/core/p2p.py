"""P2P 联机：基于 EasyTier 组虚拟局域网，游戏内走「直接连接」。

只负责拉起/停止隧道与解析虚拟 IP，不改游戏文件。
二进制不内置于仓库，首次使用时从官方 GitHub Releases 拉取。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable

from .. import paths
from . import net

REPO_API = "https://api.github.com/repos/EasyTier/EasyTier/releases/latest"
EXE = "easytier-core.exe" if os.name == "nt" else "easytier-core"
CLI = "easytier-cli.exe" if os.name == "nt" else "easytier-cli"
IP_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")


def bin_dir() -> Path:
    p = paths.app_dir() / "bin"
    p.mkdir(parents=True, exist_ok=True)
    return p


def core_path() -> Path:
    return bin_dir() / EXE


def cli_path() -> Path:
    return bin_dir() / CLI


def is_installed() -> bool:
    return core_path().exists()


def _asset_url() -> tuple[str, str]:
    """挑当前平台可用的 release 资源。"""
    data = net.get_json(REPO_API, mirror="official", timeout=40.0)
    assets = data.get("assets") or []
    platform_tag = "windows" if os.name == "nt" else ("darwin" if os.uname().sysname == "Darwin" else "linux")
    arch_tag = "x86_64" if os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64").lower() in ("amd64", "x86_64") else "aarch64"
    for a in assets:
        name = (a.get("name") or "").lower()
        if platform_tag in name and (arch_tag in name or "x64" in name) and name.endswith(".zip"):
            return a.get("name", ""), a.get("browser_download_url", "")
    for a in assets:
        name = (a.get("name") or "").lower()
        if platform_tag in name and name.endswith(".zip"):
            return a.get("name", ""), a.get("browser_download_url", "")
    raise RuntimeError("未在 EasyTier 最新发行版中找到当前平台的可执行包")


def install(on_progress: Callable[[str, int, int], None] | None = None) -> Path:
    on_progress = on_progress or (lambda *a: None)
    on_progress("查询 EasyTier 版本", 0, 1)
    name, url = _asset_url()
    if not url:
        raise RuntimeError("未取到下载地址")
    archive = paths.cache_dir() / name
    on_progress("下载 EasyTier", 0, 1)
    downloader = net.Downloader("official")
    downloader.run(
        [net.DownloadTask(url, archive)],
        lambda done, total, nm: on_progress("下载 EasyTier", done, total),
    )
    on_progress("解压 EasyTier", 0, 1)
    with zipfile.ZipFile(archive) as zf:
        for member in zf.namelist():
            base = Path(member).name
            if base in (EXE, CLI):
                target = bin_dir() / base
                with zf.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                try:
                    os.chmod(target, 0o755)
                except OSError:
                    pass
    archive.unlink(missing_ok=True)
    if not core_path().exists():
        raise RuntimeError("解压后未找到 easytier-core 可执行文件")
    on_progress("EasyTier 就绪", 1, 1)
    return core_path()


class Tunnel:
    """一个联机房间 = 一个 easytier-core 进程。"""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.ip: str = ""
        self.lines: list[str] = []
        self.backend: str = "easytier"
        self.cmd: list[str] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def _core_for(self, backend: str) -> Path | None:
        """按联机方式选内核：陶瓦联机优先用本机已装的陶瓦/EasyTier，其次内置内核。"""
        if backend == "terracotta":
            found = find_terracotta_core()
            if found is not None:
                return found
        return core_path() if core_path().exists() else None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(
        self,
        room: str,
        secret: str = "",
        peers: str = "",
        on_line: Callable[[str, str], None] | None = None,
        backend: str = "easytier",
    ) -> None:
        if self.running:
            return
        self.backend = backend or "easytier"
        core = self._core_for(self.backend)
        if core is None or not Path(core).exists():
            raise RuntimeError("尚未安装 EasyTier 运行组件")
        cmd = [str(core), "--network-name", room]
        if secret:
            cmd += ["--network-secret", secret]
        for peer in [p.strip() for p in (peers or "").split(",") if p.strip()]:
            cmd += ["-p", peer]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self.lines = []
        self.cmd = cmd
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
        self._thread = threading.Thread(target=self._pump, args=(on_line,), daemon=True)
        self._thread.start()

    def _pump(self, on_line: Callable[[str, str], None] | None) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for raw in self.proc.stdout:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            with self._lock:
                self.lines.append(line)
                if len(self.lines) > 400:
                    del self.lines[:120]
            level = "error" if re.search(r"error|fail|panic", line, re.I) else "info"
            if not self.ip:
                m = re.search(r"(?:ipv4|ip|addr)[^\d]{0,12}(\d{1,3}(?:\.\d{1,3}){3})", line, re.I)
                if m and not m.group(1).startswith(("127.", "0.")):
                    self.ip = m.group(1)
            if on_line:
                on_line(line, level)
        if on_line:
            on_line("联机隧道已退出", "warn")

    def stop(self) -> None:
        proc = self.proc
        self.proc = None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                for _ in range(20):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
                if proc.poll() is None:
                    proc.kill()
            except OSError:
                pass

    def snapshot(self) -> str:
        with self._lock:
            return "\n".join(self.lines[-80:])


def room_default_port() -> int:
    return 25565


# 支持的联机方式：p2p = 自带 EasyTier 内网穿透；terracotta = 陶瓦联机（同 EasyTier 房间协议）；
# lan = 局域网直连，不建隧道，仅整理本机局域网地址与游戏端口。
BACKENDS: dict[str, str] = {
    "p2p": "P2P 联机",
    "terracotta": "陶瓦联机",
    "lan": "局域网直连",
}


def backend_label(kind: str) -> str:
    return BACKENDS.get(kind or "p2p", BACKENDS["p2p"])


def find_terracotta_core() -> Path | None:
    """探测本机已安装的陶瓦联机 / EasyTier 内核（只读探测，不安装任何东西）。"""
    cands: list[Path] = []
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA") or (home / "AppData" / "Local"))
    roaming = Path(os.environ.get("APPDATA") or (home / "AppData" / "Roaming"))
    for base in (
        local / "Programs" / "Terracotta",
        local / "Terracotta",
        roaming / "Terracotta",
        Path(os.environ.get("ProgramFiles") or "C:/Program Files") / "Terracotta",
        Path(os.environ.get("ProgramFiles(x86)") or "C:/Program Files (x86)") / "Terracotta",
        home / ".terracotta",
    ):
        cands.append(base)
    exe_names = ("easytier-core.exe", "terracotta.exe") if os.name == "nt" else ("easytier-core",)
    for base in cands:
        if not base.is_dir():
            continue
        for name in exe_names:
            direct = base / name
            if direct.exists():
                return direct
        try:
            for path in base.rglob(exe_names[0]):
                if path.is_file():
                    return path
        except OSError:
            continue
    which = shutil.which(exe_names[0])
    if which:
        return Path(which)
    return None


def terracotta_available() -> bool:
    return find_terracotta_core() is not None


def local_ipv4() -> str:
    """取本机局域网 IPv4（不真正发包）。"""
    import socket

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.3)
            s.connect(("223.5.5.5", 80))
            return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
