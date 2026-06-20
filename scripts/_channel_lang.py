# -*- coding: utf-8 -*-
"""Ses STREAM + KANAL envanteri + her birinin DİLİ (MMS-LID) + özet/transkript kanalı seçimi.

DİL TESPİTİ: Meta MMS-LID (facebook/mms-lid-1024) — 1024 dil; Kürtçe (kmr/ckb/zza), Azerice (aze),
Arapça (arb) dahil; whisper LID'inden kat kat doğru (whisper Kürtçe/Azerice'yi fa/tr sanıyordu).
Transkripsiyon YOK, sadece "hangi dil". Müzik/gürültü örnekleri düşük güven verir → MMS_MIN ile
elenir (doğal müzik-gate). Kanal seçimi: TR konuşma > diğer konuşma > (net yoksa) en iyi diyalog
kanalı — DOWNMIX'e DÜŞME. Kürtçe-ailesi "ku" → whisper çeviremez (üst katman işaretler, çevirmez).
  venvs/asr/Scripts/python.exe scripts/_channel_lang.py "<video>"
"""
import sys, os, json, subprocess
os.environ["USE_TF"] = "0"          # transformers TF'yi import etmesin (TF↔numpy2 çökmesi) — hard-set (setdefault değil)
os.environ["USE_FLAX"] = "0"
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # pytest/redirect altında reconfigure olmayabilir

ROOT = Path(r"E:\MITAS")
FF = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffmpeg.exe"
FP = ROOT / "tools" / "ffmpeg-shared" / "ffmpeg-8.1.1-full_build-shared" / "bin" / "ffprobe.exe"
TMP = ROOT / "outputs" / "_ocrpdf_run" / "_chlang"
TMP.mkdir(parents=True, exist_ok=True)

MMS_MODEL = "facebook/mms-lid-1024"
SAMPLES = [130, 300, 480, 700, 950, 1250]     # MMS hızlı → çok nokta (müzik örnekleri zaten elenir)
EXTRA_SAMPLES = [190, 360, 540, 820, 1100]
SDUR = 20
MMS_MIN = 0.50        # bu altı güven = müzik/gürültü → oya KATMA (doğal müzik-gate)
MIN_PROB = 0.60       # ortalama güven bu üstü = net "konuşma" kanalı
MIX_RATIO = 0.30      # ikincil/birincil oran → "iç içe"
AMBIG_RATIO = 0.25    # iki dil eşikte → ekstra örnek

# MMS-LID ISO 639-3 → bizim 2-harf (whisper uyumlu). Kürtçe-ailesi → "ku" (whisper ÇEVİREMEZ).
# KAPSAM: whisper'in DESTEKLEDIGI tum dilleri kapsa (eksik kod = _pipe_asr'de ValueError cokmesi,
# 2026-06-20 forensik: swe/est/isl/cmn/jav/vie/mon eksikti → 25 film ozet placeholder). Eslenemeyen
# kod ham doner; _pipe_asr whisper-gecerli degilse atlar (cop-tr uretmez). whisper-DESTEKLEMEYEN dil
# (or gle/Irlandaca) burada eslenmez → _pipe_asr "skipped_unsupported_lang" yapar.
_KURDISH = {"kmr", "ckb", "sdh", "kur", "zza", "lki", "bdv"}
_LANG_MAP = {
    # mevcut (korundu)
    "tur": "tr", "aze": "az", "azb": "az", "arb": "ar", "ara": "ar", "arz": "ar", "ary": "ar",
    "eng": "en", "fra": "fr", "deu": "de", "spa": "es", "ita": "it", "rus": "ru", "ron": "ro",
    "ell": "el", "fas": "fa", "por": "pt", "nld": "nl", "pol": "pl", "ukr": "uk", "kat": "ka",
    "hye": "hy", "heb": "he", "jpn": "ja", "kor": "ko", "zho": "zh", "hin": "hi", "urd": "ur",
    "bul": "bg", "ces": "cs", "srp": "sr", "hrv": "hr", "tuk": "tk", "uzb": "uz", "kaz": "kk",
    # --- 2026-06-20 EKLEMELER (forensik: eksik dil-kodu → ASR cokmesi) ---
    # iskandinav / baltik / kuzey
    "swe": "sv", "nor": "no", "nob": "no", "nno": "nn", "dan": "da", "fin": "fi",
    "isl": "is", "fao": "fo", "est": "et", "lit": "lt", "lav": "lv", "ltz": "lb",
    # bati/orta avrupa
    "slk": "sk", "slv": "sl", "cat": "ca", "glg": "gl", "eus": "eu", "oci": "oc",
    "cym": "cy", "bre": "br", "lat": "la", "mlt": "mt",
    # balkan / dogu avrupa
    "mkd": "mk", "sqi": "sq", "als": "sq", "bel": "be", "bos": "bs", "tat": "tt",
    "bak": "ba",
    # cince aileleri / dogu asya
    "cmn": "zh", "yue": "yue", "wuu": "zh", "nan": "zh", "hak": "zh",
    "vie": "vi", "tha": "th", "mya": "my", "khm": "km", "lao": "lo", "bod": "bo",
    # guney/guneydogu asya
    "ind": "id", "msa": "ms", "zsm": "ms", "jav": "jw", "sun": "su",
    "tgl": "tl", "fil": "tl", "ben": "bn", "tam": "ta", "tel": "te", "mar": "mr",
    "guj": "gu", "kan": "kn", "mal": "ml", "pan": "pa", "sin": "si", "nep": "ne",
    "asm": "as", "snd": "sd", "pus": "ps", "pbt": "ps",
    # orta asya / kafkas
    "mon": "mn", "tgk": "tg",
    # afrika
    "swa": "sw", "swh": "sw", "amh": "am", "hau": "ha", "yor": "yo", "som": "so",
    "afr": "af", "sna": "sn", "mlg": "mg", "lin": "ln",
    # diger
    "san": "sa", "yid": "yi", "hat": "ht", "haw": "haw", "mri": "mi",
}
def _map_lang(c):
    if c in _KURDISH:
        return "ku"
    return _LANG_MAP.get(c, c)


