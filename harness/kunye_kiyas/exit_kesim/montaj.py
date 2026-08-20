#!/usr/bin/env python3
"""Exit-frame montaj (kontakt-sayfa) üretici.

Bir film klasöründeki `exit_%06d.png` karelerinden, her hücrede KARE NUMARASI
yazılı bir grid görsel üretir. Görsel ajan bu tek görseli okuyup jenerik-başlangıç
karesini bulur (600 kareyi tek tek okumak yerine).

Kullanım:
  montaj.py <film_dir> --coarse [--n 30]        # tüm aralığı ~n karede tara
  montaj.py <film_dir> --fine A B [--maks 48]    # [A,B] aralığını ince tara
  montaj.py <film_dir> --serit N [--yari 8]      # audit: N±yari tek satır şerit

Çıktı PNG yolu stdout'a basılır (ajan onu Read eder).
Varsayılan çıktı dizini: $SCRATCH veya /tmp/exit_montaj.
"""
import os
import re
import sys
import glob

from PIL import Image, ImageDraw, ImageFont

_FONT_YOL = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_SCRATCH = os.environ.get(
    "EXIT_MONTAJ_DIR",
    os.environ.get("SCRATCHPAD", "/tmp/exit_montaj"),
)


def _font(boyut: int):
    try:
        return ImageFont.truetype(_FONT_YOL, boyut)
    except Exception:
        return ImageFont.load_default()


def _kare_no(yol: str) -> int:
    """Dosya adının sonundaki tam sayıyı döndürür (exit_000392 -> 392)."""
    m = re.findall(r"(\d+)", os.path.basename(yol))
    return int(m[-1]) if m else -1


def kareler(film_dir: str):
    """Klasördeki tüm kareleri (yol, no) çiftleri, no'ya göre sıralı."""
    yollar = glob.glob(os.path.join(film_dir, "*.png")) + \
             glob.glob(os.path.join(film_dir, "*.jpg"))
    ciftler = [(y, _kare_no(y)) for y in yollar]
    ciftler = [c for c in ciftler if c[1] >= 0]
    ciftler.sort(key=lambda c: c[1])
    return ciftler


def _thumb(yol: str, tw: int, th: int) -> Image.Image:
    """Kareyi (tw x th) kutuya en-boy koruyarak sığdır, koyu zemine ortala."""
    kutu = Image.new("RGB", (tw, th), (18, 18, 18))
    try:
        im = Image.open(yol).convert("RGB")
    except Exception:
        d = ImageDraw.Draw(kutu)
        d.text((6, 6), "BOZUK", fill=(255, 80, 80), font=_font(14))
        return kutu
    im.thumbnail((tw, th), Image.LANCZOS)
    kutu.paste(im, ((tw - im.width) // 2, (th - im.height) // 2))
    return kutu


def montaj_uret(secili, out_yol: str, kolon: int = 6, tw: int = 240, th: int = 150):
    """secili: [(yol, no), ...] -> etiketli grid PNG yaz. Döndür: out_yol."""
    n = len(secili)
    if n == 0:
        raise SystemExit("montaj: kare yok")
    kolon = max(1, min(kolon, n))
    satir = (n + kolon - 1) // kolon
    bosl = 4
    et_h = 22  # etiket şeridi yüksekliği
    huc_w = tw + bosl
    huc_h = th + et_h + bosl
    W = kolon * huc_w + bosl
    H = satir * huc_h + bosl
    tuval = Image.new("RGB", (W, H), (0, 0, 0))
    dr = ImageDraw.Draw(tuval)
    fnt = _font(16)
    for i, (yol, no) in enumerate(secili):
        r, c = divmod(i, kolon)
        x = bosl + c * huc_w
        y = bosl + r * huc_h
        # etiket şeridi (numara)
        dr.rectangle([x, y, x + tw, y + et_h], fill=(230, 210, 0))
        dr.text((x + 5, y + 2), f"#{no}", fill=(0, 0, 0), font=fnt)
        # thumb
        tuval.paste(_thumb(yol, tw, th), (x, y + et_h))
    os.makedirs(os.path.dirname(out_yol), exist_ok=True)
    tuval.save(out_yol)
    return out_yol


def _ad(film_dir: str) -> str:
    return os.path.basename(os.path.normpath(film_dir)).replace("-exit_frames", "")


def main() -> int:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    film_dir = a[0]
    if not os.path.isdir(film_dir):
        print(f"HATA: klasör yok: {film_dir}", file=sys.stderr)
        return 2
    ks = kareler(film_dir)
    if not ks:
        print(f"HATA: kare yok: {film_dir}", file=sys.stderr)
        return 2
    ad = _ad(film_dir)
    ilk, son = ks[0][1], ks[-1][1]

    if "--coarse" in a:
        n = int(a[a.index("--n") + 1]) if "--n" in a else 30
        n = min(n, len(ks))
        adim = max(1, len(ks) // n)
        secili = ks[::adim]
        # son kareyi de dahil et (jenerik sonu görünsün)
        if secili[-1][1] != ks[-1][1]:
            secili.append(ks[-1])
        out = os.path.join(_SCRATCH, f"{ad}_coarse_{ilk}-{son}.png")
        montaj_uret(secili, out, kolon=6)
        print(out)
        print(f"# {ad}: {len(ks)} kare [{ilk}-{son}], kaba örnek {len(secili)} hücre "
              f"(adım={adim})", file=sys.stderr)
        return 0

    if "--fine" in a:
        i = a.index("--fine")
        A, B = int(a[i + 1]), int(a[i + 2])
        maks = int(a[a.index("--maks") + 1]) if "--maks" in a else 48
        pen = [c for c in ks if A <= c[1] <= B]
        if not pen:
            print(f"HATA: [{A},{B}] aralığında kare yok", file=sys.stderr)
            return 2
        if len(pen) > maks:
            adim = (len(pen) + maks - 1) // maks
            pen = pen[::adim]
        out = os.path.join(_SCRATCH, f"{ad}_fine_{A}-{B}.png")
        montaj_uret(pen, out, kolon=6)
        print(out)
        print(f"# {ad}: ince [{A}-{B}] {len(pen)} hücre", file=sys.stderr)
        return 0

    if "--serit" in a:
        i = a.index("--serit")
        N = int(a[i + 1])
        yari = int(a[a.index("--yari") + 1]) if "--yari" in a else 8
        pen = [c for c in ks if N - yari <= c[1] <= N + yari]
        if not pen:
            pen = [ks[0]]
        out = os.path.join(_SCRATCH, f"{ad}_serit_{N}.png")
        montaj_uret(pen, out, kolon=len(pen), tw=170, th=120)
        print(out)
        return 0

    print("HATA: --coarse | --fine A B | --serit N ver", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
