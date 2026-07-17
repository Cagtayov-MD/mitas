"""vLLM VIDEO girişi testi — Qwen2.5-VL-7B'ye gerçek video izletir (transformers'sız, ollama'sız).
Kullanım: python vllm_video_test.py <video> <model_snapshot> [kare_sayisi] [kuyruk_sn]
kuyruk_sn verilirse videonun SON kuyruk_sn saniyesinden örnekler (jenerik testi)."""
import sys, time
import numpy as np
import cv2


def kareleri_al(yol: str, n: int = 12, kuyruk_sn: float | None = None, genislik: int = 448) -> np.ndarray:
    cap = cv2.VideoCapture(yol)
    toplam = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    bas = 0
    son = toplam - 1
    if kuyruk_sn:
        bas = max(0, toplam - int(kuyruk_sn * fps))
    idxs = np.linspace(bas, son, n).astype(int)
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
    assert kareler, "kare okunamadi"
    return np.stack(kareler)


def main():
    from vllm import LLM, SamplingParams
    video_yol, model = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    kuyruk = float(sys.argv[4]) if len(sys.argv) > 4 else None
    genislik = int(sys.argv[5]) if len(sys.argv) > 5 else 448
    mod = sys.argv[6] if len(sys.argv) > 6 else "genel"
    video = kareleri_al(video_yol, n, kuyruk, genislik)
    print(f"VIDEO HAZIR: {video.shape} (kare,h,w,3) kuyruk={kuyruk}")

    t = time.time()
    llm = LLM(model=model, max_model_len=16384, gpu_memory_utilization=0.85,
              enforce_eager=True, dtype="float16", limit_mm_per_prompt={"video": 1})
    print("MODEL LOADED %.1fs" % (time.time() - t))

    if mod == "jenerik":
        soru = ("Bu bir film kapanış jeneriği (end credits). Ekranda görünen TÜM isimleri ve "
                "unvanları/rolleri AYNEN, satır satır listele. Uydurma; okuyamadığını atla.")
    elif mod == "jenerik_kare":
        soru = ("Bu bir film kapanış jeneriği (end credits) videosu. Her kareyi AYRI AYRI oku: "
                "'--- Kare N ---' başlığı altında o karede görünen metni AYNEN satır satır yaz. "
                "Kareleri BİRLEŞTİRME, sıralarını değiştirme. Uydurma; okuyamadığını atla.")
    else:
        soru = "Bu videoda ne görüyorsun? Türkçe anlat. Ekranda yazı/isim varsa aynen oku."
    prompt = ("<|im_start|>system\nSen yardımcı bir görsel asistansın.<|im_end|>\n"
              "<|im_start|>user\n<|vision_start|><|video_pad|><|vision_end|>"
              f"{soru}<|im_end|>\n<|im_start|>assistant\n")
    t = time.time()
    out = llm.generate([{"prompt": prompt, "multi_modal_data": {"video": video}}],
                       SamplingParams(temperature=0, max_tokens=1500))
    print("URETIM %.1fs" % (time.time() - t))
    print("=" * 60)
    print(out[0].outputs[0].text.strip())


if __name__ == "__main__":
    main()
