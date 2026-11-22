"""网络层：镜像改写、HTTP 客户端、统一并发下载内核。

所有网络下载（游戏本体、资源库、模组、世界、整合包、Java、联机组件、更新包）
统一走本模块的 Downloader / download_file，默认 16 线程，配置项 concurrency 可调，
硬下限 10 线程，并对外暴露实时速度（current_speed / format_speed）。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Iterable

import httpx

UA = "SproutLauncher/0.1 (contact: local)"

# 下载并发：默认 16，配置可调，最低 10（多线程下载硬下限）
DEFAULT_CONCURRENCY = 16
MIN_CONCURRENCY = 10
MAX_CONCURRENCY = 64
CHUNK_SIZE = 128 * 1024
# 单文件超过该体积时按 HTTP Range 切成多段并行拉取，吃满带宽
SEGMENT_MIN_SIZE = 8 * 1024 * 1024
SEGMENT_PARTS = 4

# BMCLAPI 兼容重写规则（官方 URL 前缀 -> 镜像前缀）
BMCLAPI_RULES: tuple[tuple[str, str], ...] = (
    ("https://launchermeta.mojang.com", "https://bmclapi2.bangbang93.com"),
    ("https://launcher.mojang.com", "https://bmclapi2.bangbang93.com"),
    ("https://piston-meta.mojang.com", "https://bmclapi2.bangbang93.com"),
    ("https://piston-data.mojang.com", "https://bmclapi2.bangbang93.com"),
    ("https://libraries.minecraft.net", "https://bmclapi2.bangbang93.com/maven"),
    ("https://resources.download.minecraft.net", "https://bmclapi2.bangbang93.com/assets"),
    ("https://files.minecraftforge.net/maven", "https://bmclapi2.bangbang93.com/maven"),
    ("https://maven.minecraftforge.net", "https://bmclapi2.bangbang93.com/maven"),
    ("https://maven.neoforged.net/releases", "https://bmclapi2.bangbang93.com/maven"),
)

FASTMIRROR_RULES: tuple[tuple[str, str], ...] = (
    ("https://piston-meta.mojang.com", "https://fastmcmirror.org"),
    ("https://launchermeta.mojang.com", "https://fastmcmirror.org"),
    ("https://piston-data.mojang.com", "https://fastmcmirror.org"),
)

MANIFEST_URL_OFFICIAL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MANIFEST_URL_BMCLAPI = "https://bmclapi2.bangbang93.com/mc/game/version_manifest.json"


_EFFECTIVE = "official"  # auto 模式下最近一次实测可用的源
_CANDIDATES = ("official", "bmclapi", "fastmc")


def effective_mirror() -> str:
    return _EFFECTIVE


def set_effective_mirror(mirror: str) -> None:
    global _EFFECTIVE
    if mirror in _CANDIDATES:
        _EFFECTIVE = mirror


def _apply_rules(url: str, rules) -> str:
    for src, dst in rules:
        if url.startswith(src):
            return dst + url[len(src):]
    return url


def rewrite_url(url: str, mirror: str = "auto", accel: bool = True) -> str:
    """按镜像策略改写 URL。auto 表示跟随当前实测可用的源。

    镜像改写之后再交给加速模块处理：开启 GitHub 加速时，GitHub 域名会被
    套上镜像前缀；未开启或非 GitHub 地址原样返回。
    accel=False 时跳过加速层（更新检查等 API 请求需要直连，镜像多不代理 api.github.com）。
    """
    m = _EFFECTIVE if mirror == "auto" else mirror
    if m == "official":
        out = url
    elif m == "fastmc":
        out = _apply_rules(url, FASTMIRROR_RULES)
    else:
        out = _apply_rules(url, BMCLAPI_RULES)
    return _accelerate(out) if accel else out


def _accelerate(url: str) -> str:
    """加速层（GitHub 镜像）；任何异常都退回原地址，不影响下载。"""
    try:
        from . import accelerate

        return accelerate.rewrite(url)
    except Exception:  # noqa: BLE001
        return url


def url_for(url: str, mirror: str = "auto", accel: bool = True) -> str:
    """兼容清单文件名差异：BMCLAPI/FastMC 只有 version_manifest.json。"""
    if mirror != "official" and "version_manifest_v2.json" in url:
        url = url.replace("version_manifest_v2.json", "version_manifest.json")
    return rewrite_url(url, mirror, accel)


def manifest_url(mirror: str = "auto") -> str:
    return MANIFEST_URL_OFFICIAL if (_EFFECTIVE if mirror == "auto" else mirror) == "official" else MANIFEST_URL_BMCLAPI


def ca_bundle() -> str | bool:
    """合并 certifi 与 Windows 系统根证书：本机代理/加速器常注入自签证书。"""
    try:
        from sprout import paths as _paths

        cache = _paths.cache_dir() / "ca-bundle.pem"
    except Exception:
        return True
    try:
        if cache.exists() and cache.stat().st_size > 2048:
            return str(cache)
    except OSError:
        return True
    try:
        import ssl

        import certifi

        chunks = [Path(certifi.where()).read_bytes()]
        for store in ("ROOT", "CA"):
            for cert, enc, _trust in ssl.enum_certificates(store):
                if enc == "x509_asn":
                    try:
                        chunks.append(ssl.DER_cert_to_PEM_cert(cert).encode())
                    except ValueError:
                        continue
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(b"".join(chunks))
        return str(cache)
    except Exception:
        return True


def client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(timeout, connect=10.0),
        follow_redirects=True,
        headers={"User-Agent": UA},
        http2=False,
        verify=ca_bundle(),
    )


def get_json(url: str, mirror: str = "auto", timeout: float = 30.0, accel: bool = True):
    """auto：按 当前有效源 -> 官方 -> BMCLAPI -> FastMC 依次回退，并记住成功源。

    accel=False 时跳过 GitHub 加速层，用于必须直连的接口（如 GitHub API）。
    """
    if mirror == "auto":
        order = [_EFFECTIVE] + [m for m in _CANDIDATES if m != _EFFECTIVE]
    else:
        order = [mirror]

    last: Exception | None = None
    for m in order:
        try:
            with client(timeout) as c:
                r = c.get(url_for(url, m, accel))
                r.raise_for_status()
                data = r.json()
            set_effective_mirror(m)
            return data
        except Exception as exc:  # 网络层异常：换下一个源
            last = exc
    raise last if last is not None else RuntimeError("no mirror available")


def long_path(p: Path | str) -> str:
    r"""Windows 下加 \\?\ 前缀，绕开 260 字符 MAX_PATH 限制。"""
    s = os.path.abspath(str(p))
    if os.name != "nt":
        return s
    if s.startswith("\\\\?\\"):
        return s
    if s.startswith("\\\\"):
        return "\\\\?\\UNC" + s[1:]
    return "\\\\?\\" + s


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    with open(long_path(path), "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 256), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- 并发配置
def resolve_concurrency(value=None) -> int:
    """下载线程数：未显式指定时读配置，统一夹在 [10, 64] 内。"""
    if value is None:
        try:
            from ..config import Config

            value = Config().get("concurrency")
        except Exception:  # noqa: BLE001
            value = DEFAULT_CONCURRENCY
    try:
        num = int(value)
    except (TypeError, ValueError):
        num = DEFAULT_CONCURRENCY
    return max(MIN_CONCURRENCY, min(MAX_CONCURRENCY, num))


# ---------------------------------------------------------------- 速度计
class _SpeedMeter:
    """全局下载速度计：所有下载线程把字节数喂进来，界面按它显示速度。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bytes = 0
        self._speed = 0.0
        self._last = time.monotonic()

    def add(self, count: int) -> None:
        if count <= 0:
            return
        with self._lock:
            self._bytes += count

    def sample(self) -> float:
        now = time.monotonic()
        with self._lock:
            delta = self._bytes
            self._bytes = 0
            span = now - self._last
            self._last = now
        if span <= 0:
            return self._speed
        inst = delta / span
        self._speed = inst if self._speed <= 0 else self._speed * 0.55 + inst * 0.45
        return self._speed

    def reset(self) -> None:
        with self._lock:
            self._bytes = 0
            self._speed = 0.0
            self._last = time.monotonic()

    @property
    def speed(self) -> float:
        return self._speed


