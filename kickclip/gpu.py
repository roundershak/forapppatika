"""Ekran kartı (NVIDIA) tespiti ve kullanımı.

- Whisper (faster-whisper / CTranslate2) CUDA ile çalışır. Windows'ta bunun için cuBLAS + cuDNN DLL'leri gerekir;
  baslat.bat NVIDIA kart görürse bunları pip ile kurar (nvidia-cublas-cu12, nvidia-cudnn-cu12), burada DLL
  klasörleri arama yoluna eklenir.
- Video kodlama NVENC (h264_nvenc) ile yapılır; 4K render'ı çok hızlandırır.
Her ikisi de çalışmazsa sessizce işlemciye (CPU) düşülür.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from functools import lru_cache

_DLL_DONE = False


def add_cuda_dll_dirs() -> None:
    """pip ile kurulan NVIDIA kütüphanelerinin DLL klasörlerini (Windows) arama yoluna ekler."""
    global _DLL_DONE
    if _DLL_DONE or sys.platform != "win32":
        return
    _DLL_DONE = True
    try:
        import importlib.util
        for pkg in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_runtime", "nvidia.cuda_nvrtc"):
            spec = importlib.util.find_spec(pkg)
            if not spec or not spec.submodule_search_locations:
                continue
            for base in spec.submodule_search_locations:
                for sub in ("bin", "lib"):
                    d = os.path.join(base, sub)
                    if os.path.isdir(d):
                        try:
                            os.add_dll_directory(d)
                        except OSError:
                            pass
                        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass


@lru_cache(maxsize=1)
def nvidia_name() -> str:
    """NVIDIA kartın adı (nvidia-smi ile). Yoksa boş."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return ""
    try:
        out = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return out.splitlines()[0].strip() if out else ""
    except Exception:
        return ""


@lru_cache(maxsize=1)
def cuda_devices() -> int:
    add_cuda_dll_dirs()
    try:
        import ctranslate2
        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


@lru_cache(maxsize=1)
def nvenc_ok() -> bool:
    """ffmpeg NVENC ile gerçekten kodlayabiliyor mu (kısa bir deneme ile)."""
    if os.environ.get("KICKCLIP_NO_NVENC"):
        return False
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.2:r=30",
                            "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


WHISPER_STATE = {"device": None, "error": None}


def status() -> dict:
    return {
        "nvidia": nvidia_name(),
        "cuda_devices": cuda_devices(),
        "whisper_device": WHISPER_STATE["device"],
        "whisper_error": WHISPER_STATE["error"],
        "nvenc": nvenc_ok(),
    }


def video_encoder_args(crf: int, preset: str, level: str | None) -> list[str]:
    """Kodlayıcı argümanları: NVENC varsa GPU, yoksa libx264."""
    if nvenc_ok():
        args = ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", str(crf),
                "-b:v", "0", "-profile:v", "high", "-spatial-aq", "1"]
    else:
        args = ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-profile:v", "high"]
    if level:
        args += ["-level:v", level]
    return args


def check_dlls() -> dict:
    """Windows'ta CUDA DLL'leri yüklenebiliyor mu (teşhis için)."""
    add_cuda_dll_dirs()
    res = {}
    if sys.platform != "win32":
        return res
    import ctypes
    for name in ("cublas64_12.dll", "cublasLt64_12.dll", "cudnn64_9.dll"):
        try:
            ctypes.WinDLL(name)
            res[name] = "OK"
        except OSError as e:
            res[name] = f"YOK ({e})"
    return res


def report() -> str:
    lines = [f"NVIDIA kart     : {nvidia_name() or 'bulunamadı'}",
             f"CUDA cihaz sayısı (Whisper): {cuda_devices()}",
             f"NVENC (video kodlama): {'çalışıyor' if nvenc_ok() else 'yok/çalışmıyor'}"]
    for k, v in check_dlls().items():
        lines.append(f"{k:20s}: {v}")
    if nvidia_name() and any(v != "OK" for v in check_dlls().values()):
        lines.append("\nEksik DLL var: baslat.bat'i kapatıp yeniden aç (CUDA kütüphanelerini kurar) ya da:\n"
                     "  .venv\\Scripts\\python -m pip install -r requirements-gpu.txt")
    return "\n".join(lines)
