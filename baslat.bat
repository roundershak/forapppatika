@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title KickClip

echo ==================================================
echo   KickClip baslatiliyor...
echo ==================================================
echo.

rem --- ZIP icinden calistirildi mi? ---
if not exist "kickclip\__init__.py" (
  echo [HATA] "kickclip" klasoru bulunamadi.
  echo ZIP dosyasini once bir klasore cikarin: sag tik - "Tumunu ayikla".
  echo Sonra cikan klasordeki baslat.bat dosyasini calistirin.
  goto :fail
)

rem --- Uyumlu Python bul: 64-bit 3.10-3.13 (Whisper/onnxruntime bunlari destekliyor) ---
set "PY="
set "CHECK=import sys,struct; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,13) and struct.calcsize('P')==8 else 1)"
where py >nul 2>nul
if not errorlevel 1 (
  for %%V in (3.12 3.11 3.13 3.10) do (
    if not defined PY (
      py -%%V -c "%CHECK%" >nul 2>nul && set "PY=py -%%V"
    )
  )
)
if not defined PY (
  where python >nul 2>nul && python -c "%CHECK%" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [HATA] Uyumlu Python bulunamadi.
  echo KickClip icin 64-bit Python 3.10 - 3.13 gerekli. 3.14 ve 32-bit surumler desteklenmiyor.
  echo 1. https://www.python.org/downloads/release/python-3129/ adresinden
  echo    "Windows installer 64-bit" indirin.
  echo 2. Kurulumun ILK ekraninda "Add python.exe to PATH" kutusunu isaretleyin.
  echo 3. Kurulum bitince baslat.bat'i tekrar calistirin.
  goto :fail
)
for /f "delims=" %%v in ('%PY% --version 2^>^&1') do echo [OK] %%v kullanilacak.

rem --- Sanal ortam ---
set "VPY=%~dp0.venv\Scripts\python.exe"
if exist "%VPY%" (
  "%VPY%" -c "%CHECK%" >nul 2>nul
  if errorlevel 1 (
    echo [!] Eski sanal ortam uyumsuz Python ile kurulmus, yeniden olusturuluyor...
    rmdir /s /q .venv
  )
)
if not exist "%VPY%" (
  echo [1/4] Sanal ortam olusturuluyor...
  %PY% -m venv .venv
  if errorlevel 1 goto :fail
)

rem --- Paketler: sadece ilk seferde veya requirements.txt degisince kurulur ---
fc /b requirements.txt ".venv\req.stamp" >nul 2>nul
if errorlevel 1 (
  echo [2/4] Gerekli paketler kuruluyor.
  echo       ILK SEFERDE 5-15 DAKIKA SUREBILIR, pencereyi kapatmayin...
  echo.
  "%VPY%" -m pip install --upgrade pip
  "%VPY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo [HATA] Paket kurulumu basarisiz. Yukaridaki kirmizi hatayi gonderin.
    goto :fail
  )
  copy /y requirements.txt ".venv\req.stamp" >nul
) else (
  echo [2/4] Paketler zaten kurulu.
)

rem --- ffmpeg ---
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [3/4] ffmpeg bulunamadi, kuruluyor...
  where winget >nul 2>nul
  if errorlevel 1 (
    echo [HATA] winget yok. ffmpeg'i elle kurun: https://www.gyan.dev/ffmpeg/builds/
    echo        "ffmpeg-release-essentials.zip" indirip bin klasorunu PATH'e ekleyin.
    goto :fail
  )
  winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
  echo.
  echo ffmpeg kuruldu. PATH yenilenmesi icin bu pencereyi KAPATIP baslat.bat'i TEKRAR calistirin.
  goto :fail
)
echo [3/4] ffmpeg bulundu.

rem --- Baslat ---
echo [4/4] Arayuz aciliyor, tarayici birazdan acilacak...
echo.
set "KICKCLIP_LAUNCHER=2"
rem Asagidaki blok tek parca okunur; guncelleme bu dosyayi degistirse bile guvenle yeniden baslatir.
(
  "%VPY%" -m kickclip web --open
  if errorlevel 3 if not errorlevel 4 (
    echo.
    echo Guncelleme yuklendi, KickClip yeniden baslatiliyor...
    set "KICKCLIP_NO_OPEN=1"
    start "KickClip" "%~f0"
    exit
  )
  if errorlevel 1 goto :fail
  pause
  exit /b 0
)

:fail
echo.
echo --------------------------------------------------
echo Bir sorun olustu. Bu pencerenin ekran goruntusunu gonderin.
echo --------------------------------------------------
pause
exit /b 1
