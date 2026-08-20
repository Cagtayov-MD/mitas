# LeBron fix devir planı

Tarih: 2026-08-19

Durum: Uygulama yarıda güvenli noktada durduruldu. Değişiklikler çalışma ağacında duruyor; üretim terfisi yapılmadı.

## Tamamlanan kod düzenlemeleri

Terra şu dört dosyada tasarlanan ilk düzeltmeyi yazdı:

- `Allstar/lebron_james/src/derleyici.py`
  - Normal master mevcut çöküş kuralına girerse koşullu `temporal_chunk_stack` kurtarması eklendi.
  - Normal yol değiştirilmedi; recovery yalnız çok-kare/tek-kısa-segment halinde tetikleniyor.
  - Manifest'e `collapse_recovery` tanısı eklendi.
  - Kurtarılan master `H_MAKS` sınırını geçerse görünür `boy_asimi` bırakılıyor.
  - Paddle çalışırken satır metni, confidence ve bbox alan `paddle_satir_kaniti()` eklendi.
- `Allstar/lebron_james/main.py`
  - Bantların Paddle satır/bbox haritası model yüklenmeden önce önbelleğe alınıyor.
  - Mevcut private Ollama backend satır-grounding desteklemediğini ilan ettiğinde ikinci DeepSeek çağrısı yapılmıyor.
  - Proof stratejisi `paddle_exact`, tanı `grounding_unsupported` olarak yazılıyor.
  - `collapse_recovery` legacy kanıta aktarılıyor.
- `Allstar/lebron_james/src/proof.py`
  - Free OCR satırı yalnız tek ve açık Paddle `exact`/`fold_exact` eşleşmesi bulursa bbox alıyor.
  - Fuzzy veya birden çok olası eşleşme bbox üretmiyor.
  - Master bbox mevcut layout map ile kaynak kareye çevriliyor.
  - `COMPLETE`, yalnız bütün satırlarda gerçek kaynak-kare bbox/zaman/sequence varsa yazılıyor; aksi halde `PARTIAL/NONE`.
  - Görüntü-geneli `image[[...]]` çıktısı satır kanıtı sayılmıyor.
- `Allstar/lebron_james/src/model.py`
  - Mevcut Ollama yolu `line_grounding_supported = False` ilan ediyor.

## Yapılan doğrulama

- Dört değişen Python dosyası `py_compile` kapısından geçti.
- Mevcut LeBron regresyonu: `163 passed in 16.77s`.
- Global Ollama'ya, `~/.ollama` durumuna veya model ağırlıklarına dokunulmadı.

Bu sonuç yalnız eski regresyonların bozulmadığını gösterir; yeni davranışların kabul edildiği anlamına gelmez.

## Henüz yapılmayanlar

1. Yeni davranışlara özel testler yazılmadı:
   - 100+ kare sentetik collapse recovery,
   - layout-map y-offset doğruluğu,
   - `H_MAKS` sınırı,
   - normal master piksel paritesi,
   - Paddle exact/ambiguous/unmatched proof,
   - `image[[...]]` reddi,
   - model çağrı sayısının gerçekten bire düşmesi.
2. Beş gerçek `COKME` paketi yeniden çalıştırılmadı:
   - `cag_output02/giris`
   - `cag_output02/cikis`
   - `cag_output17/giris`
   - `cag_output17/cikis`
   - `cag_output18/cikis`
3. Gerçek GPU üzerinde yeni proof kapsamı, Paddle kalıntısı, süre ve peak VRAM ölçülmedi.
4. Recovery sabit 12 karelik chunk kullanıyor; gerçek beş koşudan sonra adaptif chunk gerekip gerekmediği değerlendirilmedi.
5. Sheriff'in her `lebron tek` görevinde modeli yeniden ısıtması düzeltilmedi. İkinci çağrı kalktı, fakat yaklaşık 22 saniyelik görev-başı warmup hâlâ vardır.
6. Tam 29-video kabul yatağı tekrar koşulmadı; mevcut gece raporunun `GATE_FAILED` durumu değişmedi.
7. Kalite uzlaştırıcısı kodlanmadı. Yalnız tasarım belgesi hazırlandı.

## Sonraki oturumda güvenli uygulama sırası

1. Önce yukarıdaki yeni unit/integration testlerini ekle ve tüm LeBron suite'ini çalıştır.
2. Beş gerçek COKME girdisini `/tmp` altında izole sonuç yoluyla yeniden çalıştır; aktif gece çıktılarının üzerine yazma.
3. Her birinde recovery metadata, master görseli, satır sayısı, proof kapsamı, süre ve VRAM'i raporla.
4. Normal başarılı örneklerde master piksel paritesini doğrula.
5. Kapılar geçerse 29-video Sheriff kabul yatağını yeni pipeline hash'iyle yeniden çalıştır.
6. Ayrı bir değişiklik olarak warm-model sorununu çöz. Güvenli tasarım, model servisi VRAM tutarken Sheriff'in bunu rezervasyon olarak bilmesini ve Jordan exclusive işinden önce unload etmesini şart koşmalı; kayıtsız arka-plan daemon bırakılmamalı.
7. Bunlar geçtikten sonra `KALITE_UZLASTIRICI_PLANI_20260819.md` shadow/offline aşamasından başlanmalı.

## Hazır kalite planı

Uzlaştırıcı tasarımı:

`Allstar/nash/olcum/KALITE_UZLASTIRICI_PLANI_20260819.md`

Bu plan Nash ve LeBron'u her zaman çalıştırır, Kobe'yi yalnız daraltma ipucu yapar, Jordan'ı `SKIPPED_POLICY/READY` kararıyla yalnız anlaşmazlıkta açar ve 29 videoyu 12 kalibrasyon + 17 kör kabul kümesine ayırır.

## Uyarı

Çalışma ağacı önceden de kirliydi. Geniş `git reset`, checkout veya toplu geri alma yapılmamalı. Bu dört dosyadaki yeni satırlar da henüz gerçek kabul kapısından geçmediği için doğrudan üretime terfi edilmemeli.
