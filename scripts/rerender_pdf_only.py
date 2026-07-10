# -*- coding: utf-8 -*-
"""rerender_pdf_only.py — bir filmin künye PDF'ini MEVCUT OCR'dan GÜNCEL pipeline kararlarıyla yeniden üret.

AMAÇ: OCR'ı YENİDEN KOŞMADAN (frames/audio/ffmpeg/venvs/whisper ATLA) bir Database film klasörünün
künye PDF'ini bugünkü pipeline mantığıyla (MITAS_QC_BLOCK temizle+doldur+karar + dublaj-rol filtresi)
yeniden render et. "OCR ne okuduysa O KANUN" — mevcut ocr/<job>/kunye.txt METNİ yeniden PARSE edilir
(LLM rol-eşleştirme; bu re-OCR DEĞİL), dublaj/asistan-yönetmen rolleri credit_text_read içinde elenir,
sonra v4 düzen + qc_block ile temiz PDF basılır.

ÇALIŞMA PRENSİBİ (kişileştirme): tek_film_kunye.py ZATEN bu işi yapan kişidir — ona "--video-credits
VERME" dersek, kendisi gidip ocr/<job>/kunye.txt'i okur (read_credits_auto → dublaj-filtresi orada),
kunye_teslim.md'den özet/kanal/başlığı alır, MITAS_QC_BLOCK=1 ile temizleyip PDF basar ve bir rapor
JSON döker. Biz sadece (a) doğru klasörü/başlığı buluruz, (b) onu geçici PDF'e bastırırız, (c) başarılı
olursa pdf/kunye.pdf üzerine atomik replace + kök '<TRT> <BAŞLIK>.pdf/.txt' yüzeyleriz, (d) _DURUM.json'a
yeni kararı yazıp eskisini karar_onceki olarak saklarız. Bir film çökerse mevcut PDF'e DOKUNMAYIZ.

KULLANIM (GLOBAL python ile — tek_film_kunye reportlab'ı global'de):
  python scripts/rerender_pdf_only.py --folder "Database/KAN VE SİLAH 1969-..."   # tek film
  python scripts/rerender_pdf_only.py --trt 1969-0077-1-0000-00-1                  # TRT ile bul
  python scripts/rerender_pdf_only.py --all --limit 3 --dry-run                    # tara (DRY varsayılan)
  python scripts/rerender_pdf_only.py --all --apply                                # GERÇEK yaz (--all DRY default)

KISITLAR: OCR'ı ASLA yeniden koşmaz. Mevcut pipeline kodunu DEĞİŞTİRMEZ (yalnız bu yeni dosya).
Fail-safe: temp'e yazar, rc==0 + PDF>10KB ise replace; aksi halde mevcut PDF korunur.
"""
from __future__ import annotations
import argparse, datetime, json, os, re, shutil, subprocess, sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
DB_ROOT = PROJECT_ROOT / "Database"
EXPORT_ROOT = PROJECT_ROOT / "Mitas Output" / "export"
EXPORT_ONAYLI = EXPORT_ROOT / "ONAYLI"
EXPORT_KONTROL = EXPORT_ROOT / "KONTROL"
# tek_film_kunye reportlab'ı global python'da → V4 render orada koşmalı (venv ocr DEĞİL).
PY_PDF = Path(r"C:\Users\TRT03\AppData\Local\Programs\Python\Python310\python.exe")
if not PY_PDF.exists():
    PY_PDF = Path(sys.executable)   # fail-safe: global yoksa mevcut yorumlayıcı (testte)
V4_TIMEOUT = int(os.environ.get("MITAS_V4_TIMEOUT", "900"))

# mitas_pipeline'ı MODÜL olarak içe al → file_base/surface_deliverables/surface_logs YENİDEN-KULLAN
# (yüzeyleme mantığını kopyalamadan). mitas_pipeline top-level'da ağır iş yapmaz (stdlib + best-effort).
sys.path.insert(0, str(HERE))
try:
    import mitas_pipeline as _mp
except Exception as _e:  # noqa: BLE001
    sys.stderr.write(f"[FATAL] mitas_pipeline import edilemedi: {_e}\n")
    _mp = None

