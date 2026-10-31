
Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"

!define APPNAME "ZhumWave"
!define APPVERSION "1.0.0"
!define APPEXE "ZhumWave.exe"
!define UNINSTKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\ZhumWave"

Name "${APPNAME}"
Caption "Установка ZhumWave"
BrandingText "ZhumWave — музыкальный плеер"
!ifdef TESTMODE
OutFile "release\ZhumWave-Setup-test.exe"
InstallDir "$TEMP\ZhumWaveTest"
!else
OutFile "release\ZhumWave-Setup-${APPVERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\ZhumWave"
!endif
InstallDirRegKey HKCU "${UNINSTKEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 64
XPStyle on
ShowInstDetails show
ShowUninstDetails show
VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "ZhumWave"
VIAddVersionKey "FileDescription" "ZhumWave installer"
VIAddVersionKey "FileVersion" "1.0.0.0"
VIAddVersionKey "ProductVersion" "1.0.0.0"
VIAddVersionKey "LegalCopyright" "ZhumWave"

!define MUI_ABORTWARNING
!define MUI_ICON "ZhumWave.ico"
!define MUI_UNICON "ZhumWave.ico"
!define MUI_WELCOMEPAGE_TITLE "Установка ZhumWave"
!define MUI_WELCOMEPAGE_TEXT "Мастер установит ZhumWave в папку пользователя.$\r$\n$\r$\nБудут созданы ярлыки в меню «Пуск» и на рабочем столе. При желании можно включить автозапуск при входе в Windows — плеер загрузит сохранённый плейлист и свернётся в панель задач."
!define MUI_FINISHPAGE_RUN "$INSTDIR\ZhumWave.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Запустить ZhumWave"
!define MUI_FINISHPAGE_TEXT "ZhumWave установлен.$\r$\n$\r$\nЯрлык программы находится в меню «Пуск» и на рабочем столе. Удалить программу можно через «Параметры → Приложения» или ярлык удаления в меню «Пуск»."

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  SetShellVarContext current
  !ifndef TESTMODE
    nsExec::Exec 'taskkill /IM ZhumWave.exe'
    Sleep 700
  !endif
FunctionEnd

Section "Файлы ZhumWave" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  File "ZhumWave.exe"
  File "README.md"
  File "LICENSE.txt"
  File "ZhumWave.ico"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  !ifndef TESTMODE
    SetShellVarContext current
    CreateDirectory "$SMPROGRAMS\ZhumWave"
    CreateShortCut "$SMPROGRAMS\ZhumWave\ZhumWave.lnk" "$INSTDIR\ZhumWave.exe" "" "$INSTDIR\ZhumWave.exe" 0
    CreateShortCut "$SMPROGRAMS\ZhumWave\Удалить ZhumWave.lnk" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "${UNINSTKEY}" "DisplayName" "ZhumWave"
    WriteRegStr HKCU "${UNINSTKEY}" "DisplayVersion" "${APPVERSION}"
    WriteRegStr HKCU "${UNINSTKEY}" "Publisher" "ZhumWave"
    WriteRegStr HKCU "${UNINSTKEY}" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "${UNINSTKEY}" "DisplayIcon" "$INSTDIR\ZhumWave.exe,0"
    WriteRegStr HKCU "${UNINSTKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKCU "${UNINSTKEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
    WriteRegDWORD HKCU "${UNINSTKEY}" "NoModify" 1
    WriteRegDWORD HKCU "${UNINSTKEY}" "NoRepair" 1
    WriteRegDWORD HKCU "${UNINSTKEY}" "EstimatedSize" 65000
  !endif
SectionEnd

!ifndef TESTMODE
Section "Ярлык на рабочем столе" SecDesktop
  SetShellVarContext current
  CreateShortCut "$DESKTOP\ZhumWave.lnk" "$INSTDIR\ZhumWave.exe" "" "$INSTDIR\ZhumWave.exe" 0
SectionEnd

Section "Запускать при входе в Windows" SecAutostart
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "ZhumWave" '"$INSTDIR\ZhumWave.exe" --autostart'
SectionEnd
!endif

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "Сама программа, README, лицензия и файл удаления."
!ifndef TESTMODE
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Создать ярлык ZhumWave на рабочем столе."
  !insertmacro MUI_DESCRIPTION_TEXT ${SecAutostart} "Запускать плеер после входа в Windows. Плейлист загружается, окно сворачивается в панель задач."
!endif
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Section "Uninstall"
  SetShellVarContext current
  !ifndef TESTMODE
    nsExec::Exec 'taskkill /IM ZhumWave.exe'
    Sleep 700
  !endif
  Delete "$INSTDIR\ZhumWave.exe"
  Delete "$INSTDIR\ZhumWave.ico"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\LICENSE.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR"
  !ifndef TESTMODE
    Delete "$DESKTOP\ZhumWave.lnk"
    Delete "$SMPROGRAMS\ZhumWave\ZhumWave.lnk"
    Delete "$SMPROGRAMS\ZhumWave\Удалить ZhumWave.lnk"
    RMDir "$SMPROGRAMS\ZhumWave"
    DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "ZhumWave"
    DeleteRegKey HKCU "${UNINSTKEY}"
  !endif
SectionEnd
