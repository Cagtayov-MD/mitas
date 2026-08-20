# HAKEEM — Shaq içindeki paralel challenger motor

HAKEEM ayrı bir Allstar kulesi değildir. Shaq ile **aynı** `mitas.okuma/v1`
paketlerini okuyan, çıktısını `out_hakeem/` altında izole tutan ikinci karar
motorudur. Amaç mevcut Shaq'ı körlemesine değiştirmek değil; aynı 100 filmde,
aynı dört dosya ve aynı insan doğrusu üzerinde ölçmektir.

## Neden var?

Mevcut Shaq satırları hizalayıp riskli `A_ONLY/B_ONLY` kayıtlarını ayrı ayrı
kontrole gönderir. HAKEEM belirsiz bir bölgeyi tek bir `conflict_group` olarak
tutar. Böylece aynı görsel satırın iki uzak okuması kontrol sonunda iki ayrı
doğru satır gibi çıktı metnine giremez.

HAKEEM'in tasarım olarak daha güvenli olması beklenir; ölçülmeden daha doğru
olduğu iddia edilmez. Güvenlik artışı daha çok `KONTROL_BEKLIYOR` üretebilir.

## Değişmezler

1. `OKUNDU` boş satır listesi taşıyamaz.
2. `ARIZA + METIN_YOK`, boş kayıt üzerinden `GECTI` olamaz.
3. Farklı `producer.id` tek başına bağımsızlık değildir. İki kanalın hem
   `model_digest` hem `independence_group` değeri farklı olmalıdır. Eski pakette
   `independence_group` yoksa `engine_family::model_digest` kullanılır.
4. Fuzzy yalnız yakın conflict-group kurar; metin değiştirmez.
5. Exact iki-kanal uzlaşması, dış veritabanında bulunmayan ekip üyesini geçirir.
6. Film-kapsamlı kimlik kaynağı yalnız kesin cast/yönetmen rolünde ve gözlemlerden
   biriyle exact eşleşen tek adı seçebilir. Ham görsel satır korunur.
7. Her bbox kontrol görünümüne dönüşür; yalnız ilk bbox kullanılmaz.
8. Kontrol isteği OCR aday metnini taşımaz.
9. Kontrol cevabı request digest + crop SHA-256 + model künyesi olmadan alınmaz.
10. OCR adayı yoksa yeni metin en az iki bağımsız kontrol üreticisi, iki farklı
    model digest ve iki farklı independence group ile aynı okunmadan geçmez.
11. Film seviyesinde `giris` ve `cikis` için toplam dört paket kapanmadan
    `qc1_ready=true` olamaz.
12. HAKEEM QC1'i çağırmaz; yalnız hazır olup olmadığını manifestte bildirir.
13. `run_id`; paketler, kimlik snapshot'ı, config, ortak/Hakeem kodu ve Python,
    Pillow, PyYAML çalışma zamanı fingerprint'ini birlikte bağlar.

## Akış

```text
giris/A ─┐                         ┌─ exact bağımsız konsensüs ── geç
giris/B ─┤                         │
cikis/A ─┼─ sözleşme/bağımsızlık ─┼─ yakın conflict ─ kimlik ── geç veya kontrol
cikis/B ─┘                         │
                                  └─ uzak/yapısal/unread ────── kör bbox kontrol
                                                                  │
                           iki bölüm kapandı mı? ◀─────────────────┘
                                   │
                         film manifest / qc1_ready
```

## Aynı girdi sözleşmesi

Shaq README'sindeki `mitas.okuma/v1` aynen kullanılır. HAKEEM aşağıdaki opsiyonel
alanları da tanır:

```json
{
  "producer": {
    "id": "reader-a",
    "engine_family": "qwen-vl",
    "model_digest": "sha256:...",
    "independence_group": "qwen-family/run-policy-v1"
  },
  "lines": [{
    "line_id": "l12",
    "order": 12,
    "block_id": "credit-card-4",
    "page_id": "master-page-1",
    "role_hint": "YÖNETMEN",
    "text": "NURİ BİLGE CEYLAN",
    "evidence": [{"asset_id": "master", "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4}}]
  }]
}
```

`block_id`, rol başlığının aynı bloktaki yalın kişi adlarına aktarılmasını sağlar.
Blok kimliği yoksa açık bir cast/yönetmen başlığı yalnız hemen sonraki satıra
yayılır; bütün jeneriği yanlışlıkla cast ilan etmez.

## Conflict-group

Her group şunları taşır:

- iki kanalın ham gözlemleri ve tüm bbox kanıtları,
- `CONSENSUS`, `NEAR_CONFLICT`, `FAR_CONFLICT`, `STRUCTURAL_CONFLICT`,
  `SINGLE_CHANNEL` veya `UNREAD` türü,
