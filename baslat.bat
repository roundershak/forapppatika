@echo off
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
start "" http://127.0.0.1:7860
python -m kickclip web
pause
