#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ses_teyit_fix.py — SES_TEYIT PDF onarım + onaylı'ya taşıma.

Her film için:
  1. SES_TEYIT PDF'den mevcut veri çıkar (fitz)
  2. Database kunye.pdf'den yapımcı + afiş çıkar
  3. Eksik kalırsa TMDB'den çek
  4. _make_pdf.build() ile yeni PDF → _onaylı olarak onaylı/ klasörüne kopyala

Çalıştır: global python (reportlab + fitz burası)
  python scripts/ses_teyit_fix.py [--apply]
"""
import datetime, importlib.util, json, os, re, sys, tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import fitz
import requests

ROOT    = r"E:\MITAS"
DB      = Path(ROOT) / "Database"
SES     = Path(ROOT) / "Mitas Output" / "export" / "KONTROL" / "SES TEYİT"  # 2026-06-15: KONTROL altına taşındı
ONAY    = SES / "onaylı"
TMP     = Path(ROOT) / "_tmp_poster_fix"
PDFMITAS = Path(ROOT) / "OCR-worktree" / "pdf-mitas"
TMDB_KEY = os.environ.get("MITAS_TMDB", "")

# --- _make_pdf yükle ---
def _load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

mp = _load("mp", str(PDFMITAS / "_make_pdf.py"))

# --- Sabitler ---
FIXABLE = [
    # (ses_teyit_filename, db_clip_name, sorun)
    # sadece afiş
    ("2018-1083-1-0000-88-1 KEFERNAHUM SESTEYIT.pdf",        "KEFERNAHUM 2018-1083-1-0000-88-1",          "afis"),
    ("2022-1192-1-0000-71-0 SEKİZ DAĞ SESTEYIT.pdf",         "SEKİZ DAĞ 2022-1192-1-0000-71-0",           "afis"),
    ("2023-1189-1-0000-70-1 ÇÖZÜMLER KİTABI SESTEYIT.pdf",   "ÇÖZÜMLER KİTABI 2023-1189-1-0000-70-1",    "afis"),
    ("2024-1219-1-0000-50-1 KOCA SEVİMLİ DEV SESTEYIT.pdf",  "KOCA SEVİMLİ DEV 2024-1219-1-0000-50-1",   "afis"),
    ("2025-1015-1-0000-77-0 LUNANA SINIFTA BİR YAK SESTEYIT.pdf", "LUNANA SINIFTA BİR YAK 2025-1015-1-0000-77-0", "afis"),
    # sadece yapımcı
    ("2008-1074-1-0000-72-1 AMİRAL SESTEYIT.pdf",            "AMİRAL 2008-1074-1-0000-72-1",              "yapimci"),
    ("2011-1127-1-0000-50-1 DEMİR LEYDİ SESTEYIT.pdf",       "DEMİR LEYDİ 2011-1127-1-0000-50-1",        "yapimci"),
    ("2014-1001-1-0000-80-1 TURİST SESTEYIT.pdf",            "TURİST 2014-1001-1-0000-80-1",             "yapimci"),
    ("2018-1046-1-0000-80-1 İLK VEDA SESTEYIT.pdf",          "İLK VEDA 2018-1046-1-0000-80-1",           "yapimci"),
    ("2018-1111-1-0000-85-1 ÇALIŞMAK İÇİN GÜZEL BİR GÜN SESTEYIT.pdf", "ÇALIŞMAK İÇİN GÜZEL BİR GÜN 2018-1111-1-0000-85-1", "yapimci"),
    ("2018-1193-1-0000-74-1 ZAVALLI SESTEYIT.pdf",           "ZAVALLI 2018-1193-1-0000-74-1",             "yapimci"),
    ("2021-1268-1-0000-50-0 BELFAST SESTEYIT.pdf",           "BELFAST 2021-1268-1-0000-50-0",             "yapimci"),
    ("2022-1007-1-0000-78-1 VURGUN SESTEYIT.pdf",            "VURGUN 2022-1007-1-0000-78-1",              "yapimci"),
    ("2022-1150-1-0000-75-1 GÖLGE SAVAŞÇI SESTEYIT.pdf",    "GÖLGE SAVAŞÇI 2022-1150-1-0000-75-1",      "yapimci"),
    ("2022-1194-1-0000-50-0 RADYOAKTİF SESTEYIT.pdf",        "RADYOAKTİF 2022-1194-1-0000-50-0",          "yapimci"),
    ("2024-1083-1-0000-50-1 DÜNYANIN PARASI SESTEYIT.pdf",   "DÜNYANIN PARASI 2024-1083-1-0000-50-1",     "yapimci"),
    ("2025-1026-1-0000-23-1 BEYAZ GEMİ SESTEYIT.pdf",        "BEYAZ GEMİ 2025-1026-1-0000-23-1",         "yapimci"),
    ("2025-1143-1-0000-50-0 JACKIE SESTEYIT.pdf",            "JACKIE 2025-1143-1-0000-50-0",              "yapimci"),
    # her ikisi
    ("2014-1071-1-0000-80-1 DAĞLARIN KRALİÇESİ SESTEYIT.pdf","DAĞLARIN KRALİÇESİ 2014-1071-1-0000-80-1", "both"),
    ("2021-2164-1-0000-56-0 BEYAZ BALON SESTEYIT.pdf",        "BEYAZ BALON 2021-2164-1-0000-56-0",         "both"),
    ("2022-1119-1-0000-22-0 CEVİZ AĞACI SESTEYIT.pdf",        "CEVİZ AĞACI 2022-1119-1-0000-22-0",         "both"),
]


# ─── Ayrıştırma ─────────────────────────────────────────────────────────────

def sp(s):
    """Spaced text 'A M İ R A L' → 'AMİRAL'"""
    return re.sub(r'(?<=[A-ZÇĞİÖŞÜa-zçğışöü]) (?=[A-ZÇĞİÖŞÜa-zçğışöü])', '', s)

def clean_lines(blob):
    return [l.strip() for l in blob.split('\n') if l.strip() and l.strip() not in ('—', '')]

def parse_sesteyit(path):
    """SES_TEYIT PDF'inden tüm alanları çıkar (fitz)."""
    doc = fitz.open(str(path))
    t   = doc[0].get_text()
    d   = {}

    # Profil
    d['profile'] = 'DİZİ' if re.search(r'D [İI] Z [İI]', t) else 'FİLM'

    # Başlık ve alt başlık
    pm = re.search(r'(?:F [İI] L M|D [İI] Z [İI])\n(.+?)(?=\nA N A H T A R)', t, re.S)
    if pm:
        lines = clean_lines(pm.group(1))
        d['title']    = lines[0] if lines else ''
        d['subtitle'] = lines[1] if len(lines) > 1 else ''
    else:
        d['title'] = d['subtitle'] = ''

    # Anahtar sözcükler
    km = re.search(r'A N A H T A R [^\n]+\n(.+?)O Y U N C U L A R', t, re.S)
    d['keywords'] = km.group(1).strip().replace('\n', ' ') if km else '—'

    # Oyuncular
    cm = re.search(r'O Y U N C U L A R\n(.+?)Y A P I M', t, re.S)
    d['cast'] = clean_lines(cm.group(1)) if cm else []

    # Yönetmen
    ym = re.search(r'Yönetmen\n(.+?)(?=Yapımcı|Ö Z E T|$)', t, re.S)
    d['yonetmen'] = [l.strip() for l in (ym.group(1).split('\n') if ym else [])
                     if l.strip() and l.strip() != '—']

    # Yapımcı
    yam = re.search(r'Yapımcı\n(.+?)(?=Ö Z E T|$)', t, re.S)
    d['yapimci'] = [l.strip() for l in (yam.group(1).split('\n') if yam else [])
                    if l.strip() and l.strip() != '—']

    # Özet
    om = re.search(r'Ö Z E T\n(.+?)$', t, re.S)
    d['ozet'] = om.group(1).strip().replace('\n', ' ') if om else ''

    # Ses kanalları
    kanalar = []
    for km2 in re.finditer(r'\d+ \. +K A N A L\n([A-Z]+)', t):
        kanalar.append(km2.group(1).strip())
    d['ses_kanallari'] = kanalar

    # Ana dil / altyazı
    adm = re.search(r'A N A  D [İI] L\n([A-Z]+)', t)
    d['ana_dil'] = adm.group(1) if adm else '—'
    altm = re.search(r'A L T Y A Z I\n([A-Z]+)', t)
    d['altyazi'] = altm.group(1) if altm else 'HAYIR'

    # Tür / süre / TRT kimlik / çözünürlük
    turm = re.search(r'T [UÜ] R\n(.+?)(?=T O P L A M)', t, re.S)
    d['tur'] = turm.group(1).strip() if turm else '—'
    surem = re.search(r'T O P L A M  S [UÜ] R E\n(.+?)T R T', t, re.S)
    d['sure'] = surem.group(1).strip() if surem else '—'
    trtm = re.search(r'T R T  K [İI] M L [İI] K\n(\S+)', t)
    d['trt_id'] = trtm.group(1) if trtm else ''
    resm = re.search(r'(\d{3,4}x\d{3,4})', t)
    d['resolution'] = resm.group(1) if resm else '512x288'

    return d


