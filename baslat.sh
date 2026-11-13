#!/usr/bin/env bash
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Python 3 bulunamadı (python.org)"; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg bulunamadı: brew install ffmpeg / sudo apt install ffmpeg"; exit 1; }
[ -x .venv/bin/python ] || python3 -m venv .venv || exit 1
if ! cmp -s requirements.txt .venv/req.stamp; then
  echo "Paketler kuruluyor (ilk seferde 5-15 dk sürebilir)..."
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt || exit 1
  cp requirements.txt .venv/req.stamp
fi
export KICKCLIP_LAUNCHER=2
# döngü tek parça okunur; uygulama içi güncelleme (çıkış kodu 3) sonrası yeni kodla yeniden açılır
main() {
  local opt="--open"
  while true; do
    .venv/bin/python -m kickclip web $opt
    code=$?
    [ "$code" -eq 3 ] || exit "$code"
    echo "Güncelleme yüklendi, yeniden başlatılıyor..."
    opt=""
  done
}
main
