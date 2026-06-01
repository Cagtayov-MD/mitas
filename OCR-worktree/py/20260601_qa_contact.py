"""QA KONTAK-SAYFASI — şüpheli master'ları küçültüp tek görüntüde dizer (footage/black/bloat gözle ayırt etmek için).
SADECE denetim amaçlı küçültme (teslimat değil). Türkçe-path -> imdecode/imencode.
Çıktı: clip_pipeline100/_QA_CONTACT.png
"""
import sys, json
from pathlib import Path
import numpy as np, cv2
sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(r"E:\MITAS\OCR-worktree\clip_pipeline100")
MAST = OUT/"_MASTERS"

def imread_u(p):
    return cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
def imwrite_u(p, img):
    ok, buf = cv2.imencode(Path(p).suffix, img)
    if ok: buf.tofile(str(p))

rows = json.loads((OUT/"_TRIAGE.json").read_text(encoding="utf-8"))
top = rows[:15]
controls = [r for r in rows if r["score"] == 0][:3]
sel = top + controls

CW, CH, LBL = 240, 760, 46
cells = []
for r in sel:
    p = MAST/f"{r['film']}.png"
    img = imread_u(p)
    canvas = np.zeros((CH, CW, 3), np.uint8)
    if img is not None:
        h, w = img.shape[:2]
        sc = min(CW/w, CH/h)
        img = cv2.resize(img, (max(1, int(w*sc)), max(1, int(h*sc))))
        yh, xw = img.shape[:2]
        canvas[(CH-yh)//2:(CH-yh)//2+yh, (CW-xw)//2:(CW-xw)//2+xw] = img
    lbl = np.full((LBL, CW, 3), 40, np.uint8)
    name = r["film"].replace("_1_0000", "").replace("__", " ")[:32]
    cv2.putText(lbl, name, (3, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(lbl, f"h{r['h']} k{r['kunye']} p/l{r['ppl']}", (3, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (0, 255, 255), 1, cv2.LINE_AA)
    cell = cv2.copyMakeBorder(np.vstack([lbl, canvas]), 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(90, 90, 90))
    cells.append(cell)

COLS = 6
h0, w0 = cells[0].shape[:2]
while len(cells) % COLS:
    cells.append(np.zeros((h0, w0, 3), np.uint8))
sheet = np.vstack([np.hstack(cells[i:i+COLS]) for i in range(0, len(cells), COLS)])
out = OUT/"_QA_CONTACT.png"
imwrite_u(out, sheet)
print(f"{len(sel)} hücre -> {out}  ({sheet.shape[1]}x{sheet.shape[0]})")
for i, r in enumerate(sel):
    print(f"  {i:2} {r['film'][:46]:46} h={r['h']:>6} k={r['kunye']:>4} p/l={r['ppl']:>5}  {','.join(r['flags'])}")
