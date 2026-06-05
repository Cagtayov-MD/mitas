# -*- coding: utf-8 -*-
"""Sema-zorlamali qwen kunye sinifllandirici v2 (SIKILASTIRILMIS rol).
v1 'yapimci'yi saticilara/baslik/sirkete savurdu. v2: rol ENUM'a bagli + 'kurum' rolu +
'sadece-baslik->COP' + 'rol belirsizse->diger (tahmin etme)'. Yine structured output:
dongu/truncate imkansiz. Ozet/kimlik qwen'den DEGIL; etiketlerden DETERMINISTIK."""
import json, urllib.request, sys, time
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

KUNYE = r"E:\MITAS\Database\evoArcadmin_S_NEMA_F_LM4_2025-1186-1-0000-90-1-K_TAP_KURDU_2\ocr\ocr-3197bc81\kunye.txt"
OUT = r"E:\MITAS\_qwen_kunye_labels_v2.json"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3:8b"
CHUNK = 70

lines = [l for l in open(KUNYE, encoding="utf-8").read().splitlines() if l.strip()]

ROLLER = [
    "oyuncu", "yonetmen", "yapimci", "yonetici yapimci", "senaryo", "goruntu yonetmeni",
    "muzik", "kurgu", "sanat", "kostum", "makyaj", "ses", "kurum", "diger",
    "seslendirme sanatcisi", "seslendirme yonetmeni", "ses kayit", "miksaj", "medya yonetimi", "",
]
SCHEMA = {
    "type": "object",
    "properties": {
        "satirlar": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "etiket": {"type": "string", "enum": ["KADRO", "DUBLAJ", "UYARI", "ALTYAZI", "COP"]},
                    "rol": {"type": "string", "enum": ROLLER},
                },
                "required": ["n", "etiket", "rol"],
            },
        }
    },
    "required": ["satirlar"],
}

INSTR = """Asagidaki numarali film-jenerigi (kunye) satirlarini sinifla. Her satir icin {n, etiket, rol}.

etiket:
  KADRO  = kunyede yer alan gercek kisi VEYA kurum (oyuncu/ekip/sirket)
  DUBLAJ = Turkce seslendirme/dublaj ekibi
  UYARI  = disclaimer / resmi beyan / anlatim / tam cumle (kunye DEGIL)
  ALTYAZI= diyalog / sarki sozu / altyazi
  COP    = bozuk OCR, anlamsiz, VEYA sadece-rol-basligi (isim yok)

rol (yalniz KADRO/DUBLAJ icin; digerleri rol=""):
  KADRO : oyuncu, yonetmen, yapimci, yonetici yapimci, senaryo, goruntu yonetmeni,
          muzik, kurgu, sanat, kostum, makyaj, ses, kurum, diger
  DUBLAJ: seslendirme sanatcisi, seslendirme yonetmeni, ses kayit, miksaj, medya yonetimi, diger

KESIN KURALLAR:
1) Satir SADECE rol-basligiysa, isim YOKSA (or. PRODUCED BY, STORY BY, SCREENPLAY BY,
   DIRECTOR OF PHOTOGRAPHY, EXECUTIVE PRODUCERS, MUSIC BY, CAST) -> etiket=COP. Baslik, kunye girdisi DEGIL.
2) Sirket/kurum/hizmet (catering, banka, sigorta, arac kiralama, nakliye, hukuk, trafik, otel,
   film komisyonu, post-produksiyon sirketi) -> etiket=KADRO, rol='kurum'. ASLA yapimci/yonetmen sayma.
3) Kisi adi ama rolu net degilse -> rol='diger'. yapimci/yonetmeni TAHMIN ETME.
4) 'yonetmen'/'yapimci' rolunu YALNIZ acik kanit varsa ver.
5) 'seslendirme yonetmeni' -> DUBLAJ, FILM yonetmeni DEGIL.
6) Disclaimer ('...kabul ediyor', '...olmadigindan...', resmi tesekkur/beyan) -> UYARI.
7) Yeni isim UYDURMA, satiri DEGISTIRME; sadece etiketle.
/no_think

SATIRLAR:
"""


