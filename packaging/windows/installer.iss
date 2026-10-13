; BingoPacker Windows 安装器（Inno Setup 6）
; 所有变量由 CI 通过 ISCC /D 传入，本文件保持纯 ASCII 以避免编码问题。

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\BingoPacker"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif
#ifndef OutputBaseFilename
  #define OutputBaseFilename "BingoPacker-setup"
#endif
#ifndef IconFile
  #define IconFile "..\..\assets\icons\logo_win.ico"
#endif

[Setup]
AppId={{8E1B7E4A-6C2F-4E7A-9C3D-3F5A7B9C1D2E}
AppName=BingoPacker
AppVersion={#AppVersion}
AppVerName=BingoPacker {#AppVersion}
AppPublisher=BidouMan
DefaultDirName={autopf}\BingoPacker
DefaultGroupName=BingoPacker
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
SetupIconFile={#IconFile}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\BingoPacker.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BingoPacker"; Filename: "{app}\BingoPacker.exe"
Name: "{group}\{cm:UninstallProgram,BingoPacker}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\BingoPacker"; Filename: "{app}\BingoPacker.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BingoPacker.exe"; Description: "{cm:LaunchProgram,BingoPacker}"; Flags: nowait postinstall skipifsilent
