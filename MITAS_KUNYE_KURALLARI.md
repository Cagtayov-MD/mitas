# MİTAS KÜNYE — KANUN (v4, kesin kurallar)
> Çağatay kararları, 2026-06-03/04. **Bağlayıcı, tartışmasız.** Tüm künye batch'leri (102, 103, …) buna uyar.
> Çelişki olursa bu belge esastır. Madde madde:

---

## A. PDF FORMAT (v4)
A1. **YAPIM EKİBİ = SADECE `Yönetmen` + `Yapımcı`.** Senaryo / Ortak Yapımcı / Görüntü Yönetmeni GÖSTERİLMEZ.
A2. Sol-ray teknik alan sırası: **TÜR**, **TOPLAM SÜRE**, **TRT KİMLİK**. (Çözünürlük sağ-üstte silik.) **KARE HIZI (fps) GÖSTERİLMEZ.**
A3. **SES & ALTYAZI** bloğu: konuşma kanalları (1./2./… KANAL = dil) + **ANA DİL** + **ALTYAZI (VAR/YOK)**. EFEKT kanalları gösterilmez.
A4. **Afiş**: IMDb güvenli eşleşme (poster_fetch). Bulunamazsa afiş yok. Yanlış afiş ASLA.
A5. **PNG ÜRETİLMEZ.** Yalnız PDF.
A6. Başlık = Türkçe yayın adı (büyük); alt başlık = orijinal-dil adı.

## B. BÜYÜK HARF / KASA (başlık, oyuncu, ekip, ÖZET — HEPSİ)
B1. Çıktının tamamı **BÜYÜK HARF.**
B2. **Türkçe sözcük/ad → Türkçe kasa:** i→İ, ı→I; **ç ğ ö ş ü KORUNUR** (GÜZELLİK, GENÇ, İÇİN).
B3. **Yabancı özel ad → SADECE ASCII:** i→I (İ DEĞİL), aksan düşer (é→E), Türkçe harf YOK (KATIE, JOSE, HOLLYWOOD).
B4. Türkçe ek yabancı ada Türkçe kuralla: HOLLYWOOD'A, KATIE'NİN.

## C. ÖZET (kanonik prompt: `E:\MITAS\_102_ozet_prompt_v2.md`)
C1. Kaynak: **web (Wikipedia olay örgüsü)** — köprü yöntemi (transkript yoksa).
C2. **4 cümle, 40–65 kelime. KISA + SADE. Süs/edebi kuyruk YOK.**
C3. Adlı+sıfatlı ana karakter açılışı + somut tetikleyici → neden-sonuç → **AÇIK SPOILER FİNAL (zorunlu).**
C4. YASAK: soru, ünlem, tırnak, köşeli parantez, klişe, karakter listesi, yumuşatma.
C5. TÜMÜ BÜYÜK HARF (bkz. B).

## D. İÇERİK / KÜNYE
D1. **Oyuncular:** en çok 8, jenerik (billing) sırası, gerçek oyuncu adları.
D2. **Yapımcı:** filmin GERÇEK yapımcısı (KİŞİ). Stüdyo/şirket DEĞİL; Türkçe dublaj/TRT personeli DEĞİL; executive/associate producer DEĞİL; yapım tasarımcısı DEĞİL.
D3. **TÜR:** Türkçe BÜYÜK HARF, en çok 2 ("/"), izinli liste: DRAM, KOMEDİ, KORKU, GERİLİM, AKSİYON, MACERA, BİLİM KURGU, ANİMASYON, WESTERN, ROMANTİK, SUÇ, POLİSİYE, SAVAŞ, TARİH, BİYOGRAFİ, MÜZİKAL, FANTASTİK, GİZEM, AİLE, BELGESEL.
D4. **MÜZİKAL HARİÇ:** TÜR=MÜZİKAL filmler teslim setine (KESİN ve SES_TEYIT) ALINMAZ → silinir.
D5. **ASLA UYDURMA.** Kimlik/veri kesinleşmezse boş bırak + ayır.

