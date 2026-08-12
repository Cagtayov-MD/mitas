# Betik-Farkında Rol Tanıma — Tasarım

**Tarih:** 2026-08-12
**Tasarım:** Claude Opus · **Uygulama:** Claude Sonnet
**Onay:** Çağatay (2026-08-12)

---

## 0. Bu belge nasıl okunmalı

Uygulayan model bu belgeyi okuyup **hiçbir teşhis çalışması yapmadan** işe başlayabilmeli.
Tüm satır numaraları, veri yapıları ve test vektörleri burada. Belgede yazmayan bir şeyi
"herhalde şöyledir" diye tamamlama — belirsizlik varsa dur ve sor.

**Değişmezler bölümü (§6) pazarlığa açık değildir.** Oradaki bir ölçüm bozulursa değişiklik
geri alınır, "sonra düzeltiriz" denmez.

---

## 1. Problem (ölçüldü, uydurma değil)

Son 25 filmin 23'ü kontrole düştü. Tek tek incelendi; 6 filmde **yönetmen rol kelimesi OCR
metninde mevcut ama sistem tanımıyor**:

| film | dil | metindeki kelime |
|---|---|---|
| MASUMİYET DÜŞLERİ 1994-0238 | İbranice | `במאי` / `בימוי` |
| DOVLATOV 2018-1036 | Rusça | `режиссера` |
| KOŞUCU 2025-1047 | Farsça | `نویسنده و کارگردان` |
| SERÇELERİN ŞARKISI 2008-1114 | Farsça | `کارگردان` |
| MUCİZE 2004-9157 | Korece | `감독` |
| SENİ SEVİYORUM FRANK 1988-0480 | Latin | `Director-Cameraman` |

Bu 6 filmin **hepsinde KOBE onset'i doğru bulmuştu** (havuz 166–574 kare). Arıza tespitte
değil, rol tanımada.

---

## 2. Kök sebep — modül modül, kanıtla

### 2.1 `scripts/credit_role_lexicon.py` (isim çıkarma hattı)

`norm()` (satır 21-27) Latin dışı her karakteri siliyor:

```python
s = re.sub(r"[^A-Z ]+", " ", s)      # ← satır 25
```

Canlı test çıktısı:

```
'DIRECTED BY JOHN FORD'       → norm='DIRECTED BY JOHN FORD'  is_director_line=True   ad='JOHN FORD'
'Yönetmen: Nuri Bilge Ceylan' → norm='YONETMEN NURI BILGE...' is_director_line=True   ad='NURI BILGE CEYLAN'
'Режиссёр Алексей Герман'     → norm=''                       is_director_line=False  ad=''
'کارگردان مجید مجیدی'         → norm=''                       is_director_line=False  ad=''
'감독 박찬욱'                   → norm=''                       is_director_line=False  ad=''
'במאי'                        → norm=''                       is_director_line=False
'σκηνοθέτης'                  → norm=''                       is_director_line=False
```

Sonuç: `DIRECTOR` listesindeki `REJISOR` / `MUHARRIJ` / `DAOYAN` / `SKINOTHETIS` girdileri
**ölü kod** — üretilmesi imkânsız Latin karşılıklar. Yorumlarda "режиссёр fold->rejissor"
yazıyor ama öyle bir fold yok.

### 2.2 `harness/kunye_kiyas/credit_content.py` (KOBE onset hattı)

Kiril ve Arapça desteği **zaten var** ama LLM tahminine kilitli (satır 121-137):

```python
def cekirdek_rol_bul(kare_satirlari):
    lang = get_aktif_dil()                       # ← LLM tahmini, OCR'dan ÖNCE yapıldı
    ...
            if lang == 'ar':
                for m in _ROL_ARAP.findall(_arapca_normalize(s)): ...
            elif lang == 'ru':
                for m in _ROL_KIRIL.findall(s): ...
```

Ölçüm: son 25 filmdeki 10 Latin-dışı filmin **6'sında tahmin yanlış**.

