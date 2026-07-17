# 5-FİLM KOŞTUR-TEYİT RAPORU (2026-07-12)

> GPT'nin (Codex) `35d7fa96` commit'i (kontrol-queue-hardening, 4-film+APOLLO fix + altyapı) —
> `from_hub_batch` ile **gerçek frame/artifact zinciriyle** yeniden koşuldu. 117 unit-test yeşil,
> ardından 5 film uçtan-uca. candidate: `candidate_runs/verify5_20260712` (üretime SIFIR-dokunuş).

## Sonuç: 3/5 TAM düzeldi · 2/5 hedef-alan düzeldi ama YANLIŞ-Kontrol'de takılı

| Film | Eski | Yeni | Yönetmen (künye) | Verdict |
|---|---|---|---|---|
| BANA TRINITY DERLER | Kontrol | **Hazır** ✅ | E. B. CLUCHER | TAM DÜZELDİ |
| BÜYÜK MÜCADELE | Kontrol | **Hazır** ✅ | MICHAEL DARLOW | TAM DÜZELDİ (afiş-only→warning) |
| BİR ZAMANLAR | Kontrol | **Hazır** ✅ | SIMON CURTIS | TAM DÜZELDİ (afiş-only→warning) |
| APOLLO 11 | Kontrol | Kontrol ❌ | **NORBERTO BARBA** (doğru!) | YANLIŞ-Kontrol → KOD |
| DENİZ EJDERİ | Kontrol | Kontrol ❌ | **AGUST GUDMUNDSSON** (doğru!) | YANLIŞ-Kontrol → KOD-şüpheli |

**3 film unit-test + uçtan-uca tam doğrulandı — bunlar promote-hazır.**

---

## APOLLO 11 — KOD, GEREKLİ (yanlış YONETMEN-Kontrol)
- GPT'nin Part-2'si **çalıştı**: gerçek yönetmen **NORBERTO BARBA** ham-OCR'dan restore edildi, künyede temiz,
  `qwen_qc.yonetmen_var=true`.
- **AMA** `credit_validate.yonetmen.status=OKUNAMADI` (restore-ÖNCESİ garble'ı görmüş) →
  mitas_pipeline.py:3377 `reasons.append("yönetmen doğrulama: okunamadı")` → credit_severity_router.py:198
  `yon_garble=True` → `agir=[YONETMEN]` → Kontrol.
- **Kök:** restore (tek_film_kunye.py:804 `_ocr_corroborated_directors`) künye katmanına yazıyor ama
  routing'in okuduğu `cv_result`/`reasons`'a yansımıyor. İki katman çözüm-öncesi/sonrası ayrık.
- **Tek agir bu** → router restore'u tanısa APOLLO **Hazır**. Fix: yönetmen ham-OCR'dan corroborate
  edildiğinde "okunamadı" nedeni ÜRETİLMEZ/temizlenir (routing corroboration'ı görsün).

## DENİZ EJDERİ — KOD-şüpheli, GEREKLİ (yanlış KIMLIK-Kontrol)
- Nordik katlama **çalıştı** (AUGUST→Ágúst Guðmundsson, `kimlik_dogru=True`).
- KB cross-check **DOĞRU filmi buldu**: `eslesen_film="Sea Dragon" 1990`, **`cast_ortusme=6`** (8 okunandan),
  otoriter_yonetmen ve otoriter_cast eşleşiyor, `fuzzy...kimlik_dogru=True`.
- **AMA** `kb.external_lookup verdict="ÇELİŞKİ"` kalmış → routing `"kimlik çelişkisi / cast-örtüşmesi 0"`
  diye blokluyor. **6 örtüşme + kimlik_dogru=True varken verdict neden ÇELİŞKİ?** — bu tutarsızlık incelenmeli:
  ya verdict-mantığı bayat (KOD, düzeltilir → Hazır), ya da başka bir gerçek sebep (başlık Deniz Ejderi↔Sea
  Dragon insan-teyidi) var (KARAR). Route'daki "0", KB'nin "6"sıyla çelişiyor → sinyal-tesisatı şüpheli.

## Ortak mimari desen (İKİSİNDE DE)
Severity-router, **sonraki bir aşamanın çözdüğü** alanın **çözüm-öncesi bayat sinyalini** okuyup blokluyor:
- APOLLO: yönetmen restore edildi ↔ router garble-öncesini okuyor.
- DENİZ: kimlik teyit edildi (kimlik_dogru=True) ↔ router ÇELİŞKİ-verdict'ini okuyor.
Bu, tek-noktadan çözülebilecek bir "oku-sonra-çöz" (read-after-resolve) dikişi olabilir.

## Öneri / karar noktası
İki fix de **severity-router / credit_validate / KB-verdict** çekirdeğine dokunur — bu, TÜM ~271 filmin
Hazır/Kontrol kararını veren en yüksek-regresyon-riskli bileşen. Aceleye getirmeden, golden + hedef-cohort
+ negatif-kontrolle yapılmalı. **Çağatay'ın onayıyla** ikisini sırayla, her birini kendi filminde yeniden-koşup
kanıtlayarak yapabilirim. 3 tam-düzelen film (TRINITY, BÜYÜK MÜCADELE, BİR ZAMANLAR) zaten promote-hazır.
