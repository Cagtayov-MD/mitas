# RONALDO — Ghost Çapraz-Denetim Katmanı (Tasarım)

> İsimler (Çağatay, 2026-07-30): İBRAHİMOVİC = master-PNG motoru, MESSİ =
> framehavuz kare seçicisi, **RONALDO = ikisinin çaprazını denetleyen ghost
> katman**. "2. seçenek +1": iki motor da tam koşar, Ronaldo üstlerinde.

> Onay durumu: mimari Çağatay tarafından dikte edildi (2026-07-30 akşam);
> bu spec detay vidalarını konsey kırmızı-takım bulgularıyla kilitler.
> Konsey turu: GLM + Nemotron cevapladı (tam raporlar:
> scratchpad/ronaldo_konsey_cevap.md → kalıcı özet bu dosyada);
> Kimi bakiye-askıda, MiniMax bağlantı hatası.

## Amaç

Bugüne kadar hiçbir motorun veremediği sinyali üretmek: **"bu filmde kayıp
olabilir, gel bak."** Kanıtlanmış gerçek (2026-07-30 teşhisi): motorlar kendi
kaybını bilemez (Messi alarmı 5 kayıp filmde sessiz; exit_kesim 0.85 güvenle
558 kare sildi, içinde koca rulo vardı). Ama motorlar **birbirinin** kaybını
görür: rhum-bulvari'de İbrahimovic, Messi'nin düşürdüğü AZZI/MORAND sayfasını
yakaladı; hayat-ağacı'nda Messi+deepseek, Paddle'ın hiç okuyamadığı Farsça'yı
okudu. Ronaldo bu çapraz görüşü sistemleştirir.

## Boru hattı (üretim akışı, film başına)

```
ham havuz (dk-havuzu)
  ├─► jenerik-havuzu ─► İBRAHİMOVİC ─► master.png ─► deepseek ─► master-künye ─┐
  └─► FRAMEHAVUZ (MESSİ) ─► seçili kareler ─► deepseek ─► frame-dökümü ────────┤
                                                                               ▼
                                                                           RONALDO
                                                                               │
        ┌──────────────────────────┬───────────────────────────────────────────┤
        ▼                          ▼                                           ▼
  ronaldo_kunye.txt          ronaldo_fark.json                   manifest: confidence_band
  (birleşik künye, GÖLGE)    (fark listeleri + bantlar)          (green/yellow/red)
                                                                               │
                                              band≠green → film göz-QC kuyruğuna bayrak
```

