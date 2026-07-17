from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import socket
import time
from typing import Any
import urllib.error
import urllib.request
import uuid

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from .models import (
    BoundaryKind,
    Continuity,
    FrameRef,
    Label,
    Observation,
    WindowEvidence,
    WindowVerdict,
)


TEXT_PLANES = (
    "SCREEN_OVERLAY",
    "SCENE_SURFACE",
    "SUBTITLE_BAND",
    "FULLSCREEN_CARD",
    "NONE",
    "UNKNOWN",
)

CUES = (
    "CAST_CREW_LIST",
    "ROLE_NAME_LAYOUT",
    "PRODUCTION_LEGAL",
    "CREDIT_SCROLL",
    "ENDING_CARD",
    "SUBTITLE",
    "STORY_CARD",
    "SCENE_SURFACE",
    "UI_DOCUMENT",
    "NO_TEXT",
    "AMBIGUOUS",
)


def _is_adversarial_stage(stage: str) -> bool:
    return stage == "verify_b" or stage.endswith("_b")


def _is_chronology_stage(stage: str) -> bool:
    return "chronology" in stage


def _is_micro_stage(stage: str) -> bool:
    return "micro" in stage


def _is_semantic_sentinel_stage(stage: str) -> bool:
    return "semantic_sentinel" in stage


class VlmCallError(RuntimeError):
    def __init__(self, message: str, *, record: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.record = record or {}


@dataclass
class VlmBatchResult:
    observations: list[Observation]
    call_record: dict[str, Any]


@dataclass
class VlmWindowResult:
    evidence: WindowEvidence
    call_record: dict[str, Any]


@dataclass
class VlmCandidateAuditResult:
    """One dedicated semantic decision about the candidate frame itself."""

    decision: str
    attribution_layout: bool
    inside_story_screen: bool
    call_record: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "attribution_layout": self.attribution_layout,
            "inside_story_screen": self.inside_story_screen,
            "call_id": self.call_record.get("call_id"),
            "stage": self.call_record.get("stage"),
            "candidate_pos": self.call_record.get("candidate_pos"),
            "frame_positions": self.call_record.get("frame_positions"),
            "input_sha256": self.call_record.get("input_sha256"),
            "prompt_sha256": self.call_record.get("prompt_sha256"),
            "prompt_protocol": self.call_record.get("prompt_protocol"),
            "prompt_variant": self.call_record.get("prompt_variant"),
        }


_CANDIDATE_AUDIT_DECISIONS = (
    "ATTRIBUTION_CREDIT",
    "END_CARD",
    "TITLE_OR_STORY",
    "DIEGETIC_SCREEN",
    "OTHER_TEXT",
    "NO_TEXT",
    "UNCERTAIN",
)


_CODE_TO_LABEL = {
    "F": Label.FOOTAGE,
    "D": Label.DIEGETIC_TEXT,
    "S": Label.STORY_TEXT,
    "C": Label.CREDIT,
    "E": Label.END_CARD,
    "B": Label.BLANK,
    "U": Label.UNCERTAIN,
}


