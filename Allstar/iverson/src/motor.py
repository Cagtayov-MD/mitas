# -*- coding: utf-8 -*-
"""motor.py — Iverson kule orkestrasyonu: ses → transkript.

Kaynak: scripts/_pipe_asr.py `_lean_transcribe` (film/dizi üretim lean yolu),
kule-içi yollar ve sözleşme çıkışına çevrilmiş (2026-08-18). Mantık birebir:
  • dil: LID açıksa MMS-LID kanal-dil tespiti (yalnız çok-stream orijinal üstünde;
    16k mono wav girdide atlanır) → TR-veto (menşei TR + ku yanlış-tespit) →
    desteklenmeyen dil DIL_DESTEKSIZ (dürüst atlama; özet internetten notu)
  • model: TR/belirsiz → large-v3-turbo; desteklenen yabancı → large-v3 (tespit
    edilen dilde, beam=1)
  • CUDA float16; OOM → CPU int8 fallback (beam=1)
  • condition_on_previous_text=False; VAD on (min_silence 500ms)
  • çıktı: transcript.txt ([HH:MM:SS] satır) + transcript_plain.txt + chlang.json

KULE FARKLARI: model yolları <kule>/model/faster-whisper; ffmpeg config/env'den;
LLM-VRAM sübabı (ollama keep_alive=0) üretimde default AÇIKTI — kulede default
KAPALI (bağımsızlık), config/env ile açılır.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

KULE = Path(__file__).resolve().parent.parent
MODEL_KOKU = KULE / "model" / "faster-whisper"

_MODEL_YOLLARI = {
    "large-v3-turbo": MODEL_KOKU / "large-v3-turbo",
    "large-v3": MODEL_KOKU / "large-v3",
    "selimc-whisper-large-v3-turbo-turkish-float16": MODEL_KOKU / "selimc-whisper-large-v3-turbo-turkish-float16",
}


class MotorArizasi(Exception):
    """ARIZA'ya çevrilmek üzere yukarı atılır — koşu devam edemez."""

    def __init__(self, sinif: str, mesaj: str) -> None:
        super().__init__(mesaj)
        self.sinif, self.mesaj = sinif, mesaj


# whisper'in (faster-whisper) DESTEKLEDİĞİ dil kodları. MMS-LID 1024 dil üretebilir;
# whisper-dışı kod transcribe()'a verilirse ValueError fırlatır. Bu set tek-geçerlilik
# kapısı: dil whisper-dışıysa çöp-tr üretmek yerine dürüstçe ATLA (DIL_DESTEKSIZ).
_WHISPER_OK = frozenset({
    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo", "br", "bs", "ca", "cs", "cy", "da",
    "de", "el", "en", "es", "et", "eu", "fa", "fi", "fo", "fr", "gl", "gu", "ha", "haw", "he", "hi",
    "hr", "ht", "hu", "hy", "id", "is", "it", "ja", "jw", "ka", "kk", "km", "kn", "ko", "la", "lb",
    "ln", "lo", "lt", "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my", "ne", "nl", "nn",
    "no", "oc", "pa", "pl", "ps", "pt", "ro", "ru", "sa", "sd", "si", "sk", "sl", "sn", "so", "sq",
    "sr", "su", "sv", "sw", "ta", "te", "tg", "th", "tk", "tl", "tr", "tt", "uk", "ur", "uz", "vi",
    "yi", "yo", "yue", "zh",
})


def _lang_unsupported(language) -> bool:
    return not language or (language not in _WHISPER_OK)


def _ffmpeg(ayar: dict) -> str:
    ff = (ayar.get("ffmpeg") or os.environ.get("MITAS_FFMPEG") or "ffmpeg")
    return str(ff)


