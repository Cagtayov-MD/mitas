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
#    "bolum konuklari": YAMA SÖZLEŞMESİ madde 10 eki.
KONUK_BASLIKLARI = ("konuk oyuncular", "konuk oyuncu", "konuk sanatci", "konuklar",
                    "bolum oyunculari", "bolum konuklari", "bu bolumun konuklari",
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
    kart_no: int | None = None
    uyarilar: list[str] = []
    foldlar = [_fold(l).strip(" .:-!…") for l in lines]
    # BU-DİZİ kapanış-kalıbı (2026-07-11): "Bu Dizi TRT / Tarafından X'e / Yaptırılmıştır."
    # OCR'da 2-4 satıra bölünür ve parçaları isim sanılır. Pencere kuralı: "bu dizi" ile
    # başlayan satırdan sonraki ≤4 satır içinde "yaptirilmistir" varsa BLOK düşer;
    # tek başına "yaptirilmistir" içeren satır da düşer. "BU DİZİDE OYNAYANLAR" gibi
    # kalıpsız satırlar (pencerede yaptirilmistir yok) DOKUNULMAZ.
    dusur: set[int] = set()
    for i, f in enumerate(foldlar):
        if "yaptirilmistir" in f:
            dusur.add(i)
        if f.startswith("bu dizi"):
            for j in range(i + 1, min(i + 5, len(foldlar))):
                if "yaptirilmistir" in foldlar[j]:
                    dusur.update(range(i, j + 1))
                    break
    kalan: list[str] = []
    for i, l in enumerate(lines):
        if i in dusur:
            continue
        f = foldlar[i]
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


def _logo_kolon_suz(md_dir: str, lines: list[str], uyarilar: list[str]) -> list[str]:
    """LOGO-KOLON süzgeci (2026-07-11, Diriliş vakası): modern dizi jeneriklerinde sol kolon
    sponsor logoları, sağ kolon künye akışıdır; OneOCR ikisini aynı satır-akışına karıştırır.
    dilim_oneocr.jsonl kutu-x koordinatlarıyla iki-kolon yerleşimi tespit edilir
    (sol küme ≥3 satır ∧ sağ küme ≥ max(6, 2×sol)); tespit varsa SOL-kolon satırları
    düşürülür ve uyarıya listelenir (izlenebilir kayıp — 'okunamadı > yanlış oku': logo
    çorbası isim listesine sızmasın). Tek-kolon/jsonl-siz hub'da HİÇBİR ŞEY değişmez."""
    jl = os.path.join(md_dir, "dilim_oneocr.jsonl")
    if not os.path.isfile(jl):
        return lines
    try:
        sol_metin: list[str] = []
        sag_fold: set[str] = set()
        kayitlar = []
        with open(jl, encoding="utf-8", errors="ignore") as h:
            for ln in h:
                ln = ln.strip()
                if ln:
                    kayitlar.append(json.loads(ln))
        if not kayitlar:
            return lines
        w = max(int(k.get("x1") or 0) for k in kayitlar)
        if w <= 0:
            return lines
        for k in kayitlar:
            t = str(k.get("text") or "").strip()
            if not t:
                continue
            merkez = (int(k.get("x0") or 0) + int(k.get("x1") or 0)) / 2.0 / w
            if merkez < 0.42:
                sol_metin.append(t)
            elif merkez >= 0.5:
                sag_fold.add(_fold(t))
        if len(sol_metin) < 3 or len(sag_fold) < max(6, 2 * len(sol_metin)):
            return lines
        dusecek = {_fold(t) for t in sol_metin} - sag_fold   # sağda da geçen fold KORUNUR
        if not dusecek:
            return lines
        kalan = [l for l in lines if _fold(l) not in dusecek]
        n = len(lines) - len(kalan)
        if n:
            ornek = ", ".join(sol_metin[:5])
            uyarilar.append(f"LOGO_KOLON: {n} satır düşürüldü (sol-kolon): {ornek}")
        return kalan
    except Exception as exc:  # noqa: BLE001 — süzgeç hatası okuma akışını ASLA bozmaz
        uyarilar.append(f"LOGO_KOLON_HATA: {type(exc).__name__}: {exc}")
        return lines


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
                out = _logo_kolon_suz(md, out, uyarilar)
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


# ── VL-DİLİM FALLBACK (YAMA SÖZLEŞMESİ madde 12, Çağatay talimatı 2026-07-09):
#    OneOCR düşük-kontrastı kaçırırsa (stop-kart yok / satır sayısı sparse) master-dilim
#    PNG'leri ikinci ekran-tanığına (glm-ocr) okutulur. ADDITIVE — OneOCR satırı silinmez.
VL_DILIM_ESIK = 8  # bundan az OneOCR satırı = sparse → VL ek okuma denenir


def _vl_dilim_acik() -> bool:
    return os.environ.get("MITAS_DIZI_VL_DILIM", "1").strip().lower() not in (
        "0", "false", "off", "no")


def _ollama_vl_http(model: str, prompt: str, images_b64: list[str]) -> str:
    """Varsayılan taşıyıcı: Ollama /api/chat (stream=False) → message.content.
    Test/enjeksiyon için okuma_topla(vl_http=...) ile değiştirilebilir."""
    import urllib.request
    url = os.environ.get("MITAS_OLLAMA_URL", "http://localhost:11434").rstrip("/")
    timeout = float(os.environ.get("MITAS_DIZI_VL_TIMEOUT", "120"))
    payload = json.dumps({
        "model": model, "stream": False,
        "messages": [{"role": "user", "content": prompt, "images": images_b64}],
    }).encode("utf-8")
    req = urllib.request.Request(url + "/api/chat", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8", errors="ignore"))
    return str(((j or {}).get("message") or {}).get("content") or "")


def vl_dilim_oku(clip_dir: str, vl_http=None) -> tuple[list[str], list[str]]:
    """master_dilim/*_pNN.png parçalarını VL modeline (varsayılan glm-ocr) okutur.
    Döner: (satırlar, uyarılar). Hata çökme üretmez — ([], [VL_DILIM_HATA...])."""
    uyarilar: list[str] = []
    try:
        import base64
        pngler = sorted(glob.glob(os.path.join(clip_dir, "master_dilim", "*_p[0-9][0-9].png")))
        if not pngler:
            return [], []  # dilim PNG'siz hub (eski düzen/test) — VL imkânı yok, gürültü de yok
        model = os.environ.get("MITAS_DIZI_VL_MODEL", "glm-ocr:latest")
        prompt = ("Bu görüntüdeki TÜM metni satır satır, aynen yaz. "
                  "Yorum/çeviri/açıklama EKLEME; yalnız görünen metin.")
        http = vl_http or _ollama_vl_http
        satirlar: list[str] = []
        for p in pngler:
            b64 = base64.b64encode(open(p, "rb").read()).decode("ascii")
            cevap = http(model, prompt, [b64]) or ""
            satirlar.extend(s.strip() for s in cevap.splitlines() if s.strip())
        return satirlar, uyarilar
    except Exception as exc:  # noqa: BLE001 — VL tanığı yoksa OneOCR tek başına devam
        return [], [f"VL_DILIM_HATA: {type(exc).__name__}: {exc}"]


def _buyuk_agirlikli(s: str) -> bool:
    harfler = [c for c in s if c.isalpha()]
    if not harfler:
        return False
    return sum(1 for c in harfler if c.isupper()) / len(harfler) >= 0.8


def _cast_ajans_ayikla(lines: list[str]) -> tuple[list[str], list[str], list[str]]:
    """YAMA SÖZLEŞMESİ madde 13 (Çağatay 2026-07-09): dizi jeneriğinde 'cast' başlığı
    altında TEK büyük-harf girdi = casting AJANSI kredisi (oyuncu listesi DEĞİL; örn.
    'cast: MAVİ FİL'). Blok sonu = küçük-harf-ağırlıklı rol etiketi (dizi kalıbı:
    etiket küçük, isim BÜYÜK) veya role_of başlığı. ≥2 girdi = gerçek oyuncu listesi,
    DOKUNULMAZ. Döner: (ajanslar, kalan_satirlar, uyarilar)."""
    cp = _cp()
    ajanslar: list[str] = []
    uyarilar: list[str] = []
    cikar: set[int] = set()
    i = 0
    while i < len(lines):
        if cp.role_of(lines[i]) == "CAST":
            blok: list[int] = []
            j = i + 1
            while j < len(lines):
                ln = lines[j]
                if cp.role_of(ln) is not None or not _buyuk_agirlikli(ln):
                    break  # yeni başlık ya da küçük-harf rol etiketi → blok bitti
                if cp.is_person(ln, ""):
                    blok.append(j)
                j += 1
            if len(blok) == 1:
                ajans = lines[blok[0]]
                if _fold(ajans) not in {_fold(a) for a in ajanslar}:  # hayalet-çift dedup
                    ajanslar.append(ajans)
                    uyarilar.append(f"CAST_AJANS: {ajans}")
                cikar.add(i)
                cikar.add(blok[0])
            i = j if j > i else i + 1
        else:
            i += 1
    if not cikar:
        return [], lines, []
    return ajanslar, [ln for k, ln in enumerate(lines) if k not in cikar], uyarilar


def okuma_topla(clip_dir: str, bolum_no: int, trt_id: str | None = None,
                vl_http=None) -> dict:
    """Hub klasöründen normalize BolumOkuma topla (dizi_SISTEM.md şeması). SALT-OKUR;
    hiçbir hata çökme üretmez — uyarılara yazılır, alanlar boş döner.
    vl_http: VL-dilim fallback taşıyıcısı (test enjeksiyonu; None=Ollama)."""
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
            # VL-DİLİM FALLBACK (madde 12): OneOCR stop-kartı kaçırdıysa VEYA okuma
            # sparse ise ikinci ekran-tanığı (glm-ocr) dilim PNG'lerini okur. ADDITIVE.
            if (kaynak == "master_dilim" and _vl_dilim_acik()
                    and (kart_no is None or len(kalan) < VL_DILIM_ESIK)):
                vl_satirlar, uy_vl = vl_dilim_oku(clip_dir, vl_http)
                uyarilar.extend(uy_vl)
                if vl_satirlar:
                    v_kalan, v_kart, _ = stop_kart_suz(vl_satirlar, bolum_no)
                    if kart_no is None and v_kart is not None:
                        kart_no = v_kart
                        uyarilar.append(f"STOP_KART_VL: {v_kart}")
                        if bolum_no is not None and v_kart != bolum_no:
                            uyarilar.append(
                                f"BOLUM_NO_CELISKI: kart={v_kart} dosya={bolum_no} (vl)")
                    if len(kalan) < VL_DILIM_ESIK:
                        mevcut = {_fold(x) for x in kalan}
                        ek = [x for x in v_kalan if _fold(x) not in mevcut]
                        if ek:
                            kalan.extend(ek)
                            uyarilar.append(f"VL_DILIM_EK: {len(ek)} satır")
            okuma["stop_kart_bolum_no"] = kart_no
            konuklar, kalan2 = konuk_ayikla(kalan)
            okuma["konuk_acik"] = konuklar
            # CAST-AJANS kuralı (madde 13): tek-girdili cast bloğu ajans kredisidir.
            ajanslar, kalan2, uy3 = _cast_ajans_ayikla(kalan2)
            uyarilar.extend(uy3)
            cast, crew = _cp().parse_credits(kalan2, "", dizi=True)
            # konuk_acik isimleri cast'ten name_match (sıkı) ile düşülür — konuk hem
            # kadro-kartında hem konuk-kartında geçebilir; kadro üyeliği seri_diff'in işi.
            okuma["cast"] = [c for c in cast
                             if not any(name_match(c, g) for g in konuklar)]
            okuma["crew"] = {rol: list(isimler) for rol, isimler in crew}
            if ajanslar:
                okuma["crew"].setdefault("Cast", []).extend(ajanslar)
    except Exception as exc:  # noqa: BLE001 — adaptör ASLA çökmez ("okunamadı > yanlış oku")
        uyarilar.append(f"OKUMA_HATA: {type(exc).__name__}: {exc}")
    okuma["kb_hatti"] = _kb_hatti_oku(clip_dir, uyarilar)
    okuma["vl"] = _vl_oku(clip_dir, uyarilar)
    return okuma