Üç çıktı ayrı ayrı puanlanır: **İbrahimovic-yalnız / Messi-yalnız /
Ronaldo-birleşik** (Çağatay: "hepsinin ayrı ayrı performansını
değerlendireceğiz").

## Kilitlenen kararlar

1. **Ghost = gölge mod.** Ronaldo üretim `kunye.txt`/teslim klasörüne
   DOKUNMAZ; tüm çıktıları yan dosya. Terfi ancak pilot kanıtıyla (aşağıda).
2. **Tek okuyucu: deepseek.** master.png de Messi sayfalarıyla aynı motorla
   okunur — iki token seti aynı dili konuşur.
3. **Değerlendirme yatağı: TAZE klipler.** depo01 `Film Kapanış` +
   yanlarındaki XML kimlik; eski Ex_Frame yatağı kirli çıktı (yanlış-kayıt
   sihirli-flut + exit_kesim budamaları). 10-film pilot.
4. **Ölçüm metriği: fuzzy+KB'li recall/precision/F1.** Exact-token tuzağı
   kanıtlandı (havaci: kaybın %91'i Paddle-garble artefaktı); sadakat ölçümü
   ı/i-düzeltmeli fold + uzunluk-ölçekli fuzzy + KB-isim sayımına güncellenir.

## Ronaldo çekirdeği (konsey-revizeli)

### Diff öncesi hazırlık
- **İçsel dedup** (Nemotron #1): her kolun satırları önce kendi içinde
  fold-bazlı teke indirilir; diff yalnız kol-arası yapılır. Slit'in "YÖNETMEN
  YARDIMCISI YÖNETMEN YARDIMCISI" çift-basımı birleşime sızamaz; 40+ karakter
  ve tekrarlı 3-gram → "garble şüphesi", birleşim adayı değil, fark raporuna.
- **Halüsinasyon etiketi** (GLM #6 + Nemotron #6): deepseek çıktısında
  köşeli/normal parantez betimlemeleri ve düzyazı-imzalı satırlar (>8 kelime
  VE KB isabetsiz — 2026-07-30 taze dökümdeki "dinozor sahnesi" paragrafı
  sınıfı) `hallucination_candidate=True`; birleşime giremez, fark raporunun
  `hallucinations` listesine düşer.

### Eşleştirme
- **Fold:** Türkçe ı/i-düzeltmeli normalizasyon (sihirli-flut "yapim/yapım"
  açığı kapatılır).
- **Fuzzy eşiği uzunluğa bağlı** (Nemotron #7): `max_edit = max(1, len//5)`;
  <5 harf isimde fuzzy KAPALI (GLM #1: CAN/ÇAN, EMRE/EMREY tuzağı) — yalnız
  birebir veya KB üyeliği.
- **KB-çakışma kuralı:** iki varyant da KB'de AYRI kayıtlıysa birleştirme
  YAPILMAZ; `variants` alanında ikisi de tutulur.

### Birleşim
- **Birincil akış = Messi** (GLM #3 + Nemotron #3 mutabık): satır sırası
  Messi kare-indeksiyle sabitlenir (kronoloji = jenerik sırası). İbrahimovic
  satırları yalnız Messi'nin boşluklarını doldurur; eklenme koşulu: KB üyesi
  VEYA fuzzy-çaprazla doğrulanmış. Yazım bazı Messi varyantı; İbrahimovic
  varyantı `variants`'a.

### Güven sinyali — tek sayı YOK (Nemotron #5, GLM #5 mutabık)
- `overlap_ratio = |A∩B| / min(|A|,|B|)` ve `size_balance = min/max`:

| Bant | overlap | balance | Yorum |
|---|---|---|---|
| GREEN | ≥0.6 | ≥0.7 | normal tamamlayıcılık |
| YELLOW | 0.2–0.6 | ≥0.5 | kısmi örtüşme (çift-dil / dikey bölünme / kısmi kayıp) |
| RED | <0.2 | — | en az bir motor çökmüş ya da içerikler ayrışmış |

- **Ortak-körlük bayrağı** (Nemotron #2 + GLM #2): manifest'e
  `coverage_ratio = |seçilen∪master-kaynak| / dk-havuzu`; eşik altında
  `common_blind=True` ve confidence_band **null** — "iki kol uyumlu" hiçbir
  zaman "içerik tam" demek DEĞİLDİR. Ek yapısal çapa: dökümde
  "Directed by / Yönetmen / ©" sınıfı kapanış-çapası hiç yoksa
  `structural_anchor_missing=True` (exit_kesim-sınıfı girdi kesintisi şüphesi).

### QC ve Database bağları
- Band ≠ GREEN veya `common_blind` → film göz-QC kuyruğuna işaretlenir
  (teslim-kalite-kapısı ilkesi: Ronaldo kapıyı aşmaz, kapıya sinyal taşır).
- KB (DuckDB `mitas_people_index`, 10M ad) hem eşleştirme hakemi hem
  `[KB]` işaretleyici — pilot hattaki mevcut bağ aynen kullanılır.
- Gölge modda Database/teslim yazımı YOK.

## Ghost → terfi ölçütü (Nemotron #4 + GLM #4 birleşik)

Terfi ancak: 10-film pilotta
`F1_ronaldo ≥ max(F1_ibra, F1_messi) + 0.02` **VE**
`precision_ronaldo ≥ en iyi tekil precision − 0.03` **VE**
hiçbir filmde `common_blind` ihlali **VE** `garble_leak_ratio < 0.05`.
10 filmin ≥3'ünde birleşim en iyi tekilin altındaysa terfi RED, ghost devam.
Recall tek başına ASLA terfi ettirmez (halüsinasyon-recall şişmesi tuzağı).

## Reddedilen konsey önerileri (gerekçeli)

- **GLM: deepseek öncesi zorunlu cv2 metin-dedektör kapısı.** RED — det-körlüğü
  bu projenin kanıtlı baş belası (hayat-ağacı Farsça: Paddle det 0-3 kutu/kare;
  det-kapısı olsaydı o filmi yine kaybederdik). Yerine parantez/düzyazı
  heuristiği + Messi'nin mevcut std≥3 içeriksiz-kare kapısı.
- **GLM: rol-çapa (role-anchor) regex ayrıştırması.** ERTELENDİ (V2) — rol
  ayrıştırma başlı başına alt-sistem; uzunluk-kapılı fuzzy + KB-çakışma kuralı
  keskin kenarı şimdilik ucuza kapatıyor.
- **GLM: varyant seçimini OCR-kalite metriğiyle yap.** Sadeleştirildi —
  birincil akış zaten Messi; ayrı kalite metriği YAGNI.

## Yapı

- `harness/track_kunye/ronaldo.py` — bağımsız modül:
  `capraz(messi_dokum, master_dokum, kb) -> RonaldoSonuc(birlesik, fark,
  band, bayraklar)`. Saf metin-işlem (OCR çağırmaz) → sentetik testlerle
  TDD'lenebilir.
- `pilot_hat.py` genişler: master.png'yi de deepseek'le okuyan
  `oku_master()` + Ronaldo çağrısı.
- Üretim entegrasyonu (mitas_pipeline bağı) terfi SONRASI ayrı karar.

## Test stratejisi (TDD — kırmızı önce)

Konsey senaryoları test vakası olur: çift-basım garble sızması; ortak-körlük
0/0→NaN; sıra korunumu (Messi omurga); CAN/ÇAN kısa-isim tuzağı; EMREY fuzzy
tuzağı; çift-dil YELLOW bandı; motor-çöküşü RED bandı; halüsinasyon paragrafı
dışlama; KB-çakışan varyant ayrı tutma; ı/i fold düzeltmesi.

## Ölçüm protokolü

Taze 10-film pilotu (depo01 Film Kapanış + XML kimlik): her film için üç kolon
(İbra/Messi/Ronaldo) × (recall, precision, F1 — fuzzy+KB metriği) + göz-QC
(her birleşik künye açılıp bakılır) + confidence_band dağılımı. Terfi kararı
bu tabloyla; sonuçlar karar dokümanına işlenir.

## Karar geçmişi

- 2026-07-30: Çağatay mimariyi dikte etti ("çapraza ronaldo ismini ver...
  ghost bir sistem ekle... hepsinin ayrı ayrı performansını değerlendireceğiz
  ... 2. seçenek +1").
- 2026-07-30 konsey kırmızı-takımı: GLM 6 kırılma + Nemotron 7 kırılma;
  9 öneri kabul, 2 red (det-kapısı, OCR-kalite-metriği), 1 erteleme
  (rol-çapa). Kimi bakiye-askıda, MiniMax bağlantı hatası — üç-sesli tur
  bakiye şarjına kadar iki-sesli.
- Sahte-güven dersi bu tasarımın çekirdeği: exit_kesim 0.85 güvenle 558 kare
  sildi (sihirli-flut rulosu içindeydi); bu yüzden Ronaldo hiçbir koşulda
  "uyum yüksek → içerik tam" çıkarımı YAPMAZ (`common_blind` +
  `structural_anchor_missing` bayrakları).
