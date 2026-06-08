# KÜNYE PIPELINE — TANI, ONARIM VE TASARIM RAPORU
**2026-06-08 · Çağatay ile canlı oturum**

---

## 1. BAŞLANGIÇ: YARI SERT vakası
Tek bir künyede ("YARI SERT" = *Semi-Tough* 1977) üç sorun: cast'te garble ("ROGER", "MOSTEY" = bölünmüş "Roger E. Mosley"), yönetmen+yapımcı yok, orijinal ad yok. İlginç: eski VLM koşusunda (`outputs/credit_video/...`) Michael Ritchie + David Merrick + doğru cast **vardı** — ama PDF'i yeni metin-okuyucu üretmiş ve çuvallamış.

## 2. DENETİM: 43 künye, internet gerçek-zemine karşı
86 ajanlı workflow (`kunye-groundtruth-audit`). **Sonuç: 43/43 sorunlu — 38 kritik, 0 temiz.**

| Arıza | Kaç film |
|---|---|
| yönetmen yok | 31/43 |
| crew→cast sızıntısı | 31/43 |
| cast eksik | 31/43 |
| garble | 23/43 |
| yapımcı yanlış/yok | 24/43 |
| orijinal-ad yok | 10/43 |

Rapor: `outputs/DENETIM_43_KUNYE_2026-06-08.md`.

## 3. KÖK NEDEN (kanıtlı)
Üç baskın arıza (31/31/31) tek yere işaret etti: yeni künye-metin okuyucu `scripts/credit_text_read.py`.
- **D1 — Model zinciri "ilk-dolu kazanır":** gemma3:12b cast döndürünce (yönetmensiz, crew sızıntılı) zincir duruyor, qwen3:8b'nin bulduğu yönetmen (Lucas/Cimino) kayboluyor. Eski VLM'in ensemble+mutabakatı atılmış.
- **D2 — KB-doğrulama katmanı kaldırılmış:** crew cast'e sızıyor, başrol-oyuncuyu-yönetmen sanma (Walken/Redford) yakalanmıyor.
- **D3 — Garble/akla-yatkınlık filtresi yok:** "VAVIZ KARAKAC" OCR'da olduğu için `_guard`'tan geçiyor.

## 4. UYGULANAN ONARIMLAR (`scripts/credit_text_read.py`, COMMIT'SİZ)
1. **F1 — Ensemble:** `read_credits_auto` artık iki modeli de koşar, `_fuse_yonetmen` ile birleştirir (mutabakat→KB-onay→yoksa okunamadı).
2. **F2 — KB crew-filtresi:** `imdb.duckdb`; cast'ten KB'nin "oyuncu değil/ekip" dediğini atar (BEN BURTT vb. — 7 sızıntı temizlendi).
3. **F3 — Garble kapısı:** `garble_audit.looks_garble` + garble-varyant near-dup (VAVIZ KARAKAC ≈ YAVUZ KARAKAŞ → garble düşer).
4. **Self-consistency ayracı:** bir yönetmen adayını öneren model aynı ismi KENDİ cast'ine de koyduysa → başrol → düş (Redford düştü, Cimino korundu — KB'nin gürültülü meslek-etiketine değil, temiz kurala dayanır).
5. **Prompt rule-4:** yönetmen-etiket kalıpları eklendi — "A <İSİM> FILM" (ör. "A JOHN MCTIERNAN FILM"→McTiernan), "A FILM BY", YÖNETEN/REJİSÖR + assistant-director/DoP ayrımı. (İKİLİ OYUN, Sarayda Çocuk/Gottlieb, Uyanış, Kaçak, Kral Oidipus düzeldi.)
6. **think=False (qwen3):** düşünme modu + `format=schema` çakışıyordu; kapatınca yanlış-tahminler temiz-ABSTAIN'e döndü.
7. **KESİN KURAL — kişi-adı doğrulayıcı (`_valid_person_name` + prompt rule-0):** yönetmen/yapımcı/cast'te YALNIZ gerçek "İsim Soyisim" (≥2 kelime). Tek-token RED, marka/logo/şirket/sıfat/rol-etiketi RED, garble RED. İki katman: prompt (kaynakta) + blocklist (backstop). Birim-test 8/8.

