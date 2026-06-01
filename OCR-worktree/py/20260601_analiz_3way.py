"""15-film 3-okuyucu DERİN ANALİZ — satır farkı nereden? kim fazla/az okuyor, neden, doğruluk ne?
Her master'ın oneocr/paddle/qwen.txt'sini okur; satırları çöp/kısa/sağlam sınıflar; fark kaynağını,
qwen'in az-okuma desenini (yoğun mu bozuk mu), uzlaşma(doğruluk proxy) oranını çıkarır.
Çıktı: tester_3way/_ANALIZ.md (açıklamalı) + stdout.
"""
import sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(r"E:\MITAS\OCR-worktree\tester_3way")

def fold(s):
    s=(s or "").lower()
    for a,b in [("ı","i"),("İ","i"),("i̇","i"),("ş","s"),("ğ","g"),("ç","c"),("ö","o"),("ü","u"),("'",""),("-"," ")]:
        s=s.replace(a,b)
    return " ".join(s.split())

TR_V=set("aeıioöuüAEIİOÖUÜ")
def cls(t):
    """çöp / kısa / sağlam"""
    s=t.strip(); a=[c for c in s if c.isalpha()]
    if len(s)<=2 or len(a)<3: return "cop"
    if not any(c in TR_V for c in s): return "cop"            # RGTNRN, SKA, 2113
    body=s.replace(" ","")
    if len(set(body))<=2: return "cop"                        # AAAA, SOSO
    toks=[w for w in s.split() if any(c.isalpha() for c in w)]
    if len(toks)<=1 and len(a)<=4: return "kisa"              # Han, Hal, Fra (şüpheli parça)
    return "saglam"

def load(label,seg,fn):
    f=OUT/label/seg/fn
    return [x for x in f.read_text(encoding="utf-8").splitlines() if x.strip()] if f.exists() else []

masters=[]
for cj in sorted(OUT.glob("*/*/compare.json")):
    r=json.loads(cj.read_text(encoding="utf-8"))
    lb,sg=r["label"],r["seg"]; H=r.get("h",0)
    one=load(lb,sg,"oneocr.txt"); pad=load(lb,sg,"paddle.txt"); qwn=load(lb,sg,"qwen.txt")
    masters.append(dict(lb=lb,sg=sg,H=H,one=one,pad=pad,qwn=qwn))

def counts(lines):
    c={"cop":0,"kisa":0,"saglam":0}
    for t in lines: c[cls(t)]+=1
    return c

# ── toplamlar ───────────────────────────────────────────────────────────────
TOT={k:{"cop":0,"kisa":0,"saglam":0,"n":0} for k in ("one","pad","qwn")}
for m in masters:
    for k in ("one","pad","qwn"):
        c=counts(m[k]); TOT[k]["n"]+=len(m[k])
        for b in ("cop","kisa","saglam"): TOT[k][b]+=c[b]

# ── fark kaynağı: paddle-only / oneocr-only / qwen-missing (sağlam sınıfı) ────
pad_only_sag=[]; one_only_sag=[]; qwn_miss_sag=[]; pad_only_cop=0; one_only_cop=0
for m in masters:
    fo={fold(x) for x in m["one"]}; fp_={fold(x) for x in m["pad"]}; fq={fold(x) for x in m["qwn"]}
    for t in m["pad"]:
        if fold(t) not in fo and fold(t) not in fq:
            if cls(t)=="saglam": pad_only_sag.append((m["lb"],m["sg"],t))
            elif cls(t)=="cop": pad_only_cop+=1
    for t in m["one"]:
        if fold(t) not in fp_ and fold(t) not in fq:
            if cls(t)=="saglam": one_only_sag.append((m["lb"],m["sg"],t))
            elif cls(t)=="cop": one_only_cop+=1
    # qwen'in kaçırdığı SAĞLAM içerik (one veya pad'de sağlam, qwen'de yok)
    for t in m["one"]:
        if cls(t)=="saglam" and fold(t) not in fq and fold(t) in fp_:  # iki klasik okuyucu da görmüş, qwen yok
            qwn_miss_sag.append((m["lb"],m["sg"],t))

