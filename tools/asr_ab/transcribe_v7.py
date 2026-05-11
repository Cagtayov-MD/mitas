from __future__ import annotations

from tools.asr_ab.common import VariantConfig, build_merged_chunks, main_for, no_prompt_tr_kwargs


CONFIG = VariantConfig(
    name="v7_vad_merged_no_prompt",
    description="VAD-guided merged chunks like v2, but no initial_prompt to test prompt-leak removal.",
    output_name="out_v7",
    chunk_builder=build_merged_chunks,
    transcribe_kwargs=no_prompt_tr_kwargs(condition_on_previous_text=True),
    exit_after_write=True,
)


if __name__ == "__main__":
    main_for(CONFIG)
