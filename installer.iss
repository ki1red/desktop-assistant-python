#define MyAppName "LocalAssistant"
#define MyAppVersion "0.1.1"
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

[Code]
var
  DeleteUserData: Boolean;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  DeleteUserData := False;

  ResultCode := MsgBox(
    'Удалить пользовательские данные LocalAssistant?' + #13#10 + #13#10 +
    'Будут удалены настройки пользователя, база индексации, временные файлы и логи:' + #13#10 +
    ExpandConstant('{localappdata}\LocalAssistant') + #13#10 + #13#10 +
    'Если выбрать «Нет», программа будет удалена, но пользовательские данные останутся.',
    mbConfirmation,
    MB_YESNO
  );

  if ResultCode = IDYES then
    DeleteUserData := True;

  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  UserDataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if DeleteUserData then
    begin
      UserDataDir := ExpandConstant('{localappdata}\LocalAssistant');

      if DirExists(UserDataDir) then
      begin
        DelTree(UserDataDir, True, True, True);
      end;
    end;
  end;
end;