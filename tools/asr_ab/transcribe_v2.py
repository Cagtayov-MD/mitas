from __future__ import annotations

from tools.asr_ab.common import VariantConfig, build_merged_chunks, main_for, standard_tr_kwargs


CONFIG = VariantConfig(
    name="v2_vad_guided_merged_chunks",
    description="Merge nearby VAD speech into 12-30s chunks with prompt and previous-text conditioning.",
    output_name="out_v2",
    chunk_builder=build_merged_chunks,
    transcribe_kwargs=standard_tr_kwargs(condition_on_previous_text=True),
)


if __name__ == "__main__":
    main_for(CONFIG)
