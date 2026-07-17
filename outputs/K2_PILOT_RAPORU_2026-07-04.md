# K2 PİLOT NİHAİ RAPORU — master-dilim → VL (2026-07-04/05 gecesi)

5 film (İHTİRAS, SHERLOCK, VANYA, MÜREKKEP, YEDİ CÜCELER) × 5 model × 2 mod.
Mod-A = rol-soru (JSON yönetmen/yapımcı/oyuncu). Mod-B = TAM TRANSKRİPT ("sadece yazanı yaz,
[okunamadı]") → kalibre metin-hat rol-eşleme. Girdi: master_dilim/*.png parçaları. think=False, temp=0.

## MOD-A skor tablosu (yönetmen isabeti / süre bandı)

| Model | İsabet | Süre/film | Not |
|---|---|---|---|
| **gemma4:26b** | **5/5** | **6-30s ŞAMPİYON** | Tovstonogov (Kiril-genitif) + UNTERWALDT dahil |
| qwen3.6-27B | 5/5 | 13-34s | Tovstonogov Latin-okuma |
| qwen3.5-35B | 4/5 | 85-696s | SHERLOCK kaçtı, çok yavaş |
| gemma-31b | 4/5 | 23-45s | YEDİ CÜCELER'de "ZIPFELMÜTZEN FILM" stüdyo-çöpü |
| qwen3.6-35B | 3/5 | 78-150s | SHERLOCK'ta 'David Pirie' (SENARİST!) = yanlış-dolu; VANYA kaçtı |

## MOD-B skor tablosu (transkript kalitesi + rol-eşleme)

| Model | Rol-isabet | Döküm | Not |
|---|---|---|---|
| **qwen3.6-27B** | 4/5 | 92-519 satır, 0 [okunamadı] | **EN DİSİPLİNLİ döküm** — dizi-modu adayı |
| gemma4:26b | 4/5 | değişken | **RUNAWAY riski**: MÜREKKEP 9.080 / YEDİ CÜCELER 13.929 satır tekrar-patlaması |
| qwen3.5-35B | 1-2/5 | 25-537 seyrek | eksik döküm |
| qwen3.6-35B | — | 82-333 satır | orta |

Her iki modda VANYA'nın açığı metin-hattın Kiril rol-kalıbını tanımaması ("фильм Георгия
Товстоногова") — mod-A resim-doğrudan yakalıyor. → Lexicon Kiril-eki ayrı küçük iş.

## KAZANIMLAR (kanıtlı)

1. **VANYA/TOVSTONOGOV**: metin-zincirinin (OneOCR dahil) HİÇ yüzeye çıkaramadığı yönetmeni
   3 bağımsız model master-resimden okudu (27B Latin + 3.5-35B Kiril + 26b Kiril-genitif) —
   K2'nin ilk metin-zincirini-geçen kurtarması.
2. **Girdi > model**: aynı 27B kare-havuzundan İHTİRAS'ta BOŞ, master-dilimden 5/5 —
   Çağatay'ın "parçalanmış master'ları ver" tezi kategorik doğrulandı.
3. **Rol-soru vs transkript**: rol-soru uydurmaya itiyor (Makarov/Pirie vakaları — hep
   rol-soru modunda), transkript-modu uydurmayı düşürüyor ama runaway-bekçisi istiyor.

## ÜRETİM ÖNERİSİ (onay bekler)

- **K2-TANIK** (film-modu): gemma-26b + mod-A, film-başı ~30-90s; çıktı KARAR DEĞİL —
  mevcut kalkan/teyit zincirine ADAY olarak girer (Tovstonogov-tipi kurtarmalar için).
  Yeni model kurulumu gerekmez (26b zaten üretimde).
- **TAM-JENERİK temeli** (dizi/müzik/belgesel vizyonu): qwen27B + mod-B transkript;
  ZORUNLU: token-tavanı + tekrar-bekçisi (gemma runaway dersi). Transkript → PDF
  "JENERİK DÖKÜMÜ" bölümü (satır-kaynak etiketli, OneOCR-mutabakatlı).
- 3.6-35B ve 3.5-35B ELENDİ (yanlış-dolu + hız). Test modelleri diskte (~55GB) — silme onayı Çağatay'da.
