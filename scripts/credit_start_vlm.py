# -*- coding: utf-8 -*-
"""credit_start_vlm.py — VLM-birincil KAPANIŞ JENERİĞİ başlangıç tespiti (v1, çok-model sentezi).

Felsefe (GPT+Gemini+DeepSeek+Meta paneli): ayrım SEMANTİK → VLM birincil, CV/OCR değil.
Jenerik bir SUFFIX'tir → SONDAN-başa tara (erken footage hiç aday olmaz). Jenerik SÜREKLİdir,
diegetik yazı GEÇİCİdir → zamansal süreklilik. Ham etikette İKİLİ-ARAMA YOK (dizi monoton değil).

v1 boru hattı:
  1) Sondan-başa STRIDE tarama (VLM 6-sınıf; siyah kareler cheap-skip=BLANK)
  2) Zamansal: sürdürülen kredi bölgesinin başını bul (BLANK köprüle, sürekli FOOTAGE/DIEGETIC'te dur)
  3) İnce: bölge sınırında kare-kare tara → ilk CREDIT karesi
Çıktı: {start_frame, start_file, status, labels...}. status: found|left_censored|not_found|review

Model: qwen3-vl:30b (ollama /api/chat). 512px küçültme, temp=0, JSON.
"""
from __future__ import annotations
import argparse, base64, io, json, os, re, sys, urllib.request
from pathlib import Path

MODEL = os.environ.get("MITAS_CREDIT_VLM_MODEL", "qwen3-vl:30b")
OLLAMA = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434")
STRIDE = int(os.environ.get("MITAS_CVLM_STRIDE", "12") or 12)
CLASSES = {"CREDIT", "DIEGETIC", "FOOTAGE", "END_CARD", "BLANK", "UNCERTAIN"}

_PROMPT = (
    "Bu bir filmin son dakikalarından bir karedir. Tek bir kelimeyle SINIFLA — dile, alfabeye veya "
    "kredi-kelimelerine BAKMADAN; sadece isim görmen kredi kanıtı DEĞİLDİR. Yazının filmin dünyasına ait "
    "bir NESNE üzerinde mi (afiş/tabela/gazete/altyazı/plaka = DIEGETIC), yoksa oyuncu/ekip sunan "
    "EDİTORYAL bir katman/kart mı (kayan liste / rol-isim / statik kart = CREDIT) olduğunu değerlendir.\n"
    "SINIFLAR: CREDIT (kapanış jeneriği: oyuncu/ekip/yapım künyesi), DIEGETIC (sahne-içi yazı: tabela, "
    "afiş, gazete, ALTYAZI, plaka), FOOTAGE (yazısız normal sahne), END_CARD (tam-ekran THE END/SON/FIN), "
    "BLANK (siyah/fade/logo).\n"
    'SADECE JSON dön: {"label":"CREDIT|DIEGETIC|FOOTAGE|END_CARD|BLANK","conf":0.0-1.0}'
)


def _downscale_b64(path: Path, long_edge: int = 512) -> str:
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB")
        w, h = im.size
        s = long_edge / max(w, h)
        if s < 1.0:
            im = im.resize((max(1, int(w * s)), max(1, int(h * s))))
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return base64.b64encode(path.read_bytes()).decode()


def _is_black(path: Path) -> bool:
    try:
        from PIL import Image
        import numpy as np
        g = np.asarray(Image.open(path).convert("L"))
        return bool(g.mean() < 12 and g.std() < 10)
    except Exception:
        return False


def _parse_label(txt: str) -> tuple[str, float]:
    m = re.search(r"\{.*\}", txt, re.S)
    if m:
        try:
            j = json.loads(m.group(0))
            lab = str(j.get("label", "")).upper().strip()
            if lab in CLASSES:
                return lab, float(j.get("conf", 0.5) or 0.5)
        except Exception:
            pass
    up = txt.upper()
    for c in ("CREDIT", "END_CARD", "DIEGETIC", "FOOTAGE", "BLANK"):
        if c in up:
            return c, 0.5
    return "UNCERTAIN", 0.0


def classify(path: Path, timeout: int = 120) -> tuple[str, float]:
    if _is_black(path):
        return "BLANK", 0.9
    body = {"model": MODEL, "messages": [{"role": "user", "content": _PROMPT, "images": [_downscale_b64(path)]}],
            "stream": False, "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 64}}
    try:
        r = json.loads(urllib.request.urlopen(urllib.request.Request(
            OLLAMA + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}),
            timeout=timeout).read())
        msg = r.get("message", {}) or {}
        txt = (msg.get("content") or "") or (msg.get("thinking") or "")
        return _parse_label(txt)
    except Exception:
        return "UNCERTAIN", 0.0


