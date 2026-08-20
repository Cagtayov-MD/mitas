"""Koşu akışı — istisna sızmaz, _TAMAM en son, master okumadan bağımsız yazılır."""
import json

import main
import sahte
from sozlesme import Girdi


def _kur(monkeypatch, tmp_path, *, kanvas=True, manifest=None, satirlar=None,
         oku_hatasi=None, cokmus_mu=False, n=30):
    d = sahte.kare_dizini_kur(tmp_path, n=n)
    der = sahte.sahte_derleyici(cokmus_mu=cokmus_mu)
    k = sahte.SahteKanvas() if kanvas else None
    m = manifest if manifest is not None else sahte.manifest_ok(kare=n)
    monkeypatch.setattr(main, "_derle", lambda dizin, fid: (der, (k, m)))

    def _oku(yol, bolum, film_id, ayar):
        if oku_hatasi:
            raise oku_hatasi
        return {"satirlar": satirlar if satirlar is not None else ["YÖNETMEN: X"],
                "elenen": [], "bant_n": 3, "hata_n": 0, "elenen_n": 0,
                "kutu_durum": "tam", "bant_y0": [0, 980, 1960]}
    monkeypatch.setattr(main, "_oku", _oku)
    return d


def test_okundu_tam_akis(monkeypatch, tmp_path):
    d = _kur(monkeypatch, tmp_path)
    kok = tmp_path / "out"
    c = main.tek(Girdi(film_id="F", kareler=str(d)), kok)

    assert c.durum == "OKUNDU"
    assert c.satirlar == ["YÖNETMEN: X"]
    hedef = kok / "F" / "cikis"
    assert (hedef / "master.png").is_file()
    assert (hedef / "lebron.txt").is_file()
    assert (hedef / "_TAMAM").is_file()
    assert c.uretilen[0]["tip"] == "master"
    assert c.uretilen[0]["boy"] == 8000
    assert c.motor_surumu.startswith("lebron@")


def test_okuma_coktu_ama_master_YAZILDI(monkeypatch, tmp_path):
    """Spec 3.2: derlemeye harcanan iş çöpe gitmez, arıza hangi tarafta belli olur."""
    d = _kur(monkeypatch, tmp_path, oku_hatasi=RuntimeError("model yok"))
    kok = tmp_path / "out"
    c = main.tek(Girdi(film_id="F", kareler=str(d)), kok)

    assert c.durum == "ARIZA"
    assert c.sinif == "OKUYUCU"
    assert (kok / "F" / "cikis" / "master.png").is_file(), "master silinmis"
    assert c.uretilen and c.uretilen[0]["tip"] == "master"
    assert not (kok / "F" / "cikis" / "lebron.txt").exists()


def test_bos_satir_metin_yok(monkeypatch, tmp_path):
    d = _kur(monkeypatch, tmp_path, satirlar=[])
    kok = tmp_path / "out"
    c = main.tek(Girdi(film_id="F", kareler=str(d)), kok)
    assert c.durum == "METIN_YOK"
    assert (kok / "F" / "cikis" / "master.png").is_file()


def test_derleyici_istisnasi_sizmaz(monkeypatch, tmp_path):
    d = sahte.kare_dizini_kur(tmp_path)

    def _patla(dizin, fid):
        raise RuntimeError("paddle coktu")
    monkeypatch.setattr(main, "_derle", _patla)
    c = main.tek(Girdi(film_id="F", kareler=str(d)), tmp_path / "out")
    assert c.durum == "ARIZA" and c.sinif == "MOTOR"
    assert "paddle coktu" in c.mesaj


def test_iki_bolum_ayri_rafa_yazar(monkeypatch, tmp_path):
    d = _kur(monkeypatch, tmp_path)
    kok = tmp_path / "out"
    main.tek(Girdi(film_id="F", kareler=str(d), bolum="giris"), kok)
    main.tek(Girdi(film_id="F", kareler=str(d), bolum="cikis"), kok)
    assert (kok / "F" / "giris" / "master.png").is_file()
    assert (kok / "F" / "cikis" / "master.png").is_file()


def test_toplu_tamam_olani_atlar(monkeypatch, tmp_path, capsys):
    """İkinci koşu kaldığı yerden devam eder — _TAMAM olanı yeniden işlemez."""
    kaynak = tmp_path / "kaynak"
    for ad in ("FILM_A", "FILM_B"):
        d = kaynak / ad
        d.mkdir(parents=True)
        for i in range(1, 26):
            (d / f"c_{i:05d}.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    _kur(monkeypatch, tmp_path)
    kok = tmp_path / "out"
    main.toplu(kaynak, kok)
    ilk = capsys.readouterr().out
    assert "[atla]" not in ilk

    main.toplu(kaynak, kok)
    ikinci = capsys.readouterr().out
    assert ikinci.count("[atla]") == 2, ikinci


def test_json_sema(monkeypatch, tmp_path):
    d = _kur(monkeypatch, tmp_path)
    kok = tmp_path / "out"
    main.tek(Girdi(film_id="F", kareler=str(d)), kok)
    j = json.loads((kok / "F" / "cikis" / "lebron.json").read_text(encoding="utf-8"))
    for alan in ("film_id", "bolum", "durum", "satirlar", "uretilen", "kanit",
                 "motor_surumu", "uretim_zamani", "sure_sn"):
        assert alan in j, f"{alan} eksik"
    assert j["kanit"]["kare_bulunan"] == 30
