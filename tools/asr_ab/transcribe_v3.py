from __future__ import annotations

from tools.asr_ab.common import VariantConfig, build_fixed_windows, main_for, standard_tr_kwargs


CONFIG = VariantConfig(
    name="v3_fixed_28s_windows",
    description="Ignore VAD for transcription and use fixed 28s windows with 2s overlap, Turkish prompt, and overlap dedupe.",
    output_name="out_v3",
    chunk_builder=build_fixed_windows,
    transcribe_kwargs=standard_tr_kwargs(condition_on_previous_text=True),
    use_vad_for_transcribe=False,
    skip_initial_overlap_seconds=2.0,
)


if __name__ == "__main__":
    main_for(CONFIG)