def _is_credit(lab: str) -> bool:
    return lab in ("CREDIT", "END_CARD")


def _refine_region_start(frames, region_start, labels, n):
    """Bölge başını kare-kare keskinleştir + CREDIT sürdükçe geriye yürü (ilk kredi karesi)."""
    lo = max(0, region_start - STRIDE); hi = min(n, region_start + STRIDE + 1)
    first = None; run = 0
    for i in range(lo, hi):
        lab = labels[i][0] if i in labels else classify(frames[i])[0]
        labels.setdefault(i, (lab, 0.5))
        if _is_credit(lab):
            run += 1
            if run >= 2 and first is None:
                first = i - 1
        elif lab == "BLANK":
            pass
        else:
            run = 0; first = None
    s = first if first is not None else region_start
    b = int(s) - 1
    while b >= 0:
        lab = labels[b][0] if b in labels else classify(frames[b])[0]
        labels.setdefault(b, (lab, 0.5))
        if lab == "CREDIT":
            s = b; b -= 1
        else:
            break
    return int(s)


def _sustained_at(frames, start, labels, n):
    """start'tan +9 karede sürdürülen CREDIT sayısı (BLANK/END_CARD köprüler, saymaz)."""
    s = 0
    for i in range(int(start), min(n, int(start) + 9)):
        lab = labels[i][0] if i in labels else classify(frames[i])[0]
        labels.setdefault(i, (lab, 0.5))
        if lab == "CREDIT":
            s += 1
        elif lab in ("BLANK", "END_CARD"):
            continue
        else:
            break
    return s


