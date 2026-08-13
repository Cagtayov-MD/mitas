# Kobe giriş bloğu — tasarım

> Opus tasarımı, Sonnet uygular. 2026-08-13.
> Amaç: giriş jeneriğinin **bir tavrı olsun** — bugün boş kalıyor.
> Kalite/geliştirme ayrı faz; şimdi sistem ayağa kalkıyor.

## İlke

**Yaklaşım taşınır, kod taşınmaz.** `scripts/giris_jenerik_havuzu.py`'nin
*stratejisi* buraya gelir; dosyanın kendisi eski yerinde kalır (33 KB,
üretimde çalışıyor, dokunulmaz).

Kobe'nin zaten kendi aletleri var — `src/kutu.py` (Paddle det: "kutu var mı")
ve `src/icerik.py` ("bu satır kredi metni mi"). Giriş bloğu **bunları**
kullanır, yeni kopya almaz.

**`src/motor.py`'ye TEK SATIR dokunulmaz.** Çıkışın %94.5'i korunur.

---

## Giriş ile çıkış arasındaki temel fark

| | Çıkış | Giriş |
|---|---|---|
| Aranan | **başlangıç** (bitiş = filmin sonu) | **başlangıç + bitiş** |
| Krediler | blok halinde sona kadar akar | footage arasına **serpilir** |
| Ayraç | `SON_ERISIM=0.82` — sona ulaşmalı | ters çalışır, **kullanılamaz** |
| Pencere | son 600 sn | **ilk 240 sn** (`MITAS_OCR_HEAD`) |

Bu yüzden giriş iki adımdır: önce **(a) sınır**, sonra sınırın içinde
**(b) havuz**.

---

## (a) SINIR — mevcut motor ÇAĞRILIR

`core/pipelines/ocr/jenerik_detector.py` (921 satır, 9 üretim tüketicisi)
kopyalanmaz, **çağrılır**. Repo kökü `sys.path`'e eklenir.

**Gerçek imza** (`jenerik_detector.py:778`, doğrulandı):

```python
sys.path.insert(0, os.environ.get("MITAS_PROJECT_ROOT", "/opt/mitas"))
from core.pipelines.ocr.jenerik_detector import detect_from_frames

bolge = detect_from_frames(dizin, fps=2.0, window_start_sec=0.0, prefer="first")
```

**Dönen sözlük** (`_region_dict`, satır 547-561) — kare numaraları HAZIR
geliyor, dönüşüm gerekmez:

```python
{"found": True, "type": ..., "quad_type": ...,
 "start_sec": 12.5,  "end_sec": 96.0,
 "start_frame": 25,  "end_frame": 191,     # ← doğrudan kullanılır
 "confidence": 0.71, "low_conf": False,
 "bg_motion": ..., "text_motion": ..., "scroll_dy_px": ..., "strategy": ...}
```

Bulunamazsa: `{"found": False, "confidence": 0.0, "low_conf": True,
"start_frame": None, "end_frame": None, "reason": "no_frames"}`.

> `prefer="first"` verildiğinde motor **kendiliğinden** `_apply_ocr_refine_end`
> çağırıyor (satır 791) — *"GİRİŞ: jeneriğin bittiği (film başladığı) anı da
> bul"*. Yani bitiş sınırı zaten bu çağrının içinde. Ekstra iş gerekmiyor.

Güven kapısı — üretimin kuralı birebir (`mitas_pipeline.py:1985-1990`):

```
güven ≥ GUVEN_ESIK  →  bas = start_sec, bit = end_sec
güven <  GUVEN_ESIK →  bas = 0.0,       bit = PENCERE_SN   (sabit geri düşüş)
```

`GUVEN_ESIK` `config.yaml`'a yazılır. Düşük güvende **sessizce tahmin
edilmez** — sabit pencereye düşüldüğü `kanit`'e yazılır
(`sinir_kaynagi: "tespit" | "sabit"`).

Motor patlarsa → `ARIZA(sinif="GIRIS_SINIR")`. Sessizce sabit pencereye
düşmek YASAK — arıza arızadır.

---

## (b) HAVUZ — yaklaşım `giris_jenerik_havuzu.py`'den, aletler Kobe'den

Sınırın içindeki her kare için:

| Adım | Nasıl | Kural |
|---|---|---|
| 1. Kutu var mı | `kutu.kutu_analiz(yol)` | kutu yoksa → **footage**, alınmaz |
| 2. Metni oku | `icerik` üzerinden OCR satırları | — |
| 3. Altyazı ele — **konumsal** | satır bbox y-merkezi ≥ `ALT_BANT` (kare yüksekliğinin oranı) | alt bantta → altyazı say |
| 4. Altyazı ele — **metinsel** | `icerik`'in kredi-metni testi | kredi değilse → say ma |
| 5. Karar | **satır-bazında OR**: kareye ≥1 meşru kredi satırı yeterse **AL** | recall önceliği |
| 6. Dedup | aynı metin imzasını taşıyan kareler → **teke indir** | imza = kredi satırları sıralı-birleştirilmiş |

