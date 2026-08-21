"""FAZ 1 — kare hazırlığı: TEK görsel reçete, iki girdi yolu.

PLAN.md §2 katman [1]: girdi video ya da hazır kare dizini olabilir, ama
modele (ve OCR'a) giden kare HER İKİ yolda da aynı ölçülmüş reçeteden geçer
(Allstar/jordan/config.yaml `video.*` ile birebir — 13-klip GT yarışında
ölçülmüş ffmpeg zinciri). Frame beslemesi KANUN (PLAN §7.2): native video
hiçbir zaman modele girmez, bu modül sınırında karelere çevrilir.

İki yol, TEK filtre zinciri — **ikisi de ffmpeg**:
  * ``videodan_hazirla``        — ``fps=N,scale,unsharp`` + ``-q:v``
  * ``kare_dizininden_hazirla`` — ``scale,unsharp`` + ``-q:v`` (``fps`` filtresi
    YOK: kareler zaten ayrık, yeniden örnekleme yapılmaz)

İkinci yol neden PIL değil: ffmpeg ``unsharp=5:5:1.0`` (5x5 matris) ile PIL
``ImageFilter.UnsharpMask`` (gauss tabanlı) FARKLI algoritmalardır ve JPEG
kalite ölçekleri de aynı değildir. PIL kullanılsaydı kare dizininden gelen
filmler (havuz B'nin tamamı) videodan gelenlerden BAŞKA bir görsel reçeteyle
okunurdu — %91'lik ölçülmüş skor ise yalnız ffmpeg reçetesiyle alındı.
Komşu kulede tam bu sınıftan ölçülmüş bir bulgu var (aynı klipten farklı
kesilen kareler 43 satırın 3'ünde diakritik kaybettirdi).

Her iki yol da ``kare_manifesti.json`` (KANIT) üretir ve aynı ``gruplar`` /
``kayma_hizi`` fonksiyonlarıyla tüketilir. Bu dosya dış sözleşmeyi (vince.json
durum/sınıf alanları) BİLMEZ — ``sozlesme.py`` içe aktarılmaz; hatalar burada
tanımlı ``VideoHatasi`` ile fırlatılır, çevirisini main.py yapar.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image


class VideoHatasi(RuntimeError):
    """Kare hazırlığı patladı: ffmpeg yok/çöktü, kare dizini boş/bozuk vb."""


# ---------------------------------------------------------------------------
# Ortak yardımcılar
# ---------------------------------------------------------------------------

_KAYNAK_UZANTILARI = {".png", ".jpg", ".jpeg"}
_SAYI_DESENI = re.compile(r"(\d+)")
# ffmpeg -vf değerine giden dizge; bilinen filtre söz dizimi dışındaki her
# karakter açıkça reddedilir (config/CLI kaynaklı dizge shell'e gitmese de —
# komut LİSTE formunda kurulur — yüzey taraması jordan/okuyucu.py deseni).
_SUZGEC_DESENI = re.compile(r"[A-Za-z0-9=:,._\-()'%* ]{1,400}")


def _sha256(yol: Path) -> str:
    h = hashlib.sha256()
    with yol.open("rb") as f:
        for parca in iter(lambda: f.read(1024 * 1024), b""):
            h.update(parca)
    return h.hexdigest()


def _kare_boyutu(yol: Path) -> tuple[int, int]:
    try:
        with Image.open(yol) as im:
            return int(im.width), int(im.height)
    except Exception as e:                          # noqa: BLE001
        raise VideoHatasi(f"kare okunamadi ({yol.name}): {e}") from e


def _dogal_anahtar(ad: str) -> list:
    """Doğal sıralama anahtarı: 'c_2' < 'c_10' (düz metin sıralaması tersini yapardı)."""
    return [int(p) if p.isdigit() else p.lower() for p in _SAYI_DESENI.split(ad)]


def _dosyadan_mutlak_kare_no(ad: str) -> int:
    """Dosya adındaki İLK sayı dizisini mutlak kare numarası sayar (c_0007.png -> 7)."""
    eslesme = _SAYI_DESENI.search(ad)
    if not eslesme:
        raise VideoHatasi(f"dosya adinda kare numarasi bulunamadi: {ad}")
    return int(eslesme.group(1))


def _kare_ayarlari(cfg: dict) -> tuple[float, int, str, str, int]:
    """``config.yaml``'daki ``kare.*`` bloğunu okur ve doğrular.

    Hem video hem kare-dizini yolu AYNI kaynaktan (fps, genislik, suzgec)
    okur — tek görsel reçete iki girdi yolunda da aynı sayılardan türer.
    """
    k = cfg.get("kare", {})
    fps = float(k.get("fps", 2))
    if fps <= 0:
        raise VideoHatasi("kare.fps sifirdan buyuk olmali")
    genislik = int(k.get("genislik", 720))
    if genislik <= 0:
        raise VideoHatasi("kare.genislik sifirdan buyuk olmali")
    suzgec_ham = str(k.get("suzgec", "scale={genislik}:-2:flags=lanczos"))
    try:
        suzgec = suzgec_ham.format(genislik=genislik)
    except (KeyError, IndexError) as e:
        raise VideoHatasi(f"kare.suzgec sablonu gecersiz: {suzgec_ham!r}") from e
    if not _SUZGEC_DESENI.fullmatch(suzgec):
        raise VideoHatasi(f"kare.suzgec izin verilmeyen karakter iceriyor: {suzgec[:80]!r}")
    bicim = str(k.get("bicim", "jpg")).lower().lstrip(".")
    if bicim not in {"jpg", "jpeg", "png"}:
        raise VideoHatasi(f"desteklenmeyen kare bicimi: {bicim}")
    jpeg_kalite = int(k.get("jpeg_kalite", 2))
    return fps, genislik, suzgec, bicim, jpeg_kalite


def _ffmpeg_calistir(komut: list[str], baslik: str) -> None:
    """ffmpeg'i LİSTE formunda (shell yok) çalıştırır; her hatayı VideoHatasi'na çevirir."""
    try:
        sonuc = subprocess.run(komut, capture_output=True, text=True, timeout=1800)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise VideoHatasi(f"{baslik} baslatilamadi: {e}") from e
    if sonuc.returncode != 0:
        raise VideoHatasi(
            f"{baslik} basarisiz (rc={sonuc.returncode}): {sonuc.stderr.strip()[:300]}")


def _manifest_olustur(kareler: list[dict], *, kare_dizini: str, fps: float,
                       fps_varsayimi: bool, kaynak: str, kaynak_yol: str) -> dict:
    return {
        "kaynak": kaynak,                  # "video" | "kare_dizini"
        "kaynak_yol": kaynak_yol,
        "kare_dizini": kare_dizini,
        "fps": fps,
        # True ise kaynak_sn config'teki fps varsayimindan turetildi — kare
        # dizininin GERCEK cekim hizi bilinmiyor. Uydurma varsayim gorunur
        # olsun diye (Nash dersi) burada acikca isaretlenir.
        "fps_varsayimi": fps_varsayimi,
        "kare_sayisi": len(kareler),
        "kareler": kareler,
    }


def _manifest_yaz(cikis_dizini: Path, manifest: dict) -> Path:
    hedef = Path(cikis_dizini) / "kare_manifesti.json"
    hedef.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return hedef


def _kaynak_sn(sira: int, fps: float) -> float:
    """Zaman damgası — İKİ YOLDA DA AYNI FORMÜL (0-tabanlı).

    İlk kare her zaman 0.0'dır. Yollar arasında yarım-fps'lik bir ofset farkı
    olsaydı kare aralıkları OCR kanıt penceresini kaydırırdı (kanıt tartısı
    `s`'nin kare aralığı ± pay içinde arar — PLAN §3).
    """
    return round((sira - 1) / fps, 3)


# ---------------------------------------------------------------------------
# Yol 1 — video -> kare (ffmpeg, tek geçiş)
# ---------------------------------------------------------------------------

def videodan_hazirla(video_yolu: str | Path, cikis_dizini: str | Path, cfg: dict) -> dict:
    """Videoyu TEK ffmpeg geçişiyle karelere çevirir ve manifesti yazar.

    Komut (fps=2, genislik=720 varsayımıyla)::

        ffmpeg -y -v error -i <video> \
               -vf "fps=2,scale=720:-2:flags=lanczos,unsharp=5:5:1.0" \
               -q:v 2 <cikis>/k_%05d.jpg

    ffmpeg yoksa/çökerse ya da hiç kare üretmezse ``VideoHatasi`` fırlatılır.
    """
    video = Path(video_yolu)
    if not video.is_file():
        raise VideoHatasi(f"video bulunamadi: {video}")

    fps, _genislik, suzgec, bicim, jpeg_kalite = _kare_ayarlari(cfg)
    cikis = Path(cikis_dizini)
    cikis.mkdir(parents=True, exist_ok=True)

    komut = ["ffmpeg", "-y", "-v", "error", "-i", str(video),
             "-vf", f"fps={fps:g},{suzgec}"]
    if bicim in {"jpg", "jpeg"}:
        komut += ["-q:v", str(jpeg_kalite)]
    komut.append(str(cikis / f"k_%05d.{bicim}"))
    _ffmpeg_calistir(komut, "ffmpeg kare uretimi")

    yollar = sorted(cikis.glob(f"k_*.{bicim}"))
    if not yollar:
        raise VideoHatasi("ffmpeg hic kare uretmedi")

    kareler = []
    for i, yol in enumerate(yollar):
        genislik_px, yukseklik_px = _kare_boyutu(yol)
        sira = i + 1
        kareler.append({
            "sira": sira,
            "dosya": yol.name,
            "kaynak_sn": _kaynak_sn(sira, fps),
            "sha256": _sha256(yol),
            "genislik": genislik_px,
            "yukseklik": yukseklik_px,
        })

    manifest = _manifest_olustur(
        kareler, kare_dizini=str(cikis), fps=fps, fps_varsayimi=False,
        kaynak="video", kaynak_yol=str(video))
    _manifest_yaz(cikis, manifest)
    return manifest


# ---------------------------------------------------------------------------
# Yol 2 — kare dizini -> kare (ffmpeg, AYNI filtre zinciri, fps filtresi YOK)
# ---------------------------------------------------------------------------

def _sirali_bag_dizini(dosyalar: list[Path], uzanti: str, ust_dizin: Path) -> Path:
    """Kaynak kareleri sıfır dolgulu ARDIŞIK adlarla sembolik bağlayan geçici dizin.

    Neden glob yerine bu: ffmpeg ``-pattern_type glob`` SÖZLÜKSEL sıralar.
    Sıfır dolgusuz adlarda (``c_9.png`` < ``c_10.png`` doğal sırada, ama
    sözlükselde tersi) sıra bozulur — ve bozulduğunda kod PATLAMAZ, sessizce
    yanlış zaman damgası üretir. Ayrıca gerçek girdi yolları boşluk ve Türkçe
    karakter içeriyor (``GÜLLERİN SAVAŞI-frame``); glob metakarakterleri
    (``[``, ``?``, ``*``) bir yolda geçerse ffmpeg'in globber'ı sessizce
    eşleşmez. Kontrollü ASCII adlı bağ dizini iki riski de kapatır.
    Bağlar MUTLAK hedefe kurulur (göreli bağ = dangling sembolik bağ tuzağı).
    """
    baglar = Path(tempfile.mkdtemp(prefix="kaynak-", dir=ust_dizin))
    for i, yol in enumerate(dosyalar, 1):
        (baglar / f"s_{i:06d}{uzanti}").symlink_to(yol.resolve())
    return baglar


def kare_dizininden_hazirla(kaynak_dizini: str | Path, cikis_dizini: str | Path,
                             cfg: dict) -> dict:
    """Hazır PNG/JPG kare dizinini AYNI ffmpeg filtre zincirinden geçirir.

    Komut (genislik=720 varsayımıyla)::

        ffmpeg -y -v error -f image2 -start_number 1 -i <bag>/s_%06d.png \
               -vf "scale=720:-2:flags=lanczos,unsharp=5:5:1.0" \
               -fps_mode passthrough -q:v 2 <gecici>/o_%05d.jpg

    ``fps`` filtresi YOKTUR — kareler zaten ayrık, yeniden örnekleme yapılmaz.
    Dosya sırası ADA GÖRE DOĞAL sıralamadır (c_2 < c_10); mutlak kare numarası
    (``sira``) KAYNAK dosya adındaki sayıdan okunur, manifestte ``kaynak_dosya``
    ile birlikte tutulur (iz sürülebilirlik). Gerçek fps bilinmediği için
    ``kaynak_sn`` config'teki fps varsayımıyla hesaplanır ve manifestte
    ``fps_varsayimi: true`` diye İŞARETLENİR.
    """
    kaynak = Path(kaynak_dizini)
    if not kaynak.is_dir():
        raise VideoHatasi(f"kare dizini bulunamadi: {kaynak}")

    dosyalar = sorted(
        (p for p in kaynak.iterdir()
         if p.is_file() and p.suffix.lower() in _KAYNAK_UZANTILARI),
        key=lambda p: _dogal_anahtar(p.name),
    )
    if not dosyalar:
        raise VideoHatasi(f"kare dizininde PNG/JPG bulunamadi: {kaynak}")

    fps, _genislik, suzgec, bicim, jpeg_kalite = _kare_ayarlari(cfg)
    cikis = Path(cikis_dizini)
    cikis.mkdir(parents=True, exist_ok=True)

    # Mutlak kare numaraları ÇAKIŞMAMALI: `c_1.png` ile `c_01.jpg` aynı `sira`ya
    # düşerse çıktı dosyası sessizce üzerine yazılır — sayı kaybı görünmez olur.
    siralar = [_dosyadan_mutlak_kare_no(p.name) for p in dosyalar]
    if len(set(siralar)) != len(siralar):
        raise VideoHatasi("kare dizininde ayni mutlak kare numarasi birden fazla dosyada")

    # Karışık uzantı (png+jpg) tek image2 girdisinde okunamaz — codec bir kez
    # belirlenir. Uzantıya göre gruplayıp her grubu ayrı geçişte işleriz; global
    # sıra `sira` üzerinden korunur, çıktı adı `sira`dan türediği için gruplar
    # birbirine karışmaz.
    gruplanmis: dict[str, list[tuple[int, Path]]] = {}
    for sira, yol in zip(siralar, dosyalar):
        gruplanmis.setdefault(yol.suffix.lower(), []).append((sira, yol))

    gecici_dizinler: list[Path] = []
    kare_kayitlari: dict[int, dict] = {}
    try:
        for uzanti, oge_listesi in gruplanmis.items():
            grup_dosyalari = [yol for _s, yol in oge_listesi]
            baglar = _sirali_bag_dizini(grup_dosyalari, uzanti, cikis)
            gecici_dizinler.append(baglar)
            ham_cikis = Path(tempfile.mkdtemp(prefix="hazir-", dir=cikis))
            gecici_dizinler.append(ham_cikis)

            komut = ["ffmpeg", "-y", "-v", "error",
                     "-f", "image2", "-start_number", "1",
                     "-i", str(baglar / f"s_%06d{uzanti}"),
                     "-vf", suzgec, "-fps_mode", "passthrough"]
            if bicim in {"jpg", "jpeg"}:
                komut += ["-q:v", str(jpeg_kalite)]
            komut.append(str(ham_cikis / f"o_%05d.{bicim}"))
            _ffmpeg_calistir(komut, "ffmpeg kare hazirlama")

            uretilen = sorted(ham_cikis.glob(f"o_*.{bicim}"))
            if len(uretilen) != len(oge_listesi):
                raise VideoHatasi(
                    f"hazirlanan kare sayisi uyusmuyor ({uzanti}): "
                    f"{len(uretilen)}/{len(oge_listesi)}")

            # i'inci çıktı, o gruptaki i'inci KAYNAK dosyaya karşılık gelir.
            for (sira, kaynak_dosya), uretilen_yol in zip(oge_listesi, uretilen):
                hedef_yol = cikis / f"k_{sira:05d}.{bicim}"
                shutil.move(str(uretilen_yol), str(hedef_yol))
                genislik_px, yukseklik_px = _kare_boyutu(hedef_yol)
                kare_kayitlari[sira] = {
                    "sira": sira,
                    "dosya": hedef_yol.name,
                    "kaynak_sn": _kaynak_sn(sira, fps),
                    "sha256": _sha256(hedef_yol),
                    "genislik": genislik_px,
                    "yukseklik": yukseklik_px,
                    "kaynak_dosya": kaynak_dosya.name,
                }
    finally:
        for gecici in gecici_dizinler:
            shutil.rmtree(gecici, ignore_errors=True)

    kareler = [kare_kayitlari[s] for s in siralar]
    manifest = _manifest_olustur(
        kareler, kare_dizini=str(cikis), fps=fps, fps_varsayimi=True,
        kaynak="kare_dizini", kaynak_yol=str(kaynak))
    _manifest_yaz(cikis, manifest)
    return manifest


# ---------------------------------------------------------------------------
# Gruplama — main.py / kanal_vlm.py bu ADLARLA çağırır, değiştirme.
# ---------------------------------------------------------------------------

def gruplar(manifest: dict | list[dict], kare_sayisi: int, bindirme: int,
            faz: int = 0) -> list[dict]:
    """Kare listesini sabit boylu, bindirmeli gruplara ayırır.

    ``faz > 0`` ise başlangıç ``faz`` kare kaydırılır — ikinci (faz-kaydırmalı)
    VLM koşusu için (docs/KONSEY_2026-08-20.md karar 2). Bu penceredeki ilk
    ``faz`` kare HİÇBİR gruba girmez (o koşunun kapsamı dışında kalır — ilk
    fazın kendi koşusu zaten onları kapsar). Son grup kısa olabilir.

    ``manifest`` hem ``{"kareler": [...]}`` biçiminde tam manifest hem de
    çıplak kare listesi olarak kabul edilir (testlerde ikincisi pratik).
    """
    if kare_sayisi <= 0:
        raise ValueError("kare_sayisi sifirdan buyuk olmali")
    if bindirme < 0 or bindirme >= kare_sayisi:
        raise ValueError("bindirme 0 <= bindirme < kare_sayisi olmali")
    if faz < 0:
        raise ValueError("faz negatif olamaz")

    kareler = manifest["kareler"] if isinstance(manifest, dict) else list(manifest)
    adim = kare_sayisi - bindirme
    sonuc: list[dict] = []
    for bas in range(faz, len(kareler), adim):
        grup_kareleri = kareler[bas:bas + kare_sayisi]
        if not grup_kareleri:
            break
        sonuc.append({
            "no": len(sonuc),
            "kare_indeksleri": [k["sira"] for k in grup_kareleri],
            "ilk_sn": grup_kareleri[0]["kaynak_sn"],
            "son_sn": grup_kareleri[-1]["kaynak_sn"],
        })
        if bas + kare_sayisi >= len(kareler):
            break
    return sonuc


# ---------------------------------------------------------------------------
# Kayma hızı — yalnız KANITA yazılır, davranış değiştirmez (konsey ertelenen
# madde 4: "uyarlanabilir fps / scroll-page tespiti" — önce ölçülür).
# ---------------------------------------------------------------------------

_MAKS_DIKEY_KAYMA_PX = 60   # arama penceresi — hız icin sinirli tutuldu


def _gri_satir_profili(yol: Path) -> np.ndarray:
    """Kareyi gri tonlamaya çevirip satır ortalamasını döndürür (dikey imza)."""
    with Image.open(yol) as im:
        return np.asarray(im.convert("L"), dtype=np.float64).mean(axis=1)


def _en_iyi_dikey_kayma(onceki: np.ndarray, sonraki: np.ndarray,
                         maks: int = _MAKS_DIKEY_KAYMA_PX) -> tuple[int, float]:
    """İki satır profili arasındaki en iyi dikey kaymayı kaba SAD taramasıyla bulur.

    Döner: ``(piksel_kaymasi, kalan_fark_orani)``. ``kalan_fark_orani`` 0'a
    yakınsa kayma farkı iyi açıklamış demektir (kayan jenerik); 1'e yakınsa
    kaymanın hiçbir şeyi açıklamadığı, muhtemelen kart/sayfa değişimi.
    """
    n = min(len(onceki), len(sonraki))
    if n < 4:
        return 0, 1.0
    onceki, sonraki = onceki[:n], sonraki[:n]
    # DİKKAT: epsilon burada YOK — karşılaştırma tabanı ham (epsilonsuz) fark.
    # Epsilon karşılaştırmaya karışırsa düz/tekstürsüz karede (fark=0 her
    # kaymada) sahte bir kayma "kazanır" (0.0 < 0+epsilon oluverir). Kayma=0
    # varsayılan/öncelikli kalmalı; yalnız KESİN daha iyi bir kayma onu yener.
    sifir_fark = float(np.abs(onceki - sonraki).mean())

    en_iyi_kayma, en_iyi_fark = 0, sifir_fark
    ust_sinir = min(maks, n // 2)
    for k in range(1, ust_sinir + 1):
        # sonraki kare "yukari kaymis" varsayimiyla hizala (jenerik yukari akar)
        f_yukari = float(np.abs(onceki[k:] - sonraki[:n - k]).mean())
        if f_yukari < en_iyi_fark:
            en_iyi_fark, en_iyi_kayma = f_yukari, k
        f_asagi = float(np.abs(onceki[:n - k] - sonraki[k:]).mean())
        if f_asagi < en_iyi_fark:
            en_iyi_fark, en_iyi_kayma = f_asagi, -k

    # Epsilon YALNIZ burada, sifira bolmeyi onlemek icin.
    return en_iyi_kayma, en_iyi_fark / (sifir_fark + 1e-9)


def kayma_hizi(manifest: dict | list[dict]) -> dict:
    """Ardışık kareler arasındaki kaba dikey kaymayı ölçer.

    Basit gri satır-profili + sınırlı SAD taraması (çapraz korelasyonun ucuz
    yaklaşığı). Yalnız KANITA yazılır, hiçbir sınıflandırma/eşik kararını
    ETKİLEMEZ (konsey ertelenen madde 4).

    ÖLÇÜLMÜŞ SINIRI: düşük kontrastlı (gri-üstü-gri) kaynaklarda satır-ortalaması
    sinyali gürültüye gömülüyor ve kayan jenerik "sayfa" olarak raporlanıyor —
    güneş klibinde gözlendi, arama penceresini 250 px'e çıkarmak DÜZELTMEDİ.
    Yüksek kontrastlı kaynakta (siyah zemin/beyaz yazı) ölçüm doğru: 68 px/sn.
    Davranışa bağlı olmadığı için düzeltilmedi; Faz 5 deneyine kanıt bırakıldı.

    Döner: ``{"mod": "kayan"|"sayfa", "px_sn": <sayı>}``.
    """
    kareler = manifest["kareler"] if isinstance(manifest, dict) else list(manifest)
    kare_dizini = manifest.get("kare_dizini") if isinstance(manifest, dict) else None
    if len(kareler) < 2 or not kare_dizini:
        return {"mod": "sayfa", "px_sn": 0.0}

    taban = Path(kare_dizini)
    profiller = [_gri_satir_profili(taban / k["dosya"]) for k in kareler]

    hizlar: list[float] = []
    kalan_oranlar: list[float] = []
    for i in range(len(kareler) - 1):
        dt = kareler[i + 1]["kaynak_sn"] - kareler[i]["kaynak_sn"]
        if dt <= 0:
            continue
        kayma, kalan_oran = _en_iyi_dikey_kayma(profiller[i], profiller[i + 1])
        hizlar.append(abs(kayma) / dt)
        kalan_oranlar.append(kalan_oran)

    if not hizlar:
        return {"mod": "sayfa", "px_sn": 0.0}

    px_sn = float(np.median(hizlar))
    ortalama_kalan = float(np.mean(kalan_oranlar))
    # Kayma tutarlı biçimde farkı açıklıyorsa (dusuk kalan oran) VE sifir
    # değilse: kayan jenerik. Aksi halde (aciklanmiyor ya da hareketsiz):
    # sayfa/kart. Kaba bir ilk-gecis sezgisel esigi — kalibre edilmedi.
    mod = "kayan" if (ortalama_kalan < 0.6 and px_sn > 0.5) else "sayfa"
    return {"mod": mod, "px_sn": round(px_sn, 2)}
