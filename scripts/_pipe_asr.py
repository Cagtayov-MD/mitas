# -*- coding: utf-8 -*-
"""MITAS pipeline — ASR blok runner (venvs/asr ile kosar).

run_asr_pipeline'i cagirir; ciktiyi <out>/ altina yazar (archive/summary/...).
--max-seconds verilirse once ffmpeg ile o kadarlik 16k mono klip cikarir
(2 saatlik filmde tum ASR gece boyu surmesin diye test kolayligi).
stdout'a tek satir JSON sonuc basar.
"""
from __future__ import annotations
import sys, os, json, time, argparse, subprocess
os.environ["USE_TF"] = "0"        # MMS-LID ŞART: transformers TF'yi import etmesin (TF↔numpy2 çökmesi).
os.environ["USE_FLAX"] = "0"      # EN TEPEDE olmalı — faster_whisper/_channel_lang'den ÖNCE (geç set = TF zaten yüklü, MMS ölür).
# CUDA-12 notu (2026-07-30): ctranslate2 4.7.x encode anında libcublas.so.12 ister
# (model-load'da DEĞİL, ilk encode'da patlar — YAĞMACILAR kanıtı). Çözüm KOD DEĞİL
# ortam: venvs/asr'a nvidia-cublas-cu12 + nvidia-cudnn-cu12 kurulu olmalı
# (requirements/asr.txt); ct2 pip nvidia dizinlerini kendisi keşfediyor.
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

