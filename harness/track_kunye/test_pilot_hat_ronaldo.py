import json
import numpy as np
import cv2
import pilot_hat as ph


def test_oku_master_bantlara_boler(tmp_path, monkeypatch):
    # 3000px yüksek sahte master → bant_h=1100/bindirme=120 ile 3 bant beklenir
    img = np.zeros((3000, 640, 3), dtype=np.uint8)
    p = tmp_path / "reading_master.png"
    cv2.imwrite(str(p), img)
    gorulen = []
    monkeypatch.setattr(ph, "oku_deepseek", lambda sayfalar, cagri_timeout=900: gorulen.extend(sayfalar) or ["SATIR"])
    satirlar = ph.oku_master(p, tmp_path)
    assert len(gorulen) == 3
    assert satirlar == ["SATIR"]


def test_ronaldo_kos_dosyalari_yazar(tmp_path):
    r = ph.ronaldo_kos("test-film", tmp_path,
                       messi_dokum=["Tamino - Neill Archer"],
                       master_dokum=["Sarastro - John Connell"],
                       kb=set(), kb_tok={"neill", "archer", "john", "connell", "tamino", "sarastro"},
                       kare_toplam=100, messi_kare=40, ibra_kare=50)
    assert (tmp_path / "ronaldo_kunye.txt").is_file()
    fark = json.loads((tmp_path / "ronaldo_fark.json").read_text(encoding="utf-8"))
    assert "confidence_band" in r and "eslesen_n" in fark
