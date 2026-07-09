#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""dizi_credit_parse.py — DİZİ MODU: hub → normalize BolumOkuma adaptörü.

Sözleşme: scripts/dizi_SISTEM.md "BolumOkuma şeması" (BAĞLAYICI — sapma yok).
İlkeler:
  • SALT-OKUR: hub artefaktlarına HİÇBİR yazma yapılmaz (dizi katmanı hub'ı okur, seri
    deposu ayrı — seri_kayit.py). Hata durumunda çökme yok: uyarılar listesine yazılır,
    ilgili alanlar boş döner ("okunamadı > yanlış oku").
  • Dilim BİRİNCİL: master_dilim/dilim_oneocr.txt yalnız run-scope damgası tazeyse
    (_pipe_credit_text._dilim_lines kuralının aynısı — bayat dilim başka koşunun
    jeneriğini taşıyabilir). Bayat/yok → en yeni ocr/*/kunye.txt (kare). O da yok → "yok".
  • Parser YENİDEN YAZILMAZ: role_of/is_person/is_company/parse_credits(dizi=True)
    OCR-worktree/pdf-mitas/credit_parse.py'den (importlib) kullanılır; isim eşleme
    credit_crosscheck.name_match (sıkı — substring eşleşmesi kabul edilmez).

API: okuma_topla(clip_dir, bolum_no, trt_id=None) -> BolumOkuma dict
     konuk_ayikla(lines) -> (konuklar, kalan_satirlar)
     stop_kart_suz(lines, dosya_bolum_no) -> (kalan, kart_bolum_no, uyarilar)
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import re
import sys

_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPTS)
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from credit_crosscheck import name_match  # noqa: E402  (scripts-içi; import yan-etkisiz)

# ── OCR-worktree/pdf-mitas/credit_parse.py — importlib ile yüklenir (sözleşme:
#    bu modül sys.path'te DEĞİL; test kalıbı tests/test_credit_crew_leak_gate.py).
_CP_PATH = os.path.join(_ROOT, "OCR-worktree", "pdf-mitas", "credit_parse.py")
_CP_MODNAME = "dizi_credit_parse__credit_parse"


def _cp():
    """credit_parse modülü (tembel + sys.modules önbellekli). Ayrı modül-adı kullanılır ki
    başka test/koşucu yüklemeleriyle (ör. 'credit_parse_under_test') çakışmasın."""
    mod = sys.modules.get(_CP_MODNAME)
    if mod is not None:
        return mod
    spec = importlib.util.spec_from_file_location(_CP_MODNAME, _CP_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_CP_MODNAME] = mod
    spec.loader.exec_module(mod)
    return mod


def _fold(s: str) -> str:
    return _cp().fold(s)


# ── KONUK başlıkları (dizi_SISTEM.md fold-listesi — BİREBİR; karşılaştırma fold sonrası).
KONUK_BASLIKLARI = ("konuk oyuncular", "konuk oyuncu", "konuk sanatci", "konuklar",
                    "bolum oyunculari", "bu bolumun konuklari",
                    "guest starring", "guest stars", "special guest")

# "&" / " ve " birleşik konuk satırı bölme — credit_parse._AMPERSAND_RE ile AYNI desen
# (private üye; modül silinirse/yeniden adlanırsa yerel kopya devreye girer).
_AMP_RE_FALLBACK = re.compile(r"\s*&\s*|\s+ve\s+", re.IGNORECASE)

# ── STOP-KART regexleri (dizi_SISTEM.md): fold SONRASI uygulanır (fold küçük-ASCII üretir).
#    Tam-satır çapalı — "SONER YALÇIN" gibi gerçek isimler ASLA yakalanmaz.
_BOLUM_SONU_RE = re.compile(r"^(\d{1,4})\s*\.?\s*bolum(un)?\s*sonu$")
_DEVAM_RE = re.compile(r"^devam edecek(tir)?$")
_SON_RE = re.compile(r"^son$")


def _konuk_basligi_mi(line: str) -> bool:
    """Satır KONUK bloğu başlığı mı? Fold + kenar-noktalama temizliği sonrası fold-listeyle
    eşitlik; ek olarak boşluksuz kısa Türkçe ek (≤4 karakter: 'konuk sanatcilar' gibi
    çoğul/iyelik) kabul edilir — YENİ kelime eklenmiş satır ('konuk oyuncularin secimi')
    başlık SAYILMAZ (muhafazakâr yorum)."""
    f = _fold(line).strip(" .:-")
    for h in KONUK_BASLIKLARI:
        if f == h:
            return True
        if f.startswith(h):
            kalan = f[len(h):]
            if kalan and " " not in kalan and len(kalan) <= 4:
                return True
    return False


def konuk_ayikla(lines: list[str]) -> tuple[list[str], list[str]]:
    """KONUK bloklarını ayıkla → (konuklar, kalan_satirlar).

    Blok: başlık satırından sonra, credit_parse.role_of(l) != None olan İLK satıra KADAR.
    Blok içinde is_person + not is_company geçen satırlar konuk; "&"/" ve " birleşik satır
    parçalanır (aksi halde 'A & B' tek sahte-isim olurdu). Başlık + konuk satırları
    kalan listeden düşer (başlık fold'u 'oyuncular' içerdiğinden parse_credits'te CAST
    başlığı sanılırdı); kişi-geçmeyen blok satırı (şirket/çöp) kalanda bırakılır —
    parse_credits'in kendi süzgeci eler, burada SİLME kararı verilmez."""
    cp = _cp()
    amp_re = getattr(cp, "_AMPERSAND_RE", _AMP_RE_FALLBACK)
    konuklar: list[str] = []
    kalan: list[str] = []
    blokta = False
    for l in lines:
        if _konuk_basligi_mi(l):
            blokta = True            # yeni blok (blok içindeyken ikinci başlık = blok devam)
            continue
        if not blokta:
            kalan.append(l)
            continue
        if cp.role_of(l) is not None:
            blokta = False           # sonraki rol başlığı bloğu kapatır; satır parse'a kalır
            kalan.append(l)
            continue
        parcalar = [p.strip() for p in amp_re.split(l) if p.strip()]
        adaylar = parcalar if len(parcalar) >= 2 else [l.strip()]
        alinan = False
        for p in adaylar:
            if p and cp.is_person(p) and not cp.is_company(p):
                konuklar.append(p)
                alinan = True
        if not alinan:
            kalan.append(l)
    # fold-anahtarlı dedup (sıra korunur) — aynı konuk iki kartta görünebilir
    gorulen, tekil = set(), []
    for k in konuklar:
        fk = _fold(k)
        if fk and fk not in gorulen:
            gorulen.add(fk)
            tekil.append(k)
    return tekil, kalan


def stop_kart_suz(lines: list[str], dosya_bolum_no: int | None) -> tuple[list[str], int | None, list[str]]:
    """Bölüm-sonu / devam-edecek / SON kartlarını isim-parse'a girmeden düşür.

    Döner: (kalan, kart_bolum_no, uyarilar). Kart no'su dosya parseliyle çelişirse
    'BOLUM_NO_CELISKI: kart=X dosya=Y' uyarısı. Birden çok no'lu kart varsa İLKİ alınır
    (sözleşmede tanımsız → muhafazakâr: ilk görülen)."""
    kalan: list[str] = []
    kart_no: int | None = None
    uyarilar: list[str] = []
    for l in lines:
        f = _fold(l).strip(" .:-!…")
        m = _BOLUM_SONU_RE.match(f)
        if m:
            if kart_no is None:
                kart_no = int(m.group(1))
            continue
        if _DEVAM_RE.match(f) or _SON_RE.match(f):
            continue
        kalan.append(l)
    if kart_no is not None and dosya_bolum_no is not None and kart_no != int(dosya_bolum_no):
        uyarilar.append(f"BOLUM_NO_CELISKI: kart={kart_no} dosya={dosya_bolum_no}")
    return kalan, kart_no, uyarilar


# ─────────────────────────── hub okuma (SALT-OKUR) ───────────────────────────

def _en_yeni_ocr_job(clip_dir: str) -> tuple[str | None, str | None]:
    """En yeni ocr/<job>/ → (job_adi, kunye_txt_yolu|None). Otorite kare-fallback ile aynı:
    önce kunye.txt mtime (bkz. _pipe_credit_text._find_ocr); kunye.txt hiç yoksa dizin
    mtime'ına düşülür (damga karşılaştırması yine yapılabilsin diye)."""
    g = sorted(glob.glob(os.path.join(clip_dir, "ocr", "*", "kunye.txt")),
               key=lambda p: os.path.getmtime(p))
    if g:
        return os.path.basename(os.path.dirname(g[-1])), g[-1]
    dirs = [p for p in glob.glob(os.path.join(clip_dir, "ocr", "*")) if os.path.isdir(p)]
    if dirs:
        d = max(dirs, key=lambda p: os.path.getmtime(p))
        return os.path.basename(d), None
    return None, None


def _dilim_taze_mi(damga: str, job: str | None) -> bool:
    """Run-scope damga kuralı — _pipe_credit_text._dilim_lines'ın AYNISI: meta['ocr_job'],
    en yeni job adı VEYA '-fb' kardeşinin bazıyla eşleşmeli. Job hiç yoksa dilim
    doğrulanamaz → taze SAYILMAZ (bayat dilim riskine karşı muhafazakâr)."""
    if not job:
        return False
    base_job = job[:-3] if job.endswith("-fb") else job
    return str(damga or "") in (base_job, job)


def _satirlar_oku(clip_dir: str) -> tuple[list[str], str, list[str]]:
    """Hub'dan okuma satırları → (satirlar, kaynak, uyarilar). kaynak: master_dilim|kare|yok."""
    uyarilar: list[str] = []
    job, kunye_txt = _en_yeni_ocr_job(clip_dir)
    md = os.path.join(clip_dir, "master_dilim")
    txt = os.path.join(md, "dilim_oneocr.txt")
    meta_p = os.path.join(md, "dilim_oneocr.meta.json")
    if os.path.isfile(txt) and os.path.isfile(meta_p):
        try:
            with open(meta_p, encoding="utf-8", errors="ignore") as h:
                meta = json.load(h) or {}
            damga = str(meta.get("ocr_job") or "")
            if _dilim_taze_mi(damga, job):
                out = []
                with open(txt, encoding="utf-8", errors="ignore") as h:
                    for ln in h.read().splitlines():
                        s = ln.strip()
                        if s and not s.startswith("### DILIM-SINIRI"):
                            out.append(s)
                return out, "master_dilim", uyarilar
            uyarilar.append(f"DILIM_BAYAT: meta={damga or '—'} en_yeni={job or '—'}")
        except Exception as exc:  # noqa: BLE001 — dilim hatası akışı BOZMAZ, kare'ye düşülür
            uyarilar.append(f"DILIM_OKUNAMADI: {type(exc).__name__}: {exc}")
    if kunye_txt and os.path.isfile(kunye_txt):
        try:
            with open(kunye_txt, encoding="utf-8", errors="ignore") as h:
                out = [s.strip() for s in h.read().splitlines() if s.strip()]
            return out, "kare", uyarilar
        except Exception as exc:  # noqa: BLE001
            uyarilar.append(f"KARE_OKUNAMADI: {type(exc).__name__}: {exc}")
    return [], "yok", uyarilar


# kb_hatti aday dosyaları: tek_film_kunye v4 raporu bugün DİSKE YAZILMIYOR (yalnız stdout;
# mitas_pipeline raw_decode ile tüketir, _DURUM.json'a liste alanları geçmez) → grep-teyitli.
# İleride bir modül raporu kalıcılaştırırsa şu sabit adlardan okunur; yoksa BOŞ-fallback.
_V4_RAPOR_ADAYLARI = (os.path.join("pdf", "kunye_v4_rapor.json"), "kunye_v4_rapor.json")


def _kb_hatti_oku(clip_dir: str, uyarilar: list[str]) -> dict:
    kb = {"yonetmen": [], "yapimci": [], "cast": []}
    for rel in _V4_RAPOR_ADAYLARI:
        p = os.path.join(clip_dir, rel)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8", errors="ignore") as h:
                rapor = json.load(h) or {}
            v4 = rapor.get("v4") if isinstance(rapor.get("v4"), dict) else rapor
            kb["yonetmen"] = _isim_listesi(v4.get("yonetmen_list") or v4.get("yonetmen"))
            kb["yapimci"] = _isim_listesi(v4.get("yapimci_list") or v4.get("yapimci"))
            kb["cast"] = _isim_listesi(v4.get("cast_list"))
        except Exception as exc:  # noqa: BLE001 — bozuk rapor kb_hattını boş bırakır
            uyarilar.append(f"KB_HATTI_OKUNAMADI: {type(exc).__name__}: {exc}")
        break
    return kb


def _isim_listesi(v) -> list[str]:
    """Serbest json alanı → düz isim listesi (str olmayan/boş elemanlar elenir)."""
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if isinstance(x, str) and str(x).strip()]


def _vl_oku(clip_dir: str, uyarilar: list[str]) -> dict:
    """<clip>/gemma_kunye.json → {"yonetmen":[],"oyuncular":[],"diger_roller":[]}.
    diger_roller kaynakta [{"rol":..,"isimler":[..]}] (bkz. _pipe_shadow_vl) → şemadaki
    düz listeye İSİMLER indirgenir (seri_diff name_match ile isim arar; rol bilgisi
    dilim/kare hattında zaten var)."""
    vl = {"yonetmen": [], "oyuncular": [], "diger_roller": []}
    p = os.path.join(clip_dir, "gemma_kunye.json")
    if not os.path.isfile(p):
        return vl
    try:
        with open(p, encoding="utf-8", errors="ignore") as h:
            j = json.load(h) or {}
        vl["yonetmen"] = _isim_listesi(j.get("yonetmen"))
        vl["oyuncular"] = _isim_listesi(j.get("oyuncular"))
        dr: list[str] = []
        raw = j.get("diger_roller")
        for it in (raw if isinstance(raw, list) else []):
            if isinstance(it, dict):
                dr.extend(_isim_listesi(it.get("isimler")))
            elif isinstance(it, str) and it.strip():
                dr.append(it.strip())
        vl["diger_roller"] = dr
    except Exception as exc:  # noqa: BLE001 — VL tanığı yoksa alan boş kalır, çökme yok
        uyarilar.append(f"VL_OKUNAMADI: {type(exc).__name__}: {exc}")
    return vl


def okuma_topla(clip_dir: str, bolum_no: int, trt_id: str | None = None) -> dict:
    """Hub klasöründen normalize BolumOkuma topla (dizi_SISTEM.md şeması). SALT-OKUR;
    hiçbir hata çökme üretmez — uyarılara yazılır, alanlar boş döner."""
    uyarilar: list[str] = []
    okuma = {
        "bolum_no": bolum_no,
        "trt_id": trt_id,
        "cast": [],
        "crew": {},
        "konuk_acik": [],
        "kb_hatti": {"yonetmen": [], "yapimci": [], "cast": []},
        "vl": {"yonetmen": [], "oyuncular": [], "diger_roller": []},
        "stop_kart_bolum_no": None,
        "kaynak": "yok",
        "uyarilar": uyarilar,
    }
    try:
        satirlar, kaynak, uy = _satirlar_oku(clip_dir)
        uyarilar.extend(uy)
        okuma["kaynak"] = kaynak
        if satirlar:
            kalan, kart_no, uy2 = stop_kart_suz(satirlar, bolum_no)
            uyarilar.extend(uy2)
            okuma["stop_kart_bolum_no"] = kart_no
            konuklar, kalan2 = konuk_ayikla(kalan)
            okuma["konuk_acik"] = konuklar
            cast, crew = _cp().parse_credits(kalan2, "", dizi=True)
            # konuk_acik isimleri cast'ten name_match (sıkı) ile düşülür — konuk hem
            # kadro-kartında hem konuk-kartında geçebilir; kadro üyeliği seri_diff'in işi.
            okuma["cast"] = [c for c in cast
                             if not any(name_match(c, g) for g in konuklar)]
            okuma["crew"] = {rol: list(isimler) for rol, isimler in crew}
    except Exception as exc:  # noqa: BLE001 — adaptör ASLA çökmez ("okunamadı > yanlış oku")
        uyarilar.append(f"OKUMA_HATA: {type(exc).__name__}: {exc}")
    okuma["kb_hatti"] = _kb_hatti_oku(clip_dir, uyarilar)
    okuma["vl"] = _vl_oku(clip_dir, uyarilar)
    return okuma
