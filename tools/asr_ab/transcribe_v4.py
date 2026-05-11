from __future__ import annotations

from tools.asr_ab.common import VariantConfig, build_single_pass_chunk, main_for, standard_tr_kwargs


CONFIG = VariantConfig(
    name="v4_full_audio_single_pass",
    description="Single full-audio transcribe call with faster-whisper built-in VAD.",
    output_name="out_v4",
    chunk_builder=build_single_pass_chunk,
    transcribe_kwargs=standard_tr_kwargs(condition_on_previous_text=True, vad_filter=True),
    use_vad_for_transcribe=False,
    run_vad_metadata=False,
    single_pass=True,
)


if __name__ == "__main__":
    main_for(CONFIG)
