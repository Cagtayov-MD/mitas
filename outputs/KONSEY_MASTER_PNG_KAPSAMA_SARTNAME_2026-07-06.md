Tüm kod-gerçeğim tam. Şimdi sentezimi yazıyorum. Kritik doğrulamalar:

1. **Join-kilidi ZATEN VAR** (satır 3330 `_jp_proc.wait()` → 3444 master). Eleştirmen haklı. TEZ-2'nin "havuz-hazır-olmadan koşabiliyor" iddiası kod-yanlış.
2. **`_has_fr` guard'ı HAM frames'i de sayıyor** (3442-3443: `giris_frames, cikis_frames`) AMA `_seg_source` havuz-boşsa boş liste dönüyor (254). Bu KRİTİK ince nokta: master-adımı ham-frames varsa TETİKLENİR ama havuz boşsa ÜRETMEZ → boşa koşar, çöp üretmez. Bu, "kötü yerine hiç" garantisidir.
3. **`cikis_yazi` master'a beslenMİYOR** (`_seg_source` sadece `{seg}_jenerik` okur, `cikis_yazi`'ya bakmaz). Eleştirmen + TEZ-2 haklı. Flag açmak master'ı 0 puan artırır.
4. **Giriş-motoru ZATEN çıkışa uygulanabiliyor** (`_cikis_fallback_pool` satır 1889-1890 `giris_jenerik_havuzu.py --frames cikis_frames --pool-name cikis_yazi`). Eleştirmen'in "3. yol"u yeni değil — altyapı CANLI, ama ÇIKTISI `cikis_yazi`'ya gidiyor ve master onu okumuyor.

Bu son bulgu sentezin ANAHTARI: 3. yolu gerçekleştirmenin yolu YENİ motor yazmak değil — mevcut `_cikis_fallback_pool` çıktısını `cikis_jenerik`'e (veya master'ın okuduğu bir kaynağa) sağlık-kapısı arkasından bağlamak.

---

# KONSEY SENTEZ — Master-PNG'yi jenerikli her filmde SAĞLIKLI hale getirme ŞARTNAMESİ

## 0. Sentezin temeli: 4 kod-gerçeği (hepsi bugün doğrulandı, eksen bunlara oturuyor)

| # | Doğrulanan gerçek | Kanıt (satır) | Sonuç |
|---|---|---|---|
| G1 | Master-adımı çıkış-havuz `wait()`'inden SONRA koşuyor — **join-kilidi zaten var** | `mitas_pipeline.py:3330-3334` (wait) → `3441-3452` (master) | "Havuz-join kilidi ekle" önerisi ÖLÜ (gereksiz iş). Eleştirmen + TEZ-1 haklı. |
| G2 | `_has_fr` guard'ı HAM `giris_frames/cikis_frames`'i DE sayar → master-adımı TETİKLENİR; ama `_seg_source` havuz-boşsa BOŞ liste döner → **üretmez, çöp basmaz** | `mitas_pipeline.py:3442-3443` + `master_png_monitor.py:254-255` | Master-adımı "boşa koşar ama zararsız". Üretim-yolu fail-safe KOD-DÜZEYİNDE garantili. |
| G3 | `cikis_yazi` master'a **beslenmiyor** (`_seg_source` yalnız `{seg}_jenerik` okur) | `master_png_monitor.py:243-261` + `mitas_pipeline.py:1872` | `MITAS_CIKIS_FALLBACK_POOL=1` açmak çıkış-master'ı **0 puan** artırır. TEZ-2 + Eleştirmen haklı; TEZ-1'in "flag aç → kapsama artar" imâsı ÖLÜ. |
| G4 | Giriş-motoru (`giris_jenerik_havuzu.py`) çıkış-karelerine ZATEN uygulanabiliyor (`--frames cikis_frames --pool-name cikis_yazi`) — altyapı CANLI | `mitas_pipeline.py:1889-1890` + `giris_jenerik_havuzu.py:479-491` | Eleştirmen'in "3. yol"u yeni motor GEREKTİRMEZ. Sadece çıktı-yönlendirmesi + sağlık-kapısı ekler. |