# credit_severity_router: qc_block gerekçelerinden Hazır/Kontrol kararını ESKİ pipeline ile AYNI türet.
try:
    import credit_severity_router as _router
except Exception:  # noqa: BLE001
    _router = None


def _load_clip(folder: Path) -> dict:
    """clip.json → trt/title/profile/latest_ocr_job. Türkçe-İ tuzağı: folder gerçek (clip.json'dan değil)."""
    cj = {}
    p = folder / "clip.json"
    if p.exists():
        try:
            cj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cj = {}
    trt = (cj.get("trt_id") or "").strip()
    title = (cj.get("title") or "").strip()
    profile = (cj.get("profile") or "film").strip() or "film"
    bolum = cj.get("bolum")
    job = ((cj.get("modules") or {}).get("ocr") or {}).get("latest_job_id")
    return {"trt": trt, "title": title, "profile": profile, "bolum": bolum, "ocr_job": job, "raw": cj}


def _ocr_txt_path(folder: Path, job: str | None) -> Path | None:
    """ocr/<job>/kunye.txt (ham OCR metni). job verilse onu, yoksa en yeni kunye.txt'i seç."""
    if job:
        cand = folder / "ocr" / job / "kunye.txt"
        if cand.exists():
            return cand
    hits = sorted((folder / "ocr").glob("*/kunye.txt"), key=lambda x: x.stat().st_mtime) \
        if (folder / "ocr").exists() else []
    return hits[-1] if hits else None


def _md_meta(folder: Path) -> dict:
    """pdf/kunye_teslim.md'den yıl/orijinal-ad ipuçları (tek_film_kunye özet/kanal/başlığı KENDİ okur)."""
    out = {"year": None, "original": None}
    md = folder / "pdf" / "kunye_teslim.md"
    if not md.exists():
        return out
    import re
    t = md.read_text(encoding="utf-8", errors="replace")
    # TRT-ID içindeki ilk 4-hane yıl (1969-0077-... → 1969) — tek_film_kunye --year'ı KB cross-check'e iletir.
    m = re.search(r"ID:\s*(\d{4})", t)
    if m:
        out["year"] = m.group(1)
    return out


def _video_credits_from_trace(folder: Path) -> dict | None:
    """Üretim koşusunda v4'e verilen doğru video_okuma girdisini PDF-only rerender'a taşır."""
    trace = folder / "debug_trace" / "trace.jsonl"
    if not trace.exists():
        return None
    found = None
    try:
        with trace.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    ev = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                if ev.get("stage") != "v4" or ev.get("event") != "candidate_read":
                    continue
                subj = ev.get("subject") or {}
                if subj.get("field") != "video_okuma":
                    continue
                after = subj.get("after") or {}
                if not isinstance(after, dict):
                    continue
                vc = {
                    "yonetmen": after.get("yonetmen") or after.get("yon") or [],
                    "cast": after.get("cast") or after.get("cast_okunan") or [],
                    "yapimci": after.get("yapimci") or [],
                    "guven": after.get("guven") or "trace-video-okuma",
                }
                if vc["yonetmen"] or vc["cast"] or vc["yapimci"]:
                    found = vc
    except Exception:  # noqa: BLE001
        return None
    return found


def _export_fixed_pdf(trt: str, title: str, pdf_src: Path) -> dict:
    """Düzgün üretilmiş Hazır PDF'i ONAYLI'ya koy, eski KONTROL kopyasını kuyruktan çıkar."""
    res = {"export_synced": False, "onayli": None, "kontrol_moved": []}
    if not trt or not pdf_src.exists() or pdf_src.stat().st_size <= 10000:
        res["export_error"] = "geçerli pdf/trt yok"
        return res
    EXPORT_ONAYLI.mkdir(parents=True, exist_ok=True)
    EXPORT_KONTROL.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r'[\\/:*?"<>|]+', " ", (title or "")).strip()
    dest = EXPORT_ONAYLI / f"{trt} {safe_title}_onaylı.pdf"
    shutil.copy2(pdf_src, dest)
    if not dest.exists() or dest.stat().st_size <= 10000:
        res["export_error"] = "ONAYLI kopyası doğrulanamadı"
        return res
    backup = EXPORT_ROOT / "_KONTROL_duzeltilen_yedek" / datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for old in sorted(EXPORT_KONTROL.glob(f"*{trt}*.pdf")):
        backup.mkdir(parents=True, exist_ok=True)
        target = backup / old.name
        shutil.move(str(old), str(target))
        res["kontrol_moved"].append(str(target))
    res["export_synced"] = True
    res["onayli"] = str(dest)
    return res


