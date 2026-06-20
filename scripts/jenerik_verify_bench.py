# -*- coding: utf-8 -*-
"""JENERİK doğrulayıcı BENCHMARK v2 — "bu bölge gerçekten kredi mi": TÜM seçenekleri yan yana.

Doğrulayıcılar:
  - OCR (OneOCR kelime-içeriği → KREDI/FOOTAGE/DIYALOG kalıbı)         [baseline]
  - ollama VLM: gemma4:26b, gemma3:12b, gemma4:e4b, qwen2.5vl:7b        [backend=ollama]
  - llama-server VLM (F:\\LM GGUF): Qwen3.5-9B, Qwen3.6-27B, gemma-4-31B, Qwen3.6-35B-A3B  [backend=lcpp]

GPU tek-model: ollama'lar önce (kendi aralarında swap), sonra ollama boşaltılır, her lcpp modeli kendi
llama-server'ını başlatır→bölgeleri koşar→kapatır. Model-thrash yok.

Koşum:
  python scripts\jenerik_verify_bench.py --subset hard                       # ayırt-edici ~17 bölge, TÜM modeller
  python scripts\jenerik_verify_bench.py --models ollama:gemma4:26b,lcpp:Qwen3.6-27B
  python scripts\jenerik_verify_bench.py --limit 60                          # tüm 60 film
"""
import sys, json, csv, io, base64, argparse, importlib.util, re, subprocess, time, urllib.request
from pathlib import Path
sys.path.insert(0, r"E:\MITAS")
sys.path.insert(0, r"E:\MITAS\scripts")
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image
from core.pipelines.ocr import jenerik_detector as jd
from _ollama import ollama_chat

_spec = importlib.util.spec_from_file_location("pipeocr", r"E:\MITAS\scripts\_pipe_ocr.py")
po = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(po)

DB = Path(r"E:\MITAS\Database")
OUT = Path(r"E:\MITAS\OCR-worktree")
OLLAMA_HOST = "http://127.0.0.1:11434"
LCPP_BIN = r"E:\NemotronOmni\llamacpp\llama-server.exe"
LCPP_PORT = 8099
FRAME_W = 720
_L = r"F:\LM\lmstudio-community"
LCPP = {
    "Qwen3.5-9B": (fr"{_L}\Qwen3.5-9B-GGUF\Qwen3.5-9B-Q4_K_M.gguf", fr"{_L}\Qwen3.5-9B-GGUF\mmproj-Qwen3.5-9B-BF16.gguf"),
    "Qwen3.6-27B": (fr"{_L}\Qwen3.6-27B-GGUF\Qwen3.6-27B-Q4_K_M.gguf", fr"{_L}\Qwen3.6-27B-GGUF\mmproj-Qwen3.6-27B-BF16.gguf"),
    "gemma-4-31B": (fr"{_L}\gemma-4-31B-it-QAT-GGUF\gemma-4-31B-it-QAT-Q4_0.gguf", fr"{_L}\gemma-4-31B-it-QAT-GGUF\mmproj-gemma-4-31B-it-QAT-BF16.gguf"),
    "Qwen3.6-35B-A3B": (fr"{_L}\Qwen3.6-35B-A3B-GGUF\Qwen3.6-35B-A3B-Q4_K_M.gguf", fr"{_L}\Qwen3.6-35B-A3B-GGUF\mmproj-Qwen3.6-35B-A3B-BF16.gguf"),
}
DEFAULT_MODELS = ["ollama:gemma4:26b", "ollama:gemma3:12b", "ollama:gemma4:e4b", "ollama:qwen2.5vl:7b",
                  "lcpp:Qwen3.5-9B", "lcpp:Qwen3.6-27B", "lcpp:gemma-4-31B", "lcpp:Qwen3.6-35B-A3B"]

# (film-substring, seg) — ayırt-edici zor + kontrol bölgeleri
HARD = [
    ("CENGİZ HANIN", "giris"), ("HANNAH'NIN", "giris"), ("INNISFREE", "giris"), ("INNISFREE", "cikis"),
    ("FIRINCININ KARISI", "giris"), ("DOGMATİK", "giris"), ("ALTINCI ADAM", "giris"), ("ASRİ ZAMANLAR", "cikis"),
    ("MERYEM", "cikis"), ("ÖZEL BİR ANNE", "cikis"), ("WANDA ADINDA", "giris"), ("BABAMIN", "cikis"),
    ("KAOS 2024", "cikis"), ("AMELIA 2024", "cikis"), ("ACI ÇİKOLATA", "giris"), ("BERABER", "giris"),
    ("YERÇEKİMİ", "giris"),
]

