# Iverson — ASR transkript kulesi

> **ffmpeg çıktısı ses → transkript.** MAP'te planlı `iverson` satırının
> Faz 1'i (Faz 2: özet üretimi + tam run_asr_pipeline/diarize — bekliyor).
> Film/dizi üretim lean yolunun (scripts/_pipe_asr `_lean_transcribe`) bağımsız
> yeni evi: large-v3-turbo, beam=1, VAD on, CUDA float16 → CPU int8 fallback.

## Sorumluluk sınırı

**Yapar:** bir ses dosyasını (16k mono wav önerilir — sheriff media_prep kalıbı;
diğer sesli formatlar da olur, kule 16k mono'ya indirir) transkribe eder;
kararını + transcript dosyalarını kendi `out/` klasörüne yazar. Çok-stream
girdide istenirse MMS-LID kanal-dil tespiti yapar (TR kanalı seçer, Kürtçe
yanlış-tespitini menşeyle veto eder).

**Yapmaz:** özet üretmez (Faz 2), künye okumaz, diarize/align yapmaz (Faz 2 —
tam motor), PDF yazmaz, sheriff'e kayıt yaptırmaz.

## Çalıştırma

Kule kendi çalışma zamanını kendi bulur — venv (258 pin, venvs/asr birebir)
ve model ağırlıkları (9.6G) KULE İÇİNDE:

```bash
# TEK — 16k mono wav (sheriff media_prep çıktısı)
Allstar/iverson/iverson tek --girdi /yol/ses.wav --film-id 2025-1307-1-0000-50-0

# TEK — çok-stream video + MMS-LID kanal-dil tespiti
Allstar/iverson/iverson tek --girdi film.mkv --film-id X --lid

# TOPLU — kaldığı yerden devam eder, _TAMAM olanı atlar
Allstar/iverson/iverson start --input in/
```

Çıktı daima `out/<film_id>/iverson.json` + `_TAMAM` (+ `transcript.txt`
[HH:MM:SS] satırlar, `transcript_plain.txt` düz metin, `chlang.json` dil
tespiti varsa).

## Sözleşme

| durum | Anlam |
|---|---|
| `TRANSKRIPT` | Transkript üretildi (segment > 0) — dil, model, kanal, süre kanıtta |
| `METIN_YOK` | Ses var, konuşma yok (sessiz/müzik) — **içerik gerçeği** |
| `DIL_DESTEKSIZ` | Kürtçe-ailesi / whisper-dışı dil — dürüst atlama (özet internetten notu) |
| `ARIZA` | Koşu arızası — `sinif`+`mesaj` zorunlu (GIRDI/MODEL_YOK/FFMPEG/MOTOR). **ARIZA asla içerik gerçeğine dönüşmez** |

Motor kuralları (üretim lean yoluyla birebir): TR/belirsiz dil → `large-v3-turbo`;
desteklenen yabancı → `large-v3` (tespit edilen dilde, beam=1);
`condition_on_previous_text=False`; VAD min_silence 500ms; CUDA float16 →
OOM'da CPU int8. LLM-VRAM sübabı (ollama) kulede default KAPALI — env
`MITAS_ASR_LLM_VALVE=1` ya da config ile açılır.

## Zemin ve kule-içi varlıklar

| Ne | Yer | Not |
|---|---|---|
| Whisper ağırlıkları (5.9G) | `model/faster-whisper/{large-v3,large-v3-turbo,...}` | kule kopyası — MAP ağırlık-zemin ilkesine bilinçli istisna (kullanıcı talimatı: her şey içeride) |
| MMS-LID (3.7G) | `model/hf/hub/models--facebook--mms-lid-1024` | HF_HOME kule-içi; `--lid` ile |
| Çalışma zamanı | `venv/` (py3.10.20, 258 pin) | venvs/asr birebir freeze, `--no-deps` kurulum (el-le-yönetilen ortamın birebir çoğaltımı) |
| ffmpeg | sistem (env `MITAS_FFMPEG` ile değişir) | kobe/sheriff kalıbıyla aynı zemin aracı |
| speechbrain LID (venvs/asr'daki) | YOK | scripts/motor yolu MMS-LID kullanır; voxlingua modeli zaten ölü Windows symlink'idir |

## Yerleşim

| Ne | Yol |
|---|---|
| Motor (lean transkript) | `src/motor.py` (kaynak: scripts/_pipe_asr `_lean_transcribe`) |
| Kanal-dil tespiti (MMS-LID) | `src/channel_lang.py` (kaynak: scripts/_channel_lang.py) |
| Sözleşme | `sozlesme.py` |
| CLI + koşu akışı | `main.py`, `iverson` |
| Testler | `tests/` (sözleşme, motor-fake, izolasyon) |
| Dokümanlar | `DURUM.md`, `CHANGELOG.md` |

## Testler

```bash
cd Allstar/iverson && ./venv/bin/python -m pytest tests/ -q
```

Motor testleri faster_whisper'ı fake'ler — GPU/model gerekmez.

## Çift-kopya dönemi

scripts/_pipe_asr.py + venvs/asr **yerinde kalır**; üretim değişmez. Kule
gölgedir. Söküm, pipeline Iverson'a bağlanınca ayrı iş.
