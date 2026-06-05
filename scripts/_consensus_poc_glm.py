"""
ÇİFT-MOTOR CONSENSUS POC — KİTAP KURDU
Engine A: OneOCR  (ocr_ham.txt — 636 satır, önceden hazır)
Engine B: GLM-OCR (ollama glm-ocr:latest, kare kare okuma, stride=5)
Üretim koduna DOKUNMAZ. Çıktı: E:\MITAS\_consensus_poc_glm_kitapkurdu.txt
"""

import sys, json, base64, urllib.request, re, difflib, unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# ── Yollar ──────────────────────────────────────────────────────────────────
FILM_ROOT = Path(r"E:\MITAS\Database\evoArcadmin_S_NEMA_F_LM4_2025-1186-1-0000-90-1-K_TAP_KURDU_2")
OCR_HAM   = FILM_ROOT / "ocr" / "ham_regen" / "ocr_ham.txt"
GIRIS_DIR = FILM_ROOT / "frames" / "giris"
CIKIS_DIR = FILM_ROOT / "frames" / "cikis"
OUT_FILE  = Path(r"E:\MITAS\_consensus_poc_glm_kitapkurdu.txt")

OLLAMA = "http://localhost:11434/api/generate"
GLM    = "glm-ocr:latest"
STRIDE = 5   # her 5. kare → ~168 kare toplam

PROMPT = (
    "Transcribe the film-credit text in this image EXACTLY, top to bottom, one entry per line. "
    "Use '?' for unreadable characters. Do NOT guess, do NOT add names not visible. "
    "Preserve Turkish letters: ç ğ ı İ ö ş ü. Return JSON: {\"lines\":[\"...\",\"...\"]}"
)

# Bilinen çöp satırlar (OneOCR bozuk okumaları)
KNOWN_GARBAGE = [
    "ASTTIUK MEE", "AGIHIUIR ME", "AGIHUK MEE", "ARITIUR HEE",
    "CAUCADE BOCK", "EiJTerdd Col", "t Lagcalor", "Curade Pock",
    "Welmekasst Cal", "EOITEO SY", "gorreo sr",
    # normalizasyon için küçük harf alternatifleri de ekle
    "CAUCADE BOCK", "EIJTERDD COL", "T LAGCALOR", "CURADE POCK",
]

# ── Araçlar ──────────────────────────────────────────────────────────────────
def fold(s):
    """Küçük harf + diakritik/aksan kaldır."""
    return ''.join(
        c for c in unicodedata.normalize('NFKD', (s or '').lower())
        if not unicodedata.combining(c)
    ).strip()

_VOWELS = set("aeıioöuüâîû")

def garble(t):
    """Sesli-harfsiz uzun kelime → bozuk skor yüksek."""
    ns = sum(not c.isspace() for c in t)
    le = sum(c.isalpha() for c in t)
    if ns == 0:
        return 9.0
    s = (1 - le / ns) * 2.0
    for w in t.split():
        fw = fold(w)
        if len(fw) >= 4 and not any(c in _VOWELS for c in fw):
            s += 1.0
    return s

def extract_lines(text):
    """GLM yanıtından satırları çıkar."""
    if not text:
        return []
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()
    m = re.search(r"\{.*\"lines\".*\}", text, flags=re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj.get("lines"), list):
                return [str(x).strip() for x in obj["lines"] if str(x).strip()]
        except Exception:
            pass
    out = []
    for ln in text.splitlines():
        t = ln.strip().strip("`").strip("-*•").strip()
        if not t or t in ("{", "}", "[", "]"):
            continue
        if t.lower().startswith(("here", "sure", "```", "json")):
            continue
        if t.startswith('"') and t.endswith('",'):
            t = t[1:-2]
        out.append(t)
    return out

def fuzzy_in(f, flist, thr=0.85):
    """f, flist içindeki herhangi bir öğeyle ≥thr benzerlikte mi?"""
    return any(difflib.SequenceMatcher(None, f, g).ratio() >= thr for g in flist)