**Eksen kayması:** G1+G3 iki tezin de önerdiği iki büyük müdahaleyi öldürüyor (join-kilidi gereksiz, fallback-flag etkisiz). Geriye kalan gerçek problem tek cümleye iner: **çıkış-master'ı yalnız `cikis_jenerik`'ten besleniyor, o havuz da `not_found`/`review_scene_text`'te BOŞ kalıyor (53 film) — çünkü credit_detect sıkı `_accepted` kapısı bu durumları reddediyor (`_jenerik_pool.py:82-87`).**

---

## 1. SEÇİLEN STRATEJİ + NEDEN

**Seçim: "Kaynak-simetri + iki-katmanlı sağlık-kapısı" (Eleştirmen'in 3. yolu, TEZ-2'nin kalite-disiplini içine gömülü, TEZ-1'in backfill'i başa alınarak).**

Üç adaydan neden bu:

- **TEZ-1 saf hali (fallback-master + gevşek kapı) REDDEDİLDİ:** G3 nedeniyle fallback zaten master'a gitmiyor; ayrıca gevşek-kapı Çağatay'ın SEVDİĞİ kaliteyi (footage-flood riski) tehlikeye atar. TEZ-1'in "gürültülü-master > master-yok" tersine-çevirmesi kabul edilemez.
- **TEZ-2 saf hali (hiç dokunma, master künyeden sıkı olsun) EKSİK:** kalite-disiplini DOĞRU ama çıkış %70'i %70'te bırakır — Çağatay'ın hedefi ("jenerikli her filmde sağlıklı master") karşılanmaz. LOTR gerçek-kaçak, meşru değil.
- **3. yol (kaynak-simetri) SEÇİLDİ** çünkü:
  1. **credit_detect'e HİÇ dokunmaz** → künye-otoritesi/karar/PDF tamamen korunur (TEZ-2 kırmızı-çizgisi sağlam).
  2. Giriş'te **zaten CANLI ve Çağatay'ın sevdiği kaliteyi üreten** motoru (altyazı-eleme + `is_credit_text_line` süzgeci) çıkışa uygular → footage-flood riski motorun İÇİNDE zaten yönetiliyor, sağlık-kapısına daha az yaslanır.
  3. Altyapı zaten var (G4) → yeni motor değil, çıktı-yönlendirme + kapı.

**Kritik çerçeveleme (hedef tanımı):** Hedef "263 filmin hepsinde master" DEĞİL. Hedef = **jenerik OLAN her filmde sağlıklı master**. Metrik: `sağlıklı-master / (jenerik-var film)`. TACİZ/BEKARLIK gerçekten jeneriksizse master-yok = DOĞRU. Meşru-boşları paydadan çıkarırız.

---

## 2. BACKFILL TASARIMI — sağlık-KAPISIZ, üretim-yolu birebir tekrarı

**Karar: Backfill KAPISIZ (TEZ-1 haklı) — ama gerekçe Eleştirmen'inki: byte-nötr = drift-yasağı.**

Neden kapısız: Backfill'in girdisi tam olarak üretim-yolunun girdisidir (`{giris,cikis}_jenerik` havuzu). Aynı motoru (`master_png_monitor --once`) aynı dolu-havuza koşar. Üretim-yolunda OLMAYAN bir sağlık-kapısını backfill-yolunda uygulamak = iki yol arasında davranış-drifti = **byte-nötr ilkesinin ihlali**. Backfill üretim-yolunun idempotent tekrarıdır; ekstra hiçbir şey eklemez.

TEZ-2'nin "kapısız backfill = çöp fabrikası" endişesi G2 ile çürüyor: backfill dolu-havuzu okur, havuz zaten credit_detect-süzülmüş (`already_in_credit`/`found`/`review_boundary_ambiguous` — `_jenerik_pool.py:44,82-87`). Yani havuz-içi footage riski seçim-anında elenmiş. Backfill'in ürettiği master = üretim-koşusunun üreteceği master (aynı girdi, aynı motor).

