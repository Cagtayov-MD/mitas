from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def setup_profile(tmp_path: Path, title: str = "Test Dizi") -> Path:
    seed = ROOT / "tests" / "fixtures" / "seed.json"
    profile = tmp_path / "profile.json"
    cmd = [sys.executable, str(ROOT / "main.py"), "profil-olustur",
           "--series-id", "dizi1", "--title", title,
           "--seed", str(seed), "--profile", str(profile)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return profile


def setup_iz_pesinde_profile(tmp_path: Path) -> Path:
    seed = ROOT / "seeds" / "iz_pesinde_1989_seed.json"
    profile = tmp_path / "iz-pesinde.json"
    cmd = [sys.executable, str(ROOT / "main.py"), "profil-olustur",
           "--series-id", "iz-pesinde", "--title", "İz Peşinde",
           "--seed", str(seed), "--profile", str(profile)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return profile


def run_episode(tmp_path: Path, profile: Path, jordan: str, nash: str, lebron: str | None = None,
                series_id: str = "dizi1"):
    inputs = {}
    for name, text in (("jordan", jordan), ("nash", nash), ("lebron", lebron)):
        if text is None:
            continue
        p = tmp_path / f"{name}.txt"
        p.write_text(text, encoding="utf-8")
        inputs[name] = p
    out = tmp_path / "out"
    cmd = [sys.executable, str(ROOT / "main.py"), "tek",
           "--series-id", series_id, "--episode-id", "007",
           "--profile", str(profile), "--out", str(out)]
    for name, path in inputs.items():
        cmd.extend([f"--{name}", str(path)])
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    result = json.loads((out / series_id / "007" / "kyle.json").read_text(encoding="utf-8"))
    return proc, result, out / series_id / "007"


def test_known_people_are_suppressed(tmp_path: Path):
    profile = setup_profile(tmp_path)
    proc, result, outdir = run_episode(
        tmp_path, profile,
        "KENEN ISIK\nAYŞE DEMİR\nYÖNETMEN\nCENGİZ KURT\nIŞIK ŞEFİ\nAHMET YILMAZ\n",
        "KENAN ISIK\nAYSE DEMIR\nYONETMEN\nCENGIZ KURT\nISIK SEFI\nAHMET YILMAZ\n",
    )
    assert proc.returncode == 0
    assert result["durum"] == "DEGISIKLIK_YOK"
    assert result["changes"] == []
    assert (outdir / "_TAMAM").exists()
    assert (outdir / "rapor.pdf").exists()


def test_count_increase_red_flag(tmp_path: Path):
    profile = setup_profile(tmp_path)
    _, result, _ = run_episode(
        tmp_path, profile,
        "IŞIK ŞEFİ\nAHMET YILMAZ\nMEHMET CAN\n",
        "ISIK SEFI\nAHMET YILMAZ\nMEHMET CAN\n",
        "IŞIK ŞEFİ\nAHMET YILMAZ\nMEHMET CAM\n",
    )
    assert result["durum"] == "DEGISIKLIK_VAR"
    changes = [x for x in result["changes"] if x["role"] == "ISIK SEFI"]
    assert len(changes) == 1
    assert changes[0]["type"] == "COUNT_INCREASE"
    assert changes[0]["severity"] == "KIRMIZI"
    assert changes[0]["new_name"] == "MEHMET CAN"
    assert changes[0]["support_count"] == 3


def test_role_holder_changed(tmp_path: Path):
    profile = setup_profile(tmp_path)
    _, result, _ = run_episode(
        tmp_path, profile,
        "YÖNETMEN\nMEHMET AK\n",
        "YONETMEN\nMEHMET AK\n",
        "YÖNETMEN\nMEHMET A?\n",
    )
    change = next(x for x in result["changes"] if x["role"] == "YONETMEN")
    assert change["type"] == "ROLE_HOLDER_CHANGED"
    assert change["new_name"] == "MEHMET AK"
    assert change["previous_names"] == ["CENGİZ KURT"]


def test_guest_is_reported_but_known_cast_is_silent(tmp_path: Path):
    profile = setup_profile(tmp_path)
    _, result, _ = run_episode(
        tmp_path, profile,
        "KENAN IŞIK\nKONUK OYUNCULAR\nSELİM KAYA\n",
        "KENEN ISIK\nKONUK OYUNCU\nSELIM KAYA\n",
        "KENAN IŞK\nGUEST CAST\nSELİM KAYA\n",
    )
    assert len(result["changes"]) == 1
    assert result["changes"][0]["type"] == "NEW_GUEST"
    assert result["changes"][0]["new_name"] == "SELİM KAYA"


def test_single_source_new_name_is_not_reported(tmp_path: Path):
    profile = setup_profile(tmp_path)
    _, result, _ = run_episode(
        tmp_path, profile,
        "IŞIK ŞEFİ\nAHMET YILMAZ\nTEK KAYNAK\n",
        "ISIK SEFI\nAHMET YILMAZ\n",
    )
    assert result["durum"] == "DEGISIKLIK_YOK"
    assert any(x["candidate"] == "TEK KAYNAK" for x in result["review_candidates"])


def test_memory_patch_requires_explicit_apply(tmp_path: Path):
    profile = setup_profile(tmp_path)
    _, result, outdir = run_episode(
        tmp_path, profile,
        "KONUK OYUNCULAR\nSELİM KAYA\n",
        "KONUK OYUNCULAR\nSELIM KAYA\n",
    )
    before = json.loads(profile.read_text(encoding="utf-8"))
    assert before["roles"]["KONUK OYUNCULAR"]["members"] == []
    patch = outdir / "memory_patch.json"
    subprocess.run([sys.executable, str(ROOT / "main.py"), "uygula",
                    "--series-id", "dizi1", "--profile", str(profile), "--patch", str(patch)],
                   check=True, capture_output=True, text=True)
    after = json.loads(profile.read_text(encoding="utf-8"))
    assert after["roles"]["KONUK OYUNCULAR"]["members"][0]["canonical_name"] in {"SELİM KAYA", "SELIM KAYA"}


def test_series_title_is_metadata_not_actor(tmp_path: Path):
    profile = setup_profile(tmp_path, title="İZ PEŞİNDE")
    _, result, outdir = run_episode(
        tmp_path, profile,
        "12 PEŞİNDE\nİZ PEŞİNDE\nKENAN IŞIK\nAYŞE DEMİR\n",
        "IZ PESINDE\nKENEN ISIK\nAYSE DEMIR\n",
    )
    assert result["durum"] == "DEGISIKLIK_YOK"
    assert all(x.get("new_name") not in {"İZ PEŞİNDE", "IZ PESINDE", "12 PEŞİNDE"}
               for x in result["changes"])
    evidence = json.loads((outdir / "kanit.json").read_text(encoding="utf-8"))
    ignored = {x["raw_text"] for x in evidence["ignored_metadata"]}
    assert "İZ PEŞİNDE" in ignored
    assert "IZ PESINDE" in ignored


def test_actor_roster_is_single_view_with_existing_and_new(tmp_path: Path):
    profile = setup_profile(tmp_path)
    _, result, outdir = run_episode(
        tmp_path, profile,
        "KENAN IŞIK\nSELİM KAYA\n",
        "KENEN ISIK\nSELIM KAYA\n",
        "KENAN IŞK\nSELİM KAYA\n",
    )
    assert result["durum"] == "DEGISIKLIK_VAR"
    assert len(result["changes"]) == 1
    assert result["changes"][0]["type"] == "NEW_MEMBER"

    public = json.loads((outdir / "degisiklikler.json").read_text(encoding="utf-8"))
    actors = {(x["name"], x["status"]) for x in public["actors"]}
    assert ("KENAN IŞIK", "MEVCUT") in actors
    assert any(name in {"SELİM KAYA", "SELIM KAYA"} and status == "YENİ"
               for name, status in actors)


def test_iz_pesinde_full_crew_roles_are_recognized(tmp_path: Path):
    profile = setup_iz_pesinde_profile(tmp_path)
    text = (
        "Yönetmen\nHÜSEYİN KARAKAŞ\nYapım\nPERTEV ATASAY\n"
        "Yönetmen Yrd.\nZEYNEP TOR\nAYŞEGÜL ŞANLI\nDİLEK YARAŞ\n"
        "Kamera Yrd.\nKEMAL ŞANLI\nMETİN BALEKOĞLU\n"
        "Işık Ekibi\nFERZAN YÜCEL\nERCAN AVCİ\nBAYCAN TEMEL\n"
        "Miks\nERKAN AKTAŞ\nNegatif Kurgu\nBÜLENT ÖZAYAN\nTAMER EŞKAZAN\nOKTAY HALİLOĞLU\n"
    )
    _, result, _ = run_episode(tmp_path, profile, text, text, series_id="iz-pesinde")
    assert result["durum"] == "DEGISIKLIK_YOK"
    assert result["changes"] == []


def test_prose_metadata_breaks_last_role_context(tmp_path: Path):
    profile = setup_iz_pesinde_profile(tmp_path)
    text = (
        "Laboratuvar işlemleri\nŞAFAK FILM\n"
        "laboratuvarlarında yapılmıştır.\n"
        "Bu filmin çekiminde\nher türlü yardımı yapan\nİÇİŞLERİ BAKANLIĞI'na\n"
        "No credit text is visible in the provided images.\n"
    )
    _, result, outdir = run_episode(tmp_path, profile, text, text, series_id="iz-pesinde")
    assert result["durum"] == "DEGISIKLIK_YOK"
    evidence = json.loads((outdir / "kanit.json").read_text(encoding="utf-8"))
    ignored = {x["raw_text"] for x in evidence["ignored_metadata"]}
    assert "laboratuvarlarında yapılmıştır." in ignored
    assert "Bu filmin çekiminde" in ignored
    assert "No credit text is visible in the provided images." in ignored


def test_stable_single_holder_split_vote_is_review_not_change(tmp_path: Path):
    profile = setup_iz_pesinde_profile(tmp_path)
    _, result, _ = run_episode(
        tmp_path, profile,
        "Kurgu\nNEVZAT DİŞİAÇIK\n",
        "Kurgu\nÍSMAİL KALKAN\n",
        "Kurgu\nNEVZAT DİŞİAÇIK\n",
        series_id="iz-pesinde",
    )
    assert result["durum"] == "DEGISIKLIK_YOK"
    assert not any(x["role"] == "KURGU" for x in result["changes"])
    conflict = next(x for x in result["review_candidates"]
                    if x.get("role") == "KURGU" and x.get("candidate") == "NEVZAT DİŞİAÇIK")
    assert conflict["reason"] == "KAYNAK_CELISKISI"
    assert conflict["known_names"] == ["İSMAİL KALKAN"]
    assert conflict["known_sources"] == ["nash"]
    assert conflict["candidate_sources"] == ["jordan", "lebron"]
