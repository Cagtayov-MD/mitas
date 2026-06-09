#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
credit_qc.py — Final künye teslimat KALİTE KONTROL'ü (QC). MÜDAHALE ETMEZ; sadece SINIFLANDIRIR.

Akış: Database/<clip>/pdf/{kunye_teslim.md, kunye_onizleme.png} okur ->
  - DETERMİNİSTİK metin kontrolleri (yönetmen boş/şüpheli, yapımcı, cast, özet hata/mojibake/büyükharf,
    ses&altyazı mantığı, anahtar garble)  [credit_role_lexicon ile rol/alt-rol farkı]
  - (opsiyonel) qwen-VL GÖRSEL kontrol (önizleme PNG: İ/Ğ/Ü glyph, afiş var mı, özet tutarlı/altyazı kaçmış mı)
  -> temizse  dagitim/hazir/<clip>/   sorunluysa  dagitim/kontrol/<clip>/  (dosyalar KOPYALANIR, değişmez)
  -> kontrol nedenleri  dagitim/kontrol/_kontrol_kayit.xlsx  'e işlenir (sebep+kategori -> patern analizi)

Kullanim:
  python scripts/credit_qc.py                       # tum Database cliplerini tara, route+excel
  python scripts/credit_qc.py --clip 1              # tek clip
  python scripts/credit_qc.py --visual              # qwen-VL gorsel QC de ekle (GPU)
  python scripts/credit_qc.py --source <dir> --dest <dir>
