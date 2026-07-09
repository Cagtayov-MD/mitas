# -*- coding: utf-8 -*-
"""test_dizi_isle.py — dizi orkestratör CLI (scripts/dizi_isle.py) testleri.

KISITLAR (dizi_SISTEM.md test kuralları):
- Depo MITAS_SERILER_ROOT env + tmp_path ile yönlendirilir; X:/Y: sürücüleri + ağ + ollama YOK.
- pipeline_kos MOCK (gerçek mitas_pipeline subprocess'i ASLA koşulmaz); sahte videolar tmp
  klasörde TRT kalıbında adlarla üretilir.
- Bütünleşme derinliği: seri_kayit + seri_konsensus GERÇEK; dizi_credit_parse.okuma_topla ve
  seri_bolum_kunye akışı dikiş (_okuma_topla / _bolum_kunye_akisi) üzerinden monkeypatch.
- hub_yolu ve _export_kokleri dikişleri tmp'ye yönlendirilir (Database/ ve Mitas Output/
  gerçek kökleri test ortamında OKUNMAZ/YAZILMAZ).

Çalıştır:  python -m pytest tests/test_dizi_isle.py -x -q
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dizi_isle as di
import seri_kayit as sk

DIZI_AD = "BİZİM EVİN HALLERİ"


def _vid(klasor, bolum_no, icerik=b"video", onek="web_client_CAG1_", tip="0"):
    """TRT kalıbında sahte bölüm videosu: <önek>1900-0138-<tip>-<bölüm>-00-1 <AD>.mp4"""
    p = klasor / f"{onek}1900-0138-{tip}-{bolum_no:04d}-00-1 {DIZI_AD}.mp4"
    p.write_bytes(icerik)
    return p


def _okuma(bolum_no, trt=None, kaynak="master_dilim", cast=None, crew=None, vl=None):
    """BolumOkuma asgari örneği (dizi_credit_parse.okuma_topla sözleşmesi)."""
    return {"bolum_no": bolum_no,
            "trt_id": trt or f"1900-0138-0-{bolum_no:04d}-00-1",
            "cast": ["POLAT ALEMDAR", "AYŞE YILDIZ", "MEMATİ BAŞ"] if cast is None else cast,
            "crew": {"Yönetmen": ["SAMET POLAT"]} if crew is None else crew,
            "konuk_acik": [],
            "kb_hatti": {"yonetmen": [], "yapimci": [], "cast": []},
            "vl": vl or {"yonetmen": [], "oyuncular": [], "diger_roller": []},
            "stop_kart_bolum_no": None, "kaynak": kaynak, "uyarilar": []}


def okuma_fabrika(spec=None):
    """_okuma_topla dikişi sahtesi: bolum_no → kwargs; çağrı sırası .calls'ta."""
    spec = spec or {}
    calls = []

    def _f(hub, bolum_no, trt_id=None):
        calls.append(bolum_no)
        return _okuma(bolum_no, trt=trt_id, **spec.get(bolum_no, {}))

    _f.calls = calls
    return _f


class Kos:
    """pipeline_kos sahtesi — çağrılan dosya adlarını kaydeder, rc döner (subprocess YOK)."""

    def __init__(self, rc=0):
        self.calls = []
        self.rc = rc

    def __call__(self, video, python_exe=None):
        self.calls.append(Path(video).name)
        return self.rc


class Akis:
    """_bolum_kunye_akisi sahtesi — (bolum_no, sadece_analiz, yeniden) kaydeder, sabit sonuç döner.
    yaz: istenirse depo master'ını değiştiren callable(bolum_no) (uygula simülasyonu)."""

    def __init__(self, nedenler=None, yaz=None):
        self.calls = []
        self.nedenler = list(nedenler or [])
        self.yaz = yaz

    def __call__(self, hub, anahtar, bolum_no, sadece_analiz=False, yeniden=False):
        self.calls.append((bolum_no, sadece_analiz, yeniden))
        if self.yaz:
            self.yaz(bolum_no)
        return {"status": "ok", "kontrol_nedenleri": list(self.nedenler),
                "master_surum": 1, "pdf": None}


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    """Hermetik ortam: seri deposu + hub kökü + export kökleri tmp'de."""
    monkeypatch.setenv("MITAS_SERILER_ROOT", str(tmp_path / "_SERILER"))
    klasor = tmp_path / DIZI_AD
    klasor.mkdir()
    monkeypatch.setattr(di, "hub_yolu",
                        lambda video, trt, baslik: tmp_path / "Database" / f"HUB {trt}")
    onayli = tmp_path / "export" / "ONAYLI"
    kontrol = tmp_path / "export" / "KONTROL"
    monkeypatch.setattr(di, "_export_kokleri", lambda: (onayli, kontrol))
    return SimpleNamespace(klasor=klasor, tmp=tmp_path, onayli=onayli, kontrol=kontrol,
                           rapor=tmp_path / "rapor")


