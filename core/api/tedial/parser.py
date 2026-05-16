"""Parsers for Tedial iT Client HTML fragments."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable


@dataclass(frozen=True)
class TedialSearchResult:
    box_id: str | None
    title: str | None
    trt_id: str | None
    repository_id: str | None
    sequence_id: str | None
    asset_id: str | None
    asset_type: str | None
    fps: float | None
    tc_in: float | None
    tc_out: float | None
    keyframe_url: str | None
    image_tc_in: str | None
    image_tc_out: str | None

    @property
    def duration_units(self) -> float | None:
        if self.tc_in is None or self.tc_out is None:
            return None
        return max(0.0, self.tc_out - self.tc_in)


class _SearchHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[TedialSearchResult] = []
        self._row_depth = 0
        self._row: dict[str, str] | None = None
        self._heading_depth = 0
        self._heading_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {name: value or "" for name, value in attrs}
        if tag == "li" and _has_class(attr, "block-section-box"):
            self._row_depth = 1
            self._row = {"box_id": attr.get("id", "")}
            self._heading_depth = 0
            self._heading_parts = []
            return
        if self._row is None:
            return
        if tag == "li":
            self._row_depth += 1
        if self._heading_depth:
            self._heading_depth += 1
        elif tag == "h3":
            self._heading_depth = 1
            self._heading_parts = []
        if tag == "div":
            div_id = attr.get("id", "")
            if div_id.startswith("box-") and div_id != self._row.get("box_id"):
                self._row["sequence_box_id"] = div_id
        elif tag == "input":
            self._capture_input(attr)
        elif tag == "img" and _has_class(attr, "keyframeImg") and attr.get("src"):
            self._row["keyframe_url"] = attr["src"]
            repository_id = _repository_id_from_keyframe_url(attr["src"])
            if repository_id:
                self._row["repository_id"] = repository_id

    def handle_data(self, data: str) -> None:
        if self._row is not None and self._heading_depth and data.strip():
            self._heading_parts.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if self._row is None:
            return
        if self._heading_depth:
            self._heading_depth -= 1
            if self._heading_depth <= 0:
                self._row["heading_text"] = " ".join(self._heading_parts)
                self._heading_parts = []
        if tag != "li":
            return
        self._row_depth -= 1
        if self._row_depth <= 0:
            self.results.append(_row_to_result(self._row))
            self._row = None
            self._row_depth = 0

    def _capture_input(self, attr: dict[str, str]) -> None:
        if self._row is None:
            return
        key = attr.get("id") or attr.get("name")
        value = attr.get("value", "")
        mapping = {
            "titleHidden": "title",
            "sequenceIdHidden": "sequence_id",
            "assetIdIdHidden": "asset_id",
            "assetType": "asset_type",
            "fps": "fps",
            "tcIn": "tc_in",
            "tcOut": "tc_out",
            "imageTcIn": "image_tc_in",
            "imageTcOut": "image_tc_out",
        }
        target = mapping.get(key)
        if target:
            self._row[target] = value


def parse_search_results(html_text: str) -> list[TedialSearchResult]:
    parser = _SearchHTMLParser()
    parser.feed(html_text)
    parser.close()
    return parser.results


def _has_class(attrs: dict[str, str], class_name: str) -> bool:
    return class_name in attrs.get("class", "").split()


def _row_to_result(row: dict[str, str]) -> TedialSearchResult:
    box_id = row.get("sequence_box_id") or row.get("box_id") or None
    return TedialSearchResult(
        box_id=box_id,
        title=_empty_to_none(row.get("title")),
        trt_id=_trt_id_from_heading(row.get("heading_text")),
        repository_id=_empty_to_none(row.get("repository_id")),
        sequence_id=_empty_to_none(row.get("sequence_id")),
        asset_id=_empty_to_none(row.get("asset_id")),
        asset_type=_empty_to_none(row.get("asset_type")),
        fps=_to_float(row.get("fps")),
        tc_in=_to_float(row.get("tc_in")),
        tc_out=_to_float(row.get("tc_out")),
        keyframe_url=_empty_to_none(row.get("keyframe_url")),
        image_tc_in=_empty_to_none(row.get("image_tc_in")),
        image_tc_out=_empty_to_none(row.get("image_tc_out")),
    )


def _empty_to_none(value: str | None) -> str | None:
    return value if value else None


def _to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _repository_id_from_keyframe_url(url: str) -> str | None:
    marker = "/MamService/KeyframeService/"
    if marker not in url:
        return None
    rest = url.split(marker, 1)[1]
    parts = rest.split("/", 2)
    return parts[0] if parts else None


def _trt_id_from_heading(text: str | None) -> str | None:
    if not text:
        return None
    marker = "TRT ID:"
    if marker not in text:
        return None
    rest = text.split(marker, 1)[1].strip()
    for stop in ("ARSIV YER NO:", "ARŞİV YER NO:"):
        if stop in rest:
            rest = rest.split(stop, 1)[0].strip()
    return rest or None


__all__: Iterable[str] = ["TedialSearchResult", "parse_search_results"]