def _find_folders(args) -> list[Path]:
    """--folder / --trt / --all → işlenecek Database klasör listesi."""
    if args.folder:
        f = Path(args.folder)
        if not f.is_absolute():
            f = (PROJECT_ROOT / args.folder)
        return [f] if f.exists() else []
    if args.trt:
        hits = []
        for p in DB_ROOT.glob("*/clip.json"):
            try:
                cj = json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            if (cj.get("trt_id") or "").strip() == args.trt.strip():
                hits.append(p.parent)
        return hits
    if args.all:
        # OCR'ı OLAN + teslim md'si OLAN film klasörleri (rerender anlamlı olanlar)
        out = []
        for p in sorted(DB_ROOT.glob("*/clip.json")):
            folder = p.parent
            if (folder / "pdf" / "kunye_teslim.md").exists() and (folder / "ocr").exists():
                out.append(folder)
        return out
    return []


def _derive_karar(qcb: dict, qwen_uyari: list | None = None):
    """qc_block sonucu (karar/tip/gerekceler/floor) → (karar, route_info). qc_block'un KENDİ kararı
    OTORİTE (pipeline aynısını üretir: KONTROL/tip=OZET/CAST/... veya HAZIR). Yalnız credit/qc_block
    temelli yeniden-karar — ASR/OCR-bucket/genre kapıları re-eval EDİLMEZ (bunlar mevcut _DURUM'da kalır,
    aşağıda 'onceki_disi_nedenler' olarak korunur). Bu rerender'ın amacı künye-temizliği; tam-pipeline değil."""
    qcb = qcb or {}
    qwen_uyari = qwen_uyari or []
    gerekceler_raw = list(qcb.get("gerekceler") or [])
    gerekceler = list(gerekceler_raw)
    person_teyit = any("kişi-teyit:" in str(u).lower() for u in qwen_uyari)
    if person_teyit and gerekceler:
        bastir = ("kimlik", "zayıf-teyit", "versiyon cast-teyitsiz",
                  "yönetmen doğrulama: kaynak-çelişkisi")
        gerekceler = [g for g in gerekceler if not any(b in str(g) for b in bastir)]
    floor = qcb.get("floor") or {}
    qcb_karar = (qcb.get("karar") or "").strip().upper()
    qcb_tip = qcb.get("tip")
    if person_teyit and gerekceler_raw and not gerekceler and qcb_karar == "KONTROL":
        qcb_karar = "AUTO-FIX" if qcb_tip else ""
    reasons = ["qc_block: " + g for g in gerekceler]
    floor_fail = bool(floor.get("hedef") == 8 and not floor.get("kabul")
                      and (floor.get("ulasilan", 0) or 0) >= 1)
    # qc_block KONTROL diyorsa OTORİTE → Kontrol (router yalnız klasör-tipi için danışılır).
    karar = "Kontrol" if (qcb_karar == "KONTROL" or floor_fail) else "Hazır"
    route = {"reasons": reasons, "qc_block_karar": qcb_karar or None, "kontrol_tip": qcb_tip}
    if _router is not None:
        _U = qwen_uyari
        sig = {
            "yon_missing": any("yön+yapımcı yok" in g for g in gerekceler),
            "yon_garble": any("yönetmen" in g and ("okunamadı" in g or "garble" in g) for g in gerekceler),
            "yon_fillable": False,
            "wrongfilm_suspect": any(("kimlik kurulamadı" in g) or ("kimlik çelişki" in g) for g in gerekceler),
            "cast_count": 0 if (floor_fail or any("oyuncu yok" in g for g in gerekceler)) else 1,
            "cast_all_garble": any("cast garble" in g for g in gerekceler),
            "ozet_missing": any("özet" in g for g in gerekceler) or qcb_tip == "OZET",
            "non_latin": any("Latin-dışı" in g for g in gerekceler),
            "char_broken": False,
            "char_broken_autofixable": False,
            "afis_missing": any("afiş yok" in u for u in _U),
            "casing_bad": False,
            "foreign_accent": False,
        }
        try:
            r = _router.classify(sig)
            r["reasons"] = reasons
            r["qc_block_karar"] = qcb_karar or None
            route = r
            if r["tier"] == "TEMIZ" and karar != "Kontrol":
                karar = "Hazır"
            elif r["tier"] != "TEMIZ" or r.get("agir"):
                karar = "Kontrol"
        except Exception as e:  # noqa: BLE001
            route["router_error"] = str(e)
    return karar, route


