# Allstar — Kobe Kulesi Taşıma Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `harness/kunye_kiyas/` içindeki jenerik-başlangıç motorunu, kendi çalışma zamanı ve sözleşmesi olan bağımsız bir kuleye — `Allstar/kobe/` — ölçüm sapması sıfır olacak şekilde taşımak.

**Architecture:** Klasör + sözleşme, tek süreç, ağ yok. Kule kendi `.venv`'ini taşır (Paddle dâhil), girdiyi CLI'dan alır, çıktıyı yalnız kendi `out/`'una atomik yazar. Taşıma iki bağımsız kapıdan geçer: önce venv paritesi (dosyalar yerinde, yorumlayıcı yeni), sonra taşıma paritesi (yorumlayıcı yeni, dosyalar yeni). Tek seferde tek değişken.

**Tech Stack:** Python 3.12.13 (pyenv), paddlepaddle-gpu 3.3.1, paddleocr 3.7.0, numpy 2.3.5, pytest, ffmpeg/ffprobe.

**Spec:** `docs/superpowers/specs/2026-08-12-allstar-kobe-kulesi-design.md` — çelişki halinde spec kazanır.

## Global Constraints

- **Ölçüm sapması sıfır.** Referans (`veri/olcum_son.json`, 2026-08-12 12:43): kapsam **110**, doğru **104**, genel **%94.5**, üretim **107/110 = %97.3**, kredi-var **75/81**, kredi-yok **29/29**, eksik **5**, hata sayısı **6**. Herhangi bir sapmada **DUR ve rapor et** — kendi başına düzeltmeye çalışma.
- **ORTAM SABİT: `ollama.service` bu iş boyunca DURDURULMUŞ kalır.** Şu an
  `inactive` (2026-08-12 12:21:44'te durdu). Kobe'nin dil yönlendiricisi
  Ollama'ya HTTP ile bağlanır (`src/motor.py` ~satır 699); erişilemezse
  `except Exception: continue` ile hiç oy toplanmaz ve **her film için `'en'`
  döner**. Yani yukarıdaki %94.5 **yönlendirici devre dışıyken** ölçülmüş bir
  sayıdır — Kobe'nin mutlak skoru değil, bu ortamdaki skoru. Üç ölçüm kapısı
  (ÖNCE / VENV / SONRA) ancak aynı ortamda anlamlıdır.
  **`systemctl start ollama` ÇALIŞTIRMA.** Ollama iş ortasında açılırsa skor
  ~%93.6'ya iner (GUNLUK 2026-08-11: Farsça film 'ar'a geçiyor, onset 28 kare
  erkene kayıyor) ve kapı sahte alarm verir. Ollama'nın durumu değişmişse
  **DUR ve rapor et.**
- Kapı komutlarından önce `systemctl is-active ollama` → `inactive` doğrulanır.
- **Üretim durmuş durumda.** Hiçbir toplu koşu başlatma.
- **Dış konsey bu iş için kapalı.**
- Kule içinde `figo` adı geçmez. Tek isim: **Kobe**.
- Kobe'nin kendi yaratmadığı hiçbir dizin silinmez.
- `ARIZA` asla `KREDI_YOK`'a dönüşmez.
- Temel yorumlayıcı: `/home/cagatay/.pyenv/versions/3.12.13/bin/python3.12` (venvs/ocr ile aynı — pinler cp312 tekerleği).
- Her görev sonunda commit. Commit mesajları Türkçe, ASCII gövdeli.
- **`git add -A`, `git add .`, `git reset --hard`, `git stash` YASAK.** Çalışma
  ağacında bu işe ait olmayan 9 değişik + 68 silinmiş dosya var (`mutfak/`,
  `OCR-worktree/`, `core/pipelines/ocr/jenerik_*`, `scripts/giris_*`,
  `scripts/toplu_kosu.sh`, iki `tests/test_master*`). Geniş komutlar bunları
  ya commit'ine karıştırır ya da siler. **Yalnız adı geçen yolları sahnele**,
  ve her commit'ten önce `git status --porcelain --cached` ile ne
  sahnelendiğine bak.

---

## Dosya yapısı

**Yeni:**

