from __future__ import annotations

from core.pipelines.asr.normalize import PROJECT_ROOT
from tools.asr_ab.common import VariantConfig, build_merged_chunks, main_for, no_prompt_tr_kwargs


BASE_TURBO_CT2_MODEL = (
    PROJECT_ROOT
    / "models"
    / "asr"
    / "faster-whisper"
    / "large-v3-turbo"
)


CONFIG = VariantConfig(
    name="v11_base_turbo_vad_merged_no_prompt",
    description="OpenAI large-v3-turbo CTranslate2 conversion with the exact v7 VAD-merged no-prompt strategy.",
    output_name="out_v11",
    chunk_builder=build_merged_chunks,
    transcribe_kwargs=no_prompt_tr_kwargs(condition_on_previous_text=True),
    model_path=BASE_TURBO_CT2_MODEL,
    exit_after_write=True,
)


if __name__ == "__main__":
    main_for(CONFIG)