def _locked_master(anahtar, ardisik=0):
    """Depoya asgari LOCKED master yaz (kilit_bolumler=[1,2,3], v1)."""
    m = sk.bos_master(anahtar, DIZI_AD, "", "2026-07-09T00:00:00")
    m.update(durum="LOCKED", master_surum=1, kilit_bolumler=[1, 2, 3])
    m["alanlar"] = {"Yönetmen": {"kanonik": ["SAMET POLAT"], "guven": "KESIN",
                                 "kb_teyit": False, "tanik": {}}}
    m["format_kopusu"] = {"ardisik": ardisik, "ilk_bolum": None}
    sk.kaydet(anahtar, m)
    return m


# ─────────────────────────────────── birimler ────────────────────────────────────

def test_bolum_no_int():
    assert di.bolum_no_int("14. BÖLÜM") == 14
    assert di.bolum_no_int("617. BÖLÜM") == 617
    assert di.bolum_no_int("") is None
    assert di.bolum_no_int(None) is None
    assert di.bolum_no_int("BÖLÜM") is None


def test_tohum_kalite_kapisi_birim():
    assert di.tohum_kalite(_okuma(1)) is True
    assert di.tohum_kalite(_okuma(1, kaynak="kare")) is False        # kare-fallback sayılmaz
    assert di.tohum_kalite(_okuma(1, kaynak="yok")) is False
    assert di.tohum_kalite(_okuma(1, cast=[])) is False              # boş cast sayılmaz
    assert di.tohum_kalite(None) is False


# ───────────────────────────── bölüm keşfi + sıralama ────────────────────────────

def test_bolum_no_sirasi_leksikografik_tuzak(ortam, monkeypatch):
    # dizin-listesi sırası (önek) 100, 10, 9 verir → işleme bolum-no artan OLMALI
    _vid(ortam.klasor, 100, onek="a_", icerik=b"c100")
    _vid(ortam.klasor, 10, onek="b_", icerik=b"c10")
    _vid(ortam.klasor, 9, onek="c_", icerik=b"c9")

    bolumler, kimliksiz, atlanan = di.bolumleri_bul(ortam.klasor)
    assert [b["bolum_no"] for b in bolumler] == [9, 10, 100]
    assert kimliksiz == [] and atlanan == []

    ok = okuma_fabrika()
    monkeypatch.setattr(di, "_okuma_topla", ok)
    kos = Kos()
    di.isle(ortam.klasor, pipeline_kos=kos, rapor_dizin=ortam.rapor)
    assert ok.calls == [9, 10, 100]                     # okuma sırası da numerik
    assert kos.calls == [f"c_1900-0138-0-0009-00-1 {DIZI_AD}.mp4",
                         f"b_1900-0138-0-0010-00-1 {DIZI_AD}.mp4",
                         f"a_1900-0138-0-0100-00-1 {DIZI_AD}.mp4"]


def test_kimliksiz_ve_profil_ayrimi(ortam):
    _vid(ortam.klasor, 14)                                    # geçerli dizi bölümü
    (ortam.klasor / "rastgele_video.mp4").write_bytes(b"x")   # TRT-id YOK → kimliksiz
    _vid(ortam.klasor, 7, tip="1")                            # tip=1 → film → uyarı+atla
    _vid(ortam.klasor, 0)                                     # bölüm 0 → aralık dışı
    _vid(ortam.klasor, 2500)                                  # bölüm 2500 → aralık dışı
    (ortam.klasor / "not.txt").write_text("video değil", encoding="utf-8")  # uzantı dışı

    bolumler, kimliksiz, atlanan = di.bolumleri_bul(ortam.klasor)
    assert [b["bolum_no"] for b in bolumler] == [14]
    kim = {k["dosya"] for k in kimliksiz}
    assert "rastgele_video.mp4" in kim
    assert any("-0000-" in d for d in kim)                    # bölüm 0
    assert any("-2500-" in d for d in kim)                    # bölüm 2000 üstü
    assert len(atlanan) == 1 and "film" in atlanan[0]["neden"]


# ─────────────────────────── tanık idempotency + conflict ────────────────────────

def test_tanik_idempotency_ikinci_kosu_pipeline_cagirmaz(ortam, monkeypatch):
    for n in (1, 2, 3):
        _vid(ortam.klasor, n, icerik=b"icerik-%d" % n)
    monkeypatch.setattr(di, "_okuma_topla", okuma_fabrika())
    kos = Kos()

    di.isle(ortam.klasor, pipeline_kos=kos, rapor_dizin=ortam.rapor)
    assert len(kos.calls) == 3                                # ilk koşu: 3 pipeline
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    assert sk.yukle(anahtar)["durum"] == "LOCKED"             # 3 kaliteli tohum → kilit

    akis = Akis()
    monkeypatch.setattr(di, "_bolum_kunye_akisi", akis)
    r2 = di.isle(ortam.klasor, pipeline_kos=kos, rapor_dizin=ortam.rapor)
    assert len(kos.calls) == 3                                # İKİNCİ koşu: pipeline ARTMADI
    assert all(k["tanik"] == "AYNI" for k in r2["islenen"])
    assert [c[0] for c in akis.calls] == [1, 2, 3]            # LOCKED yolu yine koştu


