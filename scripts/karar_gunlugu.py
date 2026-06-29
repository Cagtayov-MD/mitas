# -*- coding: utf-8 -*-
"""KARAR GÜNLÜĞÜ — MITAS film-başı detaylı karar günlüğü üretici.

SALT-OKUR analiz katmanı — pipeline/üretim koduna dokunmaz.
Her film klasörünün içine KARAR_GUNLUGU.md yazar.

Kullanım:
  python scripts/karar_gunlugu.py "BÜYÜK RESTAURANT"
  python scripts/karar_gunlugu.py "1987-0251"
  python scripts/karar_gunlugu.py --all          # tüm Database
  python scripts/karar_gunlugu.py --all --dry    # klasöre YAZMAZ, stdout'a basar
"""
from __future__ import annotations
import sys, os, json, glob, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

# Türkiye yerel saati (UTC+03:00) — loglar UTC, çıktı tanıdık duvar-saati
TR_TZ = timezone(timedelta(hours=3))

# ── Encoding güvencesi ──────────────────────────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DB = Path(r"E:\MITAS\Database")
OUTPUT_FILE = "KARAR_GUNLUGU.md"


# ═══════════════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════════════

def _find_film(arg: str) -> Optional[Path]:
    """Ada, TRT-ID veya yola göre film klasörü bul."""
    p = Path(arg)
    if p.is_dir():
        return p
    if (DB / arg).is_dir():
        return DB / arg
    # tam prefix eşleşmesi
    hits = [d for d in DB.iterdir() if d.is_dir() and d.name.startswith(arg)]
    if not hits:
        # içerik araması
        hits = [d for d in DB.iterdir() if d.is_dir() and arg.lower() in d.name.lower()]
    return sorted(hits, key=lambda d: len(d.name))[0] if hits else None


def _load_log(log_path: Path) -> list[dict]:
    """_log.jsonl → olay listesi (kronolojik)."""
    events: list[dict] = []
    if not log_path.exists():
        return events
    for raw in log_path.open(encoding="utf-8", errors="replace"):
        raw = raw.strip()
        if not raw:
            continue
        try:
            events.append(json.loads(raw))
        except Exception:
            continue
    return events


def _last_by_kind(events: list[dict]) -> dict[str, dict]:
    """Her kind için EN SON olayı döndür."""
    out: dict[str, dict] = {}
    for e in events:
        k = e.get("kind")
        if k:
            out[k] = e
    return out


def _load_json(path: Path) -> dict:
    """JSON dosyasını güvenli oku."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def _det(ev: Optional[dict]) -> dict:
    """Event'in detail alanını çıkar."""
    if not ev:
        return {}
    d = ev.get("detail")
    return d if isinstance(d, dict) else {}


def _ts_fmt(ts_str: Optional[str]) -> str:
    """ISO (UTC) timestamp → HH:MM:SS Türkiye yerel saati (+03)."""
    if not ts_str:
        return "??:??:??"
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        # UTC → Türkiye yerel duvar-saati (+03:00)
        dt_local = dt.astimezone(TR_TZ)
        return dt_local.strftime("%H:%M:%S")
    except Exception:
        return ts_str[:8] if len(ts_str) >= 8 else ts_str


def _ts_sort_key(ts_str: Optional[str]) -> str:
    """Sıralama için ham ISO timestamp (UTC). Boşsa en sona itecek değer."""
    if not ts_str:
        return "9999"  # ts'siz satırlar en sona
    return ts_str


def _sn(secs: Optional[float]) -> str:
    """Saniyeyi okunabilir biçime çevir."""
    if secs is None:
        return "?"
    return f"{secs:.1f} sn"


def _nl(v, kok: int = 6) -> str:
    """JSON listesini kısa temsil."""
    if not v:
        return "—"
    return json.dumps(v[:kok], ensure_ascii=False)


def _final_kunye(film: Path) -> dict:
    """*_teknik.txt dosyasından final yönetmen + oyuncu çıkar."""
    tk = glob.glob(str(film / "*_teknik.txt"))
    res = {"yonetmen": None, "cast": [], "raw": ""}
    if not tk:
        return res
    txt = Path(tk[0]).read_text(encoding="utf-8", errors="replace")
    res["raw"] = txt[:400]
    m = re.search(r"Yönetmen\s*:\s*(.+)", txt)
    if m:
        res["yonetmen"] = m.group(1).strip()
    # OYUNCULAR bloğu
    mb = re.search(r"OYUNCULAR\s*\n[=-]+\n(.*?)(?:\n[=-]+|\Z)", txt, re.S)
    if mb:
        res["cast"] = [l.strip() for l in mb.group(1).splitlines() if l.strip()][:12]
    return res


def _master_png_status(film: Path) -> str:
    """master PNG durumu. YENİ (2026-06-29): film KÖKÜNDE '<TRT BAŞLIK> {giris,cikis}.png'
    + '<...> master_manifest.json'. ESKİ (geçiş): master/ alt-klasörü. İkisi de denenir."""
    _root_manifests = sorted(film.glob("* master_manifest.json"))
    _root_cikis = sorted(film.glob("* cikis.png"))
    _root_giris = sorted(film.glob("* giris.png"))
    master_dir = film / "master"
    manifest = _root_manifests[0] if _root_manifests else (master_dir / "master_manifest.json")
    cikis_png = _root_cikis[0] if _root_cikis else (master_dir / "cikis.png")
    giris_png = _root_giris[0] if _root_giris else (master_dir / "giris.png")
    parts = []
    if manifest.exists():
        try:
            mj = json.loads(manifest.read_text(encoding="utf-8"))
            for tip in ("giris", "cikis"):
                t = mj.get(tip) or {}
                if t.get("path"):
                    fr = t.get("frames", "?")
                    sz = t.get("size", [])
                    mode = t.get("mode", "?")
                    parts.append(f"{tip}: {fr} kare, {sz[0]}x{sz[1]} px, mod={mode}" if len(sz) == 2 else f"{tip}: {fr} kare mod={mode}")
        except Exception:
            parts.append("manifest okunamadı")
    else:
        if cikis_png.exists() or giris_png.exists():
            parts.append("PNG mevcut ama manifest yok")
        else:
            return "OLUŞMADI (master/ klasörü yok veya boş)"
    if not parts:
        return "OLUŞMADI"
    return "OLUŞTU — " + " | ".join(parts)


def _jenerik_status(film: Path) -> dict:
    """frames/jenerik_detection.json durumu (tek dosya — tip ayrımı yok)."""
    jd = film / "frames" / "jenerik_detection.json"
    if jd.exists():
        try:
            d = json.loads(jd.read_text(encoding="utf-8"))
            return {"found": True, "data": d}
        except Exception:
            return {"found": True, "data": {}}
    return {"found": False, "data": {}}


