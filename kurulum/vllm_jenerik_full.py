"""TAM jenerik VL okuma + kapasite testleri (vLLM, Qwen2.5-VL).
1) SIKLIK testi: aynı 60s pencere, 12/30/60 kare (0.2/0.5/1.0 fps) — token/süre/kalite
2) SÜRE testi: TÜM jenerik tek atışta (400s, 0.5fps=200 kare) — sığıyor mu?
3) İŞLEME: 4×~100s kayan pencere @1fps, kare-bölümlü okuma → rapor dosyası
"""
import sys, time
import numpy as np
import cv2

VIDEO = sys.argv[1]
MODEL = sys.argv[2]
KUYRUK = float(sys.argv[3]) if len(sys.argv) > 3 else 400.0
RAPOR = sys.argv[4] if len(sys.argv) > 4 else "/opt/mitas/outputs/JENERIK_VL_RAPOR.md"


def pencere_kareleri(bas_sn: float, sure_sn: float, n: int, genislik: int = 768) -> np.ndarray:
    cap = cv2.VideoCapture(VIDEO)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    toplam = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    i0 = min(toplam - 2, int(bas_sn * fps))
    i1 = min(toplam - 1, int((bas_sn + sure_sn) * fps))
    idxs = np.linspace(i0, i1, n).astype(int)
    kareler = []
    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, fr = cap.read()
        if not ok:
            continue
        fr = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)
        h, w = fr.shape[:2]
        s = float(genislik) / max(h, w)
        fr = cv2.resize(fr, (max(2, int(w * s) // 2 * 2), max(2, int(h * s) // 2 * 2)))
        kareler.append(fr)
    cap.release()
    return np.stack(kareler)


def oku(llm, sp, video: np.ndarray, kare_modu: bool = True):
    from vllm import SamplingParams
    if kare_modu:
        soru = ("Bu bir film kapanış jeneriği (end credits) videosu. Her kareyi AYRI AYRI oku: "
                "'--- Kare N ---' başlığı altında o karede görünen metni AYNEN satır satır yaz. "
                "Kareleri BİRLEŞTİRME. Uydurma; okuyamadığını atla.")
    else:
        soru = ("Bu bir film kapanış jeneriği. Görünen TÜM isim/unvanları sırayla, aynen listele. Uydurma.")
    prompt = ("<|im_start|>system\nSen hassas bir OCR asistanısın.<|im_end|>\n"
              "<|im_start|>user\n<|vision_start|><|video_pad|><|vision_end|>"
              f"{soru}<|im_end|>\n<|im_start|>assistant\n")
    t = time.time()
    out = llm.generate([{"prompt": prompt, "multi_modal_data": {"video": video}}], sp)
    sure = time.time() - t
    o = out[0]
    return o.outputs[0].text.strip(), len(o.prompt_token_ids), len(o.outputs[0].token_ids), sure


def main():
    from vllm import LLM, SamplingParams
    cap = cv2.VideoCapture(VIDEO)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    toplam_sn = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / fps
    cap.release()
    jen_bas = toplam_sn - KUYRUK
    print(f"VIDEO {toplam_sn:.0f}s, jenerik penceresi: son {KUYRUK:.0f}s (t={jen_bas:.0f}s'den itibaren)")

    t = time.time()
    llm = LLM(model=MODEL, max_model_len=32768, gpu_memory_utilization=0.85,
              enforce_eager=True, dtype="float16", limit_mm_per_prompt={"video": 1})
    print("MODEL LOADED %.1fs (max_model_len=32768)" % (time.time() - t))
    sp = SamplingParams(temperature=0, max_tokens=6000)

    R = ["# Jenerik VL Okuma Raporu — " + VIDEO, ""]

    # ---- 1) SIKLIK testi ----
    print("\n########## SIKLIK TESTI (ayni 60s pencere) ##########")
    R.append("## 1. Sıklık testi (aynı 60s pencere, 768px)")
    R.append("| kare | fps | prompt-token | üretim-token | süre |")
    R.append("|---|---|---|---|---|")
    for n in (12, 30, 60):
        v = pencere_kareleri(jen_bas + 120, 60, n)
        try:
            _, pt, ot, su = oku(llm, sp, v)
            print(f"  {n} kare (fps={n/60:.2f}): prompt={pt}tok, cikti={ot}tok, {su:.1f}s")
            R.append(f"| {n} | {n/60:.2f} | {pt} | {ot} | {su:.1f}s |")
        except Exception as e:  # noqa: BLE001
            print(f"  {n} kare: HATA {type(e).__name__}: {str(e)[:120]}")
            R.append(f"| {n} | {n/60:.2f} | HATA: {type(e).__name__} | | |")

    # ---- 2) SÜRE testi: tüm jenerik TEK atışta ----
    print("\n########## SURE TESTI (tek atis, tum jenerik) ##########")
    R.append("\n## 2. Süre testi — tüm jenerik TEK video girdisi")
    for n, etiket in ((int(KUYRUK * 0.5), "0.5fps"), (int(KUYRUK), "1.0fps")):
        v = pencere_kareleri(jen_bas, KUYRUK, n)
        try:
            _, pt, ot, su = oku(llm, sp, v, kare_modu=False)
            print(f"  {KUYRUK:.0f}s @ {etiket} = {n} kare: prompt={pt}tok, {su:.1f}s → SIGDI")
            R.append(f"- **{KUYRUK:.0f}s @ {etiket} ({n} kare): SIĞDI** — prompt {pt} token, üretim {su:.1f}s")
        except Exception as e:  # noqa: BLE001
            print(f"  {KUYRUK:.0f}s @ {etiket} = {n} kare: HATA {type(e).__name__}: {str(e)[:150]}")
            R.append(f"- {KUYRUK:.0f}s @ {etiket} ({n} kare): **SIĞMADI/HATA** — {type(e).__name__}: {str(e)[:150]}")

    # ---- 3) İŞLEME: kayan pencere, kare-bölümlü ----
    print("\n########## TAM ISLEME (kayan pencere) ##########")
    R.append("\n## 3. Tam jenerik okuma (kayan pencere, kare-bölümlü, 1fps)")
    PENCERE, ADIM = 100.0, 95.0
    b = jen_bas
    pi = 0
    while b < toplam_sn - 5:
        pi += 1
        sure_p = min(PENCERE, toplam_sn - b)
        n = max(6, int(sure_p))
        v = pencere_kareleri(b, sure_p, n)
        try:
            metin, pt, ot, su = oku(llm, sp, v)
            print(f"  pencere {pi}: t={b:.0f}-{b+sure_p:.0f}s, {n} kare, {su:.1f}s, cikti={ot}tok")
            R.append(f"\n### Pencere {pi} — t={b:.0f}s→{b+sure_p:.0f}s ({n} kare, {su:.1f}s)\n")
            R.append(metin)
        except Exception as e:  # noqa: BLE001
            print(f"  pencere {pi}: HATA {type(e).__name__}: {str(e)[:120]}")
            R.append(f"\n### Pencere {pi} — HATA: {type(e).__name__}")
        b += ADIM

    with open(RAPOR, "w", encoding="utf-8") as f:
        f.write("\n".join(R) + "\n")
    print(f"\nRAPOR YAZILDI: {RAPOR}")


if __name__ == "__main__":
    main()