def detect(frames_dir: Path) -> dict:
    frames = sorted(frames_dir.glob("*.png"))
    n = len(frames)
    if n == 0:
        return {"status": "not_found", "reason": "no_frames", "start_frame": None}
    # 1) SONDAN-başa stride tarama
    # NOT (2026-07): GPT'nin 'full-coverage + earliest-region' fikri izolasyonda ATTİLA'yı çözdü
    # (standalone 4/4) ama ÜRETİM entegrasyonu regresyon verdi (STRIDE-hassas over-merge + ÖZGÜRLÜK
    # erken-false-pozitif → start=0). Güvenli baseline = greedy-backward korundu. Doğru entegrasyon
    # GPT'nin FOUND-gating'i (2 bağımsız shifted-verify + gerçek pre-context) gerektirir → ayrı redesign.
    samples = list(range(n - 1, -1, -STRIDE))
    labels: dict[int, tuple[str, float]] = {}
    # kredi bölgesini geriye doğru izle: kredi(+blank köprü) sürerken devam, 2 ardışık non-credit'te dur
    credit_seen = False
    noncredit_run = 0
    region_start_sample = None
    for idx in samples:
        lab, conf = classify(frames[idx])
        labels[idx] = (lab, conf)
        if _is_credit(lab):
            credit_seen = True
            noncredit_run = 0
            region_start_sample = idx           # şimdilik en erken kredi örneği
        elif lab == "BLANK":
            pass                                # köprüle (kredi-arası siyah)
        else:  # FOOTAGE / DIEGETIC / UNCERTAIN
            if credit_seen:
                noncredit_run += 1
                if noncredit_run >= 2:          # sürdürülen non-credit = kredi bölgesi bitti (geriye)
                    break
    if not credit_seen:
        return {"status": "not_found", "reason": "no_credit_samples", "start_frame": None,
                "labels": {str(k): v for k, v in labels.items()}}
    # left-censored: bölge pencerenin en başına kadar gidiyorsa
    if region_start_sample is not None and region_start_sample <= STRIDE:
        # pencerenin başında hâlâ kredi → jenerik daha önce başlamış olabilir
        left = True
    else:
        left = False
    # 2/3) İNCE: [region_start_sample - STRIDE, region_start_sample + STRIDE] kare-kare, ilk CREDIT
    lo = max(0, (region_start_sample or 0) - STRIDE)
    hi = min(n, (region_start_sample or 0) + STRIDE + 1)
    first_credit = None
    run = 0
    for i in range(lo, hi):
        if i in labels:
            lab = labels[i][0]
        else:
            lab, _ = classify(frames[i])
            labels[i] = (lab, _)
        if _is_credit(lab):
            run += 1
            if run >= 2 and first_credit is None:
                first_credit = i - 1            # sürdürülen kredinin ilk karesi
        elif lab == "BLANK":
            pass
        else:
            run = 0
            first_credit = None
    start = first_credit if first_credit is not None else region_start_sample
    # İNCE-SINIR GERİ-YÜRÜME: kaba stride kredinin ilk karesini kaçırmış olabilir (YALAZA: VLM 818,
    # gerçek 808 = YÖNETMEN kartı). Baştan geriye CREDIT sürdükçe yürü, footage/diegetik'te dur.
    b = int(start) - 1
    while b >= 0:
        if b in labels:
            lab = labels[b][0]
        else:
            lab, cf = classify(frames[b]); labels[b] = (lab, cf)
        if lab == "CREDIT":
            start = b
            b -= 1
        else:
            break
    # SÜRERLİK KAPISI: gerçek kredi bloğu sürüyor mu? SON_METRO'nun tek-yanlış-footage karesini ve
    # KIZGIN'in sadece-THE-END'ini eler → uydurma başlangıç yerine not_found (KKF: false-pos öldür).
    sustained = 0
    for i in range(int(start), min(n, int(start) + 9)):
        if i in labels:
            lab = labels[i][0]
        else:
            lab, cf = classify(frames[i]); labels[i] = (lab, cf)
        if lab == "CREDIT":
            sustained += 1
        elif lab in ("BLANK", "END_CARD"):
            continue                      # köprüle ama kredi SAYMA (END_CARD tek başına kredi değil)
        else:
            break                         # FOOTAGE/DIEGETIC → sürerlik kırıldı
    if sustained < 3:
        return {"status": "not_found", "reason": "not_sustained_credit",
                "start_frame": None, "n_frames": n, "vlm_calls": len(labels),
                "peak_sustained": sustained}
    # ── DAHA-BÜYÜK-BÖLGE KONTROLÜ (2026-07, ATTİLA bug fix) ────────────────────────────────
    # Greedy-backward, kuyruktaki İZOLE bir kredi/logo bloğunda takılıp ana bloğu kaçırabiliyor:
    # ATTİLA'da 882 (18 karelik dağıtımcı-logosu) bulup, 539-858 arası 320 karelik ASIL kırmızı
    # kredi scroll'unu görmüyor (aradaki DIEGETIC kartlar geri-yürüyüşü kesiyor).
    # Guard: TAM-PENCERE kaba tara → kredi bölgelerini çıkar → bulunan bölgeden ÖNCE gelen ve
    # ÇOK DAHA BÜYÜK (>=3x kredi-örneği) bir bölge varsa ONA geç. Sadece bu koşulda müdahale eder,
    # normal vakalara (MARIE/ESKİ_ŞEHİR/ÖZGÜRLÜK) dokunmaz — additive & fail-safe.
    try:
        for idx in range(0, n, STRIDE):
            if idx not in labels:
                labels[idx] = classify(frames[idx])
        regions = []           # (r0, r1, ncred) — boşluk-toleranslı (BLANK köprüler, 3 non-credit kırar)
        cur = None; g = 0; nc = 0
        for i in sorted(labels):
            lab = labels[i][0]
            if _is_credit(lab):
                if cur is None: cur = [i, i]; nc = 1; g = 0
                else: cur[1] = i; nc += 1; g = 0
            elif lab == "BLANK":
                if cur is not None: cur[1] = i
            else:
                if cur is not None:
                    g += 1
                    if g > 3:
                        regions.append((cur[0], cur[1], nc)); cur = None; g = 0; nc = 0
        if cur is not None: regions.append((cur[0], cur[1], nc))
        cur_reg = next((r for r in regions if r[0] <= int(start) <= r[1]), None)
        cur_n = cur_reg[2] if cur_reg else 1
        bigger = [r for r in regions if r[0] < int(start) and r[2] >= max(3, cur_n * 3)]
        if bigger:
            b = max(bigger, key=lambda r: r[2])          # en büyük erken bölge
            new_start = _refine_region_start(frames, b[0], labels, n)
            new_sus = _sustained_at(frames, new_start, labels, n)
            if new_sus >= 3:
                start = new_start; sustained = new_sus
                left = start <= STRIDE
                status = "left_censored" if left else "found"
                return {"status": status, "start_frame": int(start), "start_file": frames[int(start)].name,
                        "n_frames": n, "vlm_calls": len(labels), "left_censored": left,
                        "sustained": sustained, "bigger_region_override": True,
                        "regions": regions,
                        "labels": {str(k): list(v) for k, v in sorted(labels.items())}}
    except Exception:  # noqa: BLE001 — guard hatası ana sonucu bozmasın
        pass

    status = "left_censored" if left else "found"
    return {"status": status, "start_frame": int(start), "start_file": frames[int(start)].name,
            "n_frames": n, "vlm_calls": len(labels), "left_censored": left, "sustained": sustained,
            "labels": {str(k): list(v) for k, v in sorted(labels.items())}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    a = ap.parse_args()
    res = detect(Path(a.frames))
    # labels'ı çıktıdan kısalt
    out = {k: v for k, v in res.items() if k != "labels"}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
