# -*- coding: utf-8 -*-
"""test_dizi_credit_parse.py — dizi modu hub→BolumOkuma adaptörü testleri.

Sözleşme: scripts/dizi_SISTEM.md "BolumOkuma şeması" (BAĞLAYICI).
Hermetik: tüm hub artefaktları tmp_path'e sentetik yazılır; ağ/duckdb/ollama YOK.

Çalıştır:  python -m pytest tests/test_dizi_credit_parse.py -x -q
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import dizi_credit_parse as d


# ─────────────────────────── konuk_ayikla ───────────────────────────

def test_konuk_baslik_varyantlari():
    # TR büyük/küçük, iki-nokta, BÖLÜM OYUNCULARI, İngilizce — hepsi fold ile yakalanır
    for baslik in ("KONUK OYUNCULAR", "Konuk Oyuncular:", "konuk oyuncular",
                   "BÖLÜM OYUNCULARI", "KONUK SANATÇI", "KONUKLAR", "GUEST STARRING"):
        konuklar, kalan = d.konuk_ayikla([baslik, "ALTAN ALKAN", "OKTAY DENER"])
        assert konuklar == ["ALTAN ALKAN", "OKTAY DENER"], baslik
        assert kalan == [], baslik


def test_konuk_bolum_konuklari_basligi():
    # YAMA SÖZLEŞMESİ madde 10: "bolum konuklari" listede — büyük harf,
    # Türkçe karakter (Ö/Ü/İ/ı) ve kenar-noktalama varyantları fold ile yakalanır
    for baslik in ("BÖLÜM KONUKLARI", "Bölüm Konukları:", "bölüm konukları"):
        konuklar, kalan = d.konuk_ayikla([baslik, "ALTAN ALKAN", "OKTAY DENER"])
        assert konuklar == ["ALTAN ALKAN", "OKTAY DENER"], baslik
        assert kalan == [], baslik  # başlık satırı parse_credits'e SIZMAZ


def test_konuk_blogu_rol_basliginda_kesilir():
    lines = ["KONUK OYUNCULAR", "ALTAN ALKAN", "YÖNETMEN", "SAMET POLAT"]
    konuklar, kalan = d.konuk_ayikla(lines)
    assert konuklar == ["ALTAN ALKAN"]
    # rol başlığı VE sonrası kalan satırlarda (parse_credits'e gidecek)
    assert kalan == ["YÖNETMEN", "SAMET POLAT"]


def test_konuk_blogu_sirket_konuk_degil():
    lines = ["KONUK OYUNCULAR", "ABC FİLM YAPIM", "ALTAN ALKAN"]
    konuklar, kalan = d.konuk_ayikla(lines)
    assert konuklar == ["ALTAN ALKAN"]
    assert "ABC FİLM YAPIM" not in konuklar


def test_birden_fazla_konuk_blogu():
    lines = ["KONUK OYUNCULAR", "ALTAN ALKAN", "YÖNETMEN", "SAMET POLAT",
             "BÖLÜM OYUNCULARI", "OKTAY DENER"]
    konuklar, kalan = d.konuk_ayikla(lines)
    assert konuklar == ["ALTAN ALKAN", "OKTAY DENER"]
    assert kalan == ["YÖNETMEN", "SAMET POLAT"]


def test_konuk_ampersand_ve_birlesik_satir_bolunur():
    konuklar, _ = d.konuk_ayikla(["KONUK OYUNCULAR", "ALTAN ALKAN & OKTAY DENER"])
    assert konuklar == ["ALTAN ALKAN", "OKTAY DENER"]


def test_konuk_baslik_yoksa_hicbir_sey_ayiklanmaz():
    lines = ["OYUNCULAR", "POLAT ALEMDAR"]
    konuklar, kalan = d.konuk_ayikla(lines)
    assert konuklar == []
    assert kalan == lines


# ─────────────────────────── stop_kart_suz ───────────────────────────

def test_stop_kart_bolum_sonu_dusuruluyor_no_cikartiliyor_celiski():
    kalan, kart_no, uy = d.stop_kart_suz(["SAMET POLAT", "617. Bölüm Sonu"], 14)
    assert kalan == ["SAMET POLAT"]
    assert kart_no == 617
    assert "BOLUM_NO_CELISKI: kart=617 dosya=14" in uy


def test_stop_kart_bolumun_sonu_varyanti_celiskisiz():
    kalan, kart_no, uy = d.stop_kart_suz(["617. BÖLÜMÜN SONU"], 617)
    assert kalan == []
    assert kart_no == 617
    assert uy == []


def test_stop_kart_devam_edecek_ve_son_dusuyor_isim_dusmuyor():
    lines = ["DEVAM EDECEK", "DEVAM EDECEKTİR", "SON", "SONER YALÇIN"]
    kalan, kart_no, uy = d.stop_kart_suz(lines, None)
    assert kalan == ["SONER YALÇIN"]          # "SON" tam-satır; SONER YALÇIN düşmez
    assert kart_no is None
    assert uy == []


# ─────────────────────────── okuma_topla (hub) ───────────────────────────

_T0 = 1_700_000_000  # deterministik mtime tabanı


def _hub(tmp_path, dilim_lines=None, meta=None, ocr_jobs=None, gemma=None, v4_rapor=None):
    """Sentetik hub klasörü kur. ocr_jobs: [(job_adi, satirlar|None)] — mtime sırası liste sırası."""
    clip = tmp_path / "clip"
    clip.mkdir(exist_ok=True)
    if dilim_lines is not None:
        md = clip / "master_dilim"
        md.mkdir(exist_ok=True)
        (md / "dilim_oneocr.txt").write_text("\n".join(dilim_lines), encoding="utf-8")
        (md / "dilim_oneocr.meta.json").write_text(
            json.dumps(meta or {}, ensure_ascii=False), encoding="utf-8")
    for i, (job, satirlar) in enumerate(ocr_jobs or []):
        jd = clip / "ocr" / job
        jd.mkdir(parents=True, exist_ok=True)
        if satirlar is not None:
            p = jd / "kunye.txt"
            p.write_text("\n".join(satirlar), encoding="utf-8")
            os.utime(str(p), (_T0 + i * 100, _T0 + i * 100))
        os.utime(str(jd), (_T0 + i * 100, _T0 + i * 100))
    if gemma is not None:
        (clip / "gemma_kunye.json").write_text(json.dumps(gemma, ensure_ascii=False), encoding="utf-8")
    if v4_rapor is not None:
        pd = clip / "pdf"
        pd.mkdir(exist_ok=True)
        (pd / "kunye_v4_rapor.json").write_text(json.dumps(v4_rapor, ensure_ascii=False), encoding="utf-8")
    return clip


_DILIM = ["### DILIM-SINIRI 0001 ###",
          "YÖNETMEN", "SAMET POLAT",
          "OYUNCULAR", "POLAT ALEMDAR", "MEMATİ BAŞ",
          "### DILIM-SINIRI 0002 ###",
          "KONUK OYUNCULAR", "Altan Alkan",
          "617. BÖLÜM SONU"]


def test_okuma_topla_dilim_birincil_tam_akis(tmp_path):
    clip = _hub(tmp_path, dilim_lines=_DILIM, meta={"ocr_job": "ocr-0001"},
                ocr_jobs=[("ocr-0001", ["POLAT ALEMDAR"])])
    o = d.okuma_topla(str(clip), 14, trt_id="1900-0138-0-0014-00-1")
    assert o["kaynak"] == "master_dilim"
    assert o["bolum_no"] == 14
    assert o["trt_id"] == "1900-0138-0-0014-00-1"
    assert o["crew"]["Yönetmen"] == ["SAMET POLAT"]
    assert o["cast"] == ["POLAT ALEMDAR", "MEMATİ BAŞ"]     # DILIM-SINIRI satırları sızmadı
    assert o["konuk_acik"] == ["Altan Alkan"]
    assert o["stop_kart_bolum_no"] == 617
    assert "BOLUM_NO_CELISKI: kart=617 dosya=14" in o["uyarilar"]


def test_okuma_topla_konuk_cast_ten_dusulur(tmp_path):
    # cast bölümünde farklı yazımla geçen konuk (name_match) cast'ten düşer
    dilim = ["OYUNCULAR", "Polat Alemdar", "MEMATİ BAŞ",
             "KONUK OYUNCULAR", "POLAT ALEMDAR"]
    clip = _hub(tmp_path, dilim_lines=dilim, meta={"ocr_job": "ocr-0001"},
                ocr_jobs=[("ocr-0001", ["x"])])
    o = d.okuma_topla(str(clip), 3)
    assert o["konuk_acik"] == ["POLAT ALEMDAR"]
    assert o["cast"] == ["MEMATİ BAŞ"]


def test_okuma_topla_bayat_dilim_kare_fallback(tmp_path):
    # meta damgası ocr-0001; en yeni job ocr-0002 → dilim bayat → kunye.txt (kare)
    clip = _hub(tmp_path, dilim_lines=_DILIM, meta={"ocr_job": "ocr-0001"},
                ocr_jobs=[("ocr-0001", ["ESKI SATIR"]),
                          ("ocr-0002", ["YÖNETMEN", "CEM DENIZ"])])
    o = d.okuma_topla(str(clip), 14)
    assert o["kaynak"] == "kare"
    assert o["crew"]["Yönetmen"] == ["CEM DENIZ"]


def test_okuma_topla_fb_kardesi_taze_sayilir(tmp_path):
    # en yeni job 'ocr-0001-fb'; meta damgası 'ocr-0001' → base eşleşir → dilim taze
    clip = _hub(tmp_path, dilim_lines=_DILIM, meta={"ocr_job": "ocr-0001"},
                ocr_jobs=[("ocr-0001-fb", ["POLAT ALEMDAR"])])
    o = d.okuma_topla(str(clip), 617)
    assert o["kaynak"] == "master_dilim"
    assert o["crew"]["Yönetmen"] == ["SAMET POLAT"]
    assert o["uyarilar"] == []           # kart=617 dosya=617 → çelişki yok


def test_okuma_topla_dilim_yok_kare(tmp_path):
    clip = _hub(tmp_path, ocr_jobs=[("ocr-0003", ["YÖNETMEN", "CEM DENIZ"])])
    o = d.okuma_topla(str(clip), 5)
    assert o["kaynak"] == "kare"
    assert o["crew"]["Yönetmen"] == ["CEM DENIZ"]


def test_okuma_topla_hic_artefakt_yok_cokmez(tmp_path):
    clip = tmp_path / "bos"
    clip.mkdir()
    o = d.okuma_topla(str(clip), 5)
    assert o["kaynak"] == "yok"
    assert o["cast"] == [] and o["crew"] == {} and o["konuk_acik"] == []
    assert o["kb_hatti"] == {"yonetmen": [], "yapimci": [], "cast": []}
    assert o["vl"] == {"yonetmen": [], "oyuncular": [], "diger_roller": []}
    assert o["stop_kart_bolum_no"] is None


def test_okuma_topla_gemma_kunye_okunur(tmp_path):
    gemma = {"yonetmen": ["SAMET POLAT"], "oyuncular": ["POLAT ALEMDAR"],
             "diger_roller": [{"rol": "Müzik", "isimler": ["CAN ATİLLA"]}]}
    clip = _hub(tmp_path, gemma=gemma)
    o = d.okuma_topla(str(clip), 1)
    assert o["vl"]["yonetmen"] == ["SAMET POLAT"]
    assert o["vl"]["oyuncular"] == ["POLAT ALEMDAR"]
    assert o["vl"]["diger_roller"] == ["CAN ATİLLA"]   # {rol,isimler} → düz isim listesi


def test_okuma_topla_kb_hatti_v4_rapor_varsa(tmp_path):
    v4 = {"v4": {"yonetmen_list": ["SAMET POLAT"], "yapimci_list": ["OSMAN SINAV"],
                 "cast_list": ["POLAT ALEMDAR"]}}
    clip = _hub(tmp_path, v4_rapor=v4)
    o = d.okuma_topla(str(clip), 1)
    assert o["kb_hatti"] == {"yonetmen": ["SAMET POLAT"], "yapimci": ["OSMAN SINAV"],
                             "cast": ["POLAT ALEMDAR"]}


def test_okuma_topla_bozuk_meta_cokmez_kare_fallback(tmp_path):
    clip = _hub(tmp_path, ocr_jobs=[("ocr-0001", ["YÖNETMEN", "CEM DENIZ"])])
    md = clip / "master_dilim"
    md.mkdir()
    (md / "dilim_oneocr.txt").write_text("YÖNETMEN\nBASKA ISIM", encoding="utf-8")
    (md / "dilim_oneocr.meta.json").write_text("{bozuk json", encoding="utf-8")
    o = d.okuma_topla(str(clip), 2)
    assert o["kaynak"] == "kare"
    assert o["crew"]["Yönetmen"] == ["CEM DENIZ"]
    assert any(u.startswith("DILIM_OKUNAMADI") for u in o["uyarilar"])


# ─────────── CAST-ajans kuralı + VL-dilim fallback (2026-07-09 Çağatay talimatı) ───────────

_VL_DILIM = ["YÖNETMEN", "SAMET POLAT", "cast", "MAVİ FİL",
             "ofis görevlileri", "ERTAN ERDAL", "IŞIK ŞEFİ", "TURGUT PELİT",
             "SES", "CEM ÜNER", "KURGU", "ŞENOL ŞENTÜRK"]  # 12 satır — sparse DEĞİL


def test_cast_ajans_tek_girdi_crew_e_tasinir(tmp_path):
    # dizi jeneriğinde "cast" başlığı altında TEK girdi = casting AJANSI (oyuncu değil)
    clip = _hub(tmp_path, dilim_lines=_VL_DILIM, meta={"ocr_job": "ocr-0001"},
                ocr_jobs=[("ocr-0001", ["x"])])
    o = d.okuma_topla(str(clip), 5)
    assert "MAVİ FİL" not in o["cast"]
    assert o["crew"].get("Cast") == ["MAVİ FİL"]
    assert any(u.startswith("CAST_AJANS: MAVİ FİL") for u in o["uyarilar"])


def test_cast_ajans_cok_girdi_dokunulmaz(tmp_path):
    dilim = ["CAST", "POLAT ALEMDAR", "MEMATİ BAŞ", "YÖNETMEN", "SAMET POLAT",
             "SES", "CEM ÜNER", "KURGU", "ŞENOL ŞENTÜRK", "IŞIK", "TURGUT PELİT"]
    clip = _hub(tmp_path, dilim_lines=dilim, meta={"ocr_job": "ocr-0001"},
                ocr_jobs=[("ocr-0001", ["x"])])
    o = d.okuma_topla(str(clip), 5)
    assert o["cast"] == ["POLAT ALEMDAR", "MEMATİ BAŞ"]
    assert "Cast" not in o["crew"]


def _vl_hub(tmp_path, dilim_lines, png_sayisi=1):
    clip = _hub(tmp_path, dilim_lines=dilim_lines, meta={"ocr_job": "ocr-0001"},
                ocr_jobs=[("ocr-0001", ["x"])])
    for i in range(png_sayisi):
        (clip / "master_dilim" / f"reading_master_runaware_p{i+1:02d}.png").write_bytes(b"\x89PNGtest")
    return clip


def test_vl_dilim_stop_kart_fallback(tmp_path):
    # OneOCR düşük-kontrast bölüm-sonu kartını kaçırdı → GLM (vl_http) okur, no dolar
    cagri = []

    def vl_http(model, prompt, images_b64):
        cagri.append(model)
        return "63. Bölüm Sonu\nyedinumara@fft.net.tl"

    clip = _vl_hub(tmp_path, _VL_DILIM)          # 12 satır ama stop-kart YOK
    o = d.okuma_topla(str(clip), 63, vl_http=vl_http)
    assert cagri, "vl_http hiç çağrılmadı"
    assert o["stop_kart_bolum_no"] == 63
    assert any(u.startswith("STOP_KART_VL: 63") for u in o["uyarilar"])
    assert not any(u.startswith("BOLUM_NO_CELISKI") for u in o["uyarilar"])  # kart=63 dosya=63


def test_vl_dilim_sparse_ek_satirlar(tmp_path):
    # OneOCR 3 satır (sparse<8) → VL satırları ADDITIVE katılır (dedup fold ile)
    def vl_http(model, prompt, images_b64):
        return "YÖNETMEN\nSAMET POLAT\nMÜZİK\nCAN ATİLLA"   # ilk ikisi dedup, digerleri ek

    clip = _vl_hub(tmp_path, ["YÖNETMEN", "SAMET POLAT", "63. Bölüm Sonu"])
    o = d.okuma_topla(str(clip), 63, vl_http=vl_http)
    assert o["crew"].get("Müzik") == ["CAN ATİLLA"]
    assert any(u.startswith("VL_DILIM_EK:") for u in o["uyarilar"])


def test_vl_dilim_gerek_yoksa_cagrilmaz(tmp_path):
    # satır>=8 VE stop-kart mevcut → VL hiç çağrılmaz
    cagri = []

    def vl_http(model, prompt, images_b64):
        cagri.append(1)
        return ""

    clip = _vl_hub(tmp_path, _VL_DILIM + ["63. Bölüm Sonu"])
    d.okuma_topla(str(clip), 63, vl_http=vl_http)
    assert cagri == []


def test_vl_dilim_env_kapali(tmp_path, monkeypatch):
    monkeypatch.setenv("MITAS_DIZI_VL_DILIM", "0")
    cagri = []

    def vl_http(model, prompt, images_b64):
        cagri.append(1)
        return "63. Bölüm Sonu"

    clip = _vl_hub(tmp_path, _VL_DILIM)          # stop-kart yok ama env kapalı
    o = d.okuma_topla(str(clip), 63, vl_http=vl_http)
    assert cagri == []
    assert o["stop_kart_bolum_no"] is None


def test_vl_dilim_hata_yutulur(tmp_path):
    def vl_http(model, prompt, images_b64):
        raise RuntimeError("ollama kapalı")

    clip = _vl_hub(tmp_path, _VL_DILIM)
    o = d.okuma_topla(str(clip), 63, vl_http=vl_http)   # çökmez
    assert any(u.startswith("VL_DILIM_HATA") for u in o["uyarilar"])
