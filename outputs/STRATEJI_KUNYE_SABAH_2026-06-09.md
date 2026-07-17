# KÜNYE-FIX SABAH STRATEJİSİ — 2026-06-09 gece sonrası
**Amaç: gece koşusunda ortaya çıkan credit (yön/yap/cast) sorunlarını sabah HIZLI ve KESİN çözmek.**

---

## 0. META-DERS (en önemlisi — Çağatay'ın haklı uyarısı)
"Her şeyden emin ol" denmişti; ben **logic-testi** yaptım (pipeline_v2, fail-safe, tiebreak) ama **gerçek filmde uçtan-uca çıktıyı AÇIP GÖRMEDİM** + filtre zayıflığını + koşu-eski-kod ihtimalini kaçırdım. **Kalıcı kural (P6):** hiçbir production-launch, gerçek 3 filmde FULL pipeline + **çıktı PDF'i açıp gözle doğrulama** + git-HEAD-canary olmadan "hazır" denmez. "Logic OK" ≠ "çıktı doğru".

---

## TESPİT EDİLEN 6 PROBLEM (kök-nedenli)

| # | Problem | Kök neden | Kanıt |
|---|---|---|---|
| **P1** | Koşu yeni kodu kullanmıyor olabilir | asr_server PID commit'ten ÖNCE başlamış / stale `__pycache__` | "AND"li garble koşuda elenmemiş, re-run'da elenmiş |
| **P2** | KESİN KURAL ZAYIF — çok-kelimeli garble geçiyor | `_only_persons` yalnız tek-token + blocklist yakalıyor | "AVIS - SODAME BRANDT", "DEXTER GORDON DALE TURNER", "BERTRAND TALL" hepsi geçti |
| **P3** | VL az-tetikleniyor | tetik ham yönetmene bakıyor (garble=dolu→VL atlanıyor), sonra garble temizlenip boş kalıyor | Round Midnight: garble-yön → VL yok → render boşalttı → KONTROL |
| **P4** | Final künye filtrelenmemiş kaynaktan | `tek_film_kunye` raw credit_parse / video_credits'i KESİN-KURAL'sız render ediyor | kunye_teslim.md raw garble, credit_text_read re-run'ı temizdi |
| **P5** | OCR yavaş (~9-10 dk/film) | 840-kare CLIP-tarama + stitch (2sa film) | ilk film 15 dk; glm-ocr %100 GPU sürekli |
| **P6** | Uçtan-uca doğrulama disiplini yok | bkz Madde 0 | gece sorunları |

---

## ÇÖZÜM STRATEJİSİ (sıralı; her biri NASIL + DOĞRULAMA)

### Aşama 0 — KOD-TAZELİĞİ GARANTİSİ (P1) · ~10 dk
1. `__pycache__` temizle (yapıldı) + `start_mitas.ps1` ile temiz restart.
2. **RUNTIME CANARY ekle:** `mitas_pipeline` başında `git rev-parse HEAD` log'la → her filmde "hangi commit koşuyor" görünür. (Bir daha "eski kod mu" belirsizliği olmaz.)
3. **Doğrulama:** 1 film koş → log'da HEAD imzası + çıktıda "AND"li garble ELENMİŞ mi.

### Aşama 1 — CREDIT FİLTRE + KB-DOĞRULAMA (P2 + P4) · ASIL İŞ ~1.5-2 sa
**Strateji: garble'ı kör-filtreyle ayıklamaya çalışma (BERTRAND TALL isme benziyor) → film-kimliğiyle KB-CROSS-CHECK yap.**
1. **Hızlı kazanım (önce):** `_valid_person_name`'e ekle — " - " (boşluklu tire), tek-harf bağımsız token, 4+ ardışık ALL-CAPS-fragment reddi → "AVIS - SODAME BRANDT", "M FRANCE - SELMER" düşer.
2. **ASIL: film-özel-KB cross-check (ertelenen rung-d):** OCR cast'iyle IMDB başlığını eşle → o filmin OTORİTER yön/yap/cast'ini çek → OCR isimlerini bununla DOĞRULA:
   - OCR ismi KB-kişisiyle eşleşiyor (fuzzy) → kanonik yazımla TUT ("Bertrand Tall"→"Bertrand Tavernier").
   - Eşleşmiyor + KB'de yok → AT ("Dexter Gordon Dale Turner" = oyuncu+karakter, kişi değil → düş).
   - Rol uyumsuz (Scorsese=oyuncu/kameo bu filmde, yönetmen değil) → yönetmenden düş.
   - [[feedback_jenerik_otorite]]: KB EZMEZ, sadece doğrular/yazım düzeltir/eksik-ekler; OCR cast otorite.
