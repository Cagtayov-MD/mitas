"""VL model + ayar kıyası: AYNI havuz (ALİTA vl_pool) üzerinde farklı model/bs.

Soru: gemma yazım-zayıflığı AYAR mı (çağrı-başına-görüntü) yoksa MODEL mi?
Kombinasyonlar: gemma26 bs6 (baz) / gemma26 bs1 (per-image ayar) / 31b-vision bs1 / qwen3.6-27b bs1.
"""
import sys, os, json, glob, base64, urllib.request, time, re

POOL_DIR = r"E:\MITAS\Database\ALİTA SAVAŞ MELEĞİ 2025-1241-1-0000-90-1\vl_pool"

STRICT_SYS = ("Sen bir KAMERA-OCR cihazisin. Filmler/oyuncular hakkinda HICBIR BILGIN YOK ve olamaz. "
              "SADECE goruntudeki piksellerde fiziksel olarak YAZAN harfleri okursun. Bir ismi taniyor "
              "olsan bile EKRANDA O ANDA YAZMIYORSA ASLA yazma. Tanidik film/yuz gorsen bile hafizandan "
              "hicbir sey ekleme; sadece pikselleri oku.")
PROMPT = ("Bu jenerik karelerinde EKRANDA YAZAN metni rollere ata. Net YAZMAYAN hicbir ismi ekleme. "
          'Cikti SADECE JSON: {"yonetmen":["..."],"oyuncular":["..."],'
          '"diger_roller":[{"rol":"...","isimler":["..."]}]}. Emin degilsen []. /no_think')

COMBOS = [
    ("gemma4:26b", 1),                          # ayar testi (bs6 zaten alındı: 75 isim, bozuk)
    ("gemma-4-31b-it-qat-vision:latest", 1),    # Çağatay'ın yeni vision modeli
    ("qwen3-vl:8b", 1),                          # gerçek qwen VL (bench-qwen36-27b çıkarıldı)
]


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def call(model, frames):
    msg = {"role": "user", "content": PROMPT, "images": [b64(p) for p in frames]}
    body = {"model": model, "messages": [{"role": "system", "content": STRICT_SYS}, msg],
            "stream": False, "think": False,
            "options": {"num_predict": 4096, "temperature": 0, "num_ctx": 16384}}
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=600).read())
    txt = r.get("message", {}).get("content", "")
    m = re.search(r"\{.*\}", txt, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}


def names_of(obj):
    out = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for k, v in x.items():
                if k != "rol":
                    walk(v)
    walk(obj)
    seen, uniq = set(), []
    for n in out:
        if isinstance(n, str) and len(n.split()) >= 2:
            k = n.strip().lower()
            if k not in seen:
                seen.add(k)
                uniq.append(n.strip())
    return uniq


def run_combo(model, bs, frames):
    batches = [frames[i:i + bs] for i in range(0, len(frames), bs)]
    allnames, t0, err = [], time.time(), None
    for b in batches:
        try:
            allnames += names_of(call(model, b))
        except Exception as e:
            err = repr(e)[:120]
    seen, uniq = set(), []
    for n in allnames:
        if n.lower() not in seen:
            seen.add(n.lower())
            uniq.append(n)
    return {"model": model, "bs": bs, "n": len(uniq), "names": uniq,
            "sec": round(time.time() - t0, 1), "batches": len(batches), "err": err}


if __name__ == "__main__":
    frames = sorted(glob.glob(os.path.join(POOL_DIR, "*.png")))
    print(f"HAVUZ: {len(frames)} görüntü ({POOL_DIR})\n")
    results = []
    for model, bs in COMBOS:
        print(f">>> {model} bs={bs} koşuyor...", flush=True)
        r = run_combo(model, bs, frames)
        results.append(r)
        print(f"    {model} bs={bs}: {r['n']} isim, {r['sec']}s, {r['batches']} batch"
              + (f", HATA={r['err']}" if r['err'] else ""), flush=True)
        for nm in r["names"][:40]:
            print(f"      - {nm}", flush=True)
        print(flush=True)
    print("\n=== ÖZET ===")
    for r in results:
        print(f"{r['model']:38} bs={r['bs']}  isim={r['n']:3}  {r['sec']:6.1f}s"
              + (f"  HATA" if r['err'] else ""))
    json.dump(results, open(r"E:\MITAS\outputs\vl_model_compare_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
