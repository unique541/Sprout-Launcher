---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 3b8ddf290b7a1c33bf8fdf1e3c983246_34332b25df6b11f189bc525400248c00
    ReservedCode1: lEo/sWS2X8lfnGso8Td/rpPDiTs873kHO01M5JkYJilQz3Iezo3Xtjd8KsdCeVZBfLia/UTTH32Hp7Xk2mb/DoTEyNFGbadqXs/TCaB6MVXyhLoVWnw4VExV+NHRCgF5dTGCEygZjJmS9Cly9UZlqw9I1FO6ioygpRYgd3rSlR/cbf0KAQFIrttoiEs=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 3b8ddf290b7a1c33bf8fdf1e3c983246_34332b25df6b11f189bc525400248c00
    ReservedCode2: lEo/sWS2X8lfnGso8Td/rpPDiTs873kHO01M5JkYJilQz3Iezo3Xtjd8KsdCeVZBfLia/UTTH32Hp7Xk2mb/DoTEyNFGbadqXs/TCaB6MVXyhLoVWnw4VExV+NHRCgF5dTGCEygZjJmS9Cly9UZlqw9I1FO6ioygpRYgd3rSlR/cbf0KAQFIrttoiEs=
---

# Sprout Launcher 打包说明

## 产物

| 文件 | 说明 | 体积 |
| --- | --- | --- |
| `dist/SproutLauncher.exe` | PyInstaller 单文件可执行程序（windowed，含图标） | 160.4 MB |
| `packaging/sprout_launcher.spec` | 打包配置，onedir / onefile 共用 | — |
| `assets/sprout.ico` | 16~256 多尺寸图标（构建时注入 exe） | 23 KB |

## 构建方式

```powershell
$py  = "C:\Users\1107\AppData\Local\Programs\Python\Python314\python.exe"
$spec = "...\packaging\sprout_launcher.spec"

# 单文件（交付形态）
$env:SPROUT_ONEFILE = "1"; $env:SPROUT_CONSOLE = "0"
& $py -m PyInstaller --noconfirm --distpath C:\sproutbuild\dist --workpath C:\sproutbuild\work $spec

# 目录版（调试用，启动快，便于看运行库缺失）
$env:SPROUT_ONEFILE = "0"
& $py -m PyInstaller --noconfirm --distpath C:\sproutbuild\dist_onedir --workpath C:\sproutbuild\work $spec

# 控制台版（排查启动失败，能打印 QML 报错）
$env:SPROUT_CONSOLE = "1"
```

环境：Python 3.14.0 + PySide6 6.11.2 + httpx 0.28.1 + PyInstaller 6.20.0。

## 打包关键点（踩过的坑）

1. **QML 必须落两份**：源码运行时 `main.py` 用 `Path(__file__).parent / "qml" / "Main.qml"` 定位；PyInstaller 冻结后 `__file__` 指向 `_MEIPASS` 根目录，实际取 `<内部目录>/qml/Main.qml`。spec 中同时把 `sprout/qml` 映射到 `sprout/qml` 与 `qml` 两个目标，否则窗口根本出不来（exe 静默退出，返回码 1）。

2. **构建目录不能放在长路径下**：`LongPathsEnabled=0`，工程在 Marvis 工作区下的绝对路径本身已接近 260 字符，onedir 收集阶段 `_internal\PySide6\qml\Qt5Compat\GraphicalEffects\private\...dll` 会直接触发 `FileNotFoundError`。因此中间构建目录固定用 `C:\sproutbuild`，只把最终单文件 exe 复制回工程 `dist/`。

3. **QML 运行库由 PySide6 hook 自动收集**：`PySide6/qml` 下 QtQuick、QtQuick.Controls（含 Basic/Fusion/Material/Universal 等样式）会整包带入，spec 里额外声明的 `QtQuick/QtQml/QtCore` 只是兜底，不必手动裁剪。Qt 运行库统一位于 `_internal/PySide6/`，不在 `_internal` 根目录。

4. **样式固定 Basic**：`main.py` 已执行 `QQuickStyle.setStyle("Basic")`，与 QML 中自绘的 `background` 配合，避免 Qt 默认样式覆盖自定义外观。

## 验证结果

- 单文件启动：进程常驻，窗口标题 `Sprout Launcher`，尺寸 1180×760，与 QML 设定一致；
- 冷启动耗时约 25 秒（单文件需解压约 400 MB 运行库到临时目录），二次启动更快；
- 数据目录仍为 `%APPDATA%\Sprout`（配置、实例、缓存与源码运行共用，不受打包影响）。

## 本次构建（皮肤 / 工具箱 / 性能修复）

| 项目 | 结果 |
| --- | --- |
| 单文件 exe | `dist/SproutLauncher.exe`，168.5 MB，2026-11-22 12:12 |
| 安装程序 | `dist/SproutLauncher-Setup-0.1.0.exe`，168.8 MB，2026-11-22 12:15 |
| 冒烟验证 | 双击后窗口标题 `Sprout Launcher`，工作集约 250 MB，进程常驻无崩溃 |
| 语法自检 | `compileall sprout` 返回 0；`bridge` / `accelerate` / `skin` 导入正常 |
| QML 回归 | 无界面探针加载 Main.qml，settings / accounts / home 三页 navigate 成功，QML 警告 0 |