def test_duplicate_conflict_ayni_id_farkli_icerik(ortam, monkeypatch):
    p1 = _vid(ortam.klasor, 14, icerik=b"orijinal")
    p2 = _vid(ortam.klasor, 14, icerik=b"BAMBASKA", onek="zz_kopya_")
    monkeypatch.setattr(di, "_okuma_topla", okuma_fabrika())
    kos = Kos()

    r = di.isle(ortam.klasor, pipeline_kos=kos, rapor_dizin=ortam.rapor)
    assert kos.calls == [p1.name]                             # yalnız ilk dosya işlendi
    assert len(r["conflict"]) == 1
    assert r["conflict"][0]["dosya"] == p2.name
    assert r["conflict"][0]["bolum_no"] == 14
    # tanık defterindeki hash EZİLMEDİ (orijinal içerik hash'i durur)
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    kayit = sk.yukle(anahtar)["tanik_kayitlari"]["1900-0138-0-0014-00-1"]
    import hashlib
    assert kayit["content_hash"] == hashlib.sha256(b"orijinal").hexdigest()


# ───────────────────────────── tohum: kalite kapısı + kilit ──────────────────────

def test_kalite_kapisi_kare_bolum_tohuma_sayilmaz(ortam, monkeypatch):
    for n in (1, 2, 3, 4):
        _vid(ortam.klasor, n, icerik=b"i%d" % n)
    monkeypatch.setattr(di, "_okuma_topla", okuma_fabrika({1: {"kaynak": "kare"}}))

    r = di.isle(ortam.klasor, pipeline_kos=Kos(), rapor_dizin=ortam.rapor)
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    m = sk.yukle(anahtar)
    assert m["durum"] == "LOCKED"
    assert m["kilit_bolumler"] == [2, 3, 4]                   # 1 tohuma SAYILMADI
    assert (sk.yol(anahtar) / "bolumler" / "bolum_0001.json").exists()  # okuması SAKLANDI
    kayit1 = next(k for k in r["islenen"] if k["bolum_no"] == 1)
    assert kayit1["tohum_kalite"] is False


def test_uc_tohum_kilit_kur_master_ve_geri_doldur(ortam, monkeypatch):
    for n in (1, 2, 3):
        _vid(ortam.klasor, n, icerik=b"c%d" % n)
    monkeypatch.setattr(di, "_okuma_topla", okuma_fabrika())
    akis = Akis()
    monkeypatch.setattr(di, "_bolum_kunye_akisi", akis)

    r = di.isle(ortam.klasor, pipeline_kos=Kos(), geri_doldur=True, rapor_dizin=ortam.rapor)
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    m = sk.yukle(anahtar)
    # GERÇEK seri_konsensus.kur_master gövdesi + seri_kayit.kilitle kanıtı
    assert m["durum"] == "LOCKED" and m["master_surum"] == 1
    assert m["kilit_bolumler"] == [1, 2, 3]
    assert m["alanlar"]["Yönetmen"]["kanonik"] == ["SAMET POLAT"]
    assert m["alanlar"]["Yönetmen"]["guven"] == "KESIN"
    assert set(m["oyuncular"]) == {"POLAT ALEMDAR", "AYŞE YILDIZ", "MEMATİ BAŞ"}
    assert all(o["durum"] == "AKTIF" for o in m["oyuncular"].values())
    assert len(m["tanik_kayitlari"]) == 3                     # tanık defteri kilide DEVREDİLDİ
    assert any(e.get("olay") == "kilit" for e in m["surum_gecmisi"])
    # --geri-doldur: tohum PDF'leri kanonikten yeniden basıldı (akış 1,2,3; analiz DEĞİL)
    assert [c[0] for c in akis.calls] == [1, 2, 3]
    assert all(c[1] is False for c in akis.calls)
    # vl_teyitsiz=None: tohum okumalarının VL'si boş → madde-1 kapısı atlandı (yokluk ceza değil)
    assert r["tohum"] == {"bolumler": [1, 2, 3], "kilitlendi": True, "vl_teyitsiz": None}
    # koşu raporu diske yazıldı (DIZI_<anahtar>_<tarih>.json)
    ryol = Path(r["rapor_yolu"])
    assert ryol.exists() and ryol.name.startswith(f"DIZI_{anahtar}_")
    assert json.loads(ryol.read_text(encoding="utf-8"))["tohum"]["kilitlendi"] is True