VLM_PROMPT = (
    "Bu kareler bir filmin aynı KISA bölümünden alınmıştır. İçeriğe bakıp SADECE tek kelimeyle sınıflandır:\n"
    "KREDI = film jeneriği: oyuncu/ekip İSİM LİSTESİ, başlık-künye kartı, kayan isim listesi, stüdyo logosu.\n"
    "FOOTAGE = sahne/manzara/insan görüntüsü; jenerik yazısı YOK.\n"
    "DIYALOG = filmin içindeki konuşma-altyazısı, sessiz-film diyalog kartı veya sahne-içi tabela (jenerik DEĞİL).\n"
    "Yalnızca şu üç kelimeden birini yaz: KREDI veya FOOTAGE veya DIYALOG. /no_think"
)


def _b64(path):
    im = Image.open(path).convert("RGB")
    if im.width > FRAME_W:
        im = im.resize((FRAME_W, round(im.height * FRAME_W / im.width)))
    buf = io.BytesIO(); im.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def wordlike(lines):
    out = []
    for s in lines:
        s = (s or "").strip()
        if len(s) < 3 or sum(c.isalpha() for c in s) < 3:
            continue
        try:
            if po.is_noise(s) or po.alpha_ratio(s) < 0.5:
                continue
        except Exception:
            pass
        out.append(s)
    return out


def ocr_verdict(lines):
    n = len(lines)
    if n < 2:
        return "FOOTAGE"
    sent = sum(1 for w in lines if len(w.split()) >= 5 or w.rstrip().endswith("."))
    return "DIYALOG" if sent >= max(2, n * 0.5) else "KREDI"


def _parse(txt):
    txt = (txt or "").strip().upper().replace("İ", "I")
    for k in ("FOOTAGE", "DIYALOG", "DIALOG", "KREDI", "CREDIT", "RED"):
        if k in txt:
            return {"DIALOG": "DIYALOG", "CREDIT": "KREDI"}.get(k, k)
    return (txt[:12] or "?")


def ollama_verdict(model, b64s):
    resp = ollama_chat(model=model, messages=[{"role": "user", "content": VLM_PROMPT, "images": b64s}],
                       timeout=180, host=OLLAMA_HOST, think=False, keep_alive="20m",
                       options={"temperature": 0, "top_p": 1, "num_predict": 24, "num_ctx": 4096, "repeat_penalty": 1.2})
    return _parse(resp.get("message", {}).get("content")) if resp else "ERR"


def ollama_unload(models):
    for m in models:
        try:
            urllib.request.urlopen(urllib.request.Request(
                OLLAMA_HOST + "/api/chat",
                data=json.dumps({"model": m, "messages": [{"role": "user", "content": "x"}], "keep_alive": 0, "stream": False}).encode(),
                headers={"Content-Type": "application/json"}), timeout=20)
        except Exception:
            pass
    time.sleep(4)


def lcpp_start(short):
    gguf, mm = LCPP[short]
    log = open(OUT / f"_lcpp_{re.sub(r'[^a-zA-Z0-9]', '_', short)}.log", "w", encoding="utf-8")
    proc = subprocess.Popen([LCPP_BIN, "-m", gguf, "--mmproj", mm, "--host", "127.0.0.1",
                             "--port", str(LCPP_PORT), "-ngl", "99", "-c", "8192"],
                            stdout=log, stderr=subprocess.STDOUT)
    for _ in range(300):
        if proc.poll() is not None:
            return None
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{LCPP_PORT}/health", timeout=2) as r:
                if r.status == 200:
                    return proc
        except Exception:
            pass
        time.sleep(1)
    proc.terminate(); return None


def lcpp_stop(proc):
    try:
        proc.terminate(); proc.wait(15)
    except Exception:
        try: proc.kill()
        except Exception: pass
    time.sleep(4)