# ── qwen tamlık deseni: qwen_n / max(one,pad) per film, H ile ─────────────────
qrows=[]
for m in masters:
    base=max(len(m["one"]),len(m["pad"])) or 1
    qrows.append((m["lb"]+"/"+m["sg"], len(m["one"]), len(m["pad"]), len(m["qwn"]),
                  round(len(m["qwn"])/base*100), m["H"], counts(m["qwn"])["cop"], counts(m["pad"])["cop"]))

# ── doğruluk proxy: her okuyucunun SAĞLAM satırlarının kaçı ≥1 başka okuyucuca teyitli ──
def confirm_rate(key, others):
    conf=tot=0
    for m in masters:
        osets=[{fold(x) for x in m[o]} for o in others]
        for t in m[key]:
            if cls(t)!="saglam": continue
            tot+=1
            if any(fold(t) in s for s in osets): conf+=1
    return conf, tot

cr_one=confirm_rate("one",["pad","qwn"]); cr_pad=confirm_rate("pad",["one","qwn"]); cr_qwn=confirm_rate("qwn",["one","pad"])

# ── MARKDOWN üret ─────────────────────────────────────────────────────────────
L=[]; P=lambda s="": (L.append(s), print(s))
def pct(n,d): return f"{n/max(d,1)*100:.0f}%"

P("# 15-FİLM 3-OKUYUCU — DERİN ANALİZ (kim fazla/az okuyor, neden, doğruluk?)")
P(f"_29 master · OneOCR / Paddle-tr / qwen2.5vl:7b · satırlar **çöp/kısa/sağlam** sınıflandı_")
P("")
P("## 0) KISA CEVAP")
gap_pad=TOT["pad"]["n"]-TOT["one"]["n"]; gap_qwn=TOT["one"]["n"]-TOT["qwn"]["n"]
P(f"- **Toplam satır:** OneOCR {TOT['one']['n']} · Paddle {TOT['pad']['n']} · qwen {TOT['qwn']['n']}")
P(f"- **Paddle'ın +{gap_pad} fazlası** ÇOĞUNLUKLA **çöp+parça**: Paddle'da {TOT['pad']['cop']} çöp + {TOT['pad']['kisa']} kısa-parça var "
  f"(OneOCR'da {TOT['one']['cop']}+{TOT['one']['kisa']}). **Sağlam** satırda fark küçük: OneOCR {TOT['one']['saglam']} vs Paddle {TOT['pad']['saglam']}.")
P(f"- **qwen'in -{gap_qwn} eksiği** çoğunlukla **çöp ÜRETMEMESİ** (qwen çöp={TOT['qwn']['cop']}, dürüst) + yoğun/bozuk bölümde gerçek kaçırma karışık.")
P("")
P("## 1) SATIRLARI SINIFLAYINCA — asıl tablo")
P("")
P("| okuyucu | toplam | sağlam | kısa-parça | çöp | sağlam oranı |")
P("|---|--:|--:|--:|--:|--:|")
for k,nm in [("one","OneOCR"),("pad","Paddle-tr"),("qwn","qwen")]:
    t=TOT[k]; P(f"| {nm} | {t['n']} | **{t['saglam']}** | {t['kisa']} | {t['cop']} | {pct(t['saglam'],t['n'])} |")
P("")
P("> **Yorum:** Ham satırda Paddle önde ama bu fark büyük ölçüde **çöp/parça**. Gerçek içerik (**sağlam**) "
  f"sayısında OneOCR {TOT['one']['saglam']} / Paddle {TOT['pad']['saglam']} / qwen {TOT['qwn']['saglam']} — "
  "yani 'okunabilir gerçek satır' bakımından OneOCR ve Paddle başa baş, qwen geride.")
