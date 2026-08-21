"""FAZ 3a — OCR TANIK kanalı (PaddleOCR PP-OCRv6 det + latin PP-OCRv5 rec).

Bu kanal HAKEM DEĞİL, TANIK'tır (docs/KONSEY_2026-08-20.md, karar 1): dünya
bilgisi yoktur, pikselde ne varsa onu (bozuk da olsa) verir; hüküm vermez,
kanıt üretir. Hüküm birleştiricinin (docs/BIRLESTIRICI.md Adım 5) işidir.

Çekirdek — PaddleOCR çağrısı, model yolları, eşikler, bant birleştirme —
``scratch/kanit/ocr_recall_olcum.py``'den alındı. O betik GERÇEK koşuyla
doğrulandı (marnali %96,1 / pastane %61,0 satır-recall'ı, bkz.
docs/OLCUM_OCR_RECALL.md); burada yeniden keşfedilmedi. Betikten SAPILAN her
yer aşağıda gerekçesiyle işaretlidir (bkz. "SAPMA:" notları).

Üç aday türü (docs/BIRLESTIRICI.md Adım 3 — ÖLÇÜMLE kazanılmış kural):

    bant_guclu : yalnız guven >= min_guven kutular, dikey bantta birleşti
    bant_tum   : bantın TÜM kutuları birleşti          -> zayif_birlesim: true
    kutu       : tekil kutu

Konsey kararı 5 ("zayıf kutu birleşime girmesin") pastane'de iki sütunlu 5
GERÇEK satırı (`Hacer—SERPİL TEZCAN` gibi) kanıtsız bırakıyordu. Zayıf
birleşim artık YOK EDİLMEZ, ETİKETLENİR. Aday üretmek bedava; hüküm veren
skordur (Nash'in "yok etme, düşür" dersi, kanıt katmanında).

Bu modül BÖLÜM (giriş/çıkış) bilmez — yönlendirme yalnız main.py'de
(tests/test_izolasyon.py kilitler). Normalizasyon/benzerlik işlevleri
``olcum/puan.py``'den içe aktarılMAZ: o ölçüm katmanı, bu üretim katmanı;
davranış aynı, bağımlılık yok.

Çalışma zamanı: ``venv_ocr`` (Paddle 3.3.1 + paddleocr 3.7.0). ``venv``
(torch/transformers) DEĞİL — orada Paddle yok.
"""
from __future__ import annotations

import difflib
import gc
import hashlib
import re
import time
from functools import lru_cache
from pathlib import Path

KULE = Path(__file__).resolve().parents[1]

# Bant kuralı (docs/BIRLESTIRICI.md Adım 3): iki kutu aynı banttadır <=>
# dikey merkezleri, ikisinin ORTALAMA yüksekliğinin %60'ından az ayrışır.
BANT_ORANI = 0.60

# Çatışma penceresi (docs/BIRLESTIRICI.md Adım 4) — kasten dar: 0.75 üstü
# "aynı satırın OCR kusuru", 0.30 altı "alakasız metin". Arası = aynı yuvada
# BAŞKA içerik -> insan bakmalı (hata sınıfı ②, rol<->isim kayması).
CATISMA_ALT = 0.30
CATISMA_UST = 0.75

# Aynı bant sayılma toleransı (kare yüksekliğinin oranı olarak). 0.02 ~ 480px
# karede ~10 px — bir satır yüksekliğinin altında, komşu satırlar karışmaz.
BANT_Y_TOLERANSI = 0.02

# Kanıt penceresi payı (docs/BIRLESTIRICI.md Adım 4: `kanit.kare_payi`).
VARSAYILAN_KARE_PAYI = 8

# Aday türleri — eşitlikte tercih sırası (güçlü olan önce).
TIP_SIRASI = {"bant_guclu": 0, "kutu": 1, "bant_tum": 2}


class OcrHatasi(RuntimeError):
    """OCR tanığı patladı: paddle yok, model yüklenmedi, kare okunamadı."""


# ---------------------------------------------------------------------------
# Türkçe-duyarlı normalizasyon — ocr_recall_olcum.py ile BİREBİR aynı davranış
# (docs/KONSEY_2026-08-20.md karar 6: yalnız İ<->I değil; ş/s, ğ/g, ü/u, ö/o,
# ç/c, ı/i — eşleştirme katmanında, ÇIKTI METNİNE DOKUNMADAN).
# ---------------------------------------------------------------------------

_KUCUK = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü",
                        "Ö": "ö", "Ç": "ç", "Â": "â", "Î": "î", "Û": "û"})
_KATLA = str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o",
                        "ç": "c", "â": "a", "î": "i", "û": "u"})