def lcpp_verdict(b64s):
    content = [{"type": "text", "text": VLM_PROMPT}]
    content += [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in b64s]
    payload = {"messages": [{"role": "user", "content": content}], "temperature": 0, "max_tokens": 512, "stream": False}
    req = urllib.request.Request(f"http://127.0.0.1:{LCPP_PORT}/v1/chat/completions",
                                data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=200) as r:
            d = json.loads(r.read())
        return _parse(d["choices"][0]["message"].get("content"))
    except Exception:
        return "ERR"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subset", choices=["hard"], default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--models", default=None)
    ap.add_argument("--out", default=str(OUT / "jenerik_verify_bench.csv"))
    a = ap.parse_args()
    models = [m.strip() for m in a.models.split(",")] if a.models else DEFAULT_MODELS

    gt = {}
    try:
        for r in json.load(open(OUT / "jenerik_qc_ALL.json", encoding="utf-8")):
            key = re.sub(r"[^a-z0-9]", "", r["film"].lower())
            gt[(key, "giris")] = r["giris_verdict"]; gt[(key, "cikis")] = r["cikis_verdict"]
    except Exception:
        pass

    # bölge listesi (subset hard veya tüm filmler)
    if a.subset == "hard":
        targets = HARD
    else:
        films = json.load(open(OUT / "jenerik_qc60_compact.json", encoding="utf-8"))
        if a.limit:
            films = films[:a.limit]
        targets = [(f["film"], s) for f in films for s in ("giris", "cikis")]

    ctx = jd.load_clip()
    eng, ename, _ = po.build_engine()
    print(f"CLIP+OCR({ename}) | {len(models)} model | {len(targets)} bölge | k={a.k}\n", flush=True)

    # PASS0: tespit + örnekle + OCR
    regions = []
    seen = set()
    for ti, (q, seg) in enumerate(targets, 1):
        fd = [x for x in DB.iterdir() if x.name == q] or [x for x in DB.iterdir() if q.lower() in x.name.lower()]
        if not fd:
            print(f"  YOK {q}", flush=True); continue
        fdir = fd[0] / "frames" / seg
        rk = (fd[0].name, seg)
        if rk in seen or not fdir.is_dir():
            continue
        seen.add(rk)
        print(f"  PASS0 [{ti}/{len(targets)}] {fd[0].name[:34]} {seg}", flush=True)
        key = re.sub(r"[^a-z0-9]", "", fd[0].name.lower())
        row = {"film": fd[0].name, "seg": seg, "gt": gt.get((key, seg), "?"),
               "region": "ERR", "ocr": "ERR", "b64": [], "ocr_sample": ""}
        try:
            paths = sorted(fdir.glob("*.png"))
            reg = jd.detect_from_frames(str(fdir), prefer=("first" if seg == "giris" else "last"), clip_ctx=ctx)
            if not reg.get("found"):
                row.update(region="RED", ocr="RED")
            else:
                aa, bb = reg["start_frame"], reg["end_frame"]
                n = min(a.k, bb - aa + 1)
                idxs = sorted(set(aa + int(i * (bb - aa) / max(1, n - 1)) for i in range(n)))
                fps = [paths[i] for i in idxs if 0 <= i < len(paths)]
                words = []
                for p in fps:
                    try: words += wordlike(po.ocr_frame(eng, p))
                    except Exception: pass
                words = list(dict.fromkeys(words))
                row.update(region=f"[{aa}-{bb}]", quad=reg["quad_type"], ocr=ocr_verdict(words),
                           ocr_sample=", ".join(words[:4])[:55], b64=[_b64(p) for p in fps])
        except Exception as e:
            print(f"    HATA: {type(e).__name__}: {e}", flush=True)
        regions.append(row)
    # PASS0 checkpoint: b64'süz satırları diske yaz (segfault olursa partial kurtulur)
    try:
        import json as _json
        _json.dump([{k: v for k, v in r.items() if k != "b64"} for r in regions],
                   open(a.out.replace(".csv", "_pass0.json"), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass
    print(f"PASS0 bitti: {len(regions)} bölge hazır\n", flush=True)

    ollama_models = [m.split(":", 1)[1] for m in models if m.startswith("ollama:")]
    # ollama passes
    for spec in [m for m in models if m.startswith("ollama:")]:
        name = spec.split(":", 1)[1]
        print(f"=== ollama {name} ===", flush=True)
        for r in regions:
            r[spec] = ollama_verdict(name, r["b64"]) if r.get("b64") else "RED"
        print(f"  bitti", flush=True)
    # lcpp passes
    lcpp_specs = [m for m in models if m.startswith("lcpp:")]
    if lcpp_specs:
        ollama_unload(ollama_models)
        for spec in lcpp_specs:
            short = spec.split(":", 1)[1]
            print(f"=== lcpp {short} (server başlatılıyor) ===", flush=True)
            proc = lcpp_start(short)
            if proc is None:
                print(f"  {short}: SERVER YÜKLENEMEDİ (log'a bak)", flush=True)
                for r in regions: r[spec] = "LOAD_ERR"
                continue
            for r in regions:
                r[spec] = lcpp_verdict(r["b64"]) if r.get("b64") else "RED"
            lcpp_stop(proc)
            print(f"  {short}: bitti + server kapandı", flush=True)

    cols = ["film", "seg", "gt", "region", "quad", "ocr"] + models + ["ocr_sample"]
    with open(a.out, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in regions:
            w.writerow(r)
    print(f"\n-> CSV: {a.out}  ({len(regions)} bölge)", flush=True)


if __name__ == "__main__":
    main()
