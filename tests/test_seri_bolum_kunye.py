# -*- coding: utf-8 -*-
"""test_seri_bolum_kunye.py — dizi modu: seri_bolum_kunye (master+diff+meta → d-sözlüğü + PDF CLI).

Katmanlar (sözleşme: scripts/dizi_SISTEM.md "Bölüm PDF birleştirme" — BAĞLAYICI):
  • SAF   : birlesik_kunye(master, diff, meta) → (d, kaynak_haritasi) — IO yok, girdi mutate edilmez.
  • CLI   : main() YALNIZ kendi dikişleri (_master_yukle/_okuma_yap/_diffle/_uygula_ve_kaydet)
            monkeypatch'lenerek BİRİM test edilir — seri_kayit / dizi_credit_parse / seri_diff
            modüllerine BAĞIMLILIK YOK (paralel ajanlar eş-zamanlı yazıyor).
  • DUMAN : reportlab kuruluysa gerçek _make_pdf.build render (>10KB); yoksa skip.

Hermetik kural: name_normalize'ın duckdb (X:\\...) / DeepSeek / Qwen yolları MOCK'lanır —
X:/Y: sürücülerine ve ağa ASLA dokunulmaz (dizi_SISTEM.md test kuralları).

Çalıştır:  python -m pytest tests/test_seri_bolum_kunye.py -x -q
"""
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import seri_bolum_kunye as sbk


# ── hermetik kilit: kasa fonksiyonları DB'siz/ağsız deterministik ────────────────────────────
@pytest.fixture(autouse=True)
def _hermetik(monkeypatch):
    # duckdb (X:\...) hiç açılmasın: "DB çalıştı, Türk-kanonik eşleşme yok" davranışı sabitlenir.
    monkeypatch.setattr(sbk.nn, "_mitas_people_set", lambda names: (True, {}))
    monkeypatch.setattr(sbk.nn, "_deepseek_available", lambda: False)
    monkeypatch.setattr(sbk.nn, "qwen_is_turkish", lambda names, **k: {})


SIMDI = "09.07.2026 · 12:00"

# tek_film_kunye.py:1174-1181 + :1193 d-sözlüğü anahtar seti + "bolum" (dizi_SISTEM.md sözleşmesi)
BEKLENEN_ANAHTARLAR = {"profile", "date", "title", "subtitle", "specs", "keywords", "cast",
                       "crew", "ozet", "ses_kanallari", "ana_dil", "altyazi", "poster",
                       "film_notu", "bolum"}


def _master():
    """seri_master.json (surum_sema=1) asgari örneği — LOCKED, v3."""
    return {
        "surum_sema": 1,
        "seri_anahtar": "BIZIM_EVIN_HALLERI_00000000",
        "seri_adi": "BİZİM EVİN HALLERİ",
        "durum": "LOCKED",
        "master_surum": 3,
        "alanlar": {
            "Yönetmen": {"kanonik": ["SAMET POLAT"], "guven": "KESIN"},
            "Yapımcı": {"kanonik": ["OSMAN SINAV"], "guven": "KESIN"},
            "Müzik": {"kanonik": [], "guven": "KESIN"},            # boş kanonik → satır YOK
            "Kurgu": {"kanonik": ["NUR ARSLAN"], "guven": "KESIN"},
        },
        "oyuncular": {
            "POLAT ALEMDAR": {"sira": 0, "durum": "AKTIF"},
            "AYŞE YILDIZ": {"sira": 1, "durum": "AKTIF"},
            "KEMAL DEMİR": {"sira": 2, "durum": "AYRILDI"},        # basılMAZ
            "ZEYNEP AK": {"sira": 3, "durum": "ZAYIF_UYE"},        # basılır
        },
        "teknik_ekip": {"Müzik Yönetmeni": {"CAN ATİLLA": {"bolumler": [1, 2, 3]}}},
    }