def test_limit_kirpinca_eldekilerle_kilit_yok(ortam, monkeypatch):
    for n in (1, 2, 3):
        _vid(ortam.klasor, n, icerik=b"l%d" % n)
    monkeypatch.setattr(di, "_okuma_topla", okuma_fabrika())
    kos = Kos()

    r = di.isle(ortam.klasor, limit=1, pipeline_kos=kos, rapor_dizin=ortam.rapor)
    assert len(kos.calls) == 1
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    # klasör BİTMEDİ (limit kırptı) → ">=1 varsa eldekilerle kilitle" fallback'i ÇALIŞMAZ
    assert sk.yukle(anahtar)["durum"] == "BUILDING"
    assert sum(1 for a in r["atlanan"] if "limit" in a["neden"].lower()) == 2


# ───────────────────────────────── --sadece-analiz ───────────────────────────────

def test_sadece_analiz_yazma_yapmaz(ortam, monkeypatch):
    _vid(ortam.klasor, 14)
    monkeypatch.setattr(di, "_okuma_topla", okuma_fabrika())
    kos = Kos()

    r = di.isle(ortam.klasor, sadece_analiz=True, pipeline_kos=kos, rapor_dizin=ortam.rapor)
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    assert kos.calls == []                                    # pipeline KOŞULMADI
    assert not (sk.yol(anahtar) / "seri_master.json").exists()  # depo YAZILMADI
    assert not (sk.yol(anahtar) / "bolumler").exists()          # okuma anlık görüntüsü YOK
    assert r["islenen"][0]["pipeline"] == "analiz-atlandi"
    assert Path(r["rapor_yolu"]).exists()                     # rapor yine yazılır


def test_sadece_analiz_locked_master_ve_exporta_dokunmaz(ortam, monkeypatch):
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    _locked_master(anahtar)
    once = (sk.yol(anahtar) / "seri_master.json").read_bytes()
    _vid(ortam.klasor, 14)
    akis = Akis(nedenler=["Yönetmen master'dan farklı: 'CEM DENIZ' (bölüm 14)"])
    monkeypatch.setattr(di, "_bolum_kunye_akisi", akis)
    ortam.onayli.mkdir(parents=True)
    pdf = ortam.onayli / f"1900-0138-0-0014-00-1 {DIZI_AD}_onaylı.pdf"
    pdf.write_bytes(b"%PDF")

    r = di.isle(ortam.klasor, sadece_analiz=True, pipeline_kos=Kos(), rapor_dizin=ortam.rapor)
    assert akis.calls == [(14, True, False)]                  # --sadece-analiz akışa İLETİLDİ
    assert pdf.exists()                                       # export DOKUNULMADI
    assert r["export_mutabakat"] == []
    assert (sk.yol(anahtar) / "seri_master.json").read_bytes() == once  # seri_master DEĞİŞMEDİ
    assert r["kontrol_nedenleri"]["14"] == akis.nedenler      # nedenler yine raporlanır


# ───────────────────────────────── export mutabakatı ─────────────────────────────

def test_export_mutabakati_tasima_ve_sidecar(ortam, monkeypatch):
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    _locked_master(anahtar)
    _vid(ortam.klasor, 14, icerik=b"i14")
    nedenler = ["Yönetmen master'dan farklı: 'CEM DENIZ' (bölüm 14)"]
    monkeypatch.setattr(di, "_bolum_kunye_akisi", Akis(nedenler=nedenler))
    ortam.onayli.mkdir(parents=True)
    kaynak_pdf = ortam.onayli / f"1900-0138-0-0014-00-1 {DIZI_AD}_onaylı.pdf"
    kaynak_pdf.write_bytes(b"%PDF-bolum14")

    r = di.isle(ortam.klasor, pipeline_kos=Kos(), rapor_dizin=ortam.rapor)
    assert not kaynak_pdf.exists()                            # ONAYLI'dan taşındı
    hedef = ortam.kontrol / kaynak_pdf.name
    assert hedef.exists() and hedef.read_bytes() == b"%PDF-bolum14"
    sidecar = hedef.with_suffix(".dizi_neden.json")           # <ad>.dizi_neden.json yanında
    assert sidecar.exists()
    j = json.loads(sidecar.read_text(encoding="utf-8"))
    assert j["kontrol_nedenleri"] == nedenler
    assert j["bolum_no"] == 14 and j["trt_id"] == "1900-0138-0-0014-00-1"
    assert r["export_mutabakat"] and r["export_mutabakat"][0]["pdf"] == str(hedef)
    assert r["kontrol_nedenleri"]["14"] == nedenler


