# Jordan kulesi — canlı durum

**Son güncelleme:** 2026-08-19

## Şu anki durum

- Native-video model beslemesi devre dışı; `Motor.sor()` yalnız ayrı resim
  listesi veya metin-only çağrı kabul eder.
- Sheriff üretim yolu MP4 vermez; sınırlar içindeki kesintisiz `frames.jsonl`
  havuzunu `--kareler` ile verir. Jordan kaynak PNG'leri kendi güncel görsel
  reçetesiyle hazırlayıp modele ayrı image listeleri halinde yollar.
- Varsayılan üretim modeli Qwen3-VL-8B BF16 `transformers`.
- Qwen2.5-VL-7B ve Qwen3.6-27B (`llama_mtmd`) silinmedi; ikisi de yalnız açık
  CLI seçimiyle çalışan deney kolu.
- Kare reçetesi: 2 fps, 720 px, Lanczos + unsharp, JPEG q=2.
- Üretim grup reçetesi: 8 ayrı kare, bindirme 1.
- Üretim uzunluğu: max_new_tokens 512.
- Fuzzy eleme yok; yalnız kesin yakın-dönem tekrar düşer ve kaydı kalır.
- Metin-only çiftleyici varsayılan kapalı.
- BBox henüz yok; proof durumu `NONE`.

## Doğrulama

| Kontrol | Sonuç |
|---|---|
| Jordan CPU testleri | 81/81 |
| Sheriff CPU testleri | 67/67 |
| 2.5-VL 28-klip yarışı | 28/28 dolu sonuç, doğrulanmış alt küme skoru 0,9301 |
| Qwen2.5-VL Sheriff VRAM | 17284 MiB tepe |
| Qwen2.5-VL Sheriff RSS | 15244 MiB tepe |
| 13-klip dizi GT yarışı | 8B 470/519 (%91) · 27B %80 · MiniCPM %35 |
| **8B uçtan uca canlı koşu** (2026-08-19) | Çiçek Taksi girişi: `OKUNDU`, 66,9 sn, 29 grup, 0 bozuk, 50 satır |
| **↳ GT skoru** | **BİREBİR 32/43 · hiç-yok 0** (yarış harness'ı 35/43) |
| **↳ kule vs harness kapısı** | yarış KODU + kule KARELERİ = **32/43, yakın-yanlış 11** — kulenin sonucuyla birebir |
| 8B VRAM (8 kare × 720 px) | 19,1 GB tepe / 24,5 GB |

**Uçtan uca koşunun okuduğu:** bindirme=1 örtüşmesi 34 kesin tekrarı eledi ve
**tek bir gerçek satırı bile yemedi** — 43 GT satırının hepsi çıktıda (`hiç-yok 0`).
Kulenin harness'tan 3 satır geride kalmasının sebebi kule DEĞİL: aynı yarış kodu
kulenin kareleriyle beslendiğinde birebir aynı 32/43'ü verdi. Fark tamamen kare
kaynağından geliyor (yarışın klibi yeniden kodlanmış 13 MB, buradaki klip
stream-copy 9,6 MB; kare 0 birebir aynı, sonraki kareler ortalama ~2/255 ayrışıyor).

Jordan CPU testleri güncel olarak **80/80** geçmektedir. Özgün 27B reçetesine
yalnız ham JSON schema eklenen canlı kabul koşusunda bütün gruplar ilk denemede
tamamlandı. Geçici CUDA kaynak hatası için bir retry ve 2 sn cooldown vardır;
retry kullanımı model çağrısı kanıtında görünür.

KSK referansı ile yeniden üretilen JPEG'lerin hash'leri birebirdir. Ham grup
cevaplarının orta 7/9'u aynıdır. Jordan ilk grupta `executive producer /
Glen A. Larson` satırlarını kaçırdı; son grupta referansın kesildiği yerde
`DANIEL B. RABINOVITCH` satırını ekledi. İki ortamın transformers/torch
sürümleri farklıdır; birebir tensor/runtime eşlemesi ayrı bir dondurma işidir.

## Açık kalemler

1. 3-VL aynı-reçeteli 28-klip koşusu kullanıcı tarafından 6/28'de
   durduruldu; model kararı için tamamlanmış sayılamaz.
2. Sheriff yalnız görev girdisini iletmeli; model/backend reçetesini ezmemelidir.
3. Satır→kare→bbox grounding ayrı proof çalışmasıdır.
4. Jordan venv'i ile KSK venv'inin tam sürüm dondurması istenirse yeniden
   üretilebilirlik testi yapılmalıdır.
5. ~~8B varsayılanı uçtan-uca doğrulanmadı~~ — **KAPANDI 2026-08-19**: canlı
   koşu yapıldı, kule harness ile birebir aynı sonucu üretti (yukarıya bakınız).
6. **Kare kaynağı reçeteye dahil değil, ama sonucu değiştiriyor.** Aynı klip
   penceresinden stream-copy ile kesilmiş kareler, yeniden kodlanmış kareler
   yerine kullanıldığında 43 satırın 3'ünde diakritik kaybı oldu (%7). `fps` ve
   `suzgec` sabitlemek yetmiyor; yeniden üretilebilirlik klibin nasıl kesildiğine
   de bağlı. Kesim reçetesi henüz hiçbir yerde sabitlenmiş değil.

Eski `w8a8` ve `bf16` ağırlıkları silinmedi; fakat varsayılan değiller ve
native-video stratejisi geri açık değildir.

## 2026-08-20 Sheriff girdi politikası

Aksi yönde açık karar verilene kadar Sheriff'in Jordan komutu `--kareler`dir.
Tarihsel `reader_video` rol adı korunmuştur fakat bu rolün gerçek girdisi
`materialized/<bolum>/jordan_frames/` havuzudur; `credits.mp4` Jordan'a verilmez.
Model/backend/grup/preprocessing/prompt seçimi yalnız Jordan `config.yaml`ından gelir.