def _diff(**kw):
    """seri_diff.diffle çıktı şeması asgari örneği (bolum_no=14)."""
    d = {"bolum_no": 14,
         "eslesen": {"oyuncular": [], "alanlar": {}},
         "eksik": [], "yeni": [], "kalici_degisim": [], "terfi": [],
         "format_kopusu": False,
         "bolum_ozel": {"konuk_oyuncular": [], "alan_override": {}},
         "kontrol_nedenleri": []}
    d.update(kw)
    return d


def _meta():
    """parse_teslim_md çıktısı + CLI'nin doldurduğu trt_id/bolum."""
    return {"title": "BİZİM EVİN HALLERİ", "trt_id": "1900-0138-0-0014-00-1",
            "res": "720×576", "dur": "00:45:20", "tur": "Aile",
            "ses_kanallari": ["TÜRKÇE STEREO", "EFEKT"], "ana_dil": "TR", "altyazi": "YOK",
            "ozet": "Ali eve döner. Aile büyük bir sürprizle karşılaşır.",
            "film_notu": [], "bolum": 14}


# ═══ SAF: birlesik_kunye ══════════════════════════════════════════════════════════════════════

def test_d_anahtar_tamligi_ve_sabitler():
    d, _ = sbk.birlesik_kunye(_master(), _diff(), _meta(), simdi=SIMDI)
    assert set(d.keys()) == BEKLENEN_ANAHTARLAR          # tam set — eksik/fazla anahtar YOK
    assert d["profile"] == "DİZİ"
    assert d["date"] == SIMDI                            # simdi verilince SAF/deterministik
    assert d["subtitle"] is None
    assert d["poster"] is None
    assert d["film_notu"] == []
    assert d["bolum"] == "14. BÖLÜM"
    assert d["title"] == "BİZİM EVİN HALLERİ"            # master.seri_adi otorite


def test_cast_sira_ayrildi_haric_zayif_uye_dahil():
    d, _ = sbk.birlesik_kunye(_master(), _diff(), _meta(), simdi=SIMDI)
    # sira düzeninde; AYRILDI (KEMAL DEMİR) yok; ZAYIF_UYE (ZEYNEP AK) var; Türkçe yazım korunur.
    assert d["cast"] == ["POLAT ALEMDAR", "AYŞE YILDIZ", "ZEYNEP AK"]


def test_bos_kanonik_alan_atlanir_ve_crew_sirasi():
    d, _ = sbk.birlesik_kunye(_master(), _diff(), _meta(), simdi=SIMDI)
    roller = [r for r, _ in d["crew"]]
    # TEKİL kanonik sıra (Müzik boş → atlandı), sonra teknik_ekip rolleri.
    assert roller == ["Yönetmen", "Yapımcı", "Kurgu", "Müzik Yönetmeni"]
    crew = dict(d["crew"])
    assert crew["Yönetmen"] == ["SAMET POLAT"]
    assert crew["Müzik Yönetmeni"] == ["CAN ATİLLA"]


def test_alan_override_crewe_yansir_master_mutate_edilmez():
    master = _master()
    diff = _diff(bolum_ozel={"konuk_oyuncular": [],
                             "alan_override": {"Yönetmen": ["CEM DENIZ"]}})
    d, kh = sbk.birlesik_kunye(master, diff, _meta(), simdi=SIMDI)
    assert dict(d["crew"])["Yönetmen"] == ["CEM DENIZ"]                 # bölüm-özel override
    assert kh["Yönetmen"] == "bolum:14(override)"
    # SAF: girdi master DEĞİŞMEDİ (override kalıcı değişim değildir)
    assert master["alanlar"]["Yönetmen"]["kanonik"] == ["SAMET POLAT"]


