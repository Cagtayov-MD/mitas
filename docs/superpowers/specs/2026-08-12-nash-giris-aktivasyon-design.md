# NASH/track-kunye — GİRİŞ Segmentini Aktifleştirme

**Tarih:** 2026-08-12 · **Tasarım:** Opus · **Uygulama:** Sonnet
**Talimat:** Çağatay — "nash için girişi aktif hale getir."

---

## 1. Durum

`track_kunye` (MESSİ/NASH + İBRAHİMOVİC + RONALDO, 3 kol) **yalnız çıkış** karelerinde
koşuyor. Fonksiyonlar dizin-parametreli, kısıt yok — sadece giriş hiç beslenmiyor.

Ölçüm (718 film): `frames/giris` **669** filmde, giriş master-PNG **672** filmde var —
çıkış master-PNG'den (**599**) daha yaygın. Altyapı hazır, kullanılmıyor.

**Ek değer:** NASH kendi havuzunu `havuz_derle_dizin` ile HAM `frames/giris`'ten kurar.
Yani `giris_jenerik` havuzunun altyazı-filtresinden GEÇMEZ. 2026-08-11 19:35 öncesi 118
filmi vuran ROI arızasına bağımsız ikinci bir okuma yolu sağlar.

## 2. Segmente bağlı 5 sabit kod

| # | yer | bugün | giriş karşılığı |
|---|---|---|---|
| 1 | `_pipe_track_kunye.py:126` | `out = clip_dir/"track_kunye"` | `track_kunye_giris` |
| 2 | `_pipe_track_kunye.py:55-56` `master_secim()` | `reading_master_runaware.png` + `_manifest.json` | `giris_reading_master_runaware.png` + `giris_reading_master_runaware_manifest.json` |
| 3 | `_pipe_track_kunye.py:70` `master_kare_sayisi()` | aynı manifest | aynı giriş manifesti |
| 4 | `_pipe_track_kunye.py:109` `kunye3_yaz()` | `{base} kunye3.txt` | `{base} kunye3_giris.txt` |
| 5 | `mitas_pipeline.py:4400-4402` | yalnız `cikis_frames` | ikinci çağrı: `giris_frames` |

## 3. Tasarım

### 3.1 `_pipe_track_kunye.py` — `--segment` argümanı

```python
ap.add_argument("--segment", choices=("cikis", "giris"), default="cikis")
```

**Varsayılan `cikis`** — argümansız çağrı bugünkü davranışın BİREBİR aynısı olmalı (§5.1).

Segmentten türeyen yollar tek yerde hesaplanır, fonksiyonlara parametre geçilir:

```python
_SEG = {
  "cikis": {"out": "track_kunye",       "png": "reading_master_runaware.png",
            "man": "reading_master_runaware_manifest.json",       "k3": "kunye3.txt"},
  "giris": {"out": "track_kunye_giris", "png": "giris_reading_master_runaware.png",
            "man": "giris_reading_master_runaware_manifest.json", "k3": "kunye3_giris.txt"},
}
```

`master_secim(clip_dir, segment)` ve `master_kare_sayisi(clip_dir, segment)` imzalarına
segment eklenir. `kunye3_yaz(...)` dosya adını segmentten alır.

`ozet` sözlüğüne `"segment": <seg>` eklenir (manifest.json'da görünsün).

### 3.2 `mitas_pipeline.py` — ikinci çağrı

Mevcut çıkış bloğu (4395-4445) **aynen kalır**. ARDINA bağımsız bir giriş bloğu eklenir:

- Koşul: `MITAS_TRACK_KUNYE` açık **VE** `MITAS_TRACK_KUNYE_GIRIS` açık (varsayılan `1`)
  **VE** `giris_frames.is_dir()` ve içinde `*.png` var.
- Komut: mevcut komut + `--segment giris`, `--frames str(giris_frames)`.
- Ayrı zaman anahtarı: `timings["track_kunye_giris"]`.
- Ayrı olaylar: `track_kunye_giris_completed` / `_skipped` / `_failed`.
  Ronaldo bant uyarıları da ayrı adla: `ronaldo_giris_band_red` vb.
- `summary_obj["track_kunye_giris"] = {"status":…, "band":…, "dir": str(clip_dir/"track_kunye_giris")}`
- `write_json(clip_dir / "_DURUM.json", summary_obj)` çağrısı korunur.
- **FAIL-SAFE:** giriş kolundaki hata/timeout çıkış kolunu ve kararı ASLA etkilemez.
  Mevcut bloktaki `try/except` deseni birebir taklit edilir.

### 3.3 Maliyet

Giriş ~360 kare, çıkış ~720. Film başına ek süre kabaca çıkış kolunun yarısı
(ARŞIN'da çıkış 135 sn → giriş ~70 sn beklenir). Kill-switch: `MITAS_TRACK_KUNYE_GIRIS=0`.

## 4. Kapsam dışı

- Giriş ve çıkış dökümlerini BİRLEŞTİRMEK. Bu iş yalnız giriş kolunu **üretir**;
  künyeye/PDF'e katmak ayrı iş. `track_kunye` gölge sözleşmesi (üretime dokunmaz) korunur.
- `giris_jenerik` havuzunun altyazı filtresi / ROI arızası — ayrı iş.
- 118 hasarlı filmin yeniden işlenmesi — ayrı iş, Çağatay'ın kararı.

## 5. DEĞİŞMEZLER

### 5.1 Çıkış kolu bit düzeyinde aynı
`--segment` verilmeden yapılan çağrı bugünkü çıktının aynısını üretmeli:
`track_kunye/` dizin adı, `{base} kunye3.txt` dosya adı, manifest alanları (`segment`
alanının EKLENMESİ hariç). Bir filmde önce/sonra koşturup `frame_dokum.txt`,
`master_dokum.txt`, `ronaldo_kunye.txt` diff'i **sıfır satır** olmalı.

### 5.2 Karar/PDF/teslim değişmez
`track_kunye` gölge katman. Giriş kolu eklenince `karar.pipeline.json`, `karar.view.json`,
PDF ve export çıktıları DEĞİŞMEMELİ. Bir test filminde bunların hash'i aynı kalmalı.

### 5.3 Giriş kolu çökerse film etkilenmez
Giriş kolu kasten bozulduğunda (örn. `--frames` olmayan dizin) pipeline `rc=0` ile
tamamlanmalı, `karar` üretilmeli, `track_kunye_giris_failed` olayı loglanmalı.

## 6. Test

`tests/test_track_kunye_giris.py`:
1. `--segment` yoksa yollar bugünküyle aynı (dizin/dosya adları).
2. `--segment giris` → `track_kunye_giris/`, `kunye3_giris.txt`,
   `giris_reading_master_runaware.png` seçilir.
3. `master_secim(..., "giris")` bayat manifest (`ibrahimovic_uretemedi`) → `(None, "master_bayat")`.
4. Giriş master yoksa → `(None, "master_yok")`, kol çökmez.
5. `mitas_pipeline` giriş bloğu: `giris_frames` boşken `track_kunye_giris_skipped`.
6. Giriş kolu exception atınca çıkış kolunun sonucu ve `karar` bozulmaz.