def audio_streams(video) -> list:
    """Her ses stream'inin kanal sayısı → [2, 2] = 2 stream, 2'şer kanal."""
    try:
        out = subprocess.run([str(FP), "-v", "error", "-select_streams", "a",
                              "-show_entries", "stream=channels", "-of", "csv=p=0", video],
                             capture_output=True, text=True).stdout.strip().splitlines()
        return [int(x) for x in out if x.strip().isdigit()] or [1]
    except Exception:
        return [1]


def extract(video, s, c, start, dur, dst) -> bool:
    # KRİTİK: ffmpeg başarısızsa (ses yok / kodek hatası / map tutmazsa) ÖNCEKİ filmden kalan
    # aynı-adlı (s_c_t) bayat wav'ı sınıflandırma → filmler-arası dil KONTAMİNASYONU. Önce hedefi
    # sil, sonra ffmpeg dönüş kodunu kontrol et. (TMP sabit ve filmler arası paylaşımlı.)
    try:
        dst.unlink()
    except FileNotFoundError:
        pass
    r = subprocess.run([str(FF), "-y", "-hide_banner", "-loglevel", "error",
                        "-ss", str(start), "-t", str(dur), "-i", video,
                        "-map", f"0:a:{s}", "-af", f"pan=mono|c0=c{c}",
                        "-ar", "16000", "-acodec", "pcm_s16le", str(dst)], capture_output=True)
    return r.returncode == 0 and dst.exists() and dst.stat().st_size > 1000