def test_export_mutabakati_onaylida_pdf_yoksa_sessiz(ortam, monkeypatch):
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    _locked_master(anahtar)
    _vid(ortam.klasor, 14)
    monkeypatch.setattr(di, "_bolum_kunye_akisi", Akis(nedenler=["neden"]))

    r = di.isle(ortam.klasor, pipeline_kos=Kos(), rapor_dizin=ortam.rapor)   # ONAYLI dizini YOK
    assert r["export_mutabakat"] == []                        # taşınacak şey yok → sessiz
    assert r["kontrol_nedenleri"]["14"] == ["neden"]          # nedenler yine raporda


# ─────────────────────────────── FORMAT_KOPUSU Faz-1 ─────────────────────────────

def test_format_kopusu_iki_ardisik_tespit_rapor_dur(ortam, monkeypatch, capsys):
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    _locked_master(anahtar)
    for n in (4, 5, 6):
        _vid(ortam.klasor, n, icerik=b"k%d" % n)

    def kopus_yaz(bolum_no):
        # 5. bölümde uygula simülasyonu: depo master sayacı 2-ardışığa ulaştı
        if bolum_no == 5:
            m = sk.yukle(anahtar)
            m["format_kopusu"] = {"ardisik": 2, "ilk_bolum": 4}
            sk.kaydet(anahtar, m)

    akis = Akis(yaz=kopus_yaz)
    monkeypatch.setattr(di, "_bolum_kunye_akisi", akis)

    r = di.isle(ortam.klasor, pipeline_kos=Kos(), rapor_dizin=ortam.rapor)
    assert [c[0] for c in akis.calls] == [4, 5]               # 6. bölüm İŞLENMEDİ (dur)
    assert r["format_kopusu"] == {"ardisik": 2, "ilk_bolum": 4, "bolum": 5}
    assert any("elle tohum yenileme" in a["neden"] for a in r["atlanan"])
    assert "elle tohum yenileme" in capsys.readouterr().out   # stdout mesajı


# ─────────────────────────────────── çökme yasağı ────────────────────────────────

def test_cokme_yasagi_hatali_bolum_kosuyu_durdurmaz(ortam, monkeypatch):
    for n in (1, 2, 3):
        _vid(ortam.klasor, n, icerik=b"h%d" % n)

    def patlayan_okuma(hub, bolum_no, trt_id=None):
        if bolum_no == 2:
            raise RuntimeError("bozuk hub")
        return _okuma(bolum_no, trt=trt_id)

    monkeypatch.setattr(di, "_okuma_topla", patlayan_okuma)
    r = di.isle(ortam.klasor, pipeline_kos=Kos(), rapor_dizin=ortam.rapor)
    assert [k["bolum_no"] for k in r["islenen"]] == [1, 3]    # koşu SÜRDÜ
    assert len(r["hatali"]) == 1 and r["hatali"][0]["bolum_no"] == 2
    assert "RuntimeError" in r["hatali"][0]["hata"]


# ──────────────────────────── MADDE 1: tohum-VL kapısı ───────────────────────────

def test_tohum_vl_kapisi_birim():
    m = {"alanlar": {"Yönetmen": {"kanonik": ["SAMET POLAT"]}},
         "oyuncular": {"MEMATİ BAŞ": {"durum": "AKTIF"},
                       "ESKİ ÜYE": {"durum": "AYRILDI"}}}          # AYRILDI kapıya GİRMEZ
    # VL birleşimi TAMAMEN boş → None (kapı atlanır — yokluk ceza değil)
    assert di.tohum_vl_kapisi(m, [_okuma(1), _okuma(2)]) is None
    # VL kısmî → teyitsizler listelenir (name_match sıkı; AYRILDI üye sorgulanmaz)
    okl = [_okuma(1, vl={"yonetmen": ["SAMET POLAT"], "oyuncular": [], "diger_roller": []}),
           _okuma(2)]
    assert di.tohum_vl_kapisi(m, okl) == ["MEMATİ BAŞ"]
    # fold-toleranslı eşleşme (VL aksansız yazsa da teyit sayılır) → hepsi teyitli = boş liste
    okl2 = [_okuma(1, vl={"yonetmen": ["SAMET POLAT"],
                          "oyuncular": ["MEMATI BAS"], "diger_roller": []})]
    assert di.tohum_vl_kapisi(m, okl2) == []