def test_alan_override_master_bos_alani_da_doldurur():
    # seri_diff kural 4 (DEGISIM_ADAYI, garble-siz): master'da alan BOŞ olsa bile override basılır —
    # sözleşmede açık olmayan nokta; muhafazakar yorum = override her zaman o bölümün alan değeridir.
    diff = _diff(bolum_ozel={"konuk_oyuncular": [],
                             "alan_override": {"Müzik": ["CAN ATİLLA"]}})
    d, kh = sbk.birlesik_kunye(_master(), diff, _meta(), simdi=SIMDI)
    roller = [r for r, _ in d["crew"]]
    assert roller == ["Yönetmen", "Yapımcı", "Müzik", "Kurgu", "Müzik Yönetmeni"]  # kanonik TEKİL sıra
    assert kh["Müzik"] == "bolum:14(override)"


def test_konuk_oyuncular_en_sonda_kesin_once():
    diff = _diff(bolum_ozel={"konuk_oyuncular": [
        {"isim": "OKTAY DENER", "kaynak": "cast-diff", "kesin": False},
        {"isim": "ALTAN ALKAN", "kaynak": "jenerik-basligi", "kesin": True},
    ], "alan_override": {}})
    d, kh = sbk.birlesik_kunye(_master(), diff, _meta(), simdi=SIMDI)
    rol, isimler = d["crew"][-1]                                        # EN SON satır
    assert rol == "Konuk Oyuncular"
    assert isimler == ["ALTAN ALKAN", "OKTAY DENER"]                    # kesin=true önce, sıra korunur
    assert kh["Konuk Oyuncular"] == "bolum:14(konuk)"


def test_konuk_yoksa_satir_yok():
    d, kh = sbk.birlesik_kunye(_master(), _diff(), _meta(), simdi=SIMDI)
    assert "Konuk Oyuncular" not in [r for r, _ in d["crew"]]
    assert "Konuk Oyuncular" not in kh


def test_keywords_ozet_specs_ses_kanallari():
    d, _ = sbk.birlesik_kunye(_master(), _diff(), _meta(), simdi=SIMDI)
    assert d["keywords"] == "; ".join(["POLAT ALEMDAR", "AYŞE YILDIZ", "ZEYNEP AK"])
    assert d["specs"] == [("ÇÖZÜNÜRLÜK", "720×576"), ("TÜR", "AİLE"),
                          ("TOPLAM SÜRE", "00:45:20"), ("TRT KİMLİK", "1900-0138-0-0014-00-1")]
    assert d["ozet"] == "ALİ EVE DÖNER. AİLE BÜYÜK BİR SÜRPRİZLE KARŞILAŞIR."   # ozet_v4 (tr_upper_prose)
    assert d["ses_kanallari"] == ["TÜRKÇE STEREO"]                       # EFEKT kanalı filtreli
    assert d["ana_dil"] == "TR" and d["altyazi"] == "YOK"


def test_bos_cast_ve_bos_ozet_placeholder():
    master = _master()
    master["oyuncular"] = {}
    meta = _meta()
    meta["ozet"] = ""
    d, _ = sbk.birlesik_kunye(master, _diff(), meta, simdi=SIMDI)
    assert d["cast"] == ["—"]
    assert d["keywords"] == "—"
    assert d["ozet"] == "—"                                             # "okunamadı > yanlış oku"


def test_kaynak_haritasi_etiketleri():
    d, kh = sbk.birlesik_kunye(_master(), _diff(), _meta(), simdi=SIMDI)
    assert kh["cast"] == "master:v3"
    assert kh["keywords"] == "master:v3"          # cast'ten türetilir
    assert kh["title"] == "master:v3"
    assert kh["Yönetmen"] == "master:v3"
    assert kh["Müzik Yönetmeni"] == "master:v3"
    assert kh["ozet"] == "meta"
    assert kh["specs"] == "meta"
    assert kh["bolum"] == "meta"
    assert "Müzik" not in kh                      # boş kanonik alan haritada da yok
    del d  # d yalnız üretim kanıtı


# ═══ CLI: birim seviyesi (dikişler monkeypatch) ═══════════════════════════════════════════════

