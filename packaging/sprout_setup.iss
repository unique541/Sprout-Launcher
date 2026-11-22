; Inno Setup 6 脚本：Sprout Launcher 安装程序
; 编译：ISCC.exe /DMyDist="<dist目录>" /DMyAssets="<assets目录>" packaging\sprout_setup.iss
; 产物：<dist>\SproutLauncher-Setup-<版本>.exe

#define AppName "Sprout Launcher"
#define AppVersion "0.3.2"
#define AppExe "SproutLauncher.exe"
#define AppPublisher "Sprout"
#define AppId "{{8D2F41B7-6E3A-4C58-9A21-5B7C0D93E614}"

#ifndef MyDist
  #define MyDist "..\dist"
#endif
#ifndef MyAssets
  #define MyAssets "..\assets"
#endif

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppComments=Minecraft 启动器（版本管理 / 实例 / 存档 / Mod / 联机）
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\{#AppExe}
OutputDir={#MyDist}
OutputBaseFilename=SproutLauncher-Setup-{#AppVersion}
SetupIconFile={#MyAssets}\sprout.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
AllowNoIcons=yes
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} 安装程序
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl,lang\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 安装包分发 onedir 形态（exe + _internal 目录）：程序启动不再把上百 MB 运行时自解压到 %TEMP%，
; 彻底规避 onefile 解压被打断时报 "Failed to load Python DLL ...python314.dll" 的问题，启动也更快。
Source: "{#MyDist}\SproutLauncher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
; 安装结束后删掉本次运行的安装包（自动更新从 %APPDATA%\Sprout\downloads 拉起的那个），先 ping 延时约 5 秒等 setup 自身释放文件句柄
Filename: "{cmd}"; Parameters: "/c ping -n 6 127.0.0.1 >nul & del /f /q ""{srcexe}"""; Flags: runhidden nowait

[UninstallDelete]
; 安装目录内运行期可能产生的残留（日志、临时文件）随卸载清掉；用户数据在 %APPDATA%\Sprout，另行询问
Type: filesandordirs; Name: "{app}\logs"
; onedir 形态的运行时目录，卸载时整目录清掉，避免残留 DLL
Type: filesandordirs; Name: "{app}\_internal"

[Code]
const
  DataDirLeaf = '\Sprout';

{ 卸载后询问是否连用户数据一起删：默认保留，避免误删配置、实例和下载好的 Java 运行时 }
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}') + DataDirLeaf;
    { 静默卸载不动用户数据，避免脚本化卸载误删配置与实例 }
    if DirExists(DataDir) and (not UninstallSilent) then
    begin
      if MsgBox('是否一并删除 Sprout 的用户数据（配置、实例、Java 运行时、日志）？' + #13#10#13#10
                + DataDir + #13#10#13#10
                + '选「是」彻底清理；选「否」保留，重新安装后可直接继续使用。',
                mbConfirmation, MB_YESNO) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
