#define MyAppName "SAEC-O&G"
#ifndef MyAppVersion
  #define MyAppVersion "0.3.0"
#endif

[Setup]
AppId={{5D4B1CB8-93FA-4A35-B73F-0C89E5EB6A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=SAEC-O&G
DefaultDirName={autopf}\SAEC-OG
DefaultGroupName=SAEC-O&G
OutputDir=..\dist\installer
OutputBaseFilename=SAEC-OG-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=classic
PrivilegesRequired=admin
DisableDirPage=no
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\SAEC-OG.exe

[Languages]
Name: "portuguesebrazil"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Atalhos:"

[Files]
Source: "..\dist\SAEC-OG.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\SAEC-OG-CLI.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\.env.template"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\prompts\*"; DestDir: "{app}\prompts"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\SAEC-O&G\SAEC-O&G"; Filename: "{app}\SAEC-OG.exe"
Name: "{autoprograms}\SAEC-O&G\SAEC-O&G CLI"; Filename: "{app}\SAEC-OG-CLI.exe"
Name: "{autoprograms}\SAEC-O&G\Desinstalar"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SAEC-O&G"; Filename: "{app}\SAEC-OG.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SAEC-OG.exe"; Description: "Executar SAEC-O&G agora"; Flags: postinstall nowait skipifsilent