def test_tohum_vl_teyitsiz_kilitte_isaretlenir(ortam, monkeypatch):
    for n in (1, 2, 3):
        _vid(ortam.klasor, n, icerik=b"v%d" % n)
    # yalnız bölüm 1'de VL var: yönetmen + 2 oyuncu teyitli, MEMATİ BAŞ teyitsiz kalır
    vl1 = {"yonetmen": ["SAMET POLAT"], "oyuncular": ["POLAT ALEMDAR", "AYSE YILDIZ"],
           "diger_roller": []}
    monkeypatch.setattr(di, "_okuma_topla", okuma_fabrika({1: {"vl": vl1}}))

    r = di.isle(ortam.klasor, pipeline_kos=Kos(), rapor_dizin=ortam.rapor)
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    m = sk.yukle(anahtar)
    assert m["durum"] == "LOCKED"
    assert m["tohum_vl_teyitsiz"] == ["MEMATİ BAŞ"]           # master listesine yazıldı
    assert r["tohum"]["vl_teyitsiz"] == ["MEMATİ BAŞ"]        # koşu raporuna yazıldı
    assert not any("VL kapsamı yok" in u for u in r["uyarilar"])
    # kilit olayına yazıldı (gecmis.jsonl append-only günlüğü)
    olaylar = [json.loads(s) for s in
               (sk.yol(anahtar) / "gecmis.jsonl").read_text(encoding="utf-8").splitlines() if s]
    kilit = next(o for o in olaylar if o.get("olay") == "kilit")
    assert kilit["tohum_vl_teyitsiz"] == ["MEMATİ BAŞ"]


def test_tohum_vl_bos_kapi_atlanir(ortam, monkeypatch):
    for n in (1, 2, 3):
        _vid(ortam.klasor, n, icerik=b"b%d" % n)
    monkeypatch.setattr(di, "_okuma_topla", okuma_fabrika())   # vl hep boş

    r = di.isle(ortam.klasor, pipeline_kos=Kos(), rapor_dizin=ortam.rapor)
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    m = sk.yukle(anahtar)
    assert m["durum"] == "LOCKED"
    assert m["tohum_vl_teyitsiz"] is None                     # kapı ATLANDI (ceza değil)
    assert r["tohum"]["vl_teyitsiz"] is None
    assert any("VL kapsamı yok" in u for u in r["uyarilar"])  # rapora not düştü


# ─────────────────────────── MADDE 3b: --tohum-yenile ───────────────────────────

def _yeniden_tohumla_sahte(cagrilar):
    """seri_kayit.yeniden_tohumla sözleşme-sahtesi (dizi_SISTEM.md madde 3: SAF;
    durum=BUILDING, kilit/format_kopusu sıfır, defterler korunur, olay günlüğe)."""

    def _f(anahtar, master, bolumler, simdi):
        cagrilar.append(list(bolumler))
        m = json.loads(json.dumps(master))
        m["surum_gecmisi"] = list(m.get("surum_gecmisi") or []) + [
            {"olay": "yeniden_tohum", "eski_kilit": list(m.get("kilit_bolumler") or []),
             "ts": simdi}]
        m.update(durum="BUILDING", kilit_bolumler=[],
                 format_kopusu={"ardisik": 0, "ilk_bolum": None})
        return m

    return _f


def test_yeniden_tohumla_dikisi_imza_uyarlama(monkeypatch):
    # paralel modülün iki olası imzası da desteklenir (inspect ile; TypeError yutma YOK)
    gorulen = {}

    def v4(anahtar, master, bolumler, simdi):
        gorulen["v4"] = (anahtar, list(bolumler), simdi)
        return dict(master, durum="BUILDING")

    monkeypatch.setattr(sk, "yeniden_tohumla", v4, raising=False)
    m = di._yeniden_tohumla("K", {"durum": "LOCKED"}, [1, 2], "ts")
    assert m["durum"] == "BUILDING" and gorulen["v4"] == ("K", [1, 2], "ts")

    def v3(master, bolumler, simdi):
        gorulen["v3"] = (list(bolumler), simdi)
        return dict(master, durum="BUILDING")

    monkeypatch.setattr(sk, "yeniden_tohumla", v3, raising=False)
    m = di._yeniden_tohumla("K", {"durum": "LOCKED"}, [3], "ts2")
    assert m["durum"] == "BUILDING" and gorulen["v3"] == ([3], "ts2")


def test_tohum_yenile_mutlu_yol(ortam, monkeypatch):
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    _locked_master(anahtar)                                   # eski kilit [1,2,3]
    for n in (2, 3, 4):
        sk.bolum_kaydet(anahtar, n, _okuma(n))                # ledger okumaları hazır
    cagrilar = []
    monkeypatch.setattr(sk, "yeniden_tohumla", _yeniden_tohumla_sahte(cagrilar), raising=False)
    _vid(ortam.klasor, 5, icerik=b"c5")                       # reseed SONRASI normal akış
    akis = Akis()
    monkeypatch.setattr(di, "_bolum_kunye_akisi", akis)
    kos = Kos()

    r = di.isle(ortam.klasor, tohum_yenile=[2, 3, 4], pipeline_kos=kos, rapor_dizin=ortam.rapor)
    assert cagrilar == [[2, 3, 4]]                            # yeniden_tohumla ÇAĞRILDI
    m = sk.yukle(anahtar)
    assert m["durum"] == "LOCKED" and m["kilit_bolumler"] == [2, 3, 4]
    assert set(m["oyuncular"]) == {"POLAT ALEMDAR", "AYŞE YILDIZ", "MEMATİ BAŞ"}
    olaylar = [e.get("olay") for e in m["surum_gecmisi"]]
    assert "yeniden_tohum" in olaylar                         # denetim izi kilide DEVREDİLDİ
    assert olaylar[-1] == "kilit"                             # yeni kilit en sonda
    assert r["tohum"] == {"bolumler": [2, 3, 4], "kilitlendi": True, "vl_teyitsiz": None}
    assert any("TOHUM_YENILE" in u for u in r["uyarilar"])
    assert akis.calls == [(5, False, False)]                  # normal akış DEVAM ETTİ (LOCKED)
    assert len(kos.calls) == 1 and "0005" in kos.calls[0]


