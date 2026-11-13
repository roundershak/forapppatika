@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title KickClip guncelleme
echo ==================================================
echo   KickClip guncelleniyor (GitHub'dan son surum)
echo   Kliplerin, .env, client_secret.json ve YouTube
echo   baglantin KORUNUR.
echo ==================================================
echo.
set "TMPD=%TEMP%\kickclip_guncelle"
if exist "%TMPD%" rmdir /s /q "%TMPD%"
mkdir "%TMPD%"
echo [1/3] Indiriliyor...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol='Tls12'; Invoke-WebRequest -UseBasicParsing -Uri 'https://codeload.github.com/roundershak/forapppatika/zip/refs/heads/claude/kick-auto-clip-generator-925yij' -OutFile '%TMPD%\k.zip'; Expand-Archive -Force '%TMPD%\k.zip' '%TMPD%\x'"
if errorlevel 1 goto :fail
set "SRC="
for /d %%D in ("%TMPD%\x\*") do set "SRC=%%D"
if not defined SRC goto :fail
echo [2/3] Dosyalar guncelleniyor...
rem Asagidaki blok tek parca okunur: bu dosya kendini guncellese bile guvenle biter.
(
  robocopy "%SRC%" "%~dp0." /E /NFL /NDL /NJH /NJS /NP /XD .venv venv output work .git /XF .env client_secret*.json youtube_token.json youtube_channel.json
  if errorlevel 8 (
    echo [HATA] Dosyalar kopyalanamadi. KickClip acik ise kapatip tekrar deneyin.
    pause
    exit /b 1
  )
  rmdir /s /q "%TMPD%" >nul 2>nul
  echo [3/3] Tamam! Guncellendi.
  echo.
  echo Simdi baslat.bat ile KickClip'i acabilirsin.
  echo Yeni paket gerekiyorsa baslat.bat otomatik kurar.
  pause
  exit /b 0
)

:fail
echo.
echo [HATA] Guncelleme indirilemedi. Internet baglantini kontrol et.
echo Olmazsa GitHub'dan Code - Download ZIP ile indirip bu klasorun USTUNE cikar,
echo "Dosyalari degistir" de. Silmene gerek yok.
pause
exit /b 1
