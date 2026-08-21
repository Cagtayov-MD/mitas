"""FAZ 2 — VLM okuma kanalı: Qwen3-VL-8B, kare grupları → aday kredi satırları.

PLAN.md §2 katman [2]: bu modül ÜÇ bağımsız gözlemden ikisini üretir (faz 0 ve
faz K) — aynı ağırlık, aynı istem, yalnız grup başlangıcı kaydırılmış
(docs/KONSEY_2026-08-20.md karar 2: ikinci bir VLM yerine faz-kaydırma; 0 ek
VRAM, determinizm bozulmadan "bedava dedektör").

Bu modül:
  * dış sözleşmeyi (``sozlesme.py``) BİLMEZ — kendi istisnalarını atar,
    ``Cikti``'ya çeviriyi ``main.py`` yapar;
  * bölüm (giriş/çıkış) mantığı TAŞIMAZ — Kobe izolasyon kanunu (PLAN §1),
    yönlendirme yalnız ``main.py``'de (``tests/test_izolasyon.py`` kilitler);
  * OCR kanalını bilmez — kanalların birbirini görmemesi çapraz kanıtın ön
    şartıdır (docs/KONSEY_2026-08-20.md "Reddedilenler" §1).

**Ham cevap asla değiştirilmez.** Derleyici yalnız bir GÖRÜNÜM üretir; düşen
her satır ``elenen``'de gerekçesiyle durur, dejenerasyon zinciri SİLİNMEZ,
işaretlenir (Nash dersi: "yok etme, düşür").
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from difflib import SequenceMatcher
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

try:                                    # tests/olcum: sys.path'te src/ var
    from hazirlik import gruplar as _gruplar
except ImportError:                     # main.py: paket yolu (src.hazirlik)
    from src.hazirlik import gruplar as _gruplar


# ---------------------------------------------------------------------------
# İstisnalar — sozlesme.py İÇE AKTARILMAZ; çeviriyi main.py yapar.
# ---------------------------------------------------------------------------

class ModelHatasi(RuntimeError):
    """Model yüklenemedi / üretemedi. main.py bunu ARIZA'ya çevirir."""


class BellekHatasi(ModelHatasi):
    """CUDA OOM — bir kez yeniden denendi, yine olmadı.

    AYRI sınıf, çünkü çaresi farklı: reçete (kare_sayisi) küçültülmeli. Bunu
    kanal KENDİ BAŞINA yapmaz — reçete sessizce değişirse sonuç ölçülemez
    hale gelir (PLAN §7.5: "ölçüm yapılmadan hiçbir eşik/kanal 'iyileştirme'
    sayılmaz"). Kararı çağıran verir.
    """


# ---------------------------------------------------------------------------
# İSTEM — DEĞİŞTİRME. Ölçülmüş %91'in geldiği istem (komşu kule jordan,
# 13-klip GT yarışı). Konsey turunda structured-output/JSON önerisi bilinçli
# REDDEDİLDİ (docs/KONSEY_2026-08-20.md "Reddedilenler" §2): çıktı biçimini
# değiştirmek ölçülmüş tek dayanağı riske atar.
# ---------------------------------------------------------------------------

ISTEM = (
    "Transcribe ONLY literally visible credit text from pixels verbatim from "
    "top to bottom. Pay extreme attention to Turkish dotted i (i, İ) versus "
    "dotless ı (ı, I). Output one credit per line. Never split a name or title "
    "across multiple lines."
)

# Kanarya koşusunun ölçülmüş görsel bütçesi (17,3 GB tepe / 2,2 sn üretim).
# 720px reçetede İKİSİ DE ATIL: 720x540 = 388.800 px, iki sınırın da içinde.
# Yine de kanıta yazılır — sessizce değişirse görünür olsun.
VARSAYILAN_GORSEL = {"min_pixels": 200704, "max_pixels": 3211264}
VARSAYILAN_AYGIT = "cuda:0"

