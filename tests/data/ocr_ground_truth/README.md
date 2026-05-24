# OCR Ground Truth — Manuel Etiket Seti

Bu klasör, OCR pipeline'ının V1 (text-first) mimarisini değerlendirmek için kullanılan **altın referans** etiketlerini tutar.

**Format:** JSON (konuşma kararı 2026-05-24 — proje genelinde tek format)
**Sahip:** Çağatay (manuel etiketleme), Opus IMDB öncüsel öneri (opsiyonel)
**Tüketici:** `tests/test_ocr_regression.py`

---

## Dosya kuralları

- **İsim:** `<video_id>.json` (manifest item id ile aynı)
- **Karakter seti:** UTF-8
- **Konum:** `tests/data/ocr_ground_truth/`
- **Versiyonlama:** Her etiket dosyası `schema_version`, `created_at`, `created_by` field'larıyla başlar

## Şu anki film seti (Faz 3, V1 başlangıç)

10 film hedef:

| # | Video ID | Test ettiği şey |
|---|---|---|
| 1 | `xmen_2000_end_credits` | Uzun siyah BG scroll (en zengin örnek, 238 satır referans) |
| 2 | `kukla_adam_1989_end_credits` | Statik kart serisi (D kategorisi, role\|name split) |
| 3 | `anjelik_ve_sultan_1968_end_credits` | Hareketli BG + scroll (zor durum, 55 satır referans) |
| 4 | `franny_2003_end_credits` | Kısa kart (hareketli BG + sabit text, son 30sn) |
| 5 | `pororoca_2017_end_credits` | Scroll bitiş (detector ıskalamış vakası) |
| 6 | `jurassic_park2_1997_end_credits` | Uzun siyah BG scroll (271 satır referans) |
| 7 | `robinson_crusoe_2025_end_credits` | Modern animasyon scroll (176 satır referans) |
| 8 | `barbarlari_beklerken_2019_end_credits` | Uzun modern film scroll (309 satır referans) |
| 9 | `yari_sert_1977_end_credits` | A-fb fallback senaryosu (composite BROKEN_NO_TEXT) |
| 10 | `cennetin_rengi_1999_end_credits` | A-fb fallback senaryosu (composite BROKEN_BLACK) |

V1 sonrası ek 5-10 film daha eklenecek (canlı çeşitlilik için).

---

## JSON şablonu

```json
{
  "schema_version": "1.0.0",
  "video_id": "xmen_2000_end_credits",
  "source_path": "E:/filmtest/aaaa/evoArcadmin_..._X-MEN.mp4",
  "created_at": "2026-05-24",
  "created_by": "cagatay",
  "notes": "Manuel etiketleme. start/end_sec değerleri frame inspection ile belirlendi.",
  "expected_segments": [
    {
      "segment_id": "closing_scroll",
      "start_sec": 5723.0,
      "end_sec": 6000.0,
      "type": "scroll_credit",
      "min_line_count": 200,
      "must_contain_text": [
        "ROSS FANGER",
        "LEE CLEARY",
        "DREW PETROTTA"
      ],
      "confidence_min": 0.80,
      "notes": "IMDB ile teyit edildi. ROSS FANGER → Unit Production Manager."
    },
    {
      "segment_id": "opening_intertitle",
      "start_sec": 12.0,
      "end_sec": 25.0,
      "type": "card",
      "must_contain_text": ["20TH CENTURY FOX", "MARVEL"],
      "notes": "Stüdyo logo kartları."
    }
  ]
}
```

---

## Regression test mantığı

`tests/test_ocr_regression.py` her etiket dosyası için:

1. Pipeline'ı koş (manifest = bu film, kind = film_credits)
2. Çıktıdaki `events[]` listesini al
3. Her `expected_segments[i]` için:
   - Zaman aralığı içinde event'ler bul (start_sec ± tolerance)
   - Type eşleşmeli
   - `must_contain_text` listesindeki her string en az 1 event'in text'inde geçmeli (case-insensitive partial match — OCR harf bozulmaları için)
   - Toplam line_count `min_line_count` üstünde olmalı (scroll için)
   - Confidence ortalama `confidence_min` üstünde olmalı

Başarısızsa test fail → regression yakalanır.

---

## Doldurma süreci

1. **Opus öncüsel öneri (opsiyonel):** Çağatay isterse Opus'a "X-MEN için ground truth template doldur" der → Opus IMDB'den cast/crew çeker, mevcut OCR çıktısından zaman aralıkları önerir, template doldurur.
2. **Çağatay onayı:** Çağatay önerilen değerleri gözden geçirir, video'da spot check yapar, gerekirse düzeltir.
3. **Commit:** Etiket dosyası master'a alınır, regression test'e dahil olur.

Tahmini emek: 10 film × 20-30 dk = 3-5 saat toplam.
