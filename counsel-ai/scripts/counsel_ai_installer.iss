; Inno Setup script for Counsel AI Windows installer
; Usage: iscc counsel_ai_installer.iss
; Requires: Inno Setup 6.x, Flutter Windows build completed

#define MyAppName "Counsel AI"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Counsel AI"
#define MyAppURL "https://counsel-ai.example.com"
#define MyAppExeName "counsel_ai.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\docs\LICENSE_ATTRIBUTIONS.md
OutputDir=output\windows
OutputBaseFilename=counsel-ai-setup-{#MyAppVersion}
SetupIconFile=..\app\windows\runner\resources\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppName}.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Code signing placeholder - set SIGNTOOL_PATH env var or modify below
; SignTool=signtool sign /fd SHA256 /a /t http://timestamp.digicert.com $f

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon"; Description: "{cm:CreateStartMenuIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Main Flutter Windows build
Source: "..\app\build\windows\x64\runner\Release\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Note: Ensure you've built the Flutter app first with: flutter build windows --release

; Bundled model (optional - if including a small GGUF model)
; Source: "..\models\gemma-2b-it.Q4_K_M.gguf"; DestDir: "{app}\models"; Flags: ignoreversion

; Required DLLs and dependencies are included in the Flutter build output

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppName}.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppName}.exe"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppName}.exe"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppName}.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// WinSparkle auto-update integration placeholder
// For production, integrate WinSparkle SDK and call:
// WinSparkle.spk_init();
// WinSparkle.spk_set_appcast_url("https://counsel-ai.example.com/updates/windows/appcast.xml");
// WinSparkle.spk_check_for_updates();

procedure InitializeWizard;
begin
  // Custom initialization if needed
end;

function IsUpgrade: Boolean;
var
  PreviousPath: String;
begin
  Result := RegQueryStringValue(HKLM32, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1', 'UninstallString', PreviousPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Post-install tasks: migrate data from previous version if upgrading
    if IsUpgrade then
    begin
      // Migration logic here
    end;
  end;
end;

[UninstallDelete]
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{localappdata}\CounselAI"