# Derleyici pencereleri — BIRLESTIRICI.md adım 1 (jordan'dan devralınan
# ölçülmüş değer). Bulanık eleme YOK: `Ahmat` ile `Ahmet` İKİ AYRI adaydır.
VARSAYILAN_TEKRAR_PENCERESI = 12

# Dejenerasyon dedektörü — KANARYA BULGUSU 1 (docs/KANARYA_BULGULARI.md).
# Eşik TAHMİN DEĞİL, ÖLÇÜM: gerçek `Yılmaz Erdoğan` zincirinde ardışık
# benzerlikler 0.759–0.873 (hepsi >= 0.75 → yakalanır); olcum/gt altındaki
# 9 gerçek GT dosyasının 851 satırında YANLIŞ POZİTİF 0 (2026-08-21 ölçümü).
DEJENERASYON_BENZERLIK = 0.75
DEJENERASYON_ZINCIR = 4


# ---------------------------------------------------------------------------
# Motor — modeli BİR KEZ yükler, kuyruğun tamamını o yüklemeyle işler.
# ---------------------------------------------------------------------------

class Motor:
    """Yüklenmiş Qwen3-VL + işlemci. Kule içinde modeli tanıyan TEK yer.

    Yükleme/çağrı yolu kanarya koşusuyla BİREBİR aynıdır (bkz. modül başlığı):
    ``AutoProcessor`` + ``Qwen3VLForConditionalGeneration``, içerik listesinde
    ``{"type": "image", "url": ...}``, ``apply_chat_template(tokenize=True)``.
    Ölçülmüş yolu "iyileştirmek" bu fazın işi değildir.
    """

    def __init__(self, model_yolu: str | Path, dtype: str = "bfloat16",
                 uretim: dict | None = None, gorsel: dict | None = None,
                 aygit: str = VARSAYILAN_AYGIT) -> None:
        self.yol = str(model_yolu)
        self.dtype = dtype
        self.uretim = dict(uretim or {})
        self.gorsel = dict(gorsel if gorsel is not None else VARSAYILAN_GORSEL)
        self.aygit = aygit
        self.model = None
        self.islemci = None
        self.retry_sayisi = 0          # OOM sonrası yeniden deneme sayacı

    # ── yükleme ────────────────────────────────────────────────────────
    def yukle(self) -> "Motor":
        if self.model is not None:
            return self
        try:
            import torch
            from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
        except Exception as e:                          # noqa: BLE001
            raise ModelHatasi(f"transformers/torch yuklenemedi: {e}") from e

        if not Path(self.yol, "config.json").exists():
            raise ModelHatasi(f"model bulunamadi: {self.yol}/config.json yok")

        try:
            self.islemci = AutoProcessor.from_pretrained(self.yol, **self.gorsel)
            self.model = Qwen3VLForConditionalGeneration.from_pretrained(
                self.yol, dtype=getattr(torch, self.dtype), device_map=self.aygit)
            self.model.eval()
        except Exception as e:                          # noqa: BLE001
            raise self._sinifla(e) from e
        return self

    def uretim_kwargs(self) -> dict:
        """config.yaml ``uretim:`` → generate() argümanları.

        ``do_sample=False`` PLAN §7.3'ün kesin çizgisi (üretim tekrar-
        üretilebilir olmalı). Greedy'de örneklem yoktur; temperature/top_p
        yalnız uyarı üretir ve etkisizdir — düşürülür.
        """
        kw = {"do_sample": False, "max_new_tokens": 512, **self.uretim}
        if not kw.get("do_sample"):
            for a in ("temperature", "top_p", "top_k", "min_p"):
                kw.pop(a, None)
        return kw

    # ── sorma ──────────────────────────────────────────────────────────
    def sor(self, kare_yollari: list[str]) -> str:
        """Bir kare grubu → ham model cevabı (DEĞİŞTİRİLMEDEN).

        OOM olursa: önbellek boşalt + 2 sn bekle + BİR kez yeniden dene.
        Yine olmazsa ``BellekHatasi``. Daha az kareyle sessizce yeniden
        deneme YOK — reçete değişirse sonuç ölçülemez olur.
        """
        if self.model is None:
            self.yukle()

        try:
            return self._uret(kare_yollari)
        except Exception as e:                          # noqa: BLE001
            if not self._oom_mu(e):
                raise self._sinifla(e) from e
            self.bosalt()
            time.sleep(2)
            self.retry_sayisi += 1
            try:
                return self._uret(kare_yollari)
            except Exception as e2:                     # noqa: BLE001
                if self._oom_mu(e2):
                    raise BellekHatasi(
                        f"CUDA OOM: {len(kare_yollari)} kare, bir kez yeniden "
                        f"denendi, yine yetmedi — {str(e2)[:200]}") from e2
                raise self._sinifla(e2) from e2

    def _uret(self, kare_yollari: list[str]) -> str:
        import torch

        icerik = ([{"type": "image", "url": str(k)} for k in kare_yollari]
                  + [{"type": "text", "text": ISTEM}])
        girdi = self.islemci.apply_chat_template(
            [{"role": "user", "content": icerik}], tokenize=True,
            add_generation_prompt=True, return_dict=True,
            return_tensors="pt")
        dev = self.model.device if hasattr(self.model, "device") else "cuda:0"
        girdi = {k: v.to(dev) if hasattr(v, "to") else v for k, v in girdi.items()}
        with torch.inference_mode():
            cikti = self.model.generate(**girdi, **self.uretim_kwargs())
        return self.islemci.batch_decode(
            cikti[:, girdi["input_ids"].shape[1]:], skip_special_tokens=True)[0]

    # ── kapanış ────────────────────────────────────────────────────────
    def kapat(self) -> None:
        """Modeli bellekten bırak — OCR kanalı SONRA aynı GPU'yu isteyecek.

        Tek kart (PLAN §7.4): kanallar sırayla koşar, 24 GB'ta iki VLM
        aynı anda sığmaz. `del` + `empty_cache` olmadan ikinci kanal OOM alır.
        """
        self.model = None
        self.islemci = None
        self.bosalt()

    @staticmethod
    def bosalt() -> None:
        try:
            import gc

            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:                               # noqa: BLE001
            pass

    # ── hata sınıflandırma ─────────────────────────────────────────────
    @staticmethod
    def _oom_mu(e: Exception) -> bool:
        """CUDA OOM mu? Hem tip hem metin üzerinden — sürümler arası değişir."""
        try:
            import torch
            oom_tipi = getattr(torch.cuda, "OutOfMemoryError", None)
            if oom_tipi is not None and isinstance(e, oom_tipi):
                return True
        except Exception:                               # noqa: BLE001
            pass
        return "out of memory" in str(e).lower()

    @classmethod
    def _sinifla(cls, e: Exception) -> ModelHatasi:
        if isinstance(e, ModelHatasi):
            return e
        if cls._oom_mu(e):
            return BellekHatasi(str(e)[:300])
        return ModelHatasi(f"{type(e).__name__}: {str(e)[:300]}")


