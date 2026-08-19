from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from sozlesme import SozlesmeHatasi, oku
from src.karar import reconcile
from src.kontrol import request_for
from src.hizalama import hizala
from src.roller import person_name, siniflandir


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image(path: Path) -> None:
    from PIL import Image
    Image.new("RGB", (100, 80), "white").save(path)


def packet(path: Path, producer: str, lines: list[tuple[str, str, int]], *, status: str = "OKUNDU",
           film_id: str = "F1", imdb: str | None = "tt1") -> dict:
    asset = path.parent / f"{producer}.png"
    image(asset)
    value = {"schema_version": "mitas.okuma/v1", "film": {"id": film_id, "external_ids": ({"imdb": imdb} if imdb else {})},
             "bolum": path.parent.name, "producer": {"id": producer, "engine_family": "test", "model_digest": "unit"},
             "durum": status, "assets": [{"asset_id": "asset", "path": str(asset), "sha256": digest(asset), "width": 100, "height": 80}],
             "lines": []}
    if status == "OKUNDU":
        value["lines"] = [{"line_id": lid, "text": text, "order": order,
                           "evidence": [{"asset_id": "asset", "bbox": {"x0": 10, "y0": 10, "x1": 80, "y1": 30}}]}
                          for lid, text, order in lines]
    path.write_text(json.dumps(value), encoding="utf-8")
    return value


class FakeProvider:
    version = "fake-v1"
    def __init__(self, values): self.values = values
    def candidates(self, external_ids, role): return self.values.get(role, [])


class ShaqTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_out = main.OUT
        main.OUT = self.root / "out"

    def tearDown(self):
        main.OUT = self.old_out
        self.temp.cleanup()

    def pair(self, a_lines, b_lines, *, part="cikis"):
        folder = self.root / "F1" / part; folder.mkdir(parents=True)
        a = packet(folder / "generic-one.okuma.json", "source-any-a", a_lines)
        b = packet(folder / "generic-two.okuma.json", "source-any-b", b_lines)
        return folder.parent, a, b

    def test_contract_bbox_bounds_and_hash(self):
        folder, a, _ = self.pair([("x", "A", 1)], [("x", "A", 1)])
        path = folder / "cikis" / "generic-one.okuma.json"
        bad = json.loads(path.read_text()); bad["lines"][0]["evidence"][0]["bbox"]["x1"] = 101
        path.write_text(json.dumps(bad))
        with self.assertRaises(SozlesmeHatasi): oku(path)
        path.write_text(json.dumps(a)); Path(a["assets"][0]["path"]).write_bytes(b"changed")
        with self.assertRaises(SozlesmeHatasi): oku(path)

    def test_unknown_light_chief_exact_consensus_passes_without_provider(self):
        folder, _, _ = self.pair([("x", "IŞIK ŞEFİ ZELİHA", 1)], [("y", "IŞIK ŞEFİ ZELİHA", 1)])
        out = main.tek(folder, "F1", "cikis")
        result = json.loads(out.read_text())
        self.assertEqual("GECTI", result["durum"])
        self.assertEqual("IKI_KANAL_TEYITLI", result["records"][0]["decision"])
        self.assertFalse((out.parent / "kontrol" / "istekler.jsonl").exists())

    def test_ahmat_ahmet_strong_film_cast_is_canonical(self):
        folder, _, _ = self.pair([("x", "CAST AHMAT GÜLDİKEN", 1)], [("y", "CAST AHMET GÜLDİKEN", 1)])
        db = self.root / "credits.json"; db.write_text(json.dumps({"tt1": {"CAST_KESIN": ["AHMET GÜLDİKEN"]}}))
        result = json.loads(main.tek(folder, "F1", "cikis", str(db)).read_text())
        self.assertEqual("GECTI", result["durum"])
        self.assertEqual("AHMET GÜLDİKEN", result["records"][0]["canonical_name"])
        self.assertEqual("CAST AHMET GÜLDİKEN", result["records"][0]["accepted_text"])

    def test_global_style_provider_cannot_canonicalize_unknown_role(self):
        folder, _, _ = self.pair([("x", "AHMAT GÜLDİKEN", 1)], [("y", "AHMET GÜLDİKEN", 1)])
        db = self.root / "credits.json"; db.write_text(json.dumps({"tt1": {"CAST_KESIN": ["AHMET GÜLDİKEN"]}}))
        result = json.loads(main.tek(folder, "F1", "cikis", str(db)).read_text())
        self.assertEqual("KONTROL_BEKLIYOR", result["durum"])
        self.assertIsNone(result["records"][0]["canonical_name"])

    def test_far_unpaired_not_zipped_without_two_anchors(self):
        folder, _, _ = self.pair([("a", "ALİ", 1)], [("b", "VELİ", 1)])
        result = json.loads(main.tek(folder, "F1", "cikis").read_text())
        self.assertEqual(2, len(result["records"]))
        self.assertEqual({"A_ONLY", "B_ONLY"}, {r["hizalama"] for r in result["records"]})

    def test_far_pair_only_inside_exact_anchors(self):
        folder, _, _ = self.pair([("a", "BAŞ", 1), ("x", "ALİ", 2), ("z", "SON", 3)],
                                  [("b", "BAŞ", 1), ("y", "VELİ", 2), ("q", "SON", 3)])
        result = json.loads(main.tek(folder, "F1", "cikis").read_text())
        self.assertIn("UZAK_ANCHOR", {r["hizalama"] for r in result["records"]})

    def test_blind_request_never_contains_candidate_text(self):
        req = request_for("F", "cikis", {"asset_id": "a", "bbox": {"x0": 1, "y0": 1, "x1": 2, "y1": 2}}, "CREW_KESIN")
        self.assertNotIn("AHMET", json.dumps(req))
        self.assertNotIn("text", req)

    def test_control_exact_answer_and_third_answer(self):
        folder, _, _ = self.pair([("x", "AHMAT GÜLDİKEN", 1)], [("y", "AHMET GÜLDİKEN", 1)])
        out = main.tek(folder, "F1", "cikis"); result = json.loads(out.read_text())
        ids = result["records"][0]["control_request_ids"]
        answers = self.root / "answers.jsonl"
        answers.write_text("".join(json.dumps({"request_id": x, "durum": "OKUNDU", "text": "AHMET GÜLDİKEN"}) + "\n" for x in ids))
        done = json.loads(main.tamamla("F1", "cikis", answers).read_text())
        self.assertEqual("GECTI", done["durum"])
        # Yalnız fuzzy/üçüncü metin çözüm değildir.
        out = main.tek(folder, "F1", "cikis"); ids = json.loads(out.read_text())["records"][0]["control_request_ids"]
        answers.write_text("".join(json.dumps({"request_id": x, "durum": "OKUNDU", "text": "AHMETT GÜLDİKEN"}) + "\n" for x in ids))
        self.assertEqual("COZUMSUZ", json.loads(main.tamamla("F1", "cikis", answers).read_text())["durum"])

    def test_partial_control_answers_persist_and_keep_queue(self):
        folder, _, _ = self.pair([("x", "AHMAT GÜLDİKEN", 1)], [("y", "AHMET GÜLDİKEN", 1)])
        out = main.tek(folder, "F1", "cikis"); result = json.loads(out.read_text()); ids = result["records"][0]["control_request_ids"]
        answers = self.root / "answers.jsonl"; answers.write_text(json.dumps({"request_id": ids[0], "durum": "OKUNDU", "text": "AHMET GÜLDİKEN"}) + "\n")
        partial = json.loads(main.tamamla("F1", "cikis", answers).read_text())
        self.assertEqual("KONTROL_BEKLIYOR", partial["durum"])
        self.assertIn(ids[0], partial["records"][0]["control_answers"])
        queue = [json.loads(x) for x in (out.parent / "kontrol" / "istekler.jsonl").read_text().splitlines()]
        self.assertEqual([ids[1]], [x["request_id"] for x in queue])
        answers.write_text(json.dumps({"request_id": ids[1], "durum": "OKUNDU", "text": "AHMET GÜLDİKEN"}) + "\n")
        self.assertEqual("GECTI", json.loads(main.tamamla("F1", "cikis", answers).read_text())["durum"])

    def test_ariza_distinct_from_unresolved_and_marker_last(self):
        folder, _, _ = self.pair([("x", "AHMAT GÜLDİKEN", 1)], [("y", "AHMET GÜLDİKEN", 1)])
        out = main.tek(folder, "F1", "cikis"); ids = json.loads(out.read_text())["records"][0]["control_request_ids"]
        answers = self.root / "answers.jsonl"; answers.write_text("\n".join(json.dumps({"request_id": x, "durum": "ARIZA"}) for x in ids))
        result = json.loads(main.tamamla("F1", "cikis", answers).read_text())
        self.assertEqual("ARIZA", result["durum"])
        self.assertTrue((out.parent / "_TAMAM").exists())

    def test_giris_cikis_isolated_and_source_untouched(self):
        exit_folder, a, _ = self.pair([("x", "A", 1)], [("y", "A", 1)], part="cikis")
        entry = self.root / "F1" / "giris"; entry.mkdir()
        packet(entry / "one.okuma.json", "first", [("x", "B", 1)])
        packet(entry / "two.okuma.json", "second", [("y", "B", 1)])
        source = Path(a["assets"][0]["path"]); before = digest(source)
        main.tek(exit_folder, "F1", "cikis"); main.tek(exit_folder, "F1", "giris")
        self.assertTrue((main.OUT / "F1" / "cikis" / "shaq.json").exists())
        self.assertTrue((main.OUT / "F1" / "giris" / "shaq.json").exists())
        self.assertEqual(before, digest(source))

    def test_unread_bbox_is_not_metin_yok(self):
        folder, a, b = self.pair([], [], part="cikis")
        for name, value in (("generic-one.okuma.json", a), ("generic-two.okuma.json", b)):
            value["durum"] = "METIN_YOK"
            value["unread_regions"] = [{"asset_id": "asset", "bbox": {"x0": 10, "y0": 10, "x1": 80, "y1": 30}}]
            (folder / "cikis" / name).write_text(json.dumps(value))
        result = json.loads(main.tek(folder, "F1", "cikis").read_text())
        self.assertEqual("KONTROL_BEKLIYOR", result["durum"])

    def test_same_producer_is_contract_ariza(self):
        folder, a, b = self.pair([("x", "A", 1)], [("y", "A", 1)])
        b["producer"]["id"] = a["producer"]["id"]
        (folder / "cikis" / "generic-two.okuma.json").write_text(json.dumps(b))
        result = json.loads(main.tek(folder, "F1", "cikis").read_text())
        self.assertEqual("ARIZA", result["durum"])

    def test_role_boundaries_conflict_and_auxiliary_directors(self):
        self.assertEqual("CREW_KESIN", siniflandir({"text": "ART DIRECTOR NUR", "role_hint": ""}))
        self.assertEqual("CREW_KESIN", siniflandir({"text": "CASTING DIRECTOR NUR", "role_hint": ""}))
        self.assertEqual("CREW_KESIN", siniflandir({"text": "YARDIMCI YÖNETMEN NUR", "role_hint": ""}))
        self.assertEqual("CREW_KESIN", siniflandir({"text": "MUSIC DIRECTOR NUR", "role_hint": ""}))
        self.assertEqual("ROL_BELIRSIZ", siniflandir({"text": "CAST AHMET", "role_hint": ""}, {"text": "DIRECTOR AHMET", "role_hint": ""}))
        self.assertEqual("ROL_BELIRSIZ", siniflandir({"text": "BROADCAST ENGINEER", "role_hint": ""}))

    def test_turkish_role_labels_and_name_extraction(self):
        director = {"text": "YÖNETMEN: NURİ BİLGE CEYLAN", "role_hint": ""}
        light = {"text": "IŞIK ŞEFİ ZELİHA", "role_hint": ""}
        self.assertEqual("YONETMEN_KESIN", siniflandir(director))
        self.assertEqual("NURİ BİLGE CEYLAN", person_name(director, "YONETMEN_KESIN"))
        self.assertEqual("CREW_KESIN", siniflandir(light))

    def test_near_alignment_is_monotonic_not_crossed(self):
        a = [{"line_id": "a1", "order": 1, "text": "AHMET YILMAZ"}, {"line_id": "a2", "order": 2, "text": "AHMET YILMAZ"}]
        b = [{"line_id": "b1", "order": 1, "text": "AHMET YILMAZZ"}, {"line_id": "b2", "order": 2, "text": "AHMET YILMAZ"}]
        pairs = hizala(a, b)
        pair_indices = [(x.a["order"], x.b["order"]) for x in pairs if x.a and x.b]
        self.assertEqual(sorted(pair_indices), pair_indices)

    def test_alignment_output_keeps_unmatched_before_later_match(self):
        a = [{"line_id": "a1", "order": 1, "text": "TEK KANAL SATIRI"},
             {"line_id": "a2", "order": 2, "text": "AHMET YILMAZ"}]
        b = [{"line_id": "b2", "order": 2, "text": "AHMET YILMAZZ"}]
        pairs = hizala(a, b)
        self.assertEqual(["A_ONLY", "YAKIN"], [x.sinif for x in pairs])

    def test_control_bare_name_selects_matching_visual_line(self):
        folder, _, _ = self.pair([("x", "CAST AHMAT GÜLDİKEN", 1)],
                                  [("y", "CAST AHMET GÜLDİKEN", 1)])
        out = main.tek(folder, "F1", "cikis")
        record = json.loads(out.read_text())["records"][0]
        answers = self.root / "bare-answers.jsonl"
        answers.write_text("".join(json.dumps({"request_id": request_id, "durum": "OKUNDU",
                                                 "text": "AHMET GÜLDİKEN"}) + "\n"
                                   for request_id in record["control_request_ids"]))
        done = json.loads(main.tamamla("F1", "cikis", answers).read_text())
        self.assertEqual("GECTI", done["durum"])
        self.assertEqual("CAST AHMET GÜLDİKEN", done["records"][0]["accepted_text"])

    def test_relative_asset_and_metadata_mismatch(self):
        folder, a, b = self.pair([("x", "A", 1)], [("y", "A", 1)])
        asset = Path(a["assets"][0]["path"])
        a["assets"][0]["path"] = asset.name
        one = folder / "cikis" / "generic-one.okuma.json"; one.write_text(json.dumps(a))
        self.assertEqual("GECTI", json.loads(main.tek(folder, "F1", "cikis").read_text())["durum"])
        b["film"]["external_ids"] = {"imdb": "tt-other"}
        (folder / "cikis" / "generic-two.okuma.json").write_text(json.dumps(b))
        self.assertEqual("ARIZA", json.loads(main.tek(folder, "F1", "cikis").read_text())["durum"])

    def test_provider_outage_is_neutral_and_evidence_is_scoped(self):
        class Broken:
            version = "broken"
            def candidates(self, external_ids, role): raise RuntimeError("offline")
        folder, a, b = self.pair([("x", "CAST AHMAT GÜLDİKEN", 1)], [("y", "CAST AHMET GÜLDİKEN", 1)])
        result = reconcile(a, b, provider=Broken())
        self.assertEqual("KONTROL_BEKLIYOR", result.durum)
        record = result.records[0]
        self.assertTrue(all("channel" in e and "line_id" in e for e in record["evidence"]))


if __name__ == "__main__":
    unittest.main()