def _llm_valve(ayar: dict) -> None:
    """VRAM+COMMIT-sübap: resident LLM (varsa) whisper yüklenmeden ÖNCE boşaltılır.
    Opsiyonel çevre işlemi — ollama yoksa/hata verirse SESSİZ geç (ASLA bozmaz).
    Kulede default KAPALI (bağımsızlık); config llm_valve ya da env açar."""
    acik = bool(ayar.get("llm_valve")) or os.environ.get(
        "MITAS_ASR_LLM_VALVE", "0").strip().lower() in ("1", "true", "on", "yes")
    if not acik:
        return
    try:
        import urllib.request as _ur
        oll = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434").rstrip("/")
        for m in ("gemma-4-31b-it-qat-vision:latest", "gemma4:26b"):
            try:
                _ur.urlopen(_ur.Request(oll + "/api/generate",
                            data=json.dumps({"model": m, "keep_alive": 0}).encode("utf-8"),
                            headers={"Content-Type": "application/json"}), timeout=15).read()
            except Exception:  # noqa: BLE001 — o model yüklü değil: sonrakine geç
                pass
    except Exception:  # noqa: BLE001 — sübap ASLA ASR'yi bozmaz
        pass


def _wav_hazirla(ses: Path, hedef: Path, ayar: dict, sec=None, max_saniye=None) -> Path:
    """16k mono PCM wav üret (seçili kanal varsa ondan; yoksa downmix).
    max_saniye verilirse o kadarlık klip (test kolaylığı — üretim kalıbı)."""
    cmd = [_ffmpeg(ayar), "-y", "-hide_banner", "-loglevel", "error"]
    if max_saniye:
        cmd += ["-t", str(max_saniye)]
    cmd += ["-i", str(ses)]
    if sec and sec.get("language") is not None:
        cmd += ["-map", "0:a:" + str(sec["stream"]),
                "-af", "pan=mono|c0=c" + str(sec["channel"]), "-ar", "16000"]
    else:
        cmd += ["-vn", "-ac", "1", "-ar", "16000"]
    cmd += ["-acodec", "pcm_s16le", str(hedef)]
    hedef.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not hedef.exists():
        raise MotorArizasi("FFMPEG", "16k wav uretilemedi: " + (r.stderr or "")[-300:])
    return hedef


