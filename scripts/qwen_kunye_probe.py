# -*- coding: utf-8 -*-
"""Ham qwen probe: KITAP KURDU kunye.txt'i yerel qwen'e ver, kunye-ici ayiklama
+ rol akli getirip getiremedigine bak. SEMA YOK (ilk gorus); temp 0, /no_think,
repeat_penalty loop-kiran. Sadece ATILACAKLAR + ROL KARISIKLIGI + OZET ister
(437 satiri tek tek echo etmesin diye)."""
import json, urllib.request, sys, time

sys.stdout.reconfigure(encoding="utf-8")

KUNYE = r"E:\MITAS\Database\evoArcadmin_S_NEMA_F_LM4_2025-1186-1-0000-90-1-K_TAP_KURDU_2\ocr\ocr-3197bc81\kunye.txt"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemma-4-31b-it-qat-vision:latest"

lines = [l for l in open(KUNYE, encoding="utf-8").read().splitlines() if l.strip()]
numbered = "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))

SYSTEM = """Sen film jenerigi (kunye) ayiklama uzmanisin. Asagidaki satirlar bir filmin
acilis+kapanis jeneriginden OCR ile okundu. Bu YABANCI bir film (orijinali Ingilizce) ve
TRT icin Turkce dublajli; icinde (a) Ingilizce yapim/dagitim jenerigi, (b) Turkce dublaj
ekibi, (c) bir UYARI/DISCLAIMER cumlesi, (d) OCR'in yanlis/bozuk okudugu cop satirlar
KARISIK halde.

GOREV: Her satiri zihninde su kategorilere ayir. ASLA yeni isim uydurma, satiri degistirme:
[KADRO]  = gercek kisi/kurum + rolu (oyuncu, yonetmen, yapimci, senaryo, goruntu yon., muzik, kurgu...)
[DUBLAJ] = Turkce seslendirme/dublaj ekibi. DIKKAT: 'seslendirme yonetmeni' filmin yonetmeni DEGILDIR.
[UYARI]  = disclaimer/anlatim/tam cumle, kunye DEGIL (or. 'filmin yapimcilari ... kabul ediyor').
[ALTYAZI]= diyalog/altyazi cumlesi.
[COP]    = OCR hatasi, anlamsiz/bozuk satir.

CIKTIDA tum satirlari tek tek yazma. SADECE sunlari ver:
1) ATILACAKLAR  : [UYARI]+[ALTYAZI]+[COP] satirlari -> "satir_no: kisa sebep" seklinde.
2) ROL KARISIKLIGI: yanlis role atanma riski olanlar (ozellikle dublaj yonetmeni/ekibi
   film ekibiyle karismasin) -> "satir_no: dogru rol".
3) OZET:
   - FILMIN YONETMENI:
   - BASROL OYUNCULAR:
   - YAPIMCI(LAR):
   - TURKCE DUBLAJ EKIBI:

/no_think"""

prompt = SYSTEM + "\n\nSATIRLAR:\n" + numbered

payload = {
    "model": MODEL,
    "prompt": prompt,
    "stream": False,
    "think": False,                # qwen3.x thinking modelini KAPAT (asil cevabi versin, dusunmeye butce harcamasin)
    "options": {"temperature": 0, "repeat_penalty": 1.3, "num_ctx": 12288, "num_predict": 4096},
}
req = urllib.request.Request(
    "http://localhost:11434/api/generate",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
print(f"model={MODEL} | {len(lines)} satir | think=False | istek gonderiliyor...\n", flush=True)
t = time.time()
resp = json.load(urllib.request.urlopen(req, timeout=590))
out = resp.get("response", "")
think = resp.get("thinking", "")
print(out)
if not out.strip() and think.strip():
    print("[!] response BOS, thinking alani dolu -> ilk 1500 char:\n", think[:1500])
print(f"\n{'='*60}\n[sure {time.time()-t:.1f}s | eval {resp.get('eval_count','?')} tok | "
      f"done={resp.get('done_reason','?')} | response_len={len(out)} | thinking_len={len(think)}]")
