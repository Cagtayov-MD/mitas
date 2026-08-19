# Shaq — kanıtlı okuma uzlaştırma kulesi

Shaq, iki bağımsız **okuma paketine** bakar; paketlerin hangi kuleden geldiği
kararı değiştirmez. Güvenilir iki-okuma eşleşmesini geçirir, belirsiz satırları
bbox tabanlı kör kontrole ayırır. Işık şefi gibi dış veri tabanında olmayan
kişiler iki kanal aynı okuyorsa korunur.

## Sınır

**Yapar:** satırları sıra ve kanıtla hizalar; ham okumayı saklar; gerekirse
cast/yönetmen için kesin-film kimliğiyle ayrı bir `canonical_name` ekler;
kontrol crop'u ile kör kontrol kuyruğu yazar.

**Yapmaz:** OCR çalıştırmaz, bbox icat etmez, kaynak görseli veya başka kulenin
`out/` alanını değiştirmez, global isim sözlüğüyle fuzzy düzeltme yapmaz,
IMDb/Wikipedia'da olmayan adı reddetmez ve QC1'i çağırmaz.

```text
kanal A + kanal B
        ↓
 exact LCS çapa → yakın hizalama → kimlik desteği
        ↓
 GECTI | KONTROL_BEKLIYOR | COZUMSUZ | METIN_YOK | ARIZA
```

## Girdi sözleşmesi: `mitas.okuma/v1`

Film klasöründe bölüm başına **1–3** `*.okuma.json` bulunur. `nash` paketi
ZORUNLUDUR — bbox yalnız onda vardır (ölçüldü 2026-08-19: nash %100,
lebron %1, jordan %0) ve kör kontrol kuyruğu onun koordinatlarına bağlıdır.
Diğer kanallar varsa katılır, yoksa güven düşürülür.

```text
<film>/
├─ giris/ kanal-a.okuma.json, kanal-b.okuma.json
└─ cikis/ kanal-a.okuma.json, kanal-b.okuma.json
```

Her paket `film`, `section`, `producer`, `assets`, `lines`, `status` taşır.
`producer.id` iki pakette farklıdır ama ismi serbesttir. `OKUNDU` satırında
asset referansı ve kaynak koordinat uzayında geçerli `x0,y0,x1,y1` bbox zorunlu;
asset yolu, boyutu ve SHA-256'sı da zorunludur. Piksel JSON içine konmaz.

```json
{
  "schema_version": "mitas.okuma/v1",
  "film": {"id": "F1", "external_ids": {"imdb": "tt123"}},
  "section": "cikis",
  "producer": {"id": "okuyucu-a", "engine_family": "ocr", "model_digest": "sha256:..."},
  "status": {"execution": "SUCCEEDED", "content": "READ", "proof": "COMPLETE"},
  "assets": [{"asset_id": "frame-1", "path": "/readonly/frame.png", "sha256": "64-hex", "width": 1920, "height": 1080}],
  "lines": [{"line_id": "l1", "order": 1, "raw_text": "AHMET GÜLDİKEN", "normalized_text": "ahmet güldi̇ken", "evidence": [{"asset_id": "frame-1", "bbox": [410, 220, 760, 275]}]}]
}
```

`METIN_YOK` ve `ARIZA` paketleri satır taşımaz. Ancak dedektörün metin
okuyamadığı alanları `unread_regions` içinde aynı asset+bbox biçimiyle
taşıyabilir; bu durumda Shaq içerik boşluğu demez, kör kontrole ayırır. Asset
doğrulaması hash ve bbox sınırıyla yapılır; eksik/taşmış bbox arızadır.

## Karar kuralları

- Biçimsel normalize edilmiş iki eş okuma `IKI_KANAL_TEYITLI` ile geçer.
- Exact LCS çapaları satır sırasını korur. Uzak iki yazı yalnız iki exact çapa
arasındaki tek-tek boşluksa çiftlenir; aksi durumda `A_ONLY/B_ONLY` kalır.
- Fuzzy yalnız `YAKIN` sınıfı ve hizalama için kullanılır; hiçbir ismi tek
başına değiştirmez.
- Yakın `CAST Ahmat/Ahmet` farkında açık `CAST`/`DIRECTOR` etiketi sonrası
çıkarılan kişi adı, kesin film ID'si ve film kredi listesindeki tek adayla
eşleşirse `canonical_name` kazanır. Tam görsel satır `accepted_text` olarak
ayrı korunur. `ART DIRECTOR`, `ASSISTANT DIRECTOR`, `CASTING DIRECTOR` vb.
yardımcı roller yönetmen değildir; iki kanalın rol kanıtı çelişirse rol belirsiz
kalır. Genel name DB yeterli değildir.
- Dış kaynak yokluğu nötrdür. Teknik ekip her zaman görsel kanıtla yaşar.
- Riskli satırlar için dar metin crop'u ve geniş bağlam crop'u oluşturulur.
Kontrol isteği aday isim içermez. Kontrol cevabı yalnız adaylardan (veya güçlü
kanonikten) **exact-normalized** biriyle eşleşirse kabul edilir; fuzzy cevap
çözüm değildir.

## Çalıştırma

```bash
Allstar/shaq/shaq tek --film-dir /paketler/F1 --film-id F1 --bolum cikis
Allstar/shaq/shaq start --input /paketler --bolum giris,cikis
Allstar/shaq/shaq tamamla --film-id F1 --bolum cikis --cevaplar /kontrol/cevaplar.jsonl
```

İsteğe bağlı salt-okunur yerel kimlik listesi `--kimlik-json` ile verilir:
`{"tt123": {"CAST_KESIN": ["Ahmet Güldiken"]}}`. Ağ yoktur, başlıktan film
tahmini yoktur.

## Çıktı ve kuyruk

Çıktı daima `Allstar/shaq/out/<film_id>/<bolum>/` altındadır:

```text
shaq.json
shaq.txt                         # yalnız durum=GECTI
kontrol/istekler.jsonl
kontrol/crops/<request>.png
kontrol/crops/<request>.context.png
_TAMAM                           # yazımın en son işareti; GECTI demek değildir
```

Yazım atomiktir. Eski `_TAMAM` koşu başında kaldırılır; tüketici yalnız marker
varsa dosyayı okur. Kısmi kontrol cevapları `shaq.json` içindeki
`control_answers` alanına kalıcı yazılır; yalnız yanıtlanmamış istekler kuyrukta
kalır. Bölümler ayrı dizindedir ve birbirini etkilemez.

## Test

```bash
python3 -m unittest discover -s Allstar/shaq/tests -v
```

CLI, Kobe gibi yalnız kendi `venv/` çalışma zamanını kullanır. İlk kullanımda
`Allstar/shaq/venv_kur.sh` çalıştırılmalıdır.

`golden/` davranış örneklerini, `olcum/` ise ileride insan-etiketli ölçüm
yatağını taşır. Gerçek doğruluk kapısı oluşana dek canlı QC1 bağlantısı yoktur.

## Paralel challenger: HAKEEM

Mevcut Shaq korunmuştur. Aynı `mitas.okuma/v1` girdisini daha katı bağımsızlık,
conflict-group ve deterministik kontrol kurallarıyla işleyen ikinci motor
`hakeem` adıyla aynı kule içindedir. Çıktısı `out_hakeem/` altına gider; Shaq
çıktısını ezmez. Tasarım, komutlar ve 100-film A/B ölçümü: [HAKEEM.md](HAKEEM.md).