METER = _SpeedMeter()


def current_speed() -> float:
    """最近一次采样的下载速度（字节/秒）。"""
    return METER.speed


def format_speed(bps: float) -> str:
    v = float(bps or 0.0)
    if v <= 0:
        return ""
    units = ("B/s", "KB/s", "MB/s", "GB/s")
    for idx, unit in enumerate(units):
        if v < 1024 or idx == len(units) - 1:
            return (f"{v:.0f} {unit}" if idx == 0 else f"{v:.1f} {unit}")
        v /= 1024.0
    return ""


class DownloadTask:
    __slots__ = ("url", "dest", "sha1", "size")

    def __init__(self, url: str, dest: Path, sha1: str = "", size: int = 0) -> None:
        self.url = url
        self.dest = Path(dest)
        self.sha1 = sha1
        self.size = size

    def satisfy(self) -> bool:
        """已存在且校验通过则跳过。"""
        if not self.dest.exists() or self.dest.stat().st_size == 0:
            return False
        if not self.sha1:
            return True
        try:
            return sha1_of(self.dest) == self.sha1
        except OSError:
            return False


class Downloader:
    """统一并发下载内核。

    - 多任务：线程池按 concurrency（默认 16，下限 10）并发拉取；
    - 单文件：大文件（>= 8MB）自动按 Range 切段并行下载，失败回退单连接；
    - 断点/重试：每个任务失败后自动重试一次，临时文件一律清理，不留 .part 半成品；
    - 速度：所有线程字节量汇总到 METER，可通过 on_speed 回调实时上报。
    """

    def __init__(self, mirror: str = "auto", concurrency: int | None = None,
                 accel: bool = True) -> None:
        self.mirror = mirror
        self.accel = accel
        self.concurrency = resolve_concurrency(concurrency)
        self._lock = threading.Lock()
        self.cancelled = threading.Event()
        self._local = threading.local()
        self._clients: list[httpx.Client] = []
        self._segment = True
        # 单文件字节级进度回调（done_bytes, total_bytes）
        self.on_bytes: Callable[[int, int], None] | None = None
        self._last_emit = 0.0
        self.total_bytes = 0
        self.done_bytes = 0

    # ------------------------------------------------------------ 连接复用
    def _thread_client(self) -> httpx.Client:
        """每个工作线程复用一条连接，避免数千次 TLS 握手。"""
        c = getattr(self._local, "client", None)
        if c is None:
            c = client(60.0)
            self._local.client = c
            with self._lock:
                self._clients.append(c)
        return c

    def close(self) -> None:
        with self._lock:
            clients, self._clients = self._clients, []
        for c in clients:
            try:
                c.close()
            except Exception:
                pass
        self._local = threading.local()

    def cancel(self) -> None:
        self.cancelled.set()

    # ------------------------------------------------------------ 内部实现
    def _emit_bytes(self) -> None:
        cb = self.on_bytes
        if cb is None:
            return
        now = time.monotonic()
        if now - self._last_emit < 0.2:
            return
        self._last_emit = now
        try:
            cb(self.done_bytes, self.total_bytes)
        except Exception:  # noqa: BLE001
            pass

    def _write_stream(self, r, fh) -> None:
        for chunk in r.iter_bytes(CHUNK_SIZE):
            if self.cancelled.is_set():
                break
            fh.write(chunk)
            METER.add(len(chunk))
            with self._lock:
                self.done_bytes += len(chunk)
            self._emit_bytes()

    def _fetch_single(self, url: str, tmp: Path) -> None:
        c = self._thread_client()
        with c.stream("GET", url) as r:
            r.raise_for_status()
            size = int(r.headers.get("Content-Length") or 0)
            if size:
                with self._lock:
                    self.total_bytes = max(self.total_bytes, self.done_bytes + size)
            with open(long_path(tmp), "wb") as f:
                self._write_stream(r, f)

    def _fetch_segmented(self, url: str, tmp: Path) -> bool:
        """大文件按区间多连接下载；服务器不支持或出错时返回 False 交由单连接兜底。"""
        parts = max(2, min(SEGMENT_PARTS, self.concurrency))
        try:
            with self._thread_client().get(url, headers={"Range": "bytes=0-0"}) as probe:
                if probe.status_code != 206:
                    return False
                crange = probe.headers.get("Content-Range") or ""
                total = int(crange.rsplit("/", 1)[-1]) if "/" in crange else 0
        except Exception:  # noqa: BLE001
            return False
        if total < SEGMENT_MIN_SIZE:
            return False
        with self._lock:
            self.total_bytes = max(self.total_bytes, self.done_bytes + total)
        span = total // parts
        pieces = [tmp.with_name(tmp.name + f".{i}") for i in range(parts)]
        errors: list[Exception] = []

        def pull(idx: int) -> None:
            start = idx * span
            end = total - 1 if idx == parts - 1 else start + span - 1
            try:
                with self._thread_client().stream(
                    "GET", url, headers={"Range": f"bytes={start}-{end}"}
                ) as r:
                    r.raise_for_status()
                    with open(long_path(pieces[idx]), "wb") as f:
                        self._write_stream(r, f)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        try:
            with ThreadPoolExecutor(max_workers=parts) as pool:
                list(pool.map(pull, range(parts)))
            if self.cancelled.is_set():
                raise RuntimeError("下载已取消")
            if errors:
                raise errors[0]
            with open(long_path(tmp), "wb") as out:
                for piece in pieces:
                    with open(long_path(piece), "rb") as src:
                        shutil.copyfileobj(src, out)
            return True
        finally:
            for piece in pieces:
                try:
                    os.unlink(long_path(piece))
                except OSError:
                    pass

    def _download_task(self, task: DownloadTask) -> None:
        task.dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = task.dest.with_suffix(task.dest.suffix + ".part")
        url = rewrite_url(task.url, self.mirror, self.accel)
        last: Exception | None = None
        for attempt in range(2):
            if self.cancelled.is_set():
                raise RuntimeError("下载已取消")
            try:
                done = False
                if attempt == 0 and self._segment and int(task.size or 0) >= SEGMENT_MIN_SIZE:
                    done = self._fetch_segmented(url, tmp)
                if not done:
                    self._fetch_single(url, tmp)
                if self.cancelled.is_set():
                    raise RuntimeError("下载已取消")
                if task.sha1 and sha1_of(tmp) != task.sha1:
                    raise ValueError("SHA1 校验失败")
                os.replace(long_path(tmp), long_path(task.dest))
                return
            except Exception as exc:  # noqa: BLE001
                last = exc
                # 取消或校验失败时留下的 .part 必须立刻清掉，避免磁盘残留半成品
                try:
                    os.unlink(long_path(tmp))
                except OSError:
                    pass
                if self.cancelled.is_set():
                    break
        raise last if last is not None else RuntimeError("下载失败")

    # ------------------------------------------------------------ 批量下载
    def run(
        self,
        tasks: Iterable[DownloadTask],
        on_progress: Callable[[int, int, str], None] | None = None,
        on_speed: Callable[[float], None] | None = None,
    ) -> tuple[int, list[tuple[str, str]]]:
        pending = [t for t in tasks if not t.satisfy()]
        total = len(pending)
        failures: list[tuple[str, str]] = []
        with self._lock:
            self.total_bytes = sum(int(t.size or 0) for t in pending)
            self.done_bytes = 0
        if total == 0:
            return 0, failures

        METER.reset()
        stop = threading.Event()

        def sampler() -> None:
            while not stop.wait(0.5):
                if on_speed:
                    try:
                        on_speed(METER.sample())
                    except Exception:  # noqa: BLE001
                        pass

        sampler_thread = threading.Thread(target=sampler, daemon=True, name="sprout-speed")
        sampler_thread.start()

        done = 0

        def worker(task: DownloadTask) -> None:
            nonlocal done
            try:
                self._download_task(task)
            except Exception as exc:  # noqa: BLE001
                with self._lock:
                    failures.append((task.dest.name, str(exc)))
            finally:
                with self._lock:
                    done += 1
                    current = done
                if on_progress:
                    try:
                        on_progress(current, total, task.dest.name)
                    except Exception:  # noqa: BLE001
                        pass

        try:
            workers = max(1, min(self.concurrency, total))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(worker, t) for t in pending]
                for fu in as_completed(futures):
                    fu.result()
        finally:
            stop.set()
            sampler_thread.join(timeout=1.0)
            if on_speed:
                try:
                    on_speed(0.0)
                except Exception:  # noqa: BLE001
                    pass
            self.close()
        return total, failures