本次功能变更：账号页「设置皮肤」（classic / slim、官方同步、PNG 上传与预览）；设置页「工具箱」卡片（内存优化前后对比、GitHub 镜像加速、Steam 区服路由）。

性能修复：`bridge.installedList` 原先每次读取都遍历版本目录并多次读盘（实测单次 90~330 ms），首页有 5 处绑定导致切回首页卡顿；现改为按 `installedChanged` 失效的缓存，重复读取 0 ms，切页重建耗时降至约 16~20 ms。

## 本次构建（v0.2.0：加速修复 / CurseForge 镜像 / 模组源跳转）

| 项目 | 结果 |
| --- | --- |
| 版本号 | `APP_VERSION = 0.2.0`（`sprout/core/updater.py`、`core/__init__.py`、`core/launch.py`、`core/accelerate.py` UA、`packaging/sprout_setup.iss` 同步） |
| 单文件 exe | `dist/SproutLauncher.exe`，168.5 MB，2026-11-22 15:54 |
| 安装程序 | `dist/SproutLauncher-Setup-0.2.0.exe`，168.9 MB，2026-11-22 15:56 |
| 冒烟验证 | 双击后 7.5 秒窗口标题 `Sprout Launcher` 出现，进程常驻无崩溃 |
| 语法自检 | `compileall sprout` 返回 0；`from sprout.core.updater import APP_VERSION` 输出 `0.2.0` |

本次功能变更：

1. 加速器：`_tcp_probe` 按 443→80→27015 逐个探测，`steam_route` 并行探测（最多 6 线程）；修复读取 CDN 字段应为 `host`（原读 `hostname` 恒为空导致「加速已开启却显示未启用」）；探测改后台线程，`setSteam` 耗时降至 ~7 ms，消除开启加速卡顿；新增 `apply_steam_cell` 真实写入 Steam `config.vdf`（写前自动备份 `config.vdf.sprout.bak`，Steam 运行中拒绝写入）。
2. CurseForge 镜像：API 走 `mod.mcimirror.top/curseforge/v1`，CDN 走 `mod.mcimirror.top`，镜像模式无需 API Key；`mediafilez.forgecdn.net` 不做替换。
3. 模组详情页右上角按钮改为按模组源跳转：CurseForge 源显示「转到 CurseForge」并指向 `curseforge.com`，Modrinth 源显示「转到 Modrinth」；`bridge.modDetail` 新增 `source` 字段，CurseForge 链接由 `_cf_web_url()` 按项目类型生成。

## 本次构建（v0.3.0：自动更新）

| 项目 | 结果 |
| --- | --- |
| 版本号 | `APP_VERSION = 0.3.0`（`core/updater.py`、`core/__init__.py`、`core/launch.py`、`core/accelerate.py` UA、`packaging/sprout_setup.iss` 同步） |
| 更新仓库 | `unique541/Sprout-Launcher`（`core/updater.py` 的 `DEFAULT_REPO`，可在配置 `update_repo` 覆盖） |
| 单文件 exe | `dist/SproutLauncher.exe`，168.5 MB，2026-11-22 18:08 |
| 安装程序 | `dist/SproutLauncher-Setup-0.3.0.exe`，168.9 MB，2026-11-22 18:09 |
| 冒烟验证 | 双击后 9 秒窗口标题 `Sprout Launcher` 出现，进程常驻无崩溃；当前仓库最新版 0.2.0 低于本地 0.3.0，自动检查正确静默不弹窗 |
| 语法自检 | `compileall sprout` 返回 0 |
| 隔离验证 | 假配置目录下：发现新版 → `available`；跳过版本写入 `skip_version=9.9.9` 后再次自动检查静默；`cleanup_downloads` 只删旧 exe/zip、保留当前包；`launch_installer` 能拉起真实 exe |
| 安装包自删 | 复制 setup 到临时目录 → `/VERYSILENT /DIR=<临时目录>` 安装 → 安装完成 4 秒后 setup 被删除；随后 `unins000.exe /VERYSILENT` 卸载干净，目录清空、注册表卸载项移除 |

### 自动更新流程

1. `sprout/main.py` 在窗口起来 3 秒后调用 `bridge.autoCheckUpdate()`，后台线程请求 `api.github.com/repos/<repo>/releases/latest`（先直连，失败再走加速镜像一次）。
2. 远端 tag 版本 > 本地 `APP_VERSION` 且未被 `skip_version` 跳过时，`_set_update_stage("available")`，QML 弹出 `components/UpdateDialog.qml`：显示「当前版本 → 最新版本」、发行版标题、发布时间与更新说明正文（`clean_notes()` 已剥 HTML/图片/链接并截断）。
3. 用户点「立即更新」→ `downloadUpdate()`，后台 `updater.download()` 下载到 `%APPDATA%\Sprout\downloads`，进度条实时刷新；下载完校验文件大小，并清理旧的安装包（只保留本次下载的这个）。
4. 下载完成阶段按钮变为「安装并退出」→ `installUpdate()` 用 `subprocess.Popen` 打开安装包，随后 2.5 秒退出启动器，避免运行中的 exe 被锁导致覆盖失败。
5. 安装包自删由 `packaging/sprout_setup.iss` 的 `[Run]` 段完成：`cmd /c ping -n 5 127.0.0.1 >nul & del /f /q "{srcexe}"`，即安装结束后延时 4 秒删除本次运行的 setup.exe（`{srcexe}` 就是 `%APPDATA%\Sprout\downloads` 里那个包）。
6. 用户也可在「关于」页手动「检查更新」；弹窗里「跳过此版本」会把该版本写入配置 `skip_version`，以后自动检查不再打扰，手动检查仍会提示。