3. **Final künye TEK kaynak:** `tek_film_kunye` SADECE filtrelenmiş+doğrulanmış video_credits kullansın; `_only_persons`'ı render-öncesi yön/yap/cast'e DE uygula (raw credit_parse'ı künyeye sokma).
4. **Doğrulama (çok-örnekli, ZORUNLU):** Round Midnight + 5 zor yabancı + 5 temiz Türk filmi → çıktı PDF'lerini **AÇ-GÖR** (yön/yap/cast temiz mi, garble kalmadı mı).

### Aşama 2 — VL TETİK SIRASI (P3) · ~30 dk
1. Yönetmen KB-doğrulamasını **VL tetiğinden ÖNCE** çalıştır. Tetik koşulu: "**DOĞRULANMIŞ** yönetmen yok VEYA cast<3" → VL.
2. Böylece garble-yönetmen önce temizlenir → boş kalır → VL devreye girer (kareden gerçek yönetmeni dener) → o da olmazsa KONTROL.
3. **Doğrulama:** garble-yönetmenli filmde `credit_vl_fallback` olayı düşüyor mu (log) + VL doğru yönetmeni buluyor mu.

### Aşama 3 — OCR HIZLANDIRMA (P5) · ~1 sa
1. **Stage-timing logu ekle:** `_pipe_ocr`/pipeline100'de CLIP-probe / OneOCR / stitch / GLM-consensus her birinin sn'sini bas.
2. 2-3 örnek filmde profille → **en ağır stage** kesin belirlensin (tahmin: 840-kare CLIP-probe).
3. **Kare örneklemeyi azalt** (840 → ~200; jenerik kartları yine yakalanır — credit başta+sonda) VEYA en ağır stage'i optimize et (CLIP embedding batch, ardışık-aynı-kart dedup). Hedef: ~9dk → **~3-4 dk**.
4. **Doğrulama:** aynı filmde önce/sonra HIZ + credit-kalite (kart kaçırmadı mı).

### Aşama 4 — DOĞRULAMA DİSİPLİNİ (P6) · kalıcı kural
Launch checklist (her seferinde):
- [ ] git HEAD canary log'da görünüyor (koşan kod = beklenen commit).
- [ ] 3 gerçek film FULL pipeline'dan geçti (logic değil, gerçek).
- [ ] Çıktı PDF'leri AÇILDI-GÖRÜLDÜ (yön/yap/cast/garble).
- [ ] Çok-örnek: zor-yabancı + temiz-Türk + Kürtçe.
- [ ] Süre ölçüldü (film/film).

---

## SIRA + SÜRE (sabah)
Aşama 0 (10dk) → **Aşama 1 (asıl, 1.5-2sa)** → Aşama 2 (30dk) → ara test → Aşama 3 (1sa) → final çok-örnekli doğrulama. Toplam ~4-5 sa, ama Aşama 0+1 ilk 2 saatte en büyük kazanım.

## BU GECE (devam ediyor)
- **Özetler düşüyor = asıl teslim güvende.** Credit garble → KONTROL → öteki Opus internetle düzeltiyor.
- Sabah credit'i bu stratejiyle TOPLU + KESİN düzeltir, biten filmleri yeni kodla yeniden-render ederiz.

## DOSYALAR / KOD NOKTALARI
- Filtre: `scripts/credit_text_read.py` (`_valid_person_name`, `_only_persons`)
- Final künye: `scripts/tek_film_kunye.py` (yön/yap/cast assembly + credit_kb_lookup)
- VL tetik: `scripts/mitas_pipeline.py` (BLOK VL-FALLBACK ~satır 740)
- VL modül: `scripts/_pipe_credit_vl.py` (tiebreak)
- OCR: `scripts/_pipe_ocr.py` + `OCR-worktree/py/pipeline100` (CLIP/stitch)
- KB: `Y:\DIGER\Mitas_Files\IMDB\db\imdb.duckdb`
- Tasarım: `outputs/TASARIM_KUNYE_PIPELINE_v2.md`