**Backfill algoritması (`master_png_backfill.py`, YENİ, salt-ekleyici):**
```
her Database/<film> için:
  base = _delivery_base(film)                       # master_png_monitor'dan
  havuz_dolu = (frames/giris_jenerik/*.png) VEYA (frames/cikis_jenerik/*.png)
  master_var = ("<base> giris.png") VEYA ("<base> cikis.png") kökte var
  if havuz_dolu and not master_var:
      if --apply:
          subprocess: master_png_monitor.py --once <film> --base <base>   # DEĞİŞMEDEN
      else:
          rapor-satırı yaz (film, hangi havuz dolu, hangi master eksik)
```
- **Salt-ekleyici:** master-VAR filme ASLA dokunmaz (byte-nötr).
- **Kill-switch:** `MITAS_MASTER_BACKFILL=1` (pipeline entegrasyonu için; standalone araç default çalışır).
- **Kapsam:** 5 "dolu-master-yok" + `NO_JSON`'ın havuzu sonradan dolanları (~5-22 film). En yüksek ROI, en düşük risk. **BİRİNCİ ADIM budur** (TEZ-1 sıralaması doğru).

**Join-kilidi EKLENMEZ** (G1: zaten senkron). TEZ-1+TEZ-2'nin "master-adımı havuz-join'e kilitle" önerisi gereksiz iş.

---

## 3. DETECT-KAPSAMA — çıkış-zayıflığı + LOTR-kaçağı çözümü

### 3a. Çıkış %70 < giriş %94 asimetrisinin GERÇEK kökü (Eleştirmen'in öldürücü bulgusu, onaylandı)