# ---------------------------------------------------------------------------
# Derleyici — ham cevap → satır görünümü. SIRAYLA dört kural.
# ---------------------------------------------------------------------------

_KOSELI = re.compile(r"^\[\s*(.+?)\s*\]$")


def protokol_basligi(satir: str) -> str | None:
    """KURAL 1 — ``[CREDITS]`` / ``[SUBTITLES]`` başlığı mı? Satır değildir.

    Model başlığı köşeli parantezsiz ya da bozuk yazabildiği için (jordan'da
    ölçülmüş davranış) harf-normalizasyonuyla da tanınır.
    """
    ic = satir.strip()
    koseli = _KOSELI.fullmatch(ic)
    govde = koseli.group(1) if koseli else ic
    n = re.sub(r"[^A-Z]", "", govde.upper())
    if 4 <= len(n) <= 12 and n.startswith("CRED"):
        return "credits"
    if 4 <= len(n) <= 14 and n.startswith("SUBT"):
        return "subtitles"
    return None


# KURAL 2 — modelin "burada yazı yok" BİLDİRİMİ kredi satırı DEĞİLDİR.
# KANARYA BULGUSU 2: mevcut 8B taban çizgisinde bu bildirim künye satırı
# gibi çıktıya yazılmış (gt_dizi/pastane/cikis_referans_8b.txt son satırları).
_BOS_DESENLER = (
    r"there\s+is\s+no", r"there\s+are\s+no", r"no\s+visible", r"no\s+credit\s+text",
    r"cannot\s+transcribe", r"can'?t\s+transcribe", r"unable\s+to", r"i'?m\s+sorry",
    r"the\s+images?\s+(is|are)", r"görünür.*yok", r"gorunur.*yok",
    r"metin\s+bulunam", r"yazı\s+bulunam", r"yazi\s+bulunam",
)
_BOS_BILDIRIM = re.compile("|".join(_BOS_DESENLER), re.IGNORECASE)
# Kısa "YAZI YOK" / "NO TEXT" işaretleri de bildirimdir, düzyazı değil.
_BOS_ISARET = re.compile(
    r"^(YAZI\s*YOK|NO\s*TEXT|METİN\s*YOK|METIN\s*YOK|BOŞ|BOS|EMPTY|NONE|N/?A|-+)\.?$",
    re.IGNORECASE)