**Recall kuralı (asıl kaynaktan alınır):** OCR/okuma hatası olan kare
**koşulsuz havuza alınır** — *"okunamadı > yanlış oku"*. Footage (0 satır)
alınmaz.

Bu, `giris_jenerik_havuzu.py` docstring'indeki tasarım kararının aynısı
(3 bağımsız Sonnet önerisi + Opus hakem, 2026-06-29).

---

## Sözleşme değişikliği

Giriş **iki sınır** taşır. `Cikti`'ya iki alan eklenir — **yalnız giriş
doldurur**, çıkış `None` bırakır:

```python
bitis_kare: int | None = None
bitis_sn:   float | None = None
```

`sozluk()` içinde `BULUNDU` bloğuna eklenir. Çıkışta `None` kalır ve JSON'a
yazılır (tüketici "giriş mi çıkış mı" ayrımını `bolum` alanından yapar).

Üç durum aynen geçerlidir:

| durum | Girişte anlamı |
|---|---|
| `BULUNDU` | Giriş jeneriği bulundu — `baslangic_*` + `bitis_*` dolu |
| `KREDI_YOK` | Film jeneriksiz başlıyor (doğrudan sahneye giriyor) |
| `ARIZA` | Okunamadı. `GIRIS_SINIR` / `MOTOR` / `KARE_CIKARIM` |

---

## Kare çıkarımı

`main.py:kare_cikar()` bugün **yalnız kapanış** penceresi çıkarıyor
(`ss = sure - 600`). Bölüme duyarlı hale gelir:

```
cikis:  ss = max(0, sure - 600),  length = 600
giris:  ss = 0,                   length = 240     ← MITAS_OCR_HEAD değeri
```

**240'tır, 600 DEĞİL.** 600 kapanış simetrisinden uydurulmuştu, yanlıştı.

---

## Artefakt — girişte bitiş farklı

| | Çıkış | Giriş |
|---|---|---|
| `--uret klip` | `onset−10` → **filmin sonu** | `baslangic−10` → **`bitis_sn`** |
| `--uret kare` | onset−10'dan **kaynağın sonuna** | (b)'nin seçtiği **havuz kareleri** |

Girişte kare havuzu ardışık bir aralık DEĞİL — (b)'nin ayıkladığı seçili
karelerdir. Bu, `uretilen` künyesine yazılır:

```json
"uretilen": {"tip": "kare", "yol": "kareler", "adet": 34,
             "secim": "havuz", "taranan": 480, "elenen_footage": 402,
             "dedup_temsilci": 34}
```

Çıkışta `"secim": "aralik"` olur. Tüketici farkı buradan görür.

---

## Yerleşim

```
src/
├─ motor.py        ← ÇIKIŞ, DONMUŞ, dokunulmaz
├─ kutu.py         ← ORTAK alet (Paddle det)
├─ icerik.py       ← ORTAK alet (kredi metni)
└─ giris/
   ├─ TASARIM.md   ← bu dosya
   ├─ sinir.py     ← (a) mevcut motoru çağırır
   └─ havuz.py     ← (b) kutu.py + icerik.py ile filtreler
```

`main.py` yönlendirici olur — hangi bloğu çağıracağını bilir, işin nasıl
yapıldığını bilmez:

```python
if girdi.bolum == "cikis":
    import motor;  r = motor.tespit_v5(...)
else:
    from giris import sinir, havuz
    b = sinir.bul(dizin, config)
    r = havuz.sec(dizin, b, config)   # --uret kare istenmişse
```

---

## Kayıtlı borçlar (gizlenmiyor)

1. **Giriş için GT ve ölçüm yatağı YOK.** "Kobe %94.5" yalnız **çıkış** için
   geçerlidir. Giriş hakkında hiçbir sayı yoktur. Yatak tarifi:
   `EKSIKLER.md` G5/G6.
2. **Kule sınırı bilerek esnetildi** — `jenerik_detector` kule dışından
   çağrılıyor. Kopya alınmadı çünkü 921 satır + 2 iç bağımlılık + 9 üretim
   tüketicisi var (dördüncü kopya borcu olurdu).
3. `giris_jenerik_havuzu.py`'nin **yaklaşımı** alındı, kodu değil. İkisi
   zamanla ayrışabilir; ayrışırsa hangisinin doğru olduğu **ölçülmemiştir**.

## Değişmez

Her adımda: `motor.py`'ye dokunulmaz ve
`cd olcum && ../venv/bin/python olc_pool.py --paralel 8` →
**kapsam 110, genel %94.5, üretim %97.3, kredi-yok 29/29.**
Sapma varsa iş geri alınır.
