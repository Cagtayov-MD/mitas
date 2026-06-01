"""Content profile registry for the ASR pipeline.

The pipeline distinguishes two profile concepts:

- **Model profile** (`ProfileName` from `models.py`): controls the decoder
  selection — `fast`, `quality`, `fast_with_fallback`.
- **Content profile** (this module): controls the high-level behavior matrix
  per content type (Karar 15). One content profile picks a model profile, a
  diarization intent, denoise hint, beam size, and an optional initial prompt.

A pipeline call resolves a content profile first, then derives the model
profile and the diarization intent from it (with optional explicit overrides).
This separation is what lets the same `run_asr_pipeline()` handle a news
bulletin and a feature film without growing N flag parameters per call site.

Reference: docs/MITAS_ASR_Pipeline_v0_1_Implementasyon_Plani_v2.md §2 and
Karar 15 (`mutfak/06_KARARLAR_GUNLUGU.md`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.pipelines.asr.models import ProfileName


ContentProfileName = Literal[
    "bulten_haber",
    "studio_panel",
    "muzik_programi",
    "film",
    "belgesel",
    "spor",
]


@dataclass(frozen=True)
class ContentProfile:
    """High-level pipeline behavior for one content type.

    Fields:
      - `name`: stable string identifier used in API payloads and summaries.
      - `model_profile`: which decoder strategy to use (`fast_with_fallback`,
        `quality`, etc.).
      - `diarize`: whether pyannote diarization should run by default. The
        caller can still override with `diarize_override` on the pipeline.
      - `denoise`: hint for the optional DeepFilterNet denoise sleeve. v0.1
        does not invoke denoise from the main pipeline; this field is metadata
        for downstream orchestration / future patches.
      - `beam_size`: faster-whisper `beam_size`. Passed to `transcribe()` via
        `TranscribeParams`; overrides the model-config default per content type.
      - `initial_prompt`: faster-whisper `initial_prompt`. Passed to
        `transcribe()` via `TranscribeParams`.
      - `notes`: short human-readable rationale.
    """

    name: ContentProfileName
    model_profile: ProfileName
    diarize: bool
    denoise: bool
    beam_size: int
    initial_prompt: str | None
    notes: str


CONTENT_PROFILES: dict[ContentProfileName, ContentProfile] = {
    "bulten_haber": ContentProfile(
        name="bulten_haber",
        model_profile="fast_with_fallback",
        diarize=True,
        denoise=False,
        beam_size=5,
        initial_prompt=None,
        notes="Spiker + muhabir + roportaj; net studyo + bazen saha sesi.",
    ),
    "studio_panel": ContentProfile(
        name="studio_panel",
        model_profile="fast_with_fallback",
        diarize=True,
        denoise=True,
        beam_size=5,
        initial_prompt=None,
        notes="Tartisma programi, 3-5 konusmaci, hizli turn-taking, alkis olabilir.",
    ),
    "muzik_programi": ContentProfile(
        name="muzik_programi",
        model_profile="fast_with_fallback",
        diarize=True,
        denoise=False,
        beam_size=5,
        initial_prompt="Turkce muzik programi",
        notes="Sunucu + konuk + sarki kisimlari; muzik kisimlari v0.2 audio activity layer ile ayrilir.",
    ),
    "film": ContentProfile(
        name="film",
        model_profile="fast_with_fallback",
        diarize=False,
        denoise=True,
        beam_size=5,
        initial_prompt=None,
        notes="Diyalog + muzik + efekt; diarization kapali (cast kimligi yuz tarafinda cozulur).",
    ),
    "belgesel": ContentProfile(
        name="belgesel",
        model_profile="quality",
        diarize=False,
        denoise=True,
        beam_size=8,
        initial_prompt=None,
        notes="Anlatici baskin + nadir roportaj; kalite onceligi nedeniyle large-v3 default.",
    ),
    "spor": ContentProfile(
        name="spor",
        model_profile="fast_with_fallback",
        diarize=False,
        denoise=True,
        beam_size=5,
        initial_prompt="Türkçe spor müsabakası anlatımı",
        notes="Canli spor yayini / mac anlatimi; spiker + saha sesi, tempolu konusma. Ozet spor profili soru setini kullanir.",
    ),
}


def get_content_profile(name: str) -> ContentProfile:
    """Return the `ContentProfile` for a name; raises if unknown.

    Profile names are strict (no fallback). Callers that want a default should
    pick one explicitly in their own layer.
    """
    if name not in CONTENT_PROFILES:
        known = ", ".join(sorted(CONTENT_PROFILES))
        raise ValueError(f"Unknown content profile {name!r}; known: {known}")
    return CONTENT_PROFILES[name]


def list_content_profiles() -> list[ContentProfileName]:
    """Return all registered content profile names in stable order."""
    return sorted(CONTENT_PROFILES.keys())