MD = """# MİTAS • DİZİ • BİZİM EVİN HALLERİ
- ID: 1900-0138-0-0014-00-1
Çözünürlük: 720×576 · Tür: Aile · Süre: 00:45:20
- 1. kanal: TÜRKÇE STEREO
- Ana dil: tr
- Altyazı: yok

## Özet
Ali eve döner. Aile büyük bir sürprizle karşılaşır.
"""


def _okuma():
    """BolumOkuma asgari örneği (dizi_credit_parse.okuma_topla sözleşmesi)."""
    return {"bolum_no": 14, "trt_id": "1900-0138-0-0014-00-1", "cast": [], "crew": {},
            "konuk_acik": [], "kb_hatti": {"yonetmen": [], "yapimci": [], "cast": []},
            "vl": {"yonetmen": [], "oyuncular": [], "diger_roller": []},
            "stop_kart_bolum_no": None, "kaynak": "master_dilim", "uyarilar": []}


class _FakeMp:
    """mp.build çağrı sözleşmesini kaydeder + >10KB sahte PDF yazar (replace yolunu tetikler)."""

    def __init__(self, boyut=20000):
        self.calls = []
        self._boyut = boyut

    def build(self, path, d):
        self.calls.append((path, d))
        with open(path, "wb") as f:
            f.write(b"%PDF-FAKE" + b"0" * self._boyut)


def _cli_dikis(monkeypatch, master, diff, okuma):
    monkeypatch.setattr(sbk, "_master_yukle", lambda anahtar: master)
    monkeypatch.setattr(sbk, "_okuma_yap", lambda clip, bolum_no, anahtar: okuma)
    monkeypatch.setattr(sbk, "_diffle", lambda m, o: diff)
    monkeypatch.setattr(sbk, "_uygula_ve_kaydet", lambda anahtar, m, d, o, simdi: m)


def test_cli_ok_mp_build_sozlesmesi_ve_ciktilar(tmp_path, monkeypatch, capsys):
    clip = tmp_path / "1900-0138-0-0014-00-1 BOLUM 14"
    (clip / "pdf").mkdir(parents=True)
    (clip / "pdf" / "kunye_teslim.md").write_text(MD, encoding="utf-8")
    diff = _diff(kontrol_nedenleri=["test-neden"])
    _cli_dikis(monkeypatch, _master(), diff, _okuma())
    fake = _FakeMp()
    monkeypatch.setattr(sbk, "mp", fake)

    rc = sbk.main(["--clip", str(clip), "--seri-anahtar", "BIZIM_EVIN_HALLERI_00000000",
                   "--bolum-no", "14"])
    out = capsys.readouterr().out.strip().splitlines()[-1]
    obj = json.loads(out)                                               # TEK-SATIR JSON

    assert rc == 0
    assert obj["status"] == "ok"
    assert obj["kontrol_nedenleri"] == ["test-neden"]
    assert obj["master_surum"] == 3
    hedef = clip / "pdf" / "kunye.pdf"
    assert obj["pdf"] == str(hedef)
    assert hedef.exists() and hedef.stat().st_size > 10000
    assert not (clip / "pdf" / "kunye_dizi.pdf").exists()               # os.replace ile taşındı

    # mp.build çağrı sözleşmesi: tmp yol "kunye_dizi.pdf" + d-sözlüğü
    assert len(fake.calls) == 1
    yol, d = fake.calls[0]
    assert os.path.basename(yol) == "kunye_dizi.pdf"
    assert set(d.keys()) == BEKLENEN_ANAHTARLAR
    assert d["profile"] == "DİZİ"
    assert d["bolum"] == "14. BÖLÜM"
    assert ("TRT KİMLİK", "1900-0138-0-0014-00-1") in d["specs"]        # meta trt_id dolduruldu
    assert d["cast"][0] == "POLAT ALEMDAR"

    # provenans: kunye_dizi_kaynak.json
    kaynak = json.loads((clip / "pdf" / "kunye_dizi_kaynak.json").read_text(encoding="utf-8"))
    assert kaynak["master_surum"] == 3
    assert kaynak["kunye_kaynagi"] == "master"                          # okuma.kaynak=master_dilim
    assert kaynak["kaynak_haritasi"]["cast"] == "master:v3"
    assert kaynak["diff_ozet"]["kontrol_nedenleri"] == ["test-neden"]


