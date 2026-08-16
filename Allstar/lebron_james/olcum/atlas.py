#!/usr/bin/env python
"""112-film duplikasyon "kusur dökümü" (Görev M3, MITAS_Master_Dup_Kok_Sebep_Plani_v1.md).

Amaç: `uret.py` (M2) çıktısı olan `data/master_dup/masters/<FİLM>/{metrik.json,
manifest.json}` dosyalarının TÜMÜNÜ birleştirip:
  1. zenginleştirilmiş toplu özeti `data/master_dup/veri_ozet.json`'a yazmak
     (uret.py'nin kendi çalışma-özetini GENİŞLETİR — aynı yola, per-film
     metrik+manifest alanlarıyla birleştirilmiş halde yazılır; data/ commit'lenmez),
  2. okunabilir bir Markdown dökümü (`harness/master_dup/dup_dokumu.md`) üretmek:
     dup_oran dağılımı, mod×strict_scroll_frac×boy tablosu, en kötü 15 filmin
     HİPOTEZ (H1-H4) etiketli teşhisi, hipotez->film-sayısı->fix-yönü özeti,
     kredisiz kontrol grubunun ayrı satırda özeti.
  3. en kötü 10 vaka için kanıt-kırpım PNG'leri (`data/master_dup/kanit/`).

Bu modül SALT-OKUYUCUDUR: `dup_metrik.py`, `uret.py`, `OCR-worktree/*` dosyalarına
DOKUNMAZ; yalnız onların ÇIKTILARINI (data/master_dup/masters/*) okur.

Hipotezler (plan dokümanından, H1-H4 — bkz. "Tasarım özeti"):
  H1 slit dy tahmin hatası -> bitişik dilimlerde satır tekrarı (sabit-aralıklı ofset).
  H2 ardışık-OLMAYAN kart tekrarı gardı yok -> dağınık/uzak ofsetli tekrar.
  H3 scroll koşusu statik sanılırsa -> her kare "sayfa", devasa örtüşen tekrar.
  H4 pencere yanlışsa (jenerik-dışı sahne) -> slit çığırından çıkar (canavar-boy).

Metrik (dup_metrik.py, M1) blok şartı yüzünden küçük dikiş-tekrarlarını (H1)
tek başına GÖREMEZ (bkz. plan M3 madde 2) — bu yüzden H1/H4 teşhisi için EK
sinyaller kullanılır:
  - BOY-SAĞLIĞI: beklenen_boy ~= strict_runs'taki 'R' (scroll) kare sayısı x
    havuz-çapında referans "px/kare" scroll hızı (scroll_slit bloklarının
    h/frames oranının medyanı). KIYASLANAN gerçek değer TOPLAM master
    yüksekliği DEĞİL, yalnız manifest.blocks'taki scroll_slit bloklarının
    toplam yüksekliğidir -- meşru çok-kartlı statik sayfa yüksekliği (normal
    ve duplikasyon-dışı) böylece karışıma girmez. Oran belirgin katıysa
    (>= eşik) H1/H4 şüphesi. KABA bir tahmindir (dy tek film içinden değil,
    havuzun tipik hızından çıkarılır — aksi halde tahmin döngüsel/anlamsız
    olurdu).
  - OFSET DESENİ: metrik.bloklar[].es_y1 - y1/y2 farkının (blok'un kaynak ile
    eşi arasındaki boşluk) bloklar arası değişkenliği (CV). Sabit/az değişken
    -> periyodik slit dikişi (H1). Dağınık/büyük -> uzak kart tekrarı (H2).
  - RUN SINIFLANDIRMA ÇAKIŞMASI (H3): manifest.strict_runs'ta 'R' (scroll,
    dy-kanıtlı) olan bir aralık, manifest.runs'ta (fiili kompozisyonda
    kullanılan "reading" sınıflandırıcı) aynı karelerde 'S' (statik/sayfa)
    ise -> gerçek scroll sahne "sayfa" sanılmış, örtüşen kare-kare tekrar riski.

CLI: `atlas.py` (argümansız; masters/ altını tarar). `atlas.py --v2` (Görev M4):
masters_v2/ + veri_ozet_v2.json'u tarar, dup_dokumu_v2.md + kanit_v2/ üretir
(legacy dosyalara dokunmaz -- önce/sonra karşılaştırması için ikisi de kalır).
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------- #
# Sabit yollar
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = PROJECT_ROOT / "data" / "master_dup"
MASTERS_ROOT = OUT_ROOT / "masters"
VERI_OZET_PATH = OUT_ROOT / "veri_ozet.json"
KANIT_ROOT = OUT_ROOT / "kanit"
DOKUM_PATH = Path(__file__).resolve().parent / "dup_dokumu.md"

# --v2 (Görev M4): uret.py --v2 çıktısını (masters_v2/ + veri_ozet_v2.json) tara,
# ayrı dup_dokumu_v2.md + kanit_v2/ üret -- legacy dosyalar (--v2 verilmezse
# kullanılan yollar) hiç DOKUNULMADAN kalır (önce/sonra karşılaştırma tabanı).
V2_MODE = False


def configure_v2(enabled: bool) -> None:
    global V2_MODE, MASTERS_ROOT, VERI_OZET_PATH, KANIT_ROOT, DOKUM_PATH
    V2_MODE = bool(enabled)
    MASTERS_ROOT = OUT_ROOT / ("masters_v2" if V2_MODE else "masters")
    VERI_OZET_PATH = OUT_ROOT / ("veri_ozet_v2.json" if V2_MODE else "veri_ozet.json")
    KANIT_ROOT = OUT_ROOT / ("kanit_v2" if V2_MODE else "kanit")
    DOKUM_PATH = Path(__file__).resolve().parent / ("dup_dokumu_v2.md" if V2_MODE else "dup_dokumu.md")

FPS = 1.5

# Boy-sağlığı eşikleri (kaba, plan M3 madde 2'de "kaba hesapla" olarak belirtildi)
BOY_CANAVAR_ESIK = 2.5   # beklenenin >=2.5 katı -> "canavar boy" (H4 birincil)
BOY_SUPHE_ESIK = 1.4     # beklenenin >=1.4 katı -> H1/H4 şüphesi (ikincil sinyal)

# En kötü N film / kanıt kırpım sayısı
EN_KOTU_N = 15
KANIT_N = 10
KANIT_BLOK_LIMIT = 5  # film başına en fazla kaç blok kırpılsın (en büyük alan öncelikli)


# --------------------------------------------------------------------------- #
# Veri yükleme / birleştirme
# --------------------------------------------------------------------------- #
def load_run_ozet() -> list[dict]:
    """uret.py'nin (M2) yazdığı ham çalışma özetini oku."""
    if not VERI_OZET_PATH.exists():
        return []
    data = json.loads(VERI_OZET_PATH.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return list(data.get("sonuclar", []))
    if isinstance(data, list):
        return data
    return []


def load_film_artifacts(film: str) -> tuple[dict | None, dict | None]:
    d = MASTERS_ROOT / film
    metrik = manifest = None
    mp, np_ = d / "metrik.json", d / "manifest.json"
    if mp.exists():
        try:
            metrik = json.loads(mp.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            metrik = {"status": "okuma_hatasi", "hata": str(exc)}
    if np_.exists():
        try:
            manifest = json.loads(np_.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            manifest = {"status": "okuma_hatasi", "hata": str(exc)}
    return metrik, manifest


def merge_all() -> list[dict]:
    """run_ozet (durum/hata bilgisi dahil TÜM filmler) + per-film metrik/manifest birleşimi."""
    rows = load_run_ozet()
    merged = []
    for row in rows:
        film = row.get("film")
        rec = dict(row)
        metrik, manifest = load_film_artifacts(film) if film else (None, None)
        if metrik is not None:
            rec["metrik"] = metrik
        if manifest is not None:
            manifest_copy = dict(manifest)
            prov = manifest_copy.pop("_uret_provenance", None)
            rec["manifest"] = manifest_copy
            if prov is not None:
                rec["provenance"] = prov
        merged.append(rec)
    return merged


def write_veri_ozet(merged: list[dict]) -> None:
    ok = sum(1 for r in merged if r.get("status") == "OK")
    payload = {
        "n": len(merged),
        "ok": ok,
        "hata": len(merged) - ok,
        "olusturan": "atlas.py (M3) — uret.py (M2) çalışma özetini metrik.json+manifest.json ile zenginleştirir",
        "sonuclar": merged,
    }
    VERI_OZET_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


# --------------------------------------------------------------------------- #
# İstatistik yardımcıları
# --------------------------------------------------------------------------- #
def _stat3(values: list[float]) -> dict:
    if not values:
        return {"min": None, "medyan": None, "max": None, "ortalama": None, "n": 0}
    return {
        "min": round(min(values), 4),
        "medyan": round(statistics.median(values), 4),
        "max": round(max(values), 4),
        "ortalama": round(statistics.mean(values), 4),
        "n": len(values),
    }


HIST_KENARLAR = [0.0, 0.01, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 1.01]


def histogram(values: list[float], kenarlar: list[float] = HIST_KENARLAR) -> list[tuple[str, int]]:
    kovalar = [0] * (len(kenarlar) - 1)
    for v in values:
        for i in range(len(kenarlar) - 1):
            lo, hi = kenarlar[i], kenarlar[i + 1]
            if (lo <= v < hi) or (i == len(kenarlar) - 2 and v >= lo):
                kovalar[i] += 1
                break
    etiketler = []
    for i in range(len(kenarlar) - 1):
        lo, hi = kenarlar[i], kenarlar[i + 1]
        etiketler.append(f"[{lo:.2f}, {hi:.2f})" if i < len(kenarlar) - 2 else f"[{lo:.2f}, 1.00]")
    return list(zip(etiketler, kovalar))


# --------------------------------------------------------------------------- #
# Boy-sağlığı (H1/H4 sinyali)
# --------------------------------------------------------------------------- #
def pool_scroll_rate(merged: list[dict]) -> float | None:
    """Havuz-çapında referans scroll hızı (px/kare): tüm scroll_slit bloklarının
    h/frames oranının medyanı. Tek-film içinden çıkarmak döngüsel olurdu."""
    oranlar = []
    for r in merged:
        manifest = r.get("manifest")
        if not manifest:
            continue
        for b in manifest.get("blocks", []) or []:
            if b.get("kind") == "scroll_slit" and b.get("h") and b.get("frames"):
                frames = b["frames"]
                if frames > 0:
                    oranlar.append(b["h"] / frames)
    return statistics.median(oranlar) if oranlar else None


def strict_scroll_frame_count(manifest: dict) -> int:
    toplam = 0
    for run in manifest.get("strict_runs", []) or []:
        if len(run) >= 3 and run[2] == "R":
            toplam += int(run[1]) - int(run[0]) + 1
    return toplam


def actual_scroll_height(manifest: dict) -> int:
    """Master'da fiilen yer kaplayan scroll_slit bloklarının toplam yüksekliği.

    NOT: metrik.boy[1] (TOPLAM master yüksekliği) kullanılMAZ -- o, meşru
    static-kart bloklarının yüksekliğini de içerir (çok kartlı bir filmde
    yüksek olması NORMAL, duplikasyon değildir). Yalnız scroll_slit bloklarının
    payını izole ederek karşılaştırmak, kart-ağır filmlerde sahte-pozitif
    "canavar-boy" damgasını önler (atlas.py ilk taslağında bu karışıklık test
    koşusunda yakalandı -- bkz. dry-run notu).
    """
    toplam = 0
    for b in manifest.get("blocks", []) or []:
        if b.get("kind") == "scroll_slit" and "h" in b:
            toplam += int(b["h"])
    return toplam


def boy_sagligi(rec: dict, dy_rate: float | None) -> dict:
    manifest = rec.get("manifest")
    metrik = rec.get("metrik")
    if not manifest or not metrik or not dy_rate:
        return {"gecerli": False}
    scroll_kare = strict_scroll_frame_count(manifest)
    beklenen = scroll_kare * dy_rate
    gercek_h = actual_scroll_height(manifest)
    if not beklenen or not gercek_h:
        return {
            "gecerli": False,
            "scroll_kare": scroll_kare,
            "beklenen_boy": round(beklenen, 1) if beklenen else None,
            "gercek_scroll_boy": gercek_h or 0,
        }
    oran = gercek_h / beklenen
    return {
        "gecerli": True,
        "scroll_kare": scroll_kare,
        "dy_rate_ref": round(dy_rate, 2),
        "beklenen_boy": round(beklenen, 1),
        "gercek_boy": gercek_h,  # (gercek_SCROLL_boy -- alan adı rapor uyumu için korunuyor)
        "boy_orani": round(oran, 3),
    }


# --------------------------------------------------------------------------- #
# Ofset deseni (H1 bitişik-dikiş vs H2 uzak-kart)
# --------------------------------------------------------------------------- #
# Plan sözü: "sabit-aralıklı ofsetler = slit dikişi, dağınık uzak ofsetler = kart
# tekrarı" -- birincil ayrım MAGNİTÜD'e (yakın/bitişik mi, uzak mı) dayanır, CV
# yalnız DESTEKLEYİCİ/periyodiklik notu olarak raporlanır. İlk taslak salt-CV
# kullanıyordu; dry-run testinde (çok-kart, küçük-ama-değişken ofsetli filmler)
# bunun yanlış-pozitif "dağınık" damgaladığı görüldü -- magnitüd ana sinyal
# yapılarak düzeltildi.
NEAR_GAP_MULTIPLIER = 3.0  # blok kendi span'inin bu katından küçük ofset -> "bitişik" (H1-benzeri)


def blok_ofset_deseni(bloklar: list[dict]) -> dict:
    if not bloklar:
        return {"n": 0, "desen": "blok_yok"}
    gaps = []
    yakin_n = uzak_n = 0
    for b in bloklar:
        gap = float(b["es_y1"] - b["y2"])
        span = max(1.0, float(b["y2"] - b["y1"]))
        gaps.append(gap)
        if gap <= NEAR_GAP_MULTIPLIER * span:
            yakin_n += 1
        else:
            uzak_n += 1
    ortalama = statistics.mean(gaps)
    cv = None
    if len(gaps) >= 2 and ortalama:
        cv = statistics.pstdev(gaps) / abs(ortalama)
    if yakin_n > uzak_n:
        desen = "sabit-aralikli"
    elif uzak_n > yakin_n:
        desen = "dagilmis"
    else:
        desen = "karisik"
    return {
        "n": len(gaps),
        "gaps": [round(g, 1) for g in gaps],
        "ortalama_gap": round(ortalama, 1),
        "cv": round(cv, 3) if cv is not None else None,
        "yakin_blok": yakin_n,
        "uzak_blok": uzak_n,
        "desen": desen,
    }


# --------------------------------------------------------------------------- #
# H3: run sınıflandırma çakışması (strict='R' ama reading='S')
# --------------------------------------------------------------------------- #
def h3_evidence(manifest: dict) -> list[dict]:
    runs = manifest.get("runs", []) or []
    strict = manifest.get("strict_runs", []) or []
    hits = []
    for a, b, lab in strict:
        if lab != "R":
            continue
        for c, d, lab2 in runs:
            if lab2 != "S":
                continue
            ov = min(int(b), int(d)) - max(int(a), int(c)) + 1
            if ov >= 3:
                hits.append({"strict_run": [int(a), int(b)], "reading_run": [int(c), int(d)], "ortusme_kare": ov})
    return hits


# --------------------------------------------------------------------------- #
# Hipotez atama (çok-etiketli sinyal + birincil hipotez)
# --------------------------------------------------------------------------- #
def hipotez_ata(rec: dict, dy_rate: float | None) -> dict:
    manifest = rec.get("manifest") or {}
    metrik = rec.get("metrik") or {}
    bloklar = metrik.get("bloklar", []) or []

    boy_bilgi = boy_sagligi(rec, dy_rate)
    ofset = blok_ofset_deseni(bloklar)
    h3_hits = h3_evidence(manifest) if manifest else []

    etiketler: list[str] = []
    gerekceler: list[str] = []

    boy_orani = boy_bilgi.get("boy_orani") if boy_bilgi.get("gecerli") else None
    canavar = boy_orani is not None and boy_orani >= BOY_CANAVAR_ESIK
    supheli_boy = boy_orani is not None and boy_orani >= BOY_SUPHE_ESIK

    if canavar:
        etiketler.append("H4")
        gerekceler.append(
            f"boy_orani={boy_orani} (gerçek scroll-blok boyu {boy_bilgi['gercek_boy']}px, beklenen "
            f"~{boy_bilgi['beklenen_boy']}px = {boy_bilgi['scroll_kare']} scroll-kare x "
            f"{boy_bilgi['dy_rate_ref']}px/kare havuz-medyanı) -> canavar-boy eşiğini "
            f"({BOY_CANAVAR_ESIK}x) aştı"
        )
    if h3_hits:
        etiketler.append("H3")
        ilk = h3_hits[0]
        gerekceler.append(
            f"{len(h3_hits)} run'da strict_runs='R' (dy-kanıtlı scroll) ile runs='S' "
            f"(fiili kompozisyon statik/sayfa saymış) çakışıyor -- örn strict{ilk['strict_run']} "
            f"vs reading{ilk['reading_run']} ({ilk['ortusme_kare']} kare örtüşme)"
        )
    cv_txt = f", cv={ofset['cv']}" if ofset.get("cv") is not None else ""
    if ofset["desen"] == "sabit-aralikli" and ofset["n"] > 0:
        etiketler.append("H1")
        gerekceler.append(
            f"blok ofsetleri (es_y1-y2) çoğunlukla bitişik ({ofset['yakin_blok']}/{ofset['n']} blok "
            f"kendi span'inin {NEAR_GAP_MULTIPLIER}x'inden yakın ofsetli, ort={ofset['ortalama_gap']}px{cv_txt}) "
            f"-> slit-dikişi imzası"
        )
    elif ofset["desen"] == "dagilmis" and ofset["n"] > 0:
        etiketler.append("H2")
        gerekceler.append(
            f"blok ofsetleri çoğunlukla uzak ({ofset['uzak_blok']}/{ofset['n']} blok kendi span'inin "
            f"{NEAR_GAP_MULTIPLIER}x'inden uzak ofsetli, ort={ofset['ortalama_gap']}px{cv_txt}) -> "
            f"ardışık-olmayan kart tekrarı imzası"
        )
    elif ofset["desen"] == "karisik" and ofset["n"] > 0:
        gerekceler.append(
            f"blok ofset deseni karışık ({ofset['yakin_blok']} bitişik / {ofset['uzak_blok']} uzak blok, "
            f"eşit) -- H1/H2 arasında net ayrım yok, gözle bakılmalı"
        )
    if supheli_boy and not canavar:
        etiketler.append("H1/H4-supheli")
        gerekceler.append(
            f"boy_orani={boy_orani} sınırda ({BOY_SUPHE_ESIK}x-{BOY_CANAVAR_ESIK}x arası) -- "
            f"kesin değil, gözle doğrulama önerilir"
        )
    if not etiketler:
        etiketler.append("belirsiz")
        gerekceler.append("hiçbir sinyal (boy-sağlığı/ofset-deseni/run-çakışması) net eşik aşmadı -- elle incelenmeli")

    # birincil hipotez (özet tablosu için tek-etiket): H4 > H3 > H1 > H2 > diğer
    for oncelik in ("H4", "H3", "H1", "H2"):
        if oncelik in etiketler:
            birincil = oncelik
            break
    else:
        birincil = etiketler[0]

    return {
        "etiketler": etiketler,
        "birincil": birincil,
        "gerekce": gerekceler,
        "boy_bilgi": boy_bilgi,
        "ofset": ofset,
        "h3_hits": h3_hits,
    }


# --------------------------------------------------------------------------- #
# Kanıt kırpımları (PIL): en kötü N vaka, film başına en büyük K blok
# --------------------------------------------------------------------------- #
_DEJAVU_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/opt/mitas/venvs/ocr/lib/python3.10/site-packages/cv2/qt/fonts/DejaVuSans.ttf",
]


def _font(boyut: int = 13):
    # load_default() bitmap fontu Türkçe glif setini (ı,ş,ç,ğ,ü,ö) düzgün
    # basmıyor (üst üste binen/eksik glif) -- DejaVuSans TTF tam Unicode destekli.
    for yol in _DEJAVU_CANDIDATES:
        if Path(yol).exists():
            try:
                return ImageFont.truetype(yol, boyut)
            except Exception:  # noqa: BLE001
                continue
    try:
        return ImageFont.load_default()
    except Exception:  # noqa: BLE001
        return None


KANIT_BAGLAM_PAD = 50  # px -- şerit tek başına (~25px) yorumlanamaz; çevresel bağlam eklenir


def kanit_kirp(film: str, master_png: Path, bloklar: list[dict], cikti_dir: Path, limit: int = KANIT_BLOK_LIMIT) -> list[Path]:
    if not master_png.exists() or not bloklar:
        return []
    img = Image.open(master_png).convert("RGB")
    w, h = img.size
    # en büyük alan öncelikli (kaynak taraf y2-y1 ile eş taraf ortalaması)
    siralanmis = sorted(
        enumerate(bloklar),
        key=lambda kv: (kv[1]["y2"] - kv[1]["y1"]) + (kv[1]["es_y2"] - kv[1]["es_y1"]),
        reverse=True,
    )[:limit]
    cikti_dir.mkdir(parents=True, exist_ok=True)
    yazilan = []
    fnt = _font()
    for blok_no, blok in siralanmis:
        y1, y2 = max(0, blok["y1"]), min(h, blok["y2"])
        ey1, ey2 = max(0, blok["es_y1"]), min(h, blok["es_y2"])
        if y2 <= y1 or ey2 <= ey1:
            continue
        # gerçek eşleşen şerit tek başına (~25px) yorumlanamayacak kadar ince --
        # her iki tarafa da BAĞLAM PAY'ı eklenir; asıl eşleşen bölge sarı çerçeveyle işaretlenir.
        py1, py2 = max(0, y1 - KANIT_BAGLAM_PAD), min(h, y2 + KANIT_BAGLAM_PAD)
        pey1, pey2 = max(0, ey1 - KANIT_BAGLAM_PAD), min(h, ey2 + KANIT_BAGLAM_PAD)
        crop1 = img.crop((0, py1, w, py2)).copy()
        crop2 = img.crop((0, pey1, w, pey2)).copy()
        d1, d2 = ImageDraw.Draw(crop1), ImageDraw.Draw(crop2)
        d1.rectangle([0, y1 - py1, w - 1, y2 - py1], outline=(255, 220, 0), width=2)
        d2.rectangle([0, ey1 - pey1, w - 1, ey2 - pey1], outline=(255, 220, 0), width=2)
        ayrac_h = 8
        etiket_h = 22
        toplam_h = etiket_h + crop1.height + ayrac_h + etiket_h + crop2.height
        out = Image.new("RGB", (w, toplam_h), color=(30, 30, 30))
        draw = ImageDraw.Draw(out)
        y_cursor = 0
        draw.text(
            (4, y_cursor + 2),
            f"KAYNAK y={y1}:{y2}  sim={blok.get('benzerlik')}  (sarı=eşleşen, ±{KANIT_BAGLAM_PAD}px bağlam)",
            fill=(255, 210, 90), font=fnt,
        )
        y_cursor += etiket_h
        out.paste(crop1, (0, y_cursor))
        y_cursor += crop1.height
        draw.rectangle([0, y_cursor, w, y_cursor + ayrac_h], fill=(200, 30, 30))
        y_cursor += ayrac_h
        draw.text((4, y_cursor + 2), f"ES(kopya) y={ey1}:{ey2}", fill=(120, 200, 255), font=fnt)
        y_cursor += etiket_h
        out.paste(crop2, (0, y_cursor))
        dosya = cikti_dir / f"{film}_blok{blok_no}.png"
        out.save(dosya)
        yazilan.append(dosya)
    return yazilan


# --------------------------------------------------------------------------- #
# Markdown döküm üretimi
# --------------------------------------------------------------------------- #
def _md_tablo(basliklar: list[str], satirlar: list[list[str]]) -> str:
    out = ["| " + " | ".join(basliklar) + " |", "|" + "|".join(["---"] * len(basliklar)) + "|"]
    for s in satirlar:
        out.append("| " + " | ".join(str(x) for x in s) + " |")
    return "\n".join(out)


FIX_YONU = {
    "H1": "slit dilim birleştirmede dy-doğrulamalı örtüşme kırpma (M4: bindirmeyi NCC ile hizala-kes)",
    "H2": "global kart-dHash kaydı: yeni kart önceki TÜM kartlarla ham<=eşik+maske-IoU karşılaştırılsın (M4, yalnız kart-modu)",
    "H3": "koşu sınıflandırma düzeltmesi: dy-kanıtlı koşu sayfa moduna düşemesin (M4)",
    "H4": "pencere-sağlık kapısı: beklenen-boy üst sınırı aşılırsa manifest'e size_anomaly + slit'e sınır (M4)",
    "H1/H4-supheli": "sınırda -- ek gözle doğrulama sonrası H1 veya H4 fix'ine yönlendirilebilir",
    "belirsiz": "atlas sinyalleri yetersiz -- bu vakalar elle/görsel incelenmeli (kanıt kırpımı varsa oradan başla)",
}


def build_report(merged: list[dict], dy_rate: float | None) -> tuple[str, list[dict]]:
    ok_films = [r for r in merged if r.get("status") == "OK" and r.get("metrik", {}).get("dup_oran") is not None]
    hata_films = [r for r in merged if r.get("status") != "OK"]

    dup_oranlar = [r["metrik"]["dup_oran"] for r in ok_films]
    stat = _stat3(dup_oranlar)
    hist = histogram(dup_oranlar)

    kredisiz = [r for r in ok_films if r.get("gercek_onset") == -1]
    kredili = [r for r in ok_films if r.get("gercek_onset") != -1]
    stat_kredisiz = _stat3([r["metrik"]["dup_oran"] for r in kredisiz])
    stat_kredili = _stat3([r["metrik"]["dup_oran"] for r in kredili])

    # mod x strict_scroll_frac x boy tablosu
    mod_gruplari: dict[str, list[dict]] = {}
    for r in ok_films:
        mod = (r.get("manifest") or {}).get("mode", "?")
        mod_gruplari.setdefault(mod, []).append(r)

    # hipotez ataması (yalnız en kötü EN_KOTU_N için ayrıntı; ama H1/H4 boy sinyali
    # ve H3 tüm OK filmler için hesaplanabilir -- özet tablosunda tüm havuzu kullanmak
    # için TÜM ok_films'e hipotez ata, worst-N'de ayrıntı göster)
    for r in ok_films:
        r["_hipotez"] = hipotez_ata(r, dy_rate)

    en_kotu = sorted(ok_films, key=lambda r: r["metrik"]["dup_oran"], reverse=True)[:EN_KOTU_N]

    # özet: birincil hipotez -> film sayısı, toplam/ortalama dup_oran katkısı
    hipotez_ozet: dict[str, dict] = {}
    for r in ok_films:
        h = r["_hipotez"]["birincil"]
        d = hipotez_ozet.setdefault(h, {"n": 0, "toplam_dup": 0.0})
        d["n"] += 1
        d["toplam_dup"] += r["metrik"]["dup_oran"]

    # ---- Markdown ----
    satirlar = []
    satirlar.append("# Master-PNG Duplikasyon Kusur Dökümü (Görev M3)")
    satirlar.append("")
    satirlar.append(
        "> Kaynak: `harness/master_dup/atlas.py` — `data/master_dup/masters/*/`"
        " (metrik.json + manifest.json) taranarak üretildi. Plan:"
        " `docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md` (Görev M3)."
    )
    satirlar.append("")
    satirlar.append("## 1. Genel özet")
    satirlar.append("")
    satirlar.append(f"- Toplam film (havuz): **{len(merged)}**")
    satirlar.append(f"- Başarılı (OK, metrik hesaplanmış): **{len(ok_films)}**")
    satirlar.append(f"- Başarısız/hatalı: **{len(hata_films)}**")
    if hata_films:
        satirlar.append("")
        satirlar.append("Başarısız filmler:")
        satirlar.append("")
        satirlar.append(_md_tablo(
            ["film", "status", "hata"],
            [[r.get("film", "?"), r.get("status", "?"), str(r.get("hata", ""))[:160]] for r in hata_films],
        ))
    satirlar.append("")

    satirlar.append("## 2. dup_oran dağılımı")
    satirlar.append("")
    satirlar.append(
        f"- Medyan: **{stat['medyan']}**  ·  Ortalama: **{stat['ortalama']}**  ·  Maks: **{stat['max']}**  ·  n={stat['n']}"
    )
    satirlar.append("")
    satirlar.append(_md_tablo(["dup_oran aralığı", "film sayısı"], [[etk, adet] for etk, adet in hist]))
    satirlar.append("")

    satirlar.append("## 3. Kredisiz kontrol grubu vs kredi-var küme")
    satirlar.append("")
    kredisiz_boy = [r["metrik"]["boy"][1] for r in kredisiz if r.get("metrik", {}).get("boy")]
    kredili_boy = [r["metrik"]["boy"][1] for r in kredili if r.get("metrik", {}).get("boy")]
    kredisiz_blok = [r.get("kept_blocks") for r in kredisiz if r.get("kept_blocks") is not None]
    kredili_blok = [r.get("kept_blocks") for r in kredili if r.get("kept_blocks") is not None]
    satirlar.append(
        f"- **Kredisiz** (gercek_onset=-1, son-240s pencere), n={stat_kredisiz['n']}: "
        f"dup_oran medyan={stat_kredisiz['medyan']}, ortalama={stat_kredisiz['ortalama']}, maks={stat_kredisiz['max']}  ·  "
        f"boy(H) ortalama={round(statistics.mean(kredisiz_boy), 0) if kredisiz_boy else '?'}px  ·  "
        f"kept_blocks ortalama={round(statistics.mean(kredisiz_blok), 1) if kredisiz_blok else '?'}"
    )
    satirlar.append(
        f"- **Kredi-var** (onset-15s pencere), n={stat_kredili['n']}: "
        f"dup_oran medyan={stat_kredili['medyan']}, ortalama={stat_kredili['ortalama']}, maks={stat_kredili['max']}  ·  "
        f"boy(H) ortalama={round(statistics.mean(kredili_boy), 0) if kredili_boy else '?'}px  ·  "
        f"kept_blocks ortalama={round(statistics.mean(kredili_blok), 1) if kredili_blok else '?'}"
    )
    satirlar.append(
        "- Not: kredisiz pencere (son 240s, gerçek kredi kartı YOK -- sıradan sahne) boy/blok "
        "sayısında kredili kümeden belirgin sapma gösteriyorsa, bu \"statik-kart-splitter\"ın "
        "sıradan sahne kesmelerini kart sanıp aşırı böldüğüne işaret eder (bkz. §6 -- "
        "SON_CÜCE örneği tam olarak bu grup içinde)."
    )
    satirlar.append("")

    satirlar.append("## 4. Mod x strict_scroll_frac x boy tablosu")
    satirlar.append("")
    if dy_rate:
        satirlar.append(f"(Havuz-çapında referans scroll hızı: **{round(dy_rate, 2)} px/kare** — boy-sağlığı hesabında kullanıldı.)")
    else:
        satirlar.append("(Havuz-çapında referans scroll hızı hesaplanamadı -- scroll_slit blok verisi yok/az.)")
    satirlar.append("")
    mod_satirlar = []
    for mod, grup in sorted(mod_gruplari.items(), key=lambda kv: -len(kv[1])):
        ssf = [r["manifest"].get("strict_scroll_frac") for r in grup if r["manifest"].get("strict_scroll_frac") is not None]
        boylar = [r["metrik"]["boy"][1] for r in grup if r.get("metrik", {}).get("boy")]
        dupg = [r["metrik"]["dup_oran"] for r in grup]
        canavar_n = sum(1 for r in grup if (r["_hipotez"]["boy_bilgi"].get("boy_orani") or 0) >= BOY_CANAVAR_ESIK)
        mod_satirlar.append([
            mod, len(grup),
            f"{min(ssf):.2f}/{statistics.median(ssf):.2f}/{max(ssf):.2f}" if ssf else "?",
            f"{min(boylar)}/{int(statistics.median(boylar))}/{max(boylar)}" if boylar else "?",
            round(statistics.mean(dupg), 4) if dupg else "?",
            canavar_n,
        ])
    satirlar.append(_md_tablo(
        ["mode", "film sayısı", "strict_scroll_frac min/med/max", "boy(H) min/med/max px", "ortalama dup_oran", "canavar-boy sayısı"],
        mod_satirlar,
    ))
    satirlar.append("")

    satirlar.append(f"## 5. En kötü {len(en_kotu)} film -- ayrıntı")
    satirlar.append("")
    for i, r in enumerate(en_kotu, 1):
        hip = r["_hipotez"]
        m = r["metrik"]
        man = r.get("manifest") or {}
        satirlar.append(f"### {i}. {r['film']}")
        satirlar.append("")
        satirlar.append(
            f"- dup_oran=**{m['dup_oran']}**  ·  blok_sayisi={m['blok_sayisi']}  ·  boy={m.get('boy')}  ·  "
            f"mode={man.get('mode')}  ·  strict_scroll_frac={man.get('strict_scroll_frac')}  ·  "
            f"doku_kapsami={m.get('doku_kapsami')}  ·  gercek_onset={r.get('gercek_onset')}"
        )
        satirlar.append(f"- **Hipotez(ler): {', '.join(hip['etiketler'])}** (birincil: {hip['birincil']})")
        for g in hip["gerekce"]:
            satirlar.append(f"  - {g}")
        satirlar.append("")

    satirlar.append("## 6. Boy (yükseklik) vs dup_oran -- \"canavar-boy\" tek mekanizma değil")
    satirlar.append("")
    satirlar.append(
        "Plan dokümanının kendi örneği (\"600x36695 canavarlar\") ile havuzdaki en büyük "
        "masterlar karşılaştırıldığında önemli bir ayrım ortaya çıkıyor: yüksekliğin (boy) "
        "BÜYÜK olması ile dup_oran'ın YÜKSEK olması AYNI ŞEY DEĞİL. Bir master, birbirinden "
        "FARKLI çok sayıda statik kart içerdiği için de devasa boyuta ulaşabilir -- özellikle "
        "kredisiz kontrol penceresinde (gerçek kredi kartı yerine sıradan sahne kareleri "
        "\"kart\" sanılıp aşırı bölündüğünde). Bu durumda dup_oran DÜŞÜK kalır çünkü kartlar "
        "gerçekten birbirinden farklıdır, tekrar değildir -- israf/verimsizlik olabilir ama "
        "H1-H4'ün tanımladığı \"duplikasyon\" değildir. Aşağıdaki tablo havuzdaki en yüksek 5 "
        "masterı scroll-kaynaklı / statik-kart-kaynaklı yükseklik payına ayırarak gösterir "
        "(örn. `1998-0519-1-0000-00-1_SON_CÜCE`, 600x36356, plan'ın \"36695\" örneğine neredeyse "
        "birebir denk düşüyor -- ama dup_oran'ı yalnız 0.10, çünkü boyun büyük kısmı 70+ "
        "FARKLI statik karttan geliyor, scroll'dan değil)."
    )
    satirlar.append("")
    en_buyuk = sorted(ok_films, key=lambda r: (r.get("metrik", {}).get("boy") or [0, 0])[1], reverse=True)[:5]
    buyuk_satir = []
    for r in en_buyuk:
        manifest = r.get("manifest") or {}
        metrik = r.get("metrik") or {}
        boy_h = (metrik.get("boy") or [0, 0])[1]
        scroll_h = actual_scroll_height(manifest)
        static_h = boy_h - scroll_h
        static_blok_n = sum(1 for b in manifest.get("blocks", []) or [] if b.get("kind") == "static_page" and "h" in b)
        scroll_blok_n = sum(1 for b in manifest.get("blocks", []) or [] if b.get("kind") == "scroll_slit" and "h" in b)
        buyuk_satir.append([
            r["film"], boy_h, metrik.get("dup_oran"), r.get("gercek_onset"),
            f"{scroll_h}px ({scroll_blok_n} blok)", f"{static_h}px ({static_blok_n} blok)",
        ])
    satirlar.append(_md_tablo(
        ["film", "boy(H) px", "dup_oran", "gercek_onset", "scroll-kaynaklı yükseklik", "statik-kart-kaynaklı yükseklik"],
        buyuk_satir,
    ))
    satirlar.append("")

    satirlar.append("## 7. Hipotez -> Fix Yönü Özeti")
    satirlar.append("")
    ozet_satir = []
    for h, d in sorted(hipotez_ozet.items(), key=lambda kv: -kv[1]["n"]):
        ozet_satir.append([h, d["n"], round(d["toplam_dup"], 3), FIX_YONU.get(h, "?")])
    satirlar.append(_md_tablo(["hipotez", "film sayısı", "toplam dup_oran katkısı", "önerilen fix yönü (M4)"], ozet_satir))
    satirlar.append("")

    return "\n".join(satirlar), en_kotu


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--v2", action="store_true",
        help="uret.py --v2 çıktısını tara (masters_v2/+veri_ozet_v2.json) -> "
             "dup_dokumu_v2.md + kanit_v2/ (legacy dosyalara DOKUNMAZ)",
    )
    args = ap.parse_args(argv)
    configure_v2(args.v2)

    merged = merge_all()
    if not merged:
        print(f"uret.py çalışma özeti bulunamadı ({VERI_OZET_PATH} yok/boş).")
        return 1

    dy_rate = pool_scroll_rate(merged)
    rapor_md, en_kotu = build_report(merged, dy_rate)

    # kanıt kırpımları: en kötü KANIT_N vaka
    kanit_dosyalari: list[str] = []
    for r in en_kotu[:KANIT_N]:
        film = r["film"]
        bloklar = r.get("metrik", {}).get("bloklar", [])
        master_png = MASTERS_ROOT / film / "reading_master.png"
        yazilan = kanit_kirp(film, master_png, bloklar, KANIT_ROOT)
        for p in yazilan:
            try:
                kanit_dosyalari.append(str(p.relative_to(PROJECT_ROOT)))
            except ValueError:
                kanit_dosyalari.append(str(p))

    rapor_md += "\n## 8. Kanıt kırpımları\n\n"
    if kanit_dosyalari:
        rapor_md += "\n".join(f"- `{p}`" for p in kanit_dosyalari) + "\n"
    else:
        rapor_md += "(hiçbiri üretilemedi -- en kötü vakalarda blok/master eksik olabilir)\n"

    DOKUM_PATH.write_text(rapor_md, encoding="utf-8")

    # zenginleştirilmiş veri_ozet.json (uret.py çıktısını genişletir)
    for r in merged:
        r.pop("_hipotez", None)  # rapora gömülü; ham veri dosyasında tekrar hesaplanabilir tutulur
    write_veri_ozet(merged)

    ok = sum(1 for r in merged if r.get("status") == "OK")
    print(f"-> {DOKUM_PATH}")
    print(f"-> {VERI_OZET_PATH}  ({ok}/{len(merged)} OK)")
    print(f"-> {KANIT_ROOT}  ({len(kanit_dosyalari)} kırpım)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