"""
import argparse
import base64
import glob
import json
import os
import re
import shutil
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import credit_role_lexicon as lex

SRC = r"E:\MITAS\Database"
DEST = r"E:\MITAS\dagitim"
OLLAMA_CHAT = "http://127.0.0.1:11434/api/chat"
VISUAL_MODEL = "gemma4:26b"

VOWELS = set("AEIOUÜÖİIAEİÂÎÛ")
def is_garble(w):
    w2 = re.sub(r"[^A-Za-zĞÜŞİÖÇğüşıöç]", "", w)
    return len(w2) >= 5 and not any(c.upper() in VOWELS for c in w2)

def has_mojibake(s):
    return bool(re.search(r"[ÃÂÄÅÆ�]|Ä±|Ã¼|Ã§|Ä", s or ""))

DISCLAIMER = ("IZLEYECEGINIZ", "KABUL EDIYOR", "OLMADIGINDAN", "UYARI", "SORUMLU", "TELIF",
              "BU FILM", "BU PROGRAM", "SADECE", "AMACLIDIR")

def parse_md(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    data = {"_raw": txt, "oyuncular": [], "yonetmen": "", "yapimci": "",
            "ozet": "", "ana_dil": "", "altyazi": "", "anahtar": ""}
    sec = None
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("## "):
            sec = lex.norm(s[3:]); continue
        if sec and "OYUNCULAR" in sec and s.startswith("- "):
            data["oyuncular"].append(s[2:].strip())
        elif sec and ("YAPIM" in sec) and s.startswith("-"):
            v = s.lstrip("- ").strip()
            if lex.norm(v).startswith("YAPIMCI"): data["yapimci"] = v.split(":",1)[-1].strip()
            elif lex.norm(v).startswith("YONETMEN"): data["yonetmen"] = v.split(":",1)[-1].strip()
        elif sec and ("SES" in sec or "ALTYAZ" in sec) and s.startswith("-"):
            v = lex.norm(s)
            if "ANA DIL" in v: data["ana_dil"] = v.split("ANA DIL")[-1].strip(" :")
            if "ALTYAZ" in v: data["altyazi"] = v.split("ALTYAZ")[-1].replace("I","").strip(" :I")
        elif sec and "OZET" in sec and s and not s.startswith("#"):
            data["ozet"] += (" " + s)
        elif sec and "ANAHTAR" in sec and s and not s.startswith("#"):
            data["anahtar"] += (" " + s)
    data["ozet"] = data["ozet"].strip()
    return data

EMPTY = {"", "-", "—", "–", "YOK", "OKUNAMADI", "N/A"}
def _empty(v): return lex.norm(v) in {lex.norm(x) for x in EMPTY} or not v.strip()

def det_checks(d, profile="film"):
    """Deterministik kontroller -> [(kategori, sebep)]. Bos liste = temiz."""
    flags = []
    # YONETMEN
    if _empty(d["yonetmen"]):
        flags.append(("YONETMEN_BOS", "yönetmen alanı boş"))
    else:
        nv = lex.norm(d["yonetmen"])
        if any(x in nv for x in lex.EXCLUDE):
            flags.append(("YONETMEN_ALTROL", f"yönetmen alt-rol/şüpheli: {d['yonetmen'][:40]}"))
        elif any(x in nv for x in DISCLAIMER) or any(is_garble(w) for w in d["yonetmen"].split()):
            flags.append(("YONETMEN_COP", f"yönetmen çöp/disclaimer: {d['yonetmen'][:40]}"))
    # YAPIMCI
    if _empty(d["yapimci"]):
        flags.append(("YAPIMCI_BOS", "yapımcı alanı boş"))
    elif any(x in lex.norm(d["yapimci"]) for x in DISCLAIMER):
        flags.append(("YAPIMCI_COP", f"yapımcı disclaimer: {d['yapimci'][:40]}"))
    # CAST
    cast = [c for c in d["oyuncular"] if not _empty(c)]
    if profile == "film" and len(cast) == 0:
        flags.append(("CAST_BOS", "hiç oyuncu yok"))
    if any(is_garble(c) for c in cast):
        flags.append(("CAST_GARBLE", "oyuncuda garble isim"))
    # OZET
    oz = d["ozet"]
    if _empty(oz) or len(oz) < 25:
        flags.append(("OZET_KISA", "özet yok/çok kısa"))
    if re.search(r"transcript|paylaş|belirsiz|yetersiz|lütfen", oz, re.I):
        flags.append(("OZET_HATA", "özet hata/yer-tutucu metin"))
    if has_mojibake(oz):
        flags.append(("OZET_MOJIBAKE", "özette bozuk karakter (i/ü/ğ/İ)"))
    # SES & ALTYAZI (v4: ana_dil != TR + altyazı yok = mantıksız; ana_dil TR değilse SES_TEYIT)
    if d["ana_dil"] and d["ana_dil"] != "TR":
        if d["altyazi"] and "HAYIR" in d["altyazi"]:
            flags.append(("SES_MANTIKSIZ", f"ana_dil {d['ana_dil']} ama altyazı YOK"))
        else:
            flags.append(("SES_TEYIT", f"ana_dil {d['ana_dil']} (TRT TR bekler)"))
    # GENEL mojibake
    if has_mojibake(d["_raw"]):
        flags.append(("MOJIBAKE", "teslim metninde bozuk karakter"))
    return flags

def xml_roles(xml_path):
    """Kaynak video XML sidecar'ından otoriter rolleri çıkar (BEAN/PROPERTY V_ROLE_TYPE)."""
    import xml.etree.ElementTree as ET
    out = {"yonetmen": [], "yapimci": [], "oyuncu": []}
    try:
        root = ET.parse(xml_path).getroot()
    except Exception:
        return out
    for bean in root.iter("BEAN"):
        first = last = rtype = ""
        for prop in bean.iter("PROPERTY"):
            nm = (prop.get("NAME") or "").upper(); val = (prop.text or "").strip()
            if nm == "V_ROL_FIRST": first = val
            elif nm == "V_ROL_LAST": last = val
            elif nm == "V_ROLE_TYPE": rtype = lex.norm(val)
        name = (first + " " + last).strip()
        if not name or not rtype:
            continue
        if "YONETMEN" in rtype or "YONETEN" in rtype: out["yonetmen"].append(name)
        elif "YAPIM" in rtype: out["yapimci"].append(name)
        elif "OYUNCU" in rtype or rtype == "ROL": out["oyuncu"].append(name)
    return out

def find_xml(clipdir, durum):
    cands = []
    vid = (durum or {}).get("video")
    if vid:
        cands.append(os.path.splitext(vid)[0] + ".xml")
    cands += glob.glob(os.path.join(clipdir, "source", "*.xml")) + glob.glob(os.path.join(clipdir, "*.xml"))
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None