_CUMLE_SONU = re.compile(r"[.!?](?:\s|$)")

_DUZYAZI_ASGARI_UZUNLUK = 80
_DUZYAZI_ASGARI_CUMLE = 2


def bos_bildirim(satir: str) -> bool:
    """KURAL 2 — satır, metnin YOKLUĞUNU bildiren bir ifade mi?

    İki yol: (a) bilinen desen listesi (EN + TR, büyük/küçük duyarsız),
    (b) 80 karakterden uzun VE en az iki cümlelik düzyazı — kredi satırı
    böyle görünmez, model açıklaması böyle görünür.
    """
    s = satir.strip().replace("’", "'")
    if not s:
        return False
    if _BOS_ISARET.match(s) or _BOS_BILDIRIM.search(s):
        return True
    return (len(s) > _DUZYAZI_ASGARI_UZUNLUK
            and len(_CUMLE_SONU.findall(s)) >= _DUZYAZI_ASGARI_CUMLE)


def imza(satir: str) -> str:
    """KURAL 3'ün imzası — yalnız boşluk/büyük-küçük farkını yok sayar.

    Diakritik KATLANMAZ: `Ahmat` ile `Ahmet` iki ayrı adaydır (BIRLESTIRICI.md
    adım 1 — bulanık eleme YOK).
    """
    return re.sub(r"\s+", " ", satir).strip().casefold()


def _benzerlik(a: str, b: str) -> float:
    return SequenceMatcher(None, imza(a), imza(b)).ratio()


def dejenerasyon_isaretle(satirlar: list[dict],
                          benzerlik: float = DEJENERASYON_BENZERLIK,
                          zincir: int = DEJENERASYON_ZINCIR) -> int:
    """KURAL 4 — mutasyon zincirini İŞARETLE (SİLME).

    KANARYA BULGUSU 1: taban çizgisi bir filmde ``Yapım Koordinatörü: Yılmaz
    Erdoğan / Yapım Direktörü: Yılmaz Erdoğan / …`` diye 10 mutasyon üretmiş;
    o isim ekranda HİÇ YOK. Ardışık ``zincir`` satırın İKİŞERLİ benzerliği
    ``benzerlik`` eşiğini geçiyorsa hepsi işaretlenir.

    Silme YOK: kararı birleştirici (Faz 3) OCR kanıtıyla birlikte verir.
    Yanlış pozitifin bedeli düşük (yalnız işaret), yanlış negatifin bedeli
    yüksek (uydurma satır kanıtsız terfi eder).
    """
    for s in satirlar:
        s.setdefault("dejenerasyon", False)
    if zincir < 2 or len(satirlar) < zincir:
        return 0
    for i in range(len(satirlar) - zincir + 1):
        blok = satirlar[i:i + zincir]
        if all(_benzerlik(a["metin"], b["metin"]) >= benzerlik
               for a, b in zip(blok, blok[1:])):
            for s in blok:
                s["dejenerasyon"] = True
    return sum(1 for s in satirlar if s["dejenerasyon"])


