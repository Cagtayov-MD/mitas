import sys, time


def main():
    from vllm import LLM, SamplingParams
    snap = sys.argv[1]
    t = time.time()
    llm = LLM(model=snap, gpu_memory_utilization=0.80, max_model_len=2048,
              enforce_eager=True, dtype="float16")
    print("MODEL LOADED %.1fs" % (time.time() - t))
    out = llm.generate(["Turkiye'nin baskenti neresi? Tek kelime cevap:"],
                       SamplingParams(temperature=0, max_tokens=12))
    print("VLLM URETTI:", repr(out[0].outputs[0].text.strip()[:80]))


if __name__ == "__main__":
    main()