# Linux geçişi 2026-07-17: MITAS_FFMPEG env önceliği (mitas_pipeline ile tutarlı); yoksa eski yol.
FFMPEG = Path(os.environ.get("MITAS_FFMPEG") or (
    PROJECT_ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"))

# --- Canlı log: system_events.jsonl'e tek-satir olay yaz (UI per-film adim-logu icin). ---
# mitas_pipeline.log_event ile AYNI format/dosya; ASR uzun transkripsiyon boyunca "donuk" gorunmesin
# diye periyodik ilerleme basar. observability'yi import ETME (agir dep, ayri venv) — dogrudan append.
# İP-5 (2026-07-11): candidate modunda MITAS_OUTPUTS_DIR run-root'a işaret eder (pilot side-effect
# kanıtının yakaladığı sızıntı — üretim event'ine yazıyordu); env boşsa üretim yolu BYTE-AYNI.
_EVENTS_PATH = Path(os.environ.get("MITAS_OUTPUTS_DIR") or (PROJECT_ROOT / "outputs")) / "system_events.jsonl"

# whisper'in (faster-whisper) DESTEKLEDIGI dil kodlari. MMS-LID buradan FARKLI (1024 dil) bir kod
# uretebilir; _channel_lang._LANG_MAP cogunu 2-harf'e cevirir ama eslenemeyen/whisper-disi kod
# (or 'gle' Irlandaca, ya da haritada olmayan exotik dil) transcribe()'a verilirse ValueError firlatir
# (2026-06-20 forensik: 'swe'/'cmn' gibi eksik kodlar 25 filmi cokertti). Bu set tek-gecerlilik kapisi:
# dil whisper-disiysa ASR'yi cop-tr uretmek yerine "ku" gibi DURUSTCE atla (ozet internetten gelir).
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
    """ASR ATLANMALI mi? Kurtce ('ku', whisper ceviremez) VEYA whisper-disi/eslenemeyen kod.
    'tr' ve bos/None ASLA atlanmaz (varsayilan Turkce yol). Saf fonksiyon — smoke-test edilebilir."""
    if not language or language == "tr":
        return False
    return language == "ku" or language not in _WHISPER_OK


def _fmt_hms(sec) -> str:
    sec = int(max(0, sec or 0))
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def _emit_event(kind: str, summary: str, *, level: str = "info", media_id=None, detail=None) -> None:
    """system_events.jsonl'e canli-log olayi yaz. Hata ASR'yi ASLA bozmaz (best-effort)."""
    try:
        from datetime import datetime, timezone
        from uuid import uuid4
        ev = {"event_id": f"evt-{uuid4().hex[:12]}",
              "ts": datetime.now(timezone.utc).isoformat(),
              "kind": kind, "level": level if level in ("info", "warn", "error") else "info",
              "summary": summary, "module": "asr"}
        if media_id:
            ev["media_id"] = media_id
        if detail:
            ev["detail"] = detail
        _EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _EVENTS_PATH.open("a", encoding="utf-8") as h:
            h.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — log akisi ASR'yi bozmasin
        pass


def _extract_clip(src: Path, dst: Path, max_seconds: float) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(FFMPEG) if FFMPEG.exists() else "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-t", str(max_seconds), "-i", str(src),
           "-vn", "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not dst.exists():
        raise RuntimeError((r.stderr or r.stdout or "ffmpeg clip fail")[-500:])
    return dst


_MODEL_PATHS = {
    "large-v3-turbo": PROJECT_ROOT / "models" / "asr" / "faster-whisper" / "large-v3-turbo",
    "large-v3": PROJECT_ROOT / "models" / "asr" / "faster-whisper" / "large-v3",
}


def _lean_transcribe(src: Path, out: Path, args, lid_src: Path | None = None) -> dict:
    """transcript-only HIZLI ASR: faster-whisper TEK-PASS (align/diarize/fallback YOK).

    PROFIL_KONFIG.md film_dizi lean modu. Çıktı: <out>/transcript.txt ([HH:MM:SS] satır) +
    transcript_plain.txt. mitas_pipeline ile uyumlu JSON döner.

    B-1: dil tespiti (MMS-LID) ORİJİNAL çok-stream girdi üstünde koşar (lid_src); `src` yalnız
    transkripsiyon içindir. --max-seconds'la src bir .wav klibe iner ama LID klipten ETKİLENMEZ
    (yoksa capped-test'te dil hep "tr"ye düşer, yabancı/Kürtçe görünmez)."""
    import time
    t0 = time.perf_counter()
    from faster_whisper import WhisperModel

    mp = _MODEL_PATHS.get(args.model, _MODEL_PATHS["large-v3-turbo"])
    model = None   # transkripsiyon modeli LID'den SONRA yüklenir (Kürtçe'de hiç yüklenmez)

    # --- kanal-dil tespiti: MMS-LID (1024 dil; Kürtçe/Azerice/Arapça dahil, whisper'dan DOĞRU) ---
    # B-1: tespit ORİJİNAL girdi (lid_src) üstünde; max-seconds klip-extraction'dan BAĞIMSIZ.
    # lid_src verilmezse src'ye düş (cap'siz tam-film yolu — eski davranış, BOZULMAZ).
    lid_src = lid_src or src
    language, sel, detect_info = args.language, None, None
    if getattr(args, "auto_language", False) and lid_src.suffix.lower() != ".wav":
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            import _channel_lang as cl
            streams = cl.audio_streams(str(lid_src))
            units = [cl.detect(str(lid_src), s, c) for s, nch in enumerate(streams) for c in range(nch)]
            sel, sel_reason = cl.select_summary(units)   # TR>diğer konuşma>(net yoksa) en iyi diyalog; downmix'e DÜŞME
            if sel and sel.get("language"):
                language = sel["language"]
            detect_info = {"selected": sel, "select_reason": sel_reason, "units": units, "lid": "mms-lid-1024"}
        except Exception as exc:  # noqa: BLE001 - tespit hata verirse downmix+tr'ye düş
            detect_info = {"error": f"{type(exc).__name__}: {exc}"}

    # C6 FIX (2026-06-22): menşei-kapılı TR-veto — Türkçe yapımda Kürtçe yanlış-tespitini geri al.
    # --tr-provenance: mitas_pipeline menşei Türkçe (original boş veya ==title) ise geçirir.
    # language=="ku" VE herhangi bir kanalda TR-LID-oyu>0 → en yüksek TR-oylu kanala çevir.
    # Gerçek Kürtçe film (TR-oyu yok) → dokunulmaz; yabancı film (--tr-provenance gelmez) → dokunulmaz.
    if getattr(args, "tr_provenance", False) and language == "ku":
        try:
            _tr_vote_min = int(os.environ.get("MITAS_LID_TR_VOTE_MIN", "1") or 1)
            _veto_units = (detect_info or {}).get("units") or [] if isinstance(detect_info, dict) else []
            _tr_units = [u for u in _veto_units if (u.get("votes") or {}).get("tr", 0) >= _tr_vote_min]
            if _tr_units:
                _tr_sel = max(_tr_units, key=lambda u: (u.get("votes") or {}).get("tr", 0))
                sel = _tr_sel
                language = "tr"
        except Exception:  # noqa: BLE001 — veto hata verirse Kürtçe-atla davranışı KORUNUR
            pass

    # --- DESTEKLENMEYEN dil → ASR ATLA (boş transcript), dürüst işaretle. Özet ayrı adımda
    #     İNTERNETTEN gelir (mitas_pipeline). Kürtçe-ailesi ('ku', whisper çeviremez) VEYA whisper-dışı/
    #     eşlenemeyen kod (2026-06-20: eksik dil-kodu ValueError'ı yerine dürüst atlama). ---
    if _lang_unsupported(language):
        # chlang.json YAZ — yoksa _pipe_pdf kanal-dili SIFIRDAN tekrar koşar (MMS+whisper yeniden yüklenir
        # = ağır performans israfı). Bug-3.
        chlang_path = None
        if detect_info is not None:
            try:
                chlang_path = out / "chlang.json"
                chlang_path.write_text(json.dumps(detect_info, ensure_ascii=False), encoding="utf-8")
            except Exception:  # noqa: BLE001
                chlang_path = None
        _is_ku = (language == "ku")
        _note = ("Kurtce-ailesi (whisper ceviremez) -> ASR atlandi; ozet internetten" if _is_ku
                 else f"'{language}' whisper-disi/desteklenmeyen dil -> ASR atlandi; ozet internetten")
        result = {
            "status": "skipped_unsupported_lang", "mode": "lean", "model": "none", "language": language,
            "transcript_path": None, "clean_segments": 0, "transcript_chars": 0, "transcript_head": "",
            "audio_duration": 0.0, "fallback_triggered": False, "profile_used": f"lean-skip-{language}",
            "summary_channel": (f"a:{sel['stream']}/c{sel['channel']}" if sel else "—"),
            "channel_detect": detect_info, "chlang_path": str(chlang_path) if chlang_path else None,
            "note": _note,
            "runtime_sec": round(time.perf_counter() - t0, 3),
        }
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        os._exit(0)

    # --- transkripsiyon modeli: Türkçe→turbo (hız), yabancı(desteklenen)→large-v3 (kalite, tespit edilen dilde) ---
    beam, tr_language = args.beam_size, (language or "tr")
    # VRAM+COMMIT-SÜBABI (Faz-0 2026-07-04; 2026-07-06 gecesi HER DİLE genelleştirildi):
    # resident LLM (31b/26b, ~24GB commit) whisper yüklenmeden ÖNCE explicit boşaltılır.
    # GENELLEŞTİRME KANITI: 05/07 20:31'den itibaren 14/14 filmde ASR bellek-ölümü
    # (MemoryError/mkl_malloc/CUDA-OOM/WinError-1455) — commit-tavanı 186GB doygun; yalnız
    # yabancı-dalda ateşlenen sübap Türkçe-turbo yolunu korumuyordu. Bedel: LLM-rol'de model
    # yeniden-yüklenir (~56sn/film); kazanç: transkript+özet hattı YAŞAR (kalite > hız).
    # keep_alive:0 = "hemen tahliye". FAIL-SAFE: ollama kapalı/hata → sessiz geç.
    # Kill-switch: MITAS_ASR_LLM_VALVE=0.
    if os.environ.get("MITAS_ASR_LLM_VALVE", "1").strip().lower() not in ("0", "false", "off", "no"):
        try:
            import urllib.request as _ur, json as _js
            _oll = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434").rstrip("/")
            for _m in ("gemma-4-31b-it-qat-vision:latest", "gemma4:26b"):
                try:
                    _ur.urlopen(_ur.Request(_oll + "/api/generate",
                                data=_js.dumps({"model": _m, "keep_alive": 0}).encode("utf-8"),
                                headers={"Content-Type": "application/json"}), timeout=15).read()
                except Exception:  # noqa: BLE001 — o model yüklü değil/hata: sonrakine geç
                    pass
        except Exception:  # noqa: BLE001 — sübap ASLA ASR'yi bozmaz
            pass
    if bool(language) and language != "tr":
        try:
            fp = _MODEL_PATHS.get("large-v3")
            model = (WhisperModel(str(fp), device="cuda", compute_type="float16", local_files_only=True)
                     if fp and fp.exists()
                     else WhisperModel("large-v3", device="cuda", compute_type="float16"))
            # beam: yabanci large-v3 yolu. ESKI max(beam,5)=5 KORKUNC YAVASTI (97dk film ~20dk).
            # Cagatay_22.02 altin-standardi (FilmDizi-Hybrid: large-v3 + beam=1) ayni modelle
            # iyi sure+kalite verdi; beam=5 orada yalniz saf STT profilinde. Varsayilan 1, env-ayarli.
            _foreign_beam = max(1, int(os.environ.get("MITAS_ASR_FOREIGN_BEAM", "1") or "1"))
            beam, tr_language = _foreign_beam, language   # tespit edilen dilde transkribe (yeniden-tespit YOK)
            detect_info = detect_info or {}
            detect_info["asr_model"] = f"large-v3 (yabanci ses: {language})"
        except Exception as exc:  # noqa: BLE001 - full yuklenemezse turbo'ya düş
            detect_info = detect_info or {}
            detect_info["fullv3_error"] = f"{type(exc).__name__}: {exc}"
    if model is None:
        model = WhisperModel(str(mp), device="cuda", compute_type="float16", local_files_only=True)  # turbo (tr/varsayılan)

    # ses çıkar: seçili kanal (downmix'e DÜŞME — select_summary en iyi diyalog kanalını verdi)
    wav = src
    if src.suffix.lower() != ".wav":
        wav = out / "_asr_16k.wav"
        cmd = [str(FFMPEG) if FFMPEG.exists() else "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src)]
        if sel and sel.get("language") is not None:
            cmd += ["-map", f"0:a:{sel['stream']}", "-af", f"pan=mono|c0=c{sel['channel']}", "-ar", "16000"]
        else:
            cmd += ["-vn", "-ac", "1", "-ar", "16000"]
        cmd += ["-acodec", "pcm_s16le", str(wav)]
        subprocess.run(cmd, check=True)

    segs, info = model.transcribe(
        str(wav), language=tr_language, beam_size=beam,
        vad_filter=(args.vad != "off"), vad_parameters=dict(min_silence_duration_ms=500),
        condition_on_previous_text=False, word_timestamps=False,
    )
    if not tr_language:                          # full-v3 oto-tespit ettiyse GERÇEK dili al (result/chlang için)
        language = getattr(info, "language", None) or language
    # --- canli log: transkripsiyon ilerlemesi (en uzun asama; UI'da "donuk" gorunmesin) ---
    _mid = getattr(args, "media_id", None)
    _audio_dur = float(getattr(info, "duration", 0.0) or 0.0)
    _emit_event("asr_progress",
                f"ASR transkripsiyon basladi (ses {_fmt_hms(_audio_dur)}, dil={tr_language or language or 'tr'}).",
                media_id=_mid, detail={"percent": 0, "audio_seconds": round(_audio_dur, 1)})
    _last_emit = time.perf_counter()
    lines, plain, n = [], [], 0
    for s in segs:
        n += 1
        hh, mm, ss = int(s.start // 3600), int((s.start % 3600) // 60), int(s.start % 60)
        txt = s.text.strip()
        lines.append(f"[{hh:02d}:{mm:02d}:{ss:02d}] {txt}")
        plain.append(txt)
        # ~15 sn'de bir ilerleme: yuzde = islenen-ses / toplam-ses (faster-whisper segment-akisli)
        _now = time.perf_counter()
        if _now - _last_emit >= 15.0:
            _last_emit = _now
            _pct = int(min(99, (float(s.end) / _audio_dur) * 100)) if _audio_dur > 0 else 0
            _emit_event("asr_progress",
                        f"ASR transkripsiyon: %{_pct} ({_fmt_hms(s.end)} / {_fmt_hms(_audio_dur)}, {n} segment).",
                        media_id=_mid, detail={"percent": _pct, "segments": n})
    tscr = out / "transcript.txt"
    tscr.write_text("\n".join(lines) + "\n", encoding="utf-8")
    clean = "\n".join(plain)
    (out / "transcript_plain.txt").write_text(clean + "\n", encoding="utf-8")
    # kanal-dil tespitini PDF adımı YENİDEN koşmasın diye dosyaya yaz (chlang.json)
    chlang_path = None
    if detect_info is not None:
        try:
            chlang_path = out / "chlang.json"
            chlang_path.write_text(json.dumps(detect_info, ensure_ascii=False), encoding="utf-8")
        except Exception:  # noqa: BLE001
            chlang_path = None
    result = {
        "status": "done" if n else "partial",
        "mode": "lean", "model": args.model,
        "transcript_path": str(tscr),
        "clean_segments": n, "transcript_chars": len(clean), "transcript_head": clean[:280],
        "audio_duration": round(getattr(info, "duration", 0.0), 1),
        "fallback_triggered": False, "profile_used": f"lean-{args.model}",
        "language": language,
        "summary_channel": (f"a:{sel['stream']}/c{sel['channel']}" if sel else "downmix"),
        "channel_detect": detect_info,
        "chlang_path": str(chlang_path) if chlang_path else None,
        "runtime_sec": round(time.perf_counter() - t0, 3),
    }
    # KRITIK: CTranslate2/CUDA, uzun (film) transcribe SONRASI process cikis/cleanup'inda
    # native crash edebiliyor (0xC0000409); JSON block-buffered stdout'tan silinir → mitas "failed" sanir.
    # Cozum: sonucu BURADA (transcript yazimina en yakin, return/json.dumps/main zincirine GIRMEDEN)
    # yaz+flush, sonra os._exit ile Python+CUDA cleanup'ini ATLAYARAK ANINDA cik → crash penceresi kapanir.
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    os._exit(0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--media-id", required=True)
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--content-profile", default="film")
    ap.add_argument("--max-seconds", type=float, default=0.0)
    # --- LEAN / transcript-only modu (PROFIL_KONFIG.md: film_dizi özet için) ---
    # align/diarize/fallback/word-ts YOK → turbo tek-pass, en hızlı, sadece metin.
    ap.add_argument("--lean", action="store_true")
    ap.add_argument("--model", default="large-v3-turbo")
    ap.add_argument("--beam-size", type=int, default=1)
    ap.add_argument("--vad", default="on")
    ap.add_argument("--language", default="tr")
    # kanal-dil tespiti (film): türkçe kanaldan özet, yoksa kanal-1 kendi dilinde (PROFIL_KONFIG)
    ap.add_argument("--auto-language", action="store_true")
    # C6 FIX (2026-06-22): menşei-kapılı TR-veto (Türkçe yapımda Kürtçe yanlış-tespitini engelle)
    ap.add_argument("--tr-provenance", action="store_true")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    try:
        orig = Path(args.input)              # B-1: ORİJİNAL çok-stream girdi (MMS-LID bunun üstünde koşar)
        src = orig
        if args.max_seconds and args.max_seconds > 0:
            src = _extract_clip(src, out / "_asr_input_clip.wav", args.max_seconds)

        # LEAN: özet-transcript modu → run_asr_pipeline'i (whisperx/diarize/fallback) ATLA
        if args.lean:
            # B-1: src (gerekirse klip) transkripsiyon için; lid_src=orig dil tespiti için (klipten ETKİLENMEZ).
            _lean_transcribe(src, out, args, lid_src=orig)   # sonucu kendi yazip flush+os._exit ile cikar (crash-guvenli)
            return 0                            # ulasilmaz (os._exit); butunluk icin birakildi

        from core.pipelines.asr.pipeline import run_asr_pipeline
        result = run_asr_pipeline(
            str(src),
            content_profile=args.content_profile,
            channel_mode="auto",
            word_alignment_mode="whisperx",
            output_dir=str(out),
            media_id=args.media_id,
            job_id=args.job_id,
            module_run_id=f"{args.job_id}-module",
        )
        tr = result.transcribe_result
        summary = {}
        try:
            summary = json.loads(Path(result.summary_path).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
        timing = (summary.get("timing") or {}) if isinstance(summary, dict) else {}
        clean_tx = (tr.clean_transcript or "")
        payload = {
            "status": "done" if str(result.module_run.status) in ("JobStatus.done", "done") else "partial",
            "module_status": str(result.module_run.status),
            "archive_path": str(result.archive_path),
            "summary_path": str(result.summary_path),
            "transcript_review_path": str(result.transcript_review_path),
            "timeline_events_path": str(result.timeline_events_path),
            "audio_duration": getattr(tr, "audio_duration", None),
            "clean_segments": len(getattr(tr, "clean_segments", []) or []),
            "transcript_chars": len(clean_tx),
            "transcript_head": clean_tx[:280],
            "fallback_triggered": bool(getattr(tr, "fallback_triggered", False)),
            "profile_used": getattr(tr, "profile_used", None),
            "asr_total_seconds": timing.get("total_seconds"),
            "normalize_seconds": timing.get("normalize_seconds"),
            "transcribe_total_seconds": timing.get("transcribe_total_seconds"),
            "fallback_seconds": timing.get("fallback_seconds"),
            "runtime_sec": round(time.perf_counter() - started, 3),
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        os._exit(0)   # lean ile ayni cikis-crash korumasi (bkz. yukarisi)
    except Exception as exc:  # noqa: BLE001
        import traceback
        sys.stdout.write(json.dumps({
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc()[-1500:],
            "runtime_sec": round(time.perf_counter() - started, 3),
        }, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        os._exit(1)


if __name__ == "__main__":
    raise SystemExit(main())
