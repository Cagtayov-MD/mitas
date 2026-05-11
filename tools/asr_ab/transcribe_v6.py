from __future__ import annotations

from tools.asr_ab.common import VariantConfig, build_merged_chunks, main_for, multilingual_code_switch_kwargs


CONFIG = VariantConfig(
    name="v6_vad_merged_multilingual_code_switch",
    description="VAD-guided merged chunks like v2, but allow multilingual decoding for English titles and code-switch phrases.",
    output_name="out_v6",
    chunk_builder=build_merged_chunks,
    transcribe_kwargs=multilingual_code_switch_kwargs(condition_on_previous_text=True),
)


if __name__ == "__main__":
    main_for(CONFIG)
