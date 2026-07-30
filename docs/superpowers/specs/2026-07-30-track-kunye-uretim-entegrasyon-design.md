# track_kunye Üretim Entegrasyonu (Messi + İbrahimovic-okuma + Ronaldo) — Tasarım

> Karar: Çağatay, 2026-07-30 akşam (birebir): runaware master PNG'lerin
> (`giris_reading_master_runaware.png` / `reading_master_runaware.png`)
> "üretimine dokunma; geri kalanlar için bizim sistemimiz buraya bağla...
> bundan sonra bir işlem yaptığımızda pipeline üzerinden yapacağız...
> 3 çıktı gerekecek: 1 messi 2 ronaldo 3 ibrahimovic; 2 = 1 ve 3'ün mixi...
> 15 film seç... pdf'leri düzgünce oluşana kadar süreci takip et; qc1 qc2
> gerekli tüm süreçleri düzelt revize et; sabah çalışır bir sistem istiyorum."
> Onay mercii bu gece: konsey kırmızı-takımı (GLM + Nemotron cevapladı;
> Kimi bakiye-askıda, MiniMax bağlantı hatası) + Claude hakemliği.
> Sabah Çağatay incelemesi için açık karar maddeleri en sonda.

## Amaç

track_kunye zincirini (MESSİ kare seçici → deepseek okuma → İBRAHİMOVİC
master'ının deepseek okuması → RONALDO çaprazı) üretim pipeline'ının
(scripts/mitas_pipeline.py) her film koşusuna otomatik bağlamak. Film başına
3 çıktı: Messi dökümü, İbrahimovic-okuma dökümü, Ronaldo birleşik (mix).
Gölge sözleşmesi korunur: karar/PDF/teslim/reasons'a DOKUNULMAZ (terfi,
pilot F1 kriteri sağlanınca ayrı karar — bugünkü 10-film pilotta sağlanmadı).

## Kapsam / Kapsam dışı

- KAPSAM: çıkış (kapanış) jeneriği. GİRİŞ V1 dışı (sistem exit-odaklı;
  giriş master'ı V2 motoruyla üretiliyor).
- KAPSAM DIŞI: üretimde skorlama (referans_cikar Paddle taraması + metrik.skorla
  benchmark işidir, her filmde koşmaz); PDF içeriği değişikliği (aşağıda
  yapısal kısıt); webui değişikliği (event'ler LogPanel'de zaten akar);
  runaware master üretim zinciri (master_png_monitor.py + ibrahimovic.py +
  db_compose_master.compose_reading_runaware + mitas_pipeline 4061-4118
  tetiği — DOKUNULMAZ BÖLGE, yalnız çıktısı SALT-OKUNUR tüketilir).

## Yapısal kısıt (PDF neden V1'de değişmiyor)

Runaware master, karar/PDF'ten SONRA üretilir (mitas_pipeline.py:4061-4118,
karar-sonrası gölge bölge). Ronaldo İbra-kolunu okuyacaksa blok master'dan
sonra koşmak zorunda → 3 çıktı AYNI turun PDF'ine yapısal olarak giremez.
GLM'in "master öncesine al, önceki turun (bayat) PNG'sini oku" önerisi
REDDEDİLDİ: ilk kez işlenen filmde (15-film testinin tamamı) önceki PNG hiç
yoktur; bayat-PNG tuzağı master keşfinin bilinen riski. 3 çıktının görünür
yüzeyi V1'de: `clip_dir/track_kunye/` + hub köküne özet yüzey dosyası
(aşağıda). PDF bölümü sabah karar maddesi (V2).

## Mimari

```
mitas_pipeline.main()  (karar/PDF/teslim BİTMİŞ durumda)
  ... video_vl → jenerik_debug → MASTER-PNG bloğu (4061-4118, dokunulmaz) ...
  └─► YENİ GÖLGE BLOK (master bloğunun hemen ardı):
        MITAS_TRACK_KUNYE=1 (default AÇIK; kill-switch)
        subprocess: PY_OCR scripts/_pipe_track_kunye.py
            --clip <clip_dir> --frames <frames/cikis> [--master <kök runaware>]
        timeout MITAS_TRACK_KUNYE_TIMEOUT (default 1200 sn)
        timings["track_kunye"] + log_event + _DURUM.json yüzeyleme
        HATA ASLA pipeline'ı/kararı BOZMAZ (video_vl deseni)
```