def parse_db_kunye(db_clip_dir):
    """Database kunye.pdf'inden yapımcı + yönetmen + alt başlık + afiş çıkar."""
    kunye = db_clip_dir / "pdf" / "kunye.pdf"
    if not kunye.exists():
        return [], [], None, ''
    doc = fitz.open(str(kunye))
    t   = doc[0].get_text()

    # Alt başlık (orijinal title) — FİLM/DİZİ adından sonra 2. satır
    subtitle_db = ''
    pm = re.search(r'(?:F [İI] L M|D [İI] Z [İI])\n(.+?)(?=\nA N A H T A R)', t, re.S)
    if pm:
        lines = clean_lines(pm.group(1))
        if len(lines) > 1:
            subtitle_db = lines[1]

    # Yapımcı
    yam = re.search(r'Yapımcı\n(.+?)(?=Ö Z E T|$)', t, re.S)
    yapimci = [l.strip() for l in (yam.group(1).split('\n') if yam else [])
               if l.strip() and l.strip() != '—']

    # Yönetmen (fallback)
    ym = re.search(r'Yönetmen\n(.+?)(?=Yapımcı|Ö Z E T|$)', t, re.S)
    yonetmen = [l.strip() for l in (ym.group(1).split('\n') if ym else [])
                if l.strip() and l.strip() != '—']

    # Afiş (ilk büyük resim)
    poster_path = None
    for img_info in doc[0].get_images(full=True):
        try:
            xref = img_info[0]
            bi   = doc.extract_image(xref)
            if bi.get("width", 0) > 100 and bi.get("height", 0) > 100 and len(bi.get("image", b"")) > 8000:
                ext = bi.get("ext", "jpg")
                tmp_p = TMP / f"poster_{kunye.parent.parent.name}_{xref}.{ext}"
                tmp_p.write_bytes(bi["image"])
                poster_path = str(tmp_p)
                break
        except Exception:
            pass

    return yapimci, yonetmen, poster_path, subtitle_db