| Yol | Sorumluluk |
|---|---|
| `Allstar/MAP.md` | kod adı ↔ gerçek görev sözlüğü |
| `Allstar/kobe/kobe` | sarmalayıcı betik — kendi venv'ini bulur |
| `Allstar/kobe/main.py` | CLI + koşu akışı (kare çıkarımı, scratch yaşam döngüsü) |
| `Allstar/kobe/sozlesme.py` | `Girdi` / `Cikti` / `ariza()` — kulenin dış yüzü |
| `Allstar/kobe/config.yaml` | eşikler ve bayraklar |
| `Allstar/kobe/gereksinimler.txt` | tam sürüm pinleri |
| `Allstar/kobe/.venv/` | Kobe'nin kendi Paddle'ı (git'te değil) |

**Taşınan (`git mv` — eski yerde kalmaz):**

| Kaynak | Hedef |
|---|---|
| `harness/kunye_kiyas/kobe.py` | `Allstar/kobe/src/motor.py` |
| `harness/kunye_kiyas/olc_pool.py` | `Allstar/kobe/olcum/olc_pool.py` |
| `harness/kunye_kiyas/hata_atlasi.py` | `Allstar/kobe/olcum/hata_atlasi.py` |
| `harness/kunye_kiyas/v5_izleme.py` | `Allstar/kobe/olcum/v5_izleme.py` |
| `harness/kunye_kiyas/veri/` (tüm içerik) | `Allstar/kobe/olcum/veri/` |
| `tests/test_kobe_router_ve_gorunurluk.py` | `Allstar/kobe/tests/test_motor_yonlendirici.py` |
| `docs/FIGO.md` | `Allstar/kobe/README.md` |

**Kopyalanan (`cp` — aslı yerinde kalır, gerekçe spec §4.2):**

| Kaynak | Hedef |
|---|---|
| `harness/kunye_kiyas/credit_box.py` | `Allstar/kobe/src/kutu.py` |
| `harness/kunye_kiyas/credit_content.py` | `Allstar/kobe/src/icerik.py` |

**Silinen:** `harness/kunye_kiyas/figo.py`, `Players/` (160 boş dosya, git'te izlenmiyor).

**Değişen (kule dışı):** `scripts/_jenerik_pool.py` (satır 281-282, 390).

---

## Görev 1: Ölçüm ÖNCE + geri-dönüş noktası

Hiçbir şey değiştirilmez. Amaç: taşımadan önceki gerçeği dosyaya yazmak.

**Dosyalar:**
- Oluştur: `Allstar/kobe/raporlar/olcum_ONCE.json`
- Oluştur: `Allstar/kobe/raporlar/geri_donus.txt`

- [ ] **Adım 1: Çakışma denetimi — taşınacak yollar temiz mi**

> **Ağaç kirli, bu beklenen.** Bu plan yazılırken çalışma ağacında zaten
> 9 değişik dosya (`OCR-worktree/`, `core/pipelines/ocr/jenerik_*`,
> `scripts/giris_*`, `scripts/toplu_kosu.sh`, iki `tests/test_master*`) ve
> `mutfak/` altında 68 silinmiş dosya vardı. Bunlar **bu işe ait değil**,
> bu iş başlamadan önce oradaydılar. Onlara **dokunma**, commit etme,
> geri alma. Taşımayı ilgilendiren tek soru: taşınacak yollarda yabancı
> değişiklik var mı?

```bash
cd /opt/mitas && for p in harness/kunye_kiyas tests/test_kobe_router_ve_gorunurluk.py \
    scripts/_jenerik_pool.py docs/FIGO.md Allstar Players; do
  n=$(git status --porcelain -- "$p" 2>/dev/null | grep -v "^??" | wc -l)
  echo "  $p : $n"
done
```

Beklenen: **her satır `0`**. Herhangi biri `0` değilse DUR ve rapor et — o
dosyada bilinmeyen bir değişiklik var, üstüne taşıma yapılmaz.

> **Geri dönüş bu yüzden SHA değil, yol-kapsamlı:** ağaç kirli olduğu için
> `git reset --hard` yasaktır — yabancı WIP'i siler. Geri dönmek gerekirse
> yalnız Kobe'nin yollarını geri al:
> `git checkout <SHA> -- harness/kunye_kiyas tests/test_kobe_router_ve_gorunurluk.py scripts/_jenerik_pool.py docs/FIGO.md`
> ve `rm -rf Allstar`.

- [ ] **Adım 2: Rapor dizinini aç**

```bash
mkdir -p /opt/mitas/Allstar/kobe/raporlar
```

- [ ] **Adım 3: Ölçümü koş (~140 sn)**

Önce ortamı doğrula — bu kapı sadece Ollama kapalıyken anlamlıdır:

```bash
systemctl is-active ollama
```

Beklenen: `inactive`. `active` çıkarsa **DUR ve rapor et** (referans %94.5
Ollama kapalıyken ölçüldü; açıkken ~%93.6 olur, kapı sahte alarm verir).

```bash
cd /opt/mitas/harness/kunye_kiyas && \
/opt/mitas/venvs/ocr/bin/python olc_pool.py --paralel 8 2>/dev/null | tail -12
```

Beklenen çıktı satırı:
```
KAPSAM 110 (eksik 5)  GENEL 104/110 = %94.5   ÜRETİM 107/110 = %97.3 (erken≤120 OK / geç≤20)
  kredi-var: 75/81   kredi-yok: 29/29  (kırmızı çizgi ≥29/30)
```

Bu sayılardan **herhangi biri** farklıysa DUR ve rapor et — taşımaya başlama.

- [ ] **Adım 4: Sonucu referans olarak sabitle**

```bash
cp /opt/mitas/harness/kunye_kiyas/veri/olcum_son.json \
   /opt/mitas/Allstar/kobe/raporlar/olcum_ONCE.json
```

- [ ] **Adım 5: Geri-dönüş noktasını yaz**

```bash
cd /opt/mitas && \
{ printf 'Kobe kulesi tasima oncesi geri-donus noktasi\ntarih: %s\nSHA: %s\ndal: %s\n\n' \
    "$(date '+%F %T')" "$(git rev-parse HEAD)" "$(git rev-parse --abbrev-ref HEAD)"
  printf 'GERI DONUS (agac kirli - reset --hard YASAK, yabanci WIP siler):\n'
  printf '  git checkout %s -- harness/kunye_kiyas tests/test_kobe_router_ve_gorunurluk.py \\\n' "$(git rev-parse HEAD)"
  printf '      scripts/_jenerik_pool.py docs/FIGO.md\n  rm -rf Allstar\n\n'
  printf 'TASIMA DISI (dokunma) - bu is baslamadan once kirliydi:\n'
  git status --porcelain | grep -v "^??" | sed 's/^/  /'
} > Allstar/kobe/raporlar/geri_donus.txt && head -12 Allstar/kobe/raporlar/geri_donus.txt
```

- [ ] **Adım 6: Commit**

```bash
cd /opt/mitas && git add Allstar/kobe/raporlar && \
git commit -m "olcum(kobe): tasima oncesi referans - kapsam 110, genel %94.5, uretim %97.3

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Görev 2: Allstar iskeleti + Kobe'nin kendi venv'i

**Interfaces:**
- Üretir: `Allstar/kobe/.venv/bin/python` — bundan sonraki tüm Kobe komutları bunu kullanır.

**Dosyalar:**
- Oluştur: `Allstar/.gitignore`, `Allstar/kobe/gereksinimler.txt`
- Oluştur: `Allstar/kobe/{src,olcum,tests,golden,raporlar,logs,scratch,out}/`

- [ ] **Adım 1: Dizin ağacını aç**

```bash
mkdir -p /opt/mitas/Allstar/kobe/{src,olcum,tests,golden,raporlar,logs,scratch,out}
```

- [ ] **Adım 2: `Allstar/.gitignore` yaz**

```gitignore
# Kule çalışma zamanları ve üretilen veri — git'te tutulmaz
*/*/.venv/
*/*/logs/
*/*/scratch/
*/*/out/
__pycache__/
*.pyc
```

- [ ] **Adım 3: `Allstar/kobe/gereksinimler.txt` yaz**

Pinler `venvs/ocr`'dan alınmıştır — taşıma AYNI sürümlerle ölçülmelidir.

```
paddlepaddle-gpu==3.3.1
paddleocr==3.7.0
paddlex==3.7.2
numpy==2.3.5
pillow==12.1.0
opencv-contrib-python==5.0.0.93
shapely==2.1.2
pyclipper==1.4.0
scikit-image==0.26.0
scipy==1.18.0
pandas==3.0.3
einops==0.8.2
ftfy==6.3.1
PyYAML==6.0.2
requests==2.34.2
tqdm==4.68.4
pytest
```

- [ ] **Adım 4: venv'i oluştur**

```bash
/home/cagatay/.pyenv/versions/3.12.13/bin/python3.12 -m venv /opt/mitas/Allstar/kobe/.venv && \
/opt/mitas/Allstar/kobe/.venv/bin/python -V
```

Beklenen: `Python 3.12.13`

- [ ] **Adım 5: Bağımlılıkları kur (pip önbelleği 35 GB — çoğu yerelden gelir)**

```bash
/opt/mitas/Allstar/kobe/.venv/bin/pip install --upgrade pip -q && \
/opt/mitas/Allstar/kobe/.venv/bin/pip install -r /opt/mitas/Allstar/kobe/gereksinimler.txt 2>&1 | tail -5
```

Kurulum başarısız olursa (özellikle `paddlepaddle-gpu` tekerleği bulunamazsa) DUR ve tam hata çıktısıyla rapor et.

- [ ] **Adım 6: Kurulumu doğrula**

```bash
/opt/mitas/Allstar/kobe/.venv/bin/python -c "
import paddle, paddleocr, numpy, PIL
print('paddle', paddle.__version__, 'cuda', paddle.is_compiled_with_cuda())
print('paddleocr', paddleocr.__version__)
print('numpy', numpy.__version__)
" 2>&1 | grep -v Warning
```

Beklenen:
```
paddle 3.3.1 cuda True
paddleocr 3.7.0
numpy 2.3.5
```

Üç satırdan biri tutmuyorsa DUR.

- [ ] **Adım 7: Commit**

```bash
cd /opt/mitas && git add Allstar/.gitignore Allstar/kobe/gereksinimler.txt && \
git commit -m "feat(kobe): kulenin kendi calisma zamani - .venv + surum pinleri

paddlepaddle-gpu 3.3.1 / paddleocr 3.7.0, venvs/ocr ile birebir ayni pinler.
Gerekce: surum dondurma (spec karar 11) - paralellik degil.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Görev 3: Venv paritesi kapısı

**Dosyalar taşınmaz.** Yalnız yorumlayıcı değişir. Amaç: skor kayarsa sebebin venv olduğunu burada yakalamak — taşımaya karıştırmadan.

**Dosyalar:**
- Oluştur: `Allstar/kobe/raporlar/olcum_VENV.json`

- [ ] **Adım 1: Aynı ölçümü Kobe'nin venv'iyle koş**

```bash
cd /opt/mitas/harness/kunye_kiyas && \
/opt/mitas/Allstar/kobe/.venv/bin/python olc_pool.py --paralel 8 2>/dev/null | tail -12
```

- [ ] **Adım 2: Sapma kapısı**

Çıktı Görev 1 Adım 3 ile **birebir aynı** olmalı:
```
KAPSAM 110 (eksik 5)  GENEL 104/110 = %94.5   ÜRETİM 107/110 = %97.3 (erken≤120 OK / geç≤20)
  kredi-var: 75/81   kredi-yok: 29/29  (kırmızı çizgi ≥29/30)
```

Sapma varsa **DUR**. Sebep venv'dedir; taşıma yapma, farkı rapor et.

- [ ] **Adım 3: Sonucu sabitle**

```bash
cp /opt/mitas/harness/kunye_kiyas/veri/olcum_son.json \
   /opt/mitas/Allstar/kobe/raporlar/olcum_VENV.json && \
/opt/mitas/Allstar/kobe/.venv/bin/python -c "
import json
a=json.load(open('/opt/mitas/Allstar/kobe/raporlar/olcum_ONCE.json'))
b=json.load(open('/opt/mitas/Allstar/kobe/raporlar/olcum_VENV.json'))
alan=('kapsam','dogru','genel','eksik')
fark=[k for k in alan if a[k]!=b[k]] + \
     (['uretim'] if a['uretim']['pct']!=b['uretim']['pct'] else []) + \
     (['kredi_yok'] if a['kredi_yok']!=b['kredi_yok'] else []) + \
     (['kredi_var'] if a['kredi_var']!=b['kredi_var'] else [])
print('SAPMA YOK' if not fark else 'SAPMA: '+', '.join(fark))
"
```

Beklenen: `SAPMA YOK`. Başka her şeyde DUR.

- [ ] **Adım 4: Commit**

```bash
cd /opt/mitas && git add Allstar/kobe/raporlar/olcum_VENV.json && \
git commit -m "olcum(kobe): venv paritesi - kendi venv'i eski venv ile ayni sonucu veriyor

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Görev 4: Dosya taşıma + import yolları

**Interfaces:**
- Üretir: `Allstar/kobe/src/motor.py` — `tespit_v5(dizin, fps=25.0, stride=2, ocr_stride=2) -> Sonuc`, `kareler(dizin) -> list[str]`, `_kare_no(yol) -> int`, `class Sonuc`. Sonraki görevler bu adlara dayanır.
- Üretir: `Allstar/kobe/src/kutu.py` (eski `credit_box`), `Allstar/kobe/src/icerik.py` (eski `credit_content`).

- [ ] **Adım 1: Taşı (`git mv`)**

```bash
cd /opt/mitas && \
git mv harness/kunye_kiyas/kobe.py        Allstar/kobe/src/motor.py && \
git mv harness/kunye_kiyas/olc_pool.py    Allstar/kobe/olcum/olc_pool.py && \
git mv harness/kunye_kiyas/hata_atlasi.py Allstar/kobe/olcum/hata_atlasi.py && \
git mv harness/kunye_kiyas/v5_izleme.py   Allstar/kobe/olcum/v5_izleme.py && \
git mv harness/kunye_kiyas/veri           Allstar/kobe/olcum/veri && \
git rm -q harness/kunye_kiyas/figo.py && \
git status --short | head -20
```

- [ ] **Adım 2: Kopyala (aslı yerinde kalır)**

```bash
cd /opt/mitas && \
cp harness/kunye_kiyas/credit_box.py     Allstar/kobe/src/kutu.py && \
cp harness/kunye_kiyas/credit_content.py Allstar/kobe/src/icerik.py && \
ls -la Allstar/kobe/src/
```

Beklenen: `icerik.py`, `kutu.py`, `motor.py` — üçü de mevcut. `harness/kunye_kiyas/credit_box.py` ve `credit_content.py` de hâlâ yerinde olmalı.

- [ ] **Adım 3: `src/motor.py` içindeki tembel importları düzelt**

`motor.py` içinde üç satır değişir (satır numaraları taşımadan sonra kayabilir — metinle eşleştir):

```python
# satır ~249 içinde:
    import credit_content as cc
# →
    import icerik as cc
```

```python
# tespit_v5 gövdesinin başında (~satır 730-731):
    import credit_box as cb
    import credit_content as cc
# →
    import kutu as cb
    import icerik as cc
```

Doğrula:

```bash
grep -n "import credit_\|import figo" /opt/mitas/Allstar/kobe/src/motor.py
```

Beklenen: **çıktı yok**.

- [ ] **Adım 4: `src/icerik.py` başlığındaki modül adını güncelle**

`icerik.py` içindeki `_KOK` bootstrap'ı korunur (spec karar 12: `core.lexicon.rol_tablosu` zemindir, taşınmaz). Yalnız docstring'in ilk satırındaki `credit_content` adı `icerik` yapılır. Kod değişmez.

- [ ] **Adım 5: `olcum/olc_pool.py` yollarını düzelt**

`olc_pool.py` satır 15-19 blokunu şununla değiştir:

```python
BURASI = os.path.dirname(os.path.abspath(__file__))            # Allstar/kobe/olcum
SRC = os.path.join(os.path.dirname(BURASI), "src")             # Allstar/kobe/src
sys.path.insert(0, SRC)
import motor as co

V = os.path.join(BURASI, "veri")
```

ve satır ~32'deki işçi importunu:

```python
    import motor as co_w
```

Doğrula:

```bash
grep -n "figo\|BURASI\|SRC\|^V = " /opt/mitas/Allstar/kobe/olcum/olc_pool.py | head
```

Beklenen: `figo` yok; `SRC` tanımlı; `V` `BURASI/veri`.

- [ ] **Adım 6: `olcum/hata_atlasi.py` yollarını düzelt**

Satır ~29-34 blokunu:

```python
BURASI = os.path.dirname(os.path.abspath(__file__))            # Allstar/kobe/olcum
SRC = os.path.join(os.path.dirname(BURASI), "src")
sys.path.insert(0, SRC)
import icerik as cc      # noqa: E402  (salt-okunur kullanım)
import motor as co       # noqa: E402  (salt-okunur kullanım)

V = os.path.join(BURASI, "veri")
```

- [ ] **Adım 7: `olcum/veri/det_isit.py` yollarını düzelt**

Satır ~12-13'ü:

```python
SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src")                       # Allstar/kobe/src
sys.path.insert(0, SRC)
```

ve `isit()` içindeki üç satırı:

```python
def isit(dizin: str) -> str:
    sys.path.insert(0, SRC)
    import kutu as cb
    import motor as co
```

- [ ] **Adım 8: `scripts/_jenerik_pool.py` çağıranını çevir**

Satır 281-282:

```python
    sys.path.insert(0, str(PROJECT_ROOT / "Allstar" / "kobe" / "src"))
    import motor as _co
```

Satır ~390:

```python
    sys.path.insert(0, str(PROJECT_ROOT / "Allstar" / "kobe" / "src"))
```

Satır 246'daki yorumda geçen `harness/kunye_kiyas/figo.tespit_v5` ifadesi `Allstar/kobe/src/motor.tespit_v5` yapılır.

- [ ] **Adım 9: `figo` adının kalmadığını doğrula**

```bash
cd /opt/mitas && grep -rn "figo" --include="*.py" . 2>/dev/null | grep -v __pycache__
```

Beklenen: **çıktı yok**. Çıktı varsa her satırı düzelt.

- [ ] **Adım 10: İçe aktarma dumanı**

```bash
cd /opt/mitas/Allstar/kobe/src && \
/opt/mitas/Allstar/kobe/.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
import motor
print('motor OK — tespit_v5:', callable(motor.tespit_v5), '| kareler:', callable(motor.kareler))
import kutu, icerik
print('kutu OK, icerik OK')
" 2>&1 | grep -v Warning
```

Beklenen üç satır: `motor OK — tespit_v5: True | kareler: True`, `kutu OK, icerik OK`.

- [ ] **Adım 11: Commit**

```bash
cd /opt/mitas && \
git add Allstar harness/kunye_kiyas scripts/_jenerik_pool.py && \
git status --porcelain --cached | head -20 && \
git commit -m "refactor(kobe): motor Allstar/kobe kulesine tasindi, figo adi silindi

- kobe.py -> src/motor.py, olc_pool/hata_atlasi/v5_izleme/veri -> olcum/
- credit_box/credit_content -> src/kutu.py, src/icerik.py (KOPYA; asli
  uretim okuyucusu _pipe_hibrit_okuma.py icin yerinde kaldi, spec 4.2)
- scripts/_jenerik_pool.py yeni yola cevrildi
- figo.py silindi; repoda tek isim Kobe

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Görev 5: Testlerin taşınması

**Dosyalar:**
- Taşı: `tests/test_kobe_router_ve_gorunurluk.py` → `Allstar/kobe/tests/test_motor_yonlendirici.py`

- [ ] **Adım 1: Taşımadan önce mevcut halini koştur (referans)**

```bash
cd /opt/mitas && /opt/mitas/Allstar/kobe/.venv/bin/python -m pytest \
  tests/test_kobe_router_ve_gorunurluk.py -q 2>&1 | tail -3
```

Beklenen: `19 passed`. Farklıysa sayıyı not et — taşımadan sonra **aynı** sayı beklenecek.

- [ ] **Adım 2: Taşı**

```bash
cd /opt/mitas && git mv tests/test_kobe_router_ve_gorunurluk.py \
  Allstar/kobe/tests/test_motor_yonlendirici.py
```

- [ ] **Adım 3: Test dosyasındaki yolları ve modül adlarını düzelt**

Satır 26-27:

```python
SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
```

`kobe` fixture'ı (satır ~105-115):

```python
@pytest.fixture
def kobe(monkeypatch):
    """motor modülünü sahte icerik/kutu ile taze yükler."""
    for ad in ("motor", "icerik", "kutu"):
        sys.modules.pop(ad, None)
    cc, cb = _SahteCC(), _SahteCB()
    monkeypatch.setitem(sys.modules, "icerik", cc)
    monkeypatch.setitem(sys.modules, "kutu", cb)
    import motor as _k
    _k._sahte_cc, _k._sahte_cb = cc, cb
    return _k
```

Sahte sınıfların `super().__init__()` çağrılarındaki modül adları da güncellenir:
`_SahteCC` → `super().__init__("icerik")`, `_SahteCB` → `super().__init__("kutu")`.
Docstring'lerdeki `credit_content` / `credit_box` adları `icerik` / `kutu` yapılır.

- [ ] **Adım 4: Testleri koştur**

```bash
cd /opt/mitas && /opt/mitas/Allstar/kobe/.venv/bin/python -m pytest \
  Allstar/kobe/tests -q 2>&1 | tail -3
```

Beklenen: **Adım 1 ile aynı sayı** (`19 passed`). Az bir tane bile eksikse DUR.

- [ ] **Adım 5: Commit**

```bash
cd /opt/mitas && git add Allstar/kobe/tests && \
git status --porcelain --cached | head -10 && \
git commit -m "test(kobe): yonlendirici testleri kule icine tasindi (19/19)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Görev 6: Ölçüm SONRA — taşıma kapısı

Bu, taşımanın kabul kapısıdır. Yeni yol + yeni venv.

**Dosyalar:**
- Oluştur: `Allstar/kobe/raporlar/olcum_SONRA.json`

- [ ] **Adım 1: Ölçümü yeni yerinden koş**

```bash
cd /opt/mitas/Allstar/kobe/olcum && \
/opt/mitas/Allstar/kobe/.venv/bin/python olc_pool.py --paralel 8 2>/dev/null | tail -12
```

- [ ] **Adım 2: Sapma kapısı**

```
KAPSAM 110 (eksik 5)  GENEL 104/110 = %94.5   ÜRETİM 107/110 = %97.3 (erken≤120 OK / geç≤20)
  kredi-var: 75/81   kredi-yok: 29/29  (kırmızı çizgi ≥29/30)
```

Sapma varsa **DUR ve rapor et**. Geri dönüş: `raporlar/geri_donus.txt` içindeki SHA.

- [ ] **Adım 3: Sonucu sabitle ve üç ölçümü karşılaştır**

```bash
cp /opt/mitas/Allstar/kobe/olcum/veri/olcum_son.json \
   /opt/mitas/Allstar/kobe/raporlar/olcum_SONRA.json && \
/opt/mitas/Allstar/kobe/.venv/bin/python -c "
import json
R='/opt/mitas/Allstar/kobe/raporlar/'
o,v,s=[json.load(open(R+f'olcum_{k}.json')) for k in ('ONCE','VENV','SONRA')]
for ad,d in (('ONCE',o),('VENV',v),('SONRA',s)):
    print(f\"{ad:6} kapsam={d['kapsam']} genel=%{d['genel']} uretim=%{d['uretim']['pct']}\"
          f\" kredi_var={d['kredi_var']['dogru']}/{d['kredi_var']['n']}\"
          f\" kredi_yok={d['kredi_yok']['dogru']}/{d['kredi_yok']['n']}\")
esit = (o['kapsam'],o['genel'],o['uretim']['pct'],o['kredi_var'],o['kredi_yok']) == \\
       (s['kapsam'],s['genel'],s['uretim']['pct'],s['kredi_var'],s['kredi_yok'])
print('KAPI:', 'GECTI - sapma sifir' if esit else 'KALDI - DUR VE RAPOR ET')
"
```

Beklenen son satır: `KAPI: GECTI - sapma sifir`

- [ ] **Adım 4: Commit**

```bash
cd /opt/mitas && git add Allstar/kobe/raporlar/olcum_SONRA.json && \
git commit -m "olcum(kobe): tasima kapisi GECTI - yeni yol + yeni venv, sapma sifir

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Görev 7: Sözleşme (`sozlesme.py`)

Kulenin dış yüzü. Motor değişmez — bu katman motorun `Sonuc`'unu kule sözleşmesine çevirir.

**Dosyalar:**
- Oluştur: `Allstar/kobe/sozlesme.py`
- Test: `Allstar/kobe/tests/test_sozlesme.py`

**Interfaces:**
- Üretir: `Girdi(film_id, video=None, kareler=None, config={})`, `GirdiHatasi`, `Cikti(...)`, `Cikti.sozluk() -> dict`, `Cikti.yaz(kok: Path) -> Path`, `ariza(film_id, sinif, mesaj, kanit=None) -> Cikti`. Görev 8 bunların hepsini kullanır.

- [ ] **Adım 1: Başarısız testi yaz**

`Allstar/kobe/tests/test_sozlesme.py`:

```python
"""Kobe sözleşmesi — kulenin dış yüzü. Motor koşmaz, Paddle gerekmez."""
import json
import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))

from sozlesme import Cikti, Girdi, GirdiHatasi, ariza  # noqa: E402


# ── Girdi: video/kareler XOR ────────────────────────────────────────────
def test_girdi_video_tek_basina_gecerli():
    g = Girdi(film_id="F1", video="/yol/f.mp4")
    assert g.video == "/yol/f.mp4" and g.kareler is None


def test_girdi_kareler_tek_basina_gecerli():
    g = Girdi(film_id="F1", kareler="/yol/kareler")
    assert g.kareler == "/yol/kareler" and g.video is None


def test_girdi_ikisi_birden_hata():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="F1", video="/yol/f.mp4", kareler="/yol/kareler")


def test_girdi_hicbiri_hata():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="F1")


def test_girdi_bos_film_id_hata():
    with pytest.raises(GirdiHatasi):
        Girdi(film_id="", video="/yol/f.mp4")


# ── Cikti: durum değişmezi ──────────────────────────────────────────────
def test_ariza_sinif_ve_mesaj_zorunlu():
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="ARIZA")


def test_ariza_yardimcisi_alanlari_doldurur():
    c = ariza("F1", "FFMPEG", "kare cikarilamadi", {"kod": 1})
    assert c.durum == "ARIZA" and c.sinif == "FFMPEG"
    assert c.mesaj == "kare cikarilamadi" and c.kanit == {"kod": 1}


def test_kredi_yok_sinif_tasiyamaz():
    """ARIZA asla KREDI_YOK'a dönüşmez — ters yön de kapalı."""
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="KREDI_YOK", sinif="FFMPEG")


def test_bilinmeyen_durum_reddedilir():
    with pytest.raises(ValueError):
        Cikti(film_id="F1", durum="BELKI")


# ── Yazma: atomik + _TAMAM ──────────────────────────────────────────────
def test_yaz_kobe_json_ve_tamam_uretir(tmp_path):
    c = Cikti(film_id="F1", durum="BULUNDU", baslangic_kare=940,
              baslangic_sn=470.0, guven=0.87, script="ar")
    yol = c.yaz(tmp_path)
    assert yol == tmp_path / "F1" / "kobe.json"
    assert (tmp_path / "F1" / "_TAMAM").exists()
    d = json.loads(yol.read_text(encoding="utf-8"))
    assert d["durum"] == "BULUNDU" and d["baslangic_kare"] == 940


def test_yaz_gecici_dosya_birakmaz(tmp_path):
    Cikti(film_id="F1", durum="KREDI_YOK").yaz(tmp_path)
    assert list((tmp_path / "F1").glob("*.tmp")) == []


def test_tamam_kobe_jsondan_SONRA_yazilir(tmp_path):
    """Tüketici kuralı: _TAMAM varsa kobe.json kesin tamdır."""
    c = Cikti(film_id="F1", durum="BULUNDU", baslangic_kare=1)
    c.yaz(tmp_path)
    d = tmp_path / "F1"
    assert (d / "_TAMAM").stat().st_mtime >= (d / "kobe.json").stat().st_mtime
```

- [ ] **Adım 2: Testin başarısız olduğunu gör**

```bash
cd /opt/mitas && /opt/mitas/Allstar/kobe/.venv/bin/python -m pytest \
  Allstar/kobe/tests/test_sozlesme.py -q 2>&1 | tail -3
```

Beklenen: `ModuleNotFoundError: No module named 'sozlesme'`

- [ ] **Adım 3: `sozlesme.py`'yi yaz**

```python
"""Kobe kulesinin sözleşmesi — Girdi / Cikti / ariza.

Kulenin DIŞ yüzü burada tanımlıdır. Motor (src/motor.py) bu dosyayı bilmez;
çeviri main.py'de yapılır. Böylece motorun iç tipleri (Sonuc) dışarı sızmaz.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DURUMLAR = ("BULUNDU", "KREDI_YOK", "ARIZA")


class GirdiHatasi(ValueError):
    """Girdi sözleşmesi ihlali — çağıranın hatası, kulenin değil."""


@dataclass(frozen=True)
class Girdi:
    """film_id + (video XOR kareler). Standart yol: video."""
    film_id: str
    video: str | None = None
    kareler: str | None = None
    config: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.film_id:
            raise GirdiHatasi("film_id bos olamaz")
        if bool(self.video) == bool(self.kareler):
            raise GirdiHatasi(
                "video ve kareler'den TAM OLARAK biri verilmeli — "
                f"video={self.video!r} kareler={self.kareler!r}. "
                "Kule sessizce bir tarafi secmez.")


@dataclass
class Cikti:
    """out/<film_id>/kobe.json'un birebir karsiligi."""
    film_id: str
    durum: str
    baslangic_kare: int | None = None
    baslangic_sn: float | None = None
    guven: float | None = None
    script: str | None = None
    kanit: dict = field(default_factory=dict)
    motor_surumu: str = ""
    uretim_zamani: str = ""
    sure_sn: float = 0.0
    # yalniz ARIZA
    sinif: str | None = None
    mesaj: str | None = None

    def __post_init__(self) -> None:
        if self.durum not in DURUMLAR:
            raise ValueError(f"durum {self.durum!r} gecersiz — {DURUMLAR}")
        # DEGISMEZ: ARIZA kanitsiz olamaz, KREDI_YOK ariza alani tasiyamaz.
        # Bu iki kural birlikte "ariza sessizce icerik gercegine donusmesin"
        # kapisidir (spec 4.3).
        if self.durum == "ARIZA" and not (self.sinif and self.mesaj):
            raise ValueError("ARIZA icin sinif ve mesaj zorunlu")
        if self.durum != "ARIZA" and (self.sinif or self.mesaj):
            raise ValueError(f"{self.durum} sinif/mesaj tasiyamaz")
        if not self.uretim_zamani:
            self.uretim_zamani = datetime.now(timezone.utc).astimezone().isoformat(
                timespec="seconds")

    def sozluk(self) -> dict:
        d = {"film_id": self.film_id, "durum": self.durum}
        if self.durum == "BULUNDU":
            d |= {"baslangic_kare": self.baslangic_kare,
                  "baslangic_sn": self.baslangic_sn,
                  "guven": self.guven, "script": self.script}
        if self.durum == "ARIZA":
            d |= {"sinif": self.sinif, "mesaj": self.mesaj}
        d |= {"kanit": self.kanit, "motor_surumu": self.motor_surumu,
              "uretim_zamani": self.uretim_zamani, "sure_sn": self.sure_sn}
        return d

    def yaz(self, kok: str | Path) -> Path:
        """out/<film_id>/kobe.json — atomik yaz, sonra _TAMAM.

        Kuyruk klasorun kendisi oldugu icin tuketici biz yazarken okuyabilir.
        os.replace yarim dosya okunmasini, _TAMAM ise "yaziliyor mu bitti mi"
        belirsizligini kapatir. Tuketici kurali: _TAMAM yoksa dosya yok sayilir.
        """
        d = Path(kok) / self.film_id
        d.mkdir(parents=True, exist_ok=True)
        hedef, gecici = d / "kobe.json", d / "kobe.json.tmp"
        gecici.write_text(json.dumps(self.sozluk(), ensure_ascii=False, indent=1),
                          encoding="utf-8")
        os.replace(gecici, hedef)
        (d / "_TAMAM").write_text("", encoding="utf-8")
        return hedef


def ariza(film_id: str, sinif: str, mesaj: str, kanit: dict | None = None) -> Cikti:
    """Tek ariza uretim noktasi — sinif/mesaj atlanamasin diye."""
    return Cikti(film_id=film_id, durum="ARIZA", sinif=sinif, mesaj=mesaj,
                 kanit=kanit or {})
```

- [ ] **Adım 4: Testlerin geçtiğini gör**

```bash
cd /opt/mitas && /opt/mitas/Allstar/kobe/.venv/bin/python -m pytest \
  Allstar/kobe/tests/test_sozlesme.py -q 2>&1 | tail -3
```

Beklenen: `12 passed`

- [ ] **Adım 5: Commit**

```bash
cd /opt/mitas && git add Allstar/kobe/sozlesme.py Allstar/kobe/tests/test_sozlesme.py && \
git commit -m "feat(kobe): kule sozlesmesi - Girdi/Cikti/ariza, atomik yazim + _TAMAM

Degismez: ARIZA kanitsiz olamaz, KREDI_YOK ariza alani tasiyamaz. Iki kural
birlikte arizanin sessizce icerik gercegine donusmesini engeller.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Görev 8: CLI ve koşu akışı

**Dosyalar:**
- Oluştur: `Allstar/kobe/main.py`, `Allstar/kobe/kobe`, `Allstar/kobe/config.yaml`
- Test: `Allstar/kobe/tests/test_main_akis.py`

**Interfaces:**
- Tüketir: `sozlesme.Girdi/Cikti/ariza/GirdiHatasi` (Görev 7), `src/motor.tespit_v5` (Görev 4).
- Üretir: `film_id_uret(yol, kareler_modu) -> str`, `kare_cikar(video, hedef) -> tuple[Path, int]`, `tek(girdi, kok) -> Cikti`, `toplu(girdi_dizini, kareler_modu, kok) -> list[Cikti]`.

- [ ] **Adım 1: Başarısız testi yaz**

`Allstar/kobe/tests/test_main_akis.py`:

```python
"""Kobe koşu akışı — ffmpeg ve Paddle sahte, gerçek çağrılmaz."""
import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))

import main  # noqa: E402
from sozlesme import Girdi  # noqa: E402


# ── film_id türetme: tek kural, tahmin yok ──────────────────────────────
def test_film_id_video_uzantisiz_ad():
    assert main.film_id_uret(Path("/y/2025-1307-1-0000-50-0.mp4"), False) \
        == "2025-1307-1-0000-50-0"


def test_film_id_kareler_dizin_adi():
    assert main.film_id_uret(Path("/y/BEYAZ_BALINA/"), True) == "BEYAZ_BALINA"


# ── scratch yaşam döngüsü: kule kendi yaratmadığını silmez ──────────────
def test_video_yolunda_scratch_silinir(tmp_path, monkeypatch):
    kok, scratch = tmp_path / "out", tmp_path / "scratch"
    monkeypatch.setattr(main, "SCRATCH", scratch)
    monkeypatch.setattr(main, "kare_cikar", _sahte_kare_cikar)
    monkeypatch.setattr(main, "_tespit", lambda d, c: _SahteSonuc(940))
    main.tek(Girdi(film_id="F1", video="/y/F1.mp4"), kok)
    assert not (scratch / "F1").exists()


def test_ariza_da_scratch_silinir(tmp_path, monkeypatch):
    kok, scratch = tmp_path / "out", tmp_path / "scratch"
    monkeypatch.setattr(main, "SCRATCH", scratch)
    monkeypatch.setattr(main, "kare_cikar", _sahte_kare_cikar)
    def _patla(d, c):
        raise RuntimeError("paddle coktu")
    monkeypatch.setattr(main, "_tespit", _patla)
    c = main.tek(Girdi(film_id="F1", video="/y/F1.mp4"), kok)
    assert c.durum == "ARIZA" and not (scratch / "F1").exists()


def test_disaridan_verilen_kare_dizini_SILINMEZ(tmp_path, monkeypatch):
    """Tek-yazar ilkesi: Kobe kendi yaratmadığını silmez."""
    dis = tmp_path / "baskasinin_kareleri"
    dis.mkdir()
    (dis / "c_00001.png").write_bytes(b"x")
    monkeypatch.setattr(main, "_tespit", lambda d, c: _SahteSonuc(12))
    main.tek(Girdi(film_id="F1", kareler=str(dis)), tmp_path / "out")
    assert (dis / "c_00001.png").exists()


# ── arıza asla içerik gerçeğine dönüşmez ────────────────────────────────
def test_motor_cokerse_ARIZA_dondurur_KREDI_YOK_degil(tmp_path, monkeypatch):
    def _patla(d, c):
        raise RuntimeError("OOM")
    monkeypatch.setattr(main, "_tespit", _patla)
    c = main.tek(Girdi(film_id="F1", kareler=str(tmp_path)), tmp_path / "out")
    assert c.durum == "ARIZA" and c.sinif == "MOTOR"


def test_motor_minus_bir_derse_KREDI_YOK(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "_tespit", lambda d, c: _SahteSonuc(-1))
    c = main.tek(Girdi(film_id="F1", kareler=str(tmp_path)), tmp_path / "out")
    assert c.durum == "KREDI_YOK"


# ── toplu mod: _TAMAM olanı atlar ───────────────────────────────────────
def test_toplu_tamam_olani_atlar(tmp_path, monkeypatch):
    girdi, kok = tmp_path / "girdi", tmp_path / "out"
    girdi.mkdir()
    for ad in ("A", "B"):
        (girdi / ad).mkdir()
        (girdi / ad / "c_00001.png").write_bytes(b"x")
    (kok / "A").mkdir(parents=True)
    (kok / "A" / "_TAMAM").write_text("")
    islenen = []
    def _izle(d, c):
        islenen.append(Path(d).name)
        return _SahteSonuc(5)
    monkeypatch.setattr(main, "_tespit", _izle)
    main.toplu(girdi, True, kok)
    assert islenen == ["B"]


# ── yardımcılar ─────────────────────────────────────────────────────────
class _SahteSonuc:
    def __init__(self, kare):
        self.start_frame, self.yontem, self.guven = kare, "tespit_v5", 0.9
        self.script, self.notlar, self.ocr_hata = "en", "", 0


def _sahte_kare_cikar(video, hedef):
    hedef.mkdir(parents=True, exist_ok=True)
    (hedef / "c_00001.png").write_bytes(b"x")
    return hedef, 0
```

- [ ] **Adım 2: Testin başarısız olduğunu gör**

```bash
cd /opt/mitas && /opt/mitas/Allstar/kobe/.venv/bin/python -m pytest \
  Allstar/kobe/tests/test_main_akis.py -q 2>&1 | tail -3
```

Beklenen: `ModuleNotFoundError: No module named 'main'`

- [ ] **Adım 3: `config.yaml` yaz**

```yaml
# Kobe — jenerik başlangıç tespiti. Eşikler ve bayraklar.
# Çağıran Girdi.config ile tek tek ezebilir.

kare_cikarim:
  kuyruk_sn: 600       # kapanış penceresi — havuz_kur.sh TAIL_S
  fps: 2               # havuz_kur.sh FPS. DEĞİŞTİRME: %94.5 bu fps ile ölçüldü
  kalite: 3            # ffmpeg -q:v

motor:
  fps: 25.0            # tespit_v5 imzası — yalnız iç hesap, kare fps'i DEĞİL
  stride: 2
  ocr_stride: 2

paddle:
  omp_num_threads: 4   # paralel işçilerde çekirdek taşmasını önle
```

- [ ] **Adım 4: `main.py` yaz**

```python
#!/usr/bin/env python3
"""Kobe — film sonu jeneriğinin başladığı kareyi bulur. Başka hiçbir şey yapmaz.

Kule girişi. Motor (src/motor.py) burayı bilmez; çeviri tek yönlüdür.
Çalıştırma: Allstar/kobe/kobe start --input /yol/videolar
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4")

KULE = Path(__file__).resolve().parent
SRC = KULE / "src"
SCRATCH = KULE / "scratch"
OUT = KULE / "out"
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(SRC))

from sozlesme import Cikti, Girdi, GirdiHatasi, ariza  # noqa: E402

KUYRUK_SN, KARE_FPS, KALITE = 600, 2, 3      # config.yaml varsayılanları


def _config() -> dict:
    y = KULE / "config.yaml"
    if not y.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(y.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _surum() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(KULE), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        return f"kobe@{sha}" if sha else "kobe@?"
    except Exception:
        return "kobe@?"


def film_id_uret(yol: Path, kareler_modu: bool) -> str:
    """Tek kural, tahmin yok: video → uzantısız ad, kare dizini → dizin adı."""
    return yol.name if kareler_modu else yol.stem


def kare_cikar(video: str, hedef: Path) -> tuple[Path, int]:
    """Kapanış penceresini çıkar → (dizin, pencere_baslangic_sn).

    Tarif havuz_kur.sh:74-78'den birebir alınmıştır — %94.5 bu kare üretimiyle
    ölçüldü, başka tarif skoru geçersiz kılar.
    """
    hedef.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", video],
                       capture_output=True, text=True, timeout=120)
    try:
        sure = int(float(p.stdout.strip()))
    except (ValueError, AttributeError):
        raise RuntimeError(f"ffprobe sure okuyamadi: {p.stderr.strip()[:200]}")
    ss = max(0, sure - KUYRUK_SN)
    k = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(ss), "-i", video,
                        "-vf", f"fps={KARE_FPS}", "-q:v", str(KALITE),
                        str(hedef / "c_%05d.png")],
                       capture_output=True, text=True, timeout=900)
    n = len(list(hedef.glob("*.png")))
    if n == 0:
        raise RuntimeError(f"kare cikmadi (rc={k.returncode}): {k.stderr.strip()[:200]}")
    return hedef, ss


def _tespit(dizin: str, config: dict):
    """Motoru çağıran TEK yer — testler burayı değiştirir."""
    import motor
    m = config.get("motor", {})
    return motor.tespit_v5(dizin, fps=m.get("fps", 25.0),
                           stride=m.get("stride", 2),
                           ocr_stride=m.get("ocr_stride", 2))


def tek(girdi: Girdi, kok: Path | None = None) -> Cikti:
    """Bir film → bir Cikti. Asla istisna sızdırmaz; her hata ARIZA olur."""
    kok = Path(kok) if kok else OUT
    t0 = time.time()
    benim_scratch: Path | None = None
    pencere_ss = 0
    try:
        if girdi.video:
            benim_scratch = Path(SCRATCH) / girdi.film_id
            try:
                dizin, pencere_ss = kare_cikar(girdi.video, benim_scratch)
            except Exception as e:
                c = ariza(girdi.film_id, "KARE_CIKARIM", str(e)[:300])
                c.sure_sn = round(time.time() - t0, 1)
                c.motor_surumu = _surum()
                c.yaz(kok)
                return c
        else:
            dizin = Path(girdi.kareler)

        try:
            r = _tespit(str(dizin), girdi.config)
        except Exception as e:
            c = ariza(girdi.film_id, "MOTOR", f"{type(e).__name__}: {e}"[:300])
            c.sure_sn = round(time.time() - t0, 1)
            c.motor_surumu = _surum()
            c.yaz(kok)
            return c

        n = len(list(Path(dizin).glob("*.png"))) or len(list(Path(dizin).glob("*.jpg")))
        kanit = {"kare_sayisi": n, "kare_fps": float(KARE_FPS),
                 "pencere_baslangic_sn": float(pencere_ss),
                 "yontem": getattr(r, "yontem", ""),
                 "ocr_hata": getattr(r, "ocr_hata", 0)}
        if r.start_frame == -1:
            c = Cikti(film_id=girdi.film_id, durum="KREDI_YOK", kanit=kanit)
        else:
            c = Cikti(film_id=girdi.film_id, durum="BULUNDU",
                      baslangic_kare=int(r.start_frame),
                      baslangic_sn=round(pencere_ss + r.start_frame / KARE_FPS, 2),
                      guven=round(float(getattr(r, "guven", 0.0)), 3),
                      script=getattr(r, "script", "en"), kanit=kanit)
        c.sure_sn = round(time.time() - t0, 1)
        c.motor_surumu = _surum()
        c.yaz(kok)
        return c
    finally:
        # YALNIZ Kobe'nin actigi dizin silinir. Disaridan verilen kare
        # dizinine asla dokunulmaz (tek-yazar ilkesi).
        if benim_scratch is not None:
            shutil.rmtree(benim_scratch, ignore_errors=True)


def toplu(girdi_dizini: Path, kareler_modu: bool, kok: Path | None = None) -> list[Cikti]:
    """Girdi yolundaki her öğeyi işle; _TAMAM olanı atla (kaldığı yerden devam)."""
    kok = Path(kok) if kok else OUT
    girdi_dizini = Path(girdi_dizini)
    ogeler = sorted(p for p in girdi_dizini.iterdir()
                    if (p.is_dir() if kareler_modu else p.suffix.lower()
                        in (".mp4", ".mkv", ".avi", ".mov", ".ts")))
    sonuc = []
    for p in ogeler:
        fid = film_id_uret(p, kareler_modu)
        if (kok / fid / "_TAMAM").exists():
            print(f"[atla] {fid}")
            continue
        g = Girdi(film_id=fid, **({"kareler": str(p)} if kareler_modu else {"video": str(p)}))
        c = tek(g, kok)
        sonuc.append(c)
        print(f"[{c.durum}] {fid} kare={c.baslangic_kare} sure={c.sure_sn}s")
    return sonuc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kobe", description="jenerik baslangic tespiti")
    alt = ap.add_subparsers(dest="komut", required=True)

    a = alt.add_parser("start", help="toplu: girdi yolundaki her ogeyi isle")
    a.add_argument("--input", required=True)
    a.add_argument("--kareler", action="store_true",
                   help="girdi yolu hazir kare dizinleri iceriyor")

    b = alt.add_parser("tek", help="tek film")
    b.add_argument("--video")
    b.add_argument("--kareler")
    b.add_argument("--film-id", required=True)

    n = ap.parse_args(argv)
    if n.komut == "start":
        toplu(Path(n.input), n.kareler)
        return 0
    try:
        g = Girdi(film_id=n.film_id, video=n.video, kareler=n.kareler)
    except GirdiHatasi as e:
        c = ariza(n.film_id, "GIRDI_HATASI", str(e))
        c.yaz(OUT)
        print(json.dumps(c.sozluk(), ensure_ascii=False))
        return 2
    print(json.dumps(tek(g).sozluk(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Adım 5: `kobe` sarmalayıcısını yaz**

`Allstar/kobe/kobe`:

```bash
#!/usr/bin/env bash
# Kobe kulesi girisi — kendi venv'ini kendi bulur. Cagiran python bilmez.
K="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$K/.venv/bin/python" "$K/main.py" "$@"
```

```bash
chmod +x /opt/mitas/Allstar/kobe/kobe
```

- [ ] **Adım 6: Testlerin geçtiğini gör**

```bash
cd /opt/mitas && /opt/mitas/Allstar/kobe/.venv/bin/python -m pytest \
  Allstar/kobe/tests/test_main_akis.py -q 2>&1 | tail -3
```

Beklenen: `8 passed`

- [ ] **Adım 7: Kulenin tamamını koştur**

```bash
cd /opt/mitas && /opt/mitas/Allstar/kobe/.venv/bin/python -m pytest \
  Allstar/kobe/tests -q 2>&1 | tail -3 && \
/opt/mitas/Allstar/kobe/kobe --help 2>&1 | head -5
```

Beklenen: `39 passed` (19 yönlendirici + 12 sözleşme + 8 akış) ve CLI yardımı.

- [ ] **Adım 8: Uçtan uca gerçek koşu → `golden/` demirlemesi**

Sahte değil: gerçek Paddle, gerçek kareler. Sonuç `golden/`'a demirlenir ki
ileride kule değiştiğinde çıktının kayıp kaymadığı tek komutla görülsün.

```bash
cd /opt/mitas && \
FILM=$(realpath "$(ls -d data/jenerik_havuz/pool_frames/*/ | head -1)") && \
FID=$(basename "$FILM") && echo "film: $FID" && \
/opt/mitas/Allstar/kobe/kobe tek --kareler "$FILM" --film-id "$FID" 2>/dev/null | tail -1
```

Beklenen: tek satır geçerli JSON; `durum` üç değerden biri.

```bash
cd /opt/mitas && FID=$(basename "$(ls -d data/jenerik_havuz/pool_frames/*/ | head -1)") && \
ls Allstar/kobe/out/"$FID"/ && \
test -f Allstar/kobe/out/"$FID"/_TAMAM && echo "_TAMAM var" && \
test -z "$(ls Allstar/kobe/out/"$FID"/*.tmp 2>/dev/null)" && echo "gecici dosya yok"
```

Beklenen: `kobe.json` + `_TAMAM`, `.tmp` yok.

Dış kare dizininin bozulmadığını doğrula (tek-yazar ilkesi):

```bash
ls "$(ls -d /opt/mitas/data/jenerik_havuz/pool_frames/*/ | head -1)" | wc -l
```

Beklenen: `> 50` — dizin duruyor.

- [ ] **Adım 9: `golden/` demirini yaz**

```bash
cd /opt/mitas && FID=$(basename "$(ls -d data/jenerik_havuz/pool_frames/*/ | head -1)") && \
mkdir -p Allstar/kobe/golden && \
/opt/mitas/Allstar/kobe/.venv/bin/python -c "
import json, sys
d = json.load(open(f'Allstar/kobe/out/{sys.argv[1]}/kobe.json'))
# zamana/SHA'ya bagli alanlar demirlenmez — yalniz KARAR demirlenir
demir = {k: d[k] for k in ('film_id','durum') if k in d}
demir |= {k: d[k] for k in ('baslangic_kare','script') if k in d}
json.dump(demir, open('Allstar/kobe/golden/tek_film.json','w'),
          ensure_ascii=False, indent=1)
print(json.dumps(demir, ensure_ascii=False))
" "$FID"
```

`Allstar/kobe/golden/BENIOKU.md`:

```markdown
# golden — karar demiri

`tek_film.json`, `data/jenerik_havuz/pool_frames/` içindeki ilk filmin
Kobe kararıdır (kule kurulduğu gün, gerçek Paddle ile üretildi). Zamana ve
git SHA'sına bağlı alanlar bilerek dışarıda — yalnız **karar** demirlenmiştir.

Yeniden doğrulamak için:

    FILM=$(realpath "$(ls -d data/jenerik_havuz/pool_frames/*/ | head -1)")
    Allstar/kobe/kobe tek --kareler "$FILM" --film-id "$(basename "$FILM")"

Çıkan `durum` / `baslangic_kare` / `script` bu dosyayla aynı olmalıdır.
Farklıysa kule davranışı değişmiştir — 110 filmlik tam ölçümü koş
(`olcum/olc_pool.py --paralel 8`) ve nedenini bul.
```

- [ ] **Adım 10: Koşu çıktısını temizle ve commit**

`out/` git'te değildir; yine de tezgâhı temiz bırak.

```bash
cd /opt/mitas && rm -rf Allstar/kobe/out/* && \
git add Allstar/kobe/main.py Allstar/kobe/kobe Allstar/kobe/config.yaml \
        Allstar/kobe/tests/test_main_akis.py Allstar/kobe/golden && \
git commit -m "feat(kobe): CLI ve kosu akisi - toplu kuyruk, scratch yasam dongusu

- kobe start --input <yol> : idempotent toplu kuyruk, _TAMAM olani atlar
- kare cikarimi havuz_kur.sh tarifi birebir (kuyruk 600 sn, fps 2)
- scratch YALNIZ Kobe'nin actigi dizin icin silinir; disaridan verilen
  kare dizinine dokunulmaz
- her istisna ARIZA'ya cevrilir, hicbiri KREDI_YOK'a dusmez
- golden/tek_film.json: gercek Paddle kosusuyla uretilmis karar demiri

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Görev 9: Belgeler ve temizlik

**Dosyalar:**
- Oluştur: `Allstar/MAP.md`, `Allstar/kobe/CHANGELOG.md`
- Taşı: `docs/FIGO.md` → `Allstar/kobe/README.md`
- Sil: `Players/`

- [ ] **Adım 1: README'yi taşı ve FIGO adını temizle**

```bash
cd /opt/mitas && git mv docs/FIGO.md Allstar/kobe/README.md
```

`README.md` içinde:
- Başlık → `# Kobe — jenerik başlangıç tespiti`
- Tüm `FIGO` geçişleri → `Kobe`
- Yol tablosu güncellenir: `harness/kunye_kiyas/figo.py` → `Allstar/kobe/src/motor.py`, `credit_box.py` → `src/kutu.py`, `credit_content.py` → `src/icerik.py`
- Koşum örneği sarmalayıcıya çevrilir: `Allstar/kobe/kobe tek --kareler <dizin> --film-id <id>`
- "Sorumluluk sınırı" bölümü eklenir: ne yapar / ne yapmaz (spec §4.1)

- [ ] **Adım 2: `Allstar/MAP.md` yaz**

```markdown
# Allstar — kod adı ↔ görev sözlüğü

Kule = klasör + sözleşme. Her kule kendi girdisini alır, çıktısını YALNIZ kendi
`out/`'una yazar, gerisine karışmaz. Kuleler birbirini beklemez.

| Kod adı | Gerçek görev | Durum |
|---|---|---|
| **kobe** | Film sonu jeneriğinin başladığı kareyi bulur | **kuruldu** |
| lebron_james | Master PNG üretim hattı | planlandı |
| steve_nash | Kare ayıklayıp yeni havuz | planlandı |
| jordan | MP4'ten doğrudan okutma | planlandı |
| shaq | Farkları kıyaslar + kutu kontrol | planlandı |
| phil_jackson | Shaq verisini fuzzy ile düzeltir | planlandı |
| qc1_lakers | Kalite kapısı 1 | planlandı |
| qc2_sixers | Kalite kapısı 2 | planlandı |
| iverson | ASR tam transkript + özet | planlandı |

Sonraki kule sırasını Çağatay söyler. Adım adım ilerlenir.

**Kule sınırı:** kod + ürettiği veri + sözleşme + çalışma zamanı (kendi venv'i).
Zemin (Python/CUDA/Paddle ikilileri, model ağırlıkları, `core/lexicon/` gibi
paylaşılan salt-okunur sözlükler) sınırın dışındadır. Yasak olan, başka bir
kulenin ÜRETTİĞİ veriyi doğrudan okumaktır.
```

- [ ] **Adım 3: `Allstar/kobe/CHANGELOG.md` yaz**

```markdown
# Kobe — değişiklik günlüğü

## 2026-08-12 — kule kuruldu
- `harness/kunye_kiyas/` içinden `Allstar/kobe/`'ye taşındı; `figo` adı silindi.
- Kendi çalışma zamanı: `.venv` (paddlepaddle-gpu 3.3.1 / paddleocr 3.7.0).
- Sözleşme eklendi: `Girdi` / `Cikti` / `ariza`, atomik yazım + `_TAMAM`.
- CLI eklendi: toplu kuyruk (`start`) ve tek film (`tek`).
- **Ölçüm sapması sıfır** — kapsam 110, genel %94.5, üretim %97.3,
  kredi-yok 29/29. Öncesi/sonrası: `raporlar/olcum_{ONCE,VENV,SONRA}.json`.
- Bilinen borç: `src/kutu.py` ve `src/icerik.py`, `harness/kunye_kiyas/`
  altındaki asıllarının kopyasıdır. Okuma kulesi kurulduğunda o kule kendi
  kopyasını alacak ve `harness/kunye_kiyas/` silinecek.
```

- [ ] **Adım 4: Boş `Players/` iskeletini sil**

```bash
cd /opt/mitas && \
echo "git'te izlenen: $(git ls-files Players/ | wc -l)  bos olmayan dosya: $(find Players -type f ! -size 0 | wc -l)"
```

Her iki sayı da `0` ise (doğrulandı: 160 dosyanın tamamı boş, hiçbiri git'te değil):

```bash
cd /opt/mitas && rm -rf Players && ls -d Players 2>&1
```

Sayılardan biri `0` değilse **silme** — DUR ve rapor et.

- [ ] **Adım 5: Son kapı — testler + ölçüm birlikte**

```bash
cd /opt/mitas && /opt/mitas/Allstar/kobe/.venv/bin/python -m pytest \
  Allstar/kobe/tests -q 2>&1 | tail -2 && \
grep -rn "figo" --include="*.py" --include="*.md" . 2>/dev/null | grep -v __pycache__ | \
  grep -v "docs/GUNLUK\|docs/superpowers\|CHANGELOG" | head
```

Beklenen: `39 passed`, `figo` araması boş.

```bash
cd /opt/mitas/Allstar/kobe/olcum && \
/opt/mitas/Allstar/kobe/.venv/bin/python olc_pool.py --paralel 8 2>/dev/null | tail -3
```

Beklenen: `KAPSAM 110 ... GENEL 104/110 = %94.5 ... ÜRETİM 107/110 = %97.3`, `kredi-yok: 29/29`.

- [ ] **Adım 6: Commit**

`Players/` git'te izlenmiyordu — silinmesi için sahnelenecek bir şey yok.

```bash
cd /opt/mitas && git add Allstar && \
git status --porcelain --cached | head -20 && \
git commit -m "docs(allstar): Kobe README/CHANGELOG + MAP.md; bos Players iskeleti silindi

FIGO adi repodan tamamen kalkti. Ilk kule ayakta: 39/39 test, olcum sapmasi sifir.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Adım 7: GUNLUK kaydı**

`docs/GUNLUK.md`'nin **en üstüne** yeni kayıt ekle: yapılan (kule kuruldu, üç ölçüm kapısı geçti), öğrenilen (paralellik kurulumdan değil süreçten gelir; `credit_box` üretim okuyucusu tarafından da kullanılıyordu, taşınsaydı kırılırdı), bekleyen (okuma kulesi, CPU/GPU bölüşüm ölçümü, `harness/kunye_kiyas/` kalıntısı).

```bash
cd /opt/mitas && git add docs/GUNLUK.md && \
git commit -m "docs(gunluk): Kobe kulesi kuruldu - 2026-08-12 kaydi

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Kapsam dışı

- Diğer kuleler (LeBron, Nash, Jordan, Shaq, Phil Jackson, Lakers, Sixers, Iverson).
- CPU/GPU kaynak bölüşümü ölçümü — Kobe kule olduktan sonra, Çağatay'ın onayıyla ayrı iş (spec §4.7).
- `Database/<Film>/` hardlink görünümü — tüketici kule kurulunca (spec §4.6).
- `core/pipelines/ocr/jenerik_*` dosyalarının akıbeti.
- Üretim hattının yeniden başlatılması.
- Dizi modu.