def _fold_in(name, lst):
    """name, lst içindeki herhangi biriyle (soyad+çoğu token) eşleşiyor mu?"""
    nn = lex.norm(name)
    for x in lst:
        xt = [t for t in lex.norm(x).split() if len(t) > 2]
        if xt and sum(1 for t in xt if t in nn) >= max(1, len(xt) - 1):
            return True
    return False

def xml_check(d, clipdir, durum):
    """XML ile İSİM eşleşmesi: yönetmen + oyuncu (başka alan DEĞİL). XML YOKSA boş.
    Not: XML ~%90 güvenilir, KESİN değil -> 'uyumsuz' = KARŞILIKLI uyarı (XML otomatik kazanmaz)."""
    xmlp = find_xml(clipdir, durum)
    if not xmlp:
        return []
    xr = xml_roles(xmlp)
    flags = []
    # YÖNETMEN ismi tutuyor mu
    if xr["yonetmen"]:
        if _empty(d["yonetmen"]):
            flags.append(("XML_YON_VAR_TESLIM_YOK", f"XML yönetmen var, teslimde yok: {xr['yonetmen'][0]}"))
        elif not _fold_in(d["yonetmen"], xr["yonetmen"]):
            flags.append(("XML_YON_UYUMSUZ", f"yönetmen: XML '{xr['yonetmen'][0]}' ≠ teslim '{d['yonetmen'][:30]}'"))
    # OYUNCU isimleri örtüşüyor mu (XML aktörlerinden hiçbiri teslim cast'inde yoksa)
    cast = [c for c in d["oyuncular"] if not _empty(c)]
    if xr["oyuncu"] and cast and not any(_fold_in(a, cast) for a in xr["oyuncu"]):
        flags.append(("XML_CAST_UYUMSUZ", f"oyuncu örtüşmüyor: XML {', '.join(xr['oyuncu'][:2])}"))
    return flags

def _xml_original_title(clipdir, durum):
    """XML'den orijinal başlık (kimlik için). Yoksa None."""
    xmlp = find_xml(clipdir, durum)
    if not xmlp:
        return None
    try:
        import xml.etree.ElementTree as ET
        for prop in ET.parse(xmlp).getroot().iter("PROPERTY"):
            if (prop.get("NAME") or "").upper() in ("TITLE", "V_TITLE", "ORIGINAL_TITLE", "V_ORIGINAL_TITLE", "V_ORIJINAL_AD"):
                if (prop.text or "").strip():
                    return prop.text.strip()
    except Exception:
        pass
    return None

def crosscheck_check(d, clipdir, durum, kb):
    """Idea 2 (flag): okunan yönetmen Wikidata/IMDb otoritesiyle ÇELİŞİYOR mu? Düzeltmez, flag'ler."""
    if kb is None:
        return []
    title_tr = (durum.get("title") or os.path.basename(clipdir) or "").strip()
    rd = (d.get("yonetmen") or "").strip()
    # önemsiz/çöp başlık (örn. "3", "1") yanlış-eşleşme üretir -> cross-check'i atla (en az 4 harf)
    if not title_tr or _empty(rd) or len(re.sub(r"[^A-Za-zĞÜŞİÖÇğüşıöç]", "", title_tr)) < 4:
        return []
    cast = [c for c in d.get("oyuncular", []) if not _empty(c)]
    try:
        r = kb.crosscheck(rd, cast, title_tr=title_tr, original=_xml_original_title(clipdir, durum))
    except Exception:
        return []
    if r.get("verdict") == "ÇELİŞKİ":
        oto = (r.get("otoriter_yonetmen") or [""])[0]
        return [("CROSSCHECK_CELISKI", f"yönetmen '{rd[:24]}' ≠ {r.get('kaynak')} '{str(oto)[:24]}' ({r.get('eslesen_film')})")]
    return []