# ─── TMDB ────────────────────────────────────────────────────────────────────

def tmdb_search(title, year, extra=''):
    """TMDB filmi ara. Yapımcısı olan ilk sonucu döndür; yoksa poster olan ilki; yoksa herhangi biri."""
    if not TMDB_KEY:
        return None
    words = title.split()
    candidates = [
        title,
        title.split('(')[0].strip(),
        ' '.join(words[:3]),
        words[0],
    ]
    if extra:
        candidates.insert(0, extra)
    year_opts = [year, ''] if year else ['']

    found_any = None  # yapımcı yoksa fallback

    for q in dict.fromkeys(candidates):
        if not q or len(q) < 3:
            continue
        for yr in year_opts:
            params = {"api_key": TMDB_KEY, "query": q}
            if yr:
                params["year"] = yr
            for lang in ["tr", "en", ""]:
                if lang:
                    params["language"] = lang
                elif "language" in params:
                    del params["language"]
                try:
                    r = requests.get("https://api.themoviedb.org/3/search/movie",
                                     params=params, timeout=10)
                    results = r.json().get("results", [])
                    for movie in results[:5]:   # ilk 5 sonucu dene
                        mid = movie["id"]
                        # Üreticisi olan film bulunursa hemen dön
                        prods = tmdb_producers_quick(mid)
                        if prods:
                            return movie
                        if found_any is None:
                            found_any = movie  # üretici yoksa fallback
                except Exception:
                    pass

    return found_any


def tmdb_producers_quick(movie_id):
    """Yapımcı listesi çek — boşsa [] döner, API hatası olursa da [] döner."""
    try:
        r = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}/credits",
                         params={"api_key": TMDB_KEY}, timeout=8)
        crew = r.json().get("crew", [])
        return [p["name"].upper() for p in crew
                if p.get("job") in ("Producer", "Executive Producer", "Co-Producer")]
    except Exception:
        return []


def tmdb_poster(movie_id, save_path):
    try:
        r = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}",
                         params={"api_key": TMDB_KEY}, timeout=10)
        pp = r.json().get("poster_path")
        if not pp:
            return None
        img_r = requests.get(f"https://image.tmdb.org/t/p/w500{pp}", timeout=20)
        Path(save_path).write_bytes(img_r.content)
        return save_path
    except Exception:
        return None


def tmdb_producers(movie_id):
    prods = tmdb_producers_quick(movie_id)
    return list(dict.fromkeys(prods))[:5]


# ─── Ana işlem ───────────────────────────────────────────────────────────────

