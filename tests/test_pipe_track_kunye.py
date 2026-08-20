"""_pipe_track_kunye: gölge blok betiği — GPU'suz, pilot_hat monkeypatch'li."""
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

BETIK = Path("/opt/mitas/scripts/_pipe_track_kunye.py")


def _modul_yukle():
    spec = importlib.util.spec_from_file_location("_pipe_track_kunye", BETIK)
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


def _klip_kur(tmp_path, kare_n=4, master=True, master_status=None):
    clip = tmp_path / "DENEME FILM 1999-0001-1-0000-00-1"
    frames = clip / "frames" / "cikis"
    frames.mkdir(parents=True)
    import numpy as np, cv2
    for i in range(kare_n):
        cv2.imwrite(str(frames / f"c_{i:04d}.png"),
                    np.full((60, 80), 40 + 30 * i, dtype=np.uint8))
    if master:
        cv2.imwrite(str(clip / "reading_master_runaware.png"),
                    np.full((200, 80), 128, dtype=np.uint8))
    if master_status is not None:
        (clip / "reading_master_runaware_manifest.json").write_text(
            json.dumps({"status": master_status, "frames": 58}), encoding="utf-8")
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
    return json.loads((clip / "track_kunye" / "manifest.json").read_text(encoding="utf-8"))


def test_ollama_down_skipped(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, frames = _klip_kur(tmp_path)
    ozet = _kostur(m, clip, frames, monkeypatch, ollama=False)
    assert ozet["status"] == "skipped" and ozet["reason"] == "ollama_down"


def test_frames_bos_skipped(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, frames = _klip_kur(tmp_path, kare_n=0)
    ozet = _kostur(m, clip, frames, monkeypatch,
                   ph=_sahte_pilot_hat(["A"], ["B"]))
    assert ozet["status"] == "skipped" and ozet["reason"] == "frames_bos"


def test_mutlu_yol_5_dosya_ve_kunye3(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, frames = _klip_kur(tmp_path, master=True, master_status=None)
    messi = ["Tamino - Neill Archer"] * 30   # sağlık dedektörü 200 karakteri geçsin
    ibra = ["Sarastro - John Connell"] * 20
    ozet = _kostur(m, clip, frames, monkeypatch, ph=_sahte_pilot_hat(messi, ibra))
    assert ozet["status"] == "done" and ozet["band"] == "green"
    tk = clip / "track_kunye"
    for ad in ("frame_dokum.txt", "master_dokum.txt", "ronaldo_kunye.txt",
               "ronaldo_fark.json", "manifest.json"):
        assert (tk / ad).stat().st_size > 0, ad
    k3 = clip / "DENEME FILM kunye3.txt"
    icerik = k3.read_text(encoding="utf-8")
    assert "MESSİ" in icerik and "İBRAHİMOVİC" in icerik and "RONALDO" in icerik
    assert "green" in icerik


def test_master_yok_ibra_bos_ama_devam(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, frames = _klip_kur(tmp_path, master=False)
    messi = ["Tamino - Neill Archer"] * 30
    ozet = _kostur(m, clip, frames, monkeypatch, ph=_sahte_pilot_hat(messi, []))
    assert ozet["status"] == "done"
    assert ozet["ibra_atlandi_sebep"] == "master_yok"
    assert (clip / "track_kunye" / "master_dokum.txt").read_text(encoding="utf-8").strip() == ""


def test_master_bayat_atlanir(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, _ = _klip_kur(tmp_path, master=True, master_status="ibrahimovic_uretemedi")
    png, sebep = m.master_secim(clip)
    assert png is None and sebep == "master_bayat"


def test_master_saglam_secilir(tmp_path, monkeypatch):
    m = _modul_yukle()
    clip, _ = _klip_kur(tmp_path, master=True, master_status="ok")
    png, sebep = m.master_secim(clip)
    assert png is not None and sebep is None
    assert m.master_kare_sayisi(clip) == 58


def test_ornekle_kronolojik_ve_raporlu():
    m = _modul_yukle()
    girdi = list(range(250))
    secim, dusen = m.ornekle(girdi, ust_sinir=100)
    assert 100 <= len(secim) <= 101 and dusen == 250 - len(secim)
    assert secim == sorted(secim)          # kronoloji korunur
    assert secim[0] == 0                   # baş düşmez
    assert secim[-1] == 249                # SON kare zorla dahil (© / SON kartı)
    kisa, d2 = m.ornekle([1, 2, 3], ust_sinir=100)
    assert kisa == [1, 2, 3] and d2 == 0


def test_ornekle_son_kare_sinir_vakasi():
    # Konsey bug-avı GLM-3: n=101, sınır=100 → düzgün-adım son indeksi (100)
    # hiç seçmiyordu; © kartı tam orada olur.
    m = _modul_yukle()
    secim, _ = m.ornekle(list(range(101)), ust_sinir=100)
    assert secim[-1] == 100


def test_env_int_bozuk_deger_cokertmez(monkeypatch):
    # Konsey bug-avı GLM-1/KIM-2: bozuk env betiği import'ta çökertmemeli.
    monkeypatch.setenv("MITAS_TRACK_KUNYE_MAX_FRAMES", "1k")
    monkeypatch.setenv("MITAS_TRACK_KUNYE_CAGRI_TIMEOUT", " 240 ")
    m = _modul_yukle()
    assert m.MAX_KARE == 100        # bozuk → varsayılan
    assert m.CAGRI_TIMEOUT == 240   # boşluklu → düzgün parse


def test_deepseek_saglik():
    m = _modul_yukle()
    assert m.deepseek_saglik([]) == (False, "bos_cikti")
    assert m.deepseek_saglik(["kisa"]) == (False, "cok_kisa")
    cop = ["@#!% ^^&* ()[]" * 30]
    assert m.deepseek_saglik(cop)[1] == "garble_yuksek"
    temiz = ["Directed by John Smith and produced by the whole team"] * 10
    assert m.deepseek_saglik(temiz) == (True, "ok")
