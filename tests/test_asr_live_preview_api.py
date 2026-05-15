from __future__ import annotations

import base64
from typing import Any

import pytest


def test_stt_preview_websocket_transcribes_pcm_chunk(monkeypatch) -> None:
    pytest.importorskip("fastapi.testclient")
    from fastapi.testclient import TestClient
    from core.api import asr_server

    calls: list[dict[str, Any]] = []

    def fake_transcribe(
        audio_bytes: bytes,
        media_time_start: float,
        media_time_end: float,
        publish_after: float | None = None,
        publish_until: float | None = None,
    ) -> list[dict[str, Any]]:
        calls.append(
            {
                "audio_bytes": audio_bytes,
                "media_time_start": media_time_start,
                "media_time_end": media_time_end,
                "publish_after": publish_after,
                "publish_until": publish_until,
            }
        )
        return [
            {
                "id": "live-0",
                "start": media_time_start,
                "end": media_time_end,
                "text": "Merhaba canlı transcript",
                "language": "tr",
                "avg_logprob": -0.2,
                "no_speech_prob": 0.01,
            }
        ]

    monkeypatch.setattr(asr_server, "_transcribe_live_pcm16", fake_transcribe)

    client = TestClient(asr_server.app)
    with client.websocket_connect("/api/stt/preview/ws") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "ready"
        assert ready["sample_rate"] == 16_000

        websocket.send_json({"type": "start"})
        assert websocket.receive_json()["status"] == "ready"

        websocket.send_json({"type": "resume"})
        assert websocket.receive_json()["status"] == "listening"

        pcm = b"\x00\x00" * 16_000
        websocket.send_json(
            {
                "type": "chunk",
                "chunk_id": "chunk-1",
                "media_time_start": 10.0,
                "media_time_end": 13.0,
                "publish_after": 12.0,
                "publish_until": 12.8,
                "audio_b64": base64.b64encode(pcm).decode("ascii"),
            }
        )

        resolving = websocket.receive_json()
        assert resolving["type"] == "status"
        assert resolving["status"] == "resolving"
        assert resolving["chunk_id"] == "chunk-1"

        partial = websocket.receive_json()
        assert partial["type"] == "partial"
        assert partial["text"] == "Merhaba canlı transcript"
        assert partial["chunk_id"] == "chunk-1"

        final = websocket.receive_json()
        assert final["type"] == "final"
        assert final["chunk_id"] == "chunk-1"
        assert final["media_time_start"] == 12.0
        assert final["media_time_end"] == 12.8
        assert final["publish_until"] == 12.8
        assert final["text"] == "Merhaba canlı transcript"
        assert final["segments"][0]["start"] == 10.0
        assert final["segments"][0]["end"] == 13.0
        assert final["language"] == "tr"

        listening = websocket.receive_json()
        assert listening["status"] == "listening"

    assert calls == [
        {
            "audio_bytes": pcm,
            "media_time_start": 10.0,
            "media_time_end": 13.0,
            "publish_after": 12.0,
            "publish_until": 12.8,
        }
    ]


def test_live_text_repairs_iconic_code_switching() -> None:
    from core.api.live_stt_text import repair_live_text

    assert repair_live_text("one minut five min") == "One minute"
    assert repair_live_text("Five minutes. Five minutes.") == "One minute. One minute."
    assert repair_live_text("the gardiyan diyor") == "The Guardian diyor"
    assert repair_live_text("üngiliz gazetesi") == "İngiliz gazetesi"
    assert repair_live_text("İngilizce " * 20) == ""
    assert repair_live_text("İzlediğiniz için teşekkür ederim.") == ""
    assert repair_live_text("Özel kalıplar.") == ""
