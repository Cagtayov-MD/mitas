"""Geçiş 1 — jenerik klibi → 2 fps kare grupları → ham kredi metni.

Jordan'ın kamuya açık girdisi yine videodur. Video bir kez, KSK model
karşılaştırmasında ölçülen ffmpeg reçetesiyle karelere çevrilir; model
hiçbir zaman native video almaz, her çağrıda ayrı görüntü listesi alır.

Derleyici yakın/fuzzy satırları ASLA birleştirmez. Yalnız normalize edilmiş
olarak birebir aynı ve yakın zamanda yinelenmiş satırı görünümden düşürür;
ham model cevabı ile düşürme kaydı ``kanit.gruplar`` içinde korunur.

Bu dosya dış sözleşmeyi BİLMEZ.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

from model import CiktiBozuk, ModelHatasi   # noqa: F401  (main.py sınıflandırır)


class VideoHatasi(RuntimeError):
    """ffmpeg patladı ya da kare havuzu üretilemedi."""


BOS_ISARET = re.compile(
    r"^(YAZI\s*YOK|NO\s*TEXT|METİN\s*YOK|TEXT\s*YOK|BOŞ|EMPTY|NONE|N/?A|-+)\.?$",
    re.I)
BOS_CUMLE = re.compile(
    r"(there\s*(is|are|'s)\s+no\s+(visible\s+)?text"
    r"|no\s+text\s+(is\s+)?(visible|present|found|shown)"
    r"|(metin|yazı|yazi)\s+(yok|bulunmuyor|görünmüyor|mevcut\s+değil))", re.I)


def bos_bildirim(satir: str) -> bool:
    """Satır, metnin YOKLUĞUNU bildiren bir ifade mi? Künye satırı değildir."""
    return bool(BOS_ISARET.match(satir) or BOS_CUMLE.search(satir))


def _sha256(yol: Path) -> str:
    h = hashlib.sha256()
    with yol.open("rb") as f:
        for parca in iter(lambda: f.read(1024 * 1024), b""):
            h.update(parca)
    return h.hexdigest()


def _kare_boyutu(yol: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(yol) as im:
            return int(im.width), int(im.height)
    except Exception as e:                          # noqa: BLE001
        raise VideoHatasi(f"kare okunamadi ({yol.name}): {e}") from e


def parcala(video: str, hedef: Path, cfg: dict) -> list[dict]:
    """Videoyu bir kez karelere ayır ve sabit boylu multi-image grupları kur.

    Ad tarihsel uyumluluk için ``parcala`` kaldı; dönen öğeler artık mp4
    parçaları değil, zamanı ve hash'i belli kare gruplarıdır.
    """
    v = cfg.get("video", {})
    g = cfg.get("grup", {})
    fps = float(v.get("fps", 2))
    grup_boyu = int(g.get("kare_sayisi", 8))
    bindirme = int(g.get("bindirme_kare", 0))
    if fps <= 0:
        raise VideoHatasi("video.fps sifirdan buyuk olmali")
    if grup_boyu <= 0:
        raise VideoHatasi("grup.kare_sayisi sifirdan buyuk olmali")
    if bindirme < 0 or bindirme >= grup_boyu:
        raise VideoHatasi("grup.bindirme_kare 0 <= bindirme < kare_sayisi olmali")

    suzgec = v.get("suzgec", "scale={genislik}:-2:flags=lanczos").format(
        genislik=int(v.get("genislik", 720)))
    # Komut LISTE formunda kurulur (shell yok); yine de config/CLI kaynakli
    # suzgec dizgisi ffmpeg'e girmeden once karakter yuzeyinden gecer —
    # bilinen filtre sozdizimi disindaki her deger acikca reddedilir.
    if not re.fullmatch(r"[A-Za-z0-9=:,._\-\(\)'%* ]{1,400}", suzgec):
        raise VideoHatasi(f"video.suzgec izin verilmeyen karakter iceriyor: {suzgec[:80]!r}")
    bicim = str(v.get("bicim", "jpg")).lower().lstrip(".")
    if bicim not in {"jpg", "jpeg", "png"}:
        raise VideoHatasi(f"desteklenmeyen kare bicimi: {bicim}")

    hedef.mkdir(parents=True, exist_ok=True)
    kare_dizini = Path(tempfile.mkdtemp(prefix="kareler-", dir=hedef))
    desen = kare_dizini / f"frame_%06d.{bicim}"
    komut = ["ffmpeg", "-y", "-v", "error", "-i", str(video),
             "-vf", f"fps={fps:g},{suzgec}"]
    if bicim in {"jpg", "jpeg"}:
        komut += ["-q:v", str(int(v.get("jpeg_kalite", 2)))]
    komut.append(str(desen))
    try:
        r = subprocess.run(komut, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise VideoHatasi(f"ffmpeg kare uretimi baslatilamadi: {e}") from e
    if r.returncode != 0:
        raise VideoHatasi(f"ffmpeg kare uretimi rc={r.returncode}: {r.stderr.strip()[:300]}")

    yollar = sorted(kare_dizini.glob(f"*.{bicim}"))
    if not yollar:
        raise VideoHatasi("hic kare uretilemedi")

    kareler = []
    for i, yol in enumerate(yollar):
        genislik, yukseklik = _kare_boyutu(yol)
        kareler.append({
            "sira": i + 1,
            "kaynak_sn": round(i / fps, 3),
            "yol": str(yol),
            "dosya": yol.name,
            "sha256": _sha256(yol),
            "genislik": genislik,
            "yukseklik": yukseklik,
        })

    gruplar, adim = [], grup_boyu - bindirme
    for bas in range(0, len(kareler), adim):
        grup_kareleri = kareler[bas:bas + grup_boyu]
        if not grup_kareleri:
            break
        gruplar.append({
            "no": len(gruplar),
            "bas_sn": grup_kareleri[0]["kaynak_sn"],
            "bit_sn": grup_kareleri[-1]["kaynak_sn"],
            "ilk_kare": grup_kareleri[0]["sira"],
            "son_kare": grup_kareleri[-1]["sira"],
            "kareler": grup_kareleri,
        })
        if bas + grup_boyu >= len(kareler):
            break
    return gruplar


def _imza(satir: str) -> str:
    """Yalnız boşluk/büyük-küçük farkını yok sayan kesin imza."""
    return re.sub(r"\s+", " ", satir).strip().casefold()


def _baslik(satir: str) -> str | None:
    """Modelin bozuk yazabildiği iki protokol başlığını tanı."""
    n = re.sub(r"[^A-Z]", "", satir.upper())
    if 4 <= len(n) <= 12 and n.startswith("CRED"):
        return "credits"
    if 4 <= len(n) <= 14 and n.startswith("SUBT"):
        return "subtitles"
    return None


def _coz(metin: str) -> tuple[list[list[str]], list[dict]]:
    """Etiketli yanıtı kredi bloklarına ayır; düşen her şeyi kaydet."""
    bloklar: list[list[str]] = []
    elenen: list[dict] = []
    simdiki: list[str] = []
    bolum = "credits"              # etiketi tamamen atlayan model için varsayım

    def bitir() -> None:
        if simdiki:
            bloklar.append(simdiki.copy())
            simdiki.clear()

    for no, ham in enumerate(metin.splitlines(), 1):
        satir = ham.strip()
        if not satir:
            bitir()
            continue
        baslik = _baslik(satir)
        if baslik:
            bitir()
            bolum = baslik
            elenen.append({"satir_no": no, "metin": satir,
                           "sebep": "protokol_basligi", "bolum": bolum})
            continue
        if bos_bildirim(satir):
            bitir()
            elenen.append({"satir_no": no, "metin": satir,
                           "sebep": "bos_bildirimi", "bolum": bolum})
            continue
        if bolum == "subtitles":
            elenen.append({"satir_no": no, "metin": satir,
                           "sebep": "altyazi", "bolum": bolum})
            continue
        simdiki.append(satir)
    bitir()
    return bloklar, elenen


def _bloklara_ayir(metin: str) -> list[list[str]]:
    """Test/dış kullanım için derlenmiş kredi blokları görünümü."""
    return _coz(metin)[0]


def _kare_kaniti(kare: dict) -> dict:
    """Silinecek scratch yolunu dışa sızdırmadan yeniden üretim künyesi."""
    return {k: kare[k] for k in (
        "sira", "kaynak_sn", "dosya", "sha256", "genislik", "yukseklik")}


def oku(motor, gruplar: list[dict], cfg: dict) -> tuple[list[dict], dict]:
    """Kare gruplarını okut, kayıpsız tanı + deterministik görünüm döndür."""
    istemler = cfg.get("istem", {})
    istem_anahtari = str(getattr(motor, "istem_anahtari", "okuma"))
    istem = istemler.get(istem_anahtari) or istemler.get("okuma", "")
    pencere = int(cfg.get("derleyici", {}).get("kesin_tekrar_penceresi", 12))
    if pencere < 0:
        raise ValueError("derleyici.kesin_tekrar_penceresi negatif olamaz")

    bloklar: list[dict] = []
    kabul: list[tuple[str, int, int]] = []       # (imza, grup no, blok no)
    grup_kanitlari: list[dict] = []
    tekrarlar: list[dict] = []
    bozuk = 0
    tekrar_modu = str(getattr(motor, "tekrar_modu", "pencere"))

    for grup in gruplar:
        kare_yollari = [k["yol"] if isinstance(k, dict) else str(k)
                        for k in grup["kareler"]]
        temel = {
            "grup": grup["no"], "bas_sn": grup["bas_sn"],
            "bit_sn": grup["bit_sn"], "ilk_kare": grup["ilk_kare"],
            "son_kare": grup["son_kare"],
            "kareler": [_kare_kaniti(k) for k in grup["kareler"]
                         if isinstance(k, dict)],
        }
        try:
            metin = motor.sor(istem, kareler=kare_yollari)
        except CiktiBozuk as e:
            bozuk += 1
            grup_kanitlari.append({**temel, "durum": "CIKTI_BOZUK",
                                   "hata": str(e)[:300]})
            continue

        ham_bloklar, elenen = _coz(metin)
        model_cagri = None
        kanit_al = getattr(motor, "son_cagri_kaniti", None)
        if callable(kanit_al):
            model_cagri = kanit_al()
        grup_kanitlari.append({
            **temel,
            "durum": "OKUNDU",
            "ham_metin": metin,
            "ham_sha256": hashlib.sha256(metin.encode("utf-8")).hexdigest(),
            "derleyicide_elenen": elenen,
            **({"model_cagri": model_cagri} if model_cagri else {}),
        })
        for satirlar in ham_bloklar:
            yeni = []
            for satir in satirlar:
                imza = _imza(satir)
                eslesme = next((x for x in reversed(kabul[-pencere:])
                                if x[0] == imza), None) if pencere else None
                if (eslesme and tekrar_modu == "ayni_grupta_yalniz_komsu"
                        and eslesme[1] == grup["no"]):
                    onceki_komsu = bool(kabul and kabul[-1][0] == imza
                                        and kabul[-1][1] == grup["no"])
                    if not onceki_komsu:
                        eslesme = None
                if eslesme:
                    tekrarlar.append({
                        "metin": satir, "tekrar_grup": grup["no"],
                        "ilk_grup": eslesme[1], "ilk_blok": eslesme[2],
                        "sebep": ("kesin_komsu_tekrar"
                                  if eslesme[1] == grup["no"] else "kesin_tekrar"),
                    })
                    continue
                yeni.append(satir)
                kabul.append((imza, grup["no"], len(bloklar) + 1))
            if yeni:
                bloklar.append({
                    "no": len(bloklar) + 1,
                    "grup": grup["no"],
                    # v1 tüketicileri için ad korunur; değer artık kare grubu no'sudur.
                    "parca": grup["no"],
                    "sn": grup["bas_sn"],
                    "bit_sn": grup["bit_sn"],
                    "ilk_kare": grup["ilk_kare"],
                    "son_kare": grup["son_kare"],
                    "satirlar": yeni,
                })

    kanit = {
        "besleme_modu": "multi_image",
        "istem_anahtari": istem_anahtari,
        "tekrar_modu": tekrar_modu,
        "grup_sayisi": len(gruplar),
        "parca_sayisi": len(gruplar),       # v1 uyumluluk
        "bozuk_grup": bozuk,
        "bozuk_parca": bozuk,               # v1 uyumluluk
        "kesin_tekrar_elenen": len(tekrarlar),
        "mukerrer_elenen": len(tekrarlar),  # v1 uyumluluk
        "kesin_tekrarlar": tekrarlar,
        "gruplar": grup_kanitlari,
        "dusunme_sizinti": getattr(motor, "sizinti", 0),
        "blok_sayisi": len(bloklar),
        "satir_sayisi": sum(len(b["satirlar"]) for b in bloklar),
    }
    if bozuk and bozuk == len(gruplar):
        raise CiktiBozuk(f"gruplarin hepsi bozuk cevap verdi ({bozuk})")
    return bloklar, kanit
