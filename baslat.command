#!/bin/bash
cd "$(dirname "$0")"
PY=python3
command -v $PY >/dev/null 2>&1 || { echo "python3 yok. python.org'dan Python kur (Tk dahil gelir)."; read -n1 -s; exit 1; }
echo "Paketler kontrol ediliyor..."
$PY -m pip install --user --quiet --upgrade websocket-client mss pillow pynput certifi 2>/dev/null \
 || $PY -m pip install --user --break-system-packages --quiet --upgrade websocket-client mss pillow pynput certifi
while true; do
  $PY remote_support.py
  echo
  echo "Uygulama kapandi. 3 sn sonra yeniden aciliyor. Durdurmak icin bu pencereyi kapat."
  sleep 3
done
