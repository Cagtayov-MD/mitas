"""ÖZET MODEL TESTİ — ozet_promt.txt + transcript -> Ollama /api/chat (think destekli).
Kullanım: python 20260601_ozet_test.py <model> [transcript_yolu] [think:0/1]
"""
import sys, re, json, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3.6:35b-a3b"
TSCR = sys.argv[2] if len(sys.argv) > 2 else r"F:\REPO_GitHub\DATABASE\TAM ZAMANINDA 1997-0239-1-0000-00-1\1997-0239-1-0000-00-1 TAM ZAMANINDA_tscr.txt"
THINK = (sys.argv[3].strip().lower() in ("1", "true", "think", "yes")) if len(sys.argv) > 3 else True

ozet = open(r"E:\MITAS\OCR-worktree\ozet_promt.txt", encoding="utf-8").read()
lines = open(TSCR, encoding="utf-8", errors="ignore").read().splitlines()
dlg = [m.group(1) for ln in lines if (m := re.match(r"\[\d\d:\d\d:\d\d\]\s*(.*)", ln)) and m.group(1).strip()]
if not dlg:
    dlg = [ln.strip() for ln in lines if ln.strip()]
user = "\n".join(dlg)

payload = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": ozet},
        {"role": "user", "content": user},
    ],
    "stream": False,
    "think": THINK,
    "options": {"temperature": 0.3, "num_ctx": 20480},
}
print(f"MODEL={MODEL}  THINK={THINK}  diyalog_satiri={len(dlg)}  karakter={len(user)}", flush=True)
t0 = time.time()
req = urllib.request.Request(
    "http://localhost:11434/api/chat",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=900) as r:
    res = json.loads(r.read().decode("utf-8"))
dt = time.time() - t0
msg = res.get("message", {}) or {}
think = (msg.get("thinking") or "").strip()
content = (msg.get("content") or "").strip()
if think:
    print("\n===== DÜŞÜNCE (thinking) =====\n" + think, flush=True)
print("\n===== ÖZET =====\n" + content, flush=True)
print(f"\n----- {dt:.1f}s | {len(content.split())} kelime | {len(content)} karakter -----", flush=True)
