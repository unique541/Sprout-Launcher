"""Java 运行时：探测、版本匹配、自动下载安装。"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import paths
from . import net

JAVA_EXE = "java.exe" if os.name == "nt" else "java"


@dataclass
class JavaRuntime:
    path: str
    major: int
    version: str
    arch: str
    vendor: str = ""
    source: str = "system"

    @property
    def label(self) -> str:
        return f"Java {self.major} ({self.version}){' · ' + self.vendor if self.vendor else ''}"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "major": self.major,
            "version": self.version,
            "arch": self.arch,
            "vendor": self.vendor,
            "source": self.source,
            "label": self.label,
        }


def _run(path: str, args: list[str], timeout: float = 12.0) -> str:
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            [path] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=flags,
            encoding="utf-8",
            errors="replace",
        )
        return (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.SubprocessError):
        return ""


def probe(java_path: str | Path) -> JavaRuntime | None:
    """执行 java -XshowSettings:properties -version 解析运行时信息。"""
    p = str(java_path)
    if not Path(p).exists():
        return None
    out = _run(p, ["-XshowSettings:properties", "-version"])
    if not out:
        return None
    version = arch = vendor = ""
    m = re.search(r"java\.version\s*=\s*(\S+)", out)
    if m:
        version = m.group(1)
    m = re.search(r"java\.vendor\s*=\s*(.+)", out)
    if m:
        vendor = m.group(1).strip()
    m = re.search(r"os\.arch\s*=\s*(\S+)", out)
    if m:
        arch = m.group(1)
    major = 0
    m = re.match(r"(\d+)", version or "")
    if m:
        major = int(m.group(1))
        if major == 1:
            m2 = re.match(r"1\.(\d+)", version)
            if m2:
                major = int(m2.group(1))
    if not major:
        m = re.search(r'version "(\d+)', out)
        if m:
            major = int(m.group(1))
    if not version:
        return None
    return JavaRuntime(path=p, major=major, version=version, arch=arch, vendor=vendor)


def _registry_javas() -> list[str]:
    if os.name != "nt":
        return []
    found: list[str] = []
    roots = (
        r"SOFTWARE\JavaSoft\JDK",
        r"SOFTWARE\JavaSoft\JRE",
        r"SOFTWARE\JavaSoft\Java Development Kit",
        r"SOFTWARE\JavaSoft\Java Runtime Environment",
    )
    try:
        import winreg
    except ImportError:
        return []
    for root in roots:
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, root, 0, winreg.KEY_READ | view) as k:
                        sub, _ = winreg.QueryInfoKey(k)[0], 0
                        for i in range(sub):
                            name = winreg.EnumKey(k, i)
                            with winreg.OpenKey(k, name) as kk:
                                home, _ = winreg.QueryValueEx(kk, "JavaHome")
                                found.append(str(Path(home) / "bin" / JAVA_EXE))
                except OSError:
                    continue
    return found


def _scan_dirs() -> list[str]:
    roots = [
        r"C:\Program Files\Java",
        r"C:\Program Files\Eclipse Adoptium",
        r"C:\Program Files\Zulu",
        r"C:\Program Files\BellSoft",
        r"C:\Program Files\Microsoft",
        r"C:\Program Files (x86)\Java",
        r"C:\Program Files (x86)\Eclipse Adoptium",
    ]
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            roots += [str(Path(base) / "Programs" / "Eclipse Adoptium"), str(Path(base) / "Java")]
    # 已由本启动器下载的运行时
    if paths.runtimes_dir().exists():
        roots.append(str(paths.runtimes_dir()))
    found: list[str] = []
    for root in roots:
        rp = Path(root)
        if not rp.exists():
            continue
        for exe in rp.rglob(JAVA_EXE):
            if "bin" in exe.parts:
                found.append(str(exe))
    return found


def discover(extra: list[str] | None = None) -> list[JavaRuntime]:
    """扫描系统上所有可用 Java，去重后按 major 降序返回。"""
    candidates: list[str] = []
    for env in ("JAVA_HOME", "JDK_HOME"):
        home = os.environ.get(env)
        if home:
            candidates.append(str(Path(home) / "bin" / JAVA_EXE))
    which = shutil.which("java")
    if which:
        candidates.append(which)
    candidates += _registry_javas()
    candidates += _scan_dirs()
    candidates += extra or []

    result: list[JavaRuntime] = []
    seen: set[str] = set()
    for c in candidates:
        try:
            key = str(Path(c).resolve()).lower()
        except OSError:
            key = c.lower()
        if key in seen:
            continue
        seen.add(key)
        rt = probe(c)
        if rt:
            result.append(rt)
    result.sort(key=lambda r: (-r.major, r.path))
    return result


# Minecraft 版本 -> 建议 Java 主版本（兜底用；优先读 version json 的 javaVersion）
def fallback_major(version_id: str) -> int:
    m = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", version_id)
    if not m:
        return 8
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if major == 1 and minor <= 16:
        return 8
    if major == 1 and minor == 17:
        return 17
    if major == 1 and minor <= 20 and not (minor == 20 and patch >= 5):
        return 17
    return 21


def required_major(version_data: dict) -> int:
    """以版本 JSON 的 javaVersion 为准，缺失时按版本号兜底。"""
    jv = version_data.get("javaVersion") or {}
    major = jv.get("majorVersion")
    if isinstance(major, int) and major > 0:
        return major
    return fallback_major(version_data.get("id") or version_data.get("inheritsFrom") or "1.20")


def pick(runtimes: list[JavaRuntime], want: int) -> JavaRuntime | None:
    """挑选满足要求且最接近的运行时。"""
    ok = [r for r in runtimes if r.major >= want]
    if ok:
        return min(ok, key=lambda r: (r.major - want, r.path))
    exact = [r for r in runtimes if r.major == want]
    return exact[0] if exact else None


ADOPTIUM_API = (
    "https://api.adoptium.net/v3/assets/latest/{major}/hotspot"
    "?architecture={arch}&image_type=jre&os={os}&vendor=eclipse"
)


def _platform_args() -> tuple[str, str]:
    arch = "x64" if platform.machine().lower() in ("amd64", "x86_64") else "aarch64"
    osname = "windows" if os.name == "nt" else ("mac" if platform.system() == "Darwin" else "linux")
    return arch, osname


def download_runtime(
    major: int,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> JavaRuntime | None:
    """从 Adoptium 下载 Temurin JRE 并解压到本启动器目录，返回运行时。"""
    arch, osname = _platform_args()
    url = ADOPTIUM_API.format(major=major, arch=arch, os=osname)
    data = net.get_json(url, mirror="official", timeout=60.0)
    if not isinstance(data, list) or not data:
        return None
    pkg = data[0].get("binary", {}).get("package", {})
    link = pkg.get("link")
    checksum = pkg.get("checksum", "")
    if not link:
        return None

    target = paths.runtimes_dir() / f"jre-{major}"
    archive = paths.cache_dir() / Path(link).name
    if on_progress:
        on_progress("正在下载 Java 运行时", 0, 1)
    archive.parent.mkdir(parents=True, exist_ok=True)
    downloader = net.Downloader("official")
    _total, failures = downloader.run(
        [net.DownloadTask(link, archive)],
        lambda done, total, name: on_progress("正在下载 Java 运行时", done, total) if on_progress else None,
    )
    if failures and not archive.exists():
        return None
    if checksum:
        try:
            if net.sha1_of(archive) != checksum:
                pass  # 部分镜像提供 SHA256，此处不阻断
        except OSError:
            pass

    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    if archive.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(paths.runtimes_dir())
        extracted = [p for p in paths.runtimes_dir().iterdir() if p.is_dir() and p.name != f"jre-{major}"]
        if extracted:
            newest = max(extracted, key=lambda p: p.stat().st_mtime)
            shutil.move(str(newest), str(target))
    archive.unlink(missing_ok=True)

    exe = target / "bin" / JAVA_EXE
    if exe.exists():
        rt = probe(exe)
        if rt:
            rt.source = "sprout"
            return rt
    return None
