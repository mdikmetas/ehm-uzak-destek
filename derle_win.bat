@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo == EHM Uzak Destek - Windows .exe derleme ==
where python >nul 2>nul || (echo [HATA] Python yok. python.org'dan kurun ^(Add to PATH isaretli^). & pause & exit /b)

echo -^> Paketler kuruluyor...
python -m pip install --upgrade pyinstaller websocket-client mss pillow pynput certifi

echo -^> Derleniyor (tek dosya, acilista UAC yonetici ister)...
python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin ^
  --name "EHM-Uzak-Destek" ^
  --add-data "relay.txt;." ^
  --collect-all pynput ^
  --collect-all mss ^
  --collect-all PIL ^
  --collect-all certifi ^
  remote_support.py

echo.
if exist "dist\EHM-Uzak-Destek.exe" (
  echo BITTI -^> %cd%\dist\EHM-Uzak-Destek.exe
  echo.
  echo - Bu TEK dosyayi musterilere dagitabilirsin.
  echo - Acilista UAC yonetici izni ister ^(tam denetim^).
  echo - Imzasiz oldugu icin SmartScreen uyarabilir:
  echo   "Daha fazla bilgi" -^> "Yine de calistir".
  echo - Relay adresi exe'ye gomuldu; degistirmek icin uygulama icindeki
  echo   Ayarlar panelini kullan ^(ya da exe yanina relay.txt koy^).
) else (
  echo [HATA] exe olusmadi. Yukaridaki ciktiyi kontrol et.
)
pause