`_pipe_track_kunye.py` içi akış:
1. Ollama sağlık-kontrolü (`GET /api/tags`, 3 sn): erişilemezse → son-satır
   JSON `{"status":"skipped","reason":"ollama_down"}` + exit 0 (uzun
   timeout'a hiç girmez — GLM S3 kabulü).
2. KOL 1 (MESSİ): frames/cikis'ten gri kareler → messi.havuz_derle +
   ikinci_gecis → seçim. Havuz boş → `skipped/messi_havuz_bos`. Seçim >
   MITAS_TRACK_KUNYE_MAX_FRAMES (default 100) → kronolojik düzgün-adımlı
   örnekleme + `dusurulen_n` alanı (sessiz-kırpma yasak). deepseek okuma →
   frame_dokum.txt.
3. KOL 2 (İBRAHİMOVİC-okuma): film kökündeki `reading_master_runaware.png`
   — okumadan ÖNCE `reading_master_runaware_manifest.json` durumu (gerçek
   şema uygulamada master_png_monitor.py:362-491'den doğrulanır; Nemotron
   S1 kabulü): üretilememiş/bayat/yok → İbra kolu BOŞ + manifest'e
   `ibra_atlandi_sebep` + event. Sağlamsa bindirmeli bant bölme →
   deepseek → master_dokum.txt.
4. Sağlık dedektörü (Nemotron S4 kabulü): her kol dökümü için ucuz kontrol
   (toplam < 200 karakter VEYA alfasayısal oran < 0.30 → `deepseek_degraded`
   event + manifest alanı). Ronaldo yine koşar; band dürüst düşer.
5. KOL 3 (RONALDO): ronaldo.capraz → ronaldo_kunye.txt + ronaldo_fark.json.
6. Çıktılar `clip_dir/track_kunye/`: frame_dokum.txt, master_dokum.txt,
   ronaldo_kunye.txt, ronaldo_fark.json, manifest.json (film, band,
   common_blind, coverage_ratio, structural_anchor_missing, kol kare/satır
   sayıları, deepseek_saglik, dusurulen_n, ibra_atlandi_sebep, süreler).
7. Hub kök yüzeyi: `<TRT BAŞLIK> kunye3.txt` — 3 çıktının başlıklı birleşik
   metni (MESSİ / İBRAHİMOVİC / RONALDO-MIX + band satırı), surface_deliverables
   deseninde clip_dir köküne. export/'a YAZILMAZ (teslim saflığı; Nemotron
   S6 önerisinin export ayağı bu gerekçeyle değiştirildi).
8. Son satır JSON özet (worker/blok parse deseni): {status, band, sayilar...}.

### Hata modları (Nemotron S3 kabulü — yapılandırılmış event'ler)

| Mod | Davranış | Event + alanlar |
|---|---|---|
| Ollama down | 3 sn'de tespit, atla | track_kunye_skipped, reason=ollama_down, ollama_url |
| deepseek model yok | ollama_iste hatası → atla | track_kunye_failed, error_class |
| master yok/bayat | İbra kolu boş, Ronaldo koşar | track_kunye_master_stale, manifest_status |
| frames/cikis boş | atla | track_kunye_skipped, reason=frames_bos |
| timeout | üst blok TimeoutExpired yakalar | track_kunye_failed, timeout=true |
| döküm dejenere | koş ama işaretle | track_kunye_deepseek_degraded, kol, sebep |
| band red/null veya common_blind | normal tamamlanır | ronaldo_band_red \| ronaldo_common_blind |

