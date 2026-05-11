from __future__ import annotations

from tools.asr_ab.common import VariantConfig, build_fixed_windows, main_for, multilingual_code_switch_kwargs


CONFIG = VariantConfig(
    name="v5_fixed_28s_multilingual_code_switch",
    description="Fixed 28s windows like v3, but allow multilingual decoding to test real English code-switch preservation.",
    output_name="out_v5",
    chunk_builder=build_fixed_windows,
    transcribe_kwargs=multilingual_code_switch_kwargs(condition_on_previous_text=True),
    use_vad_for_transcribe=False,
    skip_initial_overlap_seconds=2.0,
)


if __name__ == "__main__":
    main_for(CONFIG)
