#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Python 3 bulunamadı (python.org)"; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg bulunamadı: brew install ffmpeg / sudo apt install ffmpeg"; exit 1; }
[ -x .venv/bin/python ] || python3 -m venv .venv
if ! cmp -s requirements.txt .venv/req.stamp; then
  echo "Paketler kuruluyor (ilk seferde 5-15 dk sürebilir)..."
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
  cp requirements.txt .venv/req.stamp
fi
exec .venv/bin/python -m kickclip web --open
