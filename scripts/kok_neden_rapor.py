#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
kok_neden_rapor.py — forensic per-film JSON'larını OneOCR-vs-qwen ekseninde toplar,
detaylı Markdown rapor + Excel üretir.
"""
import os, json, sys, re
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")

SRC = "E:/MITAS/outputs/kok_neden"
MD = "E:/MITAS/outputs/MITAS_KOK_NEDEN_RAPORU_2026-06-15.md"
XLSX = "E:/MITAS/outputs/QC_KOK_NEDEN.xlsx"

# Kök-neden kodu → suçlu aşama
OCR_FRAME = {"S0_FRAME_MISSING", "S1_OCR_GARBLE", "S1_STITCH_DROP"}
QWEN      = {"S2_ROLE_UNMATCHED", "S2_ROLE_OVERREACH", "S4_NOISE_FILTER_MISS",
             "S4_KB_INJECT", "S5_LLM_HALLUCINATION"}
SOURCE    = {"S6_NON_LATIN", "S7_SOURCE_MISSING"}
CLEAN     = {"NONE"}

KOD_TR = {
    "S0_FRAME_MISSING":   "Frame seçimi kartı kaçırdı (CLIP)",
    "S1_OCR_GARBLE":      "OneOCR okudu ama garble (okuma hatası)",
    "S1_STITCH_DROP":     "Stitch/temizlik satırı düşürdü",
    "S2_ROLE_UNMATCHED":  "qwen okudu ama role atayamadı",
    "S2_ROLE_OVERREACH":  "qwen fazla aldı (doğru+çöp birlikte)",
    "S3_QC_DROP":         "QC kapısı eledi",
    "S4_NOISE_FILTER_MISS":"qwen çöpü temizleyemedi",
    "S4_KB_INJECT":       "KB/web yanlış isim soktu",
    "S5_LLM_HALLUCINATION":"qwen uydurdu (halüsinasyon)",
    "S6_NON_LATIN":       "Latin-dışı alfabe (CJK/Kiril/Arap…)",
    "S7_SOURCE_MISSING":  "Kaynakta künye yok",
    "NONE":               "Sorun yok / doğru",
}

def suclu(code):
    if code in OCR_FRAME: return "OneOCR/Frame"
    if code in QWEN:      return "qwen 35b"
    if code in SOURCE:    return "Kaynak/Dil"
    return "—"

# --- Yükle + dedup ---
films = {}
for f in os.listdir(SRC):
    if not f.endswith(".json"):
        continue
    try:
        v = json.load(open(os.path.join(SRC, f), encoding="utf-8"))
    except Exception:
        continue
    trt = v.get("trt") or f[:-5]
    if trt not in films:   # ilk kazanır
        films[trt] = v

vs = list(films.values())
N = len(vs)

def fld(v, f):  return (v.get(f) or {})
def rc(v, f):   return fld(v, f).get("root_cause", "NONE")

# --- Tally'ler ---
prim = Counter(v.get("primary_root_cause", "NONE") for v in vs)
dir_c = Counter(rc(v, "director") for v in vs)
pro_c = Counter(rc(v, "producer") for v in vs)
cas_c = Counter(rc(v, "cast") for v in vs)

# Suçlu aşama dağılımı (primary'e göre)
suclu_prim = Counter(suclu(v.get("primary_root_cause", "NONE")) for v in vs)

# Yönetmen kurtarılabilirlik
dir_rec = Counter(fld(v, "director").get("recoverable", "NA") for v in vs)

# QC-gate-blind benzersiz
qc_blind = sorted({v["trt"] for v in vs if v.get("qc_gate_blind")})

# Dil/script
lang = Counter(v.get("language_script", "UNKNOWN") for v in vs)

# Cast noise token tipleri
noise_types = Counter()
for v in vs:
    for nt in fld(v, "cast").get("noise_tokens", []) or []:
        noise_types[nt.get("type", "OTHER")] += 1

# Bucket → film listesi (primary'e göre)
bucket_films = defaultdict(list)
for v in vs:
    bucket_films[v.get("primary_root_cause", "NONE")].append(v)

def md_tablo(counter, toplam=None):
    toplam = toplam or sum(counter.values())
    rows = []
    for k, n in counter.most_common():
        pct = 100*n/toplam if toplam else 0
        rows.append(f"| {k} | {KOD_TR.get(k,k)} | {suclu(k)} | {n} | %{pct:.0f} |")
    return "\n".join(rows)

# === MARKDOWN RAPOR ===
out = []
out.append("# MITAS KÖK-NEDEN RAPORU — 14-15 Haziran Batch")
out.append(f"\n_Forensic analiz: {N} problemli film, OneOCR→qwen35b pipeline'ı aşama-aşama izlendi (kanıtlı)._\n")

ocr_n = suclu_prim.get("OneOCR/Frame", 0)
qwen_n = suclu_prim.get("qwen 35b", 0)
src_n = suclu_prim.get("Kaynak/Dil", 0)
out.append("## 1. MANŞET — Suçlu kim?\n")
out.append("Her filmin **baskın** kök-nedenine göre sorumlu aşama:\n")
out.append("| Suçlu aşama | Film | Oran |")
out.append("|---|---|---|")
out.append(f"| **qwen 35b** (yorum/rol/temizlik) | **{qwen_n}** | %{100*qwen_n/N:.0f} |")
out.append(f"| **OneOCR / Frame** (okuma/kare) | {ocr_n} | %{100*ocr_n/N:.0f} |")
out.append(f"| **Kaynak/Dil** (Latin-dışı, künye yok) | {src_n} | %{100*src_n/N:.0f} |")
out.append(f"\n**Sonuç:** Sorunların **%{100*qwen_n/N:.0f}'inde veri OCR'da DOĞRU okunmuş, suçlu qwen 35b** "
           f"(yanlış role attı / çöpü temizleyemedi / fazla aldı). Bu filmler **yeniden işlemeden**, "
           f"sadece qwen düzeltilerek kurtarılır.\n")

fromocr = dir_rec.get("FROM_EXISTING_OCR", 0)
out.append(f"> **En önemli sayı:** {fromocr} filmde yönetmen verisi zaten OCR'da mevcut "
           f"(`FROM_EXISTING_OCR`) — qwen düzeltilince re-OCR'sız düzelir.\n")

out.append("## 2. BASKIN KÖK-NEDEN DAĞILIMI (her film 1 oy)\n")
out.append("| Kod | Açıklama | Suçlu | Film | Oran |")
out.append("|---|---|---|---|---|")
out.append(md_tablo(prim, N))

out.append("\n## 3. ALAN BAZLI KÖK-NEDEN\n")
out.append("### 3a. YÖNETMEN\n")
out.append("| Kod | Açıklama | Suçlu | Film | Oran |")
out.append("|---|---|---|---|---|")
out.append(md_tablo(dir_c, N))
out.append("\n### 3b. YAPIMCI\n")
out.append("| Kod | Açıklama | Suçlu | Film | Oran |")
out.append("|---|---|---|---|---|")
out.append(md_tablo(pro_c, N))
out.append("\n### 3c. OYUNCULAR (cast)\n")
out.append("| Kod | Açıklama | Suçlu | Film | Oran |")
out.append("|---|---|---|---|---|")
out.append(md_tablo(cas_c, N))
out.append(f"\n**Cast gürültü token tipleri** (qwen'in temizlemesi gereken): "
           + ", ".join(f"{k}={n}" for k, n in noise_types.most_common()))

out.append("\n## 4. SİSTEMİK KUSUR — QC garble kapısı kör\n")
out.append(f"**{len(qc_blind)} filmde** `garble_frac≈0` / `bucket=GUVENILIR` raporlandı AMA OCR fiilen "
           f"garble/Latin-dışı. Garble dedektörü Latin-çöpe ve CJK'ye **kör** → çöp 'güvenilir' damgası "
           f"alıp pipeline'a giriyor. Bu, qwen'e kirli girdi veren **üst-akış kök-neden**.\n")
out.append("Etkilenen (örnek): " + ", ".join(qc_blind[:20]) + ("…" if len(qc_blind) > 20 else ""))

out.append("\n## 5. DİL/SCRIPT DAĞILIMI\n")
out.append("| Script | Film |")
out.append("|---|---|")
for k, n in lang.most_common():
    out.append(f"| {k} | {n} |")

out.append("\n## 6. ÖNCELİKLİ OPTİMİZASYON YOL HARİTASI\n")
roadmap = [
    ("S2_ROLE_OVERREACH", "qwen 'fazla alma' frenli prompt: bir rol etiketinden ('UN FILM DE', "
     "'DIRECTED BY') sonra GELEN satırları otomatik aynı role ekleme; etiket+TEK isim kuralı + "
     "sonraki satırı oyuncu/teknik say.", prim.get("S2_ROLE_OVERREACH", 0)),
    ("S4_NOISE_FILTER_MISS", "qwen çöp-filtre sözlüğü: COMPANY/FUNDING/DISCLAIMER/ROLE_LABEL "
     "kalıpları (FILMS, PICTURES, ASSOCIATION, AVEC, LOTTERY, ©, COURTESY…) cast'tan zorunlu çıkar.",
     cas_c.get("S4_NOISE_FILTER_MISS", 0)),
    ("S2_ROLE_UNMATCHED", "qwen rol-eşleme: kunye'de TEMİZ isim var ama atanmadı — etiket tanıma "
     "sözlüğünü çok-dilli genişlet (REALISE/REGIA/監督/감독 → yönetmen).", prim.get("S2_ROLE_UNMATCHED", 0)),
    ("S0_FRAME_MISSING", "CLIP frame seçimi: açılış/kapanış yönetmen kartını kaçırıyor — kredi-kartı "
     "kapsamını genişlet (ilk/son N saniye yoğun örnekleme).", prim.get("S0_FRAME_MISSING", 0)),
    ("S6_NON_LATIN+QC", "Garble kapısını CJK/Kiril/Arap farkındalığıyla güçlendir + Latin-dışı filmde "
     "transliterasyon/harici-kimlik yolu; garble_frac'ı script-aware yap.", prim.get("S6_NON_LATIN", 0)),
    ("S1_OCR_GARBLE", "OneOCR okuma: düşük çözünürlük/stilize Latin'de garble — paddle yan-kanal "
     "konsensüsü + üst-örnekleme.", prim.get("S1_OCR_GARBLE", 0)),
]
out.append("| # | Hedef kök-neden | Etki (film) | Düzeltme |")
out.append("|---|---|---|---|")
for i, (k, fix, n) in enumerate(roadmap, 1):
    out.append(f"| {i} | {k} | {n} | {fix} |")
out.append(f"\n**İlk iki madde (qwen overreach + cast çöp-filtre) ~{prim.get('S2_ROLE_OVERREACH',0)+cas_c.get('S4_NOISE_FILTER_MISS',0)} "
           f"alan-hatasını** tek qwen-prompt revizyonuyla kapatır — en yüksek getiri, sıfır re-OCR.\n")

# Per-film detay (ekte özet)
out.append("\n## 7. FİLM BAZLI DETAY\n")
out.append("Tam tablo Excel'de: `QC_KOK_NEDEN.xlsx`. Aşağıda her film tek satır özet:\n")
out.append("| Film | Dil | Primary | Suçlu | Yön | Yapımcı | Cast | Tek cümle |")
out.append("|---|---|---|---|---|---|---|---|")
for v in sorted(vs, key=lambda x: x.get("primary_root_cause", "")):
    nm = v.get("film", v["trt"])[:38]
    p = v.get("primary_root_cause", "NONE")
    out.append(f"| {nm} | {v.get('language_script','')[:4]} | {p} | {suclu(p)} | "
               f"{rc(v,'director')} | {rc(v,'producer')} | {rc(v,'cast')} | {v.get('one_line','')[:80]} |")

open(MD, "w", encoding="utf-8").write("\n".join(out))
print("Markdown rapor :", MD)

# === EXCEL ===
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Film Kök-Neden"

HDR = PatternFill("solid", fgColor="1F4E79")
RED = PatternFill("solid", fgColor="FFCCCC")
ORG = PatternFill("solid", fgColor="FCE4D6")
YEL = PatternFill("solid", fgColor="FFF2CC")
GRN = PatternFill("solid", fgColor="CCFFCC")
GRAY= PatternFill("solid", fgColor="F2F2F2")
BLU = PatternFill("solid", fgColor="CCE5FF")

COLS = ["Film", "TRT", "Dil", "Primary Kök-Neden", "Suçlu Aşama",
        "Yön Durum", "Yön Kök-Neden", "Yön Kurtarma", "Yön Kanıt",
        "Yapımcı Durum", "Yapımcı Kök-Neden",
        "Cast Durum", "Cast Kök-Neden", "Cast Gürültü#", "Cast Eksik?",
        "QC-Kör", "Tek Cümle"]
for c, h in enumerate(COLS, 1):
    cell = ws.cell(1, c, h)
    cell.fill = HDR; cell.font = Font(bold=True, color="FFFFFF", size=9)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
ws.row_dimensions[1].height = 30

def suclu_fill(s):
    return {"qwen 35b": ORG, "OneOCR/Frame": RED, "Kaynak/Dil": YEL}.get(s, GRAY)

r = 1
for v in sorted(vs, key=lambda x: (suclu(x.get("primary_root_cause","")), x.get("primary_root_cause",""))):
    r += 1
    d, pr, ca = fld(v,"director"), fld(v,"producer"), fld(v,"cast")
    p = v.get("primary_root_cause", "NONE")
    s = suclu(p)
    vals = [
        v.get("film", "")[:50], v.get("trt",""), v.get("language_script",""),
        p, s,
        d.get("status",""), d.get("root_cause",""), d.get("recoverable",""), (d.get("evidence","") or "")[:200],
        pr.get("status",""), pr.get("root_cause",""),
        ca.get("status",""), ca.get("root_cause",""),
        len(ca.get("noise_tokens",[]) or []), "EVET" if ca.get("missing_real_cast") else "",
        "EVET" if v.get("qc_gate_blind") else "", (v.get("one_line","") or "")[:120],
    ]
    for c, val in enumerate(vals, 1):
        cell = ws.cell(r, c, val)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        cell.font = Font(size=8)
        if r % 2 == 0: cell.fill = GRAY
    ws.cell(r, 5).fill = suclu_fill(s)   # suçlu aşama renkli
    if v.get("qc_gate_blind"): ws.cell(r, 16).fill = RED

widths = [40,20,7,22,14, 10,20,18,55, 10,20, 10,20,9,9, 7,60]
for i, w in enumerate(widths, 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = "A2"
ws.auto_filter.ref = ws.dimensions

# Özet sekme
ws2 = wb.create_sheet("Özet")
def yaz(ws, row, col, title, counter, tot):
    ws.cell(row, col, title).font = Font(bold=True, size=11)
    ws.cell(row+1, col, "Kod").font = Font(bold=True)
    ws.cell(row+1, col+1, "Açıklama").font = Font(bold=True)
    ws.cell(row+1, col+2, "Suçlu").font = Font(bold=True)
    ws.cell(row+1, col+3, "Film").font = Font(bold=True)
    rr = row+2
    for k, n in counter.most_common():
        ws.cell(rr, col, k); ws.cell(rr, col+1, KOD_TR.get(k,k))
        ws.cell(rr, col+2, suclu(k)); ws.cell(rr, col+3, n)
        rr += 1
    return rr+1

rr = 1
ws2.cell(rr,1,"SUÇLU AŞAMA (baskın kök-neden)").font = Font(bold=True, size=12)
rr += 1
for k,n in suclu_prim.most_common():
    ws2.cell(rr,1,k); ws2.cell(rr,2,n); ws2.cell(rr,3,f"%{100*n/N:.0f}")
    rr += 1
rr += 1
rr = yaz(ws2, rr, 1, "BASKIN KÖK-NEDEN", prim, N)
rr = yaz(ws2, rr, 1, "YÖNETMEN", dir_c, N)
rr = yaz(ws2, rr, 1, "YAPIMCI", pro_c, N)
rr = yaz(ws2, rr, 1, "CAST", cas_c, N)
for c in range(1,5):
    ws2.column_dimensions[get_column_letter(c)].width = [26,40,16,8][c-1]

wb.save(XLSX)
print("Excel          :", XLSX)
print(f"\nÖZET: {N} film | qwen={qwen_n} OneOCR/Frame={ocr_n} Kaynak/Dil={src_n} | "
      f"FROM_EXISTING_OCR(yönetmen)={fromocr} | QC-kör={len(qc_blind)}")
EOF_MARKER = None