def stamp_pdf_warning(pdf_path, cats):
    """Dağıtım KOPYASININ PDF'ine küçük uyarı damgası (orijinal Database'e DOKUNMAZ).
    XML isim uyuşmazlığında 'tutmadı' işareti — fitz ile, sağ üst köşe, küçük kırmızı."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        pg = doc[0]
        msg = "(!) isim uyusmazligi: " + ", ".join(c.replace("XML_", "").replace("CROSSCHECK_", "").replace("_", " ").lower() for c in cats)
        pg.insert_text((pg.rect.width - 250, 16), msg[:70], fontsize=7, color=(0.85, 0, 0))
        doc.save(pdf_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        doc.close()
        return True
    except Exception as e:
        sys.stderr.write(f"[uyari] pdf damga: {type(e).__name__} {e}\n")
        return False

def visual_check(png, model=VISUAL_MODEL):
    """qwen-VL/gemma onizleme gorseli QC -> [(kategori,sebep)]. GPU gerektirir."""
    # Ağır model ise (gemma4:26b) süreçler-arası VRAM mutex al — fail-open.
    try:
        from _vram_guard import heavy_gpu_guard as _heavy_gpu_guard
    except ImportError:
        from contextlib import nullcontext as _heavy_noop
        def _heavy_gpu_guard(m, **kw):  # type: ignore[misc]
            return _heavy_noop()

    prompt = ("Bu bir film künye sayfasının önizlemesi. SADECE şu kontrolleri yap ve JSON döndür:\n"
              '{"afis_var": true/false, "turkce_harf_bozuk": true/false, '
              '"ozet_tutarli": true/false, "altyazi_kacmis": true/false, "duzen_ok": true/false}\n'
              "afis_var: sayfada gerçek bir afiş/poster görseli var mı. turkce_harf_bozuk: İ Ğ Ü Ş Ö Ç "
              "kutu/bozuk mu görünüyor. ozet_tutarli: özet anlamlı bir paragraf mı. altyazi_kacmis: künyeye "
              "film altyazısı/diyalog karışmış mı. duzen_ok: genel düzen düzgün mü. Sadece JSON, açıklama yok.")
    with open(png, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = {"model": model, "messages": [{"role": "user", "content": prompt, "images": [b64]}],
               "stream": False, "think": False, "keep_alive": "10m",
               "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 200}}
    try:
        req = urllib.request.Request(OLLAMA_CHAT, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with _heavy_gpu_guard(model, label="credit_qc"):
            with urllib.request.urlopen(req, timeout=300) as r:
                content = (json.loads(r.read().decode()).get("message", {}).get("content") or "")
        m = re.search(r"\{.*\}", content, re.S)
        j = json.loads(m.group(0)) if m else {}
    except Exception as e:
        return [("GORSEL_HATA", f"görsel QC çalışmadı: {type(e).__name__}")]
    flags = []
    if j.get("afis_var") is False: flags.append(("AFIS_YOK", "önizlemede afiş görünmüyor"))
    if j.get("turkce_harf_bozuk") is True: flags.append(("GLYPH_BOZUK", "Türkçe harf glyph bozuk (görsel)"))
    if j.get("ozet_tutarli") is False: flags.append(("OZET_TUTARSIZ", "özet tutarsız (görsel)"))
    if j.get("altyazi_kacmis") is True: flags.append(("ALTYAZI_KACMIS", "künyeye altyazı karışmış (görsel)"))
    if j.get("duzen_ok") is False: flags.append(("DUZEN", "düzen bozuk (görsel)"))
    return flags

def route_and_log(clip, title, pdfdir, flags, dest):
    hazir = os.path.join(dest, "hazir"); kontrol = os.path.join(dest, "kontrol")
    os.makedirs(hazir, exist_ok=True); os.makedirs(kontrol, exist_ok=True)
    target_root = kontrol if flags else hazir
    safe = re.sub(r"[^0-9A-Za-zĞÜŞİÖÇğüşıöç._-]", "_", str(clip)) or "clip"  # benzersiz + Türkçe korunur
    target = os.path.join(target_root, safe)
    os.makedirs(target, exist_ok=True)
    for fn in ("kunye.pdf", "kunye_teslim.md", "kunye_onizleme.png"):
        src = os.path.join(pdfdir, fn)
        if os.path.exists(src):
            try: shutil.copy2(src, target)
            except Exception: pass
    # XML/cross-check isim uyuşmazlığı -> dağıtım kopyasının PDF'ine küçük uyarı damgası ("o kadar")
    stamp_cats = [c for c, _ in flags if c.startswith("XML_") or c.startswith("CROSSCHECK_")]
    if stamp_cats:
        p = os.path.join(target, "kunye.pdf")
        if os.path.exists(p):
            stamp_pdf_warning(p, stamp_cats)
    if flags:
        _excel_append(os.path.join(kontrol, "_kontrol_kayit.xlsx"), clip, title, flags)
    return "kontrol" if flags else "hazir"

def _excel_append(path, clip, title, flags):
    import openpyxl
    if os.path.exists(path):
        wb = openpyxl.load_workbook(path); ws = wb.active
    else:
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "kontrol"
        ws.append(["zaman", "clip", "baslik", "sebep_sayisi", "kategoriler", "sebepler"])
    ts = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    ws.append([ts, str(clip), str(title)[:60], len(flags),
               ", ".join(sorted(set(c for c, _ in flags))),
               " | ".join(s for _, s in flags)])
    wb.save(path)

def process(clipdir, dest, do_visual, kb=None):
    pdfdir = os.path.join(clipdir, "pdf")
    md = os.path.join(pdfdir, "kunye_teslim.md")
    durum = os.path.join(clipdir, "_DURUM.json")
    if not os.path.exists(md):
        return None
    title = clip = os.path.basename(clipdir); profile = "film"; durum_dict = {}
    if os.path.exists(durum):
        try:
            durum_dict = json.load(open(durum, encoding="utf-8"))
            title = durum_dict.get("title") or clip; profile = durum_dict.get("profile") or "film"
        except Exception: pass
    d = parse_md(md)
    flags = det_checks(d, profile)
    flags += xml_check(d, clipdir, durum_dict)     # XML V_ROLE_TYPE uyum (XML varsa)
    flags += crosscheck_check(d, clipdir, durum_dict, kb)   # Idea 2: Wikidata/IMDb çapraz-kontrol (flag açıkken)
    png = os.path.join(pdfdir, "kunye_onizleme.png")
    if do_visual and os.path.exists(png):
        flags += visual_check(png)
    karar = route_and_log(clip, title, pdfdir, flags, dest)
    return clip, karar, flags

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Künye teslimat QC (sınıflandırır, müdahale etmez)")
    ap.add_argument("--source", default=SRC); ap.add_argument("--dest", default=DEST)
    ap.add_argument("--clip", default=None); ap.add_argument("--visual", action="store_true")
    ap.add_argument("--crosscheck", action="store_true", help="Wikidata/IMDb çapraz-kontrol (Idea 2)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if args.clip:
        clips = [os.path.join(args.source, args.clip)]
    else:
        clips = [d for d in sorted(glob.glob(os.path.join(args.source, "*")))
                 if os.path.isdir(d) and os.path.exists(os.path.join(d, "pdf", "kunye_teslim.md"))]
        if args.limit: clips = clips[:args.limit]
    use_cc = args.crosscheck or os.environ.get("MITAS_USE_CROSSCHECK", "").strip().lower() in ("1", "true", "yes", "on")
    kb = None
    if use_cc:
        try:
            import credit_crosscheck as _ccm
            kb = _ccm.CreditKB()
        except Exception as e:
            sys.stderr.write(f"[uyari] crosscheck kb acilamadi: {e}\n")
    haz = kon = 0; cats = {}
    for c in clips:
        r = process(c, args.dest, args.visual, kb)
        if not r: continue
        clip, karar, flags = r
        if karar == "hazir": haz += 1
        else:
            kon += 1
            for cat, _ in flags: cats[cat] = cats.get(cat, 0) + 1
        print(f"[{karar.upper():7}] {clip[:46]:46} {'· '+', '.join(c for c,_ in flags) if flags else ''}", flush=True)
    print(f"\n=== QC BITTI: hazir {haz}, kontrol {kon} -> {args.dest} ===")
    if cats:
        print("kontrol sebep dagilimi (en cok):")
        for cat, n in sorted(cats.items(), key=lambda x: -x[1]):
            print(f"   {n:3}  {cat}")
    if kb:
        kb.close()

if __name__ == "__main__":
    main()