- A/B sıralı hipotezleri,
- rol ve ayrı `canonical_entities`,
- deterministik kontrol istekleri ve kalıcı cevap geçmişi,
- seçilen hipotez ve kabul edilen tam görsel satırlar.

Uzak iki okuma tek group içinde alternatif kalır. Kontrol yalnız bir hipotezi
exact olarak desteklerse o hipotez geçer; ikisi birden destekleniyorsa veya
hiçbiri desteklenmiyorsa `COZUMSUZ` olur.

## Kontrol cevabı `mitas.kontrol.cevap/v2`

`kontrol/istekler.jsonl` aday metin içermez. Bağlanacak model her istek için şu
biçimde cevap verir:

```json
{"schema_version":"mitas.kontrol.cevap/v2","answer_id":"judge-run-1/view-1","request_id":"hk-req-...","request_digest":"sha256-...","crop_sha256":"...","uretim_zamani":"2026-08-17T12:00:00+03:00","durum":"OKUNDU","text":"AHMET GÜLDİKEN","producer":{"id":"vlm-27b-a","engine_family":"qwen-vl","model_digest":"sha256:...","prompt_digest":"sha256:...","independence_group":"vlm-family-a"}}
```

Kontrol modeli kaynak iki okuma modelinden biri olamaz. Aynı `answer_id` farklı
içerikle tekrar kullanılamaz. Kısmi cevaplar `hakeem.json` içinde kalıcıdır;
normal yeniden çalışma aynı `run_id` için var olan durumu bozmaz.

## Çalıştırma

```bash
# Tek bölüm; hata ayıklama/pilot
Allstar/shaq/hakeem tek --film-dir /paketler/F1 --film-id F1 --bolum cikis

# Film kapısı; giris+cikis toplam dört paketi işler
Allstar/shaq/hakeem film --film-dir /paketler/F1 --film-id F1

# Toplu
Allstar/shaq/hakeem start --input /paketler --limit 100

# Kör kontrol cevaplarını işle
Allstar/shaq/hakeem tamamla --film-id F1 --bolum cikis --cevaplar cevaplar.jsonl
```

Çıktılar mevcut Shaq'a dokunmaz:

```text
Allstar/shaq/out_hakeem/<film>/<bolum>/
├─ hakeem.json
├─ hakeem.txt                 # yalnız GECTI
├─ kontrol/istekler.jsonl
├─ kontrol/crops/<run_id>/...
├─ .lock
└─ _TAMAM

Allstar/shaq/out_hakeem/<film>/
├─ manifest.json              # iki bölüm + qc1_ready
└─ _TAMAM
```

## 100 filmde tarafsız karşılaştırma

Önce dört paket uygunluğunu görün:

```bash
Allstar/shaq/karsilastir on-kontrol --input /paketler
```

Sonra iki motoru aynı ilk 100 filmde çalıştırın:

```bash
Allstar/shaq/karsilastir calistir \
  --input /paketler --limit 100 \
  --gt Allstar/shaq/olcum/gt_100.json
```

Karşılaştırıcı her filmin dört paket hash'ini Shaq öncesi ve HAKEEM sonrası
yeniden kontrol eder; koşu sırasında değişen film rapora karıştırılmaz.

GT biçimi `olcum/gt_ornek.json` içindedir. İnsan doğrusu yoksa araç yalnız
durum/çıktı anlaşmazlığını raporlar ve bilinçli olarak
`GT_YOK_KAZANAN_BELIRLENEMEZ` yazar.

GT varsa öncelik sırası sabittir:

1. en az yanlış `GECTI` (yanlış veri QC1'e geçmesin),
2. en çok tamamen doğru bölüm,
3. eşitse en az gereksiz blok.

Bir film iki ölçüm birimidir (`giris`, `cikis`); 100 film 200 bölüm eder.
200 bölümün GT'si tamamlanmadan veya motorlardan birinde `KONTROL_BEKLIYOR`
kalmışken araç kazanan ilan etmez. İki motorun kontrol crop'ları aynı model,
aynı deterministik ayar ve kayıtlı prompt digest ile okutulmalıdır. Model seçimi
yalnız tamamlanmış bu raporla yapılmalıdır.

## Bugünkü gerçek durum

Depoda henüz hiçbir `*.okuma.json` yoktur. Nash ve Jordan'ın mevcut çıktıları
bbox'lı ortak paketi üretmediği için gerçek 100-film koşusu bugün yapılamaz.
Motor, kontrol sözleşmesi ve ölçüm aracı hazırdır; sıradaki bağımlılık okuyucu
adaptörlerinin aynı dört paketi üretmesidir.
