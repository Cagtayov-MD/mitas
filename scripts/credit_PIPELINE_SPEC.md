# MITAS Künye Pipeline — Netleşmiş Mimari (2026-06-14)

Çağatay ile oturumda netleşen tam akış. Amaç: yön+yapımcı+cast doğru + özet + afiş; yanlış asla → şüpheli KONTROL.

## Akış (kademeli, QC-kapılı)
```
KADEME 1 — KİŞİLER (cascade)
  1. OneOCR oku (pipeline100 stitch)
  2. fuzzy-match + DB düzelt   (credit_fuzzy_qc.py: OCR isimlerini IMDb/Wikidata gerçek-kadroya snap'le)
  3. QC1: yönetmen + yapımcı + oyuncu tam/doğru mu?
        ├─ EVET → DEVAM
        └─ HAYIR (red-ORANI yüksek  YA DA  kişi(ler) hatalı)
             → qwen2.5vl ile TEKRAR oku → fuzzy+DB → QC1
                  ├─ EVET → DEVAM
                  └─ HAYIR → KONTROL (insan)

ARADA EKLENEN KATMAN (kişiler onaylıysa)
  + ÖZET   : ASR transcript → _generate_ozet (Gemini→Sonnet→DeepSeek) → ozet_v4 kapısı
  + AFİŞ   : poster_fetch (TMDB, cast-doğrulamalı) → poster_ok kapısı (PORTRE-only)

KADEME 2 — QC2 (final, 5 kontrol → mitas_pipeline reasons motoru)
  • özet kontrolü        (ozet_v4 + "özet yok/kısa→KONTROL" + qwen-QC)
  • afiş kontrolü        (poster_ok PORTRE-kapısı; yatay frame-grab RED)
  • yönetmen-yapımcı     (kırmızı-çizgi: okunamazsa KONTROL; şüpheli/uzun isim)
  • oyuncu kontrolü      (cast-garble; XML-PDF cast-kesişimi=yanlış-film)
  • anahtar-sözcük       (credit_qc "anahtar" alanı garble-kontrol — EN HAFİF, güçlendirilecek)
  → reasons boşsa ONAY (Hazır), biri patlarsa KONTROL   (mitas_pipeline.py:1145)
```

## Bileşen durumu (2026-06-14)
| Aşama | Durum | Kanıt / dosya |
|---|---|---|
| OneOCR-stitch | ✅ canlı | _pipe_ocr.py / pipeline100 |
| fuzzy+DB düzelt | ✅ POC kanıtlı, flag-kapılı bağlanacak | credit_fuzzy_qc.py (BEYAZ BALİNA 9/9 düzeltti) |
| QC1 oran-red | ✅ POC | credit_fuzzy_qc.py (kaçırma>eşik → KONTROL) |
| qwen2.5vl eskalasyon | ✅ kanıtlı (TR 11/11), bağlanacak | ollama qwen2.5vl:7b + "iki-sütun" prompt şart |
| özet | ✅ canlı + kapılı | tek_film_kunye.py _generate_ozet + ozet_v4 |
| afiş | ✅ canlı + kapılı | tek_film_kunye.py poster_fetch + poster_ok |
| QC2 (5 kontrol) | ✅ 4 sağlam + anahtar hafif | mitas_pipeline.py reasons + credit_qc.py |

## Oturum kanıtları (model seçimi)
- **Kişi-okuma kazananı: OneOCR + fuzzy-DB** (kirli ama küçük hata; DB snap'le 9/9 düzelir, 0 yanlış-snap). qwen2.5vl 2.motor (TR 11/11 ama "iki-sütun" prompt şart, yoksa 0; çift-sütunda tek sütun okur).
- **Reddedilenler:** glm-ocr (mangle), 30b-thinking (ollama'da <think> patlar → boş), Qwen3-Omni native-video (LOOP+halüsinasyon — "Burak Cemre"×1024), InternVL (orta).
- **KURAL:** auto-fuzzy-düzeltme YALNIZ filmin GERÇEK kadrosuna (DB) yüksek-eşik snap; eşik altı = KONTROL (yanlış-snap=felaket, kanun). Tüm-arşivde kalibrasyon ŞART.

## Entegrasyon planı (flag-kapılı, güvenli)
1. credit_fuzzy_qc.py modülü repo'da (bu commit).
2. Flag `MITAS_FUZZY_DBQC=1` (default KAPALI) ile mitas_pipeline reasons'a bağla — KAPALI = sıfır regresyon.
3. N-film kalibrasyon ("sonra kontrol") → eşikler + yanlış-snap=0 doğrulandıktan SONRA aç.
4. qwen2.5vl-eskalasyonu QC1-red'de tetikle (sonraki adım).
