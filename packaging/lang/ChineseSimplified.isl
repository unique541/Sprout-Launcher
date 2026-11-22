; Inno Setup 简体中文覆盖（仅覆盖常用界面文案；未覆盖项由 Default.isl 英文兜底）
; 由 packaging\sprout_setup.iss 通过 MessagesFile: "compiler:Default.isl,lang\ChineseSimplified.isl" 加载

[LangOptions]
LanguageName=<7B80><4F53><4E2D><6587>
LanguageID=$0804
LanguageCodePage=936

[Messages]
SetupAppTitle=安装
SetupWindowTitle=%1 安装程序
UninstallAppTitle=卸载
UninstallAppFullTitle=%1 卸载
InformationTitle=提示
ConfirmTitle=确认
ErrorTitle=错误
ButtonNext=下一步(&N) >
ButtonBack=< 上一步(&B)
ButtonInstall=安装(&I)
ButtonCancel=取消
ButtonFinish=完成(&F)
ButtonBrowse=浏览(&R)...
ButtonYes=是(&Y)
ButtonNo=否(&N)
ButtonOK=确定
WelcomeLabel1=欢迎使用 [name] 安装向导
WelcomeLabel2=这将在此计算机上安装 [name/ver]。%n%n建议关闭其它正在运行的程序后再继续。
WizardSelectDir=选择安装位置
SelectDirDesc=[name] 将安装到下面的文件夹中。
SelectDirLabel3=安装程序会将 [name] 安装到以下文件夹。
SelectDirBrowseLabel=点击「下一步」继续；如需更改安装位置，请点击「浏览」。
WizardSelectTasks=选择附加任务
WizardReady=准备安装
WizardPreparing=正在准备安装
WizardInstalling=正在安装
ReadyLabel1=安装程序现在已准备好在您的计算机上安装 [name]。
ReadyLabel2a=点击「安装」开始安装，或点击「上一步」检查并修改设置。
ReadyLabel2b=点击「安装」开始安装。
PreparingDesc=安装程序正准备开始安装 [name]。
InstallingLabel=正在安装 [name]，请稍候...
FinishedHeadingLabel=正在完成 [name] 安装向导
FinishedLabel=[name] 已安装到您的计算机。%n%n点击「完成」退出安装程序。
FinishedRestartLabel=要完成 [name] 的安装，必须重启计算机。是否现在重启？
FinishedRestartMessage=要完成 [name] 的安装，必须重启计算机。%n%n是否现在重启？
ClickFinish=点击「完成」退出安装程序。
ConfirmUninstall=确定要完全删除 %1 及其所有组件吗？
UninstallStatusLabel=正在从您的计算机删除 %1，请稍候。
UninstalledAll=%1 已成功从您的计算机删除。
UninstalledMost=%1 卸载完成。%n%n部分文件无法删除，可手动清理。
UninstalledAndNeedsRestart=要完成 %1 的卸载，必须重启计算机。%n%n是否现在重启？
StatusCreateDirs=正在创建文件夹...
StatusExtractFiles=正在解压文件...
StatusCreateRegistryEntries=正在写入注册表项...
StatusRollback=正在回滚更改...
StatusRunProgram=正在完成安装...
StatusUninstalling=正在卸载 %1...
StatusClosingApplications=正在关闭应用程序...
ExitSetupTitle=退出安装
ExitSetupMessage=安装尚未完成。如果现在退出，%1 将不会被安装。%n%n可以稍后再次运行本安装程序完成安装。%n%n确定要退出吗？
SetupAppRunningError=检测到 %1 正在运行。请先关闭它，然后点击「确定」继续，或点击「取消」退出。
UninstallAppRunningError=检测到 %1 正在运行。请先关闭它，然后点击「确定」继续，或点击「取消」退出。

[CustomMessages]
CreateDesktopIcon=创建桌面快捷方式
AdditionalIcons=附加快捷方式：
ProgramOnTheWeb=访问 %1 网站
UninstallProgram=卸载 %1
LaunchProgram=运行 %1
