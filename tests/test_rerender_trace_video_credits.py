import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import rerender_pdf_only as rr  # noqa: E402


def test_video_credits_from_trace_uses_last_v4_candidate_read(tmp_path):
    trace_dir = tmp_path / "debug_trace"
    trace_dir.mkdir()
    events = [
        {"stage": "v4", "event": "candidate_read", "subject": {
            "field": "video_okuma",
            "after": {"yonetmen": ["OLD"], "cast": ["A"], "yapimci": []},
        }},
        {"stage": "v4", "event": "candidate_read", "subject": {
            "field": "video_okuma",
            "after": {
                "yonetmen": ["SZABOLCS HAJDU"],
                "cast": ["ORION RADIES", "SILAS RADIES"],
                "yapimci": ["THOMAS FELLEGI"],
                "guven": "OKUNDU",
            },
        }},
    ]
    with (trace_dir / "trace.jsonl").open("w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")

    vc = rr._video_credits_from_trace(tmp_path)
    assert vc == {
        "yonetmen": ["SZABOLCS HAJDU"],
        "cast": ["ORION RADIES", "SILAS RADIES"],
        "yapimci": ["THOMAS FELLEGI"],
        "guven": "OKUNDU",
    }


def test_derive_karar_keeps_missing_poster_in_kontrol():
    qcb = {
        "karar": "AUTO-FIX",
        "tip": "AFIS",
        "gerekceler": [],
        "floor": {"hedef": 8, "ulasilan": 7, "kabul": True},
    }

    karar, route = rr._derive_karar(
        qcb,
        qwen_uyari=["qwen: afiş yok (deterministik poster_fetch garanti — uyarı)"],
    )

    assert karar == "Kontrol"
    assert route["tier"] == "AUTOFIX"
    assert route["kontrol_tip"] == "HAFIF_AFIS"


def test_derive_karar_clean_qc_without_qwen_warning_is_ready():
    qcb = {
        "karar": "AUTO-FIX",
        "tip": "AFIS",
        "gerekceler": [],
        "floor": {"hedef": 8, "ulasilan": 7, "kabul": True},
    }

    karar, route = rr._derive_karar(qcb, qwen_uyari=[])

    assert karar == "Hazır"
    assert route["tier"] == "TEMIZ"


def test_derive_karar_person_teyit_relaxes_identity_only_block():
    qcb = {
        "karar": "KONTROL",
        "tip": "KIMLIK",
        "gerekceler": ["kimlik kurulamadı (cast-örtüşme<2, web çapası kilitlenemedi)"],
        "floor": {"hedef": 6, "ulasilan": 10, "kabul": True},
    }

    karar, route = rr._derive_karar(
        qcb,
        qwen_uyari=[
            "kişi-teyit: cast 9/10 KB-ONAY, yön KB-ONAY → film-KB'siz doğrulama (Çağatay kuralı)"
        ],
    )

    assert karar == "Hazır"
    assert route["tier"] == "TEMIZ"
    assert route["reasons"] == []
