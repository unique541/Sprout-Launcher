"""启动参数构建：classpath、JVM 参数、游戏参数替换。"""
from __future__ import annotations

import os
from pathlib import Path

from . import meta


def library_entries(version_data: dict, features: dict[str, bool] | None = None) -> list[dict]:
    """过滤 rules 并按 name 去重。"""
    features = features or {}
    out: list[dict] = []
    seen: set[str] = set()
    for lib in version_data.get("libraries", []):
        name = lib.get("name") or ""
        if name in seen:
            continue
        if not meta.rules_allow(lib, features):
            continue
        seen.add(name)
        out.append(lib)
    return out


def _jar_chain(mc_dir: Path, version_id: str, version_data: dict, depth: int = 0) -> list[str]:
    """加载器版本没有自己的 jar，真正的客户端 jar 在 inheritsFrom 的父版本里。"""
    out: list[str] = []
    parent = version_data.get("inheritsFrom")
    if parent and depth < 4:
        pdir = mc_dir / "versions" / parent
        pjson = pdir / f"{parent}.json"
        pdata: dict = {}
        if pjson.exists():
            try:
                import json

                pdata = json.loads(pjson.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pdata = {}
        if pdata:
            out += _jar_chain(mc_dir, parent, pdata, depth + 1)
        pjar = pdir / f"{parent}.jar"
        if pjar.exists() and str(pjar) not in out:
            out.append(str(pjar))
    jar = mc_dir / "versions" / version_id / f"{version_id}.jar"
    if jar.exists() and str(jar) not in out:
        out.append(str(jar))
    return out


def build_classpath(mc_dir: Path, version_id: str, version_data: dict) -> list[str]:
    entries: list[str] = list(_jar_chain(mc_dir, version_id, version_data))
    for lib in library_entries(version_data):
        art = (lib.get("downloads") or {}).get("artifact")
        if art and art.get("path"):
            entries.append(str(mc_dir / "libraries" / art["path"]))
            continue
        if (lib.get("natives") or {}).get("windows"):
            continue  # 旧式 natives 不进 classpath
        path = meta.artifact_path(lib)
        if path:
            entries.append(str(mc_dir / "libraries" / path))
    return entries


def _sub(value: str, table: dict[str, str]) -> str:
    for k, v in table.items():
        value = value.replace("${" + k + "}", v)
    return value


def _expand(arg, table: dict[str, str], features: dict[str, bool]) -> list[str]:
    if isinstance(arg, str):
        return [_sub(arg, table)]
    if isinstance(arg, dict):
        if not meta.rules_allow(arg, features):
            return []
        val = arg.get("value", [])
        if isinstance(val, str):
            return [_sub(val, table)]
        return [_sub(v, table) for v in val]
    return []


def build_command(
    mc_dir: Path,
    version_id: str,
    version_data: dict,
    java_path: str,
    game_dir: Path,
    memory_mb: int = 4096,
    extra_jvm: str = "",
    username: str = "Player",
    uuid: str = "00000000000000000000000000000000",
    access_token: str = "0",
    user_type: str = "legacy",
    width: int = 0,
    height: int = 0,
    quick_play_singleplayer: str = "",
) -> list[str]:
    classpath = build_classpath(mc_dir, version_id, version_data)
    natives = mc_dir / "versions" / version_id / "natives"
    natives.mkdir(parents=True, exist_ok=True)
    game_dir.mkdir(parents=True, exist_ok=True)

    quick = (quick_play_singleplayer or "").strip()
    features = {
        "is_demo_user": False,
        "has_custom_resolution": bool(width and height),
        "has_quick_plays_support": bool(quick),
        "is_quick_play_singleplayer": bool(quick),
        "is_quick_play_multiplayer": False,
        "is_quick_play_realms": False,
    }

    table = {
        "auth_player_name": username,
        "version_name": version_data.get("id") or version_id,
        "game_directory": str(game_dir),
        "assets_root": str(mc_dir / "assets"),
        "game_assets": str(mc_dir / "assets" / "virtual" / "legacy"),
        "assets_index_name": (version_data.get("assetIndex") or {}).get("id", "legacy"),
        "auth_uuid": uuid,
        "auth_access_token": access_token,
        "auth_session": access_token,
        "user_type": user_type,
        "version_type": version_data.get("type", "release"),
        "natives_directory": str(natives),
        "launcher_name": "Sprout",
        "launcher_version": "0.3.2",
        "classpath": os.pathsep.join(classpath),
        "classpath_separator": os.pathsep,
        "library_directory": str(mc_dir / "libraries"),
        "resolution_width": str(width),
        "resolution_height": str(height),
        "clientid": "",
        "auth_xuid": "",
        "user_properties": "{}",
        "quickPlaySingleplayer": quick,
        # 1.20+ 的 arguments 里带 --quickPlayPath ${quickPlayPath}，
        # 不填就会把 ${quickPlayPath} 这串字面量原样丢给客户端，快速进入会失败
        "quickPlayPath": str(mc_dir / "logs" / "quickplay.log"),
        "quickPlayMultiplayer": "",
        "quickPlayRealms": "",
    }

    cmd: list[str] = [java_path, f"-Xmx{max(512, int(memory_mb))}M", f"-Djava.library.path={natives}"]

    # 依赖库统一路径（Forge 等会用到）
    cmd.append(f"-DlibraryDirectory={mc_dir / 'libraries'}")

    jvm_args = (version_data.get("arguments") or {}).get("jvm")
    has_classpath_flag = False
    if jvm_args:
        for a in jvm_args:
            expanded = _expand(a, table, features)
            if any(x in ("-cp", "-classpath") for x in expanded):
                has_classpath_flag = True
            cmd.extend(expanded)
    if not has_classpath_flag:
        cmd.extend(["-cp", os.pathsep.join(classpath)])

    if extra_jvm.strip():
        cmd.extend(extra_jvm.split())

    main_class = version_data.get("mainClass", "net.minecraft.client.main.Main")
    cmd.append(main_class)

    game_args = (version_data.get("arguments") or {}).get("game")
    if game_args:
        for a in game_args:
            cmd.extend(_expand(a, table, features))
    else:
        legacy = version_data.get("minecraftArguments", "")
        cmd.extend([_sub(tok, table) for tok in legacy.split() if tok])

    if quick and "--quickPlaySingleplayer" not in cmd:
        # 1.20 之前没有快速进入参数，硬塞会被客户端当成未知选项直接报错，
        # 只有版本元数据里确实声明了才补（部分自定义整合包把参数写在 arguments 外层）
        import json

        if "--quickPlaySingleplayer" in json.dumps(version_data.get("arguments") or {}):
            cmd.extend(["--quickPlaySingleplayer", quick])

    return cmd
