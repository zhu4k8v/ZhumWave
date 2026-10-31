@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === ZhumWave: проверка исходников ===
echo Папка: %CD%
echo.

rem Удаляем старый кэш байткода, чтобы точно запустился текущий audio_player.py
if exist __pycache__ rmdir /s /q __pycache__

echo Проверка, что это исправленная версия (должны быть строки с MUTE_STATE):
findstr /N /C:"MUTE_STATE" audio_player.py
echo.

echo Запуск...
py audio_player.py
echo.
echo Программа завершилась. Код выхода: %errorlevel%
echo Если выше есть traceback — скопируйте его полностью.
pause
