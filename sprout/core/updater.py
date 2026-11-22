"""自更新：读取 GitHub Releases，比对版本，下载新版安装包并交给安装程序。

流程：启动器启动 -> 后台请求 releases/latest 比对版本 -> 有新版弹窗（含版本号与更新说明）
-> 用户确认下载 -> 落盘 %APPDATA%\\Sprout\\downloads -> 提示是否安装 -> 启动安装程序后
启动器退出（Windows 上运行中的 exe 会被锁，必须先退出才能覆盖）-> 安装程序安装完成后
自删安装包（见 packaging/sprout_setup.iss 的 [Run] 延迟删除）。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable

from .. import paths
from . import net

APP_VERSION = "0.3.2"

# 默认更新仓库（用户/仓库名），设置里填了 update_repo 时以设置为准
DEFAULT_REPO = "unique541/Sprout-Launcher"


def _parse(version: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", version or "")
    return tuple(int(n) for n in nums[:3]) if nums else (0,)


def is_newer(remote: str, local: str = APP_VERSION) -> bool:
    return _parse(remote) > _parse(local)


def tag_version(tag: str) -> str:
    """标签名里抽出干净的版本号：SproutLauncher0.2.0 -> 0.2.0，v1.2.3 -> 1.2.3。"""
    m = re.search(r"\d+(?:\.\d+){1,3}", str(tag or ""))
    return m.group(0) if m else str(tag or "").strip().lstrip("vV")


def clean_notes(text: str, limit: int = 1500) -> str:
    """把 Release 正文压成适合弹窗展示的纯文本：去掉图片/HTML/链接语法。"""
    s = str(text or "")
    if not s.strip():
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"^\s{0,3}#{1,6}\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"(\*\*|__|`)", "", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    if len(s) > limit:
        s = s[:limit].rstrip() + "…"
    return s


def _pick_asset(assets: list) -> dict:
    """优先 setup/installer 安装包，其次任意 exe，最后 zip/msi。"""
    best = None
    for a in assets or []:
        name = (a.get("name") or "").lower()
        if not name.endswith((".exe", ".zip", ".msi")):
            continue
        if best is None:
            best = a
        if "setup" in name or "installer" in name:
            return a
    return best or {}


def check(repo: str = "") -> dict:
    """repo 形如 "unique541/Sprout-Launcher"；留空用 DEFAULT_REPO。"""
    repo = (repo or DEFAULT_REPO).strip()
    if "/" not in repo:
        raise RuntimeError("更新仓库格式应为 用户名/仓库名")
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    data = None
    first_exc: Exception | None = None
    try:
        # 先直连：GitHub 加速镜像基本不代理 api.github.com，套加速反而报域名解析失败
        data = net.get_json(url, mirror="official", timeout=25.0, accel=False)
    except Exception as exc:  # noqa: BLE001
        first_exc = exc
        try:
            data = net.get_json(url, mirror="official", timeout=25.0, accel=True)
        except Exception:  # noqa: BLE001
            data = None
    if data is None:
        text = str(first_exc or "")
        if "404" in text:
            raise RuntimeError("该仓库还没有发布发行版（或仓库名有误）") from first_exc
        if "403" in text or "rate limit" in text.lower():
            raise RuntimeError("GitHub 接口访问受限，请稍后再试") from first_exc
        raise RuntimeError(f"无法访问 GitHub：{text[:80]}") from first_exc
    tag = str(data.get("tag_name") or data.get("name") or "").strip()
    best = _pick_asset(data.get("assets") or [])
    return {
        "repo": repo,
        "version": tag_version(tag),
        "tag": tag,
        "newer": is_newer(tag),
        "current": APP_VERSION,
        "notes": clean_notes(data.get("body") or ""),
        "page": data.get("html_url") or "",
        "title": str(data.get("name") or tag),
        "asset_name": best.get("name", ""),
        "asset_url": best.get("browser_download_url", ""),
        "asset_size": int(best.get("size") or 0),
        "published": str(data.get("published_at") or "")[:10],
    }


def downloads_dir() -> Path:
    d = paths.app_dir() / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def download(info: dict, on_progress: Callable[[str, int, int], None] | None = None) -> Path:
    on_progress = on_progress or (lambda *a: None)
    url = info.get("asset_url") or ""
    if not url:
        raise RuntimeError("该发行版没有可下载的安装包")
    target_dir = downloads_dir()
    dest = target_dir / (info.get("asset_name") or Path(url).name)
    # 已下载且完整就直接复用，省一次 100MB 的重复下载
    expect = int(info.get("asset_size") or 0)
    if dest.exists() and (expect <= 0 or dest.stat().st_size == expect):
        on_progress("已存在更新包", 1, 1)
        return dest
    # Downloader.run 的 on_progress 是按“已完成文件数”回调，单个安装包只有 0/1 两次，
    # 进度条会一直停在 0 然后突然跳满；改挂 on_bytes（每 0.2 秒报一次已下载字节）驱动进度。
    total_hint = expect

    def _byte_progress(done: int, total: int) -> None:
        size = int(total or total_hint or 0)
        on_progress("下载更新包", int(done), size)

    on_progress("下载更新包", 0, total_hint)

    def _run(accel: bool):
        dl = net.Downloader("official", accel=accel)
        dl.on_bytes = _byte_progress
        # 带上 size 让 net 层对大安装包走分段多连接：既提速，进度也按字节匀速推进
        return dl.run([net.DownloadTask(url, dest, size=total_hint)])

    _total, failures = _run(False)
    if failures and not dest.exists():
        # 直连失败的真实原因优先展示，镜像重试只做后备不覆盖提示
        first_msg = str(failures[0][1])
        _total, failures = _run(True)
        if failures and not dest.exists():
            msg = first_msg
            if "404" in msg or "403" in msg:
                msg = "安装包下载失败（可能已被删除或访问受限），请到 GitHub 发布页手动下载"
            raise RuntimeError(msg)
    if dest.exists() and expect > 0 and dest.stat().st_size != expect:
        raise RuntimeError("安装包大小校验失败，请重新下载")
    on_progress("下载完成", 1, 1)
    return dest


def launch_installer(path: Path) -> None:
    """启动安装程序（独立进程，退出启动器后仍存活）。"""
    p = Path(path)
    if not p.exists():
        raise RuntimeError("安装包不存在，请重新下载")
    subprocess.Popen([str(p)], cwd=str(p.parent), close_fds=True)


def cleanup_downloads(keep: str = "") -> None:
    """清掉下载目录里除 keep 之外的旧安装包，避免每次更新越堆越多。"""
    try:
        for f in downloads_dir().iterdir():
            if f.is_file() and f.name != keep and f.suffix.lower() in (".exe", ".msi", ".zip"):
                f.unlink(missing_ok=True)
    except OSError:
        pass
