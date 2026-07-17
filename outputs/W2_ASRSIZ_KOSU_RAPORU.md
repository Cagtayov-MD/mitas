# W2 ASR'siz Koşu Raporu

**Tarih:** 2026-06-22 · **Saat:** 19:22 · **Durum:** CANLI (sürüyor)

## Koşu Parametreleri
- **Kaynak:** `W:\23.05 sonrası FİLMLER\2` → seçili 42 film, öncelik sırasıyla
- **Mod:** ASR-hariç (`--no-asr`) — whisper hiç devreye girmez; özet üretilmez
- **Komut (her film):** `mitas_pipeline.py --video <f> --profile film_dizi --no-copy-source --no-asr`
- **Yapı:** Tek döngü, tek pipeline (eşzamanlılık YOK), her film bir kez, çift kopyada SAYFA1
- **Çökme/hata:** YOK

## İlerleme: 13/42 (~%31)

| # | Film | Karar | Yönlendirme / Etiket | Süre |
|---|------|-------|----------------------|------|
| 1 | RED ROCK HAPİSHANESİ | Kontrol | _OZET | 7.4 dk |
| 2 | HAYATIN DENGESİ | Kontrol | _OZET | 7.8 dk |
| 3 | SIRILSIKLAM AŞIK | Kontrol | _OZET | 13.2 dk |
| 4 | YAĞMUR | Kontrol | _OZET | 18.6 dk |
| 5 | MANASLU | Kontrol | **BELGESEL** + _YONETMEN_KIMLIK_OZET | 13.1 dk |
| 6 | DÖRT CENAZE BİR NİKAH | Kontrol | _OZET | 7.7 dk |
| 7 | ÖLDÜREN POZ | Kontrol | _OZET | 8.0 dk |
| 8 | KULÜP EVİ DEDEKTİFLERİ | Kontrol | _OZET | 7.5 dk |
| 9 | OLAY YERİ-BÜYÜK AŞK | Kontrol | **_KIMLIK**_OZET | 7.8 dk |
| 10 | KLEPTOMAN | Kontrol | _OZET | 7.1 dk |
| 11 | KÖŞENİN KRALI | Kontrol | _OZET | 8.2 dk |
| 12 | KOMİSER CORDIER KANDIRMACA | Kontrol | _OZET | 6.3 dk |
| 13 | GEÇMİŞİN GÖLGELERİ | Kontrol | _OZET | 6.9 dk |
| 14 | HAYALPEREST | ⏳ işleniyor | — | — |

## Bulgular
- **Hepsi KONTROL'e gidiyor — bu BEKLENEN.** Sebep: ASR yok → özet yok → "özet eksik" damgası (`_OZET`). Künye/kadro/yönetmen üretimi normal çalışıyor; KONTROL kararı yalnızca özet eksikliğinden.
- **MANASLU → muzikal_animasyon_belgesel/** (BELGESEL tespit edildi — senin "ORF belgesel" notunla uyumlu). Ayrıca yönetmen-kimlik bayrağı var.
- **Yönetmen-kimlik bayrağı (_KIMLIK):** MANASLU (#5) + OLAY YERİ (#9) → bu ikisinde yönetmen okuma/doğrulama sorunu işaretlendi, gözden geçirilmeli.
- **Teslimat:** `Mitas Output\export\KONTROL\` (MANASLU → `muzikal_animasyon_belgesel\`).

## Zamanlama
- Ortalama: ~9.2 dk/film (en hızlı KOMİSER CORDIER 6.3 dk; en yavaş YAĞMUR 18.6 dk).
- Başlangıç 17:10 → 13 film ~132 dk.
- **Kalan 29 film** → ~5 saat → tahmini bitiş **~00:15 civarı** (sıradaki eski/kısa filmler hızlandırabilir).

## Notlar
- ASR'li koşuya kıyasla ~2 kat hızlı (whisper ~10 dk/film tasarrufu).
- ASR'li çıktıların korunuyor (asr'siz `_OZET` damgalı ayrı dosya → kadro/yönetmen karşılaştırması yapılabilir).
- Log: `outputs/w2_order.log` · Tamamlananlar: `outputs/w2_done.txt`
