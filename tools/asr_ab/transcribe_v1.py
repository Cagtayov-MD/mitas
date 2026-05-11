from __future__ import annotations

from tools.asr_ab.common import VariantConfig, build_current_vad_chunks, main_for, standard_tr_kwargs


CONFIG = VariantConfig(
    name="v1_minimal_patch_filter_language",
    description="Same per-VAD chunking as baseline, but force Turkish with code-switch prompt and shared post-filter.",
    output_name="out_v1",
    chunk_builder=build_current_vad_chunks,
    transcribe_kwargs=standard_tr_kwargs(condition_on_previous_text=False),
)


if __name__ == "__main__":
    main_for(CONFIG)
