from __future__ import annotations

from tools.asr_ab.common import VariantConfig, baseline_kwargs, build_current_vad_chunks, main_for


CONFIG = VariantConfig(
    name="v0_baseline_current",
    description="Current behavior: each VAD segment as a chunk, multilingual detection, no prompt, no quality-aware decode params.",
    output_name="out_v0",
    chunk_builder=build_current_vad_chunks,
    transcribe_kwargs=baseline_kwargs(),
)


if __name__ == "__main__":
    main_for(CONFIG)
