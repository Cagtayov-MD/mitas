# GPT DEVİR — 4 FIX DURUMU (2026-07-12)

> Çağatay bu kısmı (aşağıdaki 4 fix) GPT'ye devrediyor. Süreç durduruldu, git-ağacı TEMİZ.
> **Zorunlu disiplin (Çağatay 3 prensibi):** her fix için (1) doğru şeyi mi düzeltiyor? (2) çalışan
> bir şeyi bozuyor mu? (3) daha iyi yolu var mı? — VE **fix'i o filmde YENİDEN KOŞUP çıktıda kanıtla.**
> Tarihsel hata: fix yazıldı ama film hiç yeniden koşulmadı → "kağıtta tamam ama çalışmıyor" (APOLLO 8 gün).

## Yeniden-koşu aracı (kaynak-video OFFLINE olduğu için)
```
python scripts/mitas_pipeline.py --from-hub "E:\MITAS\Database\<hub>" --run-root "E:\MITAS\candidate_runs\<test>"
```
- Üretim Database/export'a SIFIR-DOKUNUŞ (pilot kanıtlı); sonuç `<run-root>/Database/<hub>/_DURUM.json`.
- ASR kapalı (ASR_KAPALI.flag). Golden: `python scripts/regresyon_golden.py` (bilinen 6/7; BAŞKAN=veri-yok).

---

## 1) APOLLO 11 (1996-0222) — Part-1 BİTTİ, Part-2 AÇIK
**Yapıldı (commit be8ce7bf):** rescue artık "2ND UNIT DIRECTOR" garble'ından "ND UNIT" üretmiyor
(`_RSC_BAD_TOK += UNIT`; `_RSC_BAD_SUB += ASSIST/SUPERVIS/COORDINAT/OPERATOR`, credit_text_read.py:1879-1885).
Canlı kanıt: `_rsc_name_ok('ND UNIT')=False`, `('Norberto Barba')=True`. Test: test_credit_text_read_garble_gate.py.
**AÇIK (Part-2):** Gerçek yönetmen **NORBERTO BARBA** ham OCR'da VAR (kunye.txt L85, YETİM=etiketsiz) +
KB-teyitli (tt0115560). Boş-yönetmene GÜVENLE doldurulmalı (uydurma DEĞİL — ekranda var). Konum: pipeline/KB
katmanı (tek_film_kunye / credit_qc_block / credit_validate). **DİKKAT:** uydurma-yasak — yalnız ham-OCR'da
birebir varsa doldur. Part-2 yapılmadan APOLLO hâlâ Kontrol.

## 2) AFİŞ POLİTİKASI — AÇIK (Çağatay: "afiş yokluğu KONTROL sebebi DEĞİL")
**Kök:** credit_severity_router.py:153-154 `if sig.get("afis_missing"): hafif.append("AFIS")` → tier=
NEEDS_REVIEW_HAFIF → folder=KONTROL. Sinyal: mitas_pipeline.py:3407 `"afis_missing": any("afiş yok"...)`.
**İstenen:** afis_missing tier'ı ETKİLEMESİN (yalnız-afiş-eksik film → TEMIZ/ONAYLI); afiş yine warning olarak
görünsün (poster_fetch sonradan doldurur). **Regresyon:** afiş-eksik + AĞIR sorunlu film YİNE Kontrol kalmalı;
diğer HAFİF kodlar (CASING/GENRE...) etkilenmesin. Etkilenen: AĞAÇ, AŞK EVLİLİĞİ, BÜYÜK MÜCADELE, BİR ZAMANLAR
(+ muhtemel onlarca). En temiz: "AFIS"i hafif-listeden çıkar, ayrı warning_codes'a koy.

## 3) DENİZ EJDERİ (1990-0350) — AÇIK · YÜKSEK REGRESYON RİSKİ
**dalga-1 hükmü:** KOD·GEREKSİZ; kök `fold()` (credit_video_read.py:75-83 + ikizi credit_text_read `_fold`).
**DİKKAT:** `fold()`/`_fold()` MERKEZİ fonksiyon — tüm isim-eşlemede kullanılır; değişiklik TÜM filmleri etkiler.
Önce fold'un DENİZ'de tam ne yanlış-pozitif ürettiğini izole et, sonra minimal+golden-korumalı dokun. Kök tam
doğrulanmadı (fix-tasarım workflow'u yarıda kesildi).

## 4) BANA TRINITY DERLER (1968-0082) — AÇIK
**dalga-1 hükmü:** KOD·GEREKSİZ; tek_film_kunye.py:697-722 — kimlik-TEYİTLİ filmde ekranda OKUNAN yönetmen
gereksiz düşürülüyor (ekran-otorite ihlali). Kök tam doğrulanmadı (workflow kesildi). Doğrula + minimal fix.

---

## Kanıt/analiz dosyaları (GPT için)
- **15-film derin neden-analizi:** outputs/KONTROL_DERIN_NEDEN_RAPORU_2026-07-12.md (her Kontrol filmi: KOD/KARAR + GEREKLİ/GEREKSİZ + kanıt)
- Kalite tablosu: outputs/LEAN_NIHAI_TABLO_2026-07-11.json (118 promote-adayı) · outputs/FRAMES_RERUN_KALITE_FARKI_2026-07-11.json
- Kötüleşen-14 incelemesi: outputs/KOTULESEN_14_INCELEME_2026-07-11.md (LOTR gerçek-regresyon kökü dahil)
- Bugünkü gate-batch (yarım, 57/118): candidate_runs/gate_batch_20260712/_gate_batch_rapor.jsonl

## Genel not
Bugün altyapı (İP-0..İP-9 + from-hub + _reasoning-kaldırma) commit'li ve ölçülü (kuyruk %75→%37). Bu 4
içerik-fix'i AÇIK — GPT'ye devredildi. Her birinde 3-prensip + film-bazlı yeniden-koşu-kanıtı ŞART.
