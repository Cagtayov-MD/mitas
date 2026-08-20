"""track_kunye GİRİŞ segmenti — spec:
docs/superpowers/specs/2026-08-12-nash-giris-aktivasyon-design.md §6 (6 madde).

1-4: _pipe_track_kunye.py --segment davranışı (gerçek yürütme, pilot_hat sahte).
5-6: mitas_pipeline.py giriş bloğu — 4000+ satırlık main() runtime'da koşturulamaz;
     emsal desen test_track_kunye_blok.py gibi kaynak-denetim testleri kullanılır.
"""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

BETIK = Path("/opt/mitas/scripts/_pipe_track_kunye.py")
PIPELINE_KAYNAK = Path("/opt/mitas/scripts/mitas_pipeline.py").read_text(encoding="utf-8")


def _modul_yukle():
    spec = importlib.util.spec_from_file_location("_pipe_track_kunye_giris_test", BETIK)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _sahte_pilot_hat(messi_satirlar, master_satirlar, band="green"):
    ph = types.ModuleType("pilot_hat")
    ph.havuz_derle_dizin = lambda d, desen="*.png": (
        sorted(Path(d).glob("*.png")), {"kare": 4, "sayfa": 2, "esik": 30,
                                        "grup": 2, "alarm": False, "ikinci_gecis_ek": 0})
    ph.oku_deepseek = lambda sayfalar, cagri_timeout=900: list(messi_satirlar)
    ph.oku_master = lambda png, out, bant_h=1100, bindirme=120, cagri_timeout=900: list(master_satirlar)
    ph.kb_yukle = lambda: {"neill archer", "john connell"}
    def ronaldo_kos(slug, out_dir, messi_dokum, master_dokum, kb, kb_tok,
                    kare_toplam, messi_kare, ibra_kare):
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "ronaldo_kunye.txt").write_text(
            "\n".join(messi_dokum + master_dokum) + "\n", encoding="utf-8")
        (out_dir / "ronaldo_fark.json").write_text("{}", encoding="utf-8")
        return {"film": slug, "confidence_band": band, "common_blind": False,
                "coverage_ratio": 0.5, "structural_anchor_missing": False,
                "birlesik_n": len(messi_dokum) + len(master_dokum)}
    ph.ronaldo_kos = ronaldo_kos
    return ph


def _klip_kur(tmp_path, kare_n=4, segment="cikis", master=True, master_status=None):
    clip = tmp_path / "DENEME FILM 1999-0001-1-0000-00-1"
    frames = clip / "frames" / segment
    frames.mkdir(parents=True)
    import numpy as np, cv2
    for i in range(kare_n):
        cv2.imwrite(str(frames / f"c_{i:04d}.png"),
                    np.full((60, 80), 40 + 30 * i, dtype=np.uint8))
    png_ad = "reading_master_runaware.png" if segment == "cikis" else "giris_reading_master_runaware.png"
    man_ad = ("reading_master_runaware_manifest.json" if segment == "cikis"
              else "giris_reading_master_runaware_manifest.json")
    if master:
        cv2.imwrite(str(clip / png_ad), np.full((200, 80), 128, dtype=np.uint8))
    if master_status is not None:
        (clip / man_ad).write_text(json.dumps({"status": master_status, "frames": 58}),
                                    encoding="utf-8")
    return clip, frames


def _kostur(m, clip, frames, monkeypatch, ph=None, ollama=True, argv_ek=()):
    monkeypatch.setattr(m, "ollama_saglik", lambda timeout=3: ollama)
    if ph is not None:
        monkeypatch.setitem(sys.modules, "pilot_hat", ph)
    monkeypatch.setattr(sys, "argv",
                        ["_pipe_track_kunye.py", "--clip", str(clip),
                         "--frames", str(frames), "--base", "DENEME FILM", *argv_ek])
    rc = m.main()
    assert rc == 0
    return rc


# ---- 1) --segment yoksa yollar bugünküyle aynı ----

