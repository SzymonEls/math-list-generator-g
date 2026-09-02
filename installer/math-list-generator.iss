; Skrypt instalatora Windows (Inno Setup 6.3+).
; Kompilacja:  ISCC.exe /DAppVersion=1.0.0 installer\math-list-generator.iss
; Wymaga wcześniejszego zbudowania aplikacji PyInstallerem do dist\MathListGenerator\.

#define AppName "Math List Generator"
#define AppExeName "MathListGenerator.exe"
#define AppPublisher "Szymon Elsner"
#define AppURL "https://github.com/SzymonEls/math-list-generator-g"

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId musi zostać niezmieniony - po nim Windows rozpoznaje aktualizacje.
AppId={{4A8592DB-F98C-483A-93E8-468830C2DEC7}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\MathListGenerator
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Instalacja dla bieżącego użytkownika - nie wymaga hasła administratora.
; Użytkownik może wybrać instalację dla wszystkich w pierwszym oknie kreatora.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename=MathListGenerator-{#AppVersion}-setup
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "polski"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\MathListGenerator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Skrót w menu Start
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
; Skrót na pulpicie (opcjonalny, do zaznaczenia w kreatorze)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
