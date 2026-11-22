"""自诊断：把「启动失败」拆成可定位的检查项，给出可执行修复建议。"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Callable

from . import java as javacore
from . import meta, net

OK, WARN, BAD, INFO = "ok", "warn", "bad", "info"

LEVEL_LABEL = {OK: "正常", WARN: "注意", BAD: "异常", INFO: "信息"}


def _item(level: str, title: str, detail: str, action: str = "") -> dict:
    return {"level": level, "title": title, "detail": detail, "action": action, "label": LEVEL_LABEL.get(level, level)}


def check_disk(mc_dir: Path) -> list[dict]:
    out: list[dict] = []
    try:
        usage = shutil.disk_usage(str(mc_dir if Path(mc_dir).exists() else Path.home()))
        free_gb = usage.free / (1024 ** 3)
        level = OK if free_gb >= 8 else (WARN if free_gb >= 3 else BAD)
        out.append(_item(level, "磁盘空间", f"剩余 {free_gb:.1f} GB", "" if level == OK else "清理磁盘或在设置中更换游戏目录"))
    except OSError as exc:
        out.append(_item(WARN, "磁盘空间", f"读取失败：{exc}"))
    return out


def check_dir(mc_dir: Path) -> list[dict]:
    out: list[dict] = []
    p = Path(mc_dir)
    if not p.exists():
        out.append(_item(BAD, "游戏目录", f"{p} 不存在", "在设置中重新选择 .minecraft 目录"))
        return out
    probe = p / ".sprout_write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        out.append(_item(OK, "目录可写", f"{p}"))
    except OSError as exc:
        out.append(_item(BAD, "目录不可写", f"{p}（{exc}）", "换到用户目录下的 .minecraft，或修复目录权限"))
    versions = p / "versions"
    count = len([d for d in versions.iterdir() if d.is_dir()]) if versions.is_dir() else 0
    out.append(_item(OK if count else WARN, "已安装版本", f"{count} 个", "" if count else "去版本库安装一个版本"))
    return out


def check_java(version_data: dict | None) -> list[dict]:
    out: list[dict] = []
    runtimes = javacore.discover()
    if not runtimes:
        out.append(_item(BAD, "Java 运行时", "未探测到任何 Java", "在设置页点击「获取 Java 17/21」"))
        return out
    labels = "、".join(sorted({f"Java {r.major}" for r in runtimes}))
    out.append(_item(OK, "Java 运行时", f"检测到 {len(runtimes)} 个：{labels}"))
    if version_data:
        want = javacore.required_major(version_data)
        picked = javacore.pick(runtimes, want)
        if picked:
            out.append(_item(OK, "Java 版本匹配", f"该版本需要 Java {want}，使用 {picked.version}"))
        else:
            out.append(_item(BAD, "Java 版本不匹配", f"该版本需要 Java {want}，本机没有可用运行时", f"下载 Java {want}"))
    return out


def check_version_files(mc_dir: Path, version_id: str) -> list[dict]:
    out: list[dict] = []
    vdir = Path(mc_dir) / "versions" / version_id
    if not (vdir / f"{version_id}.json").exists():
        out.append(_item(BAD, "版本清单", f"缺少 {version_id}.json", "重新安装该版本"))
        return out
    out.append(_item(OK, "版本清单", f"{version_id}.json"))

    try:
        data = json.loads((vdir / f"{version_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        out.append(_item(BAD, "版本清单解析", str(exc), "重新安装该版本"))
        return out

    inherits = data.get("inheritsFrom")
    jar = vdir / f"{version_id}.jar"
    if jar.exists():
        out.append(_item(OK, "客户端 jar", f"{jar.stat().st_size / 1048576:.1f} MB"))
    elif inherits:
        parent = Path(mc_dir) / "versions" / inherits / f"{inherits}.jar"
        if parent.exists():
            out.append(_item(OK, "客户端 jar", f"继承自 {inherits}"))
        else:
            out.append(_item(BAD, "客户端 jar", f"缺少 {version_id}.jar 与父版本 {inherits}.jar", "重新安装原版"))
    else:
        out.append(_item(BAD, "客户端 jar", "缺失", "重新安装该版本"))

    libs = data.get("libraries") or []
    missing: list[str] = []
    for lib in libs[:80]:
        art = (lib.get("downloads") or {}).get("artifact") or {}
        rel = art.get("path") or meta.artifact_path(lib)
        if not rel:
            continue
        if not (Path(mc_dir) / "libraries" / rel).exists():
            missing.append(rel)
    if missing:
        out.append(_item(WARN, "依赖库", f"抽查缺失 {len(missing)} 个，如 {missing[0]}", "重新运行安装补齐"))
    else:
        out.append(_item(OK, "依赖库", "抽查无缺失"))

    idx = (data.get("assetIndex") or {}).get("id")
    if idx:
        index_file = Path(mc_dir) / "assets" / "indexes" / f"{idx}.json"
        out.append(_item(OK if index_file.exists() else BAD, "资源索引", idx, "" if index_file.exists() else "重新安装补齐资源"))
    return out


def check_network(mirror: str = "auto") -> list[dict]:
    out: list[dict] = []
    try:
        url = net.manifest_url(mirror)
        data = net.get_json(url, mirror=mirror, timeout=15.0)
        count = len(data.get("versions") or []) if isinstance(data, dict) else 0
        out.append(_item(OK, "版本清单接口", f"{url.split('/')[2]}（{count} 个版本）"))
    except Exception as exc:
        out.append(_item(WARN, "版本清单接口", f"不可达：{exc}", "切换下载源后重试"))
    try:
        net.get_json("https://api.modrinth.com/v2/search?query=sodium&limit=1", mirror="official", timeout=15.0)
        out.append(_item(OK, "Modrinth 接口", "可达"))
    except Exception as exc:
        out.append(_item(WARN, "Modrinth 接口", f"不可达：{exc}", "检查网络或代理"))
    return out


def check_memory(memory_mb: int) -> list[dict]:
    if memory_mb <= 0:
        return [_item(INFO, "内存分配", "自动")]
    if memory_mb < 2048:
        return [_item(WARN, "内存分配", f"{memory_mb} MB 偏低，1.18+ 版本易崩", "调到 4096 MB 或自动")]
    if memory_mb > 16384:
        return [_item(WARN, "内存分配", f"{memory_mb} MB 过高，GC 停顿会变长", "降到 8192 MB 左右")]
    return [_item(OK, "内存分配", f"{memory_mb} MB")]


def check_logs(log_path: Path | None) -> list[dict]:
    if not log_path or not Path(log_path).exists():
        return [_item(INFO, "崩溃日志", "未找到 crash-report")]
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [_item(WARN, "崩溃日志", f"读取失败：{exc}")]
    text = text[-20000:]
    for key, hint in (
        ("UnsupportedClassVersionError", "Java 版本过低，换更高版本 Java"),
        ("NoClassDefFoundError", "依赖库缺失，重新安装版本"),
        ("java.lang.OutOfMemoryError", "内存不足，提高内存分配"),
        ("ModResolutionException", "模组依赖冲突，检查模组版本"),
        ("InvalidCredentialsException", "登录态失效，重新登录账户"),
    ):
        if key in text:
            return [_item(BAD, "崩溃原因", f"命中 {key}", hint)]
    return [_item(OK, "崩溃日志", "未发现已知错误特征")]


def run(
    mc_dir: Path,
    version_id: str = "",
    version_data: dict | None = None,
    memory_mb: int = 0,
    mirror: str = "auto",
    log_path: Path | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> dict:
    on_progress = on_progress or (lambda *a: None)
    items: list[dict] = []
    steps = 6
    on_progress("检查磁盘与目录", 1, steps)
    items += check_disk(mc_dir)
    items += check_dir(mc_dir)
    on_progress("检查 Java 环境", 2, steps)
    items += check_java(version_data)
    if version_id:
        on_progress("检查版本文件", 3, steps)
        items += check_version_files(mc_dir, version_id)
    on_progress("检查网络接口", 4, steps)
    items += check_network(mirror)
    on_progress("检查运行配置", 5, steps)
    items += check_memory(memory_mb)
    items += check_logs(log_path)
    on_progress("诊断完成", steps, steps)

    bad = len([i for i in items if i["level"] == BAD])
    warn = len([i for i in items if i["level"] == WARN])
    summary = "环境正常，可以启动" if not bad and not warn else (
        f"发现 {bad} 项异常、{warn} 项注意" if bad else f"有 {warn} 项需要注意"
    )
    report = [f"# Sprout 自诊断报告", f"", f"- 结论：{summary}", f"- 游戏目录：{mc_dir}", f"- 版本：{version_id or '未选择'}", ""]
    for i in items:
        report.append(f"## [{i['label']}] {i['title']}")
        report.append(i["detail"])
        if i["action"]:
            report.append(f"建议：{i['action']}")
        report.append("")
    return {"summary": summary, "items": items, "bad": bad, "warn": warn, "report": "\n".join(report)}