def fix_one(ses_fn, db_name, sorun, apply=False):
    ses_path = SES / ses_fn
    db_dir   = DB / db_name
    TMP.mkdir(exist_ok=True)

    # 1. SES_TEYIT verisi
    data = parse_sesteyit(ses_path)

    # 2. Database'den yapımcı + afiş + alt başlık
    db_yapimci, db_yonetmen, db_poster, db_subtitle = parse_db_kunye(db_dir)

    # 3. Birleştir
    if not data['yapimci'] and db_yapimci:
        data['yapimci'] = db_yapimci
    if not data['yonetmen'] and db_yonetmen:
        data['yonetmen'] = db_yonetmen
    poster_path = db_poster  # DB'de afiş var mı?

    # 4. Eksik kalırsa TMDB
    year = data['trt_id'].split('-')[0] if data.get('trt_id') else ''
    title = data.get('title', '')
    tmdb_movie = None

    # DB alt başlığını da TMDB aramasına ekle
    alt_title = data.get('subtitle', '') or db_subtitle

    need_tmdb = (not poster_path) or (not data['yapimci'])
    if need_tmdb and title:
        tmdb_movie = tmdb_search(title, year, extra=alt_title)
        if tmdb_movie:
            mid = tmdb_movie['id']
            if not poster_path and tmdb_movie.get('poster_path'):
                pp = str(TMP / f"tmdb_{mid}.jpg")
                poster_path = tmdb_poster(mid, pp)
            if not data['yapimci']:
                data['yapimci'] = tmdb_producers(mid)

    # 5. Doğruluk kontrolü
    missing = []
    if not (poster_path and Path(poster_path).exists()):
        missing.append('afiş')
    if not data['yapimci']:
        missing.append('yapımcı')
    if not data['yonetmen']:
        missing.append('yönetmen')
    if not data['cast']:
        missing.append('oyuncu')
    if len(data.get('ozet', '')) < 60:
        missing.append('özet')

    if missing:
        return False, missing, data

    # 6. build() dict hazırla
    crew = []
    if data['yonetmen']:
        crew.append(('Yönetmen', data['yonetmen']))
    if data['yapimci']:
        crew.append(('Yapımcı', data['yapimci']))

    specs = [
        ('TÜR',        data.get('tur', '—')),
        ('TOPLAM SÜRE', data.get('sure', '—')),
        ('TRT KİMLİK', data.get('trt_id', '—')),
        ('ÇÖZÜNÜRLÜK', data.get('resolution', '512x288')),
    ]
    d = {
        'poster':       poster_path,
        'ses_kanallari': data.get('ses_kanallari', []),
        'ana_dil':      data.get('ana_dil', '—'),
        'altyazi':      data.get('altyazi', 'HAYIR'),
        'sesler_ic_ice': False,
        'specs':        specs,
        'date':         datetime.datetime.now().strftime('%d.%m.%Y · %H:%M'),
        'profile':      data.get('profile', 'FİLM'),
        'title':        data['title'],
        'subtitle':     data.get('subtitle', ''),
        'bolum':        '',
        'keywords':     data.get('keywords', '—'),
        'cast':         data['cast'] if data['cast'] else ['—'],
        'crew':         crew,
        'ozet':         data['ozet'],
    }

    if not apply:
        return True, [], d

    # 7. PDF oluştur → onaylı/
    ONAY.mkdir(exist_ok=True)
    stem     = Path(ses_fn).stem
    out_path = ONAY / (stem + '_onaylı.pdf')
    mp.build(str(out_path), d)
    return True, [], d


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    apply = "--apply" in sys.argv
    if not apply:
        print("*** DRY-RUN (render yok). Uygulamak için --apply ***\n")

    ok_list, fail_list = [], []
    for ses_fn, db_name, sorun in FIXABLE:
        success, missing, *rest = fix_one(ses_fn, db_name, sorun, apply=apply)
        if success:
            ok_list.append(ses_fn)
            status = "[OK]"
            info   = "yapımcı/afiş tamam" + (" → render edildi" if apply else " → render edilecek")
        else:
            fail_list.append((ses_fn, missing))
            status = "[--]"
            info   = "EKSIK: " + ", ".join(missing)
        print(f"{status} {ses_fn[:55]}")
        if missing:
            print(f"     {info}")
        else:
            print(f"     {info}")

    print(f"\n{'='*60}")
    print(f"BASARILI  : {len(ok_list)}")
    print(f"BASARISIZ : {len(fail_list)}")
    if fail_list:
        print("\nEksik kalanlar:")
        for fn, m in fail_list:
            print(f"  {fn[:55]}: {', '.join(m)}")


if __name__ == "__main__":
    main()