## 5. MODEL KARŞILAŞTIRMASI

### Metin (43 film, düzeltilmiş prompt+think)
| Model | MATCH | WRONG | ABSTAIN | isabet% |
|---|---|---|---|---|
| gemma3:12b | 14 | 8 | 18 | 64% (recall yüksek, çok yanılır) |
| **qwen3:8b + think=False** | 13 | **2** | 25 | **87% (en iyi metin)** |

### Vision (metnin İKİSİNİN DE çuvalladığı 9 film — yönetmen kurtarma)
| Model | Kurtardı | Yanlış | Boş | Not |
|---|---|---|---|---|
| **qwen2.5vl:7b** | **7/9** | 1 (Redford) | 1 | hızlı (~35sn), başrol-gürültüsü ekliyor |
| **gemma4:26b** | **6/9** | 1 (Kar Kraliçesi) | 2 | temiz, güvenli (yanlış yerine boş), ağır (~70sn) |
| qwen3-vl:30b | — | — | — | tek film bile bitiremedi → PRATİK DEĞİL (24GB sınırda) |

Kurtarılanlar: Max Fischer, Francis Megahy, Michael Jenkins, Martin Gates, Peter Hyams, Irena Pavlásková, George Schaefer. İki vision **tamamlayıcı** (Kar Kraliçesi qwen✓/gemma✗).

**Çıkarım:** OCR-metin yolu, yönetmen kartı OCR'da temiz çıkmayan filmlerde YAPISAL olarak kör; **VL kareden okuyor (~%70).** Çözüm "metin mi vision mı" değil.

## 6. TASARIM: text-primary + VL-fallback (önerilen)
```
OneOCR+GLM metin → qwen ensemble (think=False, KESİN KURAL)
        ↓ QC kapısı
  yönetmen VAR + cast yeterli + temiz ───────► ONAYLI (text-only, hızlı)
  yönetmen YOK / cast<3 / garble ──► VL RE-READ (qwen2.5vl + gemma4)
        ↓ TIEBREAK MERDİVENİ (çelişkiyi ATMA, ÇÖZ):
          a) ikisi aynı → mutabakat
          b) çelişki → KB-onaylı (IMDB director) olanı seç   [Kar Kraliçesi'ni kurtarır]
          c) ikisi de onaysız → PES → Kontrol (dürüst)
        ↓ self-consistency (başrol-yönetmen ayıkla) + KESİN KURAL süzgeci
     çözüldü → ONAYLI ; çözülemedi → KONTROL
```
- VL **gap-filler** (metnin boş alanını doldurur), text'in güvenle okuduğunu **EZMEZ** ([[feedback-jenerik-otorite]]).
- VL yalnız abstain'de koşar (~%40 film) → maliyet amortismanlı ~25sn/film ortalama.
- Güven sırası (tek model): **gemma4:26b > qwen3:8b > qwen2.5vl** — ama en doğrusu katmanlı.

## 7. SÜRELER (yönetmen okuma)
qwen3:8b (metin) ~12sn · qwen2.5vl (vision) ~35sn · gemma4:26b (vision) ~70sn · qwen3-vl:30b pratik değil.

## 8. AÇIK / SONRAKİ ADIM
- **VL-fallback'i production pipeline'a bağlamak** (şu an sadece test scriptinde: `outputs/pipeline_v2_test.py`). `credit_video_read.fuse`'u abstain-tetikli dirilt.
- Hiçbir şey COMMIT'lenmedi — düzeltmeler working-tree'de.
- Kalan zor vakalar (Ağlıyorum/Waldo): ne metin ne vision okuyabildi → dürüstçe Kontrol.

## 9. DOSYALAR
- Onarım kodu: `scripts/credit_text_read.py`
- Denetim: `outputs/DENETIM_43_KUNYE_2026-06-08.md`, `outputs/kunye_audit_tier1.json`
- Ölçümler: `outputs/per_model_yon.py/.json`, `outputs/vl_recover_probe.py`, `outputs/pipeline_v2_test.py`
- Garble aracı: `outputs/garble_audit.py`
