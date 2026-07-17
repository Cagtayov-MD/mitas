# W2 ASR'siz Koşu — Fix Doğrulama Raporu (bitmiş 13 film)

**Tarih:** 2026-06-22 · **Yöntem:** 14-ajan workflow (salt-okuma) + flag-envanteri + empirik çıktı kontrolü · FINAL_RAPOR ile çapraz

## ⭐ ANA BULGU (tüm tablonun anahtarı)

**Bu koşu fix'lerin BÜYÜK KISMINI hiç devreye sokmadı.** Çünkü koşu sadece `--no-asr` ile başlatıldı; **hiçbir fix-flag set edilmedi** (doğrulandı: `MITAS_QC_BLOCK`, `MITAS_CAST_OCR_KEEP`, `MITAS_OCR_FORM_KEEP`, `MITAS_QC_NONCAST_FILTER`, `MITAS_QC_FLOORFILL_OCRGUARD` → process/User/Machine env'de **BOŞ**).

Sonuç ikiye ayrılıyor:

### Devrede olan fix'ler (default-ON, QC_BLOCK'tan bağımsız) → hatalar DÜZELDİ
| Fix | Flag (default ON) | Etki |
|---|---|---|
| VL token-kalkanı | `MITAS_VL_RAW_ADJACENCY` | MANASLU "HANS EBNER" uydurma GİTTİ |
| garble stitch frekans-oyu | `MITAS_STITCH_FREQVOTE` + `EXTRACT_GATE_BEFORE_CAP` | KÖŞENİN KRALI "ANTHONV" garble GİTTİ |
| QC false-pos gevşetme | `MITAS_XMLCAST_GATE_RELAX` | KÖŞENİN KRALI gereksiz KIMLIK→OZET |
| crew-sızma savunması (5-katman, koşulsuz) | `_CREW_CONTEXT_KW` | KOMİSER Scénario + SIRILSIKLAM producer GİTTİ |
| Latin-dışı romanizasyon | `MITAS_NONLATIN_TRANSLIT/ROMANIZE` | (Latin-dışı filmlerde aktif) |
| bekçi text-OR / poster-gate | `MITAS_BEKCI_TEXT_OR` / `MITAS_POSTER_VER_GATE` | aktif |

### Devre-DIŞI fix'ler (ya `MITAS_QC_BLOCK` kapalı ya da flag default-OFF) → hatalar AYNEN SÜRÜYOR
| Fix | Neden kapalı | Etkilenen hata |
|---|---|---|
| LOST-ACTOR kurtarma (cast OCR-keep, cap-gevşet, floor-guard) | QC_BLOCK kapalı **+** flag default-OFF | DÖRT CENAZE Walken/Lee Evans, KULÜP EVİ "LEE", ÖLDÜREN POZ Susan Pari |
| name_close OCR-form koru | QC_BLOCK kapalı **+** `MITAS_OCR_FORM_KEEP` default-OFF | HAYATIN DENGESİ LEFEBVRE→LEFEVRE |
| C5 non-cast köprü | QC_BLOCK kapalı **+** `MITAS_QC_NONCAST_FILTER` default-OFF | OLAY YERİ crew→cast (kısmen) |
| LID TR→KU vetosu | `--no-asr` ASR dalını komple atlıyor → veto ÖLÜ | (Latin-dışı/ASR-bağımlı) |
| TR-dublaj seslendiren | bu sınıf için fix/flag **hiç eklenmemiş** | BÜLBÜL (henüz bu koşuda yok) |

**Yani: "kaçak" değil — fix'in yarısı bu koşuda hiç açılmadı.** Açık olanlar çalıştı, kapalı olanların hedeflediği hatalar değişmeden duruyor.

---

## Bitmiş 13 film — empirik hüküm

