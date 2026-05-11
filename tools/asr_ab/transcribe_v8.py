from __future__ import annotations

from tools.asr_ab.common import VariantConfig, build_single_pass_chunk, main_for, no_prompt_tr_kwargs


CONFIG = VariantConfig(
    name="v8_full_audio_no_prompt",
    description="Single full-audio transcribe call with built-in VAD like v4, but no initial_prompt to test prompt-leak removal.",
    output_name="out_v8",
    chunk_builder=build_single_pass_chunk,
    transcribe_kwargs=no_prompt_tr_kwargs(condition_on_previous_text=True, vad_filter=True),
    use_vad_for_transcribe=False,
    run_vad_metadata=False,
    single_pass=True,
)


if __name__ == "__main__":
    main_for(CONFIG)