def _sha256_metin(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _sha256_dosya(yol: Path) -> str:
    h = hashlib.sha256()
    with yol.open("rb") as f:
        for parca in iter(lambda: f.read(1024 * 1024), b""):
            h.update(parca)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# kos() — bir faz koşusu: gruplar → model → derleyici → kanıt
# ---------------------------------------------------------------------------

def _kare_yollari(manifest, kare_dizini: str | Path, kare_indeksleri: list[int]) -> list[str]:
    """``sira`` → dosya yolu. Sözlük araması (indeks aritmetiği DEĞİL):
    kare dizini yolunda ``sira`` dosya adından gelir, ARDIŞIK OLMAYABİLİR."""
    kareler = manifest["kareler"] if isinstance(manifest, dict) else list(manifest)
    eslem = {k["sira"]: k["dosya"] for k in kareler}
    taban = Path(kare_dizini)
    return [str(taban / eslem[i]) for i in kare_indeksleri]


def _vram_tepe() -> dict:
    try:
        import torch
        if not torch.cuda.is_available():
            return {}
        return {
            "ayrilan_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
            "rezerve_gb": round(torch.cuda.max_memory_reserved() / 1e9, 2),
        }
    except Exception:                                   # noqa: BLE001
        return {}


def _vram_sifirla() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:                                   # noqa: BLE001
        pass


def kos(manifest, kare_dizini: str | Path, cfg: dict, faz: int = 0,
        motor: Motor | None = None) -> dict:
    """Bir VLM faz koşusu → ``{faz, gruplar, satirlar, elenen, kanit}``.

    ``motor`` verilirse O KULLANILIR (toplu koşuda film/faz başına yeniden
    yükleme YAPMA — 17 GB'ı iki kez okumak saçmadır); verilmezse burada
    kurulur ve koşu sonunda kapatılır.

    Bölüm (giriş/çıkış) parametresi YOKTUR ve olmayacaktır — Kobe izolasyon
    kanunu (PLAN §1); yönlendirme yalnız main.py'de.
    """
    g = cfg.get("grup", {})
    kare_sayisi = int(g.get("kare_sayisi", 8))
    bindirme = int(g.get("bindirme_kare", 1))
    pencere = int(cfg.get("derleyici", {}).get(
        "kesin_tekrar_penceresi", VARSAYILAN_TEKRAR_PENCERESI))
    if pencere < 0:
        raise ValueError("derleyici.kesin_tekrar_penceresi negatif olamaz")

    grup_listesi = _gruplar(manifest, kare_sayisi, bindirme, faz)

    m = cfg.get("model", {})
    kendi_motorumuz = motor is None
    if kendi_motorumuz:
        motor = Motor(m.get("yol", "model/qwen3-vl-8b"),
                      dtype=str(m.get("dtype", "bfloat16")),
                      uretim=cfg.get("uretim", {}),
                      gorsel=cfg.get("gorsel", VARSAYILAN_GORSEL),
                      aygit=str(m.get("aygit", VARSAYILAN_AYGIT)))
    retry_baslangic = motor.retry_sayisi

    _vram_sifirla()
    t0 = time.time()
    grup_kanitlari: list[dict] = []
    satirlar: list[dict] = []
    elenen: list[dict] = []
    kabul: list[tuple[str, int]] = []       # (imza, grup_no) — pencere için

    try:
        for grup in grup_listesi:
            yollar = _kare_yollari(manifest, kare_dizini, grup["kare_indeksleri"])
            ham = motor.sor(yollar)
            kare_araligi = [grup["kare_indeksleri"][0], grup["kare_indeksleri"][-1]]
            grup_kanitlari.append({
                "no": grup["no"],
                "kare_araligi": kare_araligi,
                "ilk_sn": grup["ilk_sn"],
                "son_sn": grup["son_sn"],
                "kare_sayisi": len(grup["kare_indeksleri"]),
                # HAM CEVAP — asla değiştirilmez, kırpılmaz.
                "ham_metin": ham,
                "ham_sha256": _sha256_metin(ham),
            })

            bolge = "credits"       # etiketi hiç yazmayan model için varsayım
            for no, satir_ham in enumerate(ham.splitlines(), 1):
                satir = satir_ham.strip()
                if not satir:
                    continue
                ortak = {"satir_no": no, "metin": satir, "grup_no": grup["no"]}

                baslik = protokol_basligi(satir)        # KURAL 1
                if baslik:
                    bolge = baslik
                    elenen.append({**ortak, "sebep": "protokol_basligi",
                                   "bolge": baslik})
                    continue
                if bos_bildirim(satir):                 # KURAL 2
                    elenen.append({**ortak, "sebep": "bos_bildirim",
                                   "bolge": bolge})
                    continue
                if bolge == "subtitles":                # KURAL 1'in devamı
                    elenen.append({**ortak, "sebep": "altyazi", "bolge": bolge})
                    continue

                im = imza(satir)                        # KURAL 3
                eslesme = next((x for x in reversed(kabul[-pencere:])
                                if x[0] == im), None) if pencere else None
                if eslesme:
                    elenen.append({**ortak, "sebep": "kesin_tekrar",
                                   "ilk_grup": eslesme[1], "bolge": bolge})
                    continue

                kabul.append((im, grup["no"]))
                satirlar.append({
                    "metin": satir,
                    "grup_no": grup["no"],
                    "kare_araligi": list(kare_araligi),
                    "ilk_sn": grup["ilk_sn"],
                    "son_sn": grup["son_sn"],
                })
    finally:
        if kendi_motorumuz:
            motor.kapat()

    dejenere = dejenerasyon_isaretle(satirlar)          # KURAL 4 — işaretle, silme
    sure = round(time.time() - t0, 2)

    model_yolu = Path(m.get("yol", "model/qwen3-vl-8b"))
    indeks = model_yolu / "model.safetensors.index.json"
    sebep_sayaci: dict[str, int] = {}
    for e in elenen:
        sebep_sayaci[e["sebep"]] = sebep_sayaci.get(e["sebep"], 0) + 1

    kanit = {
        "kanal": "vlm",
        "faz": faz,
        "model_yolu": str(model_yolu),
        # Ağırlık sessizce değişirse GÖRÜNÜR olsun (PLAN §2 sonu).
        "model_indeks_sha256": _sha256_dosya(indeks) if indeks.is_file() else None,
        "istem_sha256": _sha256_metin(ISTEM),
        "recete": {
            "kare_sayisi": kare_sayisi,
            "bindirme_kare": bindirme,
            "kesin_tekrar_penceresi": pencere,
            "dtype": str(m.get("dtype", "bfloat16")),
            "gorsel": dict(motor.gorsel),
            "uretim": motor.uretim_kwargs(),
            "dejenerasyon_benzerlik": DEJENERASYON_BENZERLIK,
            "dejenerasyon_zincir": DEJENERASYON_ZINCIR,
        },
        "grup_sayisi": len(grup_listesi),
        "satir_sayisi": len(satirlar),
        "elenen_sayisi": len(elenen),
        "elenen_sebep": sebep_sayaci,
        "dejenerasyon_satir": dejenere,
        "sure_sn": sure,
        "vram_tepe": _vram_tepe(),
        "retry_sayisi": motor.retry_sayisi - retry_baslangic,
    }
    return {"faz": faz, "gruplar": grup_kanitlari, "satirlar": satirlar,
            "elenen": elenen, "kanit": kanit}
