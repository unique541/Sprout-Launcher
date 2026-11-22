"""QML 与 Python 的桥梁：所有耗时操作走后台线程，结果通过信号回主线程。"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
import zipfile
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, Property, QProcess, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog

from .. import paths
from ..config import Config
from ..core import accounts as account_core
from ..core import accelerate
from ..core import diagnose as diag_core
from ..core import install as installer
from ..core import java as javacore
from ..core import launch as launcher
from ..core import loaders
from ..core import meta
from ..core import mod_zh
from ..core import mods as mod_core
from ..core import memtool
from ..core import net
from ..core import p2p
from ..core import saves as save_core
from ..core import skin as skin_core
from ..core import pack as pack_core
from ..core import updater
from ..core.instances import Instance, InstanceStore
from ..services.curseforge import CurseForgeClient
from ..services.modrinth import ModrinthClient, split_game_versions
from .models import DictListModel
from .theme import ThemeManager

VERSION_ROLES = ["id", "type", "releaseTime", "installed", "isLatest", "javaMajor"]
INSTANCE_ROLES = ["id", "name", "versionId", "loader", "playtime", "lastPlayed", "gameDir"]
SAVE_ROLES = [
    "name", "folder", "path", "gameDir", "source", "versionId", "instanceId",
    "versionName", "lastPlayed", "lastPlayedText", "sizeText", "iconUrl", "quick",
]
JAVA_ROLES = ["path", "major", "version", "arch", "vendor", "label", "source"]
SEARCH_ROLES = ["id", "title", "titleZh", "description", "iconUrl", "downloads", "author", "projectType", "installed"]
MOD_ROLES = ["file", "title", "titleZh", "size", "enabled", "hasUpdate", "projectId", "latestVersion", "source"]
DETAIL_ROLES = ["id", "versionNumber", "name", "loader", "gameVersions", "date", "downloads", "fileName", "size"]
MODDED_LOADERS = {"fabric", "forge", "neoforge", "quilt"}


def _norm_loader(value: str) -> str:
    """把 detect_loader 的 vanilla/unknown 等归一为空串，避免当作 Modrinth 分类过滤。"""
    text = (value or "").strip().lower()
    return text if text in MODDED_LOADERS else ""


class Bridge(QObject):
    stateChanged = Signal()
    versionsChanged = Signal()
    javasChanged = Signal()
    instancesChanged = Signal()
    savesChanged = Signal()
    toast = Signal(str, str)
    logLine = Signal(str)
    installFinished = Signal(str, bool)
    gameStateChanged = Signal()
    modsChanged = Signal()
    searchChanged = Signal()
    searchLoadingChanged = Signal()
    accountsChanged = Signal()
    diagnoseChanged = Signal()
    tunnelChanged = Signal()
    updateChanged = Signal()
    loaderVersionsReady = Signal(str, str, "QVariantList")
    deviceCode = Signal(str, str)
    loginStateChanged = Signal()
    installedChanged = Signal()
    tunnelBackendChanged = Signal()
    depChanged = Signal()
    modSourceChanged = Signal()
    speedChanged = Signal()
    skinChanged = Signal()
    skinBusyChanged = Signal()
    toolboxChanged = Signal()
    memChanged = Signal()
    accelReady = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._config = Config()
        self._theme = ThemeManager(self._config.get("theme") or "sprout")
        self._store = InstanceStore()
        self._accounts = account_core.AccountStore()
        self._manifest: meta.VersionManifest | None = None

        # 已安装列表缓存：installedChanged 触发时失效，避免首页反复扫盘
        self._installed_cache: list | None = None
        self.installedChanged.connect(self._drop_installed_cache)
        self._all_versions: list[dict] = []
        self._featured: dict = {}
        self._latest_release: str = ""
        self._runtimes: list[javacore.JavaRuntime] = []

        self._status = "准备就绪"
        self._progress = 0.0
        self._busy = False
        self._running = False
        self._runningVersion = ""
        self._searchText = ""
        self._typeFilter = "all"

        # 模组市场
        self._mod_query = ""
        self._mod_kind = "mod"
        self._mod_offset = 0
        self._mod_total = 0
        self._mod_loading = False
        self._mod_target = ""
        # 模组来源（modrinth / curseforge）
        self._mod_source = self._norm_source(self._config.get("mod_source"))
        self._cf_client: CurseForgeClient | None = None
        self._cf_installed: dict[str, dict] = {}
        # 下载速度（字节/秒）
        self._speed = 0.0
        self._speed_timer = QTimer(self)
        self._speed_timer.setInterval(500)
        self._speed_timer.timeout.connect(self._poll_speed)

        # 联机
        self._tunnel = p2p.Tunnel()
        self._tunnel_room = ""
        self._tunnel_log: list[str] = []
        self._tunnel_backend = "p2p"
        self._tunnel_port = p2p.room_default_port()
        self._lan_active = False
        # host = 我开房间；join = 加入别人的房间
        self._tunnel_role = "host"
        self._tunnel_join_ip = ""
        # 前置模组检查
        self._dep_open = False
        self._dep_rows: list = []
        self._dep_title = ""
        self._dep_message = ""
        self._dep_versions: list = []
        self._dep_pending: tuple | None = None

        # 诊断 / 更新 / 登录
        self._diag_items: list[dict] = []
        self._diag_summary = ""
        self._diag_report = ""
        self._diagnosing = False
        self._update: dict = {}
        self._update_stage = ""
        self._update_message = ""
        self._update_progress = 0.0
        self._update_path = ""
        self._login_busy = False
        # 皮肤上传 / 工具箱
        self._skin_busy = False
        self._mem: dict = {}
        self._mem_busy = False
        self._steam_probing = False
        accelerate.ACCEL.attach(self._config)
        self.accelReady.connect(self._on_accel_ready)

        self._versions_model = DictListModel(VERSION_ROLES, self)
        # 版本库专用：只列「未安装」的版本，用于下载新游戏
        self._library_model = DictListModel(VERSION_ROLES, self)
        self._instances_model = DictListModel(INSTANCE_ROLES, self)
        self._javas_model = DictListModel(JAVA_ROLES, self)
        self._search_model = DictListModel(SEARCH_ROLES, self)
        self._mods_model = DictListModel(MOD_ROLES, self)
        self._saves_model = DictListModel(SAVE_ROLES, self)
        self._saves_cache: dict[str, dict] = {}
        self._saves_scanned = False

        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._read_output)
        self._proc.finished.connect(self._on_game_finished)
        self._proc.errorOccurred.connect(self._on_game_error)
        self._game_started_at = 0.0
        self._stopping = False
        self._game_instance = ""
        # 进程守护：QProcess 的 finished 信号偶发丢失（游戏被外部强杀、
        # 由中间进程拉起导致句柄回收延迟等）会让状态卡在「游戏运行中」，
        # 这里定时核对进程存活情况做兜底复位
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(1500)
        self._watch_timer.timeout.connect(self._check_game_alive)
        self._watch_timer.start()

        self._sync_instances_model()
        self._refresh_mods_model()
        # 启动即扫本地，保证首页/启动选择器在联网失败时也能列出已安装游戏
        try:
            self.refreshLocal()
        except Exception:  # noqa: BLE001
            pass
        # 历史存档可能散落在 .minecraft/saves、实例目录、版本隔离目录，
        # 启动即扫一遍，用户不必手动点刷新也能看到以前玩过的世界
        try:
            self.refreshSaves()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ 属性
    @Property(QObject, constant=True)
    def theme(self) -> QObject:
        return self._theme

    @Property(QObject, constant=True)
    def versionsModel(self) -> QObject:
        return self._versions_model

    @Property(QObject, constant=True)
    def libraryModel(self) -> QObject:
        """版本库列表：只含尚未安装、可下载的版本。"""
        return self._library_model

    @Property(QObject, constant=True)
    def instancesModel(self) -> QObject:
        return self._instances_model

    @Property(QObject, constant=True)
    def savesModel(self) -> QObject:
        return self._saves_model

    @Property(int, notify=savesChanged)
    def savesCount(self) -> int:
        return self._saves_model.rowCount()

    @Property(QObject, constant=True)
    def javasModel(self) -> QObject:
        return self._javas_model

    @Property(QObject, constant=True)
    def searchModel(self) -> QObject:
        return self._search_model

    @Property(QObject, constant=True)
    def modsModel(self) -> QObject:
        return self._mods_model

    @Property(str, notify=stateChanged)
    def statusText(self) -> str:
        return self._status

    @Property(float, notify=stateChanged)
    def progress(self) -> float:
        return self._progress

    @Property(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(bool, notify=gameStateChanged)
    def running(self) -> bool:
        return self._running

    @Property(str, notify=gameStateChanged)
    def runningVersion(self) -> str:
        return self._runningVersion

    @Property(int, notify=stateChanged)
    def memoryMb(self) -> int:
        return int(self._config.get("memory_mb") or 4096)

    @Property(str, notify=stateChanged)
    def mcDir(self) -> str:
        return str(self._config.get("mc_dir") or paths.default_minecraft_dir())

    @Property(str, notify=stateChanged)
    def mirror(self) -> str:
        return str(self._config.get("mirror") or "auto")

    @Property(str, notify=stateChanged)
    def jvmArgs(self) -> str:
        return str(self._config.get("jvm_args") or "")

    @Property(str, notify=stateChanged)
    def msClientId(self) -> str:
        return str(self._config.get("ms_client_id") or account_core.DEFAULT_CLIENT_ID)

    @Property(str, notify=stateChanged)
    def updateRepo(self) -> str:
        # 设置里填了就用设置的，留空时回落到内置默认仓库，保证开箱即用
        return str(self._config.get("update_repo") or updater.DEFAULT_REPO)

    @Property(str, notify=stateChanged)
    def searchText(self) -> str:
        return self._searchText

    @Property(str, notify=versionsChanged)
    def typeFilter(self) -> str:
        return self._typeFilter

    @Property(int, notify=versionsChanged)
    def versionCount(self) -> int:
        return len(self._all_versions)

    @Property(int, notify=installedChanged)
    def installedCount(self) -> int:
        return len(self._local_versions())

    @Property("QVariantMap", notify=versionsChanged)
    def featured(self) -> dict:
        return self._featured

    @Property(str, notify=versionsChanged)
    def latestRelease(self) -> str:
        return self._latest_release

    @Property("QVariantList", notify=javasChanged)
    def javaList(self) -> list[dict]:
        return [r.to_dict() for r in self._runtimes]

    @Property(bool, notify=searchLoadingChanged)
    def searchLoading(self) -> bool:
        return self._mod_loading

    @Property(int, notify=searchChanged)
    def searchTotal(self) -> int:
        return self._mod_total

    @Property(str, notify=stateChanged)
    def modTarget(self) -> str:
        return self._mod_target

    # ------------------------------------------------------- 模组来源 / 下载
    @staticmethod
    def _norm_source(value) -> str:
        src = str(value or "").strip().lower()
        if src in ("curseforge", "cf", "curse"):
            return "curseforge"
        return "modrinth"

    @Property(str, notify=modSourceChanged)
    def modSource(self) -> str:
        return self._mod_source

    @Slot(str)
    def setModSource(self, source: str) -> None:
        src = self._norm_source(source)
        changed = src != self._mod_source
        self._mod_source = src
        if changed:
            self._config.set("mod_source", src)
            self._mod_offset = 0
            self._mod_total = 0
            self.searchChanged.emit()
            self.modSourceChanged.emit()
        if src == "curseforge" and not self.cfApiKey:
            self.toast.emit(
                "CurseForge 需要 API Key：请到 设置 → 模组来源 填写后即可搜索与下载",
                "warn",
            )
        if changed and self._mod_query is not None:
            self._mod_loading = False
            self._bg(self._do_search, True)

    @Property(str, notify=modSourceChanged)
    def cfApiKey(self) -> str:
        return str(self._config.get("cf_api_key") or "")

    @Property(bool, notify=modSourceChanged)
    def cfReady(self) -> bool:
        if bool(self._config.get("curseforge_mirror", True)):
            return True     # 国内镜像不需要 API Key
        return bool(self.cfApiKey.strip())

    @Slot(str)
    def setCfApiKey(self, value: str) -> None:
        key = (value or "").strip()
        self._config.set("cf_api_key", key)
        if self._cf_client is not None:
            try:
                self._cf_client.close()
            except Exception:  # noqa: BLE001
                pass
            self._cf_client = None
        self.modSourceChanged.emit()
        if key:
            self.toast.emit("CurseForge API Key 已保存", "success")
        else:
            self.toast.emit("已清空 CurseForge API Key", "info")

    @Property(int, notify=stateChanged)
    def concurrency(self) -> int:
        return net.resolve_concurrency(self._config.get("concurrency"))

    @Slot(int)
    def setConcurrency(self, value: int) -> None:
        num = net.resolve_concurrency(value)
        self._config.set("concurrency", num)
        self.stateChanged.emit()
        self.toast.emit(f"下载线程数已设为 {num}", "success")

    @Property(str, notify=speedChanged)
    def downloadSpeed(self) -> str:
        return net.format_speed(self._speed)

    @Property(int, notify=speedChanged)
    def downloadSpeedValue(self) -> int:
        return int(self._speed)

    def _poll_speed(self) -> None:
        speed = float(net.current_speed() or 0.0)
        if abs(speed - self._speed) < 512 and speed > 0:
            return
        if speed <= 0 and self._speed <= 0:
            return
        self._speed = speed
        self.speedChanged.emit()

    def _cf(self) -> CurseForgeClient | None:
        """取 CurseForge 客户端：镜像模式无需 API Key，官方模式必须有 Key。"""
        key = self.cfApiKey.strip()
        mirror = bool(self._config.get("curseforge_mirror", True))
        if not key and not mirror:
            return None
        if self._cf_client is None:
            self._cf_client = CurseForgeClient(key, mirror=mirror)
        return self._cf_client

    @Property("QVariantList", notify=accountsChanged)
    def accounts(self) -> list[dict]:
        out = []
        for a in self._accounts.items:
            out.append({
                "id": a.id, "name": a.name, "uuid": a.uuid, "type": a.type,
                "active": a.id == self._accounts.active_id,
                "expired": a.is_expired,
                "skin": a.skin,
                "label": "微软账户" if a.type == "microsoft" else "离线账户",
            })
        return out

    @Property("QVariantMap", notify=accountsChanged)
    def activeAccount(self) -> dict:
        a = self._accounts.active()
        return {"id": a.id, "name": a.name, "uuid": a.uuid, "type": a.type,
                "label": "微软账户" if a.type == "microsoft" else "离线账户"}

    @Property(bool, notify=loginStateChanged)
    def loginBusy(self) -> bool:
        return self._login_busy

    @Property(bool, notify=tunnelChanged)
    def tunnelRunning(self) -> bool:
        return self._tunnel.running or self._lan_active

    @Property(str, notify=tunnelChanged)
    def tunnelIp(self) -> str:
        if self._tunnel.running:
            return self._tunnel.ip or p2p.local_ipv4()
        if self._lan_active:
            # 加入房间时展示的是房主地址，房主模式展示本机地址
            if self._tunnel_role == "join" and self._tunnel_join_ip:
                return self._tunnel_join_ip
            return p2p.local_ipv4()
        return ""

    @Property(int, notify=tunnelChanged)
    def tunnelPort(self) -> int:
        return self._tunnel_port

    @Property(str, notify=tunnelChanged)
    def tunnelAddress(self) -> str:
        ip = self.tunnelIp
        return f"{ip}:{self._tunnel_port}" if ip else ""

    @Property(str, notify=tunnelChanged)
    def tunnelBackend(self) -> str:
        return self._tunnel_backend

    @Property(str, notify=tunnelBackendChanged)
    def tunnelBackendLabel(self) -> str:
        return p2p.backend_label(self._tunnel_backend)

    @Property(bool, notify=tunnelBackendChanged)
    def terracottaReady(self) -> bool:
        return p2p.terracotta_available()

    @Property("QVariantList", notify=tunnelBackendChanged)
    def tunnelMethods(self) -> list:
        ready = p2p.terracotta_available()
        return [
            {"id": "p2p", "label": "P2P 联机",
             "desc": "自带内网穿透内核，点对点组网，无需公网 IP，房间名+可选密钥"},
            {"id": "terracotta", "label": "陶瓦联机",
             "desc": ("已检测到本机陶瓦内核，填写陶瓦房间名与密钥即可互通" if ready
                      else "与陶瓦联机客户端同协议，房间名+密钥一致即可互通")},
            {"id": "lan", "label": "局域网直连",
             "desc": "同一局域网直接连接，填写游戏内「对局域网开放」给出的端口"},
        ]

    @Property(str, notify=tunnelChanged)
    def tunnelRoom(self) -> str:
        return self._tunnel_room

    @Property(str, notify=tunnelChanged)
    def tunnelRole(self) -> str:
        return self._tunnel_role

    @Property(str, notify=tunnelChanged)
    def tunnelRoleLabel(self) -> str:
        return "房主" if self._tunnel_role == "host" else "成员"

    @Property(str, notify=tunnelChanged)
    def tunnelLog(self) -> str:
        return "\n".join(self._tunnel_log[-40:])

    @Property("QVariantList", notify=diagnoseChanged)
    def diagnoseItems(self) -> list[dict]:
        return self._diag_items

    @Property(str, notify=diagnoseChanged)
    def diagnoseSummary(self) -> str:
        return self._diag_summary

    @Property(bool, notify=diagnoseChanged)
    def diagnosing(self) -> bool:
        return self._diagnosing

    @Property(str, notify=diagnoseChanged)
    def diagnoseReportPath(self) -> str:
        return self._diag_report

    @Property("QVariantMap", notify=updateChanged)
    def updateInfo(self) -> dict:
        return self._update

    @Property(str, notify=updateChanged)
    def updateStage(self) -> str:
        """空 = 无提示；available / downloading / ready / installing / error。"""
        return self._update_stage

    @Property(bool, notify=updateChanged)
    def updatePromptVisible(self) -> bool:
        return bool(self._update_stage)

    @Property(float, notify=updateChanged)
    def updateProgress(self) -> float:
        return float(self._update_progress)

    @Property(str, notify=updateChanged)
    def updateMessage(self) -> str:
        return self._update_message

    @Property(str, notify=updateChanged)
    def updateNotesText(self) -> str:
        """更新说明正文（给 QML 做属性绑定；函数调用在 QML 里不会随数据变化刷新）。"""
        notes = str(self._update.get("notes") or "").strip()
        return notes or "该版本未填写更新说明。"

    @Property(str, notify=stateChanged)
    def appVersion(self) -> str:
        return updater.APP_VERSION

    # ------------------------------------------------------------- 内部工具
    def _set_state(self, status: str | None = None, progress: float | None = None, busy: bool | None = None) -> None:
        if status is not None:
            self._status = status
        if progress is not None:
            self._progress = float(max(0.0, min(1.0, progress)))
        if busy is not None:
            self._busy = busy
            if busy:
                self._speed_timer.start()
            else:
                self._speed_timer.stop()
                if self._speed > 0:
                    self._speed = 0.0
                    self.speedChanged.emit()
        self.stateChanged.emit()

    def _bg(self, fn, *args) -> None:
        def runner() -> None:
            try:
                fn(*args)
            except Exception as exc:  # noqa: BLE001
                self.toast.emit(f"{exc}", "error")
                self._set_state(status="出错了", progress=0.0, busy=False)
        threading.Thread(target=runner, daemon=True).start()

    def _client(self) -> ModrinthClient:
        return ModrinthClient()

    def _manifest_or_fetch(self) -> meta.VersionManifest:
        if self._manifest is None or not self._manifest.versions:
            self._manifest = meta.VersionManifest(self.mirror).fetch()
        return self._manifest

    def _mc_roots(self) -> list[Path]:
        """所有可能的游戏根目录：配置目录 + 用户手动添加 + 自动探测到的候选目录。"""
        roots: list[Path] = []
        cfg = Path(self.mcDir)
        if cfg:
            roots.append(cfg)
        for raw in self.extraDirs:
            p = Path(raw)
            if p not in roots:
                roots.append(p)
        try:
            for cand in paths.minecraft_candidates():
                if cand not in roots:
                    roots.append(cand)
        except Exception:  # noqa: BLE001
            pass
        return roots

    def _local_versions(self) -> dict[str, Path]:
        """本地真实存在的版本：版本 id -> 版本目录。

        直接扫文件系统，不依赖远程版本清单，因此断网、清单拉取失败、
        整合包自定义版本名（如「乌托邦探险之旅3.5.2」）都不会漏掉。
        """
        out: dict[str, Path] = {}
        for root in self._mc_roots():
            vroot = root / "versions"
            if not vroot.is_dir():
                continue
            try:
                entries = list(vroot.iterdir())
            except OSError:
                continue
            for d in entries:
                try:
                    if not d.is_dir():
                        continue
                    vid = d.name
                    if vid.startswith("_") or vid in out:
                        continue
                    if (d / f"{vid}.json").exists():
                        out[vid] = d
                except OSError:
                    continue
        return out

    def _installed_ids(self) -> set[str]:
        return set(self._local_versions())

    def _mc_root_for(self, version_id: str) -> Path:
        """版本所在的游戏根目录（支持多份 .minecraft 共存）。"""
        vdir = self._local_versions().get(version_id)
        if vdir is not None:
            return vdir.parent.parent
        return Path(self.mcDir)

    def _game_dir_for(self, version_id: str, inst=None) -> str:
        """游戏的运行目录：优先实例记录目录，其次真实版本目录，最后游戏根目录。"""
        if inst is not None and getattr(inst, "game_dir", ""):
            return str(inst.game_dir)
        vdir = self._local_versions().get(version_id)
        if vdir is not None:
            return str(vdir)
        return str(Path(self.mcDir) / "versions" / version_id)

    def _has_worlds(self, game_dir) -> bool:
        """目录下的 saves 里是否真的有世界（空文件夹不算）。"""
        try:
            saves = Path(game_dir) / "saves"
            if not saves.is_dir():
                return False
            return any(p.is_dir() for p in saves.iterdir())
        except OSError:
            return False

    def _default_game_dir(self, mc: Path, version_id: str) -> Path:
        """新建实例用哪个游戏目录。

        以前用官方启动器玩过的版本会把世界留在 versions/<id>/saves（版本隔离），
        如果那里有世界而新建的 instances 目录还是空的，就沿用旧目录，
        否则游戏里「单人游戏」看不到以前玩过的存档。
        """
        isolated = mc / "versions" / version_id
        own = mc / "instances" / version_id
        if self._has_worlds(isolated) and not self._has_worlds(own):
            isolated.mkdir(parents=True, exist_ok=True)
            return isolated
        own.mkdir(parents=True, exist_ok=True)
        return own

    def _effective_game_dir(self, inst) -> Path:
        """实例实际该用的游戏目录，带旧存档自愈。

        实例目录里没有任何世界、而同名版本隔离目录里有世界时，本次启动改用隔离目录，
        这样老存档能在游戏内直接看到（不改用户已保存的实例配置）。
        """
        own = Path(inst.game_dir) if getattr(inst, "game_dir", "") else Path(self.mcDir) / "instances" / inst.version_id
        if self._has_worlds(own):
            return own
        isolated = self._mc_root_for(inst.version_id) / "versions" / inst.version_id
        if isolated != own and self._has_worlds(isolated):
            return isolated
        return own

    def _completion_gaps(self, version_id: str, root: Path | None = None) -> list[str]:
        """检查版本文件是否齐全。缺文件时游戏启动后会自己重下，必须先补齐。"""
        mc = Path(root) if root is not None else self._mc_root_for(version_id)
        vdir = mc / "versions" / version_id
        vjson = vdir / f"{version_id}.json"
        if not vjson.exists():
            return ["版本 json"]
        try:
            data = json.loads(vjson.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ["版本 json"]
        gaps: list[str] = []

        parent = data.get("inheritedFrom") or ""
        client = (data.get("downloads") or {}).get("client") or {}
        if client.get("url") and not parent and not (vdir / f"{version_id}.jar").exists():
            gaps.append("客户端 jar")

        index = data.get("assetIndex") or {}
        index_id = index.get("id") or ""
        index_file = mc / "assets" / "indexes" / f"{index_id}.json"
        if index_id and not index_file.exists():
            gaps.append("资源索引")

        miss_lib = 0
        # 只统计当前系统真正需要加载的库，macOS/Linux 专属库在 Windows 上永远不存在
        try:
            libs = launcher.library_entries(data)
        except Exception:  # noqa: BLE001
            libs = data.get("libraries") or []
        for lib in libs:
            art = (lib.get("downloads") or {}).get("artifact") or {}
            path = art.get("path") or ""
            if path and not (mc / "libraries" / path).exists():
                miss_lib += 1
        if miss_lib:
            gaps.append(f"运行库（{miss_lib} 个缺失）")
        return gaps

    def _apply_filter(self) -> None:
        text = self._searchText.lower().strip()
        tf = self._typeFilter
        rows = []
        for v in self._all_versions:
            if tf != "all" and v["type"] != tf:
                continue
            if text and text not in v["id"].lower():
                continue
            rows.append(dict(v))
        self._versions_model.set_items(rows)
        # 版本库只用于下载新版本：已安装的版本不再出现在这里
        self._library_model.set_items([r for r in rows if not r.get("installed")])
        self.versionsChanged.emit()

    def _sync_instances_model(self) -> None:
        rows = []
        for i in self._store.items:
            rows.append({
                "id": i.id, "name": i.name, "versionId": i.version_id, "loader": i.loader,
                "playtime": i.playtime, "lastPlayed": i.last_played, "gameDir": i.game_dir,
            })
        self._instances_model.set_items(rows)
        self.instancesChanged.emit()

    # ------------------------------------------------------------- 存档世界
    @Slot()
    def refreshSaves(self) -> None:
        """重扫全部候选目录的存档世界。"""
        self._bg(self._do_scan_saves)

    def _save_version_candidates(self, row: dict) -> str:
        """给存档匹配本地版本：优先目录里带的版本 id，其次 level.dat 的版本名。"""
        if row.get("versionId"):
            return str(row["versionId"])
        installed = self._local_versions()
        name = str(row.get("versionName") or "").strip()
        if name and name in installed:
            return name
        return ""

    def _version_supports_quick_play(self, version_id: str, depth: int = 0) -> bool:
        """1.20 起才有 --quickPlaySingleplayer；加载器版本要顺着 inheritsFrom 往上找。"""
        if not version_id or depth > 4:
            return False
        mc = self._mc_root_for(version_id)
        vjson = mc / "versions" / version_id / f"{version_id}.json"
        try:
            data = json.loads(vjson.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if "--quickPlaySingleplayer" in json.dumps(data.get("arguments") or {}):
            return True
        parent = data.get("inheritsFrom") or ""
        return self._version_supports_quick_play(parent, depth + 1) if parent else False

    def _do_scan_saves(self) -> None:
        extra = [
            (inst.game_dir, f"实例 {inst.name}", inst.version_id, inst.id)
            for inst in self._store.items
            if inst.game_dir
        ]
        try:
            found = save_core.scan_saves(Path(self.mcDir), extra)
        except Exception as exc:  # noqa: BLE001
            self.logLine.emit(f"[Sprout] 存档扫描失败：{exc}")
            found = []

        rows: list[dict] = []
        cache: dict[str, dict] = {}
        quick_support: dict[str, bool] = {}
        for row in found:
            version_id = self._save_version_candidates(row)
            if version_id:
                if version_id not in quick_support:
                    quick_support[version_id] = self._version_supports_quick_play(version_id)
                quick = quick_support[version_id]
            else:
                quick = False
            item = {
                "name": row["name"],
                "folder": row["folder"],
                "path": row["path"],
                "gameDir": row["gameDir"],
                "source": row["source"],
                "versionId": version_id,
                "instanceId": row.get("instanceId") or "",
                "versionName": row.get("versionName") or "",
                "lastPlayed": row.get("lastPlayed") or 0.0,
                "lastPlayedText": row.get("lastPlayedText") or "未知",
                "sizeText": row.get("sizeText") or "",
                "iconUrl": QUrl.fromLocalFile(row["iconPath"]).toString() if row.get("iconPath") else "",
                "quick": quick,
            }
            rows.append(item)
            cache[item["path"]] = item

        self._saves_cache = cache
        self._saves_scanned = True
        self._saves_model.set_items(rows)
        self.savesChanged.emit()
        self.logLine.emit(f"[Sprout] 扫描到 {len(rows)} 个存档世界")

    @Slot(str)
    def openSaveFolder(self, save_path: str) -> None:
        target = Path(save_path or "")
        if not target.is_dir():
            self.toast.emit("存档目录不存在，可能已被移动或删除", "warn")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    @Slot(str)
    def launchSave(self, save_path: str) -> None:
        """直接进入指定存档世界（版本支持快速进入时）。"""
        if self._running:
            self.toast.emit("游戏已在运行中", "warn")
            return
        if self._busy:
            self.toast.emit("请等待当前任务完成", "warn")
            return
        row = self._saves_cache.get(save_path or "")
        if row is None:
            self.toast.emit("存档信息已过期，请点「重新扫描」后再试", "warn")
            return
        version_id = row.get("versionId") or ""
        if not version_id:
            world_ver = row.get("versionName") or "未知"
            self.toast.emit(
                f"没找到与该存档匹配的本地版本（世界版本 {world_ver}），先在版本库里装好对应版本", "warn"
            )
            return
        quick = row.get("folder") if row.get("quick") else ""
        if not quick:
            self.toast.emit("该版本不支持直接进入世界，已启动游戏，请在「单人游戏」里选择该存档", "info")
        self._start_game(
            version_id=version_id,
            instance_id=row.get("instanceId") or "",
            game_override=row.get("gameDir") or "",
            quick_play=quick,
        )

    def _version_loader(self, version_id: str) -> str:
        inst = self._store.for_version(version_id)
        if inst and inst.loader:
            return _norm_loader(inst.loader)
        return _norm_loader(loaders.detect_loader(version_id)[0])

    def _version_game(self, version_id: str) -> str:
        return loaders.detect_loader(version_id)[1]

    def _target_game_dir(self) -> Path:
        """模组安装目标：优先选中的实例，否则按版本隔离目录。"""
        if self._mod_target:
            inst = self._store.get(self._mod_target)
            if inst and inst.game_dir:
                return Path(inst.game_dir)
        if self._featured.get("id"):
            vid = self._featured["id"]
            inst = self._store.for_version(vid)
            if inst and inst.game_dir:
                return Path(inst.game_dir)
            return Path(self.mcDir) / "instances" / vid
        return Path(self.mcDir)

    # ------------------------------------------------------------- 版本相关
    @Slot()
    def refreshVersions(self) -> None:
        if self._busy:
            return
        self._set_state(status="正在获取版本清单…", progress=0.1, busy=True)
        self._bg(self._do_refresh)

    def _do_refresh(self) -> None:
        manifest = self._manifest_or_fetch()
        installed = self._installed_ids()
        items = []
        latest = manifest.latest or {}
        for v in manifest.versions:
            vid = v.get("id", "")
            items.append({
                "id": vid,
                "type": v.get("type", "release"),
                "releaseTime": (v.get("releaseTime") or "")[:10],
                "installed": vid in installed,
                "isLatest": vid in (latest.get("release"), latest.get("snapshot")),
                "javaMajor": javacore.fallback_major(vid),
            })
        # 本地安装的整合包/自定义命名版本不在官方清单里，必须补进版本列表，否则版本库看不到
        known = {i["id"] for i in items}
        for vid in sorted(installed - known):
            items.insert(0, {
                "id": vid,
                "type": "local",
                "releaseTime": "",
                "installed": True,
                "isLatest": False,
                "javaMajor": javacore.fallback_major(vid),
            })
        self._all_versions = items
        self._latest_release = str(latest.get("release") or "")

        pick = next((v for v in items if v["installed"]), None)
        if pick is None:
            pick = next((v for v in items if v["isLatest"]), None)
        if pick is None and items:
            pick = items[0]
        self._featured = dict(pick or {})

        self._set_state(status=f"共 {len(items)} 个版本", progress=1.0, busy=False)
        self.installedChanged.emit()
        self.versionsChanged.emit()
        self._apply_filter()

    @Slot(str)
    def setSearchText(self, text: str) -> None:
        self._searchText = text
        self._apply_filter()

    @Slot(str)
    def setTypeFilter(self, kind: str) -> None:
        self._typeFilter = kind
        self._apply_filter()

    @Slot(str)
    def installVersion(self, version_id: str) -> None:
        if self._busy:
            self.toast.emit("已有任务在进行中", "warn")
            return
        if not version_id:
            return
        self._set_state(status=f"准备安装 {version_id}", progress=0.02, busy=True)
        self._bg(self._do_install, version_id)

    def _do_install(self, version_id: str) -> None:
        manifest = self._manifest_or_fetch()
        mc = Path(self.mcDir)
        mc.mkdir(parents=True, exist_ok=True)

        def on_progress(stage: str, done: int, total: int) -> None:
            ratio = (done / total) if total else 0.0
            self._set_state(status=f"{stage}  {done}/{total}", progress=ratio, busy=True)

        result = installer.install(
            mc, version_id, manifest, mirror=self.mirror, concurrency=16, on_progress=on_progress,
        )
        failed = result.get("failed_count", 0)
        self._set_state(
            status=f"{version_id} 安装完成" if not failed else f"{version_id} 有 {failed} 个文件未完成",
            progress=1.0, busy=False,
        )
        self.toast.emit(
            f"{version_id} 安装完成" if not failed else f"{version_id}：{failed} 个文件下载失败",
            "success" if not failed else "warn",
        )
        self.installFinished.emit(version_id, not failed)
        threading.Thread(target=self._do_refresh, daemon=True).start()

    @Slot(str, str)
    def fetchLoaderVersions(self, loader: str, game_version: str) -> None:
        def work() -> None:
            try:
                versions = loaders.list_versions(loader, game_version)
            except Exception as exc:  # noqa: BLE001
                self.toast.emit(f"查询 {loader} 版本失败：{exc}", "warn")
                versions = []
            self.loaderVersionsReady.emit(loader, game_version, versions)

        threading.Thread(target=work, daemon=True).start()

    @Slot(str, str, str)
    def installWithLoader(self, game_version: str, loader: str, loader_version: str) -> None:
        if self._busy:
            self.toast.emit("已有任务在进行中", "warn")
            return
        self._set_state(
            status=f"安装 {game_version} · {loaders.LOADER_LABEL.get(loader, loader)}",
            progress=0.02, busy=True,
        )
        self._bg(self._do_install_loader, game_version, loader, loader_version)

    def _do_install_loader(self, game_version: str, loader: str, loader_version: str) -> None:
        manifest = self._manifest_or_fetch()
        mc = Path(self.mcDir)
        mc.mkdir(parents=True, exist_ok=True)

        def on_progress(stage: str, done: int, total: int) -> None:
            self._set_state(status=f"{stage}  {done}/{total}" if total > 1 else stage,
                            progress=(done / total) if total else 0.3, busy=True)

        version_id = loaders.install_loader(
            mc, game_version, loader, manifest, loader_version, self.mirror, on_progress
        )
        pending = self._pending_loader
        reused = False
        if pending:
            old = self._store.get(pending[0])
            if old is not None:
                # 为已有实例补装加载器：直接并回原实例，不额外新建实例
                old.version_id = version_id
                old.loader = loader
                self._store.save()
                reused = True
                self._mod_target = old.id
        if not reused:
            inst = self._store.for_version(version_id)
            if inst is None:
                game_dir = self._default_game_dir(mc, version_id)
                game_dir.mkdir(parents=True, exist_ok=True)
                self._store.add(Instance(
                    id=version_id, name=version_id, version_id=version_id,
                    loader=loader, game_dir=str(game_dir),
                ))
        self.toast.emit(f"{version_id} 安装完成", "success")
        self._set_state(status=f"{version_id} 就绪", progress=1.0, busy=False)
        self._sync_instances_model()
        self._finish_pending_loader(version_id, loader)
        threading.Thread(target=self._do_refresh, daemon=True).start()

    @Slot(str, result=bool)
    def isInstalled(self, version_id: str) -> bool:
        return version_id in self._installed_ids()

    @Slot(str, result=bool)
    def versionReady(self, version_id: str) -> bool:
        """已安装且资源完整，可直接启动。"""
        return version_id in self._installed_ids() and not self._completion_gaps(version_id)

    # ------------------------------------------------------------- Java 相关
    @Slot()
    def detectJava(self) -> None:
        self._bg(self._do_detect_java)

    def _do_detect_java(self) -> None:
        self._runtimes = javacore.discover()
        rows = []
        for r in self._runtimes:
            rows.append({
                "path": r.path, "major": r.major, "version": r.version,
                "arch": r.arch, "vendor": r.vendor, "label": r.label, "source": r.source,
            })
        self._javas_model.set_items(rows)
        self.javasChanged.emit()

    @Slot(int)
    def downloadJava(self, major: int) -> None:
        if self._busy:
            self.toast.emit("已有任务在进行中", "warn")
            return
        self._set_state(status=f"准备获取 Java {major}", progress=0.02, busy=True)
        self._bg(self._do_download_java, major)

    def _do_download_java(self, major: int) -> None:
        def on_progress(stage: str, done: int, total: int) -> None:
            self._set_state(status=f"{stage}  {done // 1048576}MB / {max(total, 1) // 1048576}MB",
                            progress=(done / total) if total else 0.0, busy=True)

        rt = javacore.download_runtime(major, on_progress)
        if rt:
            self.toast.emit(f"Java {rt.major} 已就绪", "success")
        else:
            self.toast.emit("Java 下载失败，请检查网络", "error")
        self._do_detect_java()
        self._set_state(status="Java 准备完成" if rt else "Java 获取失败", progress=1.0, busy=False)

    def _ensure_runtime(self, major: int) -> "javacore.JavaRuntime | None":
        """确保本机有指定大版本的 Java：先重新探测，缺了就下载并解压。"""
        self._runtimes = javacore.discover()
        rt = javacore.pick(self._runtimes, major)
        if rt is not None:
            return rt

        def on_progress(stage: str, done: int, total: int) -> None:
            ratio = (done / total) if total else 0.0
            self._set_state(
                status=f"{stage}  {done // 1048576}MB / {max(total, 1) // 1048576}MB",
                progress=0.3 + 0.3 * ratio, busy=True,
            )

        self._set_state(status=f"正在获取 Java {major}…", progress=0.3, busy=True)
        try:
            rt = javacore.download_runtime(major, on_progress)
        except Exception as exc:  # noqa: BLE001
            self.logLine.emit(f"[Sprout] 获取 Java {major} 失败：{exc}")
            rt = None
        if rt is None:
            self.logLine.emit(f"[Sprout] Java {major} 自动获取失败")
            return None
        self._runtimes = javacore.discover()
        self._do_detect_java()
        self.logLine.emit(f"[Sprout] Java {rt.major} 已就绪：{rt.path}")
        return javacore.pick(self._runtimes, major) or rt

    # ------------------------------------------------------------- 启动游戏
    @Slot(str)
    def launchVersion(self, version_id: str) -> None:
        self._start_game(version_id=version_id)

    @Slot(str)
    def launchInstance(self, instance_id: str) -> None:
        self._start_game(instance_id=instance_id)

    def _start_game(
        self,
        version_id: str = "",
        instance_id: str = "",
        game_override: str = "",
        quick_play: str = "",
    ) -> None:
        if self._running:
            self.toast.emit("游戏已在运行中", "warn")
            return
        if self._busy:
            self.toast.emit("请等待当前任务完成", "warn")
            return
        if not version_id and not instance_id:
            self.toast.emit("请先选择一个版本", "warn")
            return
        self._bg(self._do_launch, version_id, instance_id, game_override, quick_play)

    def _do_launch(
        self,
        version_id: str,
        instance_id: str = "",
        game_override: str = "",
        quick_play: str = "",
    ) -> None:
        inst = self._store.get(instance_id) if instance_id else None
        if inst:
            version_id = inst.version_id
        if game_override:
            # 从「存档」页进入时运行目录以存档所在目录为准：
            # 放在 .minecraft 根下的历史存档必须用根目录启动，否则游戏找不到世界
            override_dir = Path(game_override)
            matched = next(
                (
                    i for i in self._store.items
                    if i.game_dir and Path(i.game_dir) == override_dir and i.version_id == version_id
                ),
                None,
            )
            if matched is not None:
                inst = matched
            else:
                # 临时实例，不写进实例列表，避免每点一次存档就多一条记录
                inst = Instance(
                    id=f"quick-{version_id}",
                    name=version_id,
                    version_id=version_id,
                    loader=loaders.detect_loader(version_id)[0],
                    game_dir=str(override_dir),
                )
        if not version_id:
            self.toast.emit("实例缺少版本信息", "error")
            return
        # 版本可能装在别处的 .minecraft，按它实际所在目录启动
        mc = self._mc_root_for(version_id)

        if version_id not in self._installed_ids():
            self._set_state(status=f"{version_id} 尚未安装，开始安装…", progress=0.02, busy=True)
            self._do_install(version_id)
            if version_id not in self._installed_ids():
                self.toast.emit("安装未完成，无法启动", "error")
                return
        else:
            # 已安装版本点启动就直接启动，绝不自动下载：
            # 缺游戏本体 jar 时只提示并中止，补全交给版本库里显式点的「重装」；
            # 资源索引/运行库缺口交给游戏自己处理。
            gaps = self._completion_gaps(version_id, mc)
            if "客户端 jar" in gaps:
                self.toast.emit(
                    f"{version_id} 缺少游戏本体 jar，请在该版本卡片点「重装」补全后再启动", "warn"
                )
                self._set_state(status=f"{version_id} 缺少游戏本体 jar", progress=0.0, busy=False)
                return
            if gaps:
                self.logLine.emit(f"[Sprout] {version_id} 缺少 {', '.join(gaps)}，直接尝试启动")

        self._set_state(status="正在解析版本…", progress=0.3, busy=True)
        manifest = self._manifest_or_fetch()
        data = meta.load_version(mc, version_id, manifest)
        if not data:
            self.toast.emit("版本元数据缺失", "error")
            self._set_state(status="解析失败", progress=0.0, busy=False)
            return

        want = javacore.required_major(data)
        if not self._runtimes:
            self._runtimes = javacore.discover()
        rt = javacore.pick(self._runtimes, want)
        if rt is None:
            # 本机没有该版本要求的 Java 时，先自动补齐运行时再启动。
            # 用低版本 Java 硬启新版客户端会在加载阶段直接崩溃（退出码 1），
            # 用户看到的现象就是「点了启动游戏没起来」，所以这里不再直接降级。
            self.logLine.emit(f"[Sprout] 本机缺少 Java {want}，开始自动获取运行时")
            rt = self._ensure_runtime(want)
        if rt is None:
            # 运行时获取失败才退一步：用本机最大 Java 强启，并明确告知风险
            rt = max(self._runtimes, key=lambda r: r.major) if self._runtimes else None
            if rt is not None:
                self.logLine.emit(
                    f"[Sprout] Java {want} 获取失败，暂用本机 Java {rt.major} 强启（可能无法进入游戏）"
                )
                self.toast.emit(
                    f"该版本需要 Java {want}，自动获取失败，已用本机 Java {rt.major} 尝试启动；"
                    f"若游戏打不开，请在设置页手动获取 Java {want}", "warn")
        if rt is None:
            self._set_state(status="本机未检测到任何 Java 运行时", progress=0.0, busy=False)
            self.toast.emit("本机没有可用的 Java 运行时，请先在设置页获取一个", "error")
            return

        if inst is None:
            inst = self._store.for_version(version_id)
        if inst is None:
            game_dir = self._default_game_dir(mc, version_id)
            game_dir.mkdir(parents=True, exist_ok=True)
            inst = Instance(
                id=version_id, name=version_id, version_id=version_id,
                loader=loaders.detect_loader(version_id)[0], game_dir=str(game_dir),
            )
            self._store.add(inst)
            self._sync_instances_model()

        account = self._accounts.active()
        token = account.access_token or "0"
        if account.type == "microsoft" and account.is_expired:
            try:
                account = account_core.refresh_account(account, self.msClientId)
                token = account.access_token
                self.accountsChanged.emit()
            except Exception as exc:  # noqa: BLE001
                self.logLine.emit(f"[Sprout] 登录态续期失败：{exc}")

        self._set_state(status="正在构建启动参数…", progress=0.6, busy=True)
        run_dir = self._effective_game_dir(inst)
        if run_dir != Path(inst.game_dir):
            prev = inst.game_dir
            inst.game_dir = str(run_dir)
            self._store.save()
            self._sync_instances_model()
            self.logLine.emit(f"[Sprout] 沿用旧版本目录：{run_dir}")
            self.logLine.emit(f"[Sprout] 原实例目录（无存档）：{prev}")
        cmd = launcher.build_command(
            mc, version_id, data, rt.path, run_dir,
            memory_mb=self.memoryMb,
            extra_jvm=str(self._config.get("jvm_args") or ""),
            username=account.name,
            uuid=account.uuid,
            access_token=token,
            user_type="msa" if account.type == "microsoft" else "legacy",
            quick_play_singleplayer=quick_play,
        )

        self._proc.setProgram(cmd[0])
        self._proc.setArguments(cmd[1:])
        self._proc.setWorkingDirectory(str(run_dir))
        self._game_started_at = time.time()
        self._game_instance = inst.id
        self._proc.start()
        started = self._proc.waitForStarted(15000)
        if not started:
            self.toast.emit("启动失败：无法创建游戏进程", "error")
            self._set_state(status="启动失败", progress=0.0, busy=False)
            return

        self._running = True
        self._runningVersion = version_id
        self._set_state(status=f"Sprout 已启动 {version_id}", progress=1.0, busy=False)
        self.gameStateChanged.emit()
        self.logLine.emit(f"[Sprout] Java: {rt.path}")
        self.logLine.emit(f"[Sprout] 账户: {account.name}（{account.type}）")
        self.logLine.emit(f"[Sprout] 启动 {version_id}")

    @Slot(str)
    def sendCommand(self, text: str) -> None:
        line = (text or "").strip()
        if not line:
            return
        if self._proc is None or self._proc.state() == QProcess.NotRunning:
            self.toast.emit("游戏未运行，无法发送命令", "warn")
            return
        if not line.startswith("/"):
            line = "/" + line
        self._proc.write((line + "\n").encode("utf-8"))
        self.logLine.emit(f"[Sprout] > {line}")

    def _read_output(self) -> None:
        # stderr 里才有崩溃原因（例如 UnsupportedClassVersionError），必须一起收
        for raw in (bytes(self._proc.readAllStandardOutput()),
                    bytes(self._proc.readAllStandardError())):
            if not raw:
                continue
            text = raw.decode("utf-8", "replace")
            for line in text.splitlines():
                if line.strip():
                    self.logLine.emit(line)

    def _on_game_finished(self, code: int, _status) -> None:
        if not self._running and not self._runningVersion and not self._game_instance:
            # 已经复位过（finished 与守护定时器可能重复触发），不重复结算
            self._stopping = False
            return
        self._running = False
        played = int(time.time() - self._game_started_at) if self._game_started_at else 0
        self._game_started_at = 0.0
        if self._game_instance:
            self._store.touch(self._game_instance, played)
            self._sync_instances_model()
        self._game_instance = ""
        self._runningVersion = ""
        self.logLine.emit(f"[Sprout] 游戏已退出（代码 {code}）")
        if code != 0 and not self._stopping:
            self.toast.emit(f"游戏异常退出（代码 {code}），原因见下方日志", "error")
        self._stopping = False
        self._set_state(status="游戏已退出", progress=0.0, busy=False)
        self.gameStateChanged.emit()

    def _check_game_alive(self) -> None:
        # 兜底：状态标记为运行中、但进程其实已经退出时立刻复位，
        # 避免启动器一直显示「游戏运行中」
        if not self._running:
            return
        proc = self._proc
        if proc is not None and proc.state() != QProcess.NotRunning:
            return
        code = int(proc.exitCode()) if proc is not None else 0
        self.logLine.emit("[Sprout] 检测到游戏进程已结束，复位运行状态")
        self._on_game_finished(code, QProcess.NormalExit)

    def _on_game_error(self, _err) -> None:
        self._running = False
        self._runningVersion = ""
        self._game_instance = ""
        self.gameStateChanged.emit()

    @Slot()
    def killGame(self) -> None:
        proc = self._proc
        if proc is None or proc.state() == QProcess.NotRunning:
            # 进程其实早已退出但状态没复位时，点「结束」会毫无反应，这里兜底复位
            if self._running or self._runningVersion:
                self._running = False
                self._runningVersion = ""
                self._game_instance = ""
                self._set_state(status="游戏已退出", progress=0.0, busy=False)
                self.gameStateChanged.emit()
                self.toast.emit("游戏进程已结束，状态已复位", "warn")
            else:
                self.toast.emit("当前没有正在运行的游戏", "warn")
            return
        pid = int(proc.processId() or 0)
        self._stopping = True
        self.toast.emit("正在结束游戏…", "info")
        self.logLine.emit(f"[Sprout] 结束游戏（PID {pid}）")
        proc.kill()
        # kill 只作用于主进程，Minecraft 会带子进程，立刻整棵树强杀避免残留
        if pid:
            self._force_kill_if_alive(pid)
            # 仍不退出（例如被反作弊/子进程拖住）时再补一轮
            QTimer.singleShot(2500, lambda: self._force_kill_if_alive(pid))

    def _force_kill_if_alive(self, pid: int) -> None:
        proc = self._proc
        if proc is None or proc.state() == QProcess.NotRunning:
            return
        self.logLine.emit(f"[Sprout] 进程仍未退出，强制结束 PID {pid}")
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True, creationflags=0x08000000, timeout=10,
            )
        except Exception as exc:  # noqa: BLE001
            self.logLine.emit(f"[Sprout] 强制结束失败：{exc}")
            return
        if not proc.waitForFinished(3000):
            self.logLine.emit("[Sprout] 强制结束后进程仍未退出")

    # ------------------------------------------------------------- 实例
    @Slot(str)
    def removeInstance(self, instance_id: str) -> None:
        self._store.remove(instance_id)
        self._sync_instances_model()
        self.toast.emit("实例记录已移除（游戏文件保留）", "success")

    @Slot(str)
    def setModTarget(self, instance_id: str) -> None:
        self._mod_target = instance_id
        self._mod_filter_off = False
        self.stateChanged.emit()
        self._refresh_mods_model()
        self.modsChanged.emit()

    @Slot()
    def clearModFilter(self) -> None:
        """清除「装载模组」带入的实例筛选，回到不限版本/加载器的市场浏览。"""
        self._mod_target = ""
        self._mod_filter_off = True
        self.modFilterChanged.emit()
        self.toast.emit("已清除实例筛选，可按任意版本浏览", "info")

    # ---------------------------------------------------------- 启动目标选择
    launchChoiceChanged = Signal()

    _launch_choice: str = ""

    @Property(str, notify=launchChoiceChanged)
    def launchChoice(self):
        return self._launch_choice

    @Property("QVariantList", notify=installedChanged)
    def installedList(self):
        """已安装游戏列表（带缓存）：installedChanged 触发前只扫一次盘。

        缓存原因：首页多处绑定该属性，而构造过程需要遍历版本目录并多次读盘，
        单次开销约 0.1 秒，重复求值会造成切页卡顿。
        """
        cached = getattr(self, "_installed_cache", None)
        if cached is None:
            cached = self._build_installed_list()
            self._installed_cache = cached
        return cached

    def _drop_installed_cache(self) -> None:
        self._installed_cache = None

    def _build_installed_list(self):
        """已安装游戏列表：以本地文件系统为准，不依赖远程版本清单。

        名字优先取实例名，其次用版本目录名；附带版本目录、加载器与是否可启动。
        """
        local = self._local_versions()
        order: list[tuple[float, str]] = []
        for vid, vdir in local.items():
            try:
                mtime = (vdir / f"{vid}.json").stat().st_mtime
            except OSError:
                mtime = 0.0
            order.append((mtime, vid))
        order.sort(key=lambda x: (-x[0], x[1].lower()))

        rows = []
        for _mtime, vid in order:
            inst = None
            try:
                inst = self._store.for_version(vid)
            except Exception:  # noqa: BLE001
                inst = None
            try:
                loader = self._version_loader(vid)
            except Exception:  # noqa: BLE001
                loader = ""
            try:
                game_version = self._version_game(vid)
            except Exception:  # noqa: BLE001
                game_version = ""
            try:
                gaps = self._completion_gaps(vid)
            except Exception:  # noqa: BLE001
                gaps = []
            rows.append({
                "id": vid,
                "name": (inst.name if inst and inst.name else vid),
                "versionId": vid,
                "instanceId": (inst.id if inst else ""),
                "loader": loader,
                "gameVersion": game_version or vid,
                "ready": not gaps,
                "gapText": "、".join(gaps),
                "gameDir": self._game_dir_for(vid, inst),
            })
        return rows

    @Slot()
    def refreshLocal(self) -> None:
        """只扫本地文件系统（不联网）：让「已安装游戏」立刻可见。"""
        self._sync_instances_model()
        self.installedChanged.emit()
        self.versionsChanged.emit()

    @Slot(str)
    def setLaunchChoice(self, target_id: str) -> None:
        self._launch_choice = target_id or ""
        self.launchChoiceChanged.emit()

    @Slot()
    def launchChosen(self) -> None:
        target = self._launch_choice or (self._featured.get("id", "") if self._featured else "")
        if not target:
            # 界面默认展示「已安装列表第一个」，但后端此前没有同步这个默认值，
            # 导致首页直接点「启动游戏」时 target 为空、只弹一句提示什么都不做。
            # 这里做兜底：优先第一个文件齐全的可启动项，其次列表中第一个。
            rows = list(self.installedList or [])
            ready = [r for r in rows if r.get("ready")]
            pick = (ready or rows)[0] if (ready or rows) else None
            if pick:
                target = str(pick.get("id") or "")
                self._launch_choice = target
                self.launchChoiceChanged.emit()
                self.logLine.emit(f"[Sprout] 未显式选择版本，按列表首个可启动项启动：{target}")
        if not target:
            self.toast.emit("没有可启动的游戏，请先在版本库安装", "warn")
            return
        inst = None
        try:
            inst = self._store.for_version(target)
        except Exception:  # noqa: BLE001
            inst = None
        if inst:
            self.launchInstance(inst.id)
        else:
            self.launchVersion(target)

    @Slot(str)
    def openGameDir(self, target_id: str) -> None:
        if not target_id:
            return
        inst = None
        try:
            inst = self._store.for_version(target_id)
        except Exception:  # noqa: BLE001
            inst = None
        path = Path(self._game_dir_for(target_id, inst))
        path.mkdir(parents=True, exist_ok=True)
        self.openPath(str(path))

    @Slot(str)
    def useGameForMods(self, target_id: str) -> None:
        """把某个已安装游戏设为模组操作目标。"""
        if not target_id:
            return
        inst = None
        try:
            inst = self._store.for_version(target_id)
        except Exception:  # noqa: BLE001
            inst = None
        self.setModTarget(inst.id if inst else target_id)
        self.modFilterChanged.emit()

    # ------------------------------------------- 模组目标实例 / 加载器补齐
    modFilterChanged = Signal()
    loaderPromptChanged = Signal()
    instModsChanged = Signal()

    _mod_filter_off = False
    _inst_mods_model = None
    _loader_prompt = False
    _loader_prompt_inst = ""
    _loader_prompt_game = ""
    _loader_prompt_name = ""
    _pending_loader: tuple | None = None

    def _target_instance(self):
        """当前模组操作的实例：优先显式目标，其次当前选中版本对应的实例。"""
        if self._mod_target:
            inst = self._store.get(self._mod_target)
            if inst is not None:
                return inst
        vid = str(self._featured.get("id") or "")
        if vid:
            try:
                return self._store.for_version(vid)
            except Exception:  # noqa: BLE001
                return None
        return None

    def _instance_game_dir(self, inst) -> Path:
        if inst is None:
            return Path(self.mcDir)
        try:
            return Path(self._game_dir_for(inst.version_id, inst))
        except Exception:  # noqa: BLE001
            return Path(inst.game_dir or (Path(self.mcDir) / "instances" / inst.version_id))

    def _instance_loader(self, inst) -> str:
        return _norm_loader(getattr(inst, "loader", "")) if inst is not None else ""

    def _instance_game_version(self, inst) -> str:
        if inst is None:
            return ""
        vid = str(getattr(inst, "version_id", "") or "")
        game = ""
        if vid:
            try:
                game = self._version_game(vid)
            except Exception:  # noqa: BLE001
                game = ""
        return game or vid

    @Property(str, notify=modFilterChanged)
    def modFilterGame(self) -> str:
        _loader, game = self._market_tags()
        return game

    @Property(str, notify=modFilterChanged)
    def modFilterLoader(self) -> str:
        loader, _game = self._market_tags()
        return loader

    @Property(str, notify=modFilterChanged)
    def modFilterLabel(self) -> str:
        """模组市场顶部的筛选提示，告诉用户当前按哪个版本/加载器过滤。"""
        loader, game = self._market_tags()
        if not loader and not game:
            return ""
        label = loaders.LOADER_LABEL.get(loader, loader.upper()) if loader else "原版"
        return f"筛选 {game or '任意版本'} · {label}"

    @Property(str, notify=modFilterChanged)
    def modFilterInstance(self) -> str:
        inst = self._target_instance()
        if inst is None:
            return ""
        return str(inst.name or inst.version_id or inst.id)

    @Property(bool, notify=modFilterChanged)
    def modLoaderMissing(self) -> bool:
        """目标实例没有模组加载器：装模组前需要先引导用户安装。"""
        inst = self._target_instance()
        if inst is None:
            return False
        return not self._instance_loader(inst)

    @Property(bool, notify=loaderPromptChanged)
    def loaderPromptOpen(self) -> bool:
        return self._loader_prompt

    @Property(str, notify=loaderPromptChanged)
    def loaderPromptInstance(self) -> str:
        return self._loader_prompt_name

    @Property(str, notify=loaderPromptChanged)
    def loaderPromptGame(self) -> str:
        return self._loader_prompt_game

    @Property("QVariantList", notify=loaderPromptChanged)
    def loaderPromptChoices(self) -> list[dict]:
        return [
            {"key": "fabric", "label": "Fabric", "desc": "轻量、更新最快，模组生态最广（推荐）"},
            {"key": "forge", "label": "Forge", "desc": "老牌主流，大量老整合包依赖它"},
            {"key": "neoforge", "label": "NeoForge", "desc": "Forge 分支，1.20.2 之后的新主流"},
            {"key": "quilt", "label": "Quilt", "desc": "Fabric 分支，兼容 Fabric 模组"},
        ]

    def _open_loader_prompt(self, inst) -> None:
        self._loader_prompt = True
        self._loader_prompt_inst = str(getattr(inst, "id", "") or "")
        self._loader_prompt_name = str(getattr(inst, "name", "") or getattr(inst, "version_id", "") or "")
        self._loader_prompt_game = self._instance_game_version(inst)
        self.loaderPromptChanged.emit()

    @Slot()
    def closeLoaderPrompt(self) -> None:
        self._loader_prompt = False
        self._loader_prompt_inst = ""
        self._loader_prompt_name = ""
        self._loader_prompt_game = ""
        self.loaderPromptChanged.emit()

    @Slot(str, result=bool)
    def requestModsForInstance(self, instance_id: str) -> bool:
        """「装载模组」入口：设为模组目标 + 校验加载器；缺加载器返回 False 并弹选择框。"""
        if instance_id:
            inst = self._store.get(instance_id)
            if inst is None:
                try:
                    inst = self._store.for_version(instance_id)
                except Exception:  # noqa: BLE001
                    inst = None
            self.setModTarget(inst.id if inst else instance_id)
        self.modFilterChanged.emit()
        inst = self._target_instance()
        if inst is not None and not self._instance_loader(inst):
            self._open_loader_prompt(inst)
            self.toast.emit("该实例还没有模组加载器，请先选择一个安装", "warn")
            return False
        return True

    @Slot(str)
    def installLoaderForInstance(self, loader: str) -> None:
        """用户在加载器选择框里选定加载器后安装，并把它并回原实例。"""
        key = _norm_loader(loader)
        inst = self._store.get(self._loader_prompt_inst) if self._loader_prompt_inst else None
        self.closeLoaderPrompt()
        if not key:
            return
        if inst is None:
            self.toast.emit("未找到目标实例，请重新从游戏设置进入", "error")
            return
        if self._busy:
            self.toast.emit("已有任务在进行中，请稍后再试", "warn")
            return
        game = self._instance_game_version(inst)
        if not game:
            self.toast.emit("无法判定该实例的游戏版本，请先确认版本已安装完成", "error")
            return
        self._pending_loader = (inst.id, key)
        self.installWithLoader(game, key, "")

    def _finish_pending_loader(self, version_id: str, loader: str) -> None:
        """加载器装完后刷新界面筛选状态（实例已在 _do_install_loader 里并回）。"""
        pending = self._pending_loader
        self._pending_loader = None
        if not pending:
            return
        inst_id, want = pending
        if _norm_loader(loader) != want:
            return
        inst = self._store.get(inst_id)
        if inst is None:
            return
        self._refresh_mods_model()
        self.modsChanged.emit()
        self.modFilterChanged.emit()
        self.toast.emit(
            f"{inst.name or inst_id} 已安装 {loaders.LOADER_LABEL.get(loader, loader)}，可以继续装载模组了",
            "success",
        )

    # ------------------------------------------------------- 实例已装模组列表
    def _ensure_inst_mods_model(self):
        if self._inst_mods_model is None:
            self._inst_mods_model = DictListModel(MOD_ROLES)
            self._inst_mods_model.setParent(self)
        return self._inst_mods_model

    @Property("QVariant", constant=False, notify=instModsChanged)
    def instanceModsModel(self):
        return self._ensure_inst_mods_model()

    @Property(int, notify=instModsChanged)
    def instanceModCount(self) -> int:
        return self._ensure_inst_mods_model().rowCount()

    @Slot(str)
    def loadInstanceMods(self, instance_id: str) -> None:
        """读取某个实例 mods 目录下的全部模组（含禁用状态）。"""
        inst = self._store.get(instance_id)
        if inst is None:
            try:
                inst = self._store.for_version(instance_id)
            except Exception:  # noqa: BLE001
                inst = None
        rows: list[dict] = []
        if inst is not None:
            game_dir = self._instance_game_dir(inst)
            try:
                rows = mod_core.scan(game_dir)
            except Exception:  # noqa: BLE001
                rows = []
            for row in rows:
                row["titleZh"] = mod_zh.zh_name(
                    str(row.get("projectId") or ""), str(row.get("title") or row.get("file") or "")
                )
        self._ensure_inst_mods_model().set_items(rows)
        self.instModsChanged.emit()

    @Slot(str, str)
    def toggleInstanceMod(self, instance_id: str, filename: str) -> None:
        inst = self._store.get(instance_id)
        if inst is None or not filename:
            return
        try:
            enabled = mod_core.toggle(self._instance_game_dir(inst), filename)
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"操作失败：{exc}", "error")
            return
        self.toast.emit(("已启用 " if enabled else "已禁用 ") + filename, "success")
        self.loadInstanceMods(instance_id)
        if self._mod_target == instance_id:
            self._refresh_mods_model()
            self.modsChanged.emit()

    @Slot(str)
    def installModJarToInstance(self, instance_id: str) -> None:
        """由用户指定本地 jar 文件，直接安装到该实例的 mods 目录。"""
        inst = self._store.get(instance_id)
        if inst is None:
            self.toast.emit("未找到该实例", "error")
            return
        path, _ = QFileDialog.getOpenFileName(
            None, "选择要安装的模组文件", "",
            "模组文件 (*.jar *.litemod *.zip);;所有文件 (*)",
        )
        if not path:
            return
        src = Path(path)
        if not src.is_file():
            self.toast.emit("文件不存在", "error")
            return
        game_dir = self._instance_game_dir(inst)
        target_dir = game_dir / "mods"
        target_dir.mkdir(parents=True, exist_ok=True)
        dest = target_dir / src.name
        index = 1
        while dest.exists():
            dest = target_dir / f"{src.stem}({index}){src.suffix}"
            index += 1
        try:
            shutil.copy2(src, dest)
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"复制失败：{exc}", "error")
            return
        try:
            record = mod_core.load_record(game_dir)
            record[dest.name] = {
                "title": dest.stem, "projectId": "", "versionId": "",
                "source": "local", "version": "",
            }
            mod_core.save_record(game_dir, record)
        except Exception:  # noqa: BLE001
            pass
        self.toast.emit(f"已安装 {dest.name} 到 {inst.name or instance_id}", "success")
        self.loadInstanceMods(instance_id)
        if self._mod_target == instance_id:
            self._refresh_mods_model()
            self.modsChanged.emit()

    # ------------------------------------------------- 整合包拖放到任意界面导入
    @Slot("QVariantList")
    def dropModpacks(self, urls) -> None:
        paths: list[str] = []
        for item in urls or []:
            text = ""
            try:
                text = item.toString() if isinstance(item, QUrl) else str(item)
            except Exception:  # noqa: BLE001
                text = str(item)
            text = text.strip()
            if not text:
                continue
            if text.lower().startswith("file:"):
                local = QUrl(text).toLocalFile()
            else:
                local = text
            if local:
                paths.append(local)
        self.importDroppedFiles(paths)

    @Slot(str)
    def dropModpack(self, path: str) -> None:
        self.importDroppedFiles([path])

    def importDroppedFiles(self, paths: list[str]) -> None:
        files = [p for p in (paths or []) if p and Path(p).is_file()]
        if not files:
            self.toast.emit("没有识别到可导入的整合包文件", "warn")
            return
        target = Path(files[0])
        suffix = target.suffix.lower()
        if suffix in (".mrpack",):
            self.toast.emit(f"开始导入整合包 {target.name}", "info")
            self.importModpack(str(target))
            return
        if suffix == ".zip":
            kind = ""
            try:
                with zipfile.ZipFile(target) as zf:
                    names = set(zf.namelist())
                if "modrinth.index.json" in names:
                    kind = "modrinth"
                elif "manifest.json" in names:
                    kind = "curseforge"
            except Exception:  # noqa: BLE001
                kind = ""
            if kind == "modrinth":
                self.toast.emit(f"开始导入整合包 {target.name}", "info")
                self.importModpack(str(target))
                return
            if kind == "curseforge":
                self.toast.emit(
                    "检测到 CurseForge 整合包：请改用 .mrpack，或在 设置 → 模组来源 配置 API Key 后再拖入",
                    "warn",
                )
                return
            self.toast.emit("该 zip 不是可识别的整合包（缺少 modrinth.index.json / manifest.json）", "warn")
            return
        if suffix in (".cf", ".curseforge"):
            self.toast.emit(
                "CurseForge 整合包（.cf）需先在 设置 → 模组来源 配置 API Key，再拖入对应 zip",
                "warn",
            )
            return
        self.toast.emit(f"不支持的文件类型：{suffix or target.name}", "warn")

    # -------------------------------------------------------------- 模组详情
    modDetailChanged = Signal()
    modDetailLoadingChanged = Signal()
    modVersionsChanged = Signal()

    _mod_detail: dict = {}
    _mod_detail_loading: bool = False
    _detail_filter: str = ""
    _detail_default: str = ""
    _detail_all: list = []
    _detail_view: list = []
    _detail_model = None

    def _ensure_detail_model(self):
        if self._detail_model is None:
            self._detail_model = DictListModel(DETAIL_ROLES)
            self._detail_model.setParent(self)
        return self._detail_model

    @Property("QVariantMap", notify=modDetailChanged)
    def modDetail(self):
        return self._mod_detail

    @Property(bool, notify=modDetailLoadingChanged)
    def modDetailLoading(self):
        return self._mod_detail_loading

    @Property(str, notify=modDetailChanged)
    def detailFilter(self):
        return self._detail_filter

    @Property(str, notify=modVersionsChanged)
    def detailDefaultVersion(self):
        return self._detail_default

    @Property(int, notify=modVersionsChanged)
    def detailVersionCount(self):
        return len(self._detail_view)

    @Property("QVariant", constant=False, notify=modVersionsChanged)
    def modVersionsModel(self):
        return self._ensure_detail_model()

    @Slot(str)
    def openModDetail(self, project_id: str) -> None:
        if not project_id:
            return
        self._mod_detail = {
            "id": project_id,
            "title": project_id,
            "description": "正在加载详情…",
            "iconUrl": "",
            "downloads": 0,
            "updated": "",
            "categories": [],
            "gameVersions": [],
            "loaders": [],
            "projectType": self._mod_kind,
            "source": self._mod_source,
            "sourceUrl": "",
        }
        self._detail_filter = ""
        self._detail_default = ""
        self._detail_all = []
        self._detail_view = []
        self._ensure_detail_model().set_items([])
        self._mod_detail_loading = True
        self.modDetailChanged.emit()
        self.modDetailLoadingChanged.emit()
        self.modVersionsChanged.emit()
        self._bg(self._do_load_detail, project_id)

    @Slot()
    def closeModDetail(self) -> None:
        self._mod_detail = {}
        self._detail_all = []
        self._detail_view = []
        self._detail_filter = ""
        self._ensure_detail_model().set_items([])
        self._mod_detail_loading = False
        self.modDetailChanged.emit()
        self.modDetailLoadingChanged.emit()
        self.modVersionsChanged.emit()

    @Slot(str)
    def setDetailVersionFilter(self, mc_version: str) -> None:
        """按游戏版本筛选版本列表；传空串表示显示全部。"""
        self._detail_filter = (mc_version or "").strip()
        rows = self._detail_all
        if self._detail_filter:
            want = self._detail_filter

            def _hit(row) -> bool:
                tags = [t.strip() for t in str(row.get("gameVersions") or "").split(",")]
                if want in tags:
                    return True
                # 兼容带前缀的标签，如「Fabric 1.21.1」中含目标版本
                return any(t == want or t.endswith(" " + want) for t in tags)

            rows = [r for r in rows if _hit(r)]
        self._detail_view = rows
        self._detail_default = rows[0]["id"] if rows else ""
        self._ensure_detail_model().set_items(rows)
        self.modVersionsChanged.emit()
        self.modDetailChanged.emit()

    def _do_load_detail(self, project_id: str) -> None:
        if self._mod_source == "curseforge":
            self._do_load_detail_cf(project_id)
            return
        client = self._client()
        try:
            proj = client.project(project_id)
            versions = client.versions(project_id)
            game_tags: list = []
            rows = []
            for v in versions:
                gv, _ld = split_game_versions(list(v.get("game_versions") or []))
                for g in gv:
                    if g not in game_tags:
                        game_tags.append(g)
            for v in versions:
                files = v.get("files") or []
                primary = next((f for f in files if f.get("primary")), files[0] if files else {})
                gv, _ld = split_game_versions(list(v.get("game_versions") or []))
                rows.append({
                    "id": v.get("id", ""),
                    "versionNumber": v.get("version_number") or v.get("name") or "",
                    "name": v.get("name") or "",
                    "loader": (v.get("loaders") or [""])[0],
                    "gameVersions": ", ".join(gv),
                    "date": (v.get("date_published") or "")[:10],
                    "downloads": int(v.get("downloads") or 0),
                    "fileName": primary.get("filename", ""),
                    "size": int(primary.get("size") or 0),
                })
            slug = proj.get("slug") or project_id
            ptype = proj.get("project_type") or self._mod_kind
            self._detail_all = rows
            self._detail_view = rows
            self._mod_detail = {
                "id": proj.get("id") or project_id,
                "slug": slug,
                "title": proj.get("title") or project_id,
                "description": proj.get("description") or "",
                "iconUrl": proj.get("icon_url") or "",
                "downloads": int(proj.get("downloads") or 0),
                "updated": (proj.get("updated") or "")[:10],
                "categories": proj.get("categories") or [],
                "gameVersions": game_tags,
                "gameVersionCount": len(game_tags),
                "loaders": proj.get("loaders") or [],
                "projectType": ptype,
                "source": "modrinth",
                "sourceUrl": f"https://modrinth.com/{ptype}/{slug}",
            }
            self._detail_default = rows[0]["id"] if rows else ""
            self._ensure_detail_model().set_items(rows)
            self.modVersionsChanged.emit()
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"详情加载失败：{exc}", "error")
        finally:
            client.close()
            self._mod_detail_loading = False
            self.modDetailChanged.emit()
            self.modDetailLoadingChanged.emit()

    @staticmethod
    def _cf_web_url(project_type: str, slug: str) -> str:
        """拼出 CurseForge 官网项目页地址（始终指向 CurseForge 源）。"""
        seg = {
            "mod": "mc-mods",
            "modpack": "modpacks",
            "resourcepack": "texture-packs",
            "shader": "shaders",
            "world": "worlds",
        }.get(str(project_type or "mod"), "mc-mods")
        return f"https://www.curseforge.com/minecraft/{seg}/{slug}"

    @staticmethod
    def _cf_tags(file_info: dict) -> tuple[list[str], list[str]]:
        """把 CurseForge 文件的 gameVersions 标签拆成 (游戏版本, 加载器)。"""
        games: list[str] = []
        loaders: list[str] = []
        skip = {"client", "server", "cauldron", "rift"}
        for tag in file_info.get("gameVersions") or []:
            text = str(tag or "").strip()
            if not text:
                continue
            low = text.lower()
            if low in skip:
                continue
            if low[:1].isdigit():
                if text not in games:
                    games.append(text)
            elif low not in loaders:
                loaders.append(low)
        return games, loaders

    def _do_load_detail_cf(self, project_id: str) -> None:
        cf = self._cf()
        try:
            if cf is None:
                self.toast.emit(
                    "CurseForge 未配置 API Key：请在 设置 → 模组来源 中填入后重试",
                    "warn",
                )
                return
            mod = cf.project(project_id)
            files = cf.files(project_id, page_size=50)
            rows: list[dict] = []
            game_tags: list[str] = []
            loader_tags: list[str] = []
            for f in files:
                games, loaders = self._cf_tags(f)
                for g in games:
                    if g not in game_tags:
                        game_tags.append(g)
                for ld in loaders:
                    if ld not in loader_tags:
                        loader_tags.append(ld)
                rows.append({
                    "id": f"cf:{int(mod.get('id') or project_id)}:{int(f.get('id') or 0)}",
                    "versionNumber": f.get("displayName") or f.get("fileName") or "",
                    "name": f.get("displayName") or f.get("fileName") or "",
                    "loader": loaders[0] if loaders else "",
                    "gameVersions": ", ".join(games),
                    "date": str(f.get("fileDate") or "")[:10],
                    "downloads": int(mod.get("downloadCount") or 0),
                    "fileName": f.get("fileName") or "",
                    "size": int(f.get("fileLength") or 0),
                })

            def _by_date(row) -> str:
                return str(row.get("date") or "")

            rows.sort(key=_by_date, reverse=True)
            cats = [c.get("name") for c in (mod.get("categories") or []) if c.get("name")]
            logo = mod.get("logo") or {}
            self._detail_all = rows
            self._detail_view = rows
            self._mod_detail = {
                "id": str(mod.get("id") or project_id),
                "slug": mod.get("slug") or str(project_id),
                "title": mod.get("name") or project_id,
                "description": mod.get("summary") or "",
                "iconUrl": logo.get("thumbnailUrl") or logo.get("url") or "",
                "downloads": int(mod.get("downloadCount") or 0),
                "updated": str(mod.get("dateModified") or "")[:10],
                "categories": cats,
                "gameVersions": game_tags,
                "gameVersionCount": len(game_tags),
                "loaders": loader_tags,
                "projectType": self._mod_kind,
                "source": "curseforge",
                "sourceUrl": self._cf_web_url(self._mod_kind, mod.get("slug") or str(project_id)),
            }
            self._detail_default = rows[0]["id"] if rows else ""
            self._ensure_detail_model().set_items(rows)
            self.modVersionsChanged.emit()
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"详情加载失败：{exc}", "error")
        finally:
            self._mod_detail_loading = False
            self.modDetailChanged.emit()
            self.modDetailLoadingChanged.emit()

    # ------------------------------------------------------------- 前置模组检查
    @Property(bool, notify=depChanged)
    def depOpen(self) -> bool:
        return self._dep_open

    @Property("QVariantList", notify=depChanged)
    def depRows(self) -> list:
        return self._dep_rows

    @Property(str, notify=depChanged)
    def depTitle(self) -> str:
        return self._dep_title

    @Property(str, notify=depChanged)
    def depMessage(self) -> str:
        return self._dep_message

    @Property(int, notify=depChanged)
    def depCount(self) -> int:
        return len(self._dep_rows)

    @Property(int, notify=depChanged)
    def depTotalSize(self) -> int:
        return sum(int(r.get("size") or 0) for r in self._dep_rows)

    @Slot(str, str)
    def checkDepsAndDownload(self, version_id: str, dest_dir: str) -> None:
        """下载前自动检查前置模组：已装前置直接下载，缺失则弹窗列出。"""
        if not version_id:
            return
        if self._busy:
            self.toast.emit("已有任务在进行中", "warn")
            return
        self._set_state(status="检查前置模组…", progress=0.02, busy=True)
        self._bg(self._do_check_deps, version_id, dest_dir or "")

    def _installed_rows(self, target: Path) -> list:
        """取目标目录对应的已安装模组行（兼容传入 mods 目录或实例根目录）。"""
        cands: list[Path] = []
        if target.name.lower() == "mods":
            cands.append(target.parent)
        else:
            cands.append(target)
            if target.parent.name.lower() != "mods":
                cands.append(target.parent)
        for game_dir in cands:
            try:
                rows = mod_core.scan(game_dir)
            except Exception:  # noqa: BLE001
                continue
            if rows:
                return rows
        return []

    def _market_tags(self) -> tuple[str, str]:
        """模组市场 / 依赖匹配用的 (加载器, 游戏版本)。

        用户主动清除筛选后不再回退到当前选中版本，避免市场被隐式限定。
        """
        if self._mod_filter_off and not self._mod_target:
            return "", ""
        return self._dep_tags()

    def _dep_tags(self) -> tuple[str, str]:
        """前置匹配用的 (加载器, 游戏版本)：优先按模组安装目标实例判定。"""
        vid = ""
        loader = ""
        if self._mod_target:
            inst = self._store.get(self._mod_target)
            if inst:
                vid = str(getattr(inst, "version_id", "") or "")
                if getattr(inst, "loader", ""):
                    loader = _norm_loader(inst.loader)
        if not vid:
            vid = str(self._featured.get("id") or "")
        if not loader:
            loader = self._version_loader(vid) if vid else ""
        game = self._version_game(vid) if vid else ""
        return loader, game

    def _do_check_deps(self, version_id: str, dest_dir: str) -> None:
        if self._mod_source == "curseforge":
            self._do_check_deps_cf(version_id, dest_dir)
            return
        target = Path(dest_dir) if dest_dir else self._target_game_dir()
        client = self._client()
        try:
            ver = client.version(version_id)
            loader, game = self._dep_tags()
            deps, _skipped = mod_core._required_modrinth(client, ver, loader, game)
            installed = self._installed_rows(target)
            pids = {str(r.get("projectId") or "") for r in installed if r.get("projectId")}
            file_names = " ".join(str(r.get("file") or "").lower() for r in installed)

            missing: list = []
            rows: list = []
            skip: set = set()
            for dep in deps:
                pid = str(dep.get("project_id") or "")
                if pid and pid in pids:
                    skip.add(pid)
                    continue
                info: dict = {}
                slug = ""
                title = dep.get("name") or pid
                icon = ""
                try:
                    info = client.project(pid) if pid else {}
                    slug = str(info.get("slug") or "").lower()
                    title = info.get("title") or title
                    icon = info.get("icon_url") or ""
                except Exception:  # noqa: BLE001
                    slug = ""
                if slug and slug in file_names:
                    skip.add(pid)
                    continue
                files = dep.get("files") or []
                primary = next((f for f in files if f.get("primary")), files[0] if files else {})
                missing.append(dep)
                rows.append({
                    "projectId": pid,
                    "title": title,
                    "slug": slug,
                    "iconUrl": icon,
                    "versionId": dep.get("id", ""),
                    "versionNumber": dep.get("version_number") or dep.get("name") or "",
                    "fileName": primary.get("filename", ""),
                    "size": int(primary.get("size") or 0),
                })

            if not rows:
                # 前置已齐全：直接下载主模组（已装前置不重复下载）
                self._set_state(status="前置已齐全，开始下载", progress=0.06, busy=True)
                self._do_download_version(version_id, dest_dir, skip, None)
                return

            total = sum(int(r.get("size") or 0) for r in rows)
            self._dep_rows = rows
            self._dep_versions = missing
            self._dep_title = f"「{ver.get('name') or '该模组'}」需要 {len(rows)} 个前置模组"
            self._dep_message = (
                f"当前游戏目录未安装这些前置，共约 {total // 1048576} MB。"
                "可一键连同所选模组一起下载，或只下载所选模组。"
            )
            self._dep_pending = (version_id, dest_dir, skip, ver)
            self._dep_open = True
            self._set_state(status="等待确认前置模组", progress=0.0, busy=False)
            self.depChanged.emit()
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"前置检查失败：{exc}", "error")
            self._set_state(status="前置检查失败", progress=0.0, busy=False)
        finally:
            client.close()

    def _do_check_deps_cf(self, version_id: str, dest_dir: str) -> None:
        """CurseForge 前置检查：严格按当前实例的游戏版本 + 加载器匹配。"""
        target = Path(dest_dir) if dest_dir else self._target_game_dir()
        cf = self._cf()
        try:
            if cf is None:
                self.toast.emit(
                    "CurseForge 未配置 API Key：请在 设置 → 模组来源 中填入后重试",
                    "warn",
                )
                self._set_state(status="CurseForge 未配置 API Key", progress=0.0, busy=False)
                return
            ver = self._cf_version(cf, version_id)
            loader, game = self._dep_tags()
            deps, _skipped = cf.resolve_required(
                int(ver.get("mod_id") or 0), int(ver.get("file_id") or 0), loader, game,
            )
            installed = self._installed_rows(target)
            pids = {str(r.get("projectId") or "") for r in installed if r.get("projectId")}
            file_names = " ".join(str(r.get("file") or "").lower() for r in installed)

            missing: list = []
            rows: list = []
            skip: set = set()
            for dep in deps:
                pid = str(dep.get("project_id") or "")
                if pid and pid in pids:
                    skip.add(pid)
                    continue
                title = str(dep.get("project_title") or dep.get("name") or pid)
                if title and title.lower() in file_names:
                    skip.add(pid)
                    continue
                primary = (dep.get("files") or [{}])[0]
                missing.append(dep)
                rows.append({
                    "projectId": pid,
                    "title": title,
                    "slug": "",
                    "iconUrl": dep.get("icon_url") or "",
                    "versionId": dep.get("id", ""),
                    "versionNumber": dep.get("version_number") or dep.get("name") or "",
                    "fileName": primary.get("filename", ""),
                    "size": int(primary.get("size") or 0),
                })

            if not rows:
                self._set_state(status="前置已齐全，开始下载", progress=0.06, busy=True)
                self._do_download_version(version_id, dest_dir, skip, None)
                return

            total = sum(int(r.get("size") or 0) for r in rows)
            self._dep_rows = rows
            self._dep_versions = missing
            self._dep_title = f"「{ver.get('name') or '该模组'}」需要 {len(rows)} 个前置模组"
            self._dep_message = (
                f"当前游戏目录未安装这些前置，共约 {total // 1048576} MB。"
                "前置已按当前游戏版本与加载器严格匹配。"
                "可一键连同所选模组一起下载，或只下载所选模组。"
            )
            self._dep_pending = (version_id, dest_dir, skip, ver)
            self._dep_open = True
            self._set_state(status="等待确认前置模组", progress=0.0, busy=False)
            self.depChanged.emit()
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"前置检查失败：{exc}", "error")
            self._set_state(status="前置检查失败", progress=0.0, busy=False)

    @Slot()
    def confirmDepsDownload(self) -> None:
        """弹窗「全部一并下载」：所选模组 + 缺失前置一起下载。"""
        if not self._dep_pending:
            return
        version_id, dest_dir, skip, ver = self._dep_pending
        deps = self._dep_versions
        count = len(self._dep_rows)
        self._dep_open = False
        self._dep_pending = None
        self.depChanged.emit()
        self._set_state(status="下载模组与前置…", progress=0.05, busy=True)
        self._bg(self._download_with_deps, version_id, dest_dir, ver, deps, count)

    def _download_with_deps(self, version_id: str, dest_dir: str, ver: dict,
                            deps: list, dep_count: int) -> None:
        items = [ver] + list(deps)
        self._do_download_version(version_id, dest_dir, set(), items)
        if dep_count:
            self.toast.emit(f"已同时下载 {dep_count} 个前置模组", "success")

    @Slot()
    def downloadSelectedOnly(self) -> None:
        """弹窗「仅下载所选模组」：不下载缺失前置。"""
        if not self._dep_pending:
            return
        version_id, dest_dir, _skip, _ver = self._dep_pending
        self._dep_open = False
        self._dep_pending = None
        self._dep_rows = []
        self._dep_versions = []
        self.depChanged.emit()
        self._set_state(status="下载所选模组…", progress=0.05, busy=True)
        self._bg(self._do_download_version, version_id, dest_dir, set(), None, True)

    @Slot()
    def cancelDepsDownload(self) -> None:
        self._dep_open = False
        self._dep_pending = None
        self._dep_rows = []
        self._dep_versions = []
        self.depChanged.emit()
        self._set_state(status="已取消", progress=0.0, busy=False)

    @Slot(str, str)
    def downloadModVersion(self, version_id: str, dest_dir: str) -> None:
        if not version_id:
            return
        if self._busy:
            self.toast.emit("已有任务在进行中", "warn")
            return
        self._set_state(status="准备下载…", progress=0.02, busy=True)
        self._bg(self._do_download_version, version_id, dest_dir or "")

    @staticmethod
    def _cf_split_id(version_id: str) -> tuple[int, int]:
        """解析「cf:模组ID:文件ID」形式的版本标识。"""
        text = str(version_id or "")
        if text.startswith("cf:"):
            parts = text.split(":")
            if len(parts) >= 3:
                try:
                    return int(parts[1]), int(parts[2])
                except ValueError:
                    pass
        raise ValueError("CurseForge 版本标识无效")

    def _cf_version(self, cf: CurseForgeClient, version_id: str) -> dict:
        """把 CF 文件标识还原为归一化版本字典。"""
        mod_id, file_id = self._cf_split_id(version_id)
        mod = cf.project(mod_id)
        info = None
        try:
            for f in cf.files(mod_id):
                if int(f.get("id") or 0) == file_id:
                    info = f
                    break
        except Exception:  # noqa: BLE001
            info = None
        if info is None:
            info = cf.file(mod_id, file_id)
        return cf.version_from(mod, info)

    def _do_download_version(self, version_id: str, dest_dir: str,
                             skip_ids: set | None = None,
                             dep_versions: list | None = None,
                             only_main: bool = False) -> None:
        target = Path(dest_dir) if dest_dir else self._target_game_dir()
        target.mkdir(parents=True, exist_ok=True)
        source = self._mod_source
        cf = self._cf() if source == "curseforge" else None
        client = None if source == "curseforge" else self._client()
        try:
            if source == "curseforge":
                if cf is None:
                    self.toast.emit(
                        "CurseForge 未配置 API Key：请在 设置 → 模组来源 中填入后重试",
                        "warn",
                    )
                    self._set_state(status="CurseForge 未配置 API Key", progress=0.0, busy=False)
                    return
                ver = self._cf_version(cf, version_id)
            else:
                ver = client.version(version_id)
                try:
                    title = client.project(ver.get("project_id") or "").get("title") or ""
                except Exception:  # noqa: BLE001
                    title = ""
                if title:
                    ver = dict(ver)
                    ver["project_title"] = title
            if dep_versions is not None:
                items = list(dep_versions)
            elif only_main:
                items = [ver]
            else:
                loader, game = self._dep_tags()
                if source == "curseforge":
                    deps, _skipped = cf.resolve_required(
                        int(ver.get("mod_id") or 0), int(ver.get("file_id") or 0),
                        loader, game,
                    )
                else:
                    deps, _skipped = mod_core._required_modrinth(
                        client, ver, loader, game,
                    )
                skip = skip_ids or set()
                items = [ver] + [d for d in deps if (d.get("project_id") or "") not in skip]
            total = len(items) or 1
            game_dir = self._target_game_dir()
            self._set_state(
                status=f"下载 {ver.get('name') or version_id}",
                progress=0.05, busy=True,
            )
            installed = mod_core._install_versions(
                target, items, self.mirror,
                lambda stage, done, all_count: self._set_state(
                    status=stage, progress=(done / all_count) if all_count else 0.4, busy=True,
                ),
                source=source, cf=cf, game_dir=game_dir,
            )
            names = [i.get("file") or "" for i in installed]
            self._set_state(status="下载完成", progress=1.0, busy=False)
            self.toast.emit(
                "已下载 " + ("、".join(names[:3]) if names else f"{total} 个文件"),
                "success",
            )
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"下载失败：{exc}", "error")
            self._set_state(status="下载失败", progress=0.0, busy=False)
        finally:
            if client is not None:
                client.close()
        try:
            self._refresh_mods_model()
            self.modsChanged.emit()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------- 模组市场
    @Slot(str, str)
    def searchMods(self, query: str, project_type: str) -> None:
        if self._mod_loading:
            return
        self._mod_query = query or ""
        self._mod_kind = project_type or "mod"
        self._mod_offset = 0
        self._mod_loading = True
        self.searchLoadingChanged.emit()
        self._bg(self._do_search, True)

    @Slot()
    def loadMoreMods(self) -> None:
        if self._mod_loading or self._mod_offset >= self._mod_total:
            return
        self._mod_loading = True
        self.searchLoadingChanged.emit()
        self._bg(self._do_search, False)

    def _do_search(self, reset: bool) -> None:
        if self._mod_source == "curseforge":
            self._do_search_cf(reset)
            return
        client = self._client()
        try:
            query = (self._mod_query or "").strip()
            rows = []
            # 从实例跳「装载模组」进来时，按该实例的游戏版本 + 加载器筛选
            dep_loader, game_version = self._market_tags()
            filt_loader = dep_loader if self._mod_kind == "mod" else ""
            if not query:
                # 没有搜索词也照常出列表：直接用项目类型过滤，按下载量（热度）倒序
                result = client.search(
                    "", project_type=self._mod_kind,
                    loader=filt_loader, mc_version=game_version,
                    offset=self._mod_offset, limit=20, index="downloads",
                )
                if not result.get("hits") and (filt_loader or game_version):
                    result = client.search(
                        "", project_type=self._mod_kind,
                        offset=self._mod_offset, limit=20, index="downloads",
                    )
            else:
                result = client.search(
                    query, project_type=self._mod_kind,
                    loader=filt_loader,
                    mc_version=game_version,
                    offset=self._mod_offset, limit=20,
                )
                if not result.get("hits") and (filt_loader or game_version):
                    result = client.search(
                        query, project_type=self._mod_kind,
                        offset=self._mod_offset, limit=20,
                    )
            self._mod_total = int(result.get("total_hits") or 0)
            installed = {m.get("projectId") for m in mod_core.scan(self._target_game_dir())}
            for hit in result.get("hits") or []:
                title = hit.get("title") or ""
                rows.append({
                    "id": hit.get("project_id") or hit.get("slug") or "",
                    "title": title,
                    "titleZh": mod_zh.zh_name(hit.get("slug") or hit.get("project_id") or "", title),
                    "description": (hit.get("description") or "")[:120],
                    "iconUrl": hit.get("icon_url") or "",
                    "downloads": int(hit.get("downloads") or 0),
                    "author": hit.get("author") or "",
                    "projectType": hit.get("project_type") or self._mod_kind,
                    "installed": (hit.get("project_id") or "") in installed,
                })
            uniq = []
            seen = set()
            for row in rows:
                key = row.get("id") or row.get("title")
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(row)
            rows = uniq
            if reset:
                self._search_model.set_items(rows)
            else:
                current = [self._search_model.item(i) for i in range(self._search_model.rowCount())]
                seen = {item.get("id") for item in current}
                self._search_model.set_items(
                    current + [row for row in rows if row.get("id") not in seen]
                )
            self._mod_offset += len(result.get("hits") or [])
            self.searchChanged.emit()
        finally:
            client.close()
            self._mod_loading = False
            self.searchLoadingChanged.emit()

    def _do_search_cf(self, reset: bool) -> None:
        """CurseForge 搜索：未配置 API Key 时给出明确提示而不是抛错。"""
        cf = self._cf()
        try:
            if cf is None:
                self._mod_total = 0
                if reset:
                    self._search_model.set_items([])
                self.toast.emit(
                    "CurseForge 未配置 API Key：请在 设置 → 模组来源 中填入后重试",
                    "warn",
                )
                self._set_state(status="CurseForge 未配置 API Key", progress=0.0, busy=False)
                return
            kind = self._mod_kind
            dep_loader, game = self._market_tags()
            loader = "" if kind != "mod" else dep_loader
            result = cf.search(
                (self._mod_query or "").strip(), project_type=kind,
                loader=loader, mc_version=game,
                offset=self._mod_offset, limit=20,
            )
            if not result.get("hits") and (loader or game):
                # 严格条件无结果时放宽，避免空列表让用户以为没搜到
                result = cf.search(
                    (self._mod_query or "").strip(), project_type=kind,
                    offset=self._mod_offset, limit=20,
                )
            self._mod_total = int(result.get("total") or 0)
            try:
                installed = {str(m.get("projectId") or "") for m in mod_core.scan(self._target_game_dir())}
            except Exception:  # noqa: BLE001
                installed = set()
            rows: list[dict] = []
            for hit in result.get("hits") or []:
                mid = str(hit.get("id") or "")
                logo = hit.get("logo") or {}
                authors = hit.get("authors") or []
                cname = hit.get("name") or ""
                rows.append({
                    "id": mid,
                    "title": cname,
                    "titleZh": mod_zh.zh_name("", cname),
                    "description": (hit.get("summary") or "")[:120],
                    "iconUrl": logo.get("thumbnailUrl") or logo.get("url") or "",
                    "downloads": int(hit.get("downloadCount") or 0),
                    "author": ((authors[0] or {}).get("name") if authors else "") or "",
                    "projectType": kind,
                    "installed": mid in installed,
                })
            uniq: list[dict] = []
            seen: set = set()
            for row in rows:
                key = row.get("id") or row.get("title")
                if key in seen:
                    continue
                seen.add(key)
                uniq.append(row)
            rows = uniq
            if reset:
                self._search_model.set_items(rows)
            else:
                current = [self._search_model.item(i) for i in range(self._search_model.rowCount())]
                have = {item.get("id") for item in current}
                self._search_model.set_items(current + [r for r in rows if r.get("id") not in have])
            self._mod_offset += len(result.get("hits") or [])
            self.searchChanged.emit()
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"CurseForge 搜索失败：{exc}", "error")
        finally:
            self._mod_loading = False
            self.searchLoadingChanged.emit()

    @Slot(str)
    def installMod(self, project_id: str) -> None:
        if not project_id:
            return
        if self._busy:
            self.toast.emit("已有任务在进行中", "warn")
            return
        self._set_state(status="准备安装模组", progress=0.02, busy=True)
        self._bg(self._do_install_mod, project_id, "")

    @Slot(str, str)
    def installModTo(self, project_id: str, dest_dir: str) -> None:
        """安装到用户指定目录。"""
        if not project_id:
            return
        if self._busy:
            self.toast.emit("已有任务在进行中", "warn")
            return
        self._set_state(status="准备安装模组", progress=0.02, busy=True)
        self._bg(self._do_install_mod, project_id, dest_dir or "")

    @Slot(str, str, result=str)
    def chooseDir(self, title: str, start: str) -> str:
        """选择文件夹，取消返回空串。"""
        path = QFileDialog.getExistingDirectory(None, title or "选择文件夹", start or "")
        return path or ""

    def _do_install_mod(self, project_id: str, dest_dir: str = "") -> None:
        target = self._target_game_dir()
        target.mkdir(parents=True, exist_ok=True)
        vid = self._featured.get("id", "")
        source = self._mod_source
        cf = self._cf() if source == "curseforge" else None
        client = None if source == "curseforge" else self._client()

        def on_progress(stage: str, done: int, total: int) -> None:
            self._set_state(status=stage, progress=(done / total) if total else 0.4, busy=True)

        try:
            if source == "curseforge" and cf is None:
                self.toast.emit(
                    "CurseForge 未配置 API Key：请在 设置 → 模组来源 中填入后重试",
                    "warn",
                )
                self._set_state(status="CurseForge 未配置 API Key", progress=0.0, busy=False)
                return
            kind = self._mod_kind
            if kind in ("shader", "resourcepack", "datapack"):
                loader = ""
            else:
                loader = self._version_loader(vid) if vid else ""
            dep_loader, dep_game = self._dep_tags()
            if kind not in ("shader", "resourcepack", "datapack") and dep_loader:
                loader = dep_loader
            installed = mod_core.install_project(
                client, target, project_id, loader=loader,
                mc_version=(dep_game or (self._version_game(vid) if vid else "")),
                mirror=self.mirror, on_progress=on_progress,
                dest_dir=Path(dest_dir) if dest_dir else None,
                source=source, cf=cf,
            )
            names = "、".join(i["title"] for i in installed) or "项目"
            self.toast.emit(f"已安装 {names}", "success")
            self._set_state(status="模组安装完成", progress=1.0, busy=False)
        finally:
            if client is not None:
                client.close()
        self._refresh_mods_model()
        self.modsChanged.emit()
        self._bg(self._do_search, True)

    @Slot()
    def refreshMods(self) -> None:
        self._refresh_mods_model()
        self.modsChanged.emit()

    def _refresh_mods_model(self) -> None:
        try:
            rows = mod_core.scan(self._target_game_dir())
        except OSError:
            rows = []
        for row in rows:
            row["titleZh"] = mod_zh.zh_name(
                str(row.get("projectId") or ""), str(row.get("title") or row.get("file") or "")
            )
        self._mods_model.set_items(rows)

    @Slot(str)
    def toggleMod(self, filename: str) -> None:
        enabled = mod_core.toggle(self._target_game_dir(), filename)
        self.toast.emit("已启用" if enabled else "已禁用", "success")
        self._refresh_mods_model()
        self.modsChanged.emit()

    @Slot(str)
    def removeMod(self, filename: str) -> None:
        ok = mod_core.remove(self._target_game_dir(), filename)
        self.toast.emit("已删除" if ok else "删除失败", "success" if ok else "error")
        self._refresh_mods_model()
        self.modsChanged.emit()

    @Slot()
    def checkModUpdates(self) -> None:
        if self._busy:
            self.toast.emit("已有任务在进行中", "warn")
            return
        self._set_state(status="检查模组更新…", progress=0.1, busy=True)
        self._bg(self._do_check_updates)

    def _do_check_updates(self) -> None:
        target = self._target_game_dir()
        vid = self._featured.get("id", "")
        cf = self._cf()
        client = self._client()
        try:
            updates = mod_core.check_updates(
                client, target,
                loader=self._version_loader(vid) if vid else "",
                mc_version=self._version_game(vid) if vid else "",
                cf=cf,
            )
        finally:
            client.close()
        rows = mod_core.scan(target)
        up_by_file = {u["file"]: u for u in updates}
        for row in rows:
            if row["file"] in up_by_file:
                row["hasUpdate"] = True
                row["latestVersion"] = up_by_file[row["file"]].get("latestVersion", "")
        self._mods_model.set_items(rows)
        self.modsChanged.emit()
        self._set_state(
            status=f"{len(updates)} 个模组可更新" if updates else "模组均为最新",
            progress=1.0, busy=False,
        )
        self.toast.emit(
            f"{len(updates)} 个模组有新版本" if updates else "所有模组已是最新",
            "success" if updates else "info",
        )

    @Slot()
    def updateAllMods(self) -> None:
        if self._busy:
            self.toast.emit("已有任务在进行中", "warn")
            return
        target = self._target_game_dir()
        pending = [r for r in mod_core.scan(target) if r.get("projectId")]
        if not pending:
            self.toast.emit("没有可更新的模组", "info")
            return
        self._set_state(status="更新模组…", progress=0.05, busy=True)
        self._bg(self._do_update_mods, pending)

    def _do_update_mods(self, pending: list) -> None:
        target = self._target_game_dir()
        vid = self._featured.get("id", "")
        loader = self._version_loader(vid) if vid else ""
        game = self._version_game(vid) if vid else ""
        cf = self._cf()
        client = self._client()
        rows = [r if isinstance(r, dict) else {"projectId": r} for r in pending]
        total = max(1, len(rows))
        done = 0
        try:
            for row in rows:
                pid = str(row.get("projectId") or "")
                if not pid:
                    continue
                source = str(row.get("source") or "modrinth").lower()
                use_cf = cf if source == "curseforge" else None
                if source == "curseforge" and use_cf is None:
                    continue
                try:
                    mod_core.install_project(
                        client, target, pid, loader=loader, mc_version=game, mirror=self.mirror,
                        on_progress=lambda s, d, t: self._set_state(
                            status=s, progress=(done + (d / t if t else 0)) / total, busy=True),
                        source=source, cf=use_cf,
                    )
                    done += 1
                except Exception:  # noqa: BLE001
                    continue
        finally:
            client.close()
        self._refresh_mods_model()
        self.modsChanged.emit()
        self._set_state(status=f"已更新 {done} 个模组", progress=1.0, busy=False)
        self.toast.emit(f"已更新 {done} 个模组", "success")

    # ------------------------------------------------------------- 整合包
    @Slot(str)
    def importModpack(self, pack_path: str) -> None:
        if not pack_path:
            return
        if self._busy:
            self.toast.emit("已有任务在进行中", "warn")
            return
        self._set_state(status="准备导入整合包", progress=0.02, busy=True)
        self._bg(self._do_import_pack, pack_path)

    def _do_import_pack(self, pack_path: str) -> None:
        manifest = self._manifest_or_fetch()

        def on_progress(stage: str, done: int, total: int) -> None:
            self._set_state(status=stage, progress=(done / total) if total else 0.3, busy=True)

        result = pack_core.install_pack(
            Path(pack_path), Path(self.mcDir), manifest, self._store,
            mirror=self.mirror, on_progress=on_progress,
        )
        self._sync_instances_model()
        self._set_state(status=f"{result['name']} 导入完成", progress=1.0, busy=False)
        self.toast.emit(
            f"{result['name']} 已导入（{result['files']} 个文件）" if not result.get("failures")
            else f"导入完成，{result['failures']} 个文件失败",
            "success" if not result.get("failures") else "warn",
        )
        threading.Thread(target=self._do_refresh, daemon=True).start()

    @Slot(str)
    def exportModpack(self, out_path: str) -> None:
        if not out_path:
            return
        self._set_state(status="正在导出整合包…", progress=0.2, busy=True)

        def work() -> None:
            try:
                target = self._target_game_dir()
                vid = self._featured.get("id", "")
                path = pack_core.export_pack(Path(target), Path(out_path), target.name, vid)
                self.toast.emit(f"已导出到 {path.name}", "success")
                self._set_state(status="导出完成", progress=1.0, busy=False)
            except Exception as exc:  # noqa: BLE001
                self.toast.emit(f"导出失败：{exc}", "error")
                self._set_state(status="导出失败", progress=0.0, busy=False)

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------- 账户
    @Slot(str)
    def addOfflineAccount(self, name: str) -> None:
        account = account_core.offline_account(name)
        self._accounts.upsert(account)
        self.accountsChanged.emit()
        self.toast.emit(f"已切换到 {account.name}", "success")

    @Slot(str)
    def setActiveAccount(self, account_id: str) -> None:
        if self._accounts.set_active(account_id):
            self.accountsChanged.emit()
            self.toast.emit(f"已切换到 {self._accounts.active().name}", "success")

    @Slot(str)
    def removeAccount(self, account_id: str) -> None:
        self._accounts.remove(account_id)
        self.accountsChanged.emit()

    @Slot()
    def startMicrosoftLogin(self) -> None:
        if self._login_busy:
            return
        client_id = self.msClientId
        self._login_busy = True
        self.loginStateChanged.emit()
        self._bg(self._do_ms_login, client_id)

    def _do_ms_login(self, client_id: str) -> None:
        try:
            flow = account_core.begin_device_login(client_id)
            self.deviceCode.emit(flow.get("user_code", ""), flow.get("verification_uri", ""))
            self.toast.emit("请在浏览器完成微软登录", "info")
            token = account_core.poll_device_login(
                client_id, flow.get("device_code", ""),
                flow.get("interval", 5), flow.get("expires_in", 900),
                on_wait=lambda left: None,
            )
            account = account_core.microsoft_account(token, self._accounts)
            self.accountsChanged.emit()
            self.toast.emit(f"已登录：{account.name}", "success")
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"微软登录失败：{exc}", "error")
        finally:
            self._login_busy = False
            self.loginStateChanged.emit()

    @Slot(str)
    def openUrl(self, url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))

    # ------------------------------------------------------------- 皮肤
    def _account_by_id(self, account_id: str):
        target = str(account_id or "").strip()
        for item in getattr(self._accounts, "items", []) or []:
            if str(getattr(item, "id", "")) == target:
                return item
        if target:
            return None
        return self._accounts.active()

    @Slot(str, result=str)
    def skinPreview(self, account_id: str) -> str:
        account = self._account_by_id(account_id)
        if account is None:
            return ""
        try:
            path = skin_core.preview_for_account(account, None)
        except Exception:
            return ""
        if not path:
            return ""
        return QUrl.fromLocalFile(str(path)).toString()

    @Slot(str, result=str)
    def accountSkinModel(self, account_id: str) -> str:
        account = self._account_by_id(account_id)
        return skin_core.normalize_model(getattr(account, "skin_model", "") if account is not None else "")

    @Property(bool, notify=skinBusyChanged)
    def skinBusy(self) -> bool:
        return bool(getattr(self, "_skin_busy", False))

    @Slot(str, str, str)
    def setAccountSkin(self, account_id: str, png_path: str, model: str) -> None:
        if getattr(self, "_skin_busy", False):
            self.toast.emit("皮肤处理中，请稍候", "warn")
            return
        account = self._account_by_id(account_id)
        if account is None:
            self.toast.emit("未找到该账户", "warn")
            return
        if str(getattr(account, "type", "")) != "microsoft":
            self.toast.emit("离线账户不支持自定义皮肤", "warn")
            return
        path = str(png_path or "").strip()
        if not path:
            self.toast.emit("请先选择皮肤图片", "warn")
            return
        if path.startswith("file:"):
            path = QUrl(path).toLocalFile()
        self._skin_busy = True
        self.skinBusyChanged.emit()
        self._bg(self._do_set_skin, account, path, skin_core.normalize_model(model))

    def _do_set_skin(self, account, png_path: str, model: str) -> None:
        try:
            result = skin_core.upload_skin(account, self.msClientId, png_path, model)
            url = str((result or {}).get("url") or "")
            used = skin_core.normalize_model(str((result or {}).get("model") or model))
            try:
                account.skin = url
                account.skin_model = used
            except Exception:
                pass
            self._accounts.save()
            self.toast.emit("皮肤已更新", "success")
            self.accountsChanged.emit()
            self.skinChanged.emit()
        except skin_core.SkinError as exc:
            self.toast.emit(str(exc), "error")
        except Exception as exc:
            self.toast.emit("皮肤上传失败：" + str(exc), "error")
        finally:
            self._skin_busy = False
            self.skinBusyChanged.emit()
            self.skinChanged.emit()

    @Slot(str)
    def refreshAccountSkin(self, account_id: str) -> None:
        account = self._account_by_id(account_id)
        if account is None or str(getattr(account, "type", "")) != "microsoft":
            return
        self._bg(self._do_refresh_skin, account)

    def _do_refresh_skin(self, account) -> None:
        try:
            info = skin_core.sync_from_service(account, self.msClientId) or {}
            url = str(info.get("url") or "")
            model = skin_core.normalize_model(str(info.get("model") or ""))
            try:
                account.skin = url
                account.skin_model = model
            except Exception:
                pass
            self._accounts.save()
        except Exception as exc:
            self.toast.emit("同步皮肤失败：" + str(exc), "warn")
        finally:
            self.accountsChanged.emit()
            self.skinChanged.emit()

    # ------------------------------------------------------------- 内存优化
    @Property(str, notify=memChanged)
    def memorySummary(self) -> str:
        info = getattr(self, "_mem_info", None) or {}
        if not info:
            return "尚未优化"
        try:
            before = int(info.get("beforePercent") or 0)
            after = int(info.get("afterPercent") or 0)
            freed = int(info.get("freedMb") or 0)
            return f"内存占用 {before}% -> {after}%，释放 {freed} MB"
        except Exception:
            return "已优化"

    @Property(bool, notify=memChanged)
    def memBusy(self) -> bool:
        return bool(getattr(self, "_mem_busy", False))

    @Slot()
    def optimizeMemory(self) -> None:
        if getattr(self, "_mem_busy", False):
            self.toast.emit("正在优化内存，请稍候", "warn")
            return
        self._mem_busy = True
        self.memChanged.emit()
        self._bg(self._do_optimize_memory)

    def _do_optimize_memory(self) -> None:
        try:
            info = memtool.optimize()
            info = info if isinstance(info, dict) else {}
            self._mem_info = info
            if info.get("ok"):
                self.toast.emit("内存已优化，释放 %d MB" % int(info.get("freedMb") or 0), "success")
            elif info.get("error"):
                self.toast.emit(str(info.get("error")), "warn")
            else:
                self.toast.emit("内存优化完成", "info")
        except Exception as exc:
            self.toast.emit("内存优化失败：" + str(exc), "error")
        finally:
            self._mem_busy = False
            self.memChanged.emit()

    # ------------------------------------------------------------- 工具箱
    @Slot(result="QVariantList")
    def githubMirrorOptions(self):
        return [{"id": str(m.get("id")), "name": str(m.get("name"))} for m in accelerate.GITHUB_MIRRORS]

    @Slot(result="QVariantList")
    def steamRegionOptions(self):
        return [{"id": str(r.get("id")), "name": str(r.get("name"))} for r in accelerate.STEAM_REGIONS]

    @Property(bool, notify=toolboxChanged)
    def githubAccel(self) -> bool:
        return bool(accelerate.ACCEL.github_enabled)

    @Property(str, notify=toolboxChanged)
    def githubMirrorId(self) -> str:
        return str(accelerate.ACCEL.github_mirror or "")

    @Property(bool, notify=toolboxChanged)
    def steamAccel(self) -> bool:
        return bool(accelerate.ACCEL.steam_enabled)

    @Property(str, notify=toolboxChanged)
    def steamRegionId(self) -> str:
        return str(accelerate.ACCEL.steam_region or "cn")

    @Property(str, notify=toolboxChanged)
    def steamRoute(self) -> str:
        if not accelerate.ACCEL.steam_enabled:
            return "Steam 加速未启用"
        if getattr(self, "_steam_probing", False):
            return "正在探测最优节点…"
        info = getattr(self, "_accel_state", None) or {}
        route = info.get("steamRoute") or {}
        if isinstance(route, dict):
            text = str(route.get("message") or "").strip()
            if text:
                return text
        return "已开启，等待线路探测"

    @Slot(bool, str)
    def setGithub(self, enabled: bool, mirror_id: str) -> None:
        try:
            accelerate.ACCEL.set_github(bool(enabled), str(mirror_id or "ghfast"))
        except Exception as exc:
            self.toast.emit("GitHub 加速设置失败：" + str(exc), "error")
            return
        self.toolboxChanged.emit()
        self.toast.emit("GitHub 加速已" + ("开启" if enabled else "关闭"), "info")

    @Slot(bool, str)
    def setSteam(self, enabled: bool, region_id: str) -> None:
        rid = str(region_id or "cn")
        try:
            accelerate.ACCEL.set_steam_state(bool(enabled), rid)
        except Exception as exc:
            self.toast.emit("Steam 加速设置失败：" + str(exc), "error")
            return
        # 开关状态立即生效并广播，旧快照必须清掉，否则界面会残留「未启用」
        self._accel_state = {}
        self.toolboxChanged.emit()
        self.toast.emit("Steam 加速已" + ("开启" if enabled else "关闭"), "info")
        if enabled:
            # 开启即把区服写进 Steam 客户端，否则 Steam 仍按原 cell 走，用户会觉得没效果
            self._auto_apply_steam_cell(rid)
            self._probe_accel_async()

    def _auto_apply_steam_cell(self, region_id: str) -> None:
        try:
            res = accelerate.apply_steam_cell(str(region_id or "cn"))
        except Exception as exc:  # noqa: BLE001
            self.toast.emit("写入 Steam 区服失败：" + str(exc), "warn")
            return
        res = res if isinstance(res, dict) else {}
        if res.get("ok"):
            self.toast.emit(str(res.get("message") or "已写入 Steam 区服"), "success")
        else:
            self.toast.emit(str(res.get("message") or "未能写入 Steam 区服"), "warn")
        self.toolboxChanged.emit()

    @Slot()
    def refreshAccel(self) -> None:
        if not accelerate.ACCEL.steam_enabled:
            self.toast.emit("请先开启 Steam 加速", "info")
            return
        self._probe_accel_async()

    @Property(str, notify=toolboxChanged)
    def steamClientCell(self) -> str:
        """Steam 客户端 config.vdf 里当前写着的区服（加速是否真正落到客户端）。"""
        try:
            info = accelerate.steam_cell_override()
        except Exception as exc:  # noqa: BLE001
            return "客户端区服读取失败：" + str(exc)
        info = info if isinstance(info, dict) else {}
        if not info.get("ok"):
            return str(info.get("message") or "未检测到 Steam 客户端")
        value = str(info.get("value") or "").strip()
        state = "Steam 运行中" if info.get("running") else "Steam 未运行"
        if value:
            return "客户端当前区服 cell " + value + "（" + state + "）"
        return "客户端未设置区服（" + state + "）"

    @Slot(result=str)
    def applySteamCell(self) -> str:
        """把当前区服写进 Steam 客户端（需先完全退出 Steam）。"""
        try:
            res = accelerate.apply_steam_cell(accelerate.ACCEL.steam_region)
        except Exception as exc:  # noqa: BLE001
            self.toast.emit("应用区服失败：" + str(exc), "error")
            return ""
        res = res if isinstance(res, dict) else {}
        msg = str(res.get("message") or "")
        if res.get("ok"):
            self.toast.emit(msg, "success")
        else:
            self.toast.emit(msg or "应用区服失败", "warn")
        self.toolboxChanged.emit()
        return msg

    def _probe_accel_async(self) -> None:
        if getattr(self, "_steam_probing", False):
            self.toast.emit("线路探测进行中，请稍候", "info")
            return
        self._steam_probing = True
        self.toolboxChanged.emit()

        def worker() -> None:
            try:
                info = accelerate.ACCEL.state(refresh_steam=True, allow_network=True)
            except Exception as exc:  # noqa: BLE001
                info = {"status": "线路探测失败：" + str(exc),
                        "steamRoute": {"message": "线路探测失败：" + str(exc)}}
            self.accelReady.emit(info)

        threading.Thread(target=worker, daemon=True).start()

    def _on_accel_ready(self, payload) -> None:
        self._steam_probing = False
        self._accel_state = payload if isinstance(payload, dict) else {}
        self.toolboxChanged.emit()

    @Slot(result="QVariantMap")
    def accelState(self):
        if not getattr(self, "_accel_state", None):
            try:
                self._accel_state = accelerate.ACCEL.state(refresh_steam=False, allow_network=False)
            except Exception:
                self._accel_state = {}
        return dict(getattr(self, "_accel_state", None) or {})

    @Slot(result=bool)
    def setCurseMirror(self, enabled: bool) -> bool:
        """切换 CurseForge 走国内镜像 / 官方站。"""
        self._config.set("curseforge_mirror", bool(enabled))
        self._config.save()
        if self._cf_client is not None:
            try:
                self._cf_client.close()
            except Exception:  # noqa: BLE001
                pass
            self._cf_client = None
        self.modSourceChanged.emit()
        self.toast.emit("CurseForge 已切换为" + ("国内镜像" if enabled else "官方站"), "info")
        return bool(enabled)

    @Property(bool, notify=modSourceChanged)
    def curseMirror(self) -> bool:
        return bool(self._config.get("curseforge_mirror", True))

    # ------------------------------------------------------------- 联机
    @Slot()
    def installP2P(self) -> None:
        if self._busy:
            self.toast.emit("已有任务在进行中", "warn")
            return
        self._set_state(status="准备获取联机组件", progress=0.02, busy=True)
        self._bg(self._do_install_p2p)

    def _do_install_p2p(self) -> None:
        def on_progress(stage: str, done: int, total: int) -> None:
            self._set_state(status=f"{stage}  {done // 1048576}MB / {max(total, 1) // 1048576}MB",
                            progress=(done / total) if total else 0.2, busy=True)

        try:
            p2p.install(on_progress)
            self.toast.emit("联机组件已就绪", "success")
            self._set_state(status="联机组件已就绪", progress=1.0, busy=False)
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"组件获取失败：{exc}", "error")
            self._set_state(status="组件获取失败", progress=0.0, busy=False)

    @Slot(str, str, str)
    @Slot(str, str, str, int, str)
    @Slot(str, str, str, int, str, str)
    def startTunnel(self, room: str, secret: str = "", peers: str = "",
                    port: int = 25565, backend: str = "", role: str = "host") -> None:
        kind = (backend or self._tunnel_backend or "p2p").strip()
        if kind not in p2p.BACKENDS:
            self.toast.emit("未知的联机方式", "warn")
            return
        if self._tunnel.running or self._lan_active:
            self.toast.emit("联机已在运行", "warn")
            return
        self._tunnel_role = "join" if (role or "").strip().lower() == "join" else "host"
        try:
            self._tunnel_port = int(port) if int(port) > 0 else p2p.room_default_port()
        except (TypeError, ValueError):
            self._tunnel_port = p2p.room_default_port()
        self._tunnel_backend = kind
        self._tunnel_room = (room or "").strip()
        self._tunnel_log = []

        def on_line(line: str, level: str) -> None:
            self._tunnel_log.append(line)
            if len(self._tunnel_log) > 200:
                del self._tunnel_log[:80]
            self.tunnelChanged.emit()

        # 局域网直连：
        #   房主 = 只要游戏端口 + 本机局域网地址
        #   加入 = 直接使用房主给的地址（对端节点里填的 IP:端口）
        if kind == "lan":
            if not self._tunnel_room:
                self._tunnel_room = "局域网房间"
            host_ip = (peers.split(",")[0].strip() if peers else "")
            if self._tunnel_role == "join":
                if not host_ip:
                    self.toast.emit("加入房间需要填写房主的地址，如 192.168.0.106:25565", "warn")
                    return
                if ":" in host_ip:
                    try:
                        self._tunnel_port = int(host_ip.rsplit(":", 1)[1])
                    except (TypeError, ValueError):
                        pass
                    host_ip = host_ip.rsplit(":", 1)[0]
                self._tunnel_join_ip = host_ip
                self._lan_active = True
                self._tunnel_log.append(
                    f"[Sprout] 加入局域网房间：在游戏内「多人游戏 → 直接连接」输入 {host_ip}:{self._tunnel_port}"
                )
                self.tunnelChanged.emit()
                self.toast.emit("已准备加入房间，请在游戏内输入该地址", "success")
                return
            self._lan_active = True
            self._tunnel_log.append(
                f"[Sprout] 局域网直连：本机地址 {p2p.local_ipv4()}:{self._tunnel_port}，"
                "朋友在「多人游戏 → 直接连接」输入该地址即可"
            )
            self.tunnelChanged.emit()
            self.toast.emit("局域网地址已生成", "success")
            return

        if not self._tunnel_room:
            self.toast.emit("请填写房间名", "warn")
            return
        if not p2p.is_installed() and not (kind == "terracotta" and p2p.terracotta_available()):
            self.toast.emit("请先获取联机组件", "warn")
            return
        try:
            self._tunnel.start(self._tunnel_room, secret, peers, on_line, backend=kind)
            if self._tunnel_role == "join":
                tip = f"已加入 {p2p.backend_label(kind)}房间"
            else:
                tip = f"{p2p.backend_label(kind)}房间已创建"
            if kind == "terracotta":
                tip += "（房间名与密钥需与陶瓦联机客户端一致）"
            self.toast.emit(tip, "success")
            if self._tunnel_role == "join":
                self._tunnel_log.append(
                    f"[Sprout] 已作为成员加入房间 {self._tunnel_room}；等房主在游戏内「对局域网开放」后，"
                    "用房主给出的虚拟局域网地址:端口直连"
                )
            else:
                self._tunnel_log.append(
                    f"[Sprout] 房间 {self._tunnel_room}，游戏端口 {self._tunnel_port}；"
                    "进入游戏后请「对局域网开放」并使用该端口"
                )
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"启动失败：{exc}", "error")
        self.tunnelChanged.emit()

    @Slot(str)
    def setTunnelBackend(self, kind: str) -> None:
        if kind not in p2p.BACKENDS:
            return
        self._tunnel_backend = kind
        self.tunnelBackendChanged.emit()
        self.tunnelChanged.emit()

    @Slot(int)
    def setTunnelPort(self, port: int) -> None:
        try:
            value = int(port)
        except (TypeError, ValueError):
            return
        if 1 <= value <= 65535:
            self._tunnel_port = value
            self.tunnelChanged.emit()

    @Slot()
    def stopTunnel(self) -> None:
        self._tunnel.stop()
        self._lan_active = False
        self._tunnel_join_ip = ""
        self.tunnelChanged.emit()
        self.toast.emit("联机已停止", "info")

    # ------------------------------------------------------------- 诊断
    @Slot()
    def runDiagnose(self) -> None:
        if self._diagnosing:
            return
        self._diagnosing = True
        self.diagnoseChanged.emit()
        self._bg(self._do_diagnose)

    def _do_diagnose(self) -> None:
        mc = Path(self.mcDir)
        vid = self._featured.get("id", "")
        data = None
        if vid:
            try:
                data = meta.load_version(mc, vid, self._manifest_or_fetch())
            except Exception:  # noqa: BLE001
                data = None

        def on_progress(stage: str, done: int, total: int) -> None:
            self._set_state(status=stage, progress=(done / total) if total else 0.2, busy=True)

        result = diag_core.run(
            mc, vid, data, self.memoryMb, self.mirror,
            log_path=paths.logs_dir() / "latest.log", on_progress=on_progress,
        )
        self._diag_items = result["items"]
        self._diag_summary = result["summary"]
        report = paths.logs_dir() / f"diagnose-{time.strftime('%Y%m%d-%H%M%S')}.md"
        try:
            report.write_text(result["report"], encoding="utf-8")
            self._diag_report = str(report)
        except OSError:
            self._diag_report = ""
        self._diagnosing = False
        self._set_state(status=result["summary"], progress=1.0, busy=False)
        self.diagnoseChanged.emit()

    # ------------------------------------------------------------- 更新
    def _set_update_stage(self, stage: str = "", message: str = "", progress: float | None = None) -> None:
        self._update_stage = stage
        self._update_message = message
        if progress is not None:
            self._update_progress = float(max(0.0, min(1.0, progress)))
        self.updateChanged.emit()

    @Slot()
    def autoCheckUpdate(self) -> None:
        """启动时静默检查：只在新版本出现时弹窗，任何失败都不打扰用户。"""
        if self._update_stage:
            return  # 用户已经在处理更新，别再抢弹窗

        def work() -> None:
            try:
                info = updater.check(self.updateRepo)
            except Exception:  # noqa: BLE001
                return
            self._update = info
            if not info.get("newer"):
                self.updateChanged.emit()
                return
            skipped = str(self._config.get("skip_version") or "").strip()
            if skipped and skipped == str(info.get("version") or ""):
                self.updateChanged.emit()
                return
            self._set_update_stage("available", f"发现新版本 {info.get('version')}", 0.0)

        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def checkUpdate(self) -> None:
        def work() -> None:
            try:
                info = updater.check(self.updateRepo)
            except Exception as exc:  # noqa: BLE001
                self.toast.emit(f"检查更新失败：{exc}", "error")
                return
            self._update = info
            self.updateChanged.emit()
            if info.get("newer"):
                self._set_update_stage("available", f"发现新版本 {info.get('version')}", 0.0)
            else:
                self.toast.emit(f"已是最新版本（{updater.APP_VERSION}）", "success")

        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def downloadUpdate(self) -> None:
        if self._update_stage in ("downloading", "ready", "installing"):
            return  # 正在忙，别起第二个下载线程
        if not self._update.get("asset_url"):
            self.toast.emit("该发行版没有可下载的安装包", "warn")
            return
        self._set_update_stage("downloading", "准备下载安装包…", 0.0)

        def work() -> None:
            def on_progress(stage: str, done: int, total: int) -> None:
                pct = (done / total) if total else 0.0
                if pct > 1.0:
                    pct = 1.0
                if total:
                    text = (
                        f"{stage} {done / 1048576.0:.1f} / {total / 1048576.0:.1f} MB"
                        f"（{pct * 100:.0f}%）"
                    )
                else:
                    text = f"{stage}…"
                self._set_update_stage("downloading", text, pct)

            try:
                path = updater.download(self._update, on_progress)
                updater.cleanup_downloads(keep=path.name)
                self._update_path = str(path)
                try:
                    mb = path.stat().st_size / 1048576.0
                except OSError:
                    mb = 0.0
                self._set_update_stage("ready", f"{path.name}（{mb:.1f} MB）已下载完成", 1.0)
            except Exception as exc:  # noqa: BLE001
                self._set_update_stage("error", f"下载失败：{exc}", 0.0)

        threading.Thread(target=work, daemon=True).start()

    @Slot()
    def installUpdate(self) -> None:
        """打开安装程序；启动器随后退出，否则运行中的 exe 被锁装不上。"""
        path = self._update_path
        if not path:
            self.toast.emit("还没有下载安装包", "warn")
            return
        try:
            updater.launch_installer(Path(path))
        except Exception as exc:  # noqa: BLE001
            self.toast.emit(f"无法启动安装程序：{exc}", "error")
            self._set_update_stage("error", f"无法启动安装程序：{exc}", 0.0)
            return
        self._set_update_stage("installing", "安装程序已打开，启动器将退出以便覆盖旧文件", 1.0)
        # 留足时间让安装程序起来并接管，再退启动器（运行中的 exe 被锁会挡安装）
        QTimer.singleShot(2500, QCoreApplication.quit)

    @Slot()
    def dismissUpdate(self) -> None:
        self._set_update_stage("")

    @Slot()
    def skipUpdateVersion(self) -> None:
        """跳过的版本不再自动打扰，下次手动检查仍会提示。"""
        ver = str(self._update.get("version") or "").strip()
        if ver:
            self._config.set("skip_version", ver)
            self._config.save()
            self.toast.emit(f"已忽略 {ver}，需要时可在关于页手动检查", "info")
        self._set_update_stage("")

    @Slot()
    def openUpdateDownloads(self) -> None:
        self.openPath(str(updater.downloads_dir()))

    @Slot(result=str)
    def updateNotes(self) -> str:
        notes = str(self._update.get("notes") or "").strip()
        return notes if notes else "该版本未填写更新说明。"

    # ------------------------------------------------------------- 设置相关
    @Slot(str)
    def setTheme(self, name: str) -> None:
        self._theme.set_theme(name)
        self._config.set("theme", self._theme.name)
        self._config.save()

    @Slot(str)
    def setMirror(self, mirror: str) -> None:
        self._config.set("mirror", mirror)
        self._config.save()
        self._manifest = None
        self.stateChanged.emit()

    @Slot(int)
    def setMemory(self, mb: int) -> None:
        self._config.set("memory_mb", int(mb))
        self._config.save()
        self.stateChanged.emit()

    @Slot(str)
    def setMcDir(self, path: str) -> None:
        self._config.set("mc_dir", path)
        self._config.save()
        self.stateChanged.emit()

    @Slot(str)
    def setJvmArgs(self, args: str) -> None:
        self._config.set("jvm_args", args)
        self._config.save()
        self.stateChanged.emit()

    @Slot(str)
    def setMsClientId(self, value: str) -> None:
        self._config.set("ms_client_id", value.strip())
        self._config.save()
        self.stateChanged.emit()

    # ------------------------------------------------------------- 游戏目录
    @Property("QVariantList", notify=stateChanged)
    def extraDirs(self) -> list[str]:
        raw = self._config.get("extra_dirs")
        return [str(x) for x in raw] if isinstance(raw, list) else []

    @Property("QVariantList", notify=stateChanged)
    def gameRoots(self) -> list[dict]:
        """当前参与扫描的所有游戏根目录，供设置页展示。"""
        current = str(Path(self.mcDir)).lower()
        manual = {str(x) for x in self.extraDirs}
        out: list[dict] = []
        for p in self._mc_roots():
            versions = 0
            vroot = p / "versions"
            if vroot.is_dir():
                try:
                    versions = sum(
                        1 for d in vroot.iterdir()
                        if d.is_dir() and (d / f"{d.name}.json").exists()
                    )
                except OSError:
                    versions = 0
            out.append({
                "path": str(p),
                "exists": p.exists(),
                "versions": versions,
                "current": str(p).lower() == current,
                "manual": str(p) in manual,
            })
        return out

    def _normalize_root(self, path: str) -> Path | None:
        text = (path or "").strip().strip('"')
        if not text:
            return None
        p = Path(text)
        # 允许用户直接选 .minecraft 的上级目录（如 D:\Games），自动补上 .minecraft
        if not (p / "versions").is_dir() and (p / ".minecraft" / "versions").is_dir():
            p = p / ".minecraft"
        if not p.is_dir():
            return None
        return p

    @Slot(str, result=bool)
    def addGameDir(self, path: str) -> bool:
        p = self._normalize_root(path)
        if p is None:
            self.toast.emit("目录不存在，或里面没有 versions 文件夹", "error")
            return False
        if not (p / "versions").is_dir():
            # 空目录允许登记（装好版本后生效），非空但无 versions 视为选错目录
            try:
                empty = not any(p.iterdir())
            except OSError:
                empty = False
            if not empty:
                self.toast.emit("该目录不像 Minecraft 游戏目录（缺少 versions 文件夹）", "error")
                return False
        dirs = self.extraDirs
        key = str(p)
        if key in dirs:
            self.toast.emit("该目录已在列表中", "info")
            return True
        dirs.append(key)
        self._config.set("extra_dirs", dirs)
        self._config.save()
        self.refreshLocal()
        self.stateChanged.emit()
        self.toast.emit(f"已添加游戏目录：{key}", "success")
        return True

    @Slot(result=str)
    def browseGameDir(self) -> str:
        start = self.mcDir or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(None, "选择游戏目录（含 versions 的 .minecraft）", start)
        if chosen:
            self.addGameDir(chosen)
        return chosen or ""

    @Slot()
    def autoDetectGameDirs(self) -> None:
        """一键把本机探测到的所有 .minecraft 目录加入扫描列表。"""
        dirs = self.extraDirs
        added = 0
        try:
            cands = list(paths.minecraft_candidates())
        except Exception:  # noqa: BLE001
            cands = []
        for cand in cands:
            try:
                if not (cand / "versions").is_dir():
                    continue
                key = str(cand)
                if key in dirs or str(cand).lower() == str(Path(self.mcDir)).lower():
                    continue
                dirs.append(key)
                added += 1
            except OSError:
                continue
        self._config.set("extra_dirs", dirs)
        self._config.save()
        self.refreshLocal()
        self.stateChanged.emit()
        if added:
            self.toast.emit(f"已自动添加 {added} 个游戏目录", "success")
        else:
            self.toast.emit("没有发现新的游戏目录", "info")

    @Slot(str)
    def removeGameDir(self, path: str) -> None:
        dirs = [d for d in self.extraDirs if d != path]
        self._config.set("extra_dirs", dirs)
        self._config.save()
        self.refreshLocal()
        self.stateChanged.emit()
        self.toast.emit("已从列表移除该目录（文件不受影响）", "info")

    @Slot(str)
    def setUpdateRepo(self, value: str) -> None:
        self._config.set("update_repo", value.strip())
        self._config.save()
        self.stateChanged.emit()

    @Slot(result="QVariantList")
    def candidateDirs(self) -> list[dict]:
        out = []
        for p in paths.minecraft_candidates():
            out.append({
                "path": str(p),
                "score": paths.score_minecraft_dir(p),
                "exists": p.exists(),
                "current": str(p).lower() == str(Path(self.mcDir)).lower(),
            })
        out.sort(key=lambda d: -d["score"])
        return out

    @Slot(str)
    def openPath(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            self.toast.emit("路径不存在", "warn")
            return
        target = p if p.is_dir() else p.parent
        subprocess.Popen(["explorer", str(target)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    @Slot(result=str)
    def appDataDir(self) -> str:
        return str(paths.app_dir())

    @Slot(result=str)
    def modsPath(self) -> str:
        return str(self._target_game_dir() / "mods")

    @Slot(result=str)
    def logsPath(self) -> str:
        return str(paths.logs_dir())

    # ------------------------------------------------------------ 文件选择
    @Slot(str, str, result=str)
    def pickFile(self, title: str, patterns: str) -> str:
        name_filter = patterns or "所有文件 (*)"
        path, _ = QFileDialog.getOpenFileName(None, title or "选择文件", "", name_filter)
        return path or ""

    @Slot(str, str, str, result=str)
    def pickSaveFile(self, title: str, patterns: str, default_name: str) -> str:
        name_filter = patterns or "所有文件 (*)"
        path, _ = QFileDialog.getSaveFileName(None, title or "保存文件", default_name or "", name_filter)
        return path or ""