def _current_person_teyit_warning(v4: dict) -> str | None:
    """Pipeline'daki kişi-teyit kapısını rerender'da mevcut v4 listesiyle yeniden hesapla."""
    cast = [str(x).strip() for x in (v4.get("cast_list") or []) if str(x).strip()]
    yon = [str(x).strip() for x in (v4.get("yonetmen_list") or v4.get("yonetmen") or []) if str(x).strip()]
    if len(cast) < 3:
        return None
    try:
        import credit_video_read as _cvr
        kb = _cvr.KB()
        verdicts = [kb.verify(n, "actor") for n in cast]
        onay = sum(1 for v in verdicts if v == "ONAY")
        bilinen = sum(1 for v in verdicts if v != "kayit-yok")
        oran = onay / max(1, len(cast))
        oran_bilinen = onay / bilinen if bilinen else 0.0
        yon_ok = (not yon) or any(kb.verify(n, "director") == "ONAY" for n in yon)
        if (oran >= 0.6 or (bilinen >= 2 and oran_bilinen >= 0.75)) and yon_ok:
            return ("kişi-teyit: cast %d/%d KB-ONAY" % (onay, len(cast))
                    + (", yön KB-ONAY" if yon else ", yön boş")
                    + " → film-KB'siz doğrulama (Çağatay kuralı)")
    except Exception:  # noqa: BLE001
        return None
    return None


