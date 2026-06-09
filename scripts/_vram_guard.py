# -*- coding: utf-8 -*-
"""MITAS VRAM koruyucu — 1.0.

Tek RTX 3090 (24 GB) paylaşımlı ortamda gemma4:26b (~18.7 GB) gibi
ağır modelleri aynı anda iki sürecin birden yüklememesini sağlar.

Kullanım:
    from _vram_guard import heavy_gpu_guard

    with heavy_gpu_guard("gemma4:26b", label="credit_qc"):
        resp = ollama_call(...)   # gerçek çağrı

Hafif modeller (qwen3:8b, glm-ocr vb.) için guard hiçbir şey yapmaz
→ paralel akış bozulmaz.

Env değişkenleri:
    MITAS_HEAVY_MODELS       virgülle ayrılı ağır model adları (default: gemma4:26b,qwen3-vl:30b)
    MITAS_GPU_MUTEX          Windows named mutex adı (default: Global\\MITAS_GPU_HEAVY)
    MITAS_HEAVY_MIN_VRAM_MB  ağır model için gerekli min boş VRAM MB (default: 19000)
    MITAS_GPU_MUTEX_TIMEOUT  kilit bekleme üst sınırı saniye (default: 1800)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import Generator

# ---------------------------------------------------------------------------
# Sabitler / env
# ---------------------------------------------------------------------------

_HEAVY_MODELS: frozenset[str] = frozenset(
    m.strip()
    for m in os.environ.get("MITAS_HEAVY_MODELS", "gemma4:26b,qwen3-vl:30b").split(",")
    if m.strip()
)

_MUTEX_NAME: str = os.environ.get("MITAS_GPU_MUTEX", r"Global\MITAS_GPU_HEAVY")

_DEFAULT_MIN_VRAM_MB: int = int(os.environ.get("MITAS_HEAVY_MIN_VRAM_MB", "19000"))

_MUTEX_TIMEOUT_S: int = int(os.environ.get("MITAS_GPU_MUTEX_TIMEOUT", "1800"))

# WaitForSingleObject sabit: INFINITE yerine döngü kullanıyoruz
_WAIT_MS_INTERVAL: int = 30_000   # 30 sn'de bir kontrol + log
_VRAM_POLL_S: float = 2.0         # VRAM boşalma bekleme adımı


def _log(msg: str) -> None:
    """[vram_guard] prefixli stderr log — codebase'deki mevcut stil."""
    print(f"[vram_guard] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# VRAM sorgulama
# ---------------------------------------------------------------------------

def free_vram_mb() -> int:
    """nvidia-smi'dan boş VRAM MB döndürür.

    Komut çalışmazsa (nvidia-smi yok, hata vb.) çok büyük bir sayı
    döndürür → fail-open (guard ASLA engellemez).
    """
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        first_line = out.decode("utf-8", errors="replace").strip().splitlines()[0].strip()
        return int(first_line)
    except Exception:  # noqa: BLE001 — fail-open
        return 2 ** 31   # ~2 TB, guard geçişini engelleme


# ---------------------------------------------------------------------------
# Ağır model tespiti
# ---------------------------------------------------------------------------

def is_heavy(model: str) -> bool:
    """Model adı ağır set'te mi? (tam ad karşılaştırma)"""
    return model in _HEAVY_MODELS


# ---------------------------------------------------------------------------
# Ollama'da yüklü model sorgulama (opsiyonel, fail-safe)
# ---------------------------------------------------------------------------

def model_loaded(name: str) -> bool:
    """'ollama ps' çıktısında model adı geçiyor mu.

    Hata olursa False döner — çağıran bunu opsiyonel kullanır.
    """
    try:
        out = subprocess.check_output(
            ["ollama", "ps"],
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        return name in out.decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Windows named mutex yardımcıları (asr_server.py deseniyle birebir)
# ---------------------------------------------------------------------------

def _try_build_k32():
    """kernel32 handle + fonksiyon imzaları.  Başarısızsa None döner."""
    if os.name != "nt":
        return None, None, None, None
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        # CreateMutexW
        k32.CreateMutexW.restype = wintypes.HANDLE
        k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]

        # WaitForSingleObject
        k32.WaitForSingleObject.restype = wintypes.DWORD
        k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]

        # ReleaseMutex
        k32.ReleaseMutex.restype = wintypes.BOOL
        k32.ReleaseMutex.argtypes = [wintypes.HANDLE]

        # CloseHandle
        k32.CloseHandle.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = [wintypes.HANDLE]

        return k32, ctypes, wintypes, True
    except Exception as exc:  # noqa: BLE001
        _log(f"kernel32 yüklenemedi (fail-open): {exc}")
        return None, None, None, None


# ---------------------------------------------------------------------------
# Ana context manager
# ---------------------------------------------------------------------------

