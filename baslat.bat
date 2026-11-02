@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul || (echo [HATA] Python bulunamadi. python.org'dan kurun ^(Add to PATH isaretli^). & pause & exit /b)
echo Paketler kontrol ediliyor...
python -m pip install --quiet --upgrade websocket-client mss pillow pynput certifi
:loop
python remote_support.py
echo.
echo Uygulama kapandi. 3 sn sonra yeniden aciliyor. Tamamen durdurmak icin bu pencereyi kapatin.
timeout /t 3 >nul
goto loop