def test_1_segment_yoksa_bugunku_yollar_aynı(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, frames = _klip_kur(tmp_path, segment="cikis")
    messi = ["Tamino - Neill Archer"] * 30
    ibra = ["Sarastro - John Connell"] * 20
    _kostur(m, clip, frames, monkeypatch, ph=_sahte_pilot_hat(messi, ibra))
    assert (clip / "track_kunye").is_dir()
    assert (clip / "DENEME FILM kunye3.txt").is_file()
    ozet = json.loads((clip / "track_kunye" / "manifest.json").read_text(encoding="utf-8"))
    assert ozet["segment"] == "cikis"


# ---- 2) --segment giris → track_kunye_giris/, kunye3_giris.txt, giris master seçilir ----

def test_2_segment_giris_ayri_dizin_ve_dosyalar(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, frames = _klip_kur(tmp_path, segment="giris")
    messi = ["Tamino - Neill Archer"] * 30
    ibra = ["Sarastro - John Connell"] * 20
    _kostur(m, clip, frames, monkeypatch, ph=_sahte_pilot_hat(messi, ibra),
            argv_ek=("--segment", "giris"))
    assert (clip / "track_kunye_giris").is_dir()
    assert not (clip / "track_kunye").exists()
    assert (clip / "DENEME FILM kunye3_giris.txt").is_file()
    assert not (clip / "DENEME FILM kunye3.txt").exists()
    ozet = json.loads((clip / "track_kunye_giris" / "manifest.json").read_text(encoding="utf-8"))
    assert ozet["segment"] == "giris"
    assert ozet["ibra_atlandi_sebep"] is None  # giriş master okunabildi


# ---- 3) master_secim(..., "giris") bayat manifest → (None, "master_bayat") ----

def test_3_giris_master_bayat_atlanir(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, _ = _klip_kur(tmp_path, segment="giris", master=True,
                        master_status="ibrahimovic_uretemedi")
    png, sebep = m.master_secim(clip, "giris")
    assert png is None and sebep == "master_bayat"


# ---- 4) Giriş master yoksa → (None, "master_yok"), kol çökmez ----

def test_4_giris_master_yok_kol_cokmez(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, frames = _klip_kur(tmp_path, segment="giris", master=False)
    png, sebep = m.master_secim(clip, "giris")
    assert png is None and sebep == "master_yok"
    messi = ["Tamino - Neill Archer"] * 30
    _kostur(m, clip, frames, monkeypatch, ph=_sahte_pilot_hat(messi, []),
            argv_ek=("--segment", "giris"))
    ozet = json.loads((clip / "track_kunye_giris" / "manifest.json").read_text(encoding="utf-8"))
    assert ozet["status"] == "done"
    assert ozet["ibra_atlandi_sebep"] == "master_yok"


# ---- 5) mitas_pipeline giriş bloğu: giris_frames boşken track_kunye_giris_skipped ----

def test_5_pipeline_giris_bloğu_var_ve_skip_olayı():
    assert "MITAS_TRACK_KUNYE_GIRIS" in PIPELINE_KAYNAK
    assert "track_kunye_giris_skipped" in PIPELINE_KAYNAK
    assert "track_kunye_giris_completed" in PIPELINE_KAYNAK
    assert "track_kunye_giris_failed" in PIPELINE_KAYNAK
    assert '"--segment", "giris"' in PIPELINE_KAYNAK
    assert 'timings["track_kunye_giris"]' in PIPELINE_KAYNAK
    assert 'summary_obj["track_kunye_giris"]' in PIPELINE_KAYNAK


# ---- 6) Giriş kolu exception atınca çıkış kolunun sonucu ve karar bozulmaz ----

def test_6_giris_bloğu_bağımsız_try_except_cikis_sonrasinda():
    cikis_i = PIPELINE_KAYNAK.index("TRACK-KUNYE GÖLGE")
    cikis_bitis = PIPELINE_KAYNAK.index("LEGACY GÖLGE VL")
    assert cikis_i < cikis_bitis
    cikis_parca = PIPELINE_KAYNAK[cikis_i:cikis_bitis]
    # giriş bloğu çıkış bloğunun İÇİNDE değil, ayrı ve SONRASINDA olmalı
    assert "track_kunye_giris" not in cikis_parca[:cikis_parca.index("except Exception")]
    giris_i = cikis_parca.find("track_kunye_giris")
    assert giris_i != -1
    giris_parca = cikis_parca[giris_i - 200:]
    assert "except Exception" in giris_parca
    assert "track_kunye_giris_failed" in giris_parca