def _ham_ocr(film: Path) -> list[str]:
    """stitch/ocr_ham.txt → ilk 8 satır."""
    ham = film / "stitch" / "ocr_ham.txt"
    if not ham.exists():
        return []
    lines = [l.strip() for l in ham.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    return lines


def _qc_stitch(film: Path) -> dict:
    """stitch/_QC.json varsa oku."""
    qc = film / "stitch" / "_QC.json"
    return _load_json(qc)


# ═══════════════════════════════════════════════════════════════════════════
# KARAR GÜNLÜĞÜ ÜRETİCİ
# ═══════════════════════════════════════════════════════════════════════════

def build_gunluk(film: Path) -> str:
    """Tek film için KARAR_GUNLUGU.md içeriğini üret."""
    name = film.name

    # ── Temel veri yükle ────────────────────────────────────────────────
    events = _load_log(film / "_log.jsonl")
    ev = _last_by_kind(events)
    durum = _load_json(film / "_DURUM.json")
    fk = _final_kunye(film)
    ham_lines = _ham_ocr(film)
    master_st = _master_png_status(film)
    jen_info = _jenerik_status(film)
    stitch_qc = _qc_stitch(film)

    # _log yok ama _DURUM dolu mu? (log silinmiş/taşınmış ama film İŞLENMİŞ)
    log_missing = not events
    durum_present = bool(durum)

    # ── Genel bilgiler ──────────────────────────────────────────────────
    karar = durum.get("karar") or "?"
    trt_id = (durum.get("trt_id") or name.split(" ")[-1]) if durum else name.split(" ")[-1]
    route = (durum.get("route") or {})
    route_tier = route.get("tier", "?")
    neden_list = durum.get("neden") or []
    qwen_uyari = durum.get("qwen_uyari") or []

    # QC2 izleri: otorite_audit (top-level) + neden[] içindeki "qc_block:" satırları
    _oa = durum.get("otorite_audit")
    otorite_audit = _oa if isinstance(_oa, dict) else {}
    qc_block_satirlari = [n for n in neden_list if isinstance(n, str) and n.strip().lower().startswith("qc_block:")]
    timings = durum.get("timings_sec") or {}
    toplam = timings.get("toplam")
    ts_bitis = durum.get("ts") or (ev.get("qwen_final_qc") or {}).get("ts") or ""
    ts_baslangic = (ev.get("media_imported") or {}).get("ts") or ""

    # Başlangıç/bitiş saat
    hh_baslangic = _ts_fmt(ts_baslangic)
    hh_bitis = _ts_fmt(ts_bitis)

    # ── Olay türlerine göre detay çıkar ────────────────────────────────

    # credit_detect: hem opening hem closing log'da var
    det_opening = _det(ev.get("credit_detect_opening"))
    det_closing = _det(ev.get("credit_detect_closing"))
    op_data = det_opening.get("opening") or {}
    cl_data = det_closing.get("closing") or {}

    # OCR
    det_ocr = _det(ev.get("ocr_completed"))
    ocr_bucket = det_ocr.get("bucket") or durum.get("ocr_bucket") or "?"
    ocr_lines = det_ocr.get("lines") or durum.get("ocr_lines") or 0
    ocr_engine = det_ocr.get("engine") or "?"
    ocr_dur = timings.get("ocr") or (ev.get("ocr_completed") or {}).get("duration_seconds")

    # credit_text (LLM ayıklayıcı)
    det_ct = _det(ev.get("credit_text_completed"))
    ct_yon = det_ct.get("yonetmen") or []
    ct_guven = det_ct.get("guven") or "?"
    ct_dur = timings.get("video_kunye") or (ev.get("credit_text_completed") or {}).get("duration_seconds")

    # VL fallback
    has_vl_red = "credit_qc1_red" in ev
    det_vl = _det(ev.get("credit_vl_fallback"))
    vl_kosuldu = "credit_vl_fallback" in ev
    vl_yon = det_vl.get("yonetmen") or []
    _vl_cs_raw = det_vl.get("cast_supplement")
    # cast_supplement bazen int (sayı) bazen liste olabiliyor
    if isinstance(_vl_cs_raw, list):
        vl_cast_sup = _vl_cs_raw
    elif isinstance(_vl_cs_raw, int):
        vl_cast_sup = list(range(_vl_cs_raw))  # uzunluk bilgisi için sahte liste
    else:
        vl_cast_sup = []
    vl_dur = timings.get("vl_fallback") or (ev.get("credit_vl_fallback") or {}).get("duration_seconds")

    # validate
    det_val = _det(ev.get("credit_validate"))
    val_res = det_val.get("result") or {}
    val_yon = val_res.get("yonetmen") or {}
    val_cast = val_res.get("cast") or {}
    val_kaynaklar = val_res.get("kaynaklar") or {}
    val_qc1 = val_res.get("qc1") or {}
    imdb_data = val_kaynaklar.get("imdb") or {}
    wiki_data = val_kaynaklar.get("wiki") or {}

    # QC1 olayları
    qc1_red_ev = ev.get("credit_qc1_red")
    qc1_fail_ev = ev.get("credit_qc1_failed")
    qc1_pass_ev = ev.get("credit_qc1_passed")  # VL sonrası geçti olayı (varsa)

    # routed_kontrol eventi (KONTROL kararı + qc_block gerekçeleri)
    routed_ev = ev.get("routed_kontrol")

    # qwen final QC
    det_qwen = _det(ev.get("qwen_final_qc"))
    qwen_qc = det_qwen.get("qwen_qc") or durum.get("qwen_qc") or {}

    # ASR
    det_asr = _det(ev.get("asr_completed"))
    asr_seg = det_asr.get("segments") or durum.get("asr_segments") or 0
    asr_dur = timings.get("asr") or (ev.get("asr_completed") or {}).get("duration_seconds")

    # PDF
    pdf_dur = timings.get("pdf") or (ev.get("pdf_completed") or {}).get("duration_seconds")
    v4_dur = timings.get("v4_final") or (ev.get("v4_finalize_completed") or {}).get("duration_seconds")
    qwen_dur = timings.get("qwen_qc") or (ev.get("qwen_final_qc") or {}).get("duration_seconds")
    coz_dur = timings.get("coz") or (ev.get("cozumleme_completed") or {}).get("duration_seconds")

    # ── SIZMALI yönetmen analizi (credit_trace'ten yeniden kullan) ──────
    fin_yon_str = (fk["yonetmen"] or "").strip()
    fin_empty = not fin_yon_str or fin_yon_str in ("-", "—", "okunamadı", "")
    val_yon_val = val_yon.get("value") or []
    sizinti_notu = ""
    if log_missing and not val_res:
        # _log yok → extractor/validate akışı izlenemiyor; analiz mümkün değil
        sizinti_notu = "⚠ VERİ YOK — sızıntı analizi yapılamadı (_log.jsonl eksik, extractor/validate izlenemiyor) — KÖR NOKTA"
    elif (not ct_yon) and (not val_yon_val) and fin_empty:
        # üçü de boş → akış tutarlı DEĞİL, sadece veri yok
        sizinti_notu = "⚠ VERİ YOK — extractor+validate+final üçü de BOŞ; sızıntı analizi yapılamadı (kör nokta)"
    elif (not ct_yon) and (not val_yon_val) and not fin_empty:
        cast_list = val_cast.get("value") or fk["cast"]
        c0 = cast_list[0] if cast_list else None
        if c0 and re.sub(r"\W", "", fin_yon_str.lower()) == re.sub(r"\W", "", c0.lower()):
            sizinti_notu = f"SIZINTI: cast[0] ('{c0}') yönetmen alanına sızdı (cast→director leak)"
        else:
            sizinti_notu = f"SIZINTI: extractor+validate BOŞ ama final DOLU → ADIM-5/v4 doldurma: '{fin_yon_str}'"
    elif fin_empty and (ct_yon or val_yon_val):
        sizinti_notu = "TERS-KAYIP: OCR/validate yönetmen okudu ama final BOŞ → propagation kaybı"
    else:
        sizinti_notu = "yönetmen akışı tutarlı (extractor/validate ↔ final)"

    # ── jenerik bölümü string ───────────────────────────────────────────
    jen_lines = []
    # log'dan jenerik satırları
    if "credit_detect_closing" in ev:
        cl_sum = (ev["credit_detect_closing"] or {}).get("summary", "")
        jen_lines.append(f"ÇIKIŞ: {cl_sum}")
    if "credit_detect_opening" in ev:
        op_sum = (ev["credit_detect_opening"] or {}).get("summary", "")
        jen_lines.append(f"GİRİŞ: {op_sum}")

    # frames/jenerik_detection.json
    jen_str_parts = []
    if jen_info["found"]:
        jd = jen_info["data"]
        jen_str_parts.append(f"status={jd.get('status','?')}  accepted={jd.get('accepted','?')}")
        jen_str_parts.append(f"pool_frames={jd.get('pool_frames','?')}  input_frames={jd.get('input_frames','?')}")
        jen_str_parts.append(f"conf={jd.get('confidence','?')}  credit_type={jd.get('credit_type','?')}")
        sp = jd.get("start_pos")
        sf = jd.get("start_file")
        if sp is not None:
            jen_str_parts.append(f"start_pos={sp}  start_file={sf or '?'}")
        reason = jd.get("reason")
        if reason:
            jen_str_parts.append(f"sebep: {reason[:120]}")
    else:
        jen_str_parts.append("⚠ frames/jenerik_detection.json YOK (yeni havuz sistemi bu filmde koşmamış veya dosya yok)")

    # ── B) JENERİK TAM-AKIŞ analizi ─────────────────────────────────────
    # GİRİŞ / ÇIKIŞ tespiti (credit_detect_opening/closing.detail)
    jen_opening = {
        "found": op_data.get("found"),
        "type": op_data.get("type"),
        "conf": op_data.get("confidence"),
        "start_sec": op_data.get("start_sec"),
        "end_sec": op_data.get("end_sec"),
        "summary": (ev.get("credit_detect_opening") or {}).get("summary", ""),
    }
    jen_closing = {
        "found": cl_data.get("found"),
        "type": cl_data.get("type"),
        "conf": cl_data.get("confidence"),
        "start_sec": cl_data.get("start_sec"),
        "end_sec": cl_data.get("end_sec"),
        "summary": (ev.get("credit_detect_closing") or {}).get("summary", ""),
    }

    # HAVUZ (jenerik_detection.json): motor + havuz oluştu mu / bıraktı mı
    jd = jen_info["data"] if jen_info["found"] else {}
    jen_status = jd.get("status")
    jen_accepted = jd.get("accepted")
    jen_pool = jd.get("pool_frames")
    jen_input = jd.get("input_frames")
    # motor: detector.config.ocr_mode (paddle/oneocr)
    jen_motor = ((jd.get("detector") or {}).get("config") or {}).get("ocr_mode")
    jen_start_file = jd.get("start_file")
    jen_start_pos = jd.get("start_pos")
    jen_conf = jd.get("confidence")
    jen_reason = jd.get("reason")
    jen_dur = jd.get("duration_sec")
    # jenerik_pool_completed eventi (havuz tamamlanma olayı)
    pool_ev = ev.get("jenerik_pool_completed")
    # close_back (kapanış geri-uzatma)
    close_back_ev = ev.get("credit_detect_close_back")

    # Havuz oluştu mu? (accepted + pool_frames>0)
    havuz_olustu = bool(jen_info["found"] and jen_accepted and (jen_pool or 0) > 0)
    havuz_birakti = bool(jen_info["found"] and (not jen_accepted or (jen_pool or 0) == 0))

    # Master-PNG ile bağ: master oluştu mu?
    master_var = master_st.startswith("OLUŞTU")

    # Akış anlatımı net cümle
    if not jen_info["found"]:
        jen_akis = ("Jenerik başlangıç-seçme HAVUZ sistemi (jenerik_detection.json) bu filmde **koşmadı/iz yok** → "
                    f"klasik credit_detect penceresi + ana-OCR yoluyla devam edildi. "
                    f"Master-PNG: {'oluştu' if master_var else 'oluşmadı'}.")
    elif havuz_olustu:
        jen_akis = (f"Jenerik başlangıç-seçme **ÇALIŞTI** (motor={jen_motor or '?'}, status={jen_status}) → "
                    f"**HAVUZ OLUŞTU: {jen_pool} kare** (girdi {jen_input} kareden, start={jen_start_file}@pos{jen_start_pos}) → "
                    f"buradan {'master-PNG derlemesine gitti' if master_var else 'master-PNG oluşmadı (kör nokta)'}.")
    elif havuz_birakti:
        jen_akis = (f"Jenerik başlangıç-seçme **çalıştı ama HAVUZ BIRAKTI** (motor={jen_motor or '?'}, status={jen_status}, "
                    f"accepted={jen_accepted}, pool_frames={jen_pool}) → otomatik 'found' eşiğine ulaşılamadı "
                    f"(sebep: {(jen_reason or '')[:80]}) → ana-OCR yoluyla devam edildi. "
                    f"Master-PNG: {'yine de oluştu' if master_var else 'oluşmadı'}.")
    else:
        jen_akis = f"Jenerik havuz durumu belirsiz (status={jen_status}, accepted={jen_accepted}, pool={jen_pool})."

    # ── master-PNG jenerik_debug ─────────────────────────────────────────
    jdebug = film / "jenerik_debug"
    jdebug_str = ""
    if jdebug.exists():
        sub = [d.name for d in jdebug.iterdir() if d.is_dir()]
        jdebug_str = f"jenerik_debug/ alt klasörler: {sub}"
    else:
        jdebug_str = "jenerik_debug/ yok"

    # ── XML / dış-kaynak durumu — TEK KAYNAKTAN tutarlı türet ────────────
    # XML teyidi iki yerde gelebilir: (a) sources_confirm listesinde "XML",
    # (b) notes içinde "çelişki: XML" satırı. İkisini birlikte değerlendir.
    _src = [s for s in (val_yon.get("sources_confirm") or []) if isinstance(s, str)]
    _src_upper = {s.strip().upper() for s in _src}
    xml_notlar = [n for n in (val_yon.get("notes") or []) if isinstance(n, str) and ("XML" in n or "xml" in n)]
    _xml_cati = any("çelişki" in n.lower() and "xml" in n.lower() for n in xml_notlar)
    _xml_destek = ("XML" in _src_upper)

    # xml_destekledi: True=destekledi, False=çelişti, None=yok/aranmadı
    if _xml_cati:
        xml_destekledi = False
    elif _xml_destek:
        xml_destekledi = True
    else:
        xml_destekledi = None

    # Tek tutarlı XML durum-cümlesi (3 yerde de bu kullanılır)
    if xml_destekledi is True:
        xml_sonuc = "DESTEKLEDİ (sources_confirm=XML)"
    elif xml_destekledi is False:
        aday = val_yon.get("conflict_candidates") or []
        xml_sonuc = f"ÇELİŞTİ (aday={aday})" + (f": {' | '.join(xml_notlar)}" if xml_notlar else "")
    else:
        xml_sonuc = "yok/teyit-aranmadı (XML iz yok)"

    # IMDb / Wiki durumu — aynı mantık (sources_confirm + kaynaklar.*.director)
    _imdb_dir = imdb_data.get("director") or []
    _wiki_dir = wiki_data.get("director") or []
    def _kaynak_durum(ad: str, dir_list: list) -> str:
        if ad.upper() in _src_upper:
            return f"DESTEKLEDİ ({_nl(dir_list) if dir_list else 'teyit'})"
        if dir_list:
            return f"buldu ({_nl(dir_list)}) ama sources_confirm'de değil"
        return "yok/aranmadı"
    imdb_durum = _kaynak_durum("IMDb", _imdb_dir)
    wiki_durum = _kaynak_durum("Wiki", _wiki_dir)

    # ── QC1 satırı ──────────────────────────────────────────────────────
    qc1_flag = val_qc1.get("flag_level") or "?"
    qc1_needs = val_qc1.get("needs_reread")
    qc1_reason = val_qc1.get("reason") or "?"
    # Öncelik: VL-sonrası geçti > VL-sonrası da RED > ilk RED > validate.qc1 > yok
    if qc1_pass_ev and qc1_red_ev:
        qc1_summary_str = f"İLK RED → VL-fallback → **GEÇTİ** — {(qc1_pass_ev.get('summary') or '')}"
    elif qc1_pass_ev:
        qc1_summary_str = f"GEÇTİ — {(qc1_pass_ev.get('summary') or '')}"
    elif qc1_fail_ev:
        qc1_summary_str = f"İLK RED → VL-fallback → **VL SONRASI DA RED** — {(qc1_fail_ev.get('summary') or '')}"
    elif qc1_red_ev:
        qc1_summary_str = f"RED — {(qc1_red_ev.get('summary') or '')}"
    elif val_qc1:
        qc1_summary_str = f"flag={qc1_flag} needs_reread={qc1_needs} reason={qc1_reason}"
    else:
        qc1_summary_str = "⚠ QC1 olay verisi loglanmıyor (credit_validate.qc1 alanından çekiliyor)"

    # ── RED/ONAY kararı analizi ──────────────────────────────────────────
    val_status = val_yon.get("status") or "?"
    val_conf = val_yon.get("confidence") or "?"
    src_confirm = val_yon.get("sources_confirm") or []
    conflict_cands = val_yon.get("conflict_candidates") or []

    # ── Karar gerekçe özeti ──────────────────────────────────────────────
    karar_gerekce = neden_list or ["⚠ neden listesi _DURUM.json'da yok"]

    # ═══════════════════════════════════════════════════════════════════
    # MARKDOWN ÇİZGİSİ
    # ═══════════════════════════════════════════════════════════════════
    lines: list[str] = []
    A = lines.append
    def sec(title: str):
        A("")
        A(f"## {title}")

    # Başlık
    A(f"# KARAR GÜNLÜĞÜ — {name} ({trt_id})")
    A(f"KARAR: **{karar}** | Toplam süre: {_sn(toplam)} | Başlangıç: {hh_baslangic} → Bitiş: {hh_bitis} (yerel +03)")
    A(f"Route: `{route_tier}` | {route.get('aciklama','')}")
    if log_missing and durum_present:
        A("")
        A("> ℹ️ **Not:** _log.jsonl bulunamadı ama _DURUM.json mevcut. Film **işlenmiş**; olay-logu silinmiş/taşınmış. "
          "Aşağıdaki veriler _DURUM.json + final artefaktlardan türetildi; aşama-bazlı zaman çizelgesi sınırlı.")
    A("")

    # ── ZAMAN ÇİZELGESİ ─────────────────────────────────────────────────
    sec("⏱ ZAMAN ÇİZELGESİ (Türkiye yerel saati, +03)")

    # Tüm satırları (ts, etiket, içerik, süre) tuple'ı olarak topla → ts'ye göre dizip bas.
    rows: list[tuple[str, str, str, Optional[float]]] = []

    def add_row(ts_str, etiket, icerik, sure=None):
        rows.append((ts_str or "", etiket, icerik, sure))

    if "media_imported" in ev:
        add_row(ev["media_imported"].get("ts"), "import",
                f"pipeline'a alındı — {(ev['media_imported'].get('summary',''))[:80]}")

    if "cozumleme_completed" in ev:
        add_row(ev["cozumleme_completed"].get("ts"), "coz",
                "çözümleme bitti", coz_dur)

    # Jenerik tespiti (opening + closing ayrı olaylar)
    for kind_key in ("credit_detect_opening", "credit_detect_closing"):
        if kind_key in ev:
            tip = "jenerik-G" if "opening" in kind_key else "jenerik-C"
            sum_str = (ev[kind_key].get("summary") or "")[:100]
            add_row(ev[kind_key].get("ts"), tip, sum_str)

    if "ocr_started" in ev:
        add_row(ev["ocr_started"].get("ts"), "ocr-baş", "OneOCR başladı")
    if "ocr_completed" in ev:
        add_row(ev["ocr_completed"].get("ts"), "ocr",
                f"OneOCR bitti: {ocr_lines} satır (bucket={ocr_bucket}, motor={ocr_engine})",
                ocr_dur)

    if "asr_started" in ev:
        add_row(ev["asr_started"].get("ts"), "asr-baş", "ASR başladı")
    if "asr_completed" in ev:
        asr_sum = (ev["asr_completed"].get("summary") or "")[:80]
        add_row(ev["asr_completed"].get("ts"), "asr", asr_sum, asr_dur)

    if "credit_text_completed" in ev:
        vl_flag = " → QC1-RED tetikledi" if has_vl_red else ""
        add_row(ev["credit_text_completed"].get("ts"), "extract",
                f"LLM ayıkla: yön={_nl(ct_yon)}  güven={ct_guven}{vl_flag}",
                ct_dur)

    if "credit_qc1_red" in ev:
        add_row(ev["credit_qc1_red"].get("ts"), "qc1-RED",
                (ev["credit_qc1_red"].get("summary") or "")[:100])

    if vl_kosuldu:
        add_row(ev["credit_vl_fallback"].get("ts"), "vl",
                f"VL yedek: yön={_nl(vl_yon)}  cast_sup={len(vl_cast_sup) if vl_cast_sup else 0}",
                vl_dur)

    if "credit_qc1_failed" in ev:
        add_row(ev["credit_qc1_failed"].get("ts"), "qc1-FAIL",
                (ev["credit_qc1_failed"].get("summary") or "")[:100])

    if "credit_validate" in ev:
        xml_kisa = "ÇELİŞTİ" if xml_destekledi is False else ("DESTEKLEDİ" if xml_destekledi is True else "bilinmiyor")
        add_row(ev["credit_validate"].get("ts"), "validate",
                f"KB/XML: yön_status={val_status} conf={val_conf} | XML={xml_kisa} aday={_nl(conflict_cands)}")

    if "ozet_completed" in ev:
        add_row(ev["ozet_completed"].get("ts"), "ozet",
                (ev["ozet_completed"].get("summary") or "")[:80])

    if "pdf_completed" in ev:
        add_row(ev["pdf_completed"].get("ts"), "pdf", "PDF teslim hazırlandı", pdf_dur)

    if "v4_finalize_completed" in ev:
        add_row(ev["v4_finalize_completed"].get("ts"), "v4",
                "künye v4'e çevrildi", v4_dur)

    if "qwen_final_qc" in ev:
        qw_sum = (ev["qwen_final_qc"].get("summary") or "")[:80]
        add_row(ev["qwen_final_qc"].get("ts"), "qc-final", qw_sum, qwen_dur)

    # master-PNG: ayrı olay yok; pdf_completed ts'sini referans alıp çizelgeye DAHİL et.
    master_ts = (ev.get("pdf_completed") or {}).get("ts") or ""
    add_row(master_ts, "master", f"master-PNG: {master_st[:100]}")

    # ── TS'ye göre kronolojik dizip bas (boş ts'liler en sona) ──────────
    if rows:
        for ts_str, etiket, icerik, sure in sorted(rows, key=lambda r: _ts_sort_key(r[0])):
            hh = _ts_fmt(ts_str)
            sure_str = f"  ({_sn(sure)})" if sure is not None else ""
            A(f"`{hh}`  [{etiket:<10}]  {icerik}{sure_str}")
    else:
        # _log yok → olaydan çizelge çıkmıyor; _DURUM özetini bas
        A("⚠ _log.jsonl yok — olay-bazlı çizelge üretilemiyor. _DURUM.json özeti:")
        if durum_present:
            A(f"`{hh_bitis}`  [_DURUM    ]  film İŞLENDİ (log silinmiş/taşınmış) — karar={karar}, toplam={_sn(toplam)}")
            if master_st.startswith("OLUŞTU"):
                A(f"`{hh_bitis}`  [master    ]  {master_st[:100]}")

    # ── AŞAMA DETAYLARI ─────────────────────────────────────────────────
    sec("📋 AŞAMA DETAYLARI")

    # 1. OneOCR
    A("### 1. OneOCR (Ham Okuma)")
    if log_missing and durum_present:
        # _log yok ama _DURUM dolu → film İŞLENMİŞ, log silinmiş/taşınmış. _DURUM'dan oku.
        A("ℹ️ _log.jsonl yok ama _DURUM.json mevcut → film **İŞLENDİ**, olay-logu silinmiş/taşınmış. Veriler _DURUM.json'dan okundu.")
        A(f"- Satır sayısı (_DURUM): **{durum.get('ocr_lines','?')}**  |  Bucket: **{durum.get('ocr_bucket','?')}**")
        A(f"- OCR süresi (_DURUM): {_sn(timings.get('ocr'))}")
    elif log_missing and not durum_present:
        A("⚠ Ne _log.jsonl ne _DURUM.json var — bu klasör pipeline'dan geçmemiş veya tamamen boşaltılmış.")
    else:
        A(f"- Satır sayısı: **{ocr_lines}**  |  Bucket: **{ocr_bucket}**  |  Motor: {ocr_engine}")
        A(f"- Süre: {_sn(ocr_dur)}")
        if ham_lines:
            A(f"- Ham satırlardan örnek (ilk {min(6,len(ham_lines))} satır):")
            for ln in ham_lines[:6]:
                A(f"  > `{ln[:80]}`")
        else:
            A("- ⚠ stitch/ocr_ham.txt yok (ham OCR artefaktı mevcut değil)")

    # Stitch QC
    if stitch_qc:
        A(f"- Stitch QC: {json.dumps(stitch_qc, ensure_ascii=False)[:200]}")

    # 2. VL
    A("")
    A("### 2. VL Yedek (Gemma Vision)")
    if log_missing:
        A("- ⚠ _log.jsonl yok — VL'nin koşup koşmadığı bilinemiyor (olay-logu eksik, KÖR NOKTA)")
    elif not vl_kosuldu:
        A("- **Koşmadı** (QC1-RED tetiklenmedi; extractor yönetmeni buldu)")
    else:
        A(f"- **KOŞTU** — QC1 yönetmeni boş buldu → VL fallback tetiklendi")
        A(f"- VL yönetmen: {_nl(vl_yon)}")
        A(f"- VL cast eki: {len(vl_cast_sup) if vl_cast_sup else 0} kişi")
        A(f"- Süre: {_sn(vl_dur)}")
        if "credit_qc1_failed" in ev:
            A("- VL sonrası QC1 **tekrar RED** → KONTROL'e gönderildi")

    # 3. Database/KB validate
    A("")
    A("### 3. Database / KB / XML Doğrulama (credit_validate)")
    if not val_yon and not val_res:
        if log_missing and durum_present:
            A("⚠ _log.jsonl yok — credit_validate olayı izlenemiyor. _DURUM.neden'den KB/XML kararı:")
            for n in (durum.get("neden") or []):
                A(f"  - {n}")
        else:
            A("⚠ credit_validate olayı _log.jsonl'da yok — KB doğrulama loglanmamış")
    else:
        A(f"- Yönetmen status: **{val_status}**  |  Güven: {val_conf}")
        if src_confirm:
            A(f"- Teyit kaynakları: {src_confirm}")
        else:
            A("- ⚠ sources_confirm boş (hiçbir kaynak teyit etmedi)")
        if conflict_cands:
            A(f"- Çelişki adayları: **{conflict_cands}** ← bu yüzden BAYRAK")
        yon_notes = val_yon.get("notes") or []
        if yon_notes:
            A(f"- Notlar: {' | '.join(yon_notes)}")
        # cast
        cast_val = val_cast.get("value") or []
        cast_notes = val_cast.get("notes") or []
        A(f"- Cast: {len(cast_val)} kişi — {_nl(cast_val)}")
        if cast_notes:
            A(f"  Cast notlar: {' | '.join(cast_notes[:4])}")
        # KB kaynakları (tek-kaynaktan tutarlı durum)
        A(f"- IMDb yönetmen: {imdb_durum}")
        A(f"- Wiki yönetmen: {wiki_durum}")
        # XML (tutarlı xml_sonuc — sources_confirm + notes birlikte değerlendirildi)
        A(f"- XML çapraz-kontrol: {xml_sonuc}")

    # 4. Master-PNG
    A("")
    A("### 4. Master-PNG")
    A(f"- Durum: {master_st}")
    if jdebug.exists():
        A(f"- Debug klasörü: {jdebug}  ({jdebug_str})")
    else:
        A(f"- {jdebug_str}")
    A("- ⚠ KÖR NOKTA: master-PNG oluşturma olayı _log.jsonl'a YAZILMIYOR (manifest'ten çıkarıyoruz)")

    # 5. JENERİK BAŞLANGIÇ-SEÇME SİSTEMİ (B — tam akış)
    A("")
    A("### JENERİK BAŞLANGIÇ-SEÇME SİSTEMİ")
    # GİRİŞ tespiti
    if jen_opening.get("summary") or jen_opening.get("found") is not None:
        gf = jen_opening.get("found")
        A(f"- **GİRİŞ jenerik** (credit_detect_opening): tespit={'EVET' if gf else 'HAYIR'}"
          + (f"  tip={jen_opening.get('type')}  conf={jen_opening.get('conf')}" if gf else ""))
        if jen_opening.get("start_sec") is not None:
            A(f"  - pencere: {jen_opening.get('start_sec')}s–{jen_opening.get('end_sec')}s")
        if jen_opening.get("summary"):
            A(f"  - log: {jen_opening['summary'][:130]}")
    else:
        A("- **GİRİŞ jenerik**: ⚠ credit_detect_opening olayı yok")
    # ÇIKIŞ tespiti
    if jen_closing.get("summary") or jen_closing.get("found") is not None:
        cf = jen_closing.get("found")
        A(f"- **ÇIKIŞ jenerik** (credit_detect_closing): tespit={'EVET' if cf else 'HAYIR'}"
          + (f"  tip={jen_closing.get('type')}  conf={jen_closing.get('conf')}" if cf else ""))
        if jen_closing.get("start_sec") is not None:
            A(f"  - pencere: {jen_closing.get('start_sec')}s–{jen_closing.get('end_sec')}s")
        if jen_closing.get("summary"):
            A(f"  - log: {jen_closing['summary'][:130]}")
    else:
        A("- **ÇIKIŞ jenerik**: ⚠ credit_detect_closing olayı yok")
    if close_back_ev:
        A(f"- **Kapanış geri-uzatma** (credit_detect_close_back): {(close_back_ev.get('summary') or '')[:130]}")
    # HAVUZ sistemi
    A("- **HAVUZ sistemi** (frames/jenerik_detection.json):")
    if jen_info["found"]:
        A(f"  - çalıştı: **EVET**  |  status={jen_status}  |  motor={jen_motor or '⚠ ocr_mode yok'}")
        if havuz_olustu:
            A(f"  - **HAVUZ OLUŞTU**: {jen_pool} kare (girdi {jen_input} kareden), accepted={jen_accepted}")
        elif havuz_birakti:
            A(f"  - **HAVUZ BIRAKTI** (not promoted): pool_frames={jen_pool}, accepted={jen_accepted} → havuz yok")
        A(f"  - start={jen_start_file}@pos{jen_start_pos}  conf={jen_conf}  süre={_sn(jen_dur)}")
        if jen_reason:
            A(f"  - sebep: {jen_reason[:140]}")
        if pool_ev:
            A(f"  - havuz olayı (jenerik_pool_completed): {(pool_ev.get('summary') or '')[:120]}")
    else:
        A("  - çalıştı: **HAYIR / iz yok** (jenerik_detection.json bu filmde mevcut değil)")
    # AKIŞ ANLATIMI (net cümle, master-PNG ile bağ)
    A(f"- **AKIŞ**: {jen_akis}")

    # ── QC1 + QC2 (A — ikisi de tam) ────────────────────────────────────
    A("")
    A("### QC1 + QC2 (Kalite Kontrol)")
    # --- QC1 ---
    A("**QC1 (künye okunabilirlik kapısı — OCR/VL):**")
    A(f"- Sonuç: {qc1_summary_str[:220]}")
    if not (qc1_red_ev or qc1_fail_ev or qc1_pass_ev):
        if val_qc1:
            A(f"- validate.qc1: flag={qc1_flag}  needs_reread={qc1_needs}  reason={qc1_reason}")
        if log_missing:
            A("- ⚠ _log yok → QC1 olay-izi mevcut değil (kör nokta)")
        else:
            A("- ℹ️ Ayrı credit_qc1_* olayı yok → QC1 sessiz geçti (RED tetiklenmedi)")
    # --- QC2 ---
    A("")
    A("**QC2 (kimlik-kilidi / OCR-otorite / qc_block):**")
    qc2_var = False
    # 1) otorite_audit (OCR-otorite kararı)
    if otorite_audit:
        qc2_var = True
        A("- **OCR-otorite denetimi** (_DURUM.otorite_audit):")
        A(f"  - raw_groundtruth_used={otorite_audit.get('raw_groundtruth_used')}  |  ocr_authority_violation={otorite_audit.get('ocr_authority_violation')}")
        def _oa_list(key):
            v = otorite_audit.get(key)
            return v if isinstance(v, list) else []
        od = _oa_list("ocr_dropped")
        kf = _oa_list("kb_floor_added")
        fd = _oa_list("fuzzy_dups")
        sf = _oa_list("s5_form_overwrites")
        if od:
            A(f"  - OCR'dan DÜŞÜRÜLEN (kb/web yok): {_nl(od)}")
        if kf:
            A(f"  - KB-floor EKLENEN (kb-fill): {_nl(kf)}")
        if fd:
            A(f"  - fuzzy tekrar temizlenen: {_nl(fd)}")
        if sf:
            A(f"  - s5 form-overwrite: {_nl(sf)}  (confirmed={otorite_audit.get('s5_form_overwrite_confirmed')})")
        if not (od or kf or fd or sf):
            A("  - (hiç düşürme/ekleme/overwrite yok — OCR çıktısı olduğu gibi korundu)")
    # 2) qc_block gerekçeleri (neden[] içinden)
    if qc_block_satirlari:
        qc2_var = True
        A("- **qc_block kararları** (kimlik-kilidi/garble-gate, _DURUM.neden'den):")
        for q in qc_block_satirlari:
            A(f"  - {q}")
    # 3) routed_kontrol eventi
    if routed_ev:
        qc2_var = True
        rk = route.get("kontrol_tip")
        A(f"- **KONTROL yönlendirme** (routed_kontrol): kontrol_tip={rk}  folder={route.get('folder')}")
    if not qc2_var:
        A("- ℹ️ QC2 ek-kararı yok (kimlik temiz kilitlendi veya bu film QC2-blok tetiklemedi)")
    # 4) QC2-web kimlik (adimlar.qc2_web) — KÖR NOKTA
    A("- ⚠ **QC2-web kimlik** (adimlar.qc2_web: method/imdb_id/web_yonetmen) artefakta **yapısal persist EDİLMİYOR** — kör nokta")

    # --- Qwen final QC (QC2 başlığı altında topla) ---
    A("")
    A("**Qwen final-QC (deterministik bütünlük kapısı):**")
    if qwen_qc:
        A(f"- yonetmen_var: {qwen_qc.get('yonetmen_var')}  |  oyuncu_sayisi: {qwen_qc.get('oyuncu_sayisi')}")
        A(f"- yapimci_var: {qwen_qc.get('yapimci_var')}  |  afis_var: {qwen_qc.get('afis_var')}  |  ses_dil_var: {qwen_qc.get('ses_dil_var')}")
        A(f"- hepsi_buyuk_harf: {qwen_qc.get('hepsi_buyuk_harf')}  |  turkce_karakter_bozuk: {qwen_qc.get('turkce_karakter_bozuk_var')}")
        A(f"- latin_disi_alfabe: {qwen_qc.get('latin_disi_alfabe_var')}  |  yabanci_ad_ascii_degil: {qwen_qc.get('yabanci_ad_ascii_degil')}")
        if qwen_qc.get("notlar"):
            A(f"- Notlar: {qwen_qc['notlar']}")
        if qwen_uyari:
            for uw in qwen_uyari:
                A(f"- UYARI: {uw}")
    else:
        A("- ⚠ qwen_qc verisi yok")

    # 8. ASR
    A("")
    A("### 8. ASR")
    asr_ev = ev.get("asr_completed") or {}
    det_asr2 = _det(asr_ev)
    if log_missing and durum_present:
        A(f"- (_DURUM) durum={durum.get('asr_status','?')}  |  Segment: {durum.get('asr_segments','?')}  |  Karakter: {durum.get('transcript_chars','?')}")
        A(f"- ASR süresi (_DURUM): {_sn(timings.get('asr'))}")
    else:
        A(f"- Segment: {asr_seg}  |  Süre: {_sn(asr_dur)}")
        A(f"- Profil: {det_asr2.get('profile_used','?')}  |  Fallback: {det_asr2.get('fallback_triggered','?')}")
        A(f"- Karakter: {durum.get('transcript_chars','?')}")

    # ── KARAR GEREKÇESİ ─────────────────────────────────────────────────
    sec("⚖️ KARAR GEREKÇESİ (kim-ne-neden)")

    # ── C) TEYİT-AKIŞI: yönetmen "bu isim neden burada / neden boş" ───────
    # Tek-kaynaktan türetilmiş durumları kullan (_imdb_dir/_wiki_dir/_src/xml_destekledi)
    # OCR/validate yönetmeni gerçekten OKUDU mu? (final-dolu cast-sızıntısı OLABİLİR, ayrı tut)
    ocr_yon_okudu = bool(ct_yon or val_yon_val)
    final_dolu = bool(fin_yon_str and not fin_empty)
    dis_teyit_var = bool(_src or xml_destekledi is True)  # sources_confirm gerçek teyit kaynağıdır

    def _teyit_cumlesi() -> str:
        # OCR/validate okuyamadı AMA final dolu → cast-sızıntısı/v4-doldurma
        if (not ocr_yon_okudu) and final_dolu:
            return (f"⚠ OCR/validate yönetmeni **okuyamadı** (status={val_status}) ama final alan DOLU "
                    f"→ isim OCR'dan değil **v4/cast-sızıntısından** geldi (bkz. Sızıntı analizi) → şüpheli")
        # OCR boş + final de boş → deferans
        if (not ocr_yon_okudu) and (not final_dolu):
            return "OCR okuyamadı → alan **BOŞ bırakıldı (deferans)** — uydurma yapılmadı"
        # Çelişki (XML çelişti)
        if xml_destekledi is False or val_status == "CELISKI" or conflict_cands:
            aday = conflict_cands or ["?"]
            return f"⚠ **XML çelişti** (aday: {aday}), OCR okuduğu isim esas alındı → **bayrak/KONTROL**"
        # Teyit geldi (sources_confirm dolu)
        if dis_teyit_var:
            kaynaklar = list(_src) if _src else (["XML"] if xml_destekledi is True else [])
            return f"✓ **{', '.join(kaynaklar) or 'dış kaynak'} teyit etti** → güvenle yazıldı"
        # HİÇ teyit yok ama OCR okudu → kendi güveniyle
        return (f"ℹ️ **Film teyidi gelmedi** (XML/Wiki/IMDb yok) → OCR **KENDİ GÜVENİYLE** yazdı "
                f"(güven: {ct_guven})")

    A(f"- **Yönetmen**: `{fin_yon_str or '—'}`")
    A(f"  - okuma: extractor={_nl(ct_yon)}  validate_status={val_status} (güven {val_conf})")
    A(f"  - dış-teyit: XML={xml_sonuc}  |  IMDb={imdb_durum}  |  Wiki={wiki_durum}  |  sources_confirm={_src or '(boş)'}")
    A(f"  - **SONUÇ**: {_teyit_cumlesi()}")

    # Yapımcı teyit-akışı (qwen_qc.yapimci_var üzerinden — yapısal isim persist edilmiyor)
    yapimci_var = qwen_qc.get("yapimci_var")
    yapimci_qc_block = [q for q in qc_block_satirlari if "yapım" in q.lower() or "producer" in q.lower() or "kişi kapısı" in q.lower()]
    yapimci_neden = [n for n in neden_list if isinstance(n, str) and ("yapımcı" in n.lower() or "producer" in n.lower() or "yapım ek" in n.lower())]
    A(f"- **Yapımcı**: PDF'te var={yapimci_var}")
    if yapimci_neden or yapimci_qc_block:
        for n in (yapimci_neden + yapimci_qc_block):
            A(f"  - karar-izi: {n}")
        A("  - **SONUÇ**: yapımcı alanında karar/filtre uygulandı (yukarıdaki ize bakın)")
    elif yapimci_var:
        A("  - **SONUÇ**: ✓ yapımcı yazıldı (ayrı dış-teyit izi loglanmıyor — yapısal kaynak yok)")
    else:
        A("  - **SONUÇ**: ℹ️ yapımcı alanı boş/yok → ⚠ yapımcı isim-kaynağı yapısal persist edilmiyor (kör nokta)")

    # ── İki cast listesi: validate-aşaması vs final-teknik-çıktı ──────────
    val_cast_list = val_cast.get("value") or []
    fin_cast_list = fk["cast"] or []
    A("- **Oyuncular** — iki ayrı liste (kaynakları farklı):")
    A(f"  - **validate-aşaması cast** ({len(val_cast_list)} kişi): {_nl(val_cast_list)}")
    A(f"  - **final-teknik-çıktı cast** ({len(fin_cast_list)} kişi, _teknik.txt): {_nl(fin_cast_list)}")
    # Fark var mı? (büyük/küçük + boşluk normalize ederek karşılaştır)
    def _norm_set(lst):
        return {re.sub(r"\s+", " ", x).strip().upper() for x in lst}
    if val_cast_list and fin_cast_list:
        sv, sf = _norm_set(val_cast_list), _norm_set(fin_cast_list)
        if sv != sf:
            sayi_fark = len(fin_cast_list) - len(val_cast_list)
            neden = []
            if sayi_fark != 0:
                neden.append(f"sayı farkı {sayi_fark:+d}")
            sadece_val = sv - sf
            sadece_fin = sf - sv
            if sadece_val:
                neden.append(f"yalnız validate'te: {_nl(list(sadece_val))}")
            if sadece_fin:
                neden.append(f"yalnız final'de: {_nl(list(sadece_fin))}")
            A(f"  - ⚠ **iki liste farklı**: {' | '.join(neden)} → v4-finalize/KB cast düzeltmesi listeyi değiştirmiş (ADIM-5 kör nokta)")
        else:
            A("  - ✓ iki liste tutarlı (yalnız büyük/küçük-harf farkı olabilir)")
    elif val_cast_list or fin_cast_list:
        A("  - ⚠ listelerden biri boş, diğeri dolu → karşılaştırma yapılamadı")
    else:
        # iki liste de boş (genellikle _log + _teknik.txt yok) → qwen_qc sayısına düş
        qc_oyuncu = qwen_qc.get("oyuncu_sayisi")
        if qc_oyuncu:
            A(f"  - ⚠ İzlenebilir cast listesi yok (_teknik.txt/_log eksik); _DURUM.qwen_qc'ye göre PDF'te **{qc_oyuncu} oyuncu** var (isimler bu araçtan görünmüyor — kör nokta)")
        else:
            A("  - ⚠ Hiçbir kaynakta cast verisi yok")

    A(f"- **Sızıntı analizi**: {sizinti_notu}")

    A("")
    A("**Neden listesi (_DURUM.json):**")
    for n in karar_gerekce:
        A(f"- {n}")

    A("")
    A(f"**Route detayı**: tier={route_tier}  |  kontrol_tip={route.get('kontrol_tip')}  |  folder={route.get('folder')}")
    agir = route.get("agir") or []
    hafif = route.get("hafif") or []
    if agir:
        A(f"  Ağır kusurlar: {agir}")
    if hafif:
        A(f"  Hafif kusurlar: {hafif}")

    # ── SONUÇ ──────────────────────────────────────────────────────────
    sec("✅ SONUÇ")

    A(f"**Film**: {name}")
    A(f"**TRT-ID**: {trt_id}")
    A(f"**Final Karar**: {karar}  (route={route_tier})")
    A(f"**Yönetmen (final)**: {fin_yon_str or '— OKUNAMADI'}")
    A(f"**Oyuncular (ilk 6)**: {_nl(fk['cast'])}")
    A(f"**Toplam Süre**: {_sn(toplam)}")
    A(f"**Teslim**: {durum.get('teslim','?')}")
    A("")
    A("**Neden bu karar:**")
    for n in karar_gerekce:
        A(f"- {n}")

    # ── KÖR NOKTALAR ───────────────────────────────────────────────────
    sec("🕳 KÖR NOKTALAR (loglanmayan / eksik instrumentation)")
    A("- **v4 dolgu kararı**: tek_film_kunye / v4-finalize aşamasında KB'dan hangi yönetmen çekildiği loglanmıyor (ADIM 5)")
    A("- **Master-PNG olayı**: oluşturma/başarı/boyut bilgisi log'a yazılmıyor; yalnız manifest'ten çıkarıyoruz")
    A("- **XML detayı**: XML'in hangi aday(lar)ı sunduğu ve kabul/red gerekçesi tam olarak credit_validate.result.yonetmen.notes'a sıkıştırılmış, ayrı olay yok")
    A("- **IMDB/Wiki arama sonucu**: strength=None, key=None olunca 'aranmadı mı, bulunamadı mı' belirsiz")
    A("- **QC2-web kimlik** (adimlar.qc2_web: method/imdb_id/web_yonetmen): hiçbir artefakta yapısal persist edilmiyor — yalnız qc_block metin-gerekçesi kalıyor")
    A("- **Yapımcı isim-kaynağı**: yapımcı için dış-teyit/isim-kaynağı yapısal loglanmıyor (yalnız qwen_qc.yapimci_var bool'u var)")
    A("- **ocr_ham.txt**: stitch/ocr_ham.txt bazı filmlerde eksik — ham satır listesi kör nokta")
    A("- (NOT: QC1 'geçti' artık credit_qc1_passed eventiyle loglanıyor — bu kör nokta KAPANDI)")

    # ── ÜRETİM BİLGİSİ ─────────────────────────────────────────────────
    A("")
    A("---")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    A(f"*Üretildi: karar_gunlugu.py — {now_str}*")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# TEK FİLM / --all MOD
# ═══════════════════════════════════════════════════════════════════════════

def process_one(film: Path, dry: bool = False) -> tuple[str, bool, str]:
    """Bir filmi işle. (film_adi, başarı, mesaj) döndür."""
    try:
        content = build_gunluk(film)
        out_path = film / OUTPUT_FILE
        if not dry:
            out_path.write_text(content, encoding="utf-8")
            return (film.name, True, str(out_path))
        else:
            return (film.name, True, "(dry-run, yazılmadı)")
    except Exception as exc:
        return (film.name, False, f"HATA: {exc}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Kullanım:")
        print('  python scripts/karar_gunlugu.py "BÜYÜK RESTAURANT"')
        print('  python scripts/karar_gunlugu.py "1987-0251"')
        print('  python scripts/karar_gunlugu.py --all')
        print('  python scripts/karar_gunlugu.py --all --dry')
        return 2

    dry = "--dry" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]

    if "--all" in argv:
        film_dirs = sorted([d for d in DB.iterdir() if d.is_dir()], key=lambda d: d.name)
        print(f"{len(film_dirs)} film işlenecek{'  (DRY-RUN)' if dry else ''}...")
        ok = 0
        fail = 0
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(process_one, fd, dry): fd for fd in film_dirs}
            for fut in as_completed(futs):
                name, success, msg = fut.result()
                if success:
                    ok += 1
                    print(f"  OK  {name}  →  {msg}")
                else:
                    fail += 1
                    print(f"  !! {name}  →  {msg}")
        print(f"\nBitti: {ok} OK, {fail} hata")
        return 0 if fail == 0 else 1

    # Tek film
    if not args:
        print("Film adı veya --all gerekli.")
        return 2

    film = _find_film(args[0])
    if not film:
        print(f"Film bulunamadı: {args[0]!r}")
        return 1

    content = build_gunluk(film)
    out_path = film / OUTPUT_FILE
    if not dry:
        out_path.write_text(content, encoding="utf-8")
        print(f"Yazıldı: {out_path}")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