P("")
P("## 2) PADDLE NEDEN FAZLA OKUYOR? (Paddle-only satırların içeriği)")
P(f"- Paddle'ın tek başına ürettiği **çöp** satır (diğer ikisinde yok): **{pad_only_cop}** adet — bunlar gürültü, isim değil.")
P(f"- Paddle'ın tek başına yakaladığı **sağlam** satır: **{len(pad_only_sag)}** adet — örnekler (gerçek mi parça mı, sen bak):")
for lb,sg,t in pad_only_sag[:18]: P(f"   - `{lb}/{sg}`  {t}")
P("")
P("## 3) ONEOCR NEYİ TEK BAŞINA YAKALIYOR? (OneOCR-only sağlam)")
P(f"- OneOCR tek başına çöp: {one_only_cop} | tek başına **sağlam**: {len(one_only_sag)} — örnekler:")
for lb,sg,t in one_only_sag[:18]: P(f"   - `{lb}/{sg}`  {t}")
P("")
P("## 4) QWEN SADECE YOĞUNLARI MI OKUMUYOR? (tamlık deseni)")
P("")
P("| film/seg | OneOCR | Paddle | qwen | qwen% | yükseklik px | qwen-çöp | Paddle-çöp |")
P("|---|--:|--:|--:|--:|--:|--:|--:|")
for nm,o,p,q,qp,H,qc,pc in sorted(qrows,key=lambda x:x[4]):
    P(f"| {nm} | {o} | {p} | {q} | **{qp}%** | {H} | {qc} | {pc} |")
P("")
P("> **Yorum:** qwen% düşük olan filmlere bak: bunlar genelde **bozuk/eski** kaynak (qwen çöp üretmeyip susuyor) "
  "ya da çok-yoğun. Büyük/yoğun ama TEMİZ kredilerde (X-MEN, JURASSIC çıkış) qwen ~%80+ tutuyor → "
  "yani 'yoğun olduğu için değil, KALİTE düşünce' az okuyor; ek olarak çöp üretmediği için sayısı doğal olarak düşük.")
P("")
P(f"- qwen'in kaçırdığı, **iki klasik okuyucunun da gördüğü SAĞLAM** içerik: **{len(qwn_miss_sag)}** satır (gerçek kayıp) — örnekler:")
for lb,sg,t in qwn_miss_sag[:18]: P(f"   - `{lb}/{sg}`  {t}")
P("")
P("## 5) DOĞRULUK PROXY'Sİ (ground-truth yok → çapraz-teyit)")
P("Bir okuyucunun **sağlam** satırının kaçı **en az bir başka okuyucu** tarafından da görülmüş (fold). Yüksek=güvenilir.")
P("")
P("| okuyucu | sağlam satır | ≥1 teyitli | teyit oranı |")
P("|---|--:|--:|--:|")
for nm,(c,t) in [("OneOCR",cr_one),("Paddle-tr",cr_pad),("qwen",cr_qwn)]:
    P(f"| {nm} | {t} | {c} | **{pct(c,t)}** |")
P("")
P("> Düşük teyit oranı = çok 'tek başına' satır = ya benzersiz-doğru-yakalama ya benzersiz-hata. "
  "OneOCR/Paddle teyit oranı yüksekse içerikleri büyük ölçüde örtüşüyor (güvenilir). "
  "Diakritik doğruluğu ayrı: Türkçe filmde OneOCR ş/ğ/ı/İ'de lider (önceki rapor).")
P("")
P("## 6) SONUÇ")
P(f"1. **Satır farkı yanıltıcı.** Paddle'ın +{gap_pad} fazlası ağırlıkla çöp/parça; gerçek-içerik (sağlam) farkı küçük.")
P(f"2. **Kimse büyük gerçek-içerik kaçırmıyor** klasik okuyucularda: OneOCR-only sağlam {len(one_only_sag)}, Paddle-only sağlam {len(pad_only_sag)} — birbirini tamamlıyor.")
P(f"3. **qwen** hem çöp üretmediği (dürüst, {TOT['qwn']['cop']} çöp) hem de bozuk/yoğun-kalitesiz bölümde sustuğu için az; "
  f"ama **iki okuyucunun gördüğü {len(qwn_miss_sag)} sağlam satırı kaçırmış** = gerçek bir tamlık açığı.")
P("4. **Pratik:** kapsama+hız için OneOCR/Paddle-tr; qwen yalnız kısa/şüpheli yerde derin-kontrol. Birleştirince çöp elenir, sağlam birleşir.")

(OUT/"_ANALIZ.md").write_text("\n".join(L),encoding="utf-8")
print(f"\n-> {OUT/'_ANALIZ.md'}")