def download_file(
    url: str,
    dest: Path,
    sha1: str = "",
    size: int = 0,
    mirror: str = "auto",
    on_bytes: Callable[[int, int], None] | None = None,
    on_speed: Callable[[float], None] | None = None,
    concurrency: int | None = None,
) -> Path:
    """单文件下载统一入口：走并发内核，大文件自动多连接，进度按字节回调。"""
    dest = Path(dest)
    task = DownloadTask(url, dest, sha1, size)
    if task.satisfy():
        return dest
    dl = Downloader(mirror, concurrency)
    dl.on_bytes = on_bytes
    METER.reset()
    stop = threading.Event()

    def sampler() -> None:
        while not stop.wait(0.5):
            if on_speed:
                try:
                    on_speed(METER.sample())
                except Exception:  # noqa: BLE001
                    pass

    sampler_thread = threading.Thread(target=sampler, daemon=True, name="sprout-speed")
    sampler_thread.start()
    try:
        dl._download_task(task)
    finally:
        stop.set()
        sampler_thread.join(timeout=1.0)
        if on_speed:
            try:
                on_speed(0.0)
            except Exception:  # noqa: BLE001
                pass
        dl.close()
    if on_bytes:
        try:
            on_bytes(dl.done_bytes, dl.total_bytes or dl.done_bytes)
        except Exception:  # noqa: BLE001
            pass
    return dest
