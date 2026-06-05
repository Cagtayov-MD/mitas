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
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

FFMPEG = PROJECT_ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"


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

    # --- KÜRTÇE-ailesi (ku): whisper ÇEVİREMEZ → ASR ATLA (boş transcript), dürüst işaretle.
    #     Özet ayrı adımda İNTERNETTEN gelir (mitas_pipeline, bizim prompt). ---
    if language == "ku":
        # Kürtçe'de de chlang.json YAZ — yoksa _pipe_pdf kanal-dili SIFIRDAN tekrar koşar (MMS+whisper
        # yeniden yüklenir = ağır performans israfı). Bug-3.
        chlang_path = None
        if detect_info is not None:
            try:
                chlang_path = out / "chlang.json"
                chlang_path.write_text(json.dumps(detect_info, ensure_ascii=False), encoding="utf-8")
            except Exception:  # noqa: BLE001
                chlang_path = None
        result = {
            "status": "skipped_unsupported_lang", "mode": "lean", "model": "none", "language": "ku",
            "transcript_path": None, "clean_segments": 0, "transcript_chars": 0, "transcript_head": "",
            "audio_duration": 0.0, "fallback_triggered": False, "profile_used": "lean-skip-ku",
            "summary_channel": (f"a:{sel['stream']}/c{sel['channel']}" if sel else "—"),
            "channel_detect": detect_info, "chlang_path": str(chlang_path) if chlang_path else None,
            "note": "Kurtce-ailesi (whisper ceviremez) -> ASR atlandi; ozet internetten",
            "runtime_sec": round(time.perf_counter() - t0, 3),
        }
        sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        os._exit(0)

    # --- transkripsiyon modeli: Türkçe→turbo (hız), yabancı(desteklenen)→large-v3 (kalite, tespit edilen dilde) ---
    beam, tr_language = args.beam_size, (language or "tr")
    if bool(language) and language != "tr":
        try:
            fp = _MODEL_PATHS.get("large-v3")
            model = (WhisperModel(str(fp), device="cuda", compute_type="float16", local_files_only=True)
                     if fp and fp.exists()
                     else WhisperModel("large-v3", device="cuda", compute_type="float16"))
            beam, tr_language = max(args.beam_size, 5), language   # tespit edilen dilde transkribe (yeniden-tespit YOK)
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
    lines, plain, n = [], [], 0
    for s in segs:
        n += 1
        hh, mm, ss = int(s.start // 3600), int((s.start % 3600) // 60), int(s.start % 60)
        txt = s.text.strip()
        lines.append(f"[{hh:02d}:{mm:02d}:{ss:02d}] {txt}")
        plain.append(txt)
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
