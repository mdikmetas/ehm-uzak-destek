@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul || (echo [HATA] Python bulunamadi. & pause & exit /b)
python -m pip install --quiet --upgrade websockets
:loop
python relay.py
echo Relay kapandi, 3 sn sonra yeniden aciliyor...
timeout /t 3 >nul
goto loop
