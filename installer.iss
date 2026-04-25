#define MyAppName "LocalAssistant"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Nikita Druzhinin"
#define MyAppExeName "LocalAssistant.exe"

[Setup]
AppId={{5F7F0A31-6E3B-4F3D-9C65-6F2C8C8C0A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=LocalAssistant_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать значок на рабочем столе"; GroupDescription: "Дополнительные значки:"

[Files]
Source: "dist\LocalAssistant\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\LocalAssistant\data"
Type: filesandordirs; Name: "{localappdata}\LocalAssistant\temp"
Type: filesandordirs; Name: "{localappdata}\LocalAssistant\logs"
Type: files; Name: "{localappdata}\LocalAssistant\config\settings.json"
Type: dirifempty; Name: "{localappdata}\LocalAssistant\config"
Type: dirifempty; Name: "{localappdata}\LocalAssistant"