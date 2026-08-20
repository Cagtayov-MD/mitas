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
import json
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


def _gorsel_ayarlari(cfg: dict) -> tuple[str, str]:
    v = cfg.get("video", {})
    suzgec = v.get("suzgec", "scale={genislik}:-2:flags=lanczos").format(
        genislik=int(v.get("genislik", 720)))
    if not re.fullmatch(r"[A-Za-z0-9=:,._\-\(\)'%* ]{1,400}", suzgec):
        raise VideoHatasi(
            f"video.suzgec izin verilmeyen karakter iceriyor: {suzgec[:80]!r}")
    bicim = str(v.get("bicim", "jpg")).lower().lstrip(".")
    if bicim not in {"jpg", "jpeg", "png"}:
        raise VideoHatasi(f"desteklenmeyen kare bicimi: {bicim}")
    return suzgec, bicim


def _gruplandir(kareler: list[dict], cfg: dict) -> list[dict]:
    g = cfg.get("grup", {})
    grup_boyu = int(g.get("kare_sayisi", 8))
    bindirme = int(g.get("bindirme_kare", 0))
    if grup_boyu <= 0:
        raise VideoHatasi("grup.kare_sayisi sifirdan buyuk olmali")
    if bindirme < 0 or bindirme >= grup_boyu:
        raise VideoHatasi("grup.bindirme_kare 0 <= bindirme < kare_sayisi olmali")

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


def parcala(video: str, hedef: Path, cfg: dict) -> list[dict]:
    """Videoyu bir kez karelere ayır ve sabit boylu multi-image grupları kur.

    Ad tarihsel uyumluluk için ``parcala`` kaldı; dönen öğeler artık mp4
    parçaları değil, zamanı ve hash'i belli kare gruplarıdır.
    """
    v = cfg.get("video", {})
    _gruplandir([], cfg)  # grup reçetesini pahalı ffmpeg çağrısından önce doğrula
    fps = float(v.get("fps", 2))
    if fps <= 0:
        raise VideoHatasi("video.fps sifirdan buyuk olmali")
    suzgec, bicim = _gorsel_ayarlari(cfg)
    # Komut LISTE formunda kurulur (shell yok); yine de config/CLI kaynakli
    # suzgec dizgisi ffmpeg'e girmeden once karakter yuzeyinden gecer —
    # bilinen filtre sozdizimi disindaki her deger acikca reddedilir.
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

    return _gruplandir(kareler, cfg)


def kare_havuzu(dizin: str, hedef: Path, cfg: dict, *, bolum: str | None = None) -> list[dict]:
    """Sheriff frame-v1 havuzunu doğrula, kule reçetesiyle hazırla ve grupla.

    Sheriff PNG'leri kaynak kanıttır. Model girdileri yine Jordan config'indeki
    ölçek/unsharp/biçim/kalite reçetesiyle tek seferde üretilir; modele video
    nesnesi değil ayrı image yolları gider.
    """
    _gruplandir([], cfg)  # grup reçetesini girdi/preprocess işinden önce doğrula
    kaynak = Path(dizin)
    manifest = kaynak / "frames.jsonl"
    try:
        satirlar = [json.loads(line) for line in manifest.read_text(
            encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as e:
        raise VideoHatasi(f"frame manifest okunamadi: {manifest}: {e}") from e
    if not satirlar:
        raise VideoHatasi("frame manifest bos")

    kaynaklar: list[Path] = []
    onceki_sira = 0
    for row in satirlar:
        if not isinstance(row, dict):
            raise VideoHatasi("frame manifest satiri nesne degil")
        ad, sira = row.get("filename"), row.get("sequence")
        if (not isinstance(ad, str) or not re.fullmatch(r"frame_[0-9]{6}\.png", ad)
                or not isinstance(sira, int) or isinstance(sira, bool)
                or sira <= onceki_sira or ad != f"frame_{sira:06d}.png"):
            raise VideoHatasi(f"frame manifest sira/dosya gecersiz: {ad!r}")
        if row.get("schema_version") != "mitas.frame/v1":
            raise VideoHatasi(f"frame schema gecersiz: {ad}")
        if bolum is not None and row.get("section") != bolum:
            raise VideoHatasi(f"frame bolumu uyusmuyor: {ad}")
        yol = kaynak / ad
        if not yol.is_file() or _sha256(yol) != row.get("sha256"):
            raise VideoHatasi(f"frame yok veya hash uyusmuyor: {yol}")
        kaynaklar.append(yol)
        onceki_sira = sira

    hedef.mkdir(parents=True, exist_ok=True)
    baglar = Path(tempfile.mkdtemp(prefix="kaynak-kareler-", dir=hedef))
    kare_dizini = Path(tempfile.mkdtemp(prefix="kareler-", dir=hedef))
    for i, yol in enumerate(kaynaklar, 1):
        (baglar / f"frame_{i:06d}.png").symlink_to(yol.resolve())

    fps = float(cfg.get("video", {}).get("fps", 2))
    if fps <= 0:
        raise VideoHatasi("video.fps sifirdan buyuk olmali")
    suzgec, bicim = _gorsel_ayarlari(cfg)
    desen = kare_dizini / f"frame_%06d.{bicim}"
    komut = ["ffmpeg", "-y", "-v", "error", "-framerate", f"{fps:g}",
             "-i", str(baglar / "frame_%06d.png"), "-vf", suzgec,
             "-fps_mode", "passthrough"]
    if bicim in {"jpg", "jpeg"}:
        komut += ["-q:v", str(int(cfg.get("video", {}).get("jpeg_kalite", 2)))]
    komut.append(str(desen))
    try:
        r = subprocess.run(komut, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise VideoHatasi(f"frame hazirlama baslatilamadi: {e}") from e
    if r.returncode != 0:
        raise VideoHatasi(f"frame hazirlama rc={r.returncode}: {r.stderr.strip()[:300]}")

    hazir = sorted(kare_dizini.glob(f"*.{bicim}"))
    if len(hazir) != len(satirlar):
        raise VideoHatasi(
            f"hazirlanan frame sayisi uyusmuyor: {len(hazir)}/{len(satirlar)}")
    kareler = []
    for row, yol in zip(satirlar, hazir):
        genislik, yukseklik = _kare_boyutu(yol)
        yerel_sn = row.get("section_time_s", row.get("source_time_s"))
        if not isinstance(yerel_sn, (int, float)) or isinstance(yerel_sn, bool):
            raise VideoHatasi(f"frame timecode gecersiz: {row.get('filename')}")
        kareler.append({
            "sira": row["sequence"], "kaynak_sn": round(float(yerel_sn), 3),
            "kaynak_video_sn": row.get("source_time_s"),
            "yol": str(yol), "dosya": yol.name, "sha256": _sha256(yol),
            "kaynak_dosya": row["filename"], "kaynak_sha256": row["sha256"],
            "genislik": genislik, "yukseklik": yukseklik,
        })
    return _gruplandir(kareler, cfg)


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
    zorunlu = ("sira", "kaynak_sn", "dosya", "sha256", "genislik", "yukseklik")
    istege_bagli = ("kaynak_video_sn", "kaynak_dosya", "kaynak_sha256")
    return ({k: kare[k] for k in zorunlu}
            | {k: kare[k] for k in istege_bagli if k in kare})


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