Her koşu sonunda `track_kunye_completed` (band + sayılar detail'de).
GLM'in "track_kunye hatası filmi KONTROL'e düşürsün" önerisi REDDEDİLDİ:
gölge katmanın teslimi bloklaması ghost sözleşmesi + Prensip 2 ihlali
(temiz teslimatı yan sistemin arızası durduramaz). Görünürlük event +
doğrulayıcı ile sağlanır, yönlendirmeyle değil.

## pilot_hat.py uyarlamaları (harness geriye-uyumlu)

- `havuz_derle_dizin(kare_dizin: Path, desen: str = "*.png") -> tuple[list[Path], dict]`
  — yeni; dizin-parametreli, istatistiği DÖNÜŞ değerinde (global
  SON_HAVUZ_ISTATISTIK yarış riski üretime taşınmaz). Eski `havuz_derle(slug)`
  harness için aynen kalır (yeni fonksiyonu çağırır).
- Ollama: `OLLAMA = os.environ.get("MITAS_OLLAMA_URL", "http://127.0.0.1:11434") + "/api/generate"`.
- KB: `kb_yukle()` yolu `os.environ.get("MITAS_KB_DUCKDB", <mevcut yol>)`
  (iki yol aynı dosyaya çıkıyor — 13.043.539 satır mitas_people_index doğrulandı).
- `oku_deepseek(..., cagri_timeout: int = 900)` parametreleşir; üretim 180 geçer.

## Doğrulayıcı — scripts/track_kunye_batch_dogrula.py (GLM S6 + Nemotron S6 birleşimi)

15-film testi sonrası (ve ileride her batch'te) film listesi alır, her film için:
1. PDF: hub `pdf/kunye.pdf` var + >10 KB + fitz ile açılıp sayfa sayısı ≥1.
2. Teslim: export/ONAYLI|KONTROL (veya özel-tür) kopyası var.
3. system_events.jsonl: bu filmin koşu penceresinde credit_qc1_* VE
   (credit_validate VEYA QC2 event'i) VE track_kunye_completed|skipped var.
4. track_kunye/5 dosya var ve > 0 bayt; manifest.json'da band alanı mevcut
   (null ise ibra_atlandi_sebep/skip sebebi dolu olmalı).
5. kunye3.txt hub kökünde var.
Çıktı: film×kontrol tablosu + "N/15 PASSED"; eksik varsa exit 1.
"İstisnasız bağlı çalışıyor" kanıtı bu scriptin çıktısıdır.

## Doğrulama protokolü

1. Birim testler (TDD, her yeni fonksiyon için).
2. Tek-film smoke: 15-lik listeden 1 film webui worker'ın kullandığı komutla
   (`mitas_pipeline.py --video ... --profile film`) uçtan uca; track_kunye
   çıktıları + event'ler + PDF elle incelenir.
3. 15-film gerçek test (test15_klipler.tsv: 1952-2025, XML kimlikli, pilotla
   çakışmasız) sıralı koşu; kırılan her şey düzeltilir (Linux geçiş hataları
   dahil — QC1/QC2 zinciri bu koşuda "düzelt-revize" kapsamında).
4. track_kunye_batch_dogrula → N/15 PASSED + sabah raporu
   (skorlar değil: band dağılımı, hata/degraded listesi, süre etkisi).

## Konsey karar kaydı (2026-07-30 kırmızı-takım turu)

Kabul: manifest-öncelikli master okuma (Nemotron S1); kare üst-sınırı +
boş-havuz erken çıkış (Nemotron S2; N=100, 60 değil — uzun rulolarda kapsama
kaybı riski, sessiz-kırpma yasağıyla); yapılandırılmış hata event'leri
(Nemotron S3); Ollama ön sağlık-kontrolü (GLM S3'ün sağlık-check kısmı);
deepseek-çöküş dedektörü V1 blok-içi (Nemotron S4 + GLM S4); fark.json'a
kol sayıları zenginleştirmesi (Nemotron S5); koşu-sonu özet event; batch
doğrulayıcı + 0-bayt/fitz kontrolleri (GLM S6 + Nemotron S6); 3 çıktının
hub-kök yüzeyi (Nemotron S6'nın export ayağı hub'a çevrildi).
Red: master-öncesi yerleşim/bayat-PNG okuma (GLM S1 — ilk-film tuzağı);
hata→KONTROL yönlendirmesi (GLM S3 — ghost ihlali); default KAPALI (GLM S2 —
direktife aykırı; maliyet, timeout 1200 + sağlık-check + kare sınırıyla
sınırlandı); QC2_WEB event üreticisine band alanı (Nemotron S6 — karar-yolu
koduna dokunur); Ronaldo çekirdek değişikliği bu gece (GLM S5 — önce
vahsi-afrika analizi, kanıtsız çekirdek değişikliği yasak).

## Sabah karar maddeleri (Çağatay)

1. PDF'e "çapraz-denetim" bölümü (V2): sonraki koşuda mı, PDF'in gölge-sonrası
   yeniden basımı mı, hiç mi? (yapısal kısıt yukarıda; PDF haritası çıkarıldı,
   ekleme noktaları biliniyor: _make_pdf.build FİLM NOTU deseni).
2. vahsi-afrika S5 analizi sonucu → Ronaldo birleşim çekirdeğinde değişiklik
   gerekiyor mu (gece yalnız analiz yapıldı/yapılacak, çekirdek dondu).
3. Kimi bakiye şarjı (iki turdur cevapsız); MiniMax bağlantısı.
4. exit_kesim sistematik denetimi (0.85-güven budamaları) hâlâ park halinde.
5. Bilinen leke (PDF keşfinde bulundu, bu gece dokunulmadı): --no-asr + V4
   yolunda ÖZET kutusu "—" tek karakteriyle çiziliyor (tek_film_kunye.ozet_v4
   boş girdide "—" döndürüyor, _make_pdf erken-çıkışı truthy sayıyor).
