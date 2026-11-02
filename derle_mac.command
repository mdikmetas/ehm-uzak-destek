#!/bin/bash
# === EHM Uzak Destek - macOS .app derleyici ===
cd "$(dirname "$0")"
echo "== EHM Uzak Destek - macOS derleme =="
PY=python3
command -v $PY >/dev/null 2>&1 || { echo "python3 yok. https://www.python.org/downloads/ adresinden kur."; read -n1 -s; exit 1; }

echo "-> Paketler kuruluyor..."
$PY -m pip install --user --upgrade pyinstaller websocket-client mss pillow pynput certifi 2>/dev/null \
 || $PY -m pip install --user --break-system-packages --upgrade pyinstaller websocket-client mss pillow pynput certifi

echo "-> Derleniyor..."
$PY -m PyInstaller --noconfirm --clean --windowed \
  --name "EHM-Uzak-Destek" \
  --add-data "relay.txt:." \
  --collect-all pynput \
  --collect-all mss \
  --collect-all PIL \
  --collect-all certifi \
  remote_support.py

APP="$(pwd)/dist/EHM-Uzak-Destek.app"
echo
if [ -d "$APP" ]; then
  echo "BITTI -> $APP"
  echo
  echo "1) Gatekeeper kilidini ac:"
  echo "   xattr -dr com.apple.quarantine \"$APP\""
  echo "2) System Settings > Privacy & Security:"
  echo "   - Screen Recording  -> EHM-Uzak-Destek  (ekran icin SART)"
  echo "   - Accessibility     -> EHM-Uzak-Destek  (fare/klavye icin SART)"
  echo "   Sonra uygulamayi kapat/ac."
else
  echo "HATA: .app olusmadi. Ciktiyi kontrol et."
fi
read -n1 -s
