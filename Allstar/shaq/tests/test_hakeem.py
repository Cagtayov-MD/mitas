from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hakeem_main
import karsilastir
import main as shaq_main
from src.hakeem.kontrol import ANSWER_SCHEMA, KontrolHatasi
from src.hakeem.sozlesme import cift_oku


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_image(path: Path) -> None:
    from PIL import Image
    Image.new("RGB", (160, 100), "white").save(path)


def packet(path: Path, producer: str, model: str, lines: list[tuple], *,
           status: str = "OKUNDU", unread: bool = False,
           external_ids: dict | None = None) -> dict:
    image_path = path.parent / f"{producer}.png"
    make_image(image_path)
    assets = [{"asset_id": "asset", "path": str(image_path), "sha256": digest(image_path),
               "width": 160, "height": 100}]
    rows = []
    if status == "OKUNDU":
        for item in lines:
            line_id, text, order, *extras = item
            row = {"line_id": line_id, "text": text, "order": order,
                   "evidence": [{"asset_id": "asset", "bbox": {"x0": 10, "y0": 10,
                                                                   "x1": 120, "y1": 40}}]}
            if extras:
                row.update(extras[0])
            rows.append(row)
    value = {
        "schema_version": "mitas.okuma/v1",
        "film": {"id": path.parent.parent.name, "external_ids": external_ids or {"imdb": "tt1"}},
        "bolum": path.parent.name,
        "producer": {"id": producer, "engine_family": producer, "model_digest": model},
        "durum": status, "assets": assets, "lines": rows,
    }
    if unread:
        value["unread_regions"] = [{"asset_id": "asset", "bbox": {"x0": 10, "y0": 10,
                                                                       "x1": 120, "y1": 40}}]
    path.write_text(json.dumps(value), encoding="utf-8")
    return value


def section(root: Path, film_id: str, bolum: str, a_lines: list[tuple], b_lines: list[tuple],
            *, a_status: str = "OKUNDU", b_status: str = "OKUNDU",
            unread: bool = False, same_model: bool = False) -> Path:
    folder = root / film_id / bolum
    folder.mkdir(parents=True, exist_ok=True)
    packet(folder / "one.okuma.json", "reader-a", "model-a", a_lines,
           status=a_status, unread=unread)
    packet(folder / "two.okuma.json", "reader-b", "model-a" if same_model else "model-b", b_lines,
           status=b_status, unread=unread)
    return folder.parent


def answers_for(queue: Path, text: str, *, provider: str = "judge-a", suffix: str = "a") -> Path:
    output = queue.parent / f"answers-{suffix}.jsonl"
    values = []
    for index, raw in enumerate(queue.read_text(encoding="utf-8").splitlines()):
        request = json.loads(raw)
        values.append({
            "schema_version": ANSWER_SCHEMA,
            "answer_id": f"answer-{suffix}-{index}",
            "request_id": request["request_id"],
            "request_digest": request["request_digest"],
            "crop_sha256": request["crop_sha256"],
            "uretim_zamani": "2026-08-17T12:00:00+03:00",
            "durum": "OKUNDU", "text": text,
            "producer": {"id": provider, "engine_family": "test-vlm",
                         "model_digest": f"digest-{provider}", "prompt_digest": "prompt-v1",
                         "independence_group": provider},
        })
    output.write_text("".join(json.dumps(value) + "\n" for value in values), encoding="utf-8")
    return output


class HakeemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_hakeem_out = hakeem_main.OUT
        self.old_shaq_out = shaq_main.OUT
        hakeem_main.OUT = self.root / "hakeem-out"
        shaq_main.OUT = self.root / "shaq-out"

    def tearDown(self):
        hakeem_main.OUT = self.old_hakeem_out
        shaq_main.OUT = self.old_shaq_out
        self.temp.cleanup()

    def result(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_empty_okundu_is_ariza_not_gechti(self):
        film = section(self.root, "F1", "cikis", [], [])
        result = self.result(hakeem_main.tek(film, "F1", "cikis"))
        self.assertEqual("ARIZA", result["durum"])

    def test_ariza_plus_metin_yok_is_ariza_not_gechti(self):
        film = section(self.root, "F1", "cikis", [], [], a_status="ARIZA", b_status="METIN_YOK")
        self.assertEqual("ARIZA", self.result(hakeem_main.tek(film, "F1", "cikis"))["durum"])

    def test_same_model_is_not_independent_confirmation(self):
        film = section(self.root, "F1", "cikis", [("a", "AYNI", 1)], [("b", "AYNI", 1)], same_model=True)
        result = self.result(hakeem_main.tek(film, "F1", "cikis"))
        self.assertEqual("ARIZA", result["durum"])
        self.assertIn("bagimsiz degil", result["ariza"]["mesaj"])

    def test_unknown_crew_exact_independent_consensus_passes(self):
        film = section(self.root, "F1", "cikis",
                       [("a", "IŞIK ŞEFİ ZELİHA YILMAZ", 1)],
                       [("b", "IŞIK ŞEFİ ZELİHA YILMAZ", 1)])
        result = self.result(hakeem_main.tek(film, "F1", "cikis"))
        self.assertEqual("GECTI", result["durum"])
        self.assertEqual("IKI_BAGIMSIZ_KANAL_TEYITLI", result["groups"][0]["decision"])

    def test_status_cross_product_has_no_empty_false_pass(self):
        expected = {
            ("METIN_YOK", "METIN_YOK"): "METIN_YOK",
            ("ARIZA", "ARIZA"): "ARIZA",
            ("ARIZA", "METIN_YOK"): "ARIZA",
            ("METIN_YOK", "ARIZA"): "ARIZA",
        }
        for index, ((left, right), wanted) in enumerate(expected.items()):
            film_id = f"F{index}"
            film = section(self.root, film_id, "cikis", [], [], a_status=left, b_status=right)
            with self.subTest(left=left, right=right):
                self.assertEqual(wanted, self.result(hakeem_main.tek(film, film_id, "cikis"))["durum"])

    def test_far_without_anchor_is_one_conflict_group(self):
        film = section(self.root, "F1", "cikis", [("a", "AHMET KARADUR", 1)],
                       [("b", "MEHMET ABUZER", 1)])
        result = self.result(hakeem_main.tek(film, "F1", "cikis"))
        self.assertEqual("KONTROL_BEKLIYOR", result["durum"])
        self.assertEqual(1, len(result["groups"]))
        self.assertEqual("FAR_CONFLICT", result["groups"][0]["kind"])
        self.assertEqual(2, len(result["groups"][0]["hypotheses"]))

    def test_structural_conflict_cannot_accept_both_alternatives(self):
        film = section(self.root, "F1", "cikis",
                       [("a1", "ALFA KİŞİ", 1), ("a2", "BETA KİŞİ", 2)],
                       [("b1", "GAMA KİŞİ", 1), ("b2", "DELTA KİŞİ", 2)])
        path = hakeem_main.tek(film, "F1", "cikis")
        queue = path.parent / "kontrol" / "istekler.jsonl"
        values = []
        for index, raw in enumerate(queue.read_text().splitlines()):
            request = json.loads(raw)
            # Her crop kendi yerel OCR adayini tekrar ederse iki alternatif birden
            # desteklenmis olur; HAKEEM ikisini metne eklemek yerine cozumlemez.
            local = {"a1": "ALFA KİŞİ", "a2": "BETA KİŞİ",
                     "b1": "GAMA KİŞİ", "b2": "DELTA KİŞİ"}[request["line_id"]]
            values.append({"schema_version": ANSWER_SCHEMA, "answer_id": f"s-{index}",
                           "request_id": request["request_id"], "request_digest": request["request_digest"],
                           "crop_sha256": request["crop_sha256"],
                           "uretim_zamani": "2026-08-17T12:00:00+03:00",
                           "durum": "OKUNDU", "text": local,
                           "producer": {"id": "judge", "engine_family": "test-vlm",
                                        "model_digest": "judge-model", "prompt_digest": "prompt-v1",
                                        "independence_group": "judge-group"}})
        answer_path = self.root / "structural.jsonl"
        answer_path.write_text("".join(json.dumps(value) + "\n" for value in values))
        self.assertEqual("COZUMSUZ", self.result(hakeem_main.tamamla("F1", "cikis", answer_path))["durum"])

    def test_role_heading_context_enables_film_scoped_identity(self):
        film = section(self.root, "F1", "cikis",
                       [("h1", "YÖNETMEN", 1), ("a", "NURİ BİLGA CEYLAN", 2)],
                       [("h2", "YÖNETMEN", 1), ("b", "NURİ BİLGE CEYLAN", 2)])
        db = self.root / "db.json"
        db.write_text(json.dumps({"imdb:tt1": {"YONETMEN_KESIN": ["NURİ BİLGE CEYLAN"]}}))
        result = self.result(hakeem_main.tek(film, "F1", "cikis", str(db)))
        self.assertEqual("GECTI", result["durum"])
        near = next(group for group in result["groups"] if group["kind"] == "NEAR_CONFLICT")
        self.assertEqual("FILM_KAPSAMLI_KIMLIK_TEYITLI", near["decision"])
        self.assertEqual("YONETMEN_KESIN", near["role"])

    def test_request_ids_are_deterministic_across_force_run(self):
        film = section(self.root, "F1", "cikis", [("a", "AHMAT GÜLDİKEN", 1)],
                       [("b", "AHMET GÜLDİKEN", 1)])
        first = self.result(hakeem_main.tek(film, "F1", "cikis"))
        second = self.result(hakeem_main.tek(film, "F1", "cikis", force=True))
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["groups"][0]["control_request_ids"],
                         second["groups"][0]["control_request_ids"])

    def test_provider_snapshot_is_part_of_run_identity(self):
        film = section(self.root, "F1", "cikis",
                       [("h1", "YÖNETMEN", 1), ("a", "NURİ BİLGA CEYLAN", 2)],
                       [("h2", "YÖNETMEN", 1), ("b", "NURİ BİLGE CEYLAN", 2)])
        first = self.result(hakeem_main.tek(film, "F1", "cikis"))
        db = self.root / "db.json"
        db.write_text(json.dumps({"imdb:tt1": {"YONETMEN_KESIN": ["NURİ BİLGE CEYLAN"]}}))
        second = self.result(hakeem_main.tek(film, "F1", "cikis", str(db)))
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual("GECTI", second["durum"])

    def test_control_request_is_blind_but_provenance_complete(self):
        film = section(self.root, "F1", "cikis", [("a", "AHMAT GÜLDİKEN", 1)],
                       [("b", "AHMET GÜLDİKEN", 1)])
        path = hakeem_main.tek(film, "F1", "cikis")
        raw = (path.parent / "kontrol" / "istekler.jsonl").read_text()
        request = json.loads(raw.splitlines()[0])
        self.assertNotIn("AHMAT", raw)
        self.assertNotIn("AHMET", raw)
        for field in ("channel", "producer_id", "line_id", "asset_sha256", "bbox",
                      "request_digest", "crop_sha256", "run_id", "group_id"):
            self.assertIn(field, request)

    def test_known_candidate_control_selects_one_hypothesis(self):
        film = section(self.root, "F1", "cikis", [("a", "AHMAT GÜLDİKEN", 1)],
                       [("b", "AHMET GÜLDİKEN", 1)])
        path = hakeem_main.tek(film, "F1", "cikis")
        answer_path = answers_for(path.parent / "kontrol" / "istekler.jsonl", "AHMET GÜLDİKEN")
        done = self.result(hakeem_main.tamamla("F1", "cikis", answer_path))
        self.assertEqual("GECTI", done["durum"])
        self.assertEqual(["AHMET GÜLDİKEN"], done["groups"][0]["accepted_lines"])

    def test_control_third_text_is_unresolved(self):
        film = section(self.root, "F1", "cikis", [("a", "AHMAT GÜLDİKEN", 1)],
                       [("b", "AHMET GÜLDİKEN", 1)])
        path = hakeem_main.tek(film, "F1", "cikis")
        answer_path = answers_for(path.parent / "kontrol" / "istekler.jsonl", "HASAN GÜLDİKEN")
        done = self.result(hakeem_main.tamamla("F1", "cikis", answer_path))
        self.assertEqual("COZUMSUZ", done["durum"])

    def test_tampered_request_digest_is_rejected_without_destroying_marker(self):
        film = section(self.root, "F1", "cikis", [("a", "AHMAT GÜLDİKEN", 1)],
                       [("b", "AHMET GÜLDİKEN", 1)])
        path = hakeem_main.tek(film, "F1", "cikis")
        answer_path = answers_for(path.parent / "kontrol" / "istekler.jsonl", "AHMET GÜLDİKEN")
        values = [json.loads(line) for line in answer_path.read_text().splitlines()]
        values[0]["request_digest"] = "tampered"
        answer_path.write_text("".join(json.dumps(value) + "\n" for value in values))
        with self.assertRaises(KontrolHatasi):
            hakeem_main.tamamla("F1", "cikis", answer_path)
        self.assertTrue((path.parent / "_TAMAM").exists())

    def test_control_model_must_be_independent_from_source_models(self):
        film = section(self.root, "F1", "cikis", [("a", "AHMAT GÜLDİKEN", 1)],
                       [("b", "AHMET GÜLDİKEN", 1)])
        path = hakeem_main.tek(film, "F1", "cikis")
        answer_path = answers_for(path.parent / "kontrol" / "istekler.jsonl", "AHMET GÜLDİKEN")
        values = [json.loads(line) for line in answer_path.read_text().splitlines()]
        values[0]["producer"]["model_digest"] = "model-a"
        answer_path.write_text("".join(json.dumps(value) + "\n" for value in values))
        with self.assertRaises(KontrolHatasi):
            hakeem_main.tamamla("F1", "cikis", answer_path)

    def test_unread_novel_text_requires_two_independent_judges(self):
        film = section(self.root, "F1", "cikis", [], [], a_status="METIN_YOK",
                       b_status="METIN_YOK", unread=True)
        path = hakeem_main.tek(film, "F1", "cikis")
        queue = path.parent / "kontrol" / "istekler.jsonl"
        first = answers_for(queue, "ZELİHA YILMAZ", provider="judge-a", suffix="one")
        partial = self.result(hakeem_main.tamamla("F1", "cikis", first))
        self.assertEqual("KONTROL_BEKLIYOR", partial["durum"])
        second = answers_for(queue, "ZELİHA YILMAZ", provider="judge-b", suffix="two")
        done = self.result(hakeem_main.tamamla("F1", "cikis", second))
        self.assertEqual("GECTI", done["durum"])
        self.assertEqual("KONTROL_YENI_IKI_KANAL_TEYITLI", done["groups"][0]["decision"])

    def test_unread_same_control_model_cannot_fake_two_independent_votes(self):
        film = section(self.root, "F1", "cikis", [], [], a_status="METIN_YOK",
                       b_status="METIN_YOK", unread=True)
        path = hakeem_main.tek(film, "F1", "cikis")
        queue = path.parent / "kontrol" / "istekler.jsonl"
        first = answers_for(queue, "ZELİHA YILMAZ", provider="judge-a", suffix="one")
        hakeem_main.tamamla("F1", "cikis", first)
        second = answers_for(queue, "ZELİHA YILMAZ", provider="judge-b", suffix="two")
        values = [json.loads(line) for line in second.read_text().splitlines()]
        for value in values:
            value["producer"]["model_digest"] = "digest-judge-a"
        second.write_text("".join(json.dumps(value) + "\n" for value in values))
        pending = self.result(hakeem_main.tamamla("F1", "cikis", second))
        self.assertEqual("KONTROL_BEKLIYOR", pending["durum"])

    def test_multiple_unread_regions_are_separate_decision_groups(self):
        film = section(self.root, "F1", "cikis", [], [], a_status="METIN_YOK",
                       b_status="METIN_YOK", unread=True)
        for name in ("one.okuma.json", "two.okuma.json"):
            path = film / "cikis" / name
            value = json.loads(path.read_text())
            value["unread_regions"].append({"asset_id": "asset",
                                             "bbox": {"x0": 10, "y0": 50, "x1": 120, "y1": 80}})
            path.write_text(json.dumps(value))
        result = self.result(hakeem_main.tek(film, "F1", "cikis"))
        self.assertEqual(["UNREAD", "UNREAD"], [group["kind"] for group in result["groups"]])
        self.assertEqual([2, 2], [len(group["control_request_ids"]) for group in result["groups"]])

    def test_all_evidence_boxes_become_control_views(self):
        film = section(self.root, "F1", "cikis", [("a", "AHMAT GÜLDİKEN", 1)],
                       [("b", "AHMET GÜLDİKEN", 1)])
        path = film / "cikis" / "one.okuma.json"
        value = json.loads(path.read_text())
        value["lines"][0]["evidence"].append({"asset_id": "asset",
                                               "bbox": {"x0": 20, "y0": 45, "x1": 130, "y1": 70}})
        path.write_text(json.dumps(value))
        result = self.result(hakeem_main.tek(film, "F1", "cikis"))
        self.assertEqual(3, len(result["groups"][0]["control_request_ids"]))

    def test_duplicate_order_is_contract_ariza(self):
        film = section(self.root, "F1", "cikis", [("a", "BİR", 1), ("b", "İKİ", 1)],
                       [("x", "BİR", 1), ("y", "İKİ", 2)])
        self.assertEqual("ARIZA", self.result(hakeem_main.tek(film, "F1", "cikis"))["durum"])

    def test_four_packet_film_gate_blocks_missing_section(self):
        film = section(self.root, "F1", "cikis", [("a", "AYNI METİN", 1)],
                       [("b", "AYNI METİN", 1)])
        manifest = self.result(hakeem_main.film(film, "F1"))
        self.assertFalse(manifest["qc1_ready"])
        self.assertEqual("ARIZA", manifest["sections"]["giris"]["durum"])

    def test_four_packet_film_gate_passes_two_sections(self):
        film = section(self.root, "F1", "giris", [("a", "GİRİŞ METNİ", 1)],
                       [("b", "GİRİŞ METNİ", 1)])
        section(self.root, "F1", "cikis", [("a", "ÇIKIŞ METNİ", 1)],
                [("b", "ÇIKIŞ METNİ", 1)])
        manifest = self.result(hakeem_main.film(film, "F1"))
        self.assertTrue(manifest["qc1_ready"])

    def test_control_completion_refreshes_film_gate(self):
        film = section(self.root, "F1", "giris", [("a", "GİRİŞ METNİ", 1)],
                       [("b", "GİRİŞ METNİ", 1)])
        section(self.root, "F1", "cikis", [("a", "AHMAT GÜLDİKEN", 1)],
                [("b", "AHMET GÜLDİKEN", 1)])
        manifest = self.result(hakeem_main.film(film, "F1"))
        self.assertFalse(manifest["qc1_ready"])
        queue = hakeem_main.OUT / "F1" / "cikis" / "kontrol" / "istekler.jsonl"
        answer_path = answers_for(queue, "AHMET GÜLDİKEN")
        hakeem_main.tamamla("F1", "cikis", answer_path)
        refreshed = self.result(hakeem_main.OUT / "F1" / "manifest.json")
        self.assertTrue(refreshed["qc1_ready"])

    def test_rerun_without_force_keeps_pending_control_state(self):
        film = section(self.root, "F1", "cikis", [("a", "AHMAT GÜLDİKEN", 1)],
                       [("b", "AHMET GÜLDİKEN", 1)])
        path = hakeem_main.tek(film, "F1", "cikis")
        before = path.read_bytes()
        hakeem_main.tek(film, "F1", "cikis")
        self.assertEqual(before, path.read_bytes())

    def test_comparison_without_gt_refuses_to_name_winner(self):
        film = section(self.root, "F1", "giris", [("a", "GİRİŞ METNİ", 1)],
                       [("b", "GİRİŞ METNİ", 1)])
        section(self.root, "F1", "cikis", [("a", "ÇIKIŞ METNİ", 1)],
                [("b", "ÇIKIŞ METNİ", 1)])
        karsilastir.calistir(self.root, limit=1)
        report = karsilastir.rapor([film.name])
        self.assertEqual("GT_YOK_KAZANAN_BELIRLENEMEZ", report["kazanan"])

    def test_comparison_with_gt_scores_both_engines(self):
        film = section(self.root, "F1", "giris", [("a", "GİRİŞ METNİ", 1)],
                       [("b", "GİRİŞ METNİ", 1)])
        section(self.root, "F1", "cikis", [("a", "ÇIKIŞ METNİ", 1)],
                [("b", "ÇIKIŞ METNİ", 1)])
        karsilastir.calistir(self.root, limit=1)
        gt = self.root / "gt.json"
        gt.write_text(json.dumps({"schema_version": "mitas.shaq.gt/v1", "items": [
            {"film_id": "F1", "bolum": "giris", "durum": "GECTI", "lines": ["GİRİŞ METNİ"]},
            {"film_id": "F1", "bolum": "cikis", "durum": "GECTI", "lines": ["ÇIKIŞ METNİ"]},
        ]}))
        report = karsilastir.rapor([film.name], gt_path=gt)
        self.assertEqual("ESIT", report["kazanan"])
        self.assertEqual(2, report["ozet"]["hakeem"]["kalite"]["dogru"])

    def test_comparison_does_not_name_winner_while_control_is_pending(self):
        film = section(self.root, "F1", "giris", [("a", "GİRİŞ METNİ", 1)],
                       [("b", "GİRİŞ METNİ", 1)])
        section(self.root, "F1", "cikis", [("a", "AHMAT GÜLDİKEN", 1)],
                [("b", "AHMET GÜLDİKEN", 1)])
        karsilastir.calistir(self.root, limit=1)
        gt = self.root / "gt.json"
        gt.write_text(json.dumps({"schema_version": "mitas.shaq.gt/v1", "items": [
            {"film_id": "F1", "bolum": "giris", "durum": "GECTI", "lines": ["GİRİŞ METNİ"]},
            {"film_id": "F1", "bolum": "cikis", "durum": "GECTI", "lines": ["AHMET GÜLDİKEN"]},
        ]}))
        report = karsilastir.rapor([film.name], gt_path=gt)
        self.assertEqual("KONTROL_BEKLIYOR_KAZANAN_BELIRLENEMEZ", report["kazanan"])

    def test_channel_assignment_uses_producer_not_filename(self):
        film = section(self.root, "F1", "cikis", [("a", "A METNİ", 1)], [("b", "B METNİ", 1)])
        pair = cift_oku(film, "F1", "cikis")
        self.assertEqual(["reader-a", "reader-b"], [channel.paket.producer_id for channel in pair.kanallar])

    def test_path_traversal_film_id_is_rejected(self):
        with self.assertRaises(ValueError):
            hakeem_main.tek(self.root, "../outside", "cikis")


if __name__ == "__main__":
    unittest.main()
