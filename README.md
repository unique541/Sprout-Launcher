# Sprout Launcher

Sprout Launcher 是一款面向 Windows 的 Minecraft Java 版桌面启动器，基于 **PySide6 + QML** 构建，主打开箱即用与界面一致性。

当前版本：**0.3.2**

## 功能

- **微软账号登录**：OAuth 设备码流程，登录前校验正版游戏所有权；支持多账号保存与切换、皮肤查看与更换。
- **版本管理**：原版与 Forge / Fabric / NeoForge 加载器安装、组件与 Java 运行时下载，启动参数可在设置中调整。
- **实例与存档**：多游戏目录扫描与手动添加，实例隔离；存档列表、备份与导入导出。
- **Mod 管理**：接入 Modrinth 与 CurseForge，支持按加载器 / 游戏版本筛选、搜索、一键安装与启停。
- **联机**：内置 P2P 联机通道，房主开房、玩家凭房间信息加入。
- **诊断工具**：运行环境自检、日志查看、控制台输出。
- **自动更新**：从 GitHub Releases 检查新版本，对话框内显示下载进度（按字节实时刷新）、下载完成后拉起安装程序；安装包安装结束后自动删除自身。
- **下载加速**：多线程分段下载，加速镜像可切换。

## 安装

1. 到 [Releases](https://github.com/unique541/Sprout-Launcher/releases) 下载 `SproutLauncher-Setup-<版本>.exe`。
2. 运行安装程序，按向导完成安装（默认安装到 `%LOCALAPPDATA%\Programs\Sprout Launcher`）。
3. 用户数据（配置、实例、Java 运行时、下载缓存）位于 `%APPDATA%\Sprout`，卸载时默认保留。

> 安装包内分发的是 **onedir** 形态（`SproutLauncher.exe` + `_internal`），启动时无需把运行时解压到 `%TEMP%`，启动更快，也不会出现 onefile 自解压被打断导致的 `Failed to load Python DLL ...python314.dll` 报错。

## 从源码运行

```powershell
pip install -r requirements.txt
python -m sprout.main
```

依赖：Python 3.12+（开发环境使用 3.14）、PySide6、httpx 等，详见 `requirements.txt`。

## 构建

打包说明见 [`docs/BUILD_打包说明.md`](docs/BUILD_打包说明.md)，要点：

```powershell
# 1) onedir 形态（安装包使用）
$env:SPROUT_ONEFILE="0"; $env:SPROUT_CONSOLE="0"
python -m PyInstaller --noconfirm --clean packaging\sprout_launcher.spec --distpath C:\sproutbuild\onedir --workpath C:\sproutbuild\work_onedir

# 2) 生成安装包
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyDist="C:\sproutbuild\onedir" /DMyAssets="<项目>\assets" packaging\sprout_setup.iss
```

版本号需要同步的位置：`sprout/core/updater.py`（`APP_VERSION`）、`sprout/core/__init__.py`、`sprout/core/launch.py`、`sprout/core/accelerate.py`、`packaging/sprout_setup.iss`（`AppVersion`）、`packaging/version_info.txt`。

## 目录结构

```
sprout/
  main.py            入口
  config.py          配置读写
  paths.py           路径约定
  core/              账号、版本、加载器、Java、实例、存档、Mod、联机、下载、更新
  services/          Modrinth / CurseForge 接口
  ui/                QML 桥接层（bridge）、数据模型、主题
  qml/               Main.qml 与 components / pages
packaging/           PyInstaller spec、Inno Setup 脚本、版本资源
assets/              图标与图片
docs/                构建说明与界面截图
```

## 说明

- 本项目为个人开发者自用与分享性质，与 Mojang / Microsoft 无关联。
- 使用需自备正版 Minecraft 账号。
