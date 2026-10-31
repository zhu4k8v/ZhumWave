@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] Установка зависимостей...
py -m pip install --upgrade -r requirements.txt
if errorlevel 1 goto error

echo [2/3] Создание ZhumWave.ico...
py make_icon.py
if errorlevel 1 goto error

echo [3/3] Сборка ZhumWave.exe...
py -m PyInstaller --noconfirm --clean ZhumWave.spec
if errorlevel 1 goto error

echo.
echo Готово: dist\ZhumWave.exe
echo Иконка: ZhumWave.ico (сгенерирована из ZhumWave.png)
pause
exit /b 0

:error
echo.
echo Сборка завершилась с ошибкой. Проверьте вывод выше.
pause
exit /b 1
