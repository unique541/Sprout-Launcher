"""内存优化：把本进程与游戏进程的工作集（working set）交还系统。

做法是标准的 EmptyWorkingSet（等价于 RAMMap 的 Empty Working Set）：
把页面从物理内存挪出去，进程本身不受影响、不会被结束，是安全的只读式释放。
默认只处理「启动器自身 + Minecraft 的 java/javaw 进程」，不会去动其它程序。
"""
from __future__ import annotations

import ctypes
import gc
import time
from ctypes import wintypes

_PROCESS_SET_QUOTA = 0x0100
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_TH32CS_SNAPPROCESS = 0x00000002
_MAX_PATH = 260

_JAVA_NAMES = ("java.exe", "javaw.exe", "javaws.exe")

PLAYER_SCOPE = "player"      # 启动器自身 + 游戏进程（默认，最安全）
ALL_SCOPE = "all-user"       # 额外包含当前用户下其它前台/后台进程


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * _MAX_PATH),
    ]


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _kernel32():
    return ctypes.WinDLL("kernel32", use_last_error=True)


def _psapi():
    return ctypes.WinDLL("psapi", use_last_error=True)


def _mb(value: int | float) -> int:
    return int(round(float(value) / (1024 * 1024)))


def memory_status() -> dict:
    """当前物理内存占用（MB）。"""
    stat = _MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    ok = False
    try:
        ok = bool(_kernel32().GlobalMemoryStatusEx(ctypes.byref(stat)))
    except Exception:  # noqa: BLE001
        ok = False
    if not ok:
        return {"ok": False, "totalMb": 0, "availMb": 0, "usedMb": 0,
                "percent": 0, "message": "无法读取系统内存信息"}
    total = _mb(stat.ullTotalPhys)
    avail = _mb(stat.ullAvailPhys)
    return {
        "ok": True,
        "totalMb": total,
        "availMb": avail,
        "usedMb": max(0, total - avail),
        "percent": int(stat.dwMemoryLoad),
        "message": "",
    }


def _iter_processes() -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    try:
        k32 = _kernel32()
        snap = k32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
        if snap in (None, -1) or int(snap) == -1:
            return out
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        try:
            more = k32.Process32FirstW(snap, ctypes.byref(entry))
            while more:
                name = str(entry.szExeFile or "")
                out.append((int(entry.th32ProcessID), name))
                more = k32.Process32NextW(snap, ctypes.byref(entry))
        finally:
            k32.CloseHandle(snap)
    except Exception:  # noqa: BLE001
        return out
    return out


def _working_set_mb(pid: int) -> int:
    try:
        k32 = _kernel32()
        ps = _psapi()
        handle = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return 0
        try:
            counters = _PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
            if ps.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return _mb(counters.WorkingSetSize)
        finally:
            k32.CloseHandle(handle)
    except Exception:  # noqa: BLE001
        return 0
    return 0


def empty_working_set(pid: int) -> bool:
    """把指定进程的工作集交还系统；失败（权限不足/已退出）返回 False。"""
    try:
        k32 = _kernel32()
        ps = _psapi()
        handle = k32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            return bool(ps.EmptyWorkingSet(handle))
        finally:
            k32.CloseHandle(handle)
    except Exception:  # noqa: BLE001
        return False


def optimize(scope: str = PLAYER_SCOPE) -> dict:
    """执行内存优化，返回优化前后数值与释放量。"""
    started = time.perf_counter()
    my_pid = -1
    try:
        my_pid = int(_kernel32().GetCurrentProcessId())
    except Exception:  # noqa: BLE001
        my_pid = -1

    before = memory_status()
    self_before = _working_set_mb(my_pid) if my_pid > 0 else 0

    gc.collect()
    targets: list[tuple[int, str]] = []
    if my_pid > 0:
        targets.append((my_pid, "SproutLauncher"))
    for pid, name in _iter_processes():
        if pid <= 0 or pid == my_pid:
            continue
        low = name.lower()
        if low in _JAVA_NAMES:
            targets.append((pid, name))
        elif scope == ALL_SCOPE and low and not low.startswith(("system", "registry", "memory")):
            targets.append((pid, name))

    trimmed = 0
    skipped = 0
    for pid, _name in targets:
        if empty_working_set(pid):
            trimmed += 1
        else:
            skipped += 1

    after = memory_status()
    self_after = _working_set_mb(my_pid) if my_pid > 0 else 0
    freed = int(after.get("availMb", 0)) - int(before.get("availMb", 0))
    if freed < 0:
        freed = 0
    ratio = int(round((after.get("availMb", 0) / max(1, after.get("totalMb", 1))) * 100))
    return {
        "ok": bool(before.get("ok")),
        "totalMb": after.get("totalMb", 0),
        "beforeAvailMb": before.get("availMb", 0),
        "beforeUsedMb": before.get("usedMb", 0),
        "beforePercent": before.get("percent", 0),
        "afterAvailMb": after.get("availMb", 0),
        "afterUsedMb": after.get("usedMb", 0),
        "afterPercent": after.get("percent", 0),
        "availPercent": ratio,
        "freedMb": freed,
        "selfBeforeMb": self_before,
        "selfAfterMb": self_after,
        "trimmed": trimmed,
        "skipped": skipped,
        "scope": scope,
        "elapsedMs": int((time.perf_counter() - started) * 1000),
        "message": (f"可用内存 {before.get('availMb', 0)} → {after.get('availMb', 0)} MB，"
                    f"释放 {freed} MB，处理 {trimmed} 个进程"),
    }


def game_processes() -> list[dict]:
    """当前正在运行的 Minecraft（java）进程，用于界面展示。"""
    out: list[dict] = []
    for pid, name in _iter_processes():
        if name.lower() in _JAVA_NAMES:
            out.append({"pid": pid, "name": name, "memoryMb": _working_set_mb(pid)})
    out.sort(key=lambda x: -x.get("memoryMb", 0))
    return out[:8]