def test_tohum_yenile_ledger_eksik_hata(ortam, monkeypatch):
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    _locked_master(anahtar)
    sk.bolum_kaydet(anahtar, 2, _okuma(2))                    # yalnız 2 ledger'da; 9 YOK
    cagrilar = []
    monkeypatch.setattr(sk, "yeniden_tohumla", _yeniden_tohumla_sahte(cagrilar), raising=False)
    _vid(ortam.klasor, 5, icerik=b"e5")
    akis = Akis()
    monkeypatch.setattr(di, "_bolum_kunye_akisi", akis)
    kos = Kos()

    r = di.isle(ortam.klasor, tohum_yenile=[2, 9], pipeline_kos=kos, rapor_dizin=ortam.rapor)
    assert cagrilar == []                                     # reseed HİÇ BAŞLAMADI
    assert r["hatali"] and "9" in r["hatali"][0]["hata"]      # açık hata mesajı (rc!=0 main'de)
    assert "ledger" in r["hatali"][0]["hata"].lower()
    assert r["islenen"] == [] and akis.calls == [] and kos.calls == []   # koşu bölüm İŞLEMEDİ
    m = sk.yukle(anahtar)
    assert m["durum"] == "LOCKED" and m["kilit_bolumler"] == [1, 2, 3]   # master DEĞİŞMEDİ


# ──────────────────────────── MADDE 4: --teslim-disi ─────────────────────────────

def test_teslim_disi_karantina_tasima_ve_rapor(ortam, monkeypatch):
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    _locked_master(anahtar)
    _vid(ortam.klasor, 14, icerik=b"t14")
    monkeypatch.setattr(di, "_bolum_kunye_akisi", Akis(nedenler=["neden X"]))
    kar = ortam.tmp / "outputs" / "pilot_karantina" / anahtar
    monkeypatch.setattr(di, "_karantina_koku", lambda a: kar)

    ortam.onayli.mkdir(parents=True)
    ortam.kontrol.mkdir(parents=True)
    onayli_pdf = ortam.onayli / f"1900-0138-0-0014-00-1 {DIZI_AD}_onaylı.pdf"
    onayli_pdf.write_bytes(b"%PDF-onayli")
    eski_kontrol = ortam.kontrol / f"1900-0138-0-0014-00-1 {DIZI_AD}_eski.pdf"
    eski_kontrol.write_bytes(b"%PDF-eski")                    # önceki koşudan kalan
    baska = ortam.onayli / f"1900-0139-0-0014-00-1 BASKA DIZI.pdf"
    baska.write_bytes(b"%PDF-baska")                          # BAŞKA serinin TRT-id'i
    kar.mkdir(parents=True)
    (kar / eski_kontrol.name).write_bytes(b"%PDF-var")        # ad çakışması → ' (2)' soneki

    r = di.isle(ortam.klasor, teslim_disi=True, pipeline_kos=Kos(), rapor_dizin=ortam.rapor)

    # export_mutabakat bu modda DOĞRUDAN karantinaya taşıdı (KONTROL'e yeni dosya düşmedi)
    assert not onayli_pdf.exists()
    assert (kar / onayli_pdf.name).read_bytes() == b"%PDF-onayli"
    assert (kar / onayli_pdf.name).with_suffix(".dizi_neden.json").exists()
    assert r["export_mutabakat"] and r["export_mutabakat"][0]["pdf"] == str(kar / onayli_pdf.name)
    assert not (ortam.kontrol / onayli_pdf.name).exists()
    # koşu-sonu süpürme: KONTROL'deki eski PDF karantinaya, çakışan ad ' (2)' sonekiyle
    assert not eski_kontrol.exists()
    cakisan = kar / f"1900-0138-0-0014-00-1 {DIZI_AD}_eski (2).pdf"
    assert cakisan.read_bytes() == b"%PDF-eski"
    assert (kar / eski_kontrol.name).read_bytes() == b"%PDF-var"         # mevcut EZİLMEDİ
    assert any(t["pdf"] == str(cakisan) for t in r["karantina"])         # rapora yazıldı
    assert baska.exists()                                                # başka seri DOKUNULMADI
    assert r["teslim_disi"] is True


