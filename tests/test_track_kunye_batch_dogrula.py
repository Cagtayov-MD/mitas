"""batch doğrulayıcı: sentetik clip_dir + event dosyasıyla, GPU'suz."""
import importlib.util
import json
from pathlib import Path

BETIK = Path("/opt/mitas/scripts/track_kunye_batch_dogrula.py")


def _modul_yukle():
    spec = importlib.util.spec_from_file_location("tk_dogrula", BETIK)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _klip_kur(tmp_path, mid="1999-0001-1-0000-00-1", tam=True, band="green",
              status="done"):
    clip = tmp_path / f"DENEME FILM {mid}"
    (clip / "pdf").mkdir(parents=True)
    (clip / "pdf" / "kunye.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 11000 + b"\n%%EOF")
    tk = clip / "track_kunye"
    tk.mkdir()
    if tam:
        for ad in ("frame_dokum.txt", "master_dokum.txt", "ronaldo_kunye.txt"):
            (tk / ad).write_text("icerik\n", encoding="utf-8")
        (tk / "ronaldo_fark.json").write_text("{}", encoding="utf-8")
        (clip / "DENEME FILM kunye3.txt").write_text("# 3-KOLLU\n", encoding="utf-8")
    (tk / "manifest.json").write_text(json.dumps(
        {"status": status, "band": band, "film": clip.name}), encoding="utf-8")
    return clip


def _olaylar_yaz(tmp_path, mid, kinds):
    p = tmp_path / "system_events.jsonl"
    with p.open("a", encoding="utf-8") as f:
        for k in kinds:
            f.write(json.dumps({"kind": k, "media_id": mid, "ts": "t"}) + "\n")
    return p


TAM_OLAYLAR = ["credit_qc1_passed", "credit_validate_completed", "track_kunye_completed"]


def test_saglikli_klip_gecer(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path)
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1", TAM_OLAYLAR)
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is True, sonuc


def test_bos_dosya_kaliyor(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path)
    (clip / "track_kunye" / "ronaldo_kunye.txt").write_text("", encoding="utf-8")
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1", TAM_OLAYLAR)
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is False
    assert any("ronaldo_kunye" in e for e in sonuc["eksikler"])


def test_bozuk_pdf_kaliyor(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path)
    (clip / "pdf" / "kunye.pdf").write_bytes(b"PDF DEGIL")
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1", TAM_OLAYLAR)
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is False
    assert any("pdf" in e.lower() for e in sonuc["eksikler"])


def test_qc1_olayi_yoksa_ve_karar_dosyasi_yoksa_kaliyor(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path)
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1",
                      ["credit_validate_completed", "track_kunye_completed"])
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is False
    assert any("qc1" in e.lower() for e in sonuc["eksikler"])


def test_qc1_temiz_yol_karar_dosyasiyla_gecer(tmp_path):
    # ÜRETİM GERÇEĞİ (FAKİR ÖĞRENCİ smoke, 2026-07-30): credit_qc1_* event'i
    # YALNIZ RED tetiklenince yazılır; temiz geçişte hiç event yok. Kanıt =
    # karar.pipeline.json varlığı.
    m = _modul_yukle()
    clip = _klip_kur(tmp_path)
    (clip / "karar.pipeline.json").write_text('{"karar": "Hazır"}', encoding="utf-8")
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1",
                      ["credit_validate", "track_kunye_completed"])
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is True, sonuc
    assert "qc1_temiz_yol" in sonuc["uyari"]


def test_media_id_dosya_adi_turevinde_eslesir(tmp_path):
    # ÜRETİM GERÇEĞİ: event media_id'si çıplak TRT no değil, dosya-adı türevi
    # ('evoArcadmin_..._1995-0467-1-0000-00-1-FAK_R__RENC') — alt-dizgi eşleşmeli.
    m = _modul_yukle()
    clip = _klip_kur(tmp_path)
    ev = _olaylar_yaz(tmp_path,
                      "evoArcadmin_X_1999-0001-1-0000-00-1-FILM_ADI",
                      TAM_OLAYLAR)
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is True, sonuc


def test_skipped_gecerli_sebeple_uyarili_gecer(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path, tam=False, band=None, status="skipped")
    man = clip / "track_kunye" / "manifest.json"
    man.write_text(json.dumps({"status": "skipped", "reason": "frames_bos",
                               "film": clip.name}), encoding="utf-8")
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1",
                      ["credit_qc1_passed", "credit_validate_completed",
                       "track_kunye_skipped"])
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is True and sonuc["uyari"] == "skipped:frames_bos"


def test_band_null_sebepsiz_kaliyor(tmp_path):
    m = _modul_yukle()
    clip = _klip_kur(tmp_path, band=None, status="done")
    man = clip / "track_kunye" / "manifest.json"
    man.write_text(json.dumps({"status": "done", "band": None, "film": clip.name,
                               "ibra_atlandi_sebep": None, "common_blind": False}),
                   encoding="utf-8")
    ev = _olaylar_yaz(tmp_path, "1999-0001-1-0000-00-1", TAM_OLAYLAR)
    sonuc = m.klip_dogrula(clip, m.olaylari_yukle(ev))
    assert sonuc["gecti"] is False
    assert any("band" in e.lower() for e in sonuc["eksikler"])
