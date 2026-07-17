"""Üretim-gerçekçi hız testi: CAP'li havuz (12 görüntü) + gemma26 bs=1/2/3.
Soru: bs ortası (2-3) hızı düşürürken yazımı koruyor mu? Üretimde kaç saniye?
"""
import sys, os, json, glob, base64, urllib.request, time, re

POOL_DIR = r"E:\MITAS\Database\ALİTA SAVAŞ MELEĞİ 2025-1241-1-0000-90-1\vl_pool"
CAP = 12
MODEL = "gemma4:26b"

STRICT_SYS = ("Sen bir KAMERA-OCR cihazisin. Filmler/oyuncular hakkinda HICBIR BILGIN YOK ve olamaz. "
              "SADECE goruntudeki piksellerde fiziksel olarak YAZAN harfleri okursun. Bir ismi taniyor "
              "olsan bile EKRANDA O ANDA YAZMIYORSA ASLA yazma. Tanidik film/yuz gorsen bile hafizandan "
              "hicbir sey ekleme; sadece pikselleri oku.")
PROMPT = ("Bu jenerik karelerinde EKRANDA YAZAN metni rollere ata. Net YAZMAYAN hicbir ismi ekleme. "
          'Cikti SADECE JSON: {"yonetmen":["..."],"oyuncular":["..."],'
          '"diger_roller":[{"rol":"...","isimler":["..."]}]}. Emin degilsen []. /no_think')


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def call(frames):
    msg = {"role": "user", "content": PROMPT, "images": [b64(p) for p in frames]}
    body = {"model": MODEL, "messages": [{"role": "system", "content": STRICT_SYS}, msg],
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
        if isinstance(n, str) and len(n.split()) >= 2 and n.strip().lower() not in seen:
            seen.add(n.strip().lower())
            uniq.append(n.strip())
    return uniq


def run_bs(frames, bs):
    batches = [frames[i:i + bs] for i in range(0, len(frames), bs)]
    allnames, t0 = [], time.time()
    for b in batches:
        try:
            allnames += names_of(call(b))
        except Exception as e:
            print(f"    batch hata: {repr(e)[:80]}", flush=True)
    seen, uniq = set(), []
    for n in allnames:
        if n.lower() not in seen:
            seen.add(n.lower())
            uniq.append(n)
    return uniq, round(time.time() - t0, 1), len(batches)


if __name__ == "__main__":
    allf = sorted(glob.glob(os.path.join(POOL_DIR, "*.png")))
    # CAP'e eşit-aralıklı örnekle (üretim havuzu simülasyonu)
    if len(allf) > CAP:
        frames = [allf[int(len(allf) * i / CAP)] for i in range(CAP)]
    else:
        frames = allf
    print(f"HAVUZ: {len(allf)} -> CAP {len(frames)} gorsel, model={MODEL}\n")
    results = []
    for bs in (1, 2, 3):
        print(f">>> bs={bs} koşuyor ({-(-len(frames)//bs)} batch)...", flush=True)
        names, sec, nb = run_bs(frames, bs)
        results.append({"bs": bs, "n": len(names), "sec": sec, "batches": nb, "names": names})
        print(f"    bs={bs}: {len(names)} isim, {sec}s, {nb} batch", flush=True)
        for nm in names[:30]:
            print(f"      - {nm}", flush=True)
        print(flush=True)
    print("=== ÖZET (CAP'li üretim-gerçekçi) ===")
    for r in results:
        print(f"  bs={r['bs']}  isim={r['n']:3}  {r['sec']:6.1f}s  ({r['batches']} batch)")
    json.dump(results, open(r"E:\MITAS\outputs\vl_speed_test_result.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