def calistir(ses: Path, cikti_dizini: Path, ayar: dict | None = None) -> dict:
    """Bir ses dosyası → transkript sonuç sözlüğü (sozlesme.Cikti alanlarının kaynağı).

    Döndürür: {durum, dil, model, kanal, segment_sayisi, ses_sure_sn,
              transkript, chlang, kanit}
    MotorArizasi: GIRDI / MODEL_YOK / FFMPEG / MOTOR (koşu arızası).
    """
    ayar = ayar or {}
    kanit = {"adimlar": {}}
    ses = Path(ses)
    cikti_dizini = Path(cikti_dizini)
    cikti_dizini.mkdir(parents=True, exist_ok=True)

    if not ses.exists():
        raise MotorArizasi("GIRDI", "ses dosyasi yok: " + str(ses))

    t0 = time.perf_counter()

    # ── 1. dil: LID (yalnız çok-stream orijinal üstünde; wav girdide atlanır) ──
    dil = ayar.get("dil") or "auto"
    if dil == "auto":
        dil = None                       # whisper kendi tespit eder (LID yoksa)
    sec, detect_info = None, None
    if ayar.get("lid", False) and dil is None and ses.suffix.lower() != ".wav":
        try:
            import channel_lang as cl
            streams = cl.audio_streams(str(ses))
            units = [cl.detect(str(ses), s, c)
                     for s, nch in enumerate(streams) for c in range(nch)]
            sec, sec_reason = cl.select_summary(units)
            if sec and sec.get("language"):
                dil = sec["language"]
            detect_info = {"selected": sec, "select_reason": sec_reason, "units": units,
                           "lid": "mms-lid-1024", "lid_arizali": cl.lid_arizali_mi()}
        except Exception as exc:  # noqa: BLE001 — tespit hata verirse downmix+oto'ya düş
            detect_info = {"error": type(exc).__name__ + ": " + str(exc)}
        kanit["adimlar"]["lid"] = (detect_info or {}).get("lid_arizali",
                                                          "lid kosulmadi (wav girdi ya da kapali)")

    # TR-mensei vetosu: Türkçe yapımda 'ku' yanlış-tespitini geri al (üretim C6 FIX).
    if ayar.get("tr_mensei", False) and dil == "ku" and isinstance(detect_info, dict):
        try:
            oy_min = int(os.environ.get("MITAS_LID_TR_VOTE_MIN", "1") or 1)
            tr_units = [u for u in (detect_info.get("units") or [])
                        if (u.get("votes") or {}).get("tr", 0) >= oy_min]
            if tr_units:
                sec = max(tr_units, key=lambda u: (u.get("votes") or {}).get("tr", 0))
                dil = "tr"
                detect_info["tr_veto"] = "ku→tr (menşei TR + TR-oyu var)"
        except Exception:  # noqa: BLE001 — veto hatası Kürtçe-atla davranışını KORUR
            pass

    # ── 2. desteklenmeyen dil → dürüst atlama (içerik gerçeği) ────────────────
    if _lang_unsupported(dil) and (dil is not None or detect_info):
        # dil None + LID koşuldu ama net çıkamadı → whisper oto-tespide bırak (aşağıda).
        if dil is not None:
            chlang_yaz(cikti_dizini, detect_info)
            kanit["adimlar"]["dil"] = "desteklenmeyen: " + str(dil)
            return {
                "durum": "DIL_DESTEKSIZ", "dil": dil, "model": "none",
                "kanal": ("a:" + str(sec["stream"]) + "/c" + str(sec["channel"])) if sec else "downmix",
                "segment_sayisi": 0, "ses_sure_sn": 0.0, "transkript": None,
                "chlang": detect_info,
                "kanit": kanit | {"not": ("Kürtçe-ailesi (whisper çeviremez) → ASR atlandı; "
                                          "özet internetten" if dil == "ku" else
                                          "'" + str(dil) + "' whisper-dışı dil → ASR atlandı")},
            }

    _llm_valve(ayar)

    # ── 3. model seçimi: TR/belirsiz → turbo; desteklenen yabancı → large-v3 ──
    import faster_whisper  # lazy — testler sys.modules'e fake enjekte eder

    beam = int(ayar.get("beam_size", 1) or 1)
    model_adi = ayar.get("model") or "large-v3-turbo"
    if dil and dil != "tr":
        model_adi = "large-v3"                     # üretim kuralı: yabancı ses → kalite modeli
        beam = max(1, int(os.environ.get("MITAS_ASR_FOREIGN_BEAM", "1") or 1))
        kanit["adimlar"]["model"] = "large-v3 (yabancı ses: " + dil + ")"
    yol = _MODEL_YOLLARI.get(model_adi)
    model = None
    try:
        if yol is None or not yol.exists():
            raise MotorArizasi("MODEL_YOK", "model bulunamadi: " + str(model_adi)
                               + " → " + str(yol))
        try:
            model = faster_whisper.WhisperModel(str(yol), device="cuda",
                                                compute_type="float16", local_files_only=True)
        except Exception as exc:  # noqa: BLE001 — CUDA yok/OOM → CPU int8
            sys.stderr.write("[iverson][uyari] CUDA yukleme basarisiz (" + type(exc).__name__
                             + ") → CPU int8 dusuluyor\n")
            model = faster_whisper.WhisperModel(str(yol), device="cpu",
                                                compute_type="int8")
    except MotorArizasi:
        raise
    except Exception as exc:  # noqa: BLE001
        raise MotorArizasi("MOTOR", "model yuklenemedi (" + model_adi + "): "
                           + type(exc).__name__ + ": " + str(exc)) from exc

    # ── 4. 16k mono wav hazırla (wav değilse ya da kanal seçildiyse) ──────────
    scratch = KULE / "scratch"
    wav = ses
    if ses.suffix.lower() != ".wav" or (sec and sec.get("language") is not None):
        wav = scratch / (cikti_dizini.name + "_asr_16k.wav")
        _wav_hazirla(ses, wav, ayar, sec=sec, max_saniye=ayar.get("max_saniye"))
    elif ayar.get("max_saniye"):
        wav = scratch / (cikti_dizini.name + "_asr_16k.wav")
        _wav_hazirla(ses, wav, ayar, sec=None, max_saniye=ayar.get("max_saniye"))

    # ── 5. transkripsiyon (OOM → CPU int8, beam=1) ───────────────────────────
    vad = str(ayar.get("vad", "on")).lower() != "off"
    try:
        segs, info = model.transcribe(
            str(wav), language=dil, beam_size=beam,
            vad_filter=vad, vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False, word_timestamps=False)
    except Exception as exc_oom:
        if "out of memory" in str(exc_oom).lower() or "cuda" in str(exc_oom).lower():
            sys.stderr.write("[iverson][uyari] CUDA OOM → CPU int8 fallback\n")
            try:
                cpu_model = faster_whisper.WhisperModel(str(yol), device="cpu",
                                                        compute_type="int8")
                segs, info = cpu_model.transcribe(
                    str(wav), language=dil, beam_size=1,
                    vad_filter=vad, vad_parameters=dict(min_silence_duration_ms=500),
                    condition_on_previous_text=False, word_timestamps=False)
            except Exception:
                raise exc_oom
        else:
            raise MotorArizasi("MOTOR", "transcribe hatasi: "
                               + type(exc_oom).__name__ + ": " + str(exc_oom)) from exc_oom

    if not dil:                                    # whisper oto-tespit ettiyse GERÇEK dili al
        dil = getattr(info, "language", None) or dil

    ses_sure = float(getattr(info, "duration", 0.0) or 0.0)

    # ── 6. segment akışı → transcript dosyaları ──────────────────────────────
    lines, plain, n = [], [], 0
    for s in segs:
        n += 1
        hh, mm, ss = int(s.start // 3600), int((s.start % 3600) // 60), int(s.start % 60)
        txt = s.text.strip()
        lines.append("[" + f"{hh:02d}:{mm:02d}:{ss:02d}" + "] " + txt)
        plain.append(txt)
    tscr = cikti_dizini / "transcript.txt"
    tscr.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    clean = "\n".join(plain)
    (cikti_dizini / "transcript_plain.txt").write_text(clean + ("\n" if clean else ""),
                                                       encoding="utf-8")
    chlang_yaz(cikti_dizini, detect_info)

    kanit["adimlar"]["transcribe"] = {
        "model": model_adi, "beam": beam, "vad": vad, "dil": dil,
        "cihaz": "cuda-fallback-cpu" if "cpu" in str(getattr(model, "device", "")) else "cuda",
        "ses_sure_sn": round(ses_sure, 1),
    }
    durum = "TRANSKRIPT" if n > 0 else "METIN_YOK"
    return {
        "durum": durum, "dil": dil, "model": model_adi,
        "kanal": ("a:" + str(sec["stream"]) + "/c" + str(sec["channel"])) if sec else "downmix",
        "segment_sayisi": n, "ses_sure_sn": round(ses_sure, 1),
        "transkript": {
            "yol": str(tscr), "plain_yol": str(cikti_dizini / "transcript_plain.txt"),
            "karakter_sayisi": len(clean), "ilk_280": clean[:280],
        } if n > 0 else None,
        "chlang": detect_info,
        "kanit": kanit | {"runtime_sn": round(time.perf_counter() - t0, 1)},
    }


def chlang_yaz(cikti_dizini: Path, detect_info) -> None:
    """Kanal-dil tespitini dosyaya yaz (tüketici tekrar koşmasın). Best-effort."""
    if detect_info is None:
        return
    try:
        (cikti_dizini / "chlang.json").write_text(
            json.dumps(detect_info, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