def _encode_mosaic(
    refs: list[FrameRef],
    *,
    tile_width: int,
    columns: int,
    quality: int,
) -> tuple[str, dict[str, int]]:
    """Encode one chronological contact sheet instead of N VLM images."""
    tile_height = max(72, round(tile_width * 9 / 16))
    header_height = 22
    cell_height = tile_height + header_height
    used_columns = min(columns, len(refs))
    rows = math.ceil(len(refs) / used_columns)
    sheet = Image.new(
        "RGB",
        (used_columns * tile_width, rows * cell_height),
        (18, 18, 18),
    )
    draw = ImageDraw.Draw(sheet)
    for index, ref in enumerate(refs):
        x = (index % used_columns) * tile_width
        y = (index // used_columns) * cell_height
        draw.rectangle(
            (x, y, x + tile_width - 1, y + header_height - 1),
            fill=(42, 42, 42),
            outline=(110, 110, 110),
            width=1,
        )
        draw.text((x + 6, y + 5), f"CELL {index:02d}", fill=(235, 235, 235))
        with Image.open(ref.path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image = ImageOps.contain(
                image,
                (max(1, tile_width - 4), max(1, tile_height - 4)),
                method=Image.Resampling.LANCZOS,
            )
        paste_x = x + (tile_width - image.width) // 2
        paste_y = y + header_height + (tile_height - image.height) // 2
        sheet.paste(image, (paste_x, paste_y))
        draw.rectangle(
            (x, y + header_height, x + tile_width - 1, y + cell_height - 1),
            outline=(110, 110, 110),
            width=2,
        )
    buffer = BytesIO()
    sheet.save(buffer, format="JPEG", quality=quality, optimize=True)
    raw = buffer.getvalue()
    return base64.b64encode(raw).decode("ascii"), {
        "columns": used_columns,
        "rows": rows,
        "tile_width": tile_width,
        "tile_height": tile_height,
        "header_height": header_height,
        "cell_height": cell_height,
        "mosaic_width": sheet.width,
        "mosaic_height": sheet.height,
        "jpeg_bytes": len(raw),
    }


def _encode_candidate_detail_mosaic(
    ref: FrameRef,
    *,
    tile_width: int,
    quality: int,
) -> tuple[str, dict[str, Any]]:
    """Show one candidate with whole-frame, center and lower-edge detail."""
    tile_height = max(72, round(tile_width * 9 / 16))
    header_height = 24
    labels = (
        "CANDIDATE FULL",
        "CANDIDATE FULL ENHANCED",
        "CANDIDATE CENTER ZOOM",
        "CANDIDATE LOWER ZOOM",
        "CANDIDATE BOTTOM EDGE",
    )
    with Image.open(ref.path) as source:
        full = ImageOps.exif_transpose(source).convert("RGB")
    enhanced = ImageOps.autocontrast(full, cutoff=0.5)
    enhanced = ImageEnhance.Color(enhanced).enhance(2.0)
    enhanced = ImageEnhance.Contrast(enhanced).enhance(1.35)
    center_x_margin = round(full.width * 0.20)
    center_y_margin = round(full.height * 0.20)
    center = full.crop((
        center_x_margin,
        center_y_margin,
        full.width - center_x_margin,
        full.height - center_y_margin,
    ))
    crop_top = max(0, min(full.height - 1, round(full.height * 0.72)))
    lower = full.crop((0, crop_top, full.width, full.height))
    bottom_crop_top = max(
        crop_top,
        min(full.height - 1, round(full.height * 0.90)),
    )
    bottom_edge = full.crop((0, bottom_crop_top, full.width, full.height))
    bottom_edge = ImageOps.autocontrast(bottom_edge, cutoff=1)
    views = [full, enhanced, center, lower, bottom_edge]
    columns = 3
    rows = math.ceil(len(views) / columns)
    sheet = Image.new(
        "RGB",
        (columns * tile_width, rows * (tile_height + header_height)),
        (18, 18, 18),
    )
    draw = ImageDraw.Draw(sheet)
    for index, (label, view) in enumerate(zip(labels, views)):
        x = (index % columns) * tile_width
        y = (index // columns) * (tile_height + header_height)
        draw.rectangle(
            (x, y, x + tile_width - 1, y + header_height - 1),
            fill=(42, 42, 42),
            outline=(110, 110, 110),
            width=1,
        )
        draw.text((x + 6, y + 6), label, fill=(235, 235, 235))
        if index in {0, 1}:
            rendered = ImageOps.contain(
                view,
                (max(1, tile_width - 4), max(1, tile_height - 4)),
                method=Image.Resampling.LANCZOS,
            )
        else:
            # Deliberately enlarge the entire lower strip without horizontal
            # cropping. The aspect stretch is diagnostic: it makes the first
            # 1-3 pixel-high entering glyphs visible while retaining both
            # left/right credit columns.
            rendered = view.resize(
                (max(1, tile_width - 4), max(1, tile_height - 4)),
                resample=Image.Resampling.LANCZOS,
            )
        paste_x = x + (tile_width - rendered.width) // 2
        paste_y = y + header_height + (tile_height - rendered.height) // 2
        sheet.paste(rendered, (paste_x, paste_y))
        draw.rectangle(
            (
                x,
                y + header_height,
                x + tile_width - 1,
                y + header_height + tile_height - 1,
            ),
            outline=(110, 110, 110),
            width=2,
        )
    buffer = BytesIO()
    sheet.save(buffer, format="JPEG", quality=quality, optimize=True)
    raw = buffer.getvalue()
    return base64.b64encode(raw).decode("ascii"), {
        "columns": columns,
        "rows": rows,
        "tile_width": tile_width,
        "tile_height": tile_height,
        "header_height": header_height,
        "mosaic_width": sheet.width,
        "mosaic_height": sheet.height,
        "jpeg_bytes": len(raw),
        "candidate_detail_views": list(labels),
        "center_crop_margins_ratio": [0.2, 0.2],
        "full_enhancement": {
            "autocontrast_cutoff": 0.5,
            "color": 2.0,
            "contrast": 1.35,
        },
        "lower_crop_top_ratio": round(crop_top / max(1, full.height), 4),
        "bottom_crop_top_ratio": round(
            bottom_crop_top / max(1, full.height), 4
        ),
    }


def _encode_candidate_raw_frame(
    ref: FrameRef,
    *,
    max_width: int,
    quality: int,
) -> tuple[str, dict[str, Any]]:
    """Transport a candidate without CELL chrome, borders or derived panes."""
    with Image.open(ref.path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    original_size = [image.width, image.height]
    if image.width > max_width:
        height = max(1, round(image.height * max_width / image.width))
        image = image.resize(
            (max_width, height),
            resample=Image.Resampling.LANCZOS,
        )
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    raw = buffer.getvalue()
    return base64.b64encode(raw).decode("ascii"), {
        "columns": 1,
        "rows": 1,
        "tile_width": image.width,
        "tile_height": image.height,
        "header_height": 0,
        "mosaic_width": image.width,
        "mosaic_height": image.height,
        "jpeg_bytes": len(raw),
        "raw_candidate_frame": True,
        "original_size": original_size,
    }


def _schema(
    expected_count: int,
    boundary_search_cells: tuple[int, int] | None = None,
) -> dict[str, Any]:
    first_maximum = (
        boundary_search_cells[1]
        if boundary_search_cells is not None
        else expected_count - 1
    )
    first_schema: dict[str, Any] = {
        "type": "integer",
        "minimum": -1,
        "maximum": first_maximum,
    }
    if boundary_search_cells is not None:
        first_candidate, last_candidate = boundary_search_cells
        # Structured decoding must not offer arbitrary left-context cells as a
        # TRANSITION onset.  -1 remains available for PRE/AMBIGUOUS and 0 for
        # ACTIVE_FROM_LEFT; the strict parser still enforces state consistency.
        first_schema["enum"] = [
            -1,
            0,
            *range(first_candidate, last_candidate + 1),
        ]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["state", "first", "last_support", "kind", "continuity", "reject"],
        "properties": {
            "state": {
                "type": "string",
                "enum": ["PRE_ONLY", "TRANSITION", "ACTIVE_FROM_LEFT", "AMBIGUOUS"],
            },
            "first": first_schema,
            "last_support": {"type": "integer", "minimum": -1, "maximum": expected_count - 1},
            "kind": {
                "type": "string",
                "enum": ["NONE", "CREDIT_SEQUENCE", "END_CARD_THEN_CREDITS", "TERMINAL_END_CARD"],
            },
            "continuity": {
                "type": "string",
                "enum": ["NONE", "CONFIRMED", "UNVERIFIABLE", "BROKEN"],
            },
            "reject": {
                "type": "string",
                "enum": ["NONE", "DIEGETIC", "STORY_TEXT", "NO_VISIBLE_ATTRIBUTION", "MIXED"],
            },
        },
    }


def _candidate_audit_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "decision",
            "attribution_layout",
            "inside_story_screen",
        ],
        "properties": {
            "decision": {
                "type": "string",
                "enum": list(_CANDIDATE_AUDIT_DECISIONS),
            },
            "attribution_layout": {"type": "boolean"},
            "inside_story_screen": {"type": "boolean"},
        },
    }


def _candidate_audit_prompt(*, variant: str, candidate_cell: int) -> str:
    if variant not in {"a", "b", "s"}:
        raise ValueError(f"invalid candidate audit variant: {variant}")
    if variant == "s":
        view_note = (
            "SCREEN DISPROOF AUDIT. CELL 00 is one unaltered full-frame "
            "candidate. First decide whether a photographed physical display "
            "or projection surface actually CONTAINS THE TEXT BEING CLASSIFIED. "
            "An underlying television/projection prop does not make production "
            "names diegetic when those names are composited on the final video "
            "plane, cross the depicted object's bounds, or remain aligned to "
            "the output frame. Black borders, scan lines, gate weave, tape "
            "noise, telecine marks or other transfer artifacts at the output "
            "edges are NOT evidence of a television in the story. If the film "
            "image fills the output frame and there is no visible in-scene "
            "bezel, containing plane, projection rectangle or perspective, "
            "you MUST set inside_story_screen=false and MUST NOT return "
            "DIEGETIC_SCREEN. DIEGETIC_SCREEN is allowed in this audit only "
            "when the same raw frame visibly proves a physical boundary or "
            "perspective cue around the surface that contains the classified "
            "text. A dark full-frame "
            "credit card, full-frame film image, portrait montage, or text "
            "composited over footage is not a story-world screen merely "
            "because it fills the image."
        )
    else:
        view_note = (
        "All five panes are derived from the SAME candidate frame: a full "
        "view, an enhanced full view, a center zoom, a lower-edge zoom, and "
        "a strongly enlarged, contrast-enhanced bottom-edge strip. "
        "Judge that one candidate only. The detail panes may reveal the first "
        "faint centered credit or a partial glyph entering from the bottom; "
        "they are not later frames. Enhancement may reveal existing pixels "
        "but may not invent text."
        if variant == "a"
        else (
            "The row is chronological PRE / CANDIDATE / POST. Judge only "
            f"CELL {candidate_cell:02d}; CELL 00 and CELL 02 are context and "
            "must never be substituted for the candidate."
        )
        )
    return f"""You are the final semantic false-positive auditor for a closing-credit onset detector.
{view_note}
Classify the candidate cell itself. Later genuine credits may clarify layout, but they can NEVER retroactively turn a non-qualifying title, story card, subtitle, sign, television image, or textless frame into the onset.

Return exactly one JSON object with decision, attribution_layout, and inside_story_screen.

Decision contract:
- ATTRIBUTION_CREDIT: the candidate visibly functions as non-diegetic film-production attribution: a cast/crew role and name, a production/legal credit, repeated name list/columns, a credit scroll, clearly credit-like cast names over portraits/footage, a visibly isolated credit-section heading such as AVEC/WITH, CAST, STARRING or CREDITS in a closing-credit card/sequence, or a terminal memorial card such as IN MEMORY OF followed by real-person names in a credit-card layout. A credit-section heading qualifies on its first visible frame even when its names enter on the next frame. Set attribution_layout=true and inside_story_screen=false.
- END_CARD: the candidate visibly contains a non-diegetic THE END equivalent such as THE END, FIN, SON or TAMAM. A film title is not END_CARD. Set inside_story_screen=false.
- TITLE_OR_STORY: film title, slogan, chapter heading, narrative dedication without a credit-card name layout, quotation, date/location, narrative epilogue or other story card. Do not put a terminal IN MEMORY OF plus person-name card here.
- DIEGETIC_SCREEN: the text or broadcast graphic lives inside a photographed television, monitor, cinema projection or other screen in the story world. This includes news lower-thirds, channel logos and interview name straps.
- OTHER_TEXT: subtitle/caption, sign, poster, newspaper, book, document, ID, plate, UI or other non-credit text.
- NO_TEXT: no genuinely visible qualifying text; do not turn grain, compression, scenery, fire or the machine CELL header into text.
- UNCERTAIN: the candidate cannot be assigned safely.

Hard rules:
1. Judge semantics, not darkness or text density. Credits over moving, bright or low-contrast footage are valid when the attribution is composited over the film image rather than living on an object or screen.
2. Accept Turkish, French, Arabic/Persian RTL, Cyrillic and any other script from layout and function. English keywords and readable names are not required.
3. A name alone is insufficient unless the visible layout clearly functions as cast/crew attribution, for example a repeated cast-name series or names paired with character portraits.
4. Gray CELL labels are machine-added and never film text.
5. If a television/monitor/projection or film-title interpretation remains plausible, use DIEGETIC_SCREEN, TITLE_OR_STORY or UNCERTAIN. Do not upgrade it because real credits appear later.
6. DIEGETIC_SCREEN requires a visibly photographed screen/surface context (for example a bezel, room, projected surface, or unmistakable broadcast viewed inside the scene). A full-frame film image, full-screen portrait montage, or cast portrait with composited names is NOT a story-world screen.
7. Inspect the enhanced full view and center zoom for faint/small attribution, and both enlarged lower-edge panes for partial entry. A partial production role/name or THE END glyph entering by only a few pixels already qualifies in the candidate. If a film title remains on screen while a production role/name begins at the bottom, classify ATTRIBUTION_CREDIT because the attribution itself is now visible.
8. For SCREEN DISPROOF, DIEGETIC_SCREEN requires visible physical evidence that the CLASSIFIED TEXT itself is contained by a photographed display: it follows that display's bounds/perspective and belongs to its broadcast/UI content. A screen or projection in the underlying footage is irrelevant when cast/crew names are composited across the final video plane. Never infer a physical screen from black background, small foreign-script text, oval portraits, or the fact that content fills the video frame.

Return only the JSON object. Do not transcribe names."""


def _validate_candidate_audit_payload(
    parsed: dict[str, Any],
) -> tuple[str, bool, bool]:
    decision = parsed.get("decision")
    attribution_layout = parsed.get("attribution_layout")
    inside_story_screen = parsed.get("inside_story_screen")
    if decision not in _CANDIDATE_AUDIT_DECISIONS:
        raise ValueError(f"invalid candidate semantic decision: {decision}")
    if not isinstance(attribution_layout, bool):
        raise ValueError("candidate attribution_layout must be boolean")
    if not isinstance(inside_story_screen, bool):
        raise ValueError("candidate inside_story_screen must be boolean")
    if decision == "ATTRIBUTION_CREDIT" and (
        not attribution_layout or inside_story_screen
    ):
        raise ValueError(
            "ATTRIBUTION_CREDIT requires attribution_layout=true and "
            "inside_story_screen=false"
        )
    if decision == "END_CARD" and inside_story_screen:
        raise ValueError("END_CARD cannot be inside a story-world screen")
    if decision == "DIEGETIC_SCREEN" and not inside_story_screen:
        raise ValueError("DIEGETIC_SCREEN requires inside_story_screen=true")
    if decision == "NO_TEXT" and (attribution_layout or inside_story_screen):
        raise ValueError(
            "NO_TEXT requires attribution_layout=false and "
            "inside_story_screen=false"
        )
    return str(decision), attribution_layout, inside_story_screen


def _prompt(
    frame_ids: list[int],
    columns: int,
    *,
    relative_seconds: list[float] | None = None,
    at_stream_eof: bool = False,
    stage: str = "coarse",
    boundary_search_cells: tuple[int, int] | None = None,
) -> str:
    timing = relative_seconds or [float(index) for index in range(len(frame_ids))]
    eof_note = (
        "The final cell is the real end of the extracted video tail."
        if at_stream_eof
        else "The final cell is only the end of this panel, NOT necessarily video EOF."
    )
    audit_note = (
        "ADVERSARIAL REJECTION AUDIT: actively try to disprove the candidate. "
        "Return a positive state only if the visible text is clearly a "
        "non-diegetic production/credit layer. Persistent text is not enough: "
        "use DIEGETIC, STORY_TEXT, NO_VISIBLE_ATTRIBUTION, or MIXED whenever a "
        "story-world surface, subtitle, narrative epilogue, or textless ending "
        "remains plausible."
        if _is_adversarial_stage(stage) else
        "PRIMARY BOUNDARY VIEW: find the earliest qualifying visible terminal credit."
    )
    boundary_note = ""
    if boundary_search_cells is not None:
        first_candidate, last_candidate = boundary_search_cells
        boundary_note = (
            "EXACT BOUNDARY CONTRACT: only CELL "
            f"{first_candidate:02d}..CELL {last_candidate:02d} are onset "
            "candidates. Earlier cells are left context. Later cells are "
            "SUPPORT ONLY: they may prove continuity and last_support but are "
            "FORBIDDEN as first. Find the earliest visible credit inside the "
            "candidate cells, including a faint/partial line entering at an "
            "edge. A crew role plus its person's name is already a qualifying "
            "credit; never wait for a denser cast/name list. `first` and "
            "`last_support` have different jobs: for CREDIT_SEQUENCE or "
            "END_CARD_THEN_CREDITS choose `first` only from the candidate "
            "cells, but choose `last_support` from a later SUPPORT ONLY cell "
            "roughly 8-15 seconds after first. Do not leave last_support inside "
            "the candidate range when later credit support is visible."
        )
    chronology_note = (
        "EARLIEST-CHRONOLOGY GUARD: this focused panel deliberately excludes a "
        "later, easier logo/card that attracted the coarse model. Inspect every "
        "cell from left to right for an earlier sustained attribution layout. "
        "Treat unreadable Arabic/Persian RTL, Cyrillic, or any other script as "
        "potential credits based on non-diegetic layout, repeated role/name "
        "rows, columns, scrolling and temporal persistence; English words are "
        "irrelevant. A terminal logo after sustained earlier attribution text "
        "cannot be the onset. Return the earliest visible qualifying text, or "
        "ACTIVE_FROM_LEFT if it is already present in CELL 00. Do not call "
        "unreadable non-Latin text a subtitle merely because you cannot read it."
        if _is_chronology_stage(stage) else ""
    )
    micro_note = (
        "MICRO FADE-EDGE ADJUDICATION: the candidate cells are consecutive raw "
        "film frames around an already-supported closing-credit boundary. Pick "
        "the earliest candidate containing a genuinely visible stroke/glyph of "
        "the same non-diegetic credit or ending-card layer, even if extremely "
        "faint. Compare spatially stable letter shapes with the next frame. Do "
        "not accept black-to-picture or black-to-person/scenery as a credit: "
        "the candidate itself must visibly contain non-diegetic attribution "
        "glyphs. A short static name/role card does qualify, and later black "
        "gaps between successive credit cards do not move the onset forward. "
        "Do not turn grain, fire, scenery texture, compression, or the machine CELL "
        "header into text. Support-only cells prove regime identity but can never "
        "be first. If the faint mark is not genuinely attributable text, return "
        "AMBIGUOUS/PRE_ONLY rather than guessing."
        if _is_micro_stage(stage) else ""
    )
    sentinel_note = (
        "SEMANTIC FALSE-POSITIVE SENTINEL: this is a final disproof gate, not "
        "a generic text detector. The onset candidate cell itself must visibly "
        "contain production attribution (role plus person/company, cast/crew "
        "list, production/legal credit) or an accepted THE END equivalent. "
        "Reject a television/monitor/projection inside the photographed story "
        "world, including its broadcast logo, interview name strap or news "
        "lower-third. Reject a film title, slogan, chapter heading, quotation, "
        "dedication or narrative card; later genuine credits cannot "
        "retroactively turn such a title/story card into onset. Credits over "
        "footage remain valid only when the attribution is composited directly "
        "over the film image rather than living on an object/screen in the "
        "scene. Use the long-horizon support cells to disprove temporary story "
        "text, not to excuse a non-qualifying candidate. If story-world or "
        "title-card status remains plausible, return AMBIGUOUS with DIEGETIC, "
        "STORY_TEXT or MIXED rather than a positive state."
        if _is_semantic_sentinel_stage(stage) else ""
    )
    return f"""Do not label cells independently. Locate one real terminal closing-credit regime in this chronological film-tail panel.
The image has {len(frame_ids)} cells in ROW-MAJOR order, {columns} columns. Gray CELL 00.. headers are machine-added indexes: NEVER treat those headers as film text. Cell times relative to CELL 00 are {timing} seconds. {eof_note}
{audit_note}
{boundary_note}
{chronology_note}
{micro_note}
{sentinel_note}

Output exactly one JSON decision:
- PRE_ONLY: first=-1, last_support=-1, kind=NONE, continuity=NONE. No true closing-credit regime begins or remains active here.
- TRANSITION: first=1..{len(frame_ids) - 1}. The preceding cell is pre-credit and `first` is the first actually visible terminal credit/ending-card cell. Set last_support to a later supporting cell.
- ACTIVE_FROM_LEFT: first=0. Credits are already active in CELL 00, so their onset is outside/left of this panel. Set last_support to a supporting cell.
- AMBIGUOUS: first=-1, last_support=-1, kind=NONE, continuity=UNVERIFIABLE or BROKEN.
Kinds: CREDIT_SEQUENCE, END_CARD_THEN_CREDITS, TERMINAL_END_CARD, or NONE. TERMINAL_END_CARD is allowed only when this prompt says the panel reaches real video EOF.
For CREDIT_SEQUENCE/END_CARD_THEN_CREDITS, continuity=CONFIRMED only when later cells visibly support the same credit regime for roughly 8-15 seconds. Real-EOF TERMINAL_END_CARD is the narrow exception: at least two dense cells total (the first card cell plus one later supporting card cell) are enough even when the total is under 8 seconds. It may then fade only to blank/black for at most about 15 seconds before real EOF; set last_support to the last cell where the card itself is visible. If a real-EOF panel contains exactly one plausible non-diegetic terminal card cell with a local PRE cell, keep its location as TRANSITION with last_support=first and continuity=UNVERIFIABLE; the caller will run dense confirmation. Do not use that one-cell probe exception for CREDIT_SEQUENCE, diegetic text, or story text. Otherwise use UNVERIFIABLE/BROKEN. `reject` records the strongest rejection cue or NONE.

Hard semantic rules:
1. CREDIT requires ACTUALLY VISIBLE non-diegetic cast, crew, production or legal attribution text. Scenery/footage with no visible attribution text is never CREDIT. Do not infer credits merely because the images look like an ending.
2. Reject text physically inside the story world: signs, posters, newspapers, books, IDs, plates, televisions, monitors, projections and photographed documents. A broadcast lower-third or interview name strap shown on an in-scene screen is DIEGETIC. Reject subtitles, captions, dates/locations, film titles, slogans, chapter headings, dedications, quotations and narrative epilogues. Except for the explicit THE END-equivalent rule, later credits never make an earlier title/story card count as onset. A name alone is not evidence.
3. Accept scrolling lists, static credit cards, role/name columns, credits over moving or bright scenery, faint low-contrast overlays, and Turkish, French, Arabic/Persian RTL, Cyrillic or other scripts. English keywords are not required.
4. A non-diegetic full-screen THE END / FIN / SON / TAMAM equivalent is END_CARD and counts as onset. A photographed sign/document saying it does not.
5. Use chronology: a true credit sequence persists/repeats in later cells for the local 8-15 second confirmation horizon; short blank cards are allowed. For a real-EOF TERMINAL_END_CARD, apply only the explicit two-dense-cell plus bounded blank-tail exception above. A transient diegetic/story-text cell must not create TRANSITION. If a possible start occurs too late to verify under those rules, return AMBIGUOUS.
6. Scan from CELL 00 forward. Select the EARLIEST actually visible qualifying text, even when it is faint or only one line. Never select a later cell merely because its credits are larger, denser or easier to read. If qualifying credit text is already visible in CELL 00, return ACTIVE_FROM_LEFT rather than a later TRANSITION.

Return only the JSON object. Do not transcribe names."""


def _extract_json(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        left = value.find("{")
        right = value.rfind("}")
        if left < 0 or right <= left:
            raise
        parsed = json.loads(value[left : right + 1])
    if not isinstance(parsed, dict):
        raise ValueError("VLM response root is not an object")
    return parsed


def _response_text(response: dict[str, Any]) -> tuple[str, str]:
    message = response.get("message")
    if isinstance(message, dict):
        content = str(message.get("content") or "").strip()
        if content:
            return content, "message.content"
        thinking = str(message.get("thinking") or "").strip()
        if thinking:
            return thinking, "message.thinking"
    generated = str(response.get("response") or "").strip()
    if generated:
        return generated, "response"
    return "", "none"


def _duration_ms(response: dict[str, Any], name: str) -> float | None:
    value = response.get(name)
    if isinstance(value, (int, float)):
        return round(float(value) / 1_000_000.0, 3)
    return None


class OllamaFrameClassifier:
    """Strict, auditable Ollama/Qwen3-VL frame classifier."""

    def __init__(
        self,
        *,
        model: str,
        host: str,
        timeout_seconds: float,
        keep_alive: str,
        image_width: int,
        jpeg_quality: int,
        num_ctx: int,
        num_predict: int,
        seed: int,
        temperature: float,
        retry_count: int = 2,
        mosaic_columns: int = 4,
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.keep_alive = keep_alive
        self.image_width = image_width
        self.jpeg_quality = jpeg_quality
        self.num_ctx = num_ctx
        self.num_predict = num_predict
        self.seed = seed
        self.temperature = temperature
        self.retry_count = max(1, retry_count)
        self.mosaic_columns = max(1, mosaic_columns)

    def model_identity(self) -> dict[str, Any]:
        """Resolve the exact local model before an expensive frame scan."""
        payload = json.dumps({"model": self.model}).encode("utf-8")
        request = urllib.request.Request(
            self.host + "/api/show",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=min(15.0, self.timeout_seconds)) as stream:
            response = json.loads(stream.read().decode("utf-8"))
        details = response.get("details") if isinstance(response.get("details"), dict) else {}
        model_info = response.get("model_info") if isinstance(response.get("model_info"), dict) else {}
        return {
            "requested_name": self.model,
            "family": details.get("family"),
            "families": details.get("families"),
            "parameter_size": details.get("parameter_size"),
            "quantization_level": details.get("quantization_level"),
            "architecture": model_info.get("general.architecture") or details.get("family"),
            "capabilities": response.get("capabilities", []),
            "modified_at": response.get("modified_at"),
        }

    def audit_candidate_semantics(
        self,
        refs: list[FrameRef],
        *,
        candidate_pos: int,
        variant: str,
        stage: str,
        time_budget_seconds: float | None = None,
        capture_path: Path | None = None,
    ) -> VlmCandidateAuditResult:
        """Classify only one proposed onset, using a dedicated strict schema.

        Variant A transports candidate detail panes. Variant B transports the
        immediately adjacent PRE/candidate/POST triplet. Variant S transports
        one raw full-frame screen-disproof view. Their layouts and prompts are
        intentionally different so agreement is auditable.
        """
        if variant not in {"a", "b", "s"}:
            raise ValueError("candidate semantic variant must be 'a', 'b' or 's'")
        expected_count = 3 if variant == "b" else 1
        candidate_cell = 1 if variant == "b" else 0
        if len(refs) != expected_count:
            raise ValueError(
                f"candidate semantic variant {variant} requires "
                f"{expected_count} frame(s)"
            )
        if refs[candidate_cell].pos != candidate_pos:
            raise ValueError("candidate semantic cell/position mismatch")
        if variant == "b" and not (
            refs[0].pos + 1 == candidate_pos
            and candidate_pos + 1 == refs[2].pos
        ):
            raise ValueError(
                "candidate semantic variant B requires consecutive PRE/CANDIDATE/POST"
            )

        call_id = f"{stage}-{uuid.uuid4().hex[:12]}"
        started = time.perf_counter()
        call_deadline = (
            started + max(0.0, time_budget_seconds)
            if time_budget_seconds is not None else None
        )
        prompt_text = _candidate_audit_prompt(
            variant=variant,
            candidate_cell=candidate_cell,
        )
        prompt_variant = {
            "a": "candidate_single",
            "b": "candidate_context_triplet",
            "s": "candidate_screen_disproof",
        }[variant]
        record: dict[str, Any] = {
            "call_id": call_id,
            "stage": stage,
            "model": self.model,
            "frame_positions": [ref.pos for ref in refs],
            "frame_files": [ref.path.name for ref in refs],
            "expected_count": expected_count,
            "candidate_pos": candidate_pos,
            "candidate_cell": candidate_cell,
            "semantic_variant": variant,
            "attempts": 0,
            "ok": False,
            "time_budget_seconds": time_budget_seconds,
            "prompt_protocol": "candidate_semantic_audit_v1",
            "prompt_variant": prompt_variant,
        }
        try:
            if variant == "a":
                mosaic, mosaic_meta = _encode_candidate_detail_mosaic(
                    refs[0],
                    tile_width=max(720, self.image_width),
                    quality=max(95, self.jpeg_quality),
                )
            elif variant == "s":
                mosaic, mosaic_meta = _encode_candidate_raw_frame(
                    refs[0],
                    max_width=max(960, self.image_width),
                    quality=max(95, self.jpeg_quality),
                )
            else:
                mosaic, mosaic_meta = _encode_mosaic(
                    refs,
                    tile_width=max(720, self.image_width),
                    columns=expected_count,
                    quality=max(95, self.jpeg_quality),
                )
            record["transport_image_count"] = 1
            record["mosaic"] = mosaic_meta
            mosaic_bytes = base64.b64decode(mosaic)
            record["input_sha256"] = hashlib.sha256(mosaic_bytes).hexdigest()
            if capture_path is not None:
                capture_path.parent.mkdir(parents=True, exist_ok=True)
                capture_path.write_bytes(mosaic_bytes)
                record["input_mosaic_path"] = str(capture_path.resolve())
        except Exception as exc:  # noqa: BLE001
            record.update({
                "error_kind": "image_read",
                "error": f"{type(exc).__name__}: {exc}",
                "wall_ms": round((time.perf_counter() - started) * 1000, 3),
            })
            raise VlmCallError(
                "failed to encode candidate semantic input", record=record
            ) from exc

        record["prompt_sha256"] = hashlib.sha256(
            prompt_text.encode("utf-8")
        ).hexdigest()
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": prompt_text,
                "images": [mosaic],
            }],
            "stream": False,
            "think": False,
            "keep_alive": self.keep_alive,
            "format": _candidate_audit_schema(),
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_ctx": self.num_ctx,
                "num_predict": min(self.num_predict, 96),
            },
        }
        url = self.host + "/api/chat"
        last_error: Exception | None = None
        attempt_prompt = prompt_text
        for attempt in range(1, self.retry_count + 1):
            record["attempts"] = attempt
            payload["messages"][0]["content"] = attempt_prompt
            attempt_hash = hashlib.sha256(attempt_prompt.encode("utf-8")).hexdigest()
            record["prompt_sha256"] = attempt_hash
            record.setdefault("prompt_attempt_sha256", []).append(attempt_hash)
            request = urllib.request.Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                request_timeout = self.timeout_seconds
                if call_deadline is not None:
                    remaining = call_deadline - time.perf_counter()
                    if remaining <= 0:
                        raise TimeoutError(
                            "candidate semantic audit exhausted its wall-time budget"
                        )
                    request_timeout = min(request_timeout, max(0.1, remaining))
                with urllib.request.urlopen(
                    request, timeout=request_timeout
                ) as response_stream:
                    response = json.loads(response_stream.read().decode("utf-8"))
                if not isinstance(response, dict):
                    raise ValueError("Ollama HTTP response root is not an object")
                if response.get("done_reason") == "length":
                    raise ValueError("Ollama response truncated (done_reason=length)")
                response_text, response_field = _response_text(response)
                if not response_text:
                    raise ValueError("Ollama response has no content or thinking text")
                parsed = _extract_json(response_text)
                decision, attribution_layout, inside_story_screen = (
                    _validate_candidate_audit_payload(parsed)
                )
                record.update({
                    "ok": True,
                    "response_field": response_field,
                    "done_reason": response.get("done_reason"),
                    "response_chars": len(response_text),
                    "response_json": parsed,
                    "load_ms": _duration_ms(response, "load_duration"),
                    "prompt_eval_ms": _duration_ms(response, "prompt_eval_duration"),
                    "eval_ms": _duration_ms(response, "eval_duration"),
                    "prompt_eval_count": response.get("prompt_eval_count"),
                    "eval_count": response.get("eval_count"),
                    "wall_ms": round((time.perf_counter() - started) * 1000, 3),
                })
                return VlmCandidateAuditResult(
                    decision=decision,
                    attribution_layout=attribution_layout,
                    inside_story_screen=inside_story_screen,
                    call_record=record,
                )
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:1000]
                last_error = RuntimeError(f"HTTP {exc.code}: {detail}")
                break
            except (
                urllib.error.URLError,
                socket.timeout,
                TimeoutError,
                OSError,
                json.JSONDecodeError,
                ValueError,
                TypeError,
                KeyError,
            ) as exc:
                last_error = exc
                if attempt < self.retry_count:
                    if isinstance(exc, ValueError):
                        record.setdefault("validation_failures", []).append({
                            "attempt": attempt,
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        attempt_prompt = (
                            prompt_text
                            + "\n\nSTRICT JSON REPAIR AFTER A REJECTED RESPONSE:\n"
                            + f"The previous response failed validation: {exc}\n"
                            + "Return only a fresh object with exactly decision, "
                            + "attribution_layout and inside_story_screen. "
                            + "ATTRIBUTION_CREDIT requires true/false; "
                            + "DIEGETIC_SCREEN requires inside_story_screen=true; "
                            + "NO_TEXT requires both booleans=false."
                        )
                    wait = 0.5 * attempt
                    if call_deadline is not None:
                        wait = min(
                            wait,
                            max(0.0, call_deadline - time.perf_counter()),
                        )
                    if wait > 0:
                        time.sleep(wait)

        record.update({
            "error_kind": "vlm_call_or_parse",
            "error": f"{type(last_error).__name__}: {last_error}",
            "wall_ms": round((time.perf_counter() - started) * 1000, 3),
        })
        raise VlmCallError(
            "candidate semantic audit failed strict validation", record=record
        ) from last_error

    def classify(
        self,
        refs: list[FrameRef],
        *,
        stage: str,
        time_budget_seconds: float | None = None,
        at_stream_eof: bool = False,
        capture_path: Path | None = None,
        tile_width: int | None = None,
        jpeg_quality: int | None = None,
        mosaic_columns: int | None = None,
        boundary_search_cells: tuple[int, int] | None = None,
    ) -> VlmBatchResult:
        if not refs:
            raise ValueError("classify requires at least one frame")
        if boundary_search_cells is not None:
            first_candidate, last_candidate = boundary_search_cells
            if not 1 <= first_candidate <= last_candidate < len(refs):
                raise ValueError(
                    "boundary_search_cells must be a non-empty in-panel "
                    "TRANSITION range beginning after a PRE/context cell"
                )
        call_id = f"{stage}-{uuid.uuid4().hex[:12]}"
        started = time.perf_counter()
        call_deadline = (
            started + max(0.0, time_budget_seconds)
            if time_budget_seconds is not None else None
        )
        record: dict[str, Any] = {
            "call_id": call_id,
            "stage": stage,
            "model": self.model,
            "frame_positions": [ref.pos for ref in refs],
            "frame_files": [ref.path.name for ref in refs],
            "expected_count": len(refs),
            "attempts": 0,
            "ok": False,
            "time_budget_seconds": time_budget_seconds,
            "at_stream_eof": at_stream_eof,
            "boundary_search_cells": (
                list(boundary_search_cells)
                if boundary_search_cells is not None else None
            ),
        }
        try:
            mosaic, mosaic_meta = _encode_mosaic(
                refs,
                tile_width=tile_width or self.image_width,
                columns=mosaic_columns or self.mosaic_columns,
                quality=jpeg_quality or self.jpeg_quality,
            )
            record["transport_image_count"] = 1
            record["mosaic"] = mosaic_meta
            mosaic_bytes = base64.b64decode(mosaic)
            record["input_sha256"] = hashlib.sha256(mosaic_bytes).hexdigest()
            if capture_path is not None:
                capture_path.parent.mkdir(parents=True, exist_ok=True)
                capture_path.write_bytes(mosaic_bytes)
                record["input_mosaic_path"] = str(capture_path.resolve())
        except Exception as exc:  # noqa: BLE001
            record.update({
                "error_kind": "image_read",
                "error": f"{type(exc).__name__}: {exc}",
                "wall_ms": round((time.perf_counter() - started) * 1000, 3),
            })
            raise VlmCallError("failed to encode input image", record=record) from exc

        prompt_text = _prompt(
            [ref.pos for ref in refs],
            int(record["mosaic"]["columns"]),
            relative_seconds=[
                round(ref.timestamp_seconds - refs[0].timestamp_seconds, 3)
                for ref in refs
            ],
            at_stream_eof=at_stream_eof,
            stage=stage,
            boundary_search_cells=boundary_search_cells,
        )
        record["prompt_protocol"] = "window_boundary_v1"
        record["prompt_variant"] = (
            "adversarial_reject"
            if _is_adversarial_stage(stage)
            else "primary_boundary"
        )
        record["prompt_sha256"] = hashlib.sha256(
            prompt_text.encode("utf-8")
        ).hexdigest()
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": prompt_text,
                "images": [mosaic],
            }],
            "stream": False,
            "think": False,
            "keep_alive": self.keep_alive,
            "format": _schema(len(refs), boundary_search_cells),
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
        }
        url = self.host + "/api/chat"
        last_error: Exception | None = None
        attempt_prompt = prompt_text

        for attempt in range(1, self.retry_count + 1):
            record["attempts"] = attempt
            payload["messages"][0]["content"] = attempt_prompt
            attempt_prompt_sha256 = hashlib.sha256(
                attempt_prompt.encode("utf-8")
            ).hexdigest()
            record["prompt_sha256"] = attempt_prompt_sha256
            record.setdefault("prompt_attempt_sha256", []).append(
                attempt_prompt_sha256
            )
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                request_timeout = self.timeout_seconds
                if call_deadline is not None:
                    remaining = call_deadline - time.perf_counter()
                    if remaining <= 0:
                        raise TimeoutError("VLM batch exhausted the film wall-time budget")
                    request_timeout = min(request_timeout, max(0.1, remaining))
                with urllib.request.urlopen(request, timeout=request_timeout) as response_stream:
                    response = json.loads(response_stream.read().decode("utf-8"))
                if not isinstance(response, dict):
                    raise ValueError("Ollama HTTP response root is not an object")
                if response.get("done_reason") == "length":
                    raise ValueError("Ollama response truncated (done_reason=length)")
                response_text, response_field = _response_text(response)
                if not response_text:
                    raise ValueError("Ollama response has no content or thinking text")
                parsed = _extract_json(response_text)
                observations = self._validate_frames(
                    parsed,
                    refs,
                    stage,
                    call_id,
                    boundary_search_cells=boundary_search_cells,
                )
                record.update({
                    "ok": True,
                    "response_field": response_field,
                    "done_reason": response.get("done_reason"),
                    "response_chars": len(response_text),
                    "response_json": parsed,
                    "load_ms": _duration_ms(response, "load_duration"),
                    "prompt_eval_ms": _duration_ms(response, "prompt_eval_duration"),
                    "eval_ms": _duration_ms(response, "eval_duration"),
                    "prompt_eval_count": response.get("prompt_eval_count"),
                    "eval_count": response.get("eval_count"),
                    "wall_ms": round((time.perf_counter() - started) * 1000, 3),
                })
                return VlmBatchResult(observations=observations, call_record=record)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:1000]
                last_error = RuntimeError(f"HTTP {exc.code}: {detail}")
                # Bad request/model-not-found will not heal by retrying.
                break
            except (urllib.error.URLError, socket.timeout, TimeoutError, OSError,
                    json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
                last_error = exc
                if attempt < self.retry_count:
                    if isinstance(exc, ValueError):
                        record.setdefault("validation_failures", []).append({
                            "attempt": attempt,
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                        attempt_prompt = (
                            prompt_text
                            + "\n\nSTRICT JSON REPAIR AFTER A REJECTED RESPONSE:\n"
                            + f"The previous response failed validation: {exc}\n"
                            + "Return a fresh JSON object only. PRE_ONLY or an "
                            + "onset-free AMBIGUOUS decision requires first=-1, "
                            + "last_support=-1 and kind=NONE. TRANSITION or "
                            + "ACTIVE_FROM_LEFT requires first>=0 and "
                            + "last_support>=first. Keep first inside the allowed "
                            + "boundary candidate cells and last_support inside "
                            + "the panel. Do not repeat the invalid combination."
                        )
                    wait = 0.5 * attempt
                    if call_deadline is not None:
                        wait = min(wait, max(0.0, call_deadline - time.perf_counter()))
                    if wait > 0:
                        time.sleep(wait)

        record.update({
            "error_kind": "vlm_call_or_parse",
            "error": f"{type(last_error).__name__}: {last_error}",
            "wall_ms": round((time.perf_counter() - started) * 1000, 3),
        })
        raise VlmCallError("VLM batch failed strict validation", record=record) from last_error

    def locate_window(
        self,
        refs: list[FrameRef],
        *,
        stage: str,
        time_budget_seconds: float | None = None,
        at_stream_eof: bool = False,
        capture_path: Path | None = None,
        tile_width: int | None = None,
        jpeg_quality: int | None = None,
        mosaic_columns: int | None = None,
        boundary_search_cells: tuple[int, int] | None = None,
    ) -> VlmWindowResult:
        """Return one strictly validated window-level decision.

        No per-frame CREDIT run is synthesized here. The caller must decode
        independent window evidence and verification calls directly.
        """
        batch = self.classify(
            refs,
            stage=stage,
            time_budget_seconds=time_budget_seconds,
            at_stream_eof=at_stream_eof,
            capture_path=capture_path,
            tile_width=tile_width,
            jpeg_quality=jpeg_quality,
            mosaic_columns=mosaic_columns,
            boundary_search_cells=boundary_search_cells,
        )
        parsed = batch.call_record.get("response_json")
        if not isinstance(parsed, dict):
            raise VlmCallError(
                "validated call record lost its window JSON",
                record=batch.call_record,
            )
        evidence = self._parse_window_evidence(
            parsed,
            refs,
            stage,
            str(batch.call_record.get("call_id") or ""),
            at_stream_eof=at_stream_eof,
            boundary_search_cells=boundary_search_cells,
        )
        return VlmWindowResult(evidence=evidence, call_record=batch.call_record)

    @staticmethod
    def _validate_frames(
        parsed: dict[str, Any],
        refs: list[FrameRef],
        stage: str,
        call_id: str,
        *,
        boundary_search_cells: tuple[int, int] | None = None,
    ) -> list[Observation]:
        if any(key in parsed for key in ("state", "first", "kind")):
            return OllamaFrameClassifier._validate_window_decision(
                parsed,
                refs,
                stage,
                call_id,
                boundary_search_cells=boundary_search_cells,
            )
        if "ids" in parsed or "labels" in parsed or "confidence" in parsed:
            return OllamaFrameClassifier._validate_compact(
                parsed, refs, stage, call_id
            )

        # Backward-compatible strict parser for already captured debug replies.
        # New live requests use window-level evidence; old frame-shaped replies
        # remain readable only for forensic replay and legacy tests.
        rows = parsed.get("frames")
        if not isinstance(rows, list):
            raise ValueError("response.frames is not an array")
        expected = [ref.pos for ref in refs]
        got = [row.get("id") if isinstance(row, dict) else None for row in rows]
        if got != expected:
            raise ValueError(f"frame ids mismatch: expected={expected}, got={got}")

        observations: list[Observation] = []
        for ref, row in zip(refs, rows):
            if not isinstance(row, dict):
                raise ValueError("frame result is not an object")
            label = Label(str(row["label"]))
            plane = str(row["text_plane"])
            cue = str(row["cue"])
            if plane not in TEXT_PLANES:
                raise ValueError(f"invalid text_plane: {plane}")
            if cue not in CUES:
                raise ValueError(f"invalid cue: {cue}")
            confidence = float(row["confidence"])
            if not 0.0 <= confidence <= 1.0:
                raise ValueError(f"invalid confidence: {confidence}")
            observations.append(Observation(
                pos=ref.pos,
                frame_no=ref.frame_no,
                file=ref.path.name,
                label=label,
                confidence=confidence,
                stage=stage,
                text_plane=plane,
                cue=cue,
                call_id=call_id,
            ))
        return observations

    @staticmethod
    def _parse_window_evidence(
        parsed: dict[str, Any],
        refs: list[FrameRef],
        stage: str,
        call_id: str,
        *,
        at_stream_eof: bool = False,
        boundary_search_cells: tuple[int, int] | None = None,
    ) -> WindowEvidence:
        state = parsed.get("state")
        first = parsed.get("first")
        last_support = parsed.get("last_support")
        kind = parsed.get("kind")
        continuity = parsed.get("continuity")
        reject = parsed.get("reject")
        if state not in {
            WindowVerdict.PRE_ONLY.value,
            WindowVerdict.TRANSITION.value,
            WindowVerdict.ACTIVE_FROM_LEFT.value,
            WindowVerdict.AMBIGUOUS.value,
        }:
            raise ValueError(f"invalid window state: {state}")
        if isinstance(first, bool) or not isinstance(first, int):
            raise ValueError(f"window first must be an integer: {first}")
        if isinstance(last_support, bool) or not isinstance(last_support, int):
            raise ValueError(f"window last_support must be an integer: {last_support}")
        if kind not in {item.value for item in BoundaryKind}:
            raise ValueError(f"invalid window kind: {kind}")
        if continuity not in {item.value for item in Continuity}:
            raise ValueError(f"invalid window continuity: {continuity}")
        if reject not in {
            "NONE", "DIEGETIC", "STORY_TEXT", "NO_VISIBLE_ATTRIBUTION", "MIXED"
        }:
            raise ValueError(f"invalid window reject reason: {reject}")

        if state == WindowVerdict.PRE_ONLY.value:
            if (
                first != -1
                or last_support != -1
                or kind != BoundaryKind.NONE.value
                or continuity != Continuity.NONE.value
            ):
                raise ValueError(
                    "PRE_ONLY requires first/last_support=-1, kind=NONE, "
                    f"continuity=NONE; got {parsed}"
                )
        elif state == WindowVerdict.AMBIGUOUS.value:
            if first != -1 or last_support != -1 or kind != BoundaryKind.NONE.value:
                raise ValueError(
                    "AMBIGUOUS requires first/last_support=-1 and kind=NONE; "
                    f"got {parsed}"
                )
            if continuity not in {Continuity.UNVERIFIABLE.value, Continuity.BROKEN.value}:
                raise ValueError("AMBIGUOUS requires UNVERIFIABLE or BROKEN continuity")
        else:
            if kind == BoundaryKind.NONE.value:
                raise ValueError(f"{state} requires a non-NONE boundary kind")
            if state == WindowVerdict.ACTIVE_FROM_LEFT.value and first != 0:
                raise ValueError("ACTIVE_FROM_LEFT requires first=0")
            if state == WindowVerdict.TRANSITION.value and not 1 <= first < len(refs):
                raise ValueError(
                    f"TRANSITION requires first in 1..{len(refs) - 1}; got {first}"
                )
            if (
                state == WindowVerdict.TRANSITION.value
                and boundary_search_cells is not None
                and not boundary_search_cells[0] <= first <= boundary_search_cells[1]
            ):
                raise ValueError(
                    "TRANSITION first lies outside exact boundary candidate "
                    f"cells {boundary_search_cells}: {first}"
                )
            if not first <= last_support < len(refs):
                raise ValueError(
                    "positive window requires first <= last_support < count; "
                    f"got first={first}, last_support={last_support}, count={len(refs)}"
                )

        return WindowEvidence(
            stage=stage,
            positions=[ref.pos for ref in refs],
            files=[ref.path.name for ref in refs],
            verdict=state,
            first_cell=first,
            last_support_cell=last_support,
            first_pos=(refs[first].pos if first >= 0 else None),
            last_support_pos=(refs[last_support].pos if last_support >= 0 else None),
            kind=kind,
            continuity=continuity,
            reject=reject,
            at_stream_eof=at_stream_eof,
            call_id=call_id,
            metadata={
                "response_format": "window_boundary_v1",
                "boundary_search_cells": (
                    list(boundary_search_cells)
                    if boundary_search_cells is not None else None
                ),
            },
        )

    @staticmethod
    def _validate_window_decision(
        parsed: dict[str, Any],
        refs: list[FrameRef],
        stage: str,
        call_id: str,
        *,
        boundary_search_cells: tuple[int, int] | None = None,
    ) -> list[Observation]:
        """Legacy adapter only; the window detector consumes WindowEvidence.

        This adapter keeps historical unit/debug paths readable. It must not be
        used as persistence evidence by the new window-level decoder.
        """
        evidence = OllamaFrameClassifier._parse_window_evidence(
            parsed,
            refs,
            stage,
            call_id,
            boundary_search_cells=boundary_search_cells,
        )
        state = evidence.verdict
        first = evidence.first_cell
        kind = evidence.kind

        observations: list[Observation] = []
        for local_index, ref in enumerate(refs):
            if state == WindowVerdict.PRE_ONLY.value:
                label = Label.FOOTAGE
                confidence = 0.9
            elif state == WindowVerdict.AMBIGUOUS.value:
                label = Label.UNCERTAIN
                confidence = 0.0
            elif state == WindowVerdict.ACTIVE_FROM_LEFT.value:
                label = (
                    Label.END_CARD
                    if local_index == 0 and kind != BoundaryKind.CREDIT_SEQUENCE.value
                    else Label.CREDIT
                )
                confidence = 0.9
            elif local_index < first:
                label = Label.FOOTAGE
                confidence = 0.9
            else:
                label = (
                    Label.END_CARD
                    if local_index == first and kind != BoundaryKind.CREDIT_SEQUENCE.value
                    else Label.CREDIT
                )
                confidence = 0.9

            plane = (
                "FULLSCREEN_CARD"
                if label == Label.END_CARD
                else "SCREEN_OVERLAY"
                if label == Label.CREDIT
                else "UNKNOWN"
                if label == Label.UNCERTAIN
                else "NONE"
            )
            cue = (
                "ENDING_CARD"
                if label == Label.END_CARD
                else "CAST_CREW_LIST"
                if label == Label.CREDIT
                else "AMBIGUOUS"
                if label == Label.UNCERTAIN
                else "NO_TEXT"
            )
            observations.append(Observation(
                pos=ref.pos,
                frame_no=ref.frame_no,
                file=ref.path.name,
                label=label,
                confidence=confidence,
                stage=stage,
                text_plane=plane,
                cue=cue,
                call_id=call_id,
                metadata={
                    "response_format": "window_boundary_v1_legacy_adapter",
                    "window_state": state,
                    "window_first": first,
                    "window_kind": kind,
                    "local_index": local_index,
                },
            ))
        return observations

    @staticmethod
    def _validate_compact(
        parsed: dict[str, Any],
        refs: list[FrameRef],
        stage: str,
        call_id: str,
    ) -> list[Observation]:
        labels_raw = parsed.get("labels")
        confidences_raw = parsed.get("confidence")
        label_only_protocol = isinstance(labels_raw, list) and confidences_raw is None
        legacy_array_protocol = isinstance(labels_raw, list) and isinstance(confidences_raw, list)
        if not label_only_protocol and not legacy_array_protocol:
            raise ValueError(
                "compact response requires a labels array "
                "(legacy labels/confidence arrays are accepted for debug replay)"
            )
        labels = labels_raw
        confidences = confidences_raw if legacy_array_protocol else None
        expected = [ref.pos for ref in refs]
        # Older compact debug captures may include ids. New live schema does
        # not ask the model to reproduce numbers; row-major position is the
        # identity and exact array length is grammar-constrained.
        ids = parsed.get("ids")
        if ids is not None and ids != expected:
            raise ValueError(f"frame ids mismatch: expected={expected}, got={ids}")
        if len(labels) != len(refs) or (
            confidences is not None and len(confidences) != len(refs)
        ):
            raise ValueError(
                "compact response length mismatch: "
                f"expected={len(refs)}, labels={len(labels)}, "
                f"confidence={None if confidences is None else len(confidences)}"
            )
        plane_cue = {
            Label.CREDIT: ("SCREEN_OVERLAY", "CAST_CREW_LIST"),
            Label.DIEGETIC_TEXT: ("SCENE_SURFACE", "SCENE_SURFACE"),
            Label.STORY_TEXT: ("UNKNOWN", "STORY_CARD"),
            Label.END_CARD: ("FULLSCREEN_CARD", "ENDING_CARD"),
            Label.FOOTAGE: ("NONE", "NO_TEXT"),
            Label.BLANK: ("NONE", "NO_TEXT"),
            Label.UNCERTAIN: ("UNKNOWN", "AMBIGUOUS"),
        }
        observations: list[Observation] = []
        confidence_values = confidences if confidences is not None else [None] * len(refs)
        for ref, code, raw_confidence in zip(refs, labels, confidence_values):
            label = _CODE_TO_LABEL.get(str(code))
            if label is None:
                raise ValueError(f"invalid compact label code: {code}")
            if label_only_protocol:
                confidence = 0.0 if label is Label.UNCERTAIN else 0.9
                response_format = "compact_mosaic_v2_labels"
            else:
                if isinstance(raw_confidence, bool) or not isinstance(raw_confidence, int):
                    raise ValueError(f"confidence must be an integer 0..100: {raw_confidence}")
                if not 0 <= raw_confidence <= 100:
                    raise ValueError(f"confidence out of range: {raw_confidence}")
                confidence = raw_confidence / 100.0
                response_format = "compact_mosaic_v1_arrays"
            plane, cue = plane_cue[label]
            observations.append(Observation(
                pos=ref.pos,
                frame_no=ref.frame_no,
                file=ref.path.name,
                label=label,
                confidence=confidence,
                stage=stage,
                text_plane=plane,
                cue=cue,
                call_id=call_id,
                metadata={"response_format": response_format},
            ))
        return observations
