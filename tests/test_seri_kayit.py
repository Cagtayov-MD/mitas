# -*- coding: utf-8 -*-
"""seri_kayit testleri — dizi-modu seri deposu IO katmanı.

KISITLAR (dizi_SISTEM.md sözleşmesi):
- Depo kökü MITAS_SERILER_ROOT env ile yönlendirilir (tmp_path); gerçek sürücülere DOKUNULMAZ.
- kaydet/bolum_kaydet ATOMİK: aynı dizine .tmp + os.replace; artık .tmp dosyası kalmaz.
- kilitle / versiyon_atla / tanik_ekle SAF: girdi master mutasyona uğramaz.
"""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import seri_kayit as sk


@pytest.fixture
def depo(tmp_path, monkeypatch):
    # kök import-anında SABİTLENMEMELİ — env her testte tmp'ye yönlendirilir
    monkeypatch.setenv("MITAS_SERILER_ROOT", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------- seri_anahtar

def test_seri_anahtar_turkce_fold_upper_ve_hash_soneki():
    key = sk.seri_anahtar("BiZiM EViN HALLERi")
    # Türkçe-fold + upper + "_" + 8 hex sonek — sözleşme örneği birebir
    assert re.fullmatch(r"BIZIM_EVIN_HALLERI_[0-9a-f]{8}", key), key
    # sonek ham adın sha1'inden gelir
    beklenen = hashlib.sha1("BiZiM EViN HALLERi".encode("utf-8")).hexdigest()[:8]
    assert key.endswith("_" + beklenen)


def test_seri_anahtar_trt_id_temizlenir():
    key = sk.seri_anahtar("1900-0138-0-0009-00-1 BİZİM EVİN HALLERİ")
    # TRT_RE eşleşmesi addan silinir; bölüm parseli anahtara SIZMAZ
    assert key.startswith("BIZIM_EVIN_HALLERI_"), key
    assert "0009" not in key
    assert re.fullmatch(r"BIZIM_EVIN_HALLERI_[0-9a-f]{8}", key)


def test_seri_anahtar_windows_yasak_karakterler():
    key = sk.seri_anahtar('KURTLAR: "VADİ" <PUSU>/PART\\1?*|')
    # klasör adı olarak güvenli: gövde A-Z 0-9 _, sonek küçük 8-hex; "_" tekli
    assert re.fullmatch(r"[A-Z0-9_]+_[0-9a-f]{8}", key), key
    assert "__" not in key


def test_seri_anahtar_kirpma_80():
    ad = "ÇOK UZUN BİR DİZİ ADI " * 10  # 100+ karakter
    key = sk.seri_anahtar(ad)
    govde, _, sonek = key.rpartition("_")
    assert len(govde) <= 80
    assert re.fullmatch(r"[0-9a-f]{8}", sonek)


def test_seri_anahtar_deterministik():
    a = sk.seri_anahtar("BİZİM EVİN HALLERİ")
    b = sk.seri_anahtar("BİZİM EVİN HALLERİ")
    c = sk.seri_anahtar("BAŞKA BİR DİZİ")
    assert a == b
    assert a != c


# ------------------------------------------------------------- trt_seri_on_ek

def test_trt_seri_on_ek():
    assert sk.trt_seri_on_ek("1900-0138-0-0009-00-1") == "1900-0138-0"
    assert sk.trt_seri_on_ek("1900-0138-0-0014-00-1") == "1900-0138-0"
    assert sk.trt_seri_on_ek("boyle-bir-id-yok") is None
    assert sk.trt_seri_on_ek("") is None


# ------------------------------------------------------- kaydet/yukle atomik IO

def test_kaydet_atomik_ve_roundtrip_turkce(depo):
    anahtar = sk.seri_anahtar("BİZİM EVİN HALLERİ")
    m = sk.bos_master(anahtar, "BİZİM EVİN HALLERİ", r"D:\GELEN\BİZİM EVİN HALLERİ",
                      "2026-07-09T12:00:00")
    sk.kaydet(anahtar, m)

    d = sk.yol(anahtar)
    assert (d / "seri_master.json").exists()
    # atomik yazım artığı yok
    assert list(d.glob("*.tmp")) == []
    # dosya geçerli JSON + Türkçe karakterler kaçışsız (ensure_ascii=False)
    ham = (d / "seri_master.json").read_text(encoding="utf-8")
    json.loads(ham)
    assert "BİZİM EVİN HALLERİ" in ham
    # round-trip birebir
    assert sk.yukle(anahtar) == m


def test_yukle_yoksa_none(depo):
    assert sk.yukle("BOYLE_BIR_SERI_YOK_deadbeef") is None


def test_kaydet_olay_gecmis_jsonl_append(depo):
    anahtar = "TEST_SERI_00000000"
    m = sk.bos_master(anahtar, "TEST", "D:\\X", "2026-07-09T12:00:00")
    sk.kaydet(anahtar, m, olay={"olay": "kilit", "bolumler": [1, 2, 3],
                                "ts": "2026-07-09T12:00:00"})
    sk.kaydet(anahtar, m, olay={"olay": "terfi", "isim": "OKTAY DENER",
                                "ts": "2026-07-09T13:00:00"})
    g = sk.yol(anahtar) / "gecmis.jsonl"
    satirlar = g.read_text(encoding="utf-8").strip().splitlines()
    assert len(satirlar) == 2  # append-only: her olay bir satır
    assert json.loads(satirlar[0])["olay"] == "kilit"
    assert json.loads(satirlar[1])["isim"] == "OKTAY DENER"
    # olay verilmeyen kaydet günlüğe satır EKLEMEZ
    sk.kaydet(anahtar, m)
    assert len(g.read_text(encoding="utf-8").strip().splitlines()) == 2


# ------------------------------------------------------------------ bos_master

def test_bos_master_sema_iskeleti():
    m = sk.bos_master("BIZIM_EVIN_HALLERI_a3f81c2d", "BİZİM EVİN HALLERİ",
                      r"D:\GELEN\BİZİM EVİN HALLERİ", "2026-07-09T12:00:00")
    assert m["surum_sema"] == 1
    assert m["seri_anahtar"] == "BIZIM_EVIN_HALLERI_a3f81c2d"
    assert m["seri_adi"] == "BİZİM EVİN HALLERİ"
    assert m["kaynak_klasor"] == r"D:\GELEN\BİZİM EVİN HALLERİ"
    assert m["durum"] == "BUILDING"
    assert m["master_surum"] == 0
    assert m["trt_on_ekler"] == []
    assert m["kilit_bolumler"] == []
    assert m["surum_gecmisi"] == []
    for alan in ("alanlar", "oyuncular", "teknik_ekip", "aday_havuzu",
                 "konuk_gecmisi", "tanik_kayitlari"):
        assert m[alan] == {}, alan
    assert m["bekleyen_degisimler"] == []
    assert m["format_kopusu"] == {"ardisik": 0, "ilk_bolum": None}


# --------------------------------------------------------------------- kilitle

def test_kilitle_saf_ve_alanlar():
    m = sk.bos_master("K_00000000", "K", "D:\\K", "2026-07-09T12:00:00")
    orijinal = copy.deepcopy(m)
    kilitli = sk.kilitle(m, [1, 2, 3], "2026-07-09T12:30:00")
    assert m == orijinal  # SAF: girdi mutasyonsuz
    assert kilitli["durum"] == "LOCKED"
    assert kilitli["master_surum"] == 1
    assert kilitli["kilit_bolumler"] == [1, 2, 3]
    assert kilitli["surum_gecmisi"][-1] == {
        "surum": 1, "olay": "kilit", "bolumler": [1, 2, 3],
        "ts": "2026-07-09T12:30:00",
    }


# ------------------------------------------------------------- yeniden_tohumla

def _yeniden_tohum_fikstur():
    """LOCKED + dolu defterli + kopuş-sayaçlı master (yeniden_tohumla girdisi)."""
    m = sk.kilitle(sk.bos_master("K_00000000", "K", "D:\\K", "t0"), [1, 2, 3], "t1")
    m["alanlar"] = {"Yönetmen": {"kanonik": ["SAMET POLAT"], "guven": "KESIN"}}
    m["oyuncular"] = {"POLAT ALEMDAR": {"bolumler": [1, 2, 3], "sira": 0}}
    m["teknik_ekip"] = {"Müzik Yönetmeni": {"CAN ATİLLA": {"bolumler": [1, 2, 3]}}}
    m["aday_havuzu"] = {"ALTAN ALKAN": {"alan": "oyuncular", "bolumler": [2]}}
    m["konuk_gecmisi"] = {"OKTAY DENER": {"bolumler": [5, 9]}}
    m["tanik_kayitlari"] = {"1900-0138-0-0014-00-1": {"bolum_no": 14,
                                                      "content_hash": "aaa"}}
    m["format_kopusu"] = {"ardisik": 2, "ilk_bolum": 13}
    return m


def test_yeniden_tohumla_saf_ve_durum_gecisi():
    m = _yeniden_tohum_fikstur()
    orijinal = copy.deepcopy(m)
    y = sk.yeniden_tohumla(m, [15, 16, 17], "t2")
    assert m == orijinal  # SAF: girdi mutasyonsuz
    assert y["durum"] == "BUILDING"
    assert y["kilit_bolumler"] == []
    assert y["format_kopusu"] == {"ardisik": 0, "ilk_bolum": None}
    # sürüm atlaması YOK — sürümü yeniden koşan kilit (kilitle) basar
    assert y["master_surum"] == m["master_surum"]


def test_yeniden_tohumla_olay_kaydi():
    m = _yeniden_tohum_fikstur()
    y = sk.yeniden_tohumla(m, [15, 16, 17], "t2")
    assert y["surum_gecmisi"][-1] == {
        "olay": "yeniden_tohum", "eski_kilit": [1, 2, 3],
        "hedef_bolumler": [15, 16, 17], "ts": "t2",
    }
    # önceki günlük (kilit olayı) yerinde — append-only, silme yok
    assert y["surum_gecmisi"][0]["olay"] == "kilit"
    assert len(y["surum_gecmisi"]) == len(m["surum_gecmisi"]) + 1


def test_yeniden_tohumla_defterler_korunur_ve_kopya_bagimsiz():
    m = _yeniden_tohum_fikstur()
    y = sk.yeniden_tohumla(m, [15, 16, 17], "t2")
    # denetim-izi: tanıklık defterleri AYNEN korunur
    for alan in ("alanlar", "oyuncular", "teknik_ekip", "aday_havuzu",
                 "konuk_gecmisi", "tanik_kayitlari"):
        assert y[alan] == m[alan], alan
    # dönen kopya bağımsız: y defterini değiştirmek girdiyi ETKİLEMEZ
    y["oyuncular"]["YENİ KİŞİ"] = {"bolumler": [15]}
    assert "YENİ KİŞİ" not in m["oyuncular"]


# --------------------------------------------------------------- versiyon_atla

def test_versiyon_atla_saf_ve_alanlar():
    m = sk.kilitle(sk.bos_master("K_00000000", "K", "D:\\K", "t0"), [1, 2, 3], "t1")
    orijinal = copy.deepcopy(m)
    degisiklik = {"alan": "Yönetmen", "yeni": ["CEM DENIZ"]}
    v2 = sk.versiyon_atla(m, degisiklik, gecerli_bolum=14, simdi="t2")
    assert m == orijinal  # SAF
    assert degisiklik == {"alan": "Yönetmen", "yeni": ["CEM DENIZ"]}  # girdi dict de mutasyonsuz
    assert v2["master_surum"] == 2
    son = v2["surum_gecmisi"][-1]
    assert son["surum"] == 2
    assert son["olay"] == "kalici_degisim"
    assert son["gecerli_bolumden"] == 14
    assert son["alan"] == "Yönetmen"
    assert son["yeni"] == ["CEM DENIZ"]
    assert son["ts"] == "t2"


# ------------------------------------------------------------------ tanik_ekle

def test_tanik_ekle_uc_durum():
    m0 = sk.bos_master("K_00000000", "K", "D:\\K", "t0")
    orijinal = copy.deepcopy(m0)

    m1, durum1 = sk.tanik_ekle(m0, "1900-0138-0-0014-00-1", 14, "aaa111", "t1")
    assert durum1 == "YENI"
    assert m0 == orijinal  # SAF
    kayit = m1["tanik_kayitlari"]["1900-0138-0-0014-00-1"]
    assert kayit["bolum_no"] == 14
    assert kayit["content_hash"] == "aaa111"
    assert kayit["ts"] == "t1"

    # aynı id + aynı hash → AYNI (idempotent üzerine-yazma)
    m2, durum2 = sk.tanik_ekle(m1, "1900-0138-0-0014-00-1", 14, "aaa111", "t2")
    assert durum2 == "AYNI"
    assert m2["tanik_kayitlari"]["1900-0138-0-0014-00-1"]["content_hash"] == "aaa111"
    assert m2["tanik_kayitlari"]["1900-0138-0-0014-00-1"]["ts"] == "t2"

    # aynı id + FARKLI hash → DUPLICATE_CONFLICT; mevcut kayıt ezilmez
    m3, durum3 = sk.tanik_ekle(m1, "1900-0138-0-0014-00-1", 14, "bbb222", "t3")
    assert durum3 == "DUPLICATE_CONFLICT"
    assert m3["tanik_kayitlari"]["1900-0138-0-0014-00-1"]["content_hash"] == "aaa111"


# --------------------------------------------- bolum_kaydet / bolum_okumalari

def test_bolum_kaydet_idempotent_ve_sirali(depo):
    anahtar = "TEST_SERI_00000000"
    p14 = sk.bolum_kaydet(anahtar, 14, {"bolum_no": 14, "cast": ["OKTAY DENER"]})
    sk.bolum_kaydet(anahtar, 3, {"bolum_no": 3, "cast": ["AYŞE"]})
    # idempotent üzerine-yazma: aynı bölüm ikinci kez → tek dosya, yeni içerik
    p14b = sk.bolum_kaydet(anahtar, 14, {"bolum_no": 14, "cast": ["OKTAY DENER", "YENİ"]})
    assert p14 == p14b
    assert p14.name == "bolum_0014.json"

    bolum_dizin = sk.yol(anahtar) / "bolumler"
    assert sorted(f.name for f in bolum_dizin.glob("*.json")) == [
        "bolum_0003.json", "bolum_0014.json"]
    assert list(bolum_dizin.glob("*.tmp")) == []  # atomik yazım artığı yok

    okumalar = sk.bolum_okumalari(anahtar)
    assert [o["bolum_no"] for o in okumalar] == [3, 14]  # bolum_no sıralı
    assert okumalar[1]["cast"] == ["OKTAY DENER", "YENİ"]  # üzerine-yazılan içerik
    assert okumalar[0]["cast"] == ["AYŞE"]  # Türkçe round-trip


def test_bolum_okumalari_bos_seri(depo):
    assert sk.bolum_okumalari("HIC_YOK_00000000") == []