def glm_read_frame(img_path, timeout=120):
    """Tek bir kareyi GLM ile oku, satır listesi döndür."""
    data = Path(img_path).read_bytes()
    b64 = base64.b64encode(data).decode()
    payload = {
        "model": GLM,
        "prompt": PROMPT,
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": {"temperature": 0},
        "images": [b64],
    }
    req = urllib.request.Request(
        OLLAMA,
        json.dumps(payload).encode(),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = json.loads(r.read())
    return extract_lines(raw.get("response", ""))

# ── Kare listesi ──────────────────────────────────────────────────────────────
def sampled_frames(directory, stride):
    frames = sorted(directory.glob("*.png"))
    return [f for i, f in enumerate(frames) if i % stride == 0]

# ── Ana akış ─────────────────────────────────────────────────────────────────
def main():
    # 1. Engine A yükle (OneOCR)
    one_ocr_lines = [
        ln.strip()
        for ln in OCR_HAM.read_text(encoding="utf-8", errors="ignore").splitlines()
        if ln.strip()
    ]
    print(f"[A] OneOCR satır sayısı: {len(one_ocr_lines)}", flush=True)

    # 2. Kare listesi
    all_frames = sampled_frames(GIRIS_DIR, STRIDE) + sampled_frames(CIKIS_DIR, STRIDE)
    print(f"[B] GLM okuyacak kare: {len(all_frames)} (stride={STRIDE})", flush=True)

    # 3. GLM okuma (dedup — fold bazında ilk yazım tutulur)
    glm_seen: dict[str, str] = {}   # fold → orijinal
    glm_order: list[str] = []       # ekleme sırası

    for i, fp in enumerate(all_frames):
        pct = (i + 1) * 100 // len(all_frames)
        print(f"  [{i+1}/{len(all_frames)} %{pct}] {fp.name} ...", end=" ", flush=True)
        try:
            lines = glm_read_frame(fp)
            added = 0
            for ln in lines:
                fk = fold(ln)
                if fk and len(fk) >= 2 and fk not in glm_seen:
                    glm_seen[fk] = ln
                    glm_order.append(ln)
                    added += 1
            print(f"{len(lines)} satır → {added} yeni", flush=True)
        except Exception as e:
            print(f"HATA: {e}", flush=True)

    glm_lines = glm_order
    print(f"\n[B] GLM toplam benzersiz satır: {len(glm_lines)}", flush=True)

    # 4. Fold setleri
    fo = [fold(x) for x in one_ocr_lines]
    fg = [fold(x) for x in glm_lines]
    fgs = set(fg)
    fos = set(fo)

    # 5. Sınıflandırma
    confirmed = []     # iki motor uyuştu
    one_only_clean = []   # OneOCR-only, garble düşük → TUT
    one_only_garbled = [] # OneOCR-only, garble yüksek → DÜŞÜR
    glm_only_solid = []   # GLM-only, sağlam → EKLE

    GARBLE_THR = 1.5  # bu değerin üstü garbled sayılır

    for ln, fk in zip(one_ocr_lines, fo):
        if fk in fgs or fuzzy_in(fk, fg):
            confirmed.append(ln)
        else:
            g = garble(ln)
            if g >= GARBLE_THR:
                one_only_garbled.append((ln, g))
            else:
                one_only_clean.append(ln)

    for ln, fk in zip(glm_lines, fg):
        if fk in fos or fuzzy_in(fk, fo):
            continue  # zaten confirmed veya one_ocr içinde
        tokens = [t for t in ln.split() if len(t) >= 2]
        g = garble(ln)
        if len(tokens) >= 2 and g < GARBLE_THR:
            glm_only_solid.append(ln)

    # 6. Rakamsal özet
    print("\n" + "="*60)
    print("CONSENSUS SONUÇLARI")
    print("="*60)
    print(f"  OneOCR toplam       : {len(one_ocr_lines)}")
    print(f"  GLM toplam          : {len(glm_lines)}")
    print(f"  CONFIRMED (ikisi)   : {len(confirmed)}")
    print(f"  OneOCR-only GARBLED : {len(one_only_garbled)}  (DÜŞÜRÜLECEK)")
    print(f"  OneOCR-only temiz   : {len(one_only_clean)}")
    print(f"  GLM-only sağlam     : {len(glm_only_solid)}  (EKLENECEK)")

    # 7. Bilinen çöp satırların kaderi
    known_fold = {fold(g): g for g in KNOWN_GARBAGE}
    print("\n--- BİLİNEN ÇÖP SATIRLARIN KADERI ---")
    for kf, korig in known_fold.items():
        # OneOCR'da var mı?
        matched_one = next((ln for ln, fk in zip(one_ocr_lines, fo) if fk == kf or fuzzy_in(fk, [kf])), None)
        if matched_one is None:
            # fold eşleşmesi geniş tut
            matched_one = next((ln for ln in one_ocr_lines if fold(ln) == kf), None)
        glm_match = next((ln for ln in glm_lines if fold(ln) == kf or fuzzy_in(fold(ln), [kf])), None)
        g_score = garble(korig)
        in_confirmed = (kf in fgs or fuzzy_in(kf, fg))
        outcome = "CONFIRMED (iki motor uyuştu)" if in_confirmed else "DÜŞÜRÜLDÜ (garble=%.2f)" % g_score
        print(f"  OneOCR: [{korig}]")
        print(f"    garble={g_score:.2f}  GLM teyidi: {glm_match!r}  → {outcome}")

    # 8. GLM'in bozukları doğrusu ile okuyup okumadığı
    # Bozuk satırlara yakın GLM alternatifleri bul (fuzzy, düşük eşik)
    print("\n--- GLM DOĞRU OKUMA EŞLEŞMELERI (çöp → gerçek isim?) ---")
    # "ARTHUR MEE" gibi doğru isimleri GLM'den ara
    arthur_variants = [ln for ln in glm_lines if "arthur" in fold(ln) or "arthur" in ln.lower()]
    cascade_variants = [ln for ln in glm_lines if "cascade" in fold(ln) or "cascade" in ln.lower()]
    lancelot_variants = [ln for ln in glm_lines if "lancelot" in fold(ln) or "lancelot" in ln.lower() or "lancel" in fold(ln)]
    edited_variants = [ln for ln in glm_lines if "edited" in fold(ln) or "edit" in fold(ln)]

    print(f"  'ARTHUR MEE' bozukları → GLM'de ARTHUR içerenler: {arthur_variants[:8]}")
    print(f"  'CASCADE ROCK' bozukları → GLM'de CASCADE içerenler: {cascade_variants[:8]}")
    print(f"  'LANCELOT' bozukları → GLM'de LANCELOT içerenler: {lancelot_variants[:8]}")
    print(f"  'EDITED BY' bozukları → GLM'de EDITED içerenler: {edited_variants[:8]}")

    # 9. Consensus çıktısını yaz
    consensus = confirmed + one_only_clean + glm_only_solid
    lines_out = []
    lines_out.append("# ÇİFT-MOTOR CONSENSUS — KİTAP KURDU")
    lines_out.append(f"# OneOCR={len(one_ocr_lines)} | GLM={len(glm_lines)} | "
                     f"CONFIRMED={len(confirmed)} | dropped={len(one_only_garbled)} | added={len(glm_only_solid)}")
    lines_out.append("#")
    lines_out.append("# --- CONFIRMED (iki motor uyuştu) ---")
    for ln in confirmed:
        lines_out.append(ln)
    lines_out.append("#")
    lines_out.append("# --- OneOCR-only TEMIZ (tutuldu) ---")
    for ln in one_only_clean:
        lines_out.append(ln)
    lines_out.append("#")
    lines_out.append("# --- GLM-only SAĞLAM (eklendi) ---")
    for ln in glm_only_solid:
        lines_out.append(ln)
    lines_out.append("#")
    lines_out.append("# --- OneOCR-only GARBLED (düşürüldü) ---")
    for ln, g in one_only_garbled:
        lines_out.append(f"#  GARBLE={g:.2f}  {ln}")

    OUT_FILE.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print(f"\n[OUT] Consensus dosyası yazıldı: {OUT_FILE}")
    print(f"[OUT] Toplam consensus satır: {len(confirmed) + len(one_only_clean) + len(glm_only_solid)}")

    # 10. GLM-only örnekleri göster (ilk 20)
    print("\n--- GLM-only SAĞLAM örnekler (ilk 20) ---")
    for ln in glm_only_solid[:20]:
        print(f"  + {ln}")

    # 11. OneOCR-only temiz örnekleri (ilk 10)
    print("\n--- OneOCR-only TEMIZ örnekler (ilk 10) ---")
    for ln in one_only_clean[:10]:
        print(f"  ~ {ln}")

    # 12. OneOCR-only garbled örnekler (tamamı)
    print("\n--- OneOCR-only GARBLED (tümü, düşürüldü) ---")
    for ln, g in sorted(one_only_garbled, key=lambda x: -x[1]):
        print(f"  ✗ garble={g:.2f}  [{ln}]")

    return {
        "one_ocr": len(one_ocr_lines),
        "glm": len(glm_lines),
        "confirmed": len(confirmed),
        "one_only_garbled": len(one_only_garbled),
        "one_only_clean": len(one_only_clean),
        "glm_only_solid": len(glm_only_solid),
    }

if __name__ == "__main__":
    main()