_MMS = None
_MMS_TRIED = False
def _get_mms():
    """MMS-LID'i BİR KEZ yükle (tekil). Yüklenemezse None → çağıran düşük-güvenle döner."""
    global _MMS, _MMS_TRIED
    if _MMS_TRIED:
        return _MMS
    _MMS_TRIED = True
    try:
        import torch
        from transformers import Wav2Vec2ForSequenceClassification, AutoFeatureExtractor
        fe = AutoFeatureExtractor.from_pretrained(MMS_MODEL)
        m = Wav2Vec2ForSequenceClassification.from_pretrained(MMS_MODEL)
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        m = m.to(dev).eval()
        _MMS = (fe, m, dev, torch)
        print("[info] MMS-LID yüklendi (dil tespiti)", file=sys.stderr, flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[uyarı] MMS-LID yüklenemedi: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        _MMS = None
    return _MMS


def _classify(wav):
    """wav → (2-harf dil, güven). MMS-LID yoksa (None, 0)."""
    mms = _get_mms()
    if mms is None:
        return None, 0.0
    fe, m, dev, torch = mms
    try:
        import librosa
        y, _ = librosa.load(str(wav), sr=16000, mono=True)
        inputs = fe(y, sampling_rate=16000, return_tensors="pt")
        inputs = {k: v.to(dev) for k, v in inputs.items()}
        with torch.no_grad():
            logits = m(**inputs).logits[0]
        probs = torch.softmax(logits, dim=-1)
        p, i = torch.max(probs, dim=-1)
        code3 = m.config.id2label[int(i.item())]
        return _map_lang(code3), float(p.item())
    except Exception:  # noqa: BLE001
        return None, 0.0


def _sample_into(video, s, c, times, votes, n):
    for t in times:
        smp = TMP / f"s{s}_c{c}_{int(t)}.wav"
        if not extract(video, s, c, t, SDUR, smp):
            continue
        lang, prob = _classify(smp)
        if lang and prob >= MMS_MIN:          # düşük güven = müzik/gürültü → oya KATMA (müzik-gate)
            votes[lang] = votes.get(lang, 0.0) + prob
            n[0] += 1


def detect(video, s, c) -> dict:
    votes, n = {}, [0]
    _sample_into(video, s, c, SAMPLES, votes, n)
    top = sorted(votes.items(), key=lambda x: -x[1])
    need_more = (n[0] < 2) or (len(top) >= 2 and top[1][1] >= AMBIG_RATIO * top[0][1])
    if need_more:
        _sample_into(video, s, c, EXTRA_SAMPLES, votes, n)
        top = sorted(votes.items(), key=lambda x: -x[1])
    if not votes:
        return {"stream": s, "channel": c, "language": None, "confidence": 0.0, "role": "efekt/sessiz",
                "mixed": False, "secondary": None, "label": "boş", "samples": n[0]}
    best, bv = top[0]
    conf = round(bv / max(1, n[0]), 3)
    secondary = top[1][0] if (len(top) >= 2 and top[1][1] >= MIX_RATIO * bv) else None
    role = "konuşma" if conf >= MIN_PROB else "efekt/zayıf"
    label = best.upper() if role == "konuşma" else "efekt"
    return {"stream": s, "channel": c, "language": best, "secondary": secondary, "mixed": secondary is not None,
            "confidence": conf, "role": role, "label": label, "samples": n[0],
            "votes": {k: round(v, 3) for k, v in votes.items()}}


def select_summary(units):
    """Özet/transkript kanalını seç. TR konuşma > diğer konuşma > (NET konuşma YOKSA) en iyi DİYALOG kanalı.
    KRİTİK: net konuşma yoksa DOWNMIX'e DÜŞME — en iyi kanalı seç (Çağatay + Cagatay_22.02 dersi)."""
    speech = [u for u in units if u["role"] == "konuşma"]
    tr = next((u for u in speech if u["language"] == "tr"), None)
    if tr:
        return tr, "türkçe konuşma kanalı → özet ondan"
    if speech:
        return speech[0], "türkçe yok → ilk konuşma kanalı, kendi dilinde"
    cand = [u for u in units if u.get("language")]
    tr_c = [u for u in cand if u.get("votes", {}).get("tr", 0) > 0]
    if tr_c:
        b = max(tr_c, key=lambda u: u["votes"]["tr"])
        return b, f"net konuşma yok → en çok TR-oylu kanal (conf {b['confidence']})"
    if cand:
        b = max(cand, key=lambda u: u["confidence"])
        return b, f"net konuşma yok → en güçlü diyalog kanalı ({b['language']}, conf {b['confidence']})"
    return {"stream": 0, "channel": 0, "language": None}, "ses yok → dil belirlenemedi"


def main():
    video = sys.argv[1]
    streams = audio_streams(video)
    print(f"[info] {len(streams)} stream, kanallar={streams}", file=sys.stderr, flush=True)
    units = []
    for s, nch in enumerate(streams):
        for c in range(nch):
            units.append(detect(video, s, c))
    summary, reason = select_summary(units)
    speech = [u for u in units if u["role"] == "konuşma"]
    others = [{"stream": u["stream"], "channel": u["channel"], "language": u["language"]}
              for u in speech if (u["stream"], u["channel"]) != (summary["stream"], summary["channel"])]
    print(json.dumps({
        "n_streams": len(streams), "channels_per_stream": streams,
        "units": units,
        "summary_stream": summary["stream"], "summary_channel": summary["channel"],
        "summary_language": summary["language"], "select_reason": reason,
        "lid_engine": "mms-lid-1024",
        "sesler_ic_ice": any(u.get("mixed") for u in speech),
        "ic_ice_diller": sorted({d for u in speech if u.get("mixed")
                                 for d in (u["language"], u.get("secondary")) if d}),
        "info_channels (bilgi için saklanır)": others,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