İki havuz **AYNI motorla üretilmiyor**:
- **Giriş:** `giris_jenerik_havuzu.py` → ham-yazı-varlığı (credit_detect'e bakmaz, gevşek, yüksek-kapsama). %94.
- **Çıkış:** `_jenerik_pool.py → detect_frame_dir` → kredi-çapası doğrulaması (`_accepted` sıkı; `not_found`/`review_scene_text` reddi). %70.

Asimetri "kapanış scroll zorluğu" DEĞİL — **iki farklı seçim-felsefesi**. Çözüm: çıkışa da giriş-felsefesini (ham-yazı-varlığı) İKİNCİL kaynak olarak ver.

### 3b. Çözüm: `cikis_yazi`'yı master'a bağla — AMA sağlık-kapısı ARKASINDA (G3+G4 birleştirmesi)

Bu sentezin merkezi mühendislik hamlesi. İki parça:

**Parça-1 (üretim):** `_cikis_fallback_pool` ZATEN `cikis_yazi` havuzunu üretebiliyor (G4, satır 1889-1890) — ama sadece `MITAS_CIKIS_FALLBACK_POOL=1` iken ve çıktısı master'a gitmiyor (G3).

**Parça-2 (bağlama):** `master_png_monitor.py:_seg_source`'a **İKİNCİL kaynak** ekle: `cikis_jenerik` boşsa VE `cikis_yazi` doluysa → `cikis_yazi`'yı oku, AMA **sağlık-kapısından geçir** (Bölüm 4). Ayrı çıktı-damgası: manifest'te `source: cikis_yazi` (künye-otoritesiyle karışmasın; kod zaten kaynak-etiketi yazıyor, satır 300 `info["source"]=src`).

```
_seg_source(film, "cikis"):
  cikis_jenerik dolu → onu kullan (BUGÜNKÜ davranış, DEĞİŞMEZ)
  cikis_jenerik boş VE MITAS_MASTER_CIKIS_YAZI_KAYNAK=1 VE cikis_yazi dolu:
      → cikis_yazi frames döndür, kaynak="cikis_yazi_fallback"
      → gen_master bu master'ı ürettikten SONRA sağlık-kapısı KABUL/RED verir
  aksi → boş liste (BUGÜNKÜ "kötü yerine hiç")
```

- **Kill-switch:** `MITAS_MASTER_CIKIS_YAZI_KAYNAK=1` (pilotta OFF, kanıt-sonrası ON).
- **"yanlış>boş" ihlali mi?** HAYIR. O ilke KÜNYE-KARARI (PDF içeriği) için. `cikis_yazi` master'a giderken künye/VL otoritesine DOKUNMUYOR (ayrı damga). Master ham-görsel; kimseyi künyeye yazmaz. **Master için kural künyeden FARKLI olabilir — ama YÖN önemli:** master ham-görsel + ara-katman-yok olduğu için sağlık-kapısı ZORUNLU (aşağıdaki footage-flood riski). Yani "gevşek yön"de değil, "kapı-arkasında gevşek" yönünde.

### 3c. LOTR-kaçağı: pencere-sınırının DÜRÜST kabulü (Eleştirmen'in yıkımı, onaylandı)

TEZ-1'in "`cikis_yazi` LOTR'ı kurtarır" iddiası **kısmen yanlış**: `cikis_yazi` ham `frames/cikis` üzerinde çalışır (satır 1890), ve `frames/cikis` = credit_detect'in belirlediği çıkış-penceresi. LOTR gibi detektörün **pencereyi** kaçırdığı filmde kredi o pencerede yoksa `cikis_yazi` de boş kalır.

**Ayrım:**
- credit_detect pencere-doğru + küme-kaçağı (LOTR-tip-A) → `cikis_yazi` DOLAR → 3b kurtarır.
- credit_detect pencere-kaçağı (LOTR-tip-B) → `cikis_yazi` de boş → 3b kurtarmaz.

Tip-B için ayrı ikinci-geçiş (sabit-pencere) GEREKİR — ama bu **en spekülatif, en son** adım (Faz-4, DEFAULT-OFF A/B). Şartname tip-B'yi çözmeyi VAAT ETMEZ; dürüstçe "sonraki faz" der. Çoğu çıkış-boşluğu tip-A + not_found'dur; 3b onları kapsar.

---

## 4. FOOTAGE-BLOAT KALKANI + "SAĞLIKLI MASTER" ölçülebilir kriteri

**İki-katmanlı uygulama (kritik nüans — Eleştirmen'in metrik-düzeltmesiyle):**

| Kaynak | Kapı sertliği | Neden |
|---|---|---|
| `giris_jenerik`/`cikis_jenerik` (detektör-süzülmüş, BUGÜNKÜ) | Sağlık-skoru YALNIZ **damgalar/uyarır** (üretimi engellemez) | Havuz zaten temiz; byte-nötr için üretim-yolu davranışı DEĞİŞMEZ (G2 fail-safe zaten var) |
| `cikis_yazi` (fallback, 3b) | Sağlık-skoru **KABUL-KAPISI** (flood master'ı REDDET → slot boş) | Ham-yazı-seçimi footage-üstü-yazı geçirebilir; "kötü yerine hiç" burada devrede |

**"Sağlıklı" ölçülebilir kriter (deterministik, master zaten bellekte, EK MALİYET ~0):**

`_compose_reading_seg` ZATEN üretiyor (`master_png_monitor.py:88-91`): `strict_scroll_frac`, `kept_blocks`, `runs`, `size`. Bunlardan türet:

1. **BİRİNCİL — hizalama-düzenliliği (Eleştirmen'in kritik düzeltmesi):** kredi = sol/orta hizalı sütun (dar x-varyans); sahne-yazısı = dağınık x-konumu (geniş x-varyans). **text_frac TEK BAŞINA yetmez** — footage-ÜSTÜ-yazı yüksek text_frac üretir, düz-footage'ı eler ama sahne-yazısını elemez. Hizalama birincil ayırıcıdır.
2. **BİRİNCİL — scroll/blok-tutarlılık:** `strict_scroll_frac` tutarlı + `kept_blocks > 0`. Kredi statik/düzenli-scroll; sahne-yazısı footage'la kayar (tutarsız).
3. **İKİNCİL — text-mask oranı:** `text_frac < 0.15` → düz-footage-flood REDDET (footage-flood kalkanı, ama tek başına değil).
4. **İKİNCİL — yükseklik-patlaması:** master yüksekliği makul-üst-sınırı aşıyorsa (örn. >8000px, epilog/sahne-flood imzası) → şüpheli-bayrak.

**Kill-switch:** `MITAS_MASTER_HEALTH_GATE`. **ÖLÇÜM-modu ÖNCE** (skorla+yaz, KABUL etme) → mevcut 184 çıkış-master'ın kaçı geçiyor gör, eşiği VERİYLE koy (TEZ-2 sıralaması doğru).

---

## 5. MEŞRU-BOŞ vs DETECT-KAÇAĞI ayrımı — havuz-boşluğu DEĞİL, detektör-STATUS

**Eleştirmen'in D-ekseni düzeltmesi onaylandı:** İki tezin "havuz-boş = meşru-boş" proxy'si YANLIŞ — çünkü havuz-boşluğunun 3 ayrı kökü var:
- `not_found` (conf=0.0, gerçek footage/jeneriksiz) → meşru-boş ✓
- `not_found` (LOTR, detektör-kaçağı) → meşru-boş DEĞİL ✗
- `NO_JSON` (adıma ulaşmadı, çökme/eski-koşu) → boş ama sebep timing ✗

**Doğru ayraç: detektör-STATUS** (manifest'te ZATEN var — `_jenerik_pool.py:144-159` `status`/`confidence`/`reason` yazıyor; `mitas_pipeline.py:3416` `_detector_status` okuyor).

**Ayrım kuralı:**
| Durum | İşaret | Aksiyon |
|---|---|---|
| `NO_JSON` (manifest yok) | Adıma ulaşmadı | **Backfill** (Bölüm 2) — çökme/eski-koşu, havuz sonradan dolabilir |
| `not_found` + `cikis_yazi` DOLAR | Detect-kaçağı (LOTR-tip-A) | **3b fallback + sağlık-kapısı** |
| `not_found` + `cikis_yazi` BOŞ | Meşru-boş (TACİZ) VEYA pencere-kaçağı (tip-B) | Master ÜRETME (doğru varsayılan); tip-B Faz-4'e |
| `already_in_credit`/`found` + master-yok | Timing/çökme | **Backfill** |

`cikis_yazi`'nın kendi yazı-varlığı testi (altyazı-eleme + `is_credit_text_line`) meşru-boş ile tip-A kaçağı DOĞAL ayırır: gerçekten jeneriksizse `cikis_yazi` da boş → master üretilmez, DOĞRU. Ekstra ayrım-mekanizması gerekmez.

---

## 6. KİLL-SWITCH + GOLDEN KORUMA

| Yeni davranış | Kill-switch | Default | Golden etkisi |
|---|---|---|---|
| Koşu-sonu backfill | `MITAS_MASTER_BACKFILL` | pilotta OFF → kanıt-sonrası ON | YOK (üretim-KARARINA dokunmaz; fail-safe korunur) |
| `cikis_yazi` master-kaynağı | `MITAS_MASTER_CIKIS_YAZI_KAYNAK` | OFF (Faz-3'e kadar) | YOK (yalnız BOŞ-çıkış filmlerde tetiklenir; dolu-havuz filmine dokunmaz) |
| Sağlık-kapısı | `MITAS_MASTER_HEALTH_GATE` | ÖLÇÜM-modu → kabul-modu kanıt-sonrası | YOK (ana havuzda yalnız damgalar) |
| LOTR ikinci-geçiş (Faz-4) | `MITAS_MASTER_CIKIS_2GECIS` | OFF | YOK |

**Golden garantisi:** Hiçbiri credit_detect / künye-karar / PDF'e dokunmaz. Master-PNG `gen_master` fail-safe'i (`produced=False` iken eski master KORUNUR, satır 326-333; hata iken pipeline bozulmaz, satır 3472-3476) DEĞİŞMEZ. Golden 28/28 sabit kalır (golden künye-kararını ölçer, master-PNG'yi değil).

**Byte-nötr:** Tüm yeni davranışlar default-OFF → mevcut çıktı byte-byte aynı. Açıldıklarında yalnız master-YOK/BOŞ filmlere dokunurlar; var-olan master'ı asla overwrite etmezler.

---

## 7. KADEMELİ PLAN (kanıt-kapılı)

**Faz-0 (bugün, SIFIR risk — salt-okur):**
`master_png_backfill.py` SALT-OKUR (`--apply` YOK): 293 filmi gez, `havuz-dolu ∧ master-yok` adaylarını + her filmin detektör-status'unu (NO_JSON/not_found/found) listele.
- **Kanıt-kapısı:** Kaç film? (beklenen ~5-22). 5 "dolu-master-yok" filmi tek-tek doğrula.

**Faz-1 (Backfill canlı):** `--apply` ON, `MITAS_MASTER_BACKFILL=1`.
- **Kanıt-kapısı:** çıkış-master 184→~206 (+22 hedef), regresyon=0 (var-olan master dokunulmadı → byte-nötr diff boş), golden 28/28.

**Faz-1.5 (Sağlık-kapısı ÖLÇÜM-modu):** kapıyı mevcut 184+22 çıkış-master'a skorla-yaz, KABUL ETME.
- **Kanıt-kapısı:** kaçı hizalama+scroll+text_frac eşiklerini geçiyor? Eşiği bu dağılımdan VERİYLE koy. `master_qc10` skill ile düşük-skorlu 10 master'ı gözle-doğrula (skor footage-flood'la korele mi?).

**Faz-2 (Detect-kapsama pilotu — 10 film):** `not_found` 53'ten 10 seç (5 gerçek-kredili [KOMİSER/İŞARET DİREĞİ tip] + 5 meşru-boş-şüpheli [TACİZ tip]). `MITAS_CIKIS_FALLBACK_POOL=1` + `MITAS_MASTER_CIKIS_YAZI_KAYNAK=1` + `MITAS_MASTER_HEALTH_GATE=kabul` AÇ.
- **Kanıt-kapısı:**
  - Gerçek-kredili 5'te sağlıklı-master üretildi mi? (hedef ≥4/5)
  - Meşru-boş 5'te master ÜRETİLMEDİ mi? (hedef 5/5 — yanlış-pozitif=0)
  - `master_qc10` ile 10 master gözle: footage-flood var mı? (hedef 0)

**Faz-3 (Tam salım):** Faz-2 temizse `MITAS_MASTER_CIKIS_YAZI_KAYNAK` + sağlık-kapısı default-ON.
- **Kanıt-kapısı:** çıkış-master ~206→~250+; meşru-boşlar hariç kalır (DOĞRU %100).

**Faz-4 (LOTR-tip-B, en spekülatif — OPSİYONEL):** pencere-kaçağı için master-özel sabit-pencere ikinci-geçiş, `MITAS_MASTER_CIKIS_2GECIS=1`, DEFAULT-OFF A/B. Yalnız Faz-3 sonrası kalan boşlukları ölçtükten sonra.

Her faz: byte-nötr, kill-switch'li, fail-safe; hiçbiri karar/PDF'e dokunmaz.

---

## 8. İLK ADIM (bugün yazılacak kod — dosya + fonksiyon)

**Dosya:** `E:\MITAS\scripts\master_png_backfill.py` (YENİ, salt-ekleyici, kill-switch'li).

**Fonksiyon imzaları:**
```python
def scan_candidates(db_root: Path) -> list[dict]:
    """Her Database/<film> için: (film, base, havuz_dolu, master_var, detector_status)
    döndür. Sadece (havuz_dolu ∧ ¬master_var) adaylarını işaretle. SALT-OKUR."""
    # base = master_png_monitor._delivery_base(film) (import ederek yeniden-kullan)
    # havuz_dolu = frames/giris_jenerik/*.png VEYA frames/cikis_jenerik/*.png
    # master_var = "<base> giris.png" VEYA "<base> cikis.png" kökte
    # detector_status = frames/jenerik_detection.json'dan status (yoksa "NO_JSON")

def apply_backfill(film: Path, base: str) -> dict:
    """master_png_monitor.py --once <film> --base <base> koş (DEĞİŞMEDEN).
    Salt-ekleyici: master-VAR filme dokunma. FAIL-SAFE: hata bir sonraki filmi bozmaz."""

def main(argv):
    """--db (default Database), --apply (yoksa salt-okur rapor), --limit.
    Rapor: aday-sayısı + detector-status dağılımı (kaç NO_JSON / not_found / found)."""
```

**Bugün çalıştırma (kanıt toplar, HİÇBİR ŞEY üretmez):**
```
python scripts/master_png_backfill.py --db Database          # salt-okur
```
Bu tek komut: (a) Bölüm-2 backfill'in gerçek kapsamını kanıtlar, (b) 5 "dolu-master-yok" filmi tek-tek doğrular, (c) Bölüm-5 detektör-status dağılımını (NO_JSON vs not_found) canlı-ölçer. Kanıt gelince aynı script'e `--apply` eklenir.

**Dosya DEĞİŞTİRİLMEDİ** (bu oturum salt-okur; kod-gerçeği doğrulandı, şartname üretildi).

---

## KESİN HÜKÜM ÖZETİ (tezler arası)

| Eksen | Hüküm | Dayanak |
|---|---|---|
| Backfill | YAŞAR, kapısız, üretim-yolu tekrarı. Join-kilidi ÖLÜ. | G1 (kilit zaten var), G2 (fail-safe zaten var) |
| Fallback-flag tek başına | ÖLÜ (0 puan). `cikis_yazi`→master **bağlaması** + sağlık-kapısı gerekir. | G3 (master `cikis_yazi` okumaz) |
| 3. yol (kaynak-simetri) | SEÇİLDİ. Altyapı zaten var, yeni motor gerekmez. | G4 (`_cikis_fallback_pool` canlı) |
| Sağlık metriği | Hizalama+scroll BİRİNCİL; text_frac İKİNCİL (tek başına footage-üstü-yazıyı elemez). ÖLÇÜM-modu önce. | Eleştirmen düzeltmesi + `master_png_monitor.py:88-91` |
| Meşru-boş ayrımı | Detektör-STATUS (NO_JSON≠not_found), havuz-boşluk-proxy DEĞİL. | Eleştirmen D-düzeltmesi + `_jenerik_pool.py:144-159` |
| Master için "yanlış>boş" | Master ham-görsel → kural künyeden FARKLI olabilir, AMA sağlık-kapısı ZORUNLU (gevşek-yön değil, kapı-arkasında). | TEZ-2 kalite-disiplini + TEZ-1 medyum-ayrımı |

**Okunan/doğrulanan dosyalar (kanıt):**
- `E:\MITAS\scripts\mitas_pipeline.py:3327-3476` (havuz-wait senkron G1 + master-adımı `_has_fr` G2 + master fail-safe), `1869-1945` (`_cikis_fallback_pool` G4 + giriş-havuz motoru)
- `E:\MITAS\OCR-worktree\master_png_monitor.py:83-93` (sağlık-sinyalleri hazır), `243-261` (`_seg_source` `cikis_yazi` reddi G3), `264-334` (`gen_master` fail-safe + kaynak-damgası)
- `E:\MITAS\scripts\_jenerik_pool.py:44,82-88,144-164` (sıkı `_accepted` = çıkış-zayıflık kökü + manifest-status meşru-boş ayracı)
- `E:\MITAS\scripts\giris_jenerik_havuzu.py:472-498` (`--frames`+`--pool-name` = kaynak-simetri altyapısı G4)