def rerender_one(folder: Path, dry_run: bool = True) -> dict:
    """Tek film: tek_film_kunye'yi MEVCUT OCR + qc_block ile temp PDF'e bastır; başarılı+!dry ise yüzeyle.
    ASLA çökmez (her şey try/except); mevcut PDF'i yalnız atomik-replace ile değiştirir."""
    res = {"folder": str(folder), "ok": False, "wrote": False, "dry_run": dry_run}
    try:
        clip = _load_clip(folder)
        trt, title, profile = clip["trt"], clip["title"], clip["profile"]
        res.update(trt=trt, title=title, profile=profile, ocr_job=clip["ocr_job"])
        if not title:
            res["error"] = "clip.json'da title yok"
            return res
        ocr_txt = _ocr_txt_path(folder, clip["ocr_job"])
        if not ocr_txt:
            res["error"] = "ocr/<job>/kunye.txt yok (rerender için kaynak metin gerekli)"
            return res
        res["ocr_txt"] = str(ocr_txt)
        if not (folder / "pdf" / "kunye_teslim.md").exists():
            res["error"] = "pdf/kunye_teslim.md yok"
            return res
        meta = _md_meta(folder)

        # Üretimde v4'e verilen video_okuma girdisi trace'te varsa aynen kullan; yoksa eski davranış:
        # tek_film_kunye OCR metninden yeniden okur.
        tmp_pdf = folder / "pdf" / "kunye_rerender_tmp.pdf"
        cmd = [str(PY_PDF), str(HERE / "tek_film_kunye.py"),
               "--clip", str(folder), "--title", title, "--out", str(tmp_pdf),
               "--profile", profile]
        trace_vc = _video_credits_from_trace(folder)
        if trace_vc:
            cmd += ["--video-credits", json.dumps(trace_vc, ensure_ascii=False)]
            res["video_credits_source"] = "debug_trace/v4/candidate_read"
        if meta.get("year"):
            cmd += ["--year", str(meta["year"])]
        if clip.get("bolum"):
            cmd += ["--bolum", str(clip["bolum"])]

        # Üretim flag setini os.environ'a yükle (setdefault → kullanıcı override'ı ezilmez);
        # snapshot'tan ÖNCE çalışması şart — aksi hâlde QC2/CAST/QC_OTORITE_ROUTE vb. subprocess'e geçmez.
        if _mp is not None:
            _mp._apply_production_defaults()
        env = dict(os.environ)
        env["MITAS_QC_BLOCK"] = "1"   # birleşik QC bloğu (temizle+doldur+karar) — bu rerender'ın ÇEKİRDEĞİ
        env.setdefault("PYTHONIOENCODING", "utf-8")

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=V4_TIMEOUT, env=env)
        except Exception as e:  # noqa: BLE001
            res["error"] = f"tek_film_kunye koşulamadı: {type(e).__name__}: {e}"
            return res
        res["rc"] = r.returncode
        # rapor JSON'ını stdout'tan çöz (indent=2 çok-satır → ilk '{'ten raw_decode)
        rapor = {}
        i = (r.stdout or "").find("{")
        if i >= 0:
            try:
                rapor, _ = json.JSONDecoder().raw_decode((r.stdout or "")[i:])
            except Exception:  # noqa: BLE001
                rapor = {}
        v4 = rapor.get("v4") or {}
        qcblock = (rapor.get("adimlar") or {}).get("qc_block") or {}
        res["qc_block"] = {
            "karar": v4.get("qc_block_karar") or qcblock.get("karar"),
            "tip": v4.get("qc_block_tip") or qcblock.get("kontrol_tip"),
            "gerekceler": v4.get("qc_block_gerekceler") or qcblock.get("gerekceler") or [],
            "floor": v4.get("qc_block_floor") or qcblock.get("floor") or {},
        }
        _stderr = r.stderr or ""
        res["v4_yonetmen"] = v4.get("yonetmen_list") or v4.get("yonetmen") or []
        res["v4_yapimci"] = v4.get("yapimci_list") or v4.get("yapimci") or []
        res["v4_cast_n"] = v4.get("cast") if isinstance(v4.get("cast"), int) else len(v4.get("cast_list") or [])
        res["v4_afis"] = bool(v4.get("afis"))
        try:
            _durum_for_route = json.loads((folder / "_DURUM.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            _durum_for_route = {}
        _qwen_route = list(_durum_for_route.get("qwen_uyari") or [])
        if res["v4_afis"]:
            _qwen_route = [u for u in _qwen_route if "afiş yok" not in str(u).lower()]
        elif not any("afiş yok" in str(u).lower() for u in _qwen_route):
            _qwen_route.append("qwen: afiş yok (deterministik poster_fetch garanti — uyarı)")
        _person_teyit = _current_person_teyit_warning(v4)
        if _person_teyit:
            _qwen_route = [u for u in _qwen_route if "kişi-teyit:" not in str(u).lower()]
            _qwen_route.append(_person_teyit)
        res["qwen_uyari_for_route"] = _qwen_route
        # DUBLAJ/ROL-FİLTRE KANITI: (a) stderr'de rol-atfı düşüş satırı VEYA (b) ham OCR'da dublaj/seslendirme
        # markeri VARDI ama nihai yönetmen o garble adı İÇERMİYOR (filtre temizledi). İki sinyal de yeterli.
        _stderr_sig = ("rol-atfı" in _stderr) or ("yönetmen-dışı rol" in _stderr) or ("dublaj" in _stderr.lower())
        _ocr_dub = False
        try:
            _ocr_blob = ocr_txt.read_text(encoding="utf-8", errors="replace").lower()
            _ocr_dub = any(m in _ocr_blob for m in
                           ("seslendirme yon", "seslendirme yön", "dublaj yön", "dublaj yon", "seslendirme yard"))
        except Exception:  # noqa: BLE001
            _ocr_dub = False
        res["ocr_dublaj_markeri"] = _ocr_dub
        res["dublaj_filtre_uygulandi"] = bool(_stderr_sig or _ocr_dub)

        # yeni kararı türet (qc_block-temelli; qc_block.karar OTORİTE)
        karar_yeni, route = _derive_karar(res["qc_block"], qwen_uyari=_qwen_route)
        res["karar_yeni"] = karar_yeni
        res["route"] = route

        if r.returncode != 0 or not (tmp_pdf.exists() and tmp_pdf.stat().st_size > 10000):
            res["error"] = f"render başarısız (rc={r.returncode}, pdf={tmp_pdf.exists()})"
            res["stderr_tail"] = _stderr[-400:]
            if tmp_pdf.exists():
                try:
                    tmp_pdf.unlink()
                except Exception:  # noqa: BLE001
                    pass
            return res
        res["ok"] = True
        res["tmp_pdf"] = str(tmp_pdf)
        res["tmp_pdf_kb"] = round(tmp_pdf.stat().st_size / 1024, 1)

        if dry_run:
            # DRY: temp'i SİL (mevcut PDF'e dokunma), kararı göster
            try:
                tmp_pdf.unlink()
                png = tmp_pdf.with_name(tmp_pdf.stem + "_onizleme.png")
                if png.exists():
                    png.unlink()
            except Exception:  # noqa: BLE001
                pass
            return res

        # ── GERÇEK YAZIM: atomik replace + kök yüzeyleme + _DURUM.json güncelle ──
        pdf_dst = folder / "pdf" / "kunye.pdf"
        os.replace(str(tmp_pdf), str(pdf_dst))
        # önizleme PNG'sini de taşı (varsa)
        tmp_png = tmp_pdf.with_name(tmp_pdf.stem + "_onizleme.png")
        if tmp_png.exists():
            os.replace(str(tmp_png), str(folder / "pdf" / "kunye_onizleme.png"))
        res["wrote"] = True

        # kök '<TRT> <BAŞLIK>.pdf/.txt' + afis — mitas_pipeline.surface_deliverables YENİDEN-KULLAN.
        # v4_credits = V4 PDF otoriter cast/yön/yapımcı → kök .txt'yi PDF ile HİZALA (propagation fix).
        if _mp is not None:
            try:
                tur_override = (v4.get("tur") or "").strip()
                if tur_override == "—":
                    tur_override = ""
                pdf_info = {"pdf_path": str(pdf_dst),
                            "md_path": str(folder / "pdf" / "kunye_teslim.md")}
                _mp.surface_deliverables(folder, trt, title, pdf_info,
                                         tur_override=tur_override, v4_credits=v4)
                res["surface"] = True
            except Exception as e:  # noqa: BLE001 — yüzeyleme PDF'i bozmaz
                res["surface_error"] = f"{type(e).__name__}: {e}"

        if karar_yeni == "Hazır":
            try:
                res["export"] = _export_fixed_pdf(trt, title, pdf_dst)
            except Exception as e:  # noqa: BLE001 — export senkronu PDF'i bozmaz
                res["export"] = {"export_synced": False, "export_error": f"{type(e).__name__}: {e}"}

        # _DURUM.json: yeni karar/neden yaz, eskisini karar_onceki olarak SAKLA (denetlenebilir iz).
        try:
            dp = folder / "_DURUM.json"
            durum = json.loads(dp.read_text(encoding="utf-8")) if dp.exists() else {}
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            # eski kararı arşivle (önceki rerender izini EZME: zincir tut)
            onceki = {"karar": durum.get("karar"), "neden": durum.get("neden"),
                      "ts": durum.get("ts"), "kaynak": durum.get("rerender_kaynak") or "pipeline"}
            gecmis = durum.get("karar_gecmisi")
            if not isinstance(gecmis, list):
                gecmis = []
            if isinstance(durum.get("karar_onceki"), dict):
                gecmis.append(durum["karar_onceki"])
            gecmis.append(onceki)
            durum["karar_gecmisi"] = gecmis[-20:]
            durum["karar_onceki"] = onceki
            durum["karar"] = karar_yeni
            durum["route"] = route
            durum["neden"] = route.get("reasons") or []
            if karar_yeni == "Hazır":
                _export_onayli = ((res.get("export") or {}).get("onayli")
                                  if isinstance(res.get("export"), dict) else None)
                durum["teslim"] = _export_onayli or str(pdf_dst)
            _qw = list(res.get("qwen_uyari_for_route") or durum.get("qwen_uyari") or [])
            if res.get("v4_afis"):
                _qw = [u for u in _qw if "afiş yok" not in str(u).lower()]
            if isinstance(durum.get("qwen_qc"), dict):
                durum["qwen_qc"]["afis_var"] = bool(res.get("v4_afis"))
                durum["qwen_qc"]["oyuncu_sayisi"] = int(res.get("v4_cast_n") or 0)
                durum["qwen_qc"]["yonetmen_var"] = bool(res.get("v4_yonetmen"))
                durum["qwen_qc"]["yapimci_var"] = bool(res.get("v4_yapimci"))
                if res.get("v4_yapimci") and "yapımcı bilgisi yok" in str(durum["qwen_qc"].get("notlar") or "").lower():
                    durum["qwen_qc"]["notlar"] = ""
            durum["qwen_uyari"] = _qw
            durum["rerender_kaynak"] = "rerender_pdf_only"
            durum["rerender_ts"] = now
            durum["rerender_qc_block"] = res["qc_block"]
            durum["rerender_dublaj_filtre"] = res["dublaj_filtre_uygulandi"]
            durum["ts"] = now
            dp.write_text(json.dumps(durum, ensure_ascii=False, indent=2), encoding="utf-8")
            res["durum_guncellendi"] = True
        except Exception as e:  # noqa: BLE001 — _DURUM yazımı PDF'i bozmaz
            res["durum_error"] = f"{type(e).__name__}: {e}"

        return res
    except Exception as e:  # noqa: BLE001 — film-bazlı tam fail-safe
        res["error"] = f"beklenmeyen: {type(e).__name__}: {e}"
        return res


def main():
    ap = argparse.ArgumentParser(description="Künye PDF'ini MEVCUT OCR'dan güncel kararlarla yeniden üret")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--folder", help="tek Database film klasörü (mutlak veya proje-göreli)")
    g.add_argument("--trt", help="TRT kimliği ile bul (clip.json trt_id)")
    g.add_argument("--all", action="store_true", help="tüm Database filmlerini tara (DRY varsayılan)")
    ap.add_argument("--dry-run", action="store_true", help="PDF yazmadan kararı göster")
    ap.add_argument("--apply", action="store_true", help="--all ile GERÇEK yaz (yoksa --all DRY)")
    ap.add_argument("--limit", type=int, default=0, help="işlenecek film sayısı sınırı (0=hepsi)")
    a = ap.parse_args()

    folders = _find_folders(a)
    if a.limit and a.limit > 0:
        folders = folders[:a.limit]
    if not folders:
        print(json.dumps({"ok": False, "error": "eşleşen klasör yok", "args": vars(a)}, ensure_ascii=False))
        return 2

    # DRY belirleme: --dry-run açıksa DRY. --all GÜVENLİ varsayılan DRY (yazmak için --apply şart).
    if a.dry_run:
        dry = True
    elif a.all:
        dry = not a.apply
    else:
        dry = False   # tek film (--folder/--trt) → gerçek yaz (açıkça --dry-run demedikçe)

    results = []
    for folder in folders:
        r = rerender_one(folder, dry_run=dry)
        results.append(r)
        _wr = "DRY" if dry else ("YAZILDI" if r.get("wrote") else "YAZILMADI")
        _kb = r.get("qc_block", {})
        print(f"[{_wr}] {folder.name} | ok={r.get('ok')} "
              f"karar={r.get('karar_yeni')} qc_block={_kb.get('karar')}/{_kb.get('tip')} "
              f"dublaj_filtre={r.get('dublaj_filtre_uygulandi')} "
              f"yön={r.get('v4_yonetmen')} cast={r.get('v4_cast_n')} "
              + (f"HATA={r.get('error')}" if r.get("error") else ""), file=sys.stderr)

    ozet = {
        "ok": True, "dry_run": dry, "toplam": len(results),
        "render_basarili": sum(1 for x in results if x.get("ok")),
        "yazildi": sum(1 for x in results if x.get("wrote")),
        "cokme": sum(1 for x in results if x.get("error")),
        "results": results,
    }
    print(json.dumps(ozet, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