| film | tahmin | metnin gerçek betiği |
|---|---|---|
| DOVLATOV | `en` | KİRİL |
| MASUMİYET DÜŞLERİ | `en` | İBRANİ |
| GÖLGELER KENTİ | `en` | CJK |
| MUCİZE | `en` | CJK |
| ARŞIN MAL ALAN | `ar` | KİRİL |
| KIZIL HAYAT | `ru` | LATİN |

DOVLATOV Kiril metin taşıyor ama `lang='en'` olduğu için Kiril dalı **hiç çalışmadı**.
ARŞIN Kiril metin taşıyor ama `lang='ar'` olduğu için **Arapça dalı Kiril metinde koştu**.

Ayrıca `_ROL_CEKIRDEK` (satır 88) `\b...\b` tam-kelime eşleşmesi kullanıyor — boşluk
kullanmayan betiklerde (CJK, Hangul) `\b` çalışmaz.

Mevcut kapsam: EN/TR/IT/FR/DE/ES/HU + SV/NO/DA (2026-08-12'de eklendi). Hepsi Latin.
Yok: Kiril (kilitli), Arapça (kilitli), İbranice, Korece, Yunanca, CJK.

### 2.3 `scripts/credit_text_read.py:582` (canlı yönetmen regex'i)

Kendi ayrı listesi var, tamamen Latin, `\b` sınırlı:

```python
r"\b(directed by|a film by|film by|un film de|ein film von|film von|realise par|realisateur|"
r"regia di|dirigido por|yonetmen|yoneten|rejisor|regie|"
r"...|written and directed|directed and edited|produced and directed)\b"
```

### 2.4 `OCR-worktree/pdf-mitas/credit_parse.py:70` (PDF hattı)

Kendi `_ROLE_MATCH` listesi + **sıra hatası**. `Kameraman` girdisi `Yönetmen`den önce
geldiği için:

```
role_of('Director-Cameraman')  → 'Kameraman'      (yanlış — yönetmen olmalı)
```

### 2.5 Ortam kısıtı

Üç modül de **saf stdlib** (`re`, `unicodedata`, `contextvars`, `os`, `sys`), birbirini
import etmiyor, **üç ayrı sys.path ağacında**:

| modül | ağaç | nasıl yükleniyor |
|---|---|---|
| `credit_content.py` | `harness/kunye_kiyas/` | `_jenerik_pool.py` path'e ekliyor |
| `credit_role_lexicon.py` | `scripts/` | `scripts/` içinden düz import |
| `credit_parse.py` | `OCR-worktree/pdf-mitas/` | `_pipe_pdf.py` importlib + path insert |

Ortak tablo bu üçünden de erişilebilir olmalı.

---

## 3. Tasarım

### 3.1 Temel ilke: dil tahmini iki fazlı

```
FAZ-1  OCR ÖNCESİ — tahmin kaçınılmaz (metin henüz yok)
       karelerden dil tahmini  →  Paddle hangi OCR modeliyle koşacak

FAZ-2  OCR SONRASI — kesinlik mümkün (metin elimizde)
       unicodedata ile betik  →  %100 kesin
                               →  rol eşleşmesi DAİMA bunu kullanır
                               →  tahmin ≠ gerçek ise olay logla
```

**Kural:** Rol kelimesi eşleşmesi hiçbir yerde `get_aktif_dil()` değerine bakmaz.
Betik, eşleşme anında satırın kendisinden hesaplanır.

Bu tek başına DOVLATOV ve ARŞIN vakalarını çözer — kod ve kelimeler zaten var, sadece
yanlış kapının arkasındalar.

### 3.2 Ortak tablo — yeni dosya

**Yol:** `core/lexicon/rol_tablosu.py`
**Bağımlılık:** yalnız `unicodedata`, `re`. Başka hiçbir proje modülünü import etmez.

```python
TABLO = {
  "LATIN":  {"YONETMEN": [...§4.1'e bak...], "HARIC": [...§4.1'e bak...]},
  "KIRIL":  {"YONETMEN": ["РЕЖИСС", "ПОСТАНОВЩИК"],
             "HARIC":    ["АССИСТЕНТ", "ПОМОЩНИК", "ВТОРОЙ", "ХУДОЖНИК", "ОПЕРАТОР"]},
  "ARAP":   {"YONETMEN": ["کارگردان", "مخرج", "اخراج"],
             "HARIC":    ["دستیار", "مساعد", "فیلمبرداری"]},
  "IBRANI": {"YONETMEN": ["במאי", "בימוי"],
             "HARIC":    ["עוזר", "משנה", "צילום"]},
  "YUNAN":  {"YONETMEN": ["ΣΚΗΝΟΘΕΤ"],
             "HARIC":    ["ΒΟΗΘΟΣ", "ΦΩΤΟΓΡΑΦΙΑ"]},
  "HANGUL": {"YONETMEN": ["감독", "연출"],
             "HARIC":    ["조감독", "촬영감독", "미술감독", "음악감독"]},
  "CJK":    {"YONETMEN": ["导演", "導演", "監督"],
             "HARIC":    ["副导演", "助理导演", "执行导演", "撮影監督", "美術監督"]},
}
```

İki genel yardımcı:

```python
def betik_bul(s: str) -> str:
    """Satırın baskın betiği. Harf olmayan karakterler sayılmaz.
    Dönüş: LATIN | KIRIL | ARAP | IBRANI | YUNAN | HANGUL | CJK | BOS"""

def rol_esles(s: str, tur: str = "YONETMEN", haric_uygula: bool = True) -> bool:
    """Satır bu rol türüne uyuyor mu. Betiği kendisi bulur.
    haric_uygula=False → HARIC listesi atlanır (KOBE onset çapası için)."""
```

**Yeni dil eklemek = TABLO'ya satır eklemek.** Kod değişmez.
Tek istisna: Latin-genişletilmiş harfler (Vietnamca `đạo diễn`, `đ`=U+0111). Bunun için
LATIN karakter sınıfı bir kez genişletilir; §4.1'de yapılacak, sonra kapanır.

### 3.3 Betiğe göre eşleşme kuralı

| Betik | Kural | Gerekçe |
|---|---|---|
| LATIN | **Mevcut kod hiç değişmeden** | Sıfır regresyon (§6.1) |
| KIRIL, YUNAN | Kök-önek eşleşme | Bükünlü. `РЕЖИСС` → режиссёр / режиссер / режиссёра / режиссёром hepsini yakalar |
| ARAP, IBRANI | Alt-dize | Bu kelimelerde çekim eki sorunu yok |
| HANGUL, CJK | Alt-dize, `\b` YOK | Boşluk yok; `\b` bu betiklerde eşleşmez |

**Kiril ё↔е katlaması zorunlu:** Rusça'da `режиссёр` ve `режиссер` ikisi de yaygın.
Karşılaştırmadan önce `ё→е`, `Ё→Е`.

**Büyük/küçük harf:** Kiril ve Yunan için `.upper()` uygulanır (Yunanca final sigma
`ς`→`Σ` dönüşümü Python'da doğru çalışır). Arap/İbrani/CJK/Hangul'da harf durumu yoktur.

### 3.4 İki tüketici, iki sıkılık

```
KOBE onset (credit_content.py)       →  rol_esles(..., haric_uygula=False)
    "yardımcı yönetmen" de jeneriktir.  Çapa için hepsi geçerli.

İsim çıkarma (credit_role_lexicon)   →  rol_esles(..., haric_uygula=True)
    "촬영감독" (görüntü yön.) yönetmen DEĞİLDİR.  Ayrım şart.
```

Bu ayrım Çağatay'ın katkısı ve dış konseyin en ağır itirazını (her dil için EXCLUDE bakım
yükü) yalnızca ikinci hatta hapsediyor. KOBE hattı EXCLUDE taşımaz.

### 3.5 Görünürlük

Betiği `TABLO`'da karşılığı olmayan bir satır gelirse (`BOS` değil ama tabloda yok),
`rol_tablosu_bosluk` olayı loglanır: `{"betik": "THAI", "ornek": "<satırın ilk 40 karakteri>"}`.

Amaç: "neden Tayca filmde yönetmen yok" sorusunun cevabı 6 ay sonra `git blame` değil,
log araması olsun. Dış konseyin "sessiz çürüme" uyarısına karşı önlem.

---

## 4. Değişiklik yüzeyi — dosya dosya

### 4.0 Ortak yükleme deseni (üç tüketici de BUNU kullanır)

`core/` zaten bir paket (`core/__init__.py` var) ve projede `MITAS_PROJECT_ROOT`
konvansiyonu mevcut (`scripts/_jenerik_pool.py:34-35`). Üç tüketici de şu korumalı
bootstrap'i kullanır — başka yöntem icat edilmez:

```python
import os, sys
from pathlib import Path
_KOK = Path(os.environ.get("MITAS_PROJECT_ROOT") or "/opt/mitas")
if str(_KOK) not in sys.path:
    sys.path.insert(0, str(_KOK))
from core.lexicon.rol_tablosu import betik_bul, rol_esles   # noqa: E402
```

Neden her dosyada tekrar: `credit_content.py` bazen `_jenerik_pool.py` üzerinden
(PROJECT_ROOT path'te), bazen `olc_pool.py` üzerinden (yalnız `harness/kunye_kiyas`
path'te — satır 16) yükleniyor. Korumalı bootstrap ikisinde de çalışır.

`core/lexicon/__init__.py` boş olarak oluşturulur.

### 4.1 YENİ: `core/lexicon/rol_tablosu.py`

- `TABLO` sözlüğü (§3.2).
- `LATIN.YONETMEN` = `credit_role_lexicon.DIRECTOR` listesinin **birebir kopyası**
  (satır 29-70). Kelime EKLEME, ÇIKARMA, sıra değiştirme YOK.
- `LATIN.HARIC` = `credit_role_lexicon.EXCLUDE` listesinin **birebir kopyası** (satır 94-121).
- LATIN karakter sınıfına Latin-genişletilmiş harfler eklenir (`đ` U+0111, `Đ` U+0110 ve
  NFKD sonrası ASCII'ye inmeyen diğer Latin harfleri). Bu tek seferlik.
- `betik_bul()`, `rol_esles()` (§3.2).
- `__init__.py` gerekiyorsa `core/lexicon/__init__.py` boş oluşturulur.

### 4.2 `harness/kunye_kiyas/credit_content.py`

> ⚠️ **DİKKAT — `get_aktif_dil()` SİLİNMEZ.** Bu fonksiyon iki ayrı iş yapıyor:
> 1. **OCR model seçimi** (satır 193 `_qwen_vision_ocr(..., lang=...)`, satır 468) —
>    bu Faz-1'dir, **olduğu gibi kalır**. Dokunulursa OCR bozulur.
> 2. **Rol eşleşmesi kapısı** (satır 124-135) — **yalnız bu kaldırılır.**
>
> Yani `set_aktif_dil` / `get_aktif_dil` / `contextvars` altyapısı yerinde durur;
> sadece `cekirdek_rol_bul` ve `cekirdek_rol_bul_genis` içindeki `lang` kapısı
> `betik_bul(s)` ile değiştirilir.

- `cekirdek_rol_bul()` (satır 121-137): satır 124'teki `lang = get_aktif_dil()`
  **bu fonksiyon içinde** kullanılmaz olur. Yerine her satır için `betik_bul(s)`.
- `if lang == 'ar'` / `elif lang == 'ru'` dalları betik koşuluna çevrilir (aşağıdaki akış).
- Mevcut regexler **silinmez**, ama rolleri netleşir:
  - `_ROL_CEKIRDEK`, `_ROL_MACAR_ONEK` → **aynen kalır**, LATIN satırlarda bugünkü gibi
    çalışır. Dokunulmaz (§6.1).
  - `_ROL_ARAP`, `_ROL_KIRIL` → regexlerin kendisi kalır ama **`lang` kapısı kalkar**.
    Artık `betik_bul(s) == "ARAP"` / `== "KIRIL"` olduğunda çalışırlar. Yani aynı
    kelimeler, doğru kapı. Tabloya EK olarak değil, tablonun ARAP/KIRIL girdileriyle
    birlikte çalışırlar — tablodaki kelime listesi bunların üstüne gelir.
  - Yeni betikler (IBRANI, HANGUL, CJK, YUNAN) yalnız tablodan gelir.

  Net akış:

  ```python
  for s in sl:
      b = betik_bul(s)
      if b == "LATIN":
          ...mevcut _ROL_CEKIRDEK + _ROL_MACAR_ONEK yolu, birebir...
      elif b == "ARAP":
          ...mevcut _ROL_ARAP yolu + tablo ARAP...
      elif b == "KIRIL":
          ...mevcut _ROL_KIRIL yolu + tablo KIRIL...
      else:
          ...yalnız tablo[b]...
  ```
- `cekirdek_rol_bul_genis()` (satır 159) aynı desenle güncellenir.
- `haric_uygula=False` kullanılır.

### 4.3 `scripts/credit_role_lexicon.py`

- `norm()` **DEĞİŞTİRİLMEZ.** Yanına `norm_betik(s)` eklenir.
- `is_director_line()`, `director_name_from_line()`, `_match_head()`, `_has_excl()`:
  başına betik dalı eklenir.

```python
if betik_bul(text) == "LATIN":
    ...bugünkü kod, birebir...
else:
    ...yeni betik-koruyan yol...
```

- `director_name_from_line()` Latin-dışı için: rol kelimesi soyulur, kalan kısım isim
  sayılır. `_is_name()` Latin-dışında `[A-Z]` varsayımı yapamaz — betik-dışı yol için
  ayrı sadeleştirilmiş isim kontrolü (boş değil, rakam-ağırlıklı değil, HARIC içermiyor).

### 4.4 `scripts/credit_text_read.py`

- Satır 582-585'teki yönetmen regex'i **silinir**, `rol_tablosu.rol_esles(..., "YONETMEN")`
  çağrısına delege edilir.
- Regex'in Latin kelimeleri zaten `LATIN.YONETMEN`'de var; kayıp olmadığı test edilir (§7).

### 4.5 `OCR-worktree/pdf-mitas/credit_parse.py`

- `_ROLE_MATCH` (satır 70-101) içindeki `Yönetmen` girdisi `rol_tablosu`'na delege edilir.
- **Sıra hatası düzeltilir:** `role_of()` (satır 155-173) içinde `Yönetmen` kontrolü
  `Kameraman`dan ÖNCE yapılır — ama yalnız satır "Yönetmen Yardımcısı" / "Görüntü Yönetmeni"
  / "Sanat Yönetmeni" gibi nitelikli bir role uymuyorsa. Yani öncelik sırası:
  `Yönetmen Yardımcısı > Görüntü Yönetmeni > Sanat Yönetmeni > Yönetmen > Kameraman Yardımcısı > Kameraman`.
  Beklenen: `role_of('Director-Cameraman') == 'Yönetmen'`.
- Bu dosya ayrı ağaçta; `rol_tablosu`'nu `_pipe_pdf.py`'nin kullandığı importlib+path
  desenini taklit ederek yükler. Yeni bağımlılık eklenmez.

---

## 5. Uygulama sırası (Sonnet bu sırayla ilerlesin)

**Öncelik: KOBE hattı.** Çağatay'ın hedefi KOBE'nin yer tespiti — tablo kurulur kurulmaz
oraya geçilir, isim-çıkarma hattı sonra.

1. `core/lexicon/rol_tablosu.py` + birim testleri → yeşil.
2. **`credit_content.py` delege (KOBE onset)** → `olc_pool.py` ölçümü, §6.2 değişmezleri.
3. `credit_role_lexicon.py` delege → Latin regresyon testi + yeni betik testleri yeşil.
4. `credit_text_read.py` delege → testler yeşil.
5. `credit_parse.py` delege + sıra düzeltmesi → testler yeşil.

Her adım ayrı commit. Bir adım kırmızıysa sonrakine geçilmez.

---

## 6. DEĞİŞMEZLER — bunlardan biri bozulursa değişiklik geri alınır

### 6.1 Latin davranışı bit düzeyinde aynı

Latin bir satır yeni kodun **tek satırına bile girmemeli**. Betik dalı `LATIN` ise bugünkü
kod yolu birebir çalışır.

**Kanıt yöntemi — somut, Sonnet bunu uygulasın:**

1. Değişiklikten ÖNCE, `scripts/anlik_latin_taban.py` adıyla tek kullanımlık bir betik yaz.
   Database'deki `*/ocr/*/ocr_ham.txt` dosyalarından **yalnız `betik_bul(s)=="LATIN"` olan
   satırları** topla (üst sınır 50.000 satır, deterministik sıra: dosya adı + satır no).
2. Her satır için `is_director_line`, `director_name_from_line`, `credit_parse.role_of`
   çıktılarını `scratchpad/latin_taban_once.jsonl`'e yaz.
3. Değişiklikten SONRA aynı betiği koştur → `latin_taban_sonra.jsonl`.
4. `diff` **sıfır satır** vermeli. Tek satır fark varsa değişiklik geri alınır.

Bu betik geçici; iş bitince silinir (repoda kalmaz).

### 6.2 `olc_pool.py` ölçümü gerilememelİ

Değişiklik öncesi taban (`harness/kunye_kiyas/veri/olcum_son.json`):

```
kapsam 110 · genel %93.6 · üretim %97.3 · kredi_var 74/81 · kredi_yok 29/29
```

**`kredi_yok 29/29` özellikle kritiktir.** `credit_content.py`'ye rol kelimesi eklemek
`len(core_roller) >= 2` eşiğini şişirip seyrek-yolu yanlış açabilir ve jeneriksiz bir filmi
"jenerik var" sanabilir. Dosyanın 142-156. satırlarındaki `_PRODUC_GENIS` içtihadı tam bu
yüzden var: produc-ailesi kaç yüzey-formu geçerse geçsin **TEK kanonik rol** sayılır.

**Aynı disiplin yeni betiklere de uygulanacak:** bir betikteki yönetmen kelimesinin farklı
yüzey-formları (`режиссёр` / `режиссера` / `режиссёром`) rol çeşitliliğine **en fazla +1**
katkı yapar. Set'e ham yüzey-formu değil, **kanonik rol adı** eklenir.

Adım 3 sonrası `olc_pool.py --paralel 8` koşulur. `kredi_yok` 29/29'un altına düşerse
değişiklik geri alınır.

### 6.3 Yanlış-pozitif kırmızı çizgisi

İsim çıkarma hattında (`haric_uygula=True`) şunlar yönetmen sayılırsa hata:
`촬영감독`, `조감독`, `副导演`, `助理导演`, `עוזר במאי`, `دستیار کارگردان`,
`ΒΟΗΘΟΣ ΣΚΗΝΟΘΕΤΗΣ`, `АССИСТЕНТ РЕЖИССЕРА`, `ПОМОЩНИК РЕЖИССЕРА`.

---

## 7. Test planı (TDD — önce kırmızı)

Yeni dosya: `tests/test_rol_tablosu.py`

**A. Betik tespiti** — her betik için 2 vektör + karışık satır + boş satır.

**B. Pozitif eşleşme** (her betik, `haric_uygula=False`):

| betik | girdi | beklenen |
|---|---|---|
| KIRIL | `Режиссёр Алексей Герман` | True |
| KIRIL | `режиссера` (çekimli) | True |
| KIRIL | `РЕЖИССЕР` (е ile) | True |
| ARAP | `کارگردان مجید مجیدی` | True |
| IBRANI | `במאי` / `בימוי` | True |
| HANGUL | `감독 박찬욱` | True |
| CJK | `导演张艺谋` (boşluksuz) | True |
| CJK | `導演` (geleneksel) | True |
| CJK | `監督：是枝裕和` | True |
| YUNAN | `ΣΚΗΝΟΘΕΤΗΣ` | True |

**C. HARIC negatifleri** (`haric_uygula=True` → False, `haric_uygula=False` → True):
§6.3'teki 9 vektörün tamamı.

**D. Latin regresyonu** — mevcut davranışın korunduğu en az 10 vektör:
`DIRECTED BY JOHN FORD`, `Yönetmen: Nuri Bilge Ceylan`, `REGIA`, `UN FILM DE`,
`GÖRÜNTÜ YÖNETMENİ` (False), `ASSISTANT DIRECTOR` (False), `DIRECTION ARTISTIQUE` (False) …

**E. Sıra hatası** — `role_of('Director-Cameraman') == 'Yönetmen'`.

**F. Gerçek film vektörleri** — §1'deki 6 filmin OCR metninden alınmış gerçek satırlar.
Bu satırlar `ocr_ham.txt` dosyalarından kopyalanır, uydurulmaz.

---

## 8. Kapsam dışı (bu işte YAPILMAYACAK)

- **Dil yönlendiricisinin (Faz-1) kendisini düzeltmek.** Bu tasarım router'ın hatasını
  *etkisiz kılıyor* (rol eşleşmesi artık ona bakmıyor) ama Paddle'ın hangi OCR modeliyle
  koşacağı hâlâ router'a bağlı. Ayrı iş, ayrı spec.
- **Romanizasyon / harf çevirisi.** Bilinçli reddedildi: Kiril→Latin'in rakip şemaları var,
  Arap/İbrani ünsüz-yazımı kayıplı, CJK→pinyin/romaji oynak.
- **A grubu (kapanış jeneriği olmayan filmler) için açılış-jeneriğinden künye okuma.**
  Son 25 filmin 8'i bu grupta; ayrı ve daha büyük iş.
- **Lemmatization / stemmer kütüphanesi.** Kök-önek eşleşmesi bu iş için yeterli;
  bağımlılık eklemiyoruz.

---

## 9. Dış konsey turu (2026-08-12)

Kırmızı takım modunda soruldu. Yanıtlayanlar: GLM, Nemotron, MiniMax
(Qwen — hesap arızası; Kimi — model EOL).

**Konsey tasarımı bu haliyle REDDETTİ.** Ana itirazlar ve karşılığı:

| itiraz | karar |
|---|---|
| `norm()` Latin-dışını siliyor, native match matematiksel olarak imkânsız | **Kabul** — §3.3, §4.3'te betik-koruyan yol eklendi |
| Bükünlü dillerde tam eşleşme çuvallar (`режиссёра`, `감독님`) | **Kabul** — §3.3 kök-önek eşleşmesi |
| Her dil için EXCLUDE listesi = bakım kabusu | **Kısmen** — Çağatay'ın onset/isim ayrımı (§3.4) bu yükü yalnız isim hattına hapsediyor. KOBE hattı EXCLUDE taşımaz |
| Boşluksuz betikte `\b` çalışmaz | **Kabul** — §3.3 |
| Geleneksel/basit Çince, Kanji/katakana Japonca | **Kabul** — §3.2 tabloda ikisi de var |
| Sessiz çürüme, log yok | **Kabul** — §3.5 `rol_tablosu_bosluk` olayı |
| "Sözlüğe satır ekle, kod değişmez" sloganı Latin-genişletilmiş harflerde yalan | **Kabul, açıkça yazıldı** — §3.2 istisna maddesi |
| Romanizasyon (ICU) yapılmalıydı | **Reddedildi** — §8'deki gerekçe. Konseyin bu maddesi alınmadı |

---

## 10. Bu işin çözmediği şey

Son 25 filmin kontrole düşme sebepleri beş grup:

| grup | film | bu iş çözüyor mu |
|---|---|---|
| A · kapanış jeneriği yok, açılışa düşen yol yok | 8 | **Hayır** (§8) |
| B · rol kelimesi var, sözlük tanımıyor | 6 | **Evet** |
| C · metinde rol kelimesi bulunamadı | 3 | Kısmen — 1'i OCR modelinin resmi tarif etmesi, ayrı arıza |
| D · yönetmen okundu, başka kapı (KIMLIK/CAST/RENDER) | 4 | Hayır, ayrı iş |
| E · rol eşleşti, isim çıkarılamadı | 2 | Muhtemelen — §4.3 isim çıkarma yolu bunlara da dokunuyor |

Beklenen kazanım: **6 film kesin, 2 film muhtemel.** Kontrol oranında tek başına dramatik
düşüş beklenmiyor — asıl kütle A grubunda ve o ayrı iş.