def test_cli_out_parametresi(tmp_path, monkeypatch, capsys):
    clip = tmp_path / "KLIP"
    (clip / "pdf").mkdir(parents=True)
    (clip / "pdf" / "kunye_teslim.md").write_text(MD, encoding="utf-8")
    _cli_dikis(monkeypatch, _master(), _diff(), _okuma())
    monkeypatch.setattr(sbk, "mp", _FakeMp())

    hedef = tmp_path / "cikti" / "ozel.pdf"                             # olmayan klasör → CLI açar
    rc = sbk.main(["--clip", str(clip), "--seri-anahtar", "K", "--bolum-no", "14",
                   "--out", str(hedef)])
    obj = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0
    assert obj["pdf"] == str(hedef)
    assert hedef.exists() and hedef.stat().st_size > 10000


def test_cli_master_hazir_degil_rc2(tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("master hazır değilken akış devam etmemeli")

    monkeypatch.setattr(sbk, "_master_yukle",
                        lambda anahtar: {"durum": "BUILDING", "master_surum": 1})
    monkeypatch.setattr(sbk, "_okuma_yap", boom)
    monkeypatch.setattr(sbk, "_diffle", boom)
    monkeypatch.setattr(sbk, "_uygula_ve_kaydet", boom)
    monkeypatch.setattr(sbk, "mp", types.SimpleNamespace(build=boom))

    rc = sbk.main(["--clip", str(tmp_path), "--seri-anahtar", "X", "--bolum-no", "1"])
    cap = capsys.readouterr()
    obj = json.loads(cap.out.strip().splitlines()[-1])
    assert rc == 2
    assert obj["status"] == "master_hazir_degil"
    assert obj["pdf"] is None
    assert obj["master_surum"] == 1
    assert cap.err.strip()                                              # stderr uyarısı var


def test_cli_sadece_analiz(tmp_path, monkeypatch, capsys):
    clip = tmp_path / "KLIP"
    (clip / "pdf").mkdir(parents=True)
    diff = _diff(kontrol_nedenleri=["Yönetmen master'dan farklı (ilk kez, bölüm 14)"])
    _cli_dikis(monkeypatch, _master(), diff, _okuma())

    def boom(*a, **k):
        raise AssertionError("--sadece-analiz: uygula/kaydet ve render ÇAĞRILMAMALI")

    monkeypatch.setattr(sbk, "_uygula_ve_kaydet", boom)
    monkeypatch.setattr(sbk, "mp", types.SimpleNamespace(build=boom))

    rc = sbk.main(["--clip", str(clip), "--seri-anahtar", "K", "--bolum-no", "14",
                   "--sadece-analiz"])
    obj = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert rc == 0
    assert obj["status"] == "analiz"
    assert obj["pdf"] is None
    assert obj["diff"]["bolum_no"] == 14                                # diff raporu gömülü
    assert obj["kontrol_nedenleri"] == diff["kontrol_nedenleri"]
    assert not (clip / "pdf" / "kunye.pdf").exists()                    # 5-6 atlandı
    assert not (clip / "pdf" / "kunye_dizi_kaynak.json").exists()


# ═══ DUMAN: gerçek render (reportlab varsa) ═══════════════════════════════════════════════════

def test_render_duman_reportlab(tmp_path):
    pytest.importorskip("reportlab")
    d, _ = sbk.birlesik_kunye(_master(), _diff(), _meta(), simdi=SIMDI)
    hedef = tmp_path / "duman_dizi.pdf"
    sbk.mp.build(str(hedef), d)
    assert hedef.exists() and hedef.stat().st_size > 10000              # >10KB gerçek PDF