def call(numbered):
    payload = {
        "model": MODEL, "prompt": INSTR + numbered, "stream": False,
        "think": False, "format": SCHEMA,
        "options": {"temperature": 0, "repeat_penalty": 1.3, "num_ctx": 8192, "num_predict": 3584},
    }
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    resp = json.load(urllib.request.urlopen(req, timeout=300))
    return json.loads(resp.get("response", "{}"))


items = []
t0 = time.time()
for c in range(0, len(lines), CHUNK):
    seg = lines[c:c + CHUNK]
    numbered = "\n".join(f"{c+i+1}. {l}" for i, l in enumerate(seg))
    t = time.time()
    try:
        got = call(numbered).get("satirlar", [])
        items.extend(got)
        print(f"  chunk {c+1}-{c+len(seg)}: {len(got)} etiket | {time.time()-t:.0f}s", flush=True)
    except Exception as e:
        print(f"  chunk {c+1}-{c+len(seg)}: HATA {type(e).__name__}: {e}", flush=True)

by_n = {it["n"]: it for it in items if isinstance(it, dict) and "n" in it}
json.dump({"model": MODEL, "items": items}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def show(label, pred, cap=40):
    sel = [(n, by_n[n]) for n in sorted(by_n) if pred(by_n[n])]
    print(f"\n### {label} ({len(sel)})")
    for n, it in sel[:cap]:
        print(f"  {n:>3} [{it.get('rol','')}] {lines[n-1] if 1<=n<=len(lines) else '?'}")


print(f"\n{'='*64}\nTOPLAM {len(by_n)}/{len(lines)} etiket | {time.time()-t0:.0f}s | model={MODEL} -> {OUT}")
print("\n--- ETIKET dagilimi ---", dict(Counter(it.get("etiket") for it in by_n.values())))
print("--- ROL dagilimi ---", dict(Counter(it.get("rol") for it in by_n.values() if it.get("rol"))))
show("UYARI -> ATILIR", lambda it: it["etiket"] == "UYARI")
show("KADRO rol=yonetmen/yapimci (AZ olmali, kanitli)", lambda it: it["etiket"] == "KADRO" and it.get("rol") in ("yonetmen", "yapimci", "yonetici yapimci"))
show("KADRO rol=kurum (sirket/hizmet)", lambda it: it["etiket"] == "KADRO" and it.get("rol") == "kurum")

print(f"\n{'='*64}\nKRITIK KONTROLLER (v1->v2 iyilesme):")
for n in (21, 24, 26):
    print(f"  {n} '{lines[n-1][:34]}' -> {by_n.get(n,{}).get('etiket','YOK')}  (UYARI olmali)")
print(f"  435 'SESLENDIRME YONETMENI' -> {by_n.get(435,{}).get('etiket','YOK')}/{by_n.get(435,{}).get('rol','')}  (DUBLAJ olmali)")
for n, ad in ((226, "BILLIONAIRES CATERING"), (220, "TRAFFIC MANAGEMENT NZ"), (378, "...KIWIBANK")):
    print(f"  {n} '{ad}' -> {by_n.get(n,{}).get('etiket','YOK')}/{by_n.get(n,{}).get('rol','')}  (kurum olmali, yapimci DEGIL)")
for n, ad in ((98, "PRODUCED BY"), (106, "STORY BY"), (86, "EXECUTIVE PRODUCERS")):
    print(f"  {n} '{ad}' -> {by_n.get(n,{}).get('etiket','YOK')}  (COP olmali, baslik)")
print(f"  72 'KARYN RACHTMAN' -> {by_n.get(72,{}).get('etiket','YOK')}/{by_n.get(72,{}).get('rol','')}  (yonetmen OLMAMALI)")