@lru_cache(maxsize=200_000)
def norm(s: str, katla: bool = True, bosluksuz: bool = False) -> str:
    """Türkçe casefold + diakritik katlama (+ istenirse boşluksuz varyant).

    SAPMA (davranışsız): ölçüm betiğindeki aynı işlev ``lru_cache``'lendi —
    ``ara()`` aynı aday metnini yüzlerce kez normalize ediyor. Sonuç birebir
    aynı, yalnız tekrar hesap yok.
    """
    s = s.translate(_KUCUK).lower()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    if katla:
        s = s.translate(_KATLA)
    if bosluksuz:
        s = s.replace(" ", "")
    return s


def _oran(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def benzer(a: str, b: str) -> float:
    """İki metnin benzerliği: boşluklu ve boşluksuz varyantın EN İYİsi.

    Boşluksuz varyant, ölçülmüş hata sınıfı ④'ü (kelime ortası boşluk)
    kanıt kaybına çevirmemek için var: `SER PİL` ile `SERPİL` aynı satırdır.
    """
    return max(_oran(norm(a), norm(b)),
               _oran(norm(a, bosluksuz=True), norm(b, bosluksuz=True)))


def _ust_sinir(a1: str, b1: str, a2: str, b2: str) -> float:
    """``benzer`` için KESİN üst sınır: ratio <= 2*min(la,lb)/(la+lb).

    Arama sırasında "bu aday mevcut en iyiyi geçemez" kararını SequenceMatcher
    çalıştırmadan verir. Üst sınır olduğu için maksimumu asla kaçırmaz —
    hızlandırma, yaklaşıklama değil.
    """
    def _s(x: str, y: str) -> float:
        t = len(x) + len(y)
        return (2.0 * min(len(x), len(y)) / t) if t else 0.0
    return max(_s(a1, b1), _s(a2, b2))


# ---------------------------------------------------------------------------
# Tanık — PaddleOCR'ı BİR KEZ kurar, kare okur, GPU'yu bırakır
# ---------------------------------------------------------------------------

def _mutlak(yol: str | Path, taban: Path = KULE) -> Path:
    p = Path(yol)
    return p if p.is_absolute() else (taban / p)


def _sha256(yol: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with yol.open("rb") as f:
            for parca in iter(lambda: f.read(1024 * 1024), b""):
                h.update(parca)
        return h.hexdigest()
    except OSError:
        return None


class Tanik:
    """PaddleOCR sarmalayıcısı — model BİR KEZ kurulur, kareler tek tek okunur.

    ``model`` enjekte edilirse Paddle hiç içe aktarılmaz (testler GPU'suz
    koşsun diye). Gerçek koşuda ``config.yaml``'ın ``ocr:`` bloğu okunur;
    hiçbir eşik burada yeniden icat edilmez.
    """

    def __init__(self, cfg: dict | None = None, *, kule: Path = KULE,
                 model=None, cihaz: str = "gpu") -> None:
        o = dict((cfg or {}).get("ocr", {}))
        self.kule = Path(kule)
        self.cihaz = str(o.get("cihaz", cihaz))
        self.ayarlar = {
            "det_model": str(o.get("det_model", "PP-OCRv6_medium_det")),
            "det_model_dir": str(_mutlak(
                o.get("det_model_dir", "model/paddle/PP-OCRv6_medium_det"), self.kule)),
            "rec_model": str(o.get("rec_model", "latin_PP-OCRv5_mobile_rec")),
            "rec_model_dir": str(_mutlak(
                o.get("rec_model_dir", "model/paddle/latin_PP-OCRv5_mobile_rec"), self.kule)),
            "rec_batch": int(o.get("rec_batch", 8)),
            "det_thresh": float(o.get("det_thresh", 0.20)),
            "box_thresh": float(o.get("box_thresh", 0.45)),
            "unclip_ratio": float(o.get("unclip_ratio", 1.40)),
            "min_guven": float(o.get("min_guven", 0.80)),
        }
        self._model = model
        self._enjekte = model is not None
        self._kanit_onbellek: dict | None = None
        self.okunan_kare = 0
        self.okunan_kutu = 0

    # -- model ------------------------------------------------------------
    def _kur(self):
        """PaddleOCR çağrısı — ocr_recall_olcum.py'deki ÇAĞRININ AYNISI."""
        import os
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        try:
            from paddleocr import PaddleOCR
        except Exception as e:                                    # noqa: BLE001
            raise OcrHatasi(
                "paddleocr ice aktarilamadi — bu kanal venv_ocr ile kosar "
                f"(./venv_ocr/bin/python), venv ile degil: {e}") from e
        a = self.ayarlar
        for anahtar in ("det_model_dir", "rec_model_dir"):
            if not Path(a[anahtar]).is_dir():
                raise OcrHatasi(f"model dizini yok ({anahtar}): {a[anahtar]}")
        try:
            return PaddleOCR(
                text_detection_model_name=a["det_model"],
                text_detection_model_dir=a["det_model_dir"],
                text_recognition_model_name=a["rec_model"],
                text_recognition_model_dir=a["rec_model_dir"],
                text_recognition_batch_size=a["rec_batch"],
                use_doc_orientation_classify=False, use_doc_unwarping=False,
                use_textline_orientation=False,
                text_det_thresh=a["det_thresh"],
                text_det_box_thresh=a["box_thresh"],
                text_det_unclip_ratio=a["unclip_ratio"],
                text_rec_score_thresh=0.0,     # ELEME YOK — filtre etiket katmanında
                device=self.cihaz, enable_hpi=False,
                precision="fp32", enable_mkldnn=True)
        except Exception as e:                                    # noqa: BLE001
            raise OcrHatasi(f"PaddleOCR kurulamadi: {e}") from e

    @property
    def model(self):
        if self._model is None:
            self._model = self._kur()
        return self._model

    # -- okuma ------------------------------------------------------------
    def oku(self, kare_yolu: str | Path, kare_no: int | None = None) -> list[dict]:
        """Bir kareyi okur -> kutu listesi.

        kutu = {kare_no, metin, guven, x1, y1, x2, y2, y_orani}
        (``y_orani = y_merkez / kare_yuksekligi``)

        Görüntü cv2 ile (BGR) okunur — ölçüm betiğiyle aynı kod yolu. PIL'e
        düşülmez: JPEG çözücüler piksel düzeyinde ayrışır ve OCR çıktısını
        sessizce değiştirebilir (hazirlik.py'deki "PIL değil ffmpeg" dersinin
        aynısı).
        """
        yol = Path(kare_yolu)
        if kare_no is None:
            kare_no = _dosyadan_kare_no(yol.name)
        try:
            import cv2
        except Exception as e:                                    # noqa: BLE001
            raise OcrHatasi(f"cv2 ice aktarilamadi (venv_ocr gerekli): {e}") from e
        im = cv2.imread(str(yol), cv2.IMREAD_COLOR)
        if im is None:
            # SAPMA: ölçüm betiği okunamayan kareyi SESSİZCE atlıyordu
            # (`if im is None: continue`). Üretimde sessiz atlama = kanıtta
            # görünmeyen kayıp; burada patlar, main.py ARIZA'ya çevirir.
            raise OcrHatasi(f"kare okunamadi: {yol}")
        yukseklik = int(im.shape[0])

        try:
            sonuc = list(self.model.predict(im))
        except Exception as e:                                    # noqa: BLE001
            raise OcrHatasi(f"OCR tahmini basarisiz ({yol.name}): {e}") from e
        ham = sonuc[0].json if sonuc and hasattr(sonuc[0], "json") else {}
        res = ham.get("res", ham) if isinstance(ham, dict) else {}
        metinler = res.get("rec_texts") or []
        skorlar = res.get("rec_scores") or []
        polys = res.get("rec_polys")
        if polys is None:
            polys = res.get("dt_polys")

        kutular: list[dict] = []
        for j, m in enumerate(metinler):
            if not m or not str(m).strip():
                continue
            skor = float(skorlar[j]) if j < len(skorlar) else 0.0
            try:
                xs = [float(n[0]) for n in polys[j]]
                ys = [float(n[1]) for n in polys[j]]
            except Exception:                                     # noqa: BLE001
                continue          # köşe noktası yoksa konum kanıtı da yok
            kutular.append(_kutu(kare_no, str(m), skor, xs, ys, yukseklik))

        self.okunan_kare += 1
        self.okunan_kutu += len(kutular)
        return kutular

    # -- kanıt / kapanış ---------------------------------------------------
    def kanit(self) -> dict:
        """Model yolları + ağırlık sha256'sı + eşikler (kanıta gömülür).

        Ağırlık sessizce değişirse kanıtta GÖRÜNÜR (PLAN §2).
        """
        if self._kanit_onbellek is None:
            a = self.ayarlar
            self._kanit_onbellek = {
                "det": {"ad": a["det_model"], "dizin": a["det_model_dir"],
                        "sha256": _sha256(Path(a["det_model_dir"]) / "inference.pdiparams")},
                "rec": {"ad": a["rec_model"], "dizin": a["rec_model_dir"],
                        "sha256": _sha256(Path(a["rec_model_dir"]) / "inference.pdiparams")},
                "cihaz": self.cihaz,
                "surumler": _surumler(),
            }
        return dict(self._kanit_onbellek)

    def kapat(self) -> None:
        """Modeli bırak ve (mümkünse) GPU önbelleğini boşalt."""
        self._model = None
        self._enjekte = False
        try:
            import paddle
            if hasattr(paddle, "device") and hasattr(paddle.device, "cuda"):
                paddle.device.cuda.empty_cache()
        except Exception:                                          # noqa: BLE001
            pass
        gc.collect()

    def __enter__(self) -> "Tanik":
        return self

    def __exit__(self, *_) -> None:
        self.kapat()


def _surumler() -> dict:
    s = {}
    for ad in ("paddle", "paddleocr"):
        try:
            m = __import__(ad)
            s[ad] = getattr(m, "__version__", "?")
        except Exception:                                          # noqa: BLE001
            s[ad] = None
    return s


_SAYI = re.compile(r"(\d+)")


def _dosyadan_kare_no(ad: str) -> int:
    """`k_00007.jpg` -> 7. hazirlik.py çıktı adlandırmasıyla aynı kural."""
    e = _SAYI.search(ad)
    if not e:
        raise OcrHatasi(f"dosya adinda kare numarasi yok: {ad}")
    return int(e.group(1))


def _kutu(kare_no: int, metin: str, guven: float, xs, ys,
          kare_yuksekligi: float) -> dict:
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    yc = (y1 + y2) / 2.0
    return {"kare_no": int(kare_no), "metin": metin, "guven": float(guven),
            "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2),
            "y_orani": (yc / kare_yuksekligi) if kare_yuksekligi else 0.0}


# ---------------------------------------------------------------------------
# Adım 3 — satır adayları (bant birleştirme)
# ---------------------------------------------------------------------------

def _yc(k: dict) -> float:
    return (k["y1"] + k["y2"]) / 2.0


def _yuk(k: dict) -> float:
    return k["y2"] - k["y1"]


def _bantlara_topla(kutular: list[dict], bant_orani: float) -> list[list[dict]]:
    """Kutuları dikey bantlara toplar (ölçüm betiğindeki kuralın aynısı).

    Karşılaştırma bandın İLK üyesine (çapa) göredir, son üyeye göre değil:
    zincirleme kayma (her kutu bir öncekine yakın diye tüm ekranın tek banda
    erimesi) böyle engellenir. Ölçüm betiği de ``b[0]`` kullanıyordu.
    """
    bantlar: list[list[dict]] = []
    for k in sorted(kutular, key=lambda k: (_yc(k), k["x1"])):
        for b in bantlar:
            if abs(_yc(b[0]) - _yc(k)) < bant_orani * (_yuk(b[0]) + _yuk(k)) / 2:
                b.append(k)
                break
        else:
            bantlar.append([k])
    return bantlar


def _bant_adayi(bant: list[dict], tip: str, zayif: bool,
                kare_yuksekligi: float) -> dict:
    """Bant üyelerini x1 sırasıyla tek boşlukla birleştirir."""
    uyeler = sorted(bant, key=lambda k: k["x1"])
    x1 = min(k["x1"] for k in uyeler)
    y1 = min(k["y1"] for k in uyeler)
    x2 = max(k["x2"] for k in uyeler)
    y2 = max(k["y2"] for k in uyeler)
    # SAPMA (davranışsız): ölçüm betiği bandın y_orani'sına EN SOLDAKİ kutunun
    # değerini yazıyordu (`b[0]["y_orani"]`, x1 sıralamasından sonra). Bant
    # merkezini üyelerin ortalaması temsil eder; recall ölçümü y_orani'yi hiç
    # kullanmadığı için ölçülmüş sayılar bundan etkilenmez, ama çatışma
    # tespiti (aynı bant = |Δy_orani| < 0.02) sütun yüksekliği farkından
    # yanılmasın diye ortalama alındı.
    yc = sum(_yc(k) for k in uyeler) / len(uyeler)
    return {
        "kare_no": uyeler[0]["kare_no"],
        "metin": " ".join(k["metin"] for k in uyeler),
        "guven": min(k["guven"] for k in uyeler),   # bant güveni = EN ZAYIF üye
        "y_orani": (yc / kare_yuksekligi) if kare_yuksekligi else 0.0,
        "tip": tip,
        "zayif_birlesim": zayif,
        "kutu_sayisi": len(uyeler),
        "x1": x1, "y1": y1, "x2": x2, "y2": y2,
    }


def satir_adaylari(kutular: list[dict], kare_yuksekligi: float,
                   min_guven: float = 0.80,
                   bant_orani: float = BANT_ORANI) -> list[dict]:
    """Bir karenin kutularından ÜÇ TÜR aday üretir (BIRLESTIRICI Adım 3).

    Dönen aday::

        {kare_no, metin, guven, y_orani, tip, zayif_birlesim,
         kutu_sayisi, x1, y1, x2, y2}

    ``tip`` ∈ {bant_guclu, bant_tum, kutu}. ``guven`` bantlarda EN ZAYIF
    üyenin güvenidir (``guven_min``), tekil kutuda kutunun kendi güveni.

    Sıra bilinçlidir: önce ``bant_guclu``, sonra ``kutu``, en son ``bant_tum``
    — ``ara()`` eşitlikte listedeki ilkini tercih eder, yani güçlü kanıt
    zayıfın önüne geçer.
    """
    kutular = [k for k in kutular if str(k.get("metin", "")).strip()]
    if not kutular:
        return []

    adaylar: list[dict] = []
    guclu = [k for k in kutular if k["guven"] >= min_guven]
    for b in _bantlara_topla(guclu, bant_orani):
        adaylar.append(_bant_adayi(b, "bant_guclu", False, kare_yuksekligi))

    for k in kutular:
        adaylar.append({
            "kare_no": k["kare_no"], "metin": k["metin"], "guven": k["guven"],
            "y_orani": k["y_orani"], "tip": "kutu", "zayif_birlesim": False,
            "kutu_sayisi": 1,
            "x1": k["x1"], "y1": k["y1"], "x2": k["x2"], "y2": k["y2"],
        })

    for b in _bantlara_topla(kutular, bant_orani):
        adaylar.append(_bant_adayi(b, "bant_tum", True, kare_yuksekligi))

    return _tekille(adaylar)


def _tekille(adaylar: list[dict]) -> list[dict]:
    """Aynı karede AYNI ham metin + AYNI konum -> tek aday (en güçlü etiket).

    Tüm kutuları güçlü olan bir bantta ``bant_guclu`` ile ``bant_tum`` birebir
    aynı dizeyi üretir; tek kutuluk bant da ``kutu`` adayının kopyasıdır. Bu
    kopyalar yeni bilgi taşımaz, yalnız indeksi şişirir ve zayıf etiketli
    kopya güçlü olanın önüne geçebilir.

    Tekilleştirme HAM metin üzerindedir (normalize edilmiş değil): `ÜMİT` ile
    `UMIT` ayrı adaylardır — diakritik hakemliği (BIRLESTIRICI Adım 6/6b) tam
    bu farkı okumak zorunda. Yani bu adım aday YOK ETMEZ, kopya siler.
    """
    en_iyi: dict[tuple, dict] = {}
    sira: list[tuple] = []
    for a in adaylar:
        anahtar = (a["metin"], round(a["y_orani"], 4))
        onceki = en_iyi.get(anahtar)
        if onceki is None:
            en_iyi[anahtar] = a
            sira.append(anahtar)
        elif _tercih(a) < _tercih(onceki):
            en_iyi[anahtar] = a
    return [en_iyi[k] for k in sira]


def _tercih(a: dict) -> tuple:
    """Küçük olan tercih edilir: önce zayıf-olmayan, sonra yüksek güven, sonra tip."""
    return (1 if a.get("zayif_birlesim") else 0, -float(a.get("guven", 0.0)),
            TIP_SIRASI.get(a.get("tip", ""), 9))


# ---------------------------------------------------------------------------
# Kanıt indeksi — tüm kareler -> kare -> adaylar
# ---------------------------------------------------------------------------

def kanit_indeksi(manifest: dict | list[dict], kare_dizini: str | Path,
                  cfg: dict | None = None, tanik: "Tanik | None" = None,
                  ilerleme=None) -> dict:
    """Manifestteki her kareyi okur ve kare -> adaylar indeksini kurar.

    Dönüş::

        {"kareler": {kare_no: [aday, ...]},
         "kanit": {model yolları+sha256, eşikler, kare sayısı, süre,
                   ortalama kutu/kare, ...}}

    ``kare_no`` manifestteki ``sira``dır — ``hazirlik.gruplar()`` de grup
    ``kare_indeksleri``ni aynı ``sira``dan üretir. İkisi aynı sayı uzayında
    olmasa kanıt penceresi (``ara(..., kare_araligi, pay)``) sessizce yanlış
    kareleri tarardı.

    ``tanik`` enjekte edilirse kapatılmaz (sahibi çağırandır).
    """
    t0 = time.time()
    kareler = manifest["kareler"] if isinstance(manifest, dict) else list(manifest)
    dizin = Path(kare_dizini)
    ocfg = dict((cfg or {}).get("ocr", {}))
    min_guven = float(ocfg.get("min_guven", 0.80))

    kendi = tanik is None
    t = tanik if tanik is not None else Tanik(cfg)
    indeks: dict[int, list[dict]] = {}
    toplam_kutu = 0
    try:
        for sayac, kare in enumerate(kareler, 1):
            no = int(kare["sira"])
            yukseklik = float(kare.get("yukseklik") or 0)
            kutular = t.oku(dizin / kare["dosya"], kare_no=no)
            toplam_kutu += len(kutular)
            if not yukseklik and kutular:
                raise OcrHatasi(
                    f"manifestte kare yuksekligi yok (sira={no}) — y_orani "
                    "hesaplanamaz, konum kaniti uretilemez")
            indeks[no] = satir_adaylari(kutular, yukseklik, min_guven=min_guven)
            if ilerleme is not None:
                ilerleme(sayac, len(kareler), no, len(kutular), len(indeks[no]))
        kanit = t.kanit()
    finally:
        if kendi:
            t.kapat()

    sure = time.time() - t0
    kare_sayisi = len(kareler)
    tip_dagilimi: dict[str, int] = {}
    guvenler: list[float] = []
    for adaylar in indeks.values():
        for a in adaylar:
            tip_dagilimi[a["tip"]] = tip_dagilimi.get(a["tip"], 0) + 1
            guvenler.append(float(a["guven"]))

    kanit.update({
        "esikler": {k: v for k, v in t.ayarlar.items()
                    if k in ("det_thresh", "box_thresh", "unclip_ratio",
                             "min_guven", "rec_batch")},
        "bant_orani": BANT_ORANI,
        "kare_dizini": str(dizin),
        "kare_sayisi": kare_sayisi,
        "toplam_kutu": toplam_kutu,
        "toplam_aday": sum(len(v) for v in indeks.values()),
        "aday_tipleri": tip_dagilimi,
        "ortalama_kutu_kare": round(toplam_kutu / kare_sayisi, 2) if kare_sayisi else 0.0,
        "ortalama_guven": round(sum(guvenler) / len(guvenler), 4) if guvenler else 0.0,
        "sure_sn": round(sure, 1),
        "kare_sn": round(sure / kare_sayisi, 3) if kare_sayisi else 0.0,
    })
    if isinstance(manifest, dict):
        kanit["manifest"] = {k: manifest.get(k) for k in
                             ("kaynak", "kaynak_yol", "fps", "fps_varsayimi",
                              "kare_sayisi")}
    return {"kareler": indeks, "kanit": kanit}


def yuvarla(indeks: dict, koordinat_ondalik: int = 1) -> dict:
    """JSON'a yazmadan önce sayıları kısaltır (dosya boyutu için).

    Metinlere ve etiketlere DOKUNMAZ; yalnız koordinat/oran/güven yuvarlar.
    """
    kareler = indeks.get("kareler", {})
    yeni: dict = {}
    for no, adaylar in kareler.items():
        liste = []
        for a in adaylar:
            b = dict(a)
            for alan in ("x1", "y1", "x2", "y2"):
                if alan in b and b[alan] is not None:
                    b[alan] = round(float(b[alan]), koordinat_ondalik)
            if b.get("y_orani") is not None:
                b["y_orani"] = round(float(b["y_orani"]), 4)
            if b.get("guven") is not None:
                b["guven"] = round(float(b["guven"]), 4)
            liste.append(b)
        yeni[no] = liste
    return {"kareler": yeni, "kanit": indeks.get("kanit", {})}


# ---------------------------------------------------------------------------
# Adım 4 — arama (metin + zaman penceresi; konum kanıtı çağırana döner)
# ---------------------------------------------------------------------------

def _kare_ogeleri(kareler):
    """JSON'dan dönen dizge anahtarlarını da kabul eder (kare_no -> int)."""
    for anahtar, adaylar in kareler.items():
        try:
            yield int(anahtar), adaylar
        except (TypeError, ValueError):
            continue


def _bos_sonuc() -> dict:
    return {"ocr_skor": 0.0, "kare_no": None, "y_orani": None, "guven": None,
            "tip": None, "zayif_birlesim": False, "eslesen_metin": None}


def ara(indeks: dict, metin: str, kare_araligi, pay: int = VARSAYILAN_KARE_PAYI) -> dict:
    """Verilen kare aralığı ± pay içinde ``metin``e en iyi OCR kanıtını arar.

    Dönüş::

        {ocr_skor, kare_no, y_orani, guven, tip, zayif_birlesim, eslesen_metin}
        (+ eşleşilen bantta başka içerik varsa) {"catisma": {...}}

    Pencere DIŞINDAKİ aday kanıt sayılmaz — kanıt üçlüdür (metin + kare
    aralığı + konum). Metin eşleşmesi tek başına yeterli olsaydı, VLM'in
    yanlış role taşıdığı bir isim (hata ②) ekranın BAŞKA bir yerinde
    gerçekten bulunduğu için KESİN'e terfi ederdi (GLM'in yakaladığı sessiz
    hata, docs/BIRLESTIRICI.md Adım 4).

    Y-BANDI/Kendall konum uyumu BURADA yapılmaz: o karar bir satırın
    komşularını bilmeyi gerektirir, yani birleştiricinin işidir. Bu kanal
    ham konumu (``y_orani``) kanıt olarak döner.
    """
    kareler = indeks.get("kareler", indeks) if isinstance(indeks, dict) else {}
    if not kareler:
        return _bos_sonuc()
    try:
        a, b = int(kare_araligi[0]), int(kare_araligi[1])
    except (TypeError, ValueError, IndexError, KeyError):
        return _bos_sonuc()
    if a > b:
        a, b = b, a
    pay = max(0, int(pay))
    alt, ust = a - pay, b + pay

    q1, q2 = norm(metin), norm(metin, bosluksuz=True)
    en_skor = 0.0
    en_aday: dict | None = None
    for kare_no, adaylar in _kare_ogeleri(kareler):
        if not (alt <= kare_no <= ust):
            continue
        for aday in adaylar:
            m = str(aday.get("metin", ""))
            if not m.strip():
                continue
            b1, b2 = norm(m), norm(m, bosluksuz=True)
            if _ust_sinir(q1, b1, q2, b2) < en_skor:
                continue                     # bu aday en iyiyi GEÇEMEZ
            s = max(_oran(q1, b1), _oran(q2, b2))
            if s > en_skor or (s == en_skor and en_aday is not None
                               and _tercih(aday) < _tercih(en_aday)):
                en_skor, en_aday = s, aday

    if en_aday is None:
        return _bos_sonuc()

    sonuc = {
        "ocr_skor": round(en_skor, 4),
        "kare_no": int(en_aday["kare_no"]),
        "y_orani": en_aday.get("y_orani"),
        "guven": en_aday.get("guven"),
        "tip": en_aday.get("tip"),
        "zayif_birlesim": bool(en_aday.get("zayif_birlesim", False)),
        "eslesen_metin": en_aday.get("metin"),
    }
    catisma = _catisma_bul(kareler, metin, en_aday, en_skor)
    if catisma:
        sonuc["catisma"] = catisma
    return sonuc


def _belirtec(metin: str) -> frozenset:
    return frozenset(norm(metin).split())


def _ayni_yuva_parcasi(a: str, b: str) -> bool:
    """İki metin aynı yuvanın iki görünümü mü (biri diğerinin parçası)?

    Belirteç (kelime) kümesi altküme/üstküme ise EVET. `Hacer SERPİL TEZCAN`
    ile `SERPİL TEZCAN` aynı bandın bandı ve kutusudur — farklı içerik değil.
    Alt dize yerine belirteç kümesi kullanılır: `bant_guclu` zayıf kutuyu
    atladığı için `A C` üretirken `bant_tum` `A B C` üretir; alt dize testi
    bunları "farklı" sanıp SAHTE çatışma yazardı.
    """
    ta, tb = _belirtec(a), _belirtec(b)
    if not ta or not tb:
        return True
    return ta <= tb or tb <= ta


def _catisma_bul(kareler, metin: str, eslesen: dict, ocr_skor: float) -> dict | None:
    """Aynı yuvada BAŞKA içerik var mı? (docs/BIRLESTIRICI.md Adım 4)

    İki mekanizma — ikisi de aynı `catisma` alanını doldurur, `kaynak`
    alanıyla ayırt edilir. Birleştirici hangisine ne ağırlık vereceğine
    kendisi karar verir; bu kanal yalnız işaretler.

    1. ``rakip_aday`` — aynı kare + aynı bantta (|Δy_orani| < 0.02) FARKLI
       bir aday ve benzerliği 0.30–0.75. Şartnamenin harfi budur.
    2. ``eslesen_bant`` — eşleşmenin KENDİ metni s'den farklı ve `ocr_skor`
       0.30–0.75. PLAN §3'ün tarifi ("OCR aynı yerde FARKLI metin
       gösteriyor").

    İkincisi neden eklendi (SAPMA, gerekçeli): yalnız (1) uygulandığında
    kural pratikte ÖLÜ kalıyor. Bir bandın `bant_tum` adayı o bandın TÜM
    kutularını içerdiği için, aynı banttaki her rakip adayın belirteç kümesi
    onun altkümesidir; eşleşme çoğu zaman bu tam-bant adayına düştüğünden
    (1) hiçbir zaman ateşlenemez. Oysa hedeflenen hata (② rol<->isim kayması)
    tam olarak (2)'nin gördüğü şeydir: VLM `Kostüm EDITH HEAD` derken o
    yuvada `Kostüm EDWARD STEVENSON` yazıyorsa, eşleşmenin kendi skoru
    0.30–0.75 bandına düşer. Kuralı silmedim, ikinci mekanizmayı ekledim;
    hangisinin ateşlediği kanıtta görünür.
    """
    y = eslesen.get("y_orani")
    if ocr_skor < CATISMA_ALT or (eslesen.get("guven") or 0.0) < 0.70:
        return None

    kare_no = int(eslesen["kare_no"])
    es_metin = str(eslesen.get("metin", ""))

    hedef: list = []
    if y is not None:
        for no, adaylar in _kare_ogeleri(kareler):
            if no == kare_no:
                hedef = adaylar
                break

    en_iyi = None
    en_skor = 0.0
    for aday in hedef:
        if aday is eslesen:
            continue
        dy = aday.get("y_orani")
        if dy is None or abs(float(dy) - float(y)) >= BANT_Y_TOLERANSI:
            continue
        dm = str(aday.get("metin", ""))
        if not dm.strip() or norm(dm) == norm(es_metin):
            continue
        if _ayni_yuva_parcasi(dm, es_metin):
            continue                       # aynı yuvanın parçası — çatışma değil
        s = benzer(metin, dm)
        if CATISMA_ALT <= s <= CATISMA_UST and s > en_skor:
            en_skor = s
            en_iyi = {"kaynak": "rakip_aday", "metin": dm,
                      "benzerlik": round(s, 4), "kare_no": kare_no,
                      "y_orani": dy, "guven": aday.get("guven"),
                      "tip": aday.get("tip")}
    if en_iyi:
        return en_iyi

    if (CATISMA_ALT <= ocr_skor <= CATISMA_UST
            and norm(es_metin) != norm(metin)
            and not eslesen.get("zayif_birlesim")):
        return {"kaynak": "eslesen_bant", "metin": es_metin,
                "benzerlik": round(ocr_skor, 4), "kare_no": kare_no,
                "y_orani": y, "guven": eslesen.get("guven"),
                "tip": eslesen.get("tip")}
    return None


# ---------------------------------------------------------------------------
# Dış Çağrı & CLI köprüsü (venv -> venv_ocr izolasyonu)
# ---------------------------------------------------------------------------

def ocr_indeksi_uret(manifest: dict | list[dict] | str | Path,
                     kare_dizini: str | Path,
                     cfg: dict | None = None,
                     tanik: "Tanik | None" = None) -> dict:
    """Manifest ve kare dizininden OCR indeksini üretir.

    Geçerli Python ortamında Paddle yüklüyse (örn. venv_ocr) doğrudan çağırır;
    değilse (örn. venv) venv_ocr alt süreci başlatıp sonucu JSON olarak alır.
    """
    import json
    import subprocess
    import tempfile

    if isinstance(manifest, (str, Path)):
        manifest_data = json.loads(Path(manifest).read_text(encoding="utf-8"))
    elif isinstance(manifest, dict):
        manifest_data = manifest
    else:
        manifest_data = {"kareler": list(manifest)}

    if tanik is not None:
        return kanit_indeksi(manifest_data, kare_dizini, cfg=cfg, tanik=tanik)

    try:
        import paddleocr  # noqa: F401
        return kanit_indeksi(manifest_data, kare_dizini, cfg=cfg)
    except Exception:
        pass

    venv_ocr_py = KULE / "venv_ocr" / "bin" / "python"
    if not venv_ocr_py.is_file():
        raise OcrHatasi(f"venv_ocr python bulunamadi: {venv_ocr_py}")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fm, \
         tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fo, \
         tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fc:
        json.dump(manifest_data, fm, ensure_ascii=False)
        fm.flush()
        json.dump(cfg or {}, fc, ensure_ascii=False)
        fc.flush()
        man_tmp, out_tmp, cfg_tmp = Path(fm.name), Path(fo.name), Path(fc.name)

    try:
        cmd = [
            str(venv_ocr_py),
            str(KULE / "src" / "kanal_ocr.py"),
            "--manifest", str(man_tmp),
            "--kare-dizini", str(kare_dizini),
            "--config-json", str(cfg_tmp),
            "--cikti", str(out_tmp),
        ]
        sonuc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if sonuc.returncode != 0:
            raise OcrHatasi(f"OCR alt sureci basarisiz (rc={sonuc.returncode}): {sonuc.stderr.strip()[:400]}")
        if not out_tmp.is_file() or out_tmp.stat().st_size == 0:
            raise OcrHatasi("OCR alt sureci cikti dosyasi uretmedi")
        return json.loads(out_tmp.read_text(encoding="utf-8"))
    finally:
        man_tmp.unlink(missing_ok=True)
        out_tmp.unlink(missing_ok=True)
        cfg_tmp.unlink(missing_ok=True)


def main(argv=None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(prog="kanal_ocr", description="PaddleOCR tanik kanali CLI")
    ap.add_argument("--manifest", required=True, help="manifest json dosyasi")
    ap.add_argument("--kare-dizini", required=True, help="karelerin bulundugu dizin")
    ap.add_argument("--config-json", help="config json dosyasi")
    ap.add_argument("--cikti", help="cikti json dosyasi (yoksa stdout)")
    n = ap.parse_args(argv)

    man = json.loads(Path(n.manifest).read_text(encoding="utf-8"))
    cfg = json.loads(Path(n.config_json).read_text(encoding="utf-8")) if n.config_json else {}

    indeks = kanit_indeksi(man, Path(n.kare_dizini), cfg=cfg)
    if n.cikti:
        p = Path(n.cikti)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(indeks, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        print(json.dumps(indeks, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