@contextmanager
def heavy_gpu_guard(
    model: str,
    min_mb: int | None = None,
    label: str = "",
) -> Generator[None, None, None]:
    """Ağır GPU modelleri için süreçler-arası karşılıklı dışlama.

    - Hafif model ise: hiçbir şey yapma, hemen yield (sıfır ek yük).
    - Ağır model ise:
        1. Windows named mutex al (Global\\MITAS_GPU_HEAVY).
        2. Model henüz yüklü değilse VRAM >= min_mb olana kadon bekle.
        3. yield (gerçek çağrı burada gerçekleşir).
        4. finally: mutex serbest bırak.
    Windows dışı veya mutex kurulamıyorsa fail-open (sadece yield).
    """
    _min_mb = min_mb if min_mb is not None else _DEFAULT_MIN_VRAM_MB
    _label = f"[{label}] " if label else ""

    # Hafif model → hiçbir şey yapma
    if not is_heavy(model):
        yield
        return

    # Windows mutex girişimi
    k32, ctypes, wintypes, ok = _try_build_k32()

    if not ok or k32 is None:
        # fail-open: Windows değil veya ctypes kurulamadı
        _log(f"{_label}fail-open (mutex kurulamadı) — model={model}, doğrudan devam")
        yield
        return

    mutex_handle = None
    try:
        # 1. Mutex oluştur veya var olanı aç (sahip OL → True ile)
        mutex_handle = k32.CreateMutexW(None, False, _MUTEX_NAME)
        if not mutex_handle:
            _log(f"{_label}mutex handle alınamadı, fail-open — model={model}")
            yield
            return

        _log(f"{_label}ağır model={model}, GPU mutex bekleniyor...")

        # 2. WaitForSingleObject döngüsü — 30sn aralıklarla, üst sınır _MUTEX_TIMEOUT_S
        WAIT_OBJECT_0 = 0x00000000
        WAIT_TIMEOUT   = 0x00000102
        elapsed = 0
        acquired = False

        while elapsed < _MUTEX_TIMEOUT_S:
            wait_ms = min(_WAIT_MS_INTERVAL, (_MUTEX_TIMEOUT_S - elapsed) * 1000)
            ret = k32.WaitForSingleObject(mutex_handle, int(wait_ms))
            if ret == WAIT_OBJECT_0:
                acquired = True
                break
            elif ret == WAIT_TIMEOUT:
                elapsed += wait_ms // 1000
                _log(
                    f"{_label}mutex bekleniyor... {elapsed}s geçti (üst sınır {_MUTEX_TIMEOUT_S}s) "
                    f"— model={model}"
                )
            else:
                # Beklenmedik dönüş kodu → fail-open
                _log(f"{_label}WaitForSingleObject dönüş={ret:#x}, fail-open — model={model}")
                break

        if not acquired:
            _log(
                f"{_label}UYARI: mutex bekleme süresi doldu ({_MUTEX_TIMEOUT_S}s) "
                f"— yine de devam ediliyor (fail-open). model={model}"
            )
            # Mutex almadan devam et — kaynağı serbest bırakmaya gerek yok
            try:
                yield
            finally:
                k32.CloseHandle(mutex_handle)
            return

        # Mutex alındı
        _log(f"{_label}mutex alındı — model={model}")

        # 3. VRAM kontrolü (model zaten yüklüyse beklemeden geç)
        if model_loaded(model):
            _log(f"{_label}model zaten VRAM'da yüklü, VRAM beklemesi atlanıyor — model={model}")
        else:
            vram_elapsed = 0
            while vram_elapsed < _MUTEX_TIMEOUT_S:
                free = free_vram_mb()
                if free >= _min_mb:
                    _log(f"{_label}VRAM tamam: {free} MB serbest (≥ {_min_mb} MB) — model={model}")
                    break
                _log(
                    f"{_label}VRAM yetersiz: {free} MB < {_min_mb} MB, "
                    f"{_VRAM_POLL_S:.0f}s bekle... (toplam {vram_elapsed}s)"
                )
                time.sleep(_VRAM_POLL_S)
                vram_elapsed += _VRAM_POLL_S
            else:
                _log(
                    f"{_label}UYARI: VRAM bekleme süresi doldu ({_MUTEX_TIMEOUT_S}s), "
                    f"yine de devam (fail-open). model={model}"
                )

        # 4. Gerçek çağrı
        yield

    finally:
        # Mutex'i her durumda serbest bırak
        if mutex_handle:
            try:
                k32.ReleaseMutex(mutex_handle)
            except Exception:  # noqa: BLE001
                pass
            try:
                k32.CloseHandle(mutex_handle)
            except Exception:  # noqa: BLE001
                pass
            _log(f"{_label}mutex serbest bırakıldı — model={model}")
