from __future__ import annotations

from core.pipelines.asr.normalize import PROJECT_ROOT
from tools.asr_ab.common import VariantConfig, build_merged_chunks, main_for, no_prompt_tr_kwargs


SELIMC_CT2_MODEL = (
    PROJECT_ROOT
    / "models"
    / "asr"
    / "faster-whisper"
    / "selimc-whisper-large-v3-turbo-turkish-float16"
)


CONFIG = VariantConfig(
    name="v10_selimc_turkish_turbo_ct2_vad_merged",
    description="selimc/whisper-large-v3-turbo-turkish converted to CTranslate2 float16, using the v7 VAD-merged no-prompt strategy.",
    output_name="out_v10",
    chunk_builder=build_merged_chunks,
    transcribe_kwargs=no_prompt_tr_kwargs(condition_on_previous_text=True),
    model_path=SELIMC_CT2_MODEL,
    exit_after_write=True,
)


if __name__ == "__main__":
    main_for(CONFIG)
