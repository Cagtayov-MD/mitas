"""OCR-pipeline akış diyagramı (YAŞAYAN harita — kararlar değiştikçe bu script güncellenir).
Çıktı: E:\\MITAS\\OCR-worktree\\OCR-pipeline.png   (sabit isim, üzerine yazılır)
Üretici sabit isimli (zaman damgasız) — çünkü tek bir güncel diyagram tutuyoruz.
"""
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = r"E:\MITAS\OCR-worktree\OCR-pipeline.png"
fig, ax = plt.subplots(figsize=(14, 11)); ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

def box(cx, cy, w, h, title, body, fc, ec, tc="#111"):
    ax.add_patch(FancyBboxPatch((cx-w/2, cy-h/2), w, h,
        boxstyle="round,pad=0.3,rounding_size=1.4", fc=fc, ec=ec, lw=1.8))
    ax.text(cx, cy+h*0.26, title, ha="center", va="center", fontsize=11.5, fontweight="bold", color=tc)
    if body: ax.text(cx, cy-h*0.20, body, ha="center", va="center", fontsize=8.6, color=tc)

def arrow(x0, y0, x1, y1, label=None, c="#555", lab_dx=1.4):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=c, lw=1.7, shrinkA=0, shrinkB=0))
    if label:
        ax.text((x0+x1)/2+lab_dx, (y0+y1)/2, label, fontsize=8.5, color=c, ha="left", va="center",
                fontstyle="italic")

# renkler
RED="#f6d4d7"; REDE="#c0392b"; BLU="#d6e8fb"; BLUE="#2878c8"; PUR="#e7dcf6"; PURE="#7d4fc0"
GRN="#d8f0d8"; GRNE="#3a9d3a"; GLD="#ffe39a"; GLDE="#b8860b"; GRY="#e3e3e3"; GRYE="#888"

# başlık
ax.text(50, 98.5, "OCR PIPELINE — jenerik → tek master PNG", ha="center", fontsize=16, fontweight="bold")
ax.text(50, 95.4, "FINAL KARAR (şimdilik): ① BEKÇİ ✓(göz 5/5) · ② split ✓ · ③ reconstruct ✓ · ④ diz ✓  —  İLK BÜYÜK TEST · 2026-05-30", ha="center", fontsize=8, color="#666")

# kutular
box(49, 90, 30, 5.5, "SEGMENT (kareler)", "ffmpeg ile çıkarılan jenerik segmenti", "#f0f0f0", "#999")
box(49, 80, 54, 9.5, "①  BEKÇİ — jenerik mi, film mi?",
    "GÖZ (qwen2.5vl) + dy  ·  is_credit 5/5 + dizide genelledi\nÇALIŞIYOR ✓  (keystone)", GRN, GRNE)
box(88, 80, 19, 7, "ATLA", "film footage\n→ işleme", GRY, GRYE)
box(49, 66, 54, 9.5, "②  ZAMAN-ÇİZGİSİ AYIRICI  (dy durum makinesi)",
    "segmenti homojen bloklara böl:  [STATİK][SCROLL][CUT]…\n'yarı scroll yarı statik' burada çözülür   [ prototip ✓ ]", BLU, BLUE)
box(49, 53, 54, 8, "③  4-KUTU  —  her blok için: HAREKET × ARKA PLAN",
    "arka plan? = yazı-maskeli dy  vs  maske-dışı dy", PUR, PURE)

# 4 yaprak (blok bazında motorlar)
leaves = [
    (15, "SCROLL + zemin\nSABİT / SİYAH", "→ KARAR 1\ndüz slit-scan\n[ kanıtlı ✓ ]", BLU, BLUE),
    (37.7, "SCROLL + zemin\nHAREKETLİ", "→ KARAR 3\nYOL1 ✓ (yabandan/marie)\nYOL2 aday (Anjelik)", BLU, BLUE),
    (60.3, "STATİK + zemin\nSABİT", "→ KARAR 2\nduran koşu\n[ kanıtlı ✓ ]", GRN, GRNE),
    (83, "STATİK + zemin\nHAREKETLİ", "→ temporal medyan\n[ test edilmedi ]", GRN, GRNE),
]
for cx, t, b, fc, ec in leaves:
    box(cx, 39, 21, 15, t, b, fc, ec)

box(49, 22, 40, 8, "④  DİZ", "blok master'larını SIRAYLA birleştir", GRN, GRNE)
box(49, 11, 30, 7, "SEGMENT MASTER", "tek uzun PNG · her satır bir kez", GLD, GLDE)

# oklar
arrow(49, 87.2, 49, 85.0)                                  # segment -> bekçi
arrow(49, 75.2, 49, 71.0, "jenerik ↓")                     # bekçi -> ayırıcı
arrow(76.2, 80, 78.5, 80, "film", c=REDE)                  # bekçi -> atla
arrow(49, 61.2, 49, 57.2, "her blok ↓")                    # ayırıcı -> 4-kutu
for cx, *_ in leaves:                                       # 4-kutu -> yapraklar
    arrow(49, 49.0, cx, 46.7, c="#888")
for cx, *_ in leaves:                                       # yapraklar -> diz
    arrow(cx, 31.4, 49, 26.2, c="#888")
arrow(49, 18.0, 49, 14.6)                                   # diz -> master

ax.text(50, 3.0, "güncellenebilir harita — kararlar değiştikçe py/pipeline_diagram.py yenilenir · "
        "test günlüğü: py-log.md · kararlar: ocr-opus-final.md",
        ha="center", fontsize=8, color="#888", fontstyle="italic")

plt.savefig(OUT, dpi=150, bbox_inches="tight"); plt.close()
print("OK ->", OUT)
