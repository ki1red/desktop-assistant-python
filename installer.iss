#define MyAppName "LocalAssistant"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "LocalAssistant"
#define MyAppExeName "LocalAssistant.exe"

[Setup]
AppId={{7F8B8F3B-7A2B-4D26-9A9F-LOCALASSISTANT}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}

OutputDir=installer_output
OutputBaseFilename=LocalAssistantSetup

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

PrivilegesRequired=lowest
DisableProgramGroupPage=yes
DisableDirPage=no

UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

CloseApplications=yes
RestartApplications=no

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные значки:"; Flags: unchecked

[Files]
Source: "dist\LocalAssistant\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LocalAssistant"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Удалить LocalAssistant"; Filename: "{uninstallexe}"
Name: "{autodesktop}\LocalAssistant"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить LocalAssistant"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\*.log"