### 发布新版本的操作顺序

1. 改版本号五处：`sprout/core/updater.py` 的 `APP_VERSION`、`core/__init__.py` 的 `__version__`、`core/launch.py` 的 `launcher_version`、`core/accelerate.py` 的 UA、`packaging/sprout_setup.iss` 的 `#define AppVersion`。
2. 按上文命令重新打包，得到 `SproutLauncher.exe` 与 `SproutLauncher-Setup-x.y.z.exe`。
3. 在 GitHub `unique541/Sprout-Launcher` 新建 Release，tag 用 `SproutLauncherx.y.z`（`tag_version()` 会把前缀剥掉再比版本），把 setup.exe 作为附件上传，更新说明写在 Release 正文里（弹窗正文就取这个字段）。
4. 老版本启动后即会自动检测到该 Release 并走上面的更新流程。

## 本次构建（v0.3.1：移除自动重启 / 进程守护兜底 / exe 版本资源）

| 项目 | 结果 |
| --- | --- |
| 版本号 | `APP_VERSION = 0.3.1`（`core/updater.py`、`core/__init__.py`、`core/launch.py`、`core/accelerate.py` UA、`packaging/sprout_setup.iss` 同步） |
| 单文件 exe | `dist/SproutLauncher.exe`，160.7 MB，2026-11-22 18:54，文件版本 `0.3.1.0` |
| 安装程序 | `dist/SproutLauncher-Setup-0.3.1.exe`，161 MB，2026-11-22 18:56（ISCC 编译 23.5 s，exit=0） |
| 冒烟验证 | 双击后 30 秒内窗口标题 `Sprout Launcher` 出现，进程常驻无崩溃 |
| 安装闭环 | `/VERYSILENT /DIR=<临时目录>` 安装 exit=0，注册表卸载项版本 0.3.1；`unins000.exe /VERYSILENT` 卸载 exit=0，目录删除、注册表项清零 |
| 语法自检 | `compileall sprout` 返回 0 |

本次功能变更：

1. 移除「游戏退出后自动重启」整套机制：`bridge.py` 删除 `autoRelaunch` 属性、`setAutoRelaunch` 槽及 `_relaunch_kind/arg/override/tries/timer` 等全部字段与 `_relaunch_game()`；`SettingsPage.qml` 删除对应设置项；`config.py` 删除 `auto_relaunch` 默认值。
2. 进程守护兜底：`bridge.py` 新增 `_watch_timer`（`QTimer`，1500 ms，timeout → `_check_game_alive()`），用于在 `finished` 信号丢失时回收运行状态。
3. `_on_game_finished` 加幂等保护（`_running` / `_runningVersion` / `_game_instance` 全为假时直接 return）并重置 `_game_started_at`；`killGame()` 改用 `proc.kill()` 后立即 `_force_kill_if_alive(pid)`，2.5 秒后再补一轮。
4. 首页启动按钮交互：`SproutButton.qml` 新增 `hovered` 只读属性；`HomePage.qml` 按钮在运行中显示「游戏运行中」，悬停变「结束游戏」，点击调 `killGame()`；未运行时按是否已安装显示「启动游戏 / 安装并启动」。
5. exe 版本资源：新增 `packaging/version_info.txt`（`filevers/prodvers = 0.3.1.0`、产品名、版权、原始文件名），spec 两处 `EXE()` 均追加 `version=str(VERSION_FILE) if VERSION_FILE.exists() else None`，此后「属性 → 详细信息」可读到版本号。

### 版本号同步位置（0.3.1 起共 6 处）

`sprout/core/updater.py`（`APP_VERSION`）、`sprout/core/__init__.py`（`__version__`）、`sprout/core/launch.py`（`launcher_version`）、`sprout/core/accelerate.py`（User-Agent）、`packaging/sprout_setup.iss`（`#define AppVersion`）、`packaging/version_info.txt`（`filevers` / `prodvers` / `FileVersion` / `ProductVersion`）。

## 后续可做

- 体积优化：剔除未使用的 Controls 样式目录（Imagine/Material/Universal/Fusion/Windows、Qt5Compat），预计可减 10~20 MB；
- `packaging/version_info.txt` 的版本号目前需手工同步，可改为构建时从 `sprout/core/updater.py` 的 `APP_VERSION` 自动生成；
- 增量更新：当前为整包替换（约 169 MB），后续可只下发变动的资源包。
*（内容由AI生成，仅供参考）*
