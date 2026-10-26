@echo off
setlocal
set "ER_ME3=%~1"
if not defined ER_ME3 set "ER_ME3=F:\Steam\steamapps\common\ELDEN RING\Game\bin\me3.exe"
if not exist "%ER_ME3%" (
  echo Usage: Launch.cmd "full path to me3.exe"
  exit /b 1
)
tasklist /FI "IMAGENAME eq eldenring.exe" /NH | findstr /I /C:"eldenring.exe" >nul
if not errorlevel 1 (
  echo Exit Elden Ring normally before launching this profile.
  exit /b 1
)
"%ER_ME3%" launch --game eldenring --profile "%~dp0EROfflineMessages.me3"
exit /b %errorlevel%