## E. SES / DİL / ALTYAZI  ← EN KRİTİK BÖLÜM
E1. **ANA DİL = whisper dil tespiti** (faster-whisper large-v3-turbo): her ses akışından 30sn örnekler, oy ver; ana_dil = bir akış TR ise TR, yoksa ilk konuşma dili. Conf = whisper olasılığı. **Bu bir TAHMİN, kanıt değil** → düşük güven/"—" şüpheli.
E2. **ALTYAZI = GÖRSEL OCR** (`scripts/_subtitle_detect.py`, alt-%20 bant PaddleOCR, venvs/ocr; ~40-60 örnek kare). **ffprobe altyazı-AKIŞI YETMEZ** — TRT yabancı filmleri GÖMÜLÜdür (hardsub), ffprobe görmez.
E3. **MANTIK KURALI: `ana_dil ≠ TR` ⟹ ALTYAZI VAR (zorunlu).** Yabancı-ses film TRT'de dublajsızsa mutlaka TR altyazılıdır (yoksa izlenemezdi).
E4. **TUTARLILIK TESTİ:**
   - `ana_dil = TR` → dublaj (altyazı genelde YOK). Makul.
   - `ana_dil ≠ TR` **+ OCR altyazı BULDU** → tutarlı, makul (orijinal dil + TR altyazı).
   - `ana_dil ≠ TR` **+ OCR altyazı YOK** → İNCELE (3 olasılık): **(1)** ana_dil yanlış — düşük güvenliyse TR dublajı yanlış okumuş olabilir → tüm akışları TR için yeniden tara, TR çıkarsa KESİN'e; **(2)** OCR kaçırdı (bant/Türkçe model); **(3) GERÇEKTEN orijinal-dil arşiv kopyası** (TR dublaj/altyazı yok). KESİNLEŞTİRME: birkaç KAREYİ AÇ-GÖR. Yüksek güvenli yabancı + kare-onaylı altyazısız = gerçek orijinal kopya (2026-06-04 ANJELİK: 0/60, kare-onaylı) → SES_TEYIT'te kalır, **uydurma TR atanmaz.** Disposition arşiv kararı.

## F. KADEMELEME + TESLİM
F1. **`*_KESIN` (teslim):** içerik QC TEMİZ + kimlik OK + özet tam BÜYÜK HARF + **ana_dil = TR** + müzikal değil. **TR-dil = "emin" (conf eşiği YOK).** (Çağatay 2026-06-04: "sadece emin = TR-dil olanları tut.")
F2. **`*_DIGER` (TR olmayan = ayrı klasör, teslimde DEĞİL):** `ana_dil ≠ TR` (yabancı + "—") olan HER film. Künyesi doğru olabilir ama TR-dil olmadığı için "emin" sayılmaz → ayrı tutulur (arşiv sonra karar verir). E-bölümü analiz içindir; teslim ayrımı budur.
F3. **`*_KONTROL` / silinen:** QC SORUNLU / kimlik doğrulanamadı / özet bulunamadı / video yok → teslim edilmez.
F4. **EKSİK OLMASI NORMAL.** Hedef tamlık değil, **temizlik/doğruluk.** Boşluk için uydurma YOK.

## G. QC (kalite)
G1. Akış: **üret → SALDIRGAN/tarafsız QC → işaretlenenleri düzelt → re-QC.** QC'nin işi onaylamak değil HATA BULMAK; "kontrol ettim" deyip geçmek YASAK.
G2. **XML çapraz-kontrol:** üretilen içerik kaynak XML kimliğiyle aynı filmi mi tarif ediyor (yanlış-eşleşme yakala).
G3. Teslimden önce **PDF'i AÇ-GÖR** (format + kasa + ses/altyazı tutarlılığı).

## H. TEKNİK
H1. `dur` = dosyanın ffprobe süresi. PAL 25fps yayın ≈ sinema süresinden ~%4 kısa → **HATA DEĞİL** (IMDb süresine göre "düzeltme" yapma).
H2. Aynı filmin birden çok dosyası (tekrar TRT kodu) → **trt'ye göre dedup.**
H3. Üretim/QC hep **paralel Sonnet ajanları/workflow** ile (ölçek). Resume'lu batch'ler.

## I. DOSYA/SCRIPT HARİTASI (102)
- Manifest: `scripts/_102_manifest.py` → `_102_manifest.json`
- Kanal-dil: `scripts/_102_chanlang_batch.py` + `_102_ses_redetect.py` (yoğun) → `_102_chanlang_all.json`, `_102_ses_redetect.json`
- **Altyazı (gerçek):** `scripts/_subtitle_detect.py` / `_102_altyazi_batch.py` (venvs/ocr, PaddleOCR) → `_102_altyazi.json`
- Özet promptu: `_102_ozet_prompt_v2.md`
- Render: `scripts/_102_render_kesin.py` (KESİN=TR) + `_102_render_sesteyit.py`
- Veri: `_102_master_FINAL.json`
- Render motoru: `OCR-worktree/pdf-mitas/_make_pdf.py` + `name_normalize.py` (kasa) + `poster_fetch.py` (afiş)
