#!/usr/bin/env python3
"""Görev 3 — 31 hatanın kanıt-bazlı atlası.

GT'de karar != "dogru" olan (31) film için tespit_v5 çalıştırılır ve şunlar
markdown'a yazılır: (a) aday listesi (seri["adaylar"]); (b) gerçek-onset'in
adaylara göre konumu; (c) gt-2/gt/gt+4 karelerinde credit_content.satirlar
ilk 8 satırı; (d) gt±10 penceresinde scroll istatistiği (dy>3 & corr>=0.85
oranı + dy medyanı, tespit_v5 ile AYNI stride=2 indekslemesiyle); (e) otomatik
ön-teşhis etiketi.

Salt-okunur: figo.py / credit_content.py / credit_box.py / olc_pool.py
DEĞİŞTİRİLMEZ — yalnızca import edilip okunur. Kareleri henüz inmemiş filmler
"BEKLIYOR" bölümüne yazılır (idempotent: yeniden koşunca inmiş olanlar işlenir).

Kullanım:
  hata_atlasi.py                 # tüm 31 hata filmi (inmemiş olanlar BEKLIYOR'a)
  hata_atlasi.py --film TAKKELİ   # ad-parçası eşleşen tek film (hızlı deneme)
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

import numpy as np

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
import credit_content as cc      # noqa: E402  (salt-okunur kullanım)
import figo as co        # noqa: E402  (salt-okunur kullanım)

V = os.path.join(BURASI, "veri")
KOK = "/opt/mitas/data/jenerik_havuz/pool_frames"
PENCERE = 10            # (d) gerçek-onset ± bu kadar mutlak kare
SCROLL_ORAN_ESIK = 0.3  # Görev4 taslağıyla tutarlı "scroll-tip pencere" eşiği

# hedef görev listeleri — plandaki Görev4/5/6 hedef-film adları (norm sonrası
# eşleşme için; yalnız raporlama amaçlı, karar mantığı sapma-işaretine dayanır)
_GOREV4_ORNEK = {"MESLEĞE_DÖNÜŞ", "TAKKELİ_MELEK", "KARAVAN", "DİPTEKİLER",
                 "SAKLI_GERÇEKLER", "6", "İNİŞLİ_ÇIKIŞLI_BİR_ÖYK", "GELECEK_GÜNLER"}
_GOREV5_ORNEK = {"YALNIZ_SAVAŞÇI", "HARİKA_KÖPEK_5", "İKİ_KAFADAR", "KIZIL_HAYAT",
                 "TESS", "POTEMKİN_ZIRHLISI", "KNUTE_ROICKNE", "YÜREKTEN_SEVMEK",
                 "MEVLANA_AŞKIN_DANSI"}
_GOREV6_ORNEK = {"DERSU_UZALA", "DOĞUM_GÜNÜN_KUTLU_OLSUN_MAR", "VANYA_DAYI",
                 "ÖLDÜRME_ZAMANI", "MELEKLERİ_GÖRMEK_İSTEDİM", "SEN_TOM_SAWYER_DEĞİLSİN",
                 "KÜÇÜK_SİMBA_DÜNYA_KUPASIN", "ROBOCOP_KARA_ADALET", "TAKTİKLER_SAVAŞI",
                 "KANDAHAR", "ARKADAŞIMIN_EVİ_NEREDE"}


def norm(s: str) -> str:
    return s.replace("’", "'").split(" (")[0].strip()


def kisa_ad(ad: str) -> str:
    """Dosya-adı öneki (tarih/kod) atılmış kısa film adı — hedef-liste eşleşmesi için."""
    parcalar = ad.split("_", 1)
    if len(parcalar) == 2 and "-" in parcalar[0]:
        return parcalar[1]
    return ad


# ── (b) konum ────────────────────────────────────────────────────────────
def iceren_aday(gt: int, adaylar: list[dict]) -> dict | None:
    for ad in adaylar:
        if ad["kare_a"] <= gt <= ad["kare_b"]:
            return ad
    return None


def konum_yaz(gt: int, adaylar: list[dict]) -> str:
    if not adaylar:
        return "adaysız bölgede (hiç kutu-koşusu yok)"
    for i, ad in enumerate(adaylar):
        if ad["kare_a"] <= gt <= ad["kare_b"]:
            return (f"aday {i} İÇİNDE [{ad['kare_a']}-{ad['kare_b']}] "
                    f"(son_ok={ad['son_ok']}, kb={ad['kb']})")
    if gt < adaylar[0]["kare_a"]:
        return f"İLK adaydan ÖNCE (aday0 başlangıcı={adaylar[0]['kare_a']})"
    if gt > adaylar[-1]["kare_b"]:
        return f"SON adaydan SONRA (aday{len(adaylar) - 1} bitişi={adaylar[-1]['kare_b']})"
    for i in range(len(adaylar) - 1):
        if adaylar[i]["kare_b"] < gt < adaylar[i + 1]["kare_a"]:
            return f"aday {i} ile aday {i + 1} ARASINDA boşlukta"
    return "adaysız bölgede (belirsiz konum)"


# ── (c) içerik örnekleri ─────────────────────────────────────────────────
def kare_dosya_haritasi(dizin: str) -> dict[int, str]:
    """Mutlak kare no -> dosya yolu. Klasör c_00001'den başlamayabilir; bu yüzden
    konumdan değil, her dosya adından co._kare_no ile ayrıştırılan sayıdan haritalanır."""
    return {co._kare_no(p): p for p in co.kareler(dizin)}


def icerik_ornekleri(dizin: str, gt: int) -> list[tuple[int, str | None, list[str]]]:
    harita = kare_dosya_haritasi(dizin)
    sonuc = []
    for hedef in (gt - 2, gt, gt + 4):
        p = harita.get(hedef)
        if p is None:
            sonuc.append((hedef, None, []))
            continue
        try:
            satirlar = cc.satirlar(p)
        except Exception as e:  # noqa: BLE001 — bir kare OCR'ı patlarsa atlası düşürme
            satirlar = [f"[OCR HATASI: {e}]"]
        sonuc.append((hedef, p, satirlar[:8]))
    return sonuc


# ── (d) scroll istatistiği (gt±10, tespit_v5 ile AYNI stride=2 indeksleme) ─
def scroll_istatistik(dizin: str, gt: int, stride: int = 2, pencere: int = PENCERE) -> dict:
    """credit_onset._gri + dy_cift ile bağımsız hesap (tespit_v5'in iç dizileri
    Sonuc.seri'de yok — T2 yalnız 'adaylar'ı taşıyor). AYNI idx=range(0,len(g),stride)
    örneklemesi kullanılır ki index hizası tespit_v5 ile birebir tutarlı olsun."""
    g = co.kareler(dizin)
    if not g:
        return {"n": 0, "oran": None, "dy_medyan": None}
    idx = list(range(0, len(g), stride))
    abs_no = [co._kare_no(g[i]) for i in idx]
    secili = [s for s, an in enumerate(abs_no) if gt - pencere <= an <= gt + pencere]
    if not secili:
        return {"n": 0, "oran": None, "dy_medyan": None}
    lo, hi = min(secili), min(max(secili), len(idx) - 2)
    if hi < lo:
        return {"n": 0, "oran": None, "dy_medyan": None}
    gk = {s: co._gri(g[idx[s]]) for s in range(lo, hi + 2)}
    dys, corrs = [], []
    for s in range(lo, hi + 1):
        d, r = co.dy_cift(gk[s], gk[s + 1])
        dys.append(d)
        corrs.append(r)
    dys_a = np.array(dys, dtype=np.float32)
    corrs_a = np.array(corrs, dtype=np.float32)
    aktif = (dys_a > 3) & (corrs_a >= 0.85)
    return {"n": int(len(dys_a)), "oran": round(float(aktif.mean()), 2),
            "dy_medyan": round(float(np.median(dys_a)), 1)}


# ── (e) otomatik ön-teşhis etiketi ───────────────────────────────────────
def etiket_belirle(gt: int, pred: int, adaylar: list[dict], scroll: dict) -> tuple[str, str]:
    """Öncelik sırası (yukarıdan aşağı, plandaki tanım sırasıyla):
    SCROLL_GEC_BASLADI > SON_ERISIM_KURBANI > ICERIK_REDDI > KUTU_YOK >
    ERKEN_METIN > DIGER."""
    if gt == -1:
        return ("DIGER", "GT kredi_yok(-1) ama v5 kredi_var dedi — ters yönlü "
                          "yanlış-pozitif, 6 etiketten hiçbiri tam uymuyor")
    kazanan_gec = (pred != -1 and pred > gt)
    scroll_lu = (scroll.get("oran") is not None and scroll["oran"] >= SCROLL_ORAN_ESIK)
    if kazanan_gec and scroll_lu:
        return ("SCROLL_GEC_BASLADI",
                 f"kazanan koşu gt'den geç (pred={pred}>gt={gt}) ve gt-penceresi "
                 f"scroll'lu (oran={scroll['oran']}, dy_med={scroll['dy_medyan']})")
    ic = iceren_aday(gt, adaylar)
    if ic is None:
        return ("KUTU_YOK", "gt hiçbir adayın kutu-koşusu içinde değil")
    if not ic["son_ok"]:
        return ("SON_ERISIM_KURBANI",
                 f"gt aday[{ic['kare_a']}-{ic['kare_b']}] içinde ama son_ok=False "
                 f"(SON_ERISIM={0.82}'ye takıldı, içerik hiç ölçülmedi)")
    if ic["kb"] is not None and ic["kb"] < 0.6:
        return ("ICERIK_REDDI",
                 f"gt aday[{ic['kare_a']}-{ic['kare_b']}] içinde ama kb={ic['kb']}<0.6 "
                 f"(içerik-eşiği geçilemedi)")
    if pred != -1 and pred < gt:
        return ("ERKEN_METIN",
                 f"tahmin={pred} < gt={gt} (koşu başı kredi-dışı metin erken tetiklemiş; "
                 f"gt'yi içeren aday içerik-eşiğini geçmesine rağmen daha erken bir aday kazandı)")
    return ("DIGER", f"pred={pred} gt={gt} — yukarıdaki kalıplara net uymuyor")


def hedef_gorev(gt: int, pred: int, kisaad: str) -> str:
    """Raporlama amaçlı: sapma işaretinden T4/T5/T6 kestirimi (plan hedef-listeleriyle
    çapraz kontrol edilir; karar mantığını DEĞİŞTİRMEZ, yalnız ÖZET tablosunu doldurur)."""
    if kisaad in _GOREV6_ORNEK or (gt != -1 and pred == -1):
        return "T6"
    if kisaad in _GOREV4_ORNEK or (gt != -1 and pred != -1 and pred > gt):
        return "T4"
    if kisaad in _GOREV5_ORNEK or (gt != -1 and pred != -1 and pred < gt):
        return "T5"
    if gt == -1:
        return "?? (ters-yönlü yanlış-pozitif, T4/T5/T6 dışı — ayrı ele alınmalı)"
    return "??"


# ── ana akış ──────────────────────────────────────────────────────────────
def aday_tablosu_md(adaylar: list[dict]) -> str:
    if not adaylar:
        return "_(aday yok — kutu-koşusu hiç bulunamadı)_\n"
    satirlar = ["| # | kare_a | kare_b | son_ok | kb | joint | roller |",
                "|---|---|---|---|---|---|---|"]
    for i, ad in enumerate(adaylar):
        roller = ", ".join(ad["roller"]) if ad["roller"] else "—"
        kb = "—" if ad["kb"] is None else f"{ad['kb']:.3f}"
        joint = "—" if ad["joint"] is None else f"{ad['joint']:.3f}"
        satirlar.append(f"| {i} | {ad['kare_a']} | {ad['kare_b']} | {ad['son_ok']} "
                         f"| {kb} | {joint} | {roller} |")
    return "\n".join(satirlar) + "\n"


def film_islem(ad: str, kisaad: str, x: dict, dizin: str) -> tuple[str, dict]:
    """Bir hata filmini işler → (markdown_bolumu, ozet_kaydi)."""
    gt = x["gercek_onset"]
    karar = x["karar"]
    t0 = time.time()
    try:
        r = co.tespit_v5(dizin)
    except Exception as e:  # noqa: BLE001 — bir filmin patlaması atlası düşürmesin
        md = (f"## {ad}\n\n**GT:** karar={karar}  gercek_onset={gt}\n\n"
              f"**İŞLEME HATASI:** tespit_v5 çalışırken patladı: `{e}`\n\n---\n\n")
        return md, {"film": ad, "kisaad": kisaad, "karar": karar, "gt": gt,
                     "pred": None, "etiket": "DIGER", "hedef": "??", "hata": str(e)}

    pred = r.start_frame
    adaylar = r.seri.get("adaylar", [])
    sapma = (pred - gt) if (gt != -1 and pred != -1) else None

    bolumler = [f"## {ad}\n",
                f"**GT:** karar=`{karar}`  gercek_onset=`{gt}`  "
                f"**v5(şimdi):** tahmin=`{pred}`  yöntem=`{r.yontem}`  sapma=`{sapma}`\n",
                f"v5 notları: {r.notlar}\n",
                "\n**(a) Aday listesi (seri[\"adaylar\"]):**\n",
                aday_tablosu_md(adaylar)]

    if gt == -1:
        bolumler.append("\n**(b)-(d):** GT kredi_yok(-1) — gerçek-onset yok, "
                         "konum/içerik/scroll penceresi tanımsız (atlandı).\n")
        scroll = {"n": 0, "oran": None, "dy_medyan": None}
    else:
        konum = konum_yaz(gt, adaylar)
        bolumler.append(f"\n**(b) Gerçek-onset ({gt}) konumu:** {konum}\n")

        ornekler = icerik_ornekleri(dizin, gt)
        bolumler.append("\n**(c) İçerik örnekleri (gt-2, gt, gt+4) — "
                         "credit_content.satirlar ilk 8 satır:**\n")
        for hedef, p, satirlar_ in ornekler:
            if p is None:
                bolumler.append(f"- kare {hedef}: _[KARE YOK — dosya bulunamadı]_\n")
            else:
                dosya = os.path.basename(p)
                bolumler.append(f"- kare {hedef} (`{dosya}`): {satirlar_}\n")

        scroll = scroll_istatistik(dizin, gt)
        bolumler.append(f"\n**(d) Scroll istatistiği (gt±{PENCERE}, stride=2):** "
                         f"n={scroll['n']} örnek-çift, "
                         f"oran(dy>3&corr≥.85)={scroll['oran']}, "
                         f"dy_medyan={scroll['dy_medyan']}\n")

    etiket, gerekce = etiket_belirle(gt, pred, adaylar, scroll)
    hedef = hedef_gorev(gt, pred, kisaad)
    bolumler.append(f"\n**(e) Ön-teşhis etiketi:** `{etiket}` — {gerekce}\n")
    bolumler.append(f"\n_(hedef görev: {hedef}; işleme süresi {time.time() - t0:.1f} sn)_\n")
    bolumler.append("\n---\n")

    return "\n".join(bolumler), {"film": ad, "kisaad": kisaad, "karar": karar, "gt": gt,
                                  "pred": pred, "sapma": sapma, "etiket": etiket,
                                  "hedef": hedef, "hata": None}


def main() -> int:
    gt_all = json.load(open(f"{V}/dogrulama_sonuc.json", encoding="utf-8"))["filmler"]
    hatalar = [x for x in gt_all if x["karar"] != "dogru"]
    klas = {norm(os.path.basename(p.rstrip("/"))): p
            for p in sorted(glob.glob(f"{KOK}/*/"))}

    tekil = None
    if "--film" in sys.argv:
        tekil = sys.argv[sys.argv.index("--film") + 1]

    bolumler_md = []
    ozet = []
    bekleyenler = []
    t0 = time.time()

    for x in hatalar:
        ad = norm(x["film"])
        if tekil and tekil not in ad:
            continue
        kisaad = kisa_ad(ad)
        p = klas.get(ad)
        if not p or len(glob.glob(p + "*.png")) < 50:
            bekleyenler.append(ad)
            continue
        print(f"[{len(ozet) + 1}/{len(hatalar)}] işleniyor: {ad} ...", file=sys.stderr, flush=True)
        md, kayit = film_islem(ad, kisaad, x, p)
        bolumler_md.append(md)
        ozet.append(kayit)
        print(f"  -> etiket={kayit['etiket']} hedef={kayit['hedef']} "
              f"pred={kayit['pred']} gt={kayit['gt']}", file=sys.stderr, flush=True)

    # ── ÖZET tablosu ──
    etiket_sayim: dict[str, int] = {}
    etiket_hedefler: dict[str, set] = {}
    for k in ozet:
        etiket_sayim[k["etiket"]] = etiket_sayim.get(k["etiket"], 0) + 1
        etiket_hedefler.setdefault(k["etiket"], set()).add(k["hedef"])

    ozet_md = ["## ÖZET\n",
               f"İşlenen: {len(ozet)} film   Bekleyen (kare eksik): {len(bekleyenler)} film   "
               f"(toplam hata: {len(hatalar)})\n",
               "\n| Etiket | Film sayısı | Hedef görev |",
               "|---|---|---|"]
    for et in ("SCROLL_GEC_BASLADI", "SON_ERISIM_KURBANI", "ICERIK_REDDI",
               "KUTU_YOK", "ERKEN_METIN", "DIGER"):
        n = etiket_sayim.get(et, 0)
        hedefler = ", ".join(sorted(etiket_hedefler.get(et, set()))) if n else "—"
        ozet_md.append(f"| {et} | {n} | {hedefler} |")

    ozet_md.append("\n### Film → etiket → hedef görev (ayrıntı)\n")
    ozet_md.append("| Film | karar | gt | pred | sapma | etiket | hedef |")
    ozet_md.append("|---|---|---|---|---|---|---|")
    for k in ozet:
        ozet_md.append(f"| {k['film']} | {k['karar']} | {k['gt']} | {k['pred']} | "
                        f"{k.get('sapma')} | {k['etiket']} | {k['hedef']} |")

    ozet_md.append("\n### BEKLIYOR (kare klasörü eksik/<50 png)\n")
    if bekleyenler:
        for ad in bekleyenler:
            ozet_md.append(f"- {ad}")
    else:
        ozet_md.append("_(yok — tüm hata filmlerinin kareleri inmiş)_")

    ozet_md.append(f"\n_Toplam işlem süresi: {round(time.time() - t0)} sn_\n")

    baslik = ("# Hata Atlası — 31 hatanın kanıt-bazlı teşhisi (Görev 3 / T3)\n\n"
              f"Üretim: `hata_atlasi.py`  GT kaynağı: `veri/dogrulama_sonuc.json` "
              f"(karar != \"dogru\", {len(hatalar)} film)\n\n"
              "Salt-okunur girdi: `tespit_v5` (figo.py) değiştirilmedi. "
              "Bu atlas Görev 4/5/6'nın tasarım kararlarının kanıt tabanıdır.\n\n---\n\n")

    with open(f"{V}/hata_atlasi.md", "w", encoding="utf-8") as f:
        f.write(baslik)
        f.write("\n".join(bolumler_md))
        f.write("\n\n" + "\n".join(ozet_md) + "\n")

    print(f"\nYAZILDI: {V}/hata_atlasi.md  (işlenen {len(ozet)}, bekleyen {len(bekleyenler)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
