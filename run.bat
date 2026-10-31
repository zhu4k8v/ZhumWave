@echo off
chcp 65001 >nul
cd /d "%~dp0"
py audio_player.py
echo.
echo ZhumWave завершён. Код выхода: %errorlevel%
echo Если выше есть traceback — скопируйте его полностью.
pause