### ✅ DÜZELDİ (6) — açık fix işe yaradı
- **MANASLU** — "HANS EBNER" uydurma oyuncu GİTTİ; doğrusu HANNELORE EBNER (OCR'da 6× bitişik). VL-kalkanı (commit 112124286e) çalıştı.
- **KÖŞENİN KRALI** — "ANTHONV MACTROMAURO" garble → "ANTHONY MASTROMAURO" (frekans-oyu); gereksiz KIMLIK→OZET'e döndü.
- **KOMİSER CORDIER** — "Scénario / Marc-Antoine Laurent" (Fransız senarist) cast'ten KALKTI; yerine gerçek oyuncu Claire Février.
- **SIRILSIKLAM** — yapımcı alanı temiz (BEN SILVERMAN sızmadı, ROBERT SIMONDS doğru PRODUCED BY).
- **GEÇMİŞİN GÖLGELERİ** — 5/8 KB-şişme GİTTİ; cast artık OCR-otoriter (Ving Rhames + Ja Rule).
- **YAĞMUR** — SCOTT COOPER cast'te (3 yüzeyde de), .txt↔PDF yönetmen birebir aynı (Wilson), divergence yok.

### ✅ ZATEN TEMİZ KALDI (2)
- **RED ROCK** — cast doğru (Caan/Carradine/Gyllenhaal); footage-bloat cast'i etkilememiş.
- **KLEPTOMAN** — temiz; ANDY WINDERBAUM KB-eklentisi belgeli-beklenen (OCR'da yok ama bilinen davranış).

### 🟡 KISMİ (1)
- **HAYATIN DENGESİ** — KIM BERLIN bozuk-form GİTTİ; **AMA LEFEBVRE→LEFEVRE ezme teslim PDF'inde HÂLÂ var** (iç kunye.txt/md doğru "LEFEBVRE" ama nihai PDF render "LEFEVRE"e eziyor). name_close fix kapalı.

### 🔴 HÂLÂ VAR / KAÇAK (3) + 1 REGRESYON
- **DÖRT CENAZE** — Christopher Walken + Lee Evans (OCR'da 28×/40×) HÂLÂ 8-cap'te düşük; JOSH→JOSHUA ezme HÂLÂ. Hem KONTROL hem ONAYLI PDF'te.
- **KULÜP EVİ** — "JAIMEE LEE WYSON"→"JAIMEE WYSON" (LEE düştü) teslim PDF'inde HÂLÂ; ayrıca DELANY WESTFALL oyuncusu komple düşmüş. (İç md doğru, ezme sadece PDF render'ında.)
- **OLAY YERİ** — başrol kaybı HÂLÂ (Manchen/Held/Broumis master'da var, OCR'da 0); crew→cast sızma sürüyor (senarist Daniel Martin Eckhart 1. oyuncu). **Önemli:** bekçi text-OR açık olsa bile işe yaramadı — darboğaz frame-seçimi değil, o text-over-footage karelerinin OCR'ının **hiç metin döndürmemesi** (OCR-recall problemi, flag çözmez → re-OCR/farklı yaklaşım gerekir).
- **ÖLDÜREN POZ** 🔻 — negatif-kontrol olması gerekirken **REGRESYON**: SUSAN PARI (OCR'da 34×, baş-rol) düştü, 8→7 cast. Önceki koşu 8 veriyordu. (Lost-actor/cap fix kapalı.)

---

## Not: bayat artefakt riski
Birkaç filmde export'ta ESKİ koşudan kalma ikinci PDF var (ör. KOMİSER eski ONAYLI'da hâlâ sızıntılı; DÖRT CENAZE/ÖLDÜREN POZ eski ONAYLI/HAFIF_AFIS). `_DURUM.json` güncel KONTROL dosyasını işaret ediyor ama eski dosyalar silinmedi → karşılaştırmada yalnız `_DURUM`'un işaret ettiği dosyaya bakılmalı.

## Sonuç ve öneri
- **Bu koşu fix'leri tam test ETMEDİ.** Sadece default-ON olanlar değerlendirilebildi (ve çoğu başarılı). Flag-kapılı aile (lost-actor, name-form-keep, non-cast-köprü) hiç açılmadı.
- Fix'leri gerçekten A/B test etmek için koşu şu env ile tekrarlanmalı:
  `MITAS_QC_BLOCK=1 MITAS_CAST_OCR_KEEP=1 MITAS_OCR_FORM_KEEP=1 MITAS_QC_NONCAST_FILTER=1 MITAS_QC_FLOORFILL_OCRGUARD=1`
- **İstisna:** OLAY YERİ tipi başrol kaybı flag ile çözülmez (OCR o kareleri hiç okumuyor) — re-OCR/frame-stratejisi gerekir.
- Kalan 29 film tamamlandıkça aynı doğrulama 2. dalga olarak koşulacak (BEKARLIK, KEDİ GÖZÜ, HABABAM, BÜLBÜL, FEDORA dahil — 4 CRITICAL bunlarda).
