# MITAS Künye-Okuma Sistemi — Genel Akış (2026-06-04)

Amaç: filmden **yönetmen + yapımcı + cast** (dizi: tam kadro) güvenilir çıkar. Ölçüt: **okuyamadıysa "okunamadı"** (yanlış çıktı asla) + **kontrol gerektirmeyen güven**. Güven, tek kaynağı kutsamaktan değil **bağımsız kaynakların örtüşmesinden** gelir.

## Boru hattı (bağımsız modüller)
```
video jenerik kareleri
   │  (baş+son örnekleme: uzun jenerikte ilk~900 + son~900, ortadaki crew scroll atlanır)
   ▼
credit_video_read.py   ── VLM ensemble: gemma4:26b + qwen2.5vl:7b (think=False)
   │   • mutabakat → YÜKSEK güven · KB-onay → ORTA · tek okuma → DÜŞÜK · hiçbiri → OKUNAMADI
   │   • KB (imdb.duckdb) NET rol-uyumsuzluğunu reddeder (writer'ı yapımcı sanmaz)
   │   • çelişki → KB-onaylıyı seç, yoksa "okunamadı"
   ▼
{yonetmen, yapimci, cast, guven}     ──(rol etiketi gerekirse)── credit_role_lexicon.py
   │                                     çok-dilli DETERMİNİSTİK çapalama (TR/EN/FR/DE/IT/ES/PT,
   │                                     alt-rol dışlama; halüsine edemez)
   ▼
credit_video_batch.py  ── seri üzerinde resumable koşar → outputs/credit_video/<film>.json + _OZET.tsv
   ▼
[production: → role_reconcile + XML + _pipe_pdf → kunye.pdf]   ← BEKLEYEN entegrasyon
   ▼
credit_qc.py           ── teslimat KALİTE KONTROL (MÜDAHALE ETMEZ, SINIFLANDIRIR)
       • deterministik: yönetmen boş/alt-rol/çöp, yapımcı, cast, özet hata/mojibake, ses&altyazı(v4)
       • XML İSİM eşleşmesi: yönetmen + oyuncu (yapımcı değil) — XML ~%90, KARŞILIKLI uyarı
       • qwen-VL görsel (opsiyonel): İ/Ğ glyph, afiş, özet tutarlı, altyazı kaçmış
       • temiz → dagitim/hazir/  ·  sorunlu → dagitim/kontrol/  (KOPYA; orijinal el değmez)
       • dagitim/kontrol/_kontrol_kayit.xlsx → sebep+kategori (patern analizi)
       • XML isim uyuşmazlığı → dağıtım kopyasının PDF'ine küçük "(!) XML uyusmuyor" damgası
```

## İlkeler (bağlayıcı)
1. **İçerik birincil.** Filmin kendi jeneriği (VLM-okuma) en doğrudan gerçektir.
2. **Katalog/XML ~%90, KESİN DEĞİL.** ID'deki yıl = sisteme eklenme yılı, yapım yılı değil (2014-9073=1971 Leone). XML yalnız çapraz-kontrol sinyali; çelişki = karşılıklı uyarı, XML otomatik kazanmaz.
3. **Müdahale YOK.** Sistem düzeltmez; sınıflar/işaretler. İnsan karar verir.
4. **Güven = örtüşme.** VLM+XML+IMDb aynı → kesin; ikisi → yüksek; çelişki → flag.
5. **Dürüst çekimserlik.** Okunamayan "okunamadı" der; uydurmaz.

## Sonuç (zorlu 53-film benchmark `E:\filmtest\aaaa`)
Yönetmen %91 kapsam · YÜKSEK 29 / ORTA 14 / DÜŞÜK 5 / OKUNAMADI 5 · gerçek false-positive ~0 (güven kademeleri hataları DÜŞÜK/okunamadı'ya düşürüyor).

## Kullanım
```
python scripts/credit_video_read.py  --film-dir <.../film>     # tek film oku
python scripts/credit_video_batch.py                            # seriyi koş (resumable)
python scripts/credit_qc.py [--visual]                          # teslimatları QC + dağıt
python scripts/credit_role_lexicon.py                           # lexicon self-test
```

## BEKLEYEN (Çağatay: "MUTLAKA HATIRLAT")
1. Bu sistemi **production `mitas_pipeline`'a göm** (master-OCR yerine/yanında → role_reconcile + QC → Hazır/Kontrol).
2. **Otonom XML/IMDb çapraz-kontrol** — kimlik = XML orijinal-ad + cast (katalog numarası DEĞİL); asla otomatik düzeltmez, örtüşme/çelişki raporlar.
3. Ufak: yazım-kayması (Smight→Smith) düzeltmesi; şüphelileri içerikten doğrulama.
