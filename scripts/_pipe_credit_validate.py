#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_pipe_credit_validate.py — mitas_pipeline subprocess: 35B çıktısını credit_validate ile DOĞRULA.
venvs/ocr python ile koşar (duckdb burada). Tek-satır JSON sonuç. ASLA çökmez (hata → status=HATA)."""
import argparse, json, os, sys
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def xml_roles(video):
    """video yanındaki <stem>.xml sidecar → {yonetmen, oyuncu} + orijinal başlık."""
    out = {"yonetmen": [], "oyuncu": []}
    title = ""
    try:
        xp = os.path.splitext(video)[0] + ".xml"
        if not (video and os.path.exists(xp)):
            return out, title
        root = ET.parse(xp).getroot()
        for p in root.iter("PROPERTY"):
            if p.attrib.get("NAME") == "JT:V_ROLE:V_ROL":
                b = p.find("BEAN")
                if b is None:
                    continue
                d = {x.attrib.get("NAME"): (x.text or "") for x in b.findall("PROPERTY")}
                nm = (d.get("V_ROL_FIRST", "") + " " + d.get("V_ROL_LAST", "")).strip()
                rt = (d.get("V_ROLE_TYPE", "") or "").upper()
                if not nm:
                    continue
                if "YÖNETMEN" in rt or "YONETMEN" in rt:
                    out["yonetmen"].append(nm)
                elif "OYUNCU" in rt or "ROL" in rt:
                    out["oyuncu"].append(nm)
            if p.attrib.get("NAME") == "JT:EDC_DUBLIN_CORE:DC_DESCRIPTION":
                b = p.find("BEAN")
                if b is not None:
                    for x in b.findall("PROPERTY"):
                        if x.attrib.get("NAME") == "DM_TITLE":
                            title = (x.text or "").strip()
    except Exception:  # noqa: BLE001
        pass
    return out, title


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-credits", required=True, help="35B JSON {yonetmen,cast,...}")
    ap.add_argument("--video", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--ocr", default="", help="ham kunye.txt (kare-içi konsensüs)")
    ap.add_argument("--profile", default="film")
    a = ap.parse_args()
    out = {"yonetmen": {"status": "HATA"}}
    try:
        vc = json.loads(a.video_credits) if a.video_credits else {}
        ext = {"yonetmen": vc.get("yonetmen") or [], "cast": vc.get("cast") or []}
        xr, xt = xml_roles(a.video)
        title = a.title or xt
        ocr_text = ""
        if a.ocr and os.path.exists(a.ocr):
            ocr_text = open(a.ocr, encoding="utf-8", errors="ignore").read()
        import credit_validate as cvmod
        out = cvmod.validate(ext, xml_roles=xr, title=title, ocr_text=ocr_text)
    except Exception as e:  # noqa: BLE001 — pipeline'ı ASLA bozma
        out = {"yonetmen": {"status": "HATA", "hata": f"{type(e).__name__}: {e}"}}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
