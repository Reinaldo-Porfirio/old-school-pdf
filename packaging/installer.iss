; Instalador do Old School PDF (Inno Setup 6).
; Rode pelo packaging/build.py, que informa versão e pastas com /D.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\pyinstaller\OldSchoolPDF"
#endif
#ifndef AssetsDir
  #define AssetsDir "..\build\assets"
#endif
#ifndef RootDir
  #define RootDir ".."
#endif

#define AppName "Old School PDF"
#define AppExe "OldSchoolPDF.exe"
#define ProgId "OldSchoolPDF.Document"

[Setup]
; O AppId identifica o programa entre versões. Não altere.
AppId={{0BF3710E-86CF-4AB1-8780-C4AFF91EE365}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
AppComments=Editor de PDF local, livre e sem assinatura.
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
; Instala só para o usuário atual, sem pedir administrador. O assistente oferece a outra opção.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=classic
WizardImageFile={#AssetsDir}\wizard.bmp
WizardSmallImageFile={#AssetsDir}\wizard-small.bmp
SetupIconFile={#AssetsDir}\oldschoolpdf.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
InfoBeforeFile={#RootDir}\packaging\antes-de-instalar.txt
OutputBaseFilename=OldSchoolPDF-{#AppVersion}-setup
Compression=lzma2/ultra64
SolidCompression=yes
ChangesAssociations=yes
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoDescription=Instalador do {#AppName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "openwith"; Description: "Mostrar o {#AppName} em ""Abrir com"" para arquivos .pdf"; GroupDescription: "Integração com o Windows:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RootDir}\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "{#RootDir}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; DestName: "AVISOS DE TERCEIROS.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Licença (AGPL-3.0)"; Filename: "{app}\LICENSE.txt"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Aparece em "Abrir com" sem tomar o lugar do leitor de PDF padrão do usuário.
Root: HKA; Subkey: "Software\Classes\{#ProgId}"; ValueType: string; ValueData: "Documento PDF"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgId}\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExe},0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\{#ProgId}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "{#ProgId}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""; Flags: uninsdeletekey; Tasks: openwith

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