def test_teslim_disi_sadece_analiz_dokunmaz(ortam, monkeypatch):
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    _locked_master(anahtar)
    _vid(ortam.klasor, 14)
    monkeypatch.setattr(di, "_bolum_kunye_akisi", Akis(nedenler=["neden"]))
    kar = ortam.tmp / "kar" / anahtar
    monkeypatch.setattr(di, "_karantina_koku", lambda a: kar)
    ortam.onayli.mkdir(parents=True)
    pdf = ortam.onayli / f"1900-0138-0-0014-00-1 {DIZI_AD}_onaylı.pdf"
    pdf.write_bytes(b"%PDF")

    r = di.isle(ortam.klasor, teslim_disi=True, sadece_analiz=True,
                pipeline_kos=Kos(), rapor_dizin=ortam.rapor)
    assert pdf.exists()                                       # HİÇBİR taşıma yok
    assert r["karantina"] == [] and r["export_mutabakat"] == []


# ───────────────────────── MADDE 6: --yeniden iletimi ────────────────────────────

def test_bolum_kunye_akisi_yeniden_argv(monkeypatch):
    argvler = []

    def fmain(argv):
        argvler.append(list(argv))
        print(json.dumps({"status": "ok"}))
        return 0

    monkeypatch.setitem(sys.modules, "seri_bolum_kunye", SimpleNamespace(main=fmain))
    s = di._bolum_kunye_akisi("HUB", "K", 7, sadece_analiz=False, yeniden=True)
    assert s["status"] == "ok" and "--yeniden" in argvler[-1]
    di._bolum_kunye_akisi("HUB", "K", 7, sadece_analiz=True)
    assert "--yeniden" not in argvler[-1] and "--sadece-analiz" in argvler[-1]


def test_isle_yeniden_bayragi_akisa_tasinir(ortam, monkeypatch):
    anahtar = sk.seri_anahtar(ortam.klasor.name)
    _locked_master(anahtar)
    _vid(ortam.klasor, 14)
    akis = Akis()
    monkeypatch.setattr(di, "_bolum_kunye_akisi", akis)

    di.isle(ortam.klasor, yeniden=True, pipeline_kos=Kos(), rapor_dizin=ortam.rapor)
    assert akis.calls == [(14, False, True)]                  # --yeniden akışa İLETİLDİ


# ─────────────────────────────────────── CLI ─────────────────────────────────────

def test_main_cli_bayrak_iletimi(tmp_path, monkeypatch):
    kayit = {}

    def sahte_isle(klasor, **kw):
        kayit.update(kw, klasor=klasor)
        return {"hatali": []}

    monkeypatch.setattr(di, "isle", sahte_isle)
    rc = di.main(["--klasor", str(tmp_path), "--sadece-analiz", "--geri-doldur",
                  "--limit", "5", "--python", "px"])
    assert rc == 0
    assert kayit["sadece_analiz"] is True
    assert kayit["geri_doldur"] is True
    assert kayit["limit"] == 5
    assert kayit["python_exe"] == "px"
    assert kayit["tohum_yenile"] is None                      # bayrak verilmedi → None
    assert kayit["teslim_disi"] is False
    assert kayit["yeniden"] is False

    rc = di.main(["--klasor", str(tmp_path), "--tohum-yenile", "4, 2,2", "--teslim-disi",
                  "--yeniden"])
    assert rc == 0
    assert kayit["tohum_yenile"] == [2, 4]                    # sıralı + tekilleştirilmiş
    assert kayit["teslim_disi"] is True
    assert kayit["yeniden"] is True


def test_main_cli_tohum_yenile_dogrulama(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "isle", lambda klasor, **kw: {"hatali": []})
    assert di.main(["--klasor", str(tmp_path), "--tohum-yenile", "a,b"]) == 2   # sayı değil
    assert di.main(["--klasor", str(tmp_path), "--tohum-yenile", ","]) == 2     # boş liste
    # --sadece-analiz ile birleşemez: yeniden tohum kalıcı yazar
    assert di.main(["--klasor", str(tmp_path), "--tohum-yenile", "1,2",
                    "--sadece-analiz"]) == 2


def test_main_cli_klasor_yok_rc2(tmp_path):
    assert di.main(["--klasor", str(tmp_path / "YOK")]) == 2


def test_main_cli_hatali_bolum_rc1(tmp_path, monkeypatch):
    monkeypatch.setattr(di, "isle", lambda klasor, **kw: {"hatali": [{"bolum_no": 1}]})
    assert di.main(["--klasor", str(tmp_path)]) == 1
