#define MyAppName "LocalAssistant"
#define MyAppVersion "0.1.1"
#define MyAppPublisher "Nikita Druzhinin"
#define MyAppExeName "LocalAssistant.exe"

[Setup]
AppId={{5F7F0A31-6E3B-4F3D-9C65-6F2C8C8C0A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

; Установка без прав администратора в папку пользователя.
; Если захочешь ставить в Program Files, замени на:
; DefaultDirName={autopf}\{#MyAppName}
; PrivilegesRequired=admin
DefaultDirName={localappdata}\Programs\{#MyAppName}

DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=release
OutputBaseFilename=LocalAssistant_Setup_{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

; Если появится .ico-файл установщика, можно включить:
; SetupIconFile=assets\installer.ico

CloseApplications=yes
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать значок на рабочем столе"; GroupDescription: "Дополнительные значки:"; Flags: unchecked

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
  DeleteUserDataOnUninstall: Boolean;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
  DataPath: String;
begin
  DeleteUserDataOnUninstall := False;
  DataPath := ExpandConstant('{localappdata}\LocalAssistant');

  if DirExists(DataPath) then
  begin
    ResultCode := MsgBox(
      'Удалить пользовательские данные LocalAssistant?' + #13#10 + #13#10 +
      'Будут удалены:' + #13#10 +
      '- пользовательские настройки;' + #13#10 +
      '- база индексации;' + #13#10 +
      '- история и служебные данные;' + #13#10 +
      '- временные файлы;' + #13#10 +
      '- логи приложения.' + #13#10 + #13#10 +
      'Папка:' + #13#10 +
      DataPath + #13#10 + #13#10 +
      'Если планируете переустановить или обновить приложение, лучше выбрать «Нет».',
      mbConfirmation,
      MB_YESNO or MB_DEFBUTTON2
    );

    DeleteUserDataOnUninstall := ResultCode = IDYES;
  end;

  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataPath: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if DeleteUserDataOnUninstall then
    begin
      DataPath := ExpandConstant('{localappdata}\LocalAssistant');

      if DirExists(DataPath) then
      begin
        DelTree(DataPath, True, True, True);
      end;
    end;
  end;
end;