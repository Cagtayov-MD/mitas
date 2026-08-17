# Kobe — eksikler listesi

> 2026-08-13 itibarıyla, koddan doğrulanmış durum. Her madde: **ne eksik ·
> neden önemli · nereye bakılacak · kaba maliyet**.
> Kararların gerekçesi `DURUM.md`, mimarî `KATALOG.md`.

---

# ÇIKIŞ (kapanış jeneriği)

## Yapıldı ✅

| | Kanıt |
|---|---|
| Motor kuleye taşındı, `figo` adı silindi | `src/motor.py` 1325 satır, commit `3577c8b9` |
| Kendi çalışma zamanı (paddle 3.3.1 + CUDA, 167 pin) | `venv/`, `venv_kur.sh` |
| Sözleşme — `Girdi`/`Cikti`/`ariza`, atomik yazım + `_TAMAM` | `sozlesme.py` |
| CLI — `tek` / `start`, idempotent toplu kuyruk | `main.py`, `kobe` |
| Artefakt — kare havuzu + sessiz klip, onset−10 sn | `--uret kare\|klip` |
| Bölüm ayrımı — `out/<film>/cikis/` | `--bolum` |
| Ölçüm yatağı — 120 film + GT, kule içinde | `olcum/`, `havuz/` (28 GB) |
| **Üç ölçüm kapısı, sapma sıfır** — %94.5 / %97.3 / 29-29 | `raporlar/olcum_*.json` |
| Golden kanarya (tek film, saniyeler) | `golden/tek_film.json` |
| 69 test | `tests/` |
| Belgeler | `KATALOG.md`, `README.md`, `CHANGELOG.md`, `DURUM.md` |

## Eksik ❌

### E1 — Üretim hattı kuleyi KULE olarak kullanmıyor 🔴 EN ÖNEMLİ

`scripts/_jenerik_pool.py:282-283`:

```python
sys.path.insert(0, str(PROJECT_ROOT / "Allstar" / "kobe" / "src"))
import motor as _co
r = _co.tespit_v5(str(frames_dir))
```

Üretim, Kobe'yi **kütüphane** gibi import edip motoru doğrudan çağırıyor.
Sözleşme (`Girdi`/`Cikti`), `kobe.json`, `_TAMAM`, `out/` kuyruğu — **hiçbiri
devrede değil.** Yani kule kuruldu ama üretim ondan faydalanmıyor; kuyruk
mimarisinin ("Kobe binlerce filmi işleyip klasörüne bıraksın, LeBron oradan
alsın") hiçbir parçası çalışmıyor.

**Neden önemli:** Kulenin tüm değeri sözleşmede. Bu bağlanmazsa Kobe sadece
"yeri değişmiş bir .py dosyası" olarak kalır.

**Nereye:** `scripts/_jenerik_pool.py` → `kobe tek --kareler ... --film-id ...`
alt-süreç çağrısına çevrilmeli, çıktı `out/<id>/cikis/kobe.json`'dan okunmalı.
Desen mevcut: `scripts/tek_film_kunye.py:83` zaten "alt-süreç koş, stdout'tan
JSON çöz" yapıyor.

**Maliyet:** orta. Üretim durmuş olduğu için güvenli; ama pipeline'ın
`start_pos`/`PAD`/`METIN_KAPI` mantığı korunmalı.

---

### E2 — `src/` yeniden düzenlemesi yapılmadı 🟡

Şu an düz: `src/motor.py`, `src/kutu.py`, `src/icerik.py`.
`DURUM.md` Karar 2'de kararlaştırılan yapı:

```
src/
├─ cikis/   ← motor.py (DONMUŞ)
├─ giris/   ← yeni blok
└─ ortak/   ← kutu.py + icerik.py (alet)
```

**Neden önemli:** Giriş bloğu yazılmadan bu ayrım yapılmazsa, giriş kodu
çıkışın yanına düşer ve Çağatay'ın "karışmasın" kuralı ilk günden bozulur.

**Nereye:** `src/`, import satırları (`motor.py` içinde `import kutu as cb`,
`import icerik as cc`; `olcum/*.py`; `tests/`).

**Maliyet:** düşük — ama **ölçüm kapısı şart**: taşıma sonrası
`olc_pool.py --paralel 8` → %94.5 sapma sıfır olmalı.

---

### E3 — `kutu.py` / `icerik.py` kopya borcu 🟡

İkisi de `harness/kunye_kiyas/` altındaki asıllarının **kopyası**. Aslını
üretim okuyucusu kullanıyor (`scripts/_pipe_hibrit_okuma.py:111`).

**Neden önemli:** Rol sözlüğüne veya kutu mantığına yapılan bir düzeltme
yalnız bir kopyaya girer; diğeri sessizce eskir.

**Nereye:** okuma kulesi kurulduğunda kapanacak. `harness/kunye_kiyas/`
tamamen silinecek.

**Maliyet:** okuma kulesine bağlı, tek başına yapılmaz.

---

### E4 — `Database/<Film>/` hardlink görünümü yok 🟡

Spec §4.6'da tasarlandı, **hiç uygulanmadı**. `Allstar/kobe/*.py` içinde
`os.link` geçmiyor.

**Neden önemli:** Teslim edilen PDF'in yanında film klasöründen Kobe kararına
erişim yok. Symlink DEĞİL hardlink olmalı (kırık kısayol bu repoda zaten
sessiz arıza üretti: `models/lid/…` → `C:/Users/TRT03/…`).

**Nereye:** `main.py`, `Cikti.yaz()` sonrası. Aynı dosya sistemi şart
(`/dev/nvme3n1p2` — doğrulandı).

**Maliyet:** düşük.

---

### E5 — `%94.5` Ollama KAPALIYKEN ölçüldü 🟠

Kobe'nin dil yönlendiricisi Ollama'ya HTTP ile bağlanıyor (`src/motor.py`
~699). Erişilemezse `except Exception: continue` → hiç oy toplanmaz → **her
film için `'en'`**. Ölçüm 12:43'te yapıldı, Ollama 12:21'de durmuştu.

**Neden önemli:** Üretim Ollama açık koşacak. O zaman skor **~%93.6** (GUNLUK
2026-08-11: Farsça film 'ar'a geçiyor, onset 28 kare erkene kayıyor — üretim
ölçütünün içinde). Yani **üretimdeki gerçek sayı ölçülmedi.**

**Nereye:** `systemctl start ollama` + `olc_pool.py --paralel 8` → yeni
referans. İki sayı da kaydedilmeli (yönlendirici açık/kapalı).

**Maliyet:** düşük (~140 sn + ollama başlatma). **Ama dikkat:** mevcut tüm
kapılar Ollama kapalı varsayıyor; yeni referans alınırsa `DURUM.md` ve
`README.md` güncellenmeli.

---

### E6 — Toplu koşuda `maxtasksperchild` yok 🟡

`olcum/olc_pool.py:82` → `mp.get_context("spawn").Pool(paralel)` — işçi
tazeleme yok.

**Neden önemli:** 1000 filmlik koşuda işçi süreç bellek/VRAM biriktirir.
Çağatay'ın hedeflediği "7/24 akış" tam bu senaryo.

**Nereye:** `Pool(paralel, maxtasksperchild=25)`. Ayrıca `main.py`'nin `toplu`
fonksiyonu bugün **tek süreçte sırayla** koşuyor — paralel havuz hiç yok.

**Maliyet:** düşük.

---

### E7 — CPU/GPU kaynak bölüşümü ölçülmedi 🟢

Spec §4.7 hedefi: Kobe CPU'da geniş paralel, okuma kulesi GPU'da → "CPU GPU
boş kalmaz". Kobe'nin yükü ağırlıkla detection-only olduğu için CPU'ya uygun
görünüyor, **ama ölçülmedi**. Kayan-nokta farkı det kutusunu oynatabilir.

**Nereye:** 110 filmlik yatakta CPU koşusu, sapma sıfır kontrolü.

**Maliyet:** orta (CPU'da 2-4 kat yavaş).

---

### E8 — `--uret` üretim hattına bağlı değil 🟡

`--uret kare|klip` çalışıyor ama `scripts/_jenerik_pool.py` bunu kullanmıyor;
üretim kendi havuzunu kendi kuruyor. E1 çözülünce bu da çözülür.

---

### E9 — 6 bilinen hata (dar-VLM sınıfı) 🟢 bilinçli

`YALNIZ_SAVAŞÇI` −190 · `HARİKA_KÖPEK_5` −124 · `İNİŞLİ_ÇIKIŞLI` +89 ·
`İKİ_KAFADAR` / `KIZIL_HAYAT` / `TESS` (üretim ölçütünde doğru).
Çözüm yolu dar-VLM — ayrı proje, bu kulenin kapsamı dışında.

---

# GİRİŞ (giriş jeneriği)

## Yapıldı ✅ — 2026-08-13, commit `41bc799f`

| | Kanıt |
|---|---|
| Klasör ayrımı — `out/<film>/giris/` | `sozlesme.py`, `BOLUMLER` |
| Sözleşmede `bolum` + `bitis_kare`/`bitis_sn` (yalnız giriş doldurur) | `test_bolum.py` |
| **G1** `src/giris/sinir.py` — (a) sınır, `detect_from_frames` ÇAĞRILIR | gerçek koşu, güven 0.754 / 0.761 |
| **G1** `src/giris/havuz.py` — (b) havuz, `giris_jenerik_havuzu.py` stratejisi | 480 tarandı → 231 elendi → 75 temsilci |
| **G2** Giriş kare çıkarımı — `ss=0`, `length=240` | `main.py:kare_cikar()` |
| **G3** Giriş artefaktları — klip `bitis_sn`'de biter, kare = havuz seçimi | `klip.mp4` 21.000 sn (ffprobe), 75 PNG |
| **G4** `main.py` yönlendiricisi giriş bloğuna gidiyor | eski `ARIZA(BOLUM_HAZIR_DEGIL)` kaldırıldı |
| Çok-seçimli CLI — `--bolum giris,cikis --uret kare,klip` | `test_main_akis.py` |
| **Çıkış-giriş izolasyonu kodda kilitli** | `test_izolasyon.py` — 7 test, ihlal enjekte edilip doğrulandı |
| Güven kapısı **görünür** — sabit pencereye düşüş `kanit.sinir_kaynagi`'na yazılır | `sinir.py`, sessiz tahmin yok |

> **Giriş artık iş yapıyor.** Uçtan uca doğrulandı: iki farklı gerçek film,
> biri mp4 üretti biri kare havuzu. **Ama doğruluğu ölçülmedi** — aşağıya bak.

## Eksik ❌

### G5 — GT YOK 🔴

Giriş için tek bir insan-doğrulanmış kayıt yok. Çıkışta `dogrulama_sonuc.json`
110 film içeriyor (`gercek_onset` + gerekçe); girişin karşılığı **hiç yok**.

**Sonuç:** giriş kuleye girdiğinde **"Kobe %94.5" cümlesi yalnız çıkış için
geçerli olacak.** Giriş hakkında hiçbir sayı olmayacak. Bilinçli borç.

**Yatak tarifi (kararlaştırıldı):** 15 film — `filmtest/depo_3006/` altındaki
**tam** filmlerden (`filmtest/test_film_vl/` altındakiler VL deneylerinden
kalma **parça** dosyalar, film değil). İlk **240 sn**, fps 2 → 480 kare/film.
GT'yi Çağatay verir: motorun önerdiği sınırın etrafındaki kareler gösterilir,
~30 sn/film.

---

### G6 — Ölçüm yatağı ve ölçüm scripti YOK 🔴

`olcum/giris/` klasörü açıldı ama **boş**. Çıkıştaki `olc_pool.py`'nin
karşılığı yok.

**Dikkat — metrik şekli farklı:** çıkışta "onset sapması ±N kare"; girişte
sınır iki uçlu (`start` + `end`), yani iki sapma ölçülür. Çıkışın asimetrik
politikası (erken ≤120 / geç ≤20) girişe **doğrudan kopyalanamaz** —
girişte geç kalmak jeneriğin başını, erken kalmak film sahnesini alır.

---

### G7 — Golden kanarya YOK 🟡

Çıkışta `golden/tek_film.json` var (saniyelerde doğrulama). Girişin karşılığı
G5/G6'dan sonra kurulabilir.

---

### G8 — Uyarlanır pencere taşınmadı 🟡 *(uygulama sırasında ortaya çıktı)*

Kobe giriş penceresini **sabit 240 sn** çıkarıyor. Üretim hattı daha akıllısını
yapıyordu (`mitas_pipeline.py:1985-1990`): güven yeterliyse pencereyi
`end_sec+5`'e kadar **genişletiyor** (tavan 720 sn).

**Neden önemli:** gerçek koşuda SİLAHLAR_KONUŞUYOR'un kredi kareleri **476.
kareye** (≈238 sn) kadar yayıldı — yani 240 sn penceresinin ucuna dayandı.
Uzun jenerikli bir filmde pencere kesecek ve **kimse fark etmeyecek**.

**Yapılacak:** iki geçiş — önce sınır, sınır geniş çıkarsa pencereyi büyütüp
kareyi yeniden çıkar. G6 (ölçüm yatağı) kurulmadan bunun kazandırdığı
ölçülemez, o yüzden sonra.

---

### G9 — Havuz/sınır birim testi YOK 🟢 *(bilinçli)*

Doğrulama gerçek koşuya dayanıyor. Kapsam daraltması gereği ağır mock'lu test
yazılmadı. `test_izolasyon.py` yapıyı koruyor ama **mantığı** korumuyor —
havuz eşiği yanlış değişirse test yakalamaz, ancak G6 yakalar.

---

# Önerilen sıra — güncel

| Sıra | İş | Neden bu sırada |
|---|---|---|
| 1 | **E1** — üretim hattını sözleşmeye bağla (`_jenerik_pool.py` hâlâ `import motor` yapıyor) | Kulenin değeri burada açığa çıkar; yeni pipeline'ın girdisi |
| 2 | **E2** — `src/cikis/` + `src/ortak/` ayrımı | Giriş `src/giris/`'te ama çıkış hâlâ `src/motor.py` — simetri yarım |
| 3 | **G5 + G6** — giriş GT'si ve ölçüm yatağı | **Girişin doğruluğu bilinmiyor.** Bundan sonrası ölçüsüz gider |
| 4 | **G8** — uyarlanır pencere | G6 olmadan kazancı ölçülemez |
| 5 | **E5** — Ollama açıkken referans ölçüm | Üretimdeki gerçek sayı |
| 6 | **G7 + E4 + E6** — kanarya, hardlink, `maxtasksperchild` | Ucuz, bağımsız |
| 7 | **E7** — CPU/GPU bölüşümü | En son; optimizasyon |

## Değişmezler — her adımda geçerli

1. **`src/motor.py`'ye dokunulmaz.** Çıkışın %94.5'i ona bağlı.
2. **Çıkış girişin işine karışmaz.** Karar mantıkları birleşmez; ortak olan
   yalnız aletlerdir (`kutu.py`, `icerik.py`). `test_izolasyon.py` kilitler.
3. **Çıkışa dokunan iş** `olc_pool.py --paralel 8` → **%94.5 sapma sıfır**
   ile doğrulanır. *Yalnız çıkışa dokunulduğunda* — giriş işi bu kapıya tabi
   değil (Çağatay, 2026-08-13: *"ölçüm şu an yapılacak iş değil"*).
