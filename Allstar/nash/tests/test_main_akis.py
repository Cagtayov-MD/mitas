"""Akış testleri — üç gerçek doğru duruma çevriliyor mu, kuyruk devam ediyor mu?"""
import json

import cv2
import numpy as np
import pytest

import main
import okuyucu
import senaryo
from sozlesme import Girdi


@pytest.fixture(autouse=True)
def _birim_testinde_legacy_secim(monkeypatch):
    """Eski akış senaryoları Paddle/model istemeden yalnız sözleşmeyi sınar."""
    cfg = main._config()
    cfg["secim"]["strateji"] = "legacy"
    cfg["okuma"]["mod"] = "free_ocr"
    cfg["okuma"]["paddle_ensemble"]["enabled"] = False
    monkeypatch.setattr(main, "_config", lambda: cfg)


def _kareler(dizin, kareler):
    dizin.mkdir(parents=True, exist_ok=True)
    for i, k in enumerate(kareler):
        cv2.imwrite(str(dizin / f"c_{i:05d}.png"), k)
    return dizin


def _iyi(tmp_path, ad="film"):
    return _kareler(tmp_path / ad,
                    senaryo.kart("BIRINCI KART UZUN METIN", 6) +
                    senaryo.kart("XYZW BAMBASKA ICERIK QQ", 6))


def _sor_iyi(p):
    """Sayfa basina FARKLI icerik — gercek jenerikte oldugu gibi. Ayni metni
    her sayfada dondurmek dedup'i tetikler ve tek kartlik bir film taklit eder."""
    n = p.stem
    return (f"YONETMEN AHMET MEHMET VELI OZTURK {n}\n"
            f"GORUNTU YONETMENI AYSE FATMA KARADENIZ {n}\n"
            f"KURGU MUSTAFA KEMAL YILDIRIM ARSLAN {n}\n"
            f"MUZIK JOHN WILLIAMS SYMPHONY ORCHESTRA {n}\n"
            f"YAPIM TRT TURKIYE RADYO TELEVIZYON KURUMU {n}")


def _cikti_json(kok, fid="F1", bolum="cikis"):
    return json.loads((kok / fid / bolum / "nash.json").read_text("utf-8"))


# ── mutlu yol ────────────────────────────────────────────────────────────────

def test_okundu_diske_yazilir(tmp_path):
    d = _iyi(tmp_path)
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", _sor_iyi)
    assert c.durum == "OKUNDU" and c.satirlar
    j = _cikti_json(tmp_path / "out")
    assert j["durum"] == "OKUNDU"
    assert j["kanit"]["havuz"]["kare"] == 12
    assert j["kanit"]["saglik"] == "ok"
    assert (tmp_path / "out" / "F1" / "cikis" / "_TAMAM").is_file()
    assert (tmp_path / "out" / "F1" / "cikis" / "nash.txt").read_text("utf-8").strip()


def test_motor_surumu_ve_sure_yazilir(tmp_path):
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", _sor_iyi)
    assert c.motor_surumu.startswith("nash@") and c.sure_sn >= 0


# ── üç gerçeğin ayrımı ───────────────────────────────────────────────────────

def test_dizin_yok_ariza_girdi_hatasi(tmp_path):
    c = main.tek(Girdi(film_id="F1", kareler=str(tmp_path / "yok")),
                 tmp_path / "out", _sor_iyi)
    assert c.durum == "ARIZA" and c.sinif == "GIRDI_HATASI"


def test_kareler_acilamiyor_ariza_kare_okunamadi(tmp_path):
    d = tmp_path / "bozuk"
    d.mkdir()
    for i in range(3):
        (d / f"c_{i}.png").write_bytes(b"PNG degil")
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", _sor_iyi)
    assert c.durum == "ARIZA" and c.sinif == "KARE_OKUNAMADI"
    assert c.kanit["acilamayan"] == 3


def test_hepsi_iceriksiz_metin_yok_ariza_degil(tmp_path):
    """Bu bir İÇERİK GERÇEĞİ — arıza değil. Bugün üretimde ikisi aynı kutuda."""
    d = _kareler(tmp_path / "duz",
                 [np.full((160, 200), 128, np.uint8) for _ in range(6)])
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", _sor_iyi)
    assert c.durum == "METIN_YOK"
    assert c.sinif is None and not c.satirlar
    assert _cikti_json(tmp_path / "out")["kanit"]["havuz"]["kare"] == 6


def test_model_bos_dondu_metin_yok(tmp_path):
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", lambda p: "")
    assert c.durum == "METIN_YOK"


def test_eski_tamam_detector_cagrilmadan_once_kaldirilir(tmp_path):
    d = _iyi(tmp_path)
    out = tmp_path / "out"
    marker = out / "F1" / "cikis" / "_TAMAM"
    marker.parent.mkdir(parents=True)
    marker.write_text("", encoding="utf-8")
    cfg = main._config()
    cfg["secim"]["strateji"] = "text_run"
    cfg["okuma"]["mod"] = "hybrid"

    def detector(yollar, _ayar):
        assert not marker.exists()
        return ({p.name: {"boxes": [], "lines": []} for p in yollar}, {})

    c = main.tek(Girdi(film_id="F1", kareler=str(d)), out, cfg=cfg,
                 detector=detector)
    assert c.durum == "METIN_YOK"


def test_hybrid_kapali_fallbackte_dusuk_guven_ariza_cikti_bozuk(tmp_path):
    d = _iyi(tmp_path)
    cfg = main._config()
    cfg["secim"]["strateji"] = "text_run"
    cfg["okuma"]["mod"] = "hybrid"
    cfg["okuma"]["deepseek_fallback_enabled"] = False

    def detector(yollar, _ayar):
        return ({p.name: {"boxes": [[.2, .2, .8, .5]], "lines": [{
            "text": "YONETMEN AHMET", "score": .50,
            "box": [.2, .2, .8, .5]}]} for p in yollar}, {})

    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out",
                 cfg=cfg, detector=detector)
    assert c.durum == "ARIZA" and c.sinif == "CIKTI_BOZUK"


def test_hybrid_yalniz_tek_karakter_gurultusu_metin_yok(tmp_path):
    d = _iyi(tmp_path)
    cfg = main._config()
    cfg["secim"]["strateji"] = "text_run"
    cfg["okuma"]["mod"] = "hybrid"
    cfg["okuma"]["deepseek_fallback_enabled"] = False

    def detector(yollar, _ayar):
        return ({p.name: {"boxes": [[.2, .2, .8, .5]], "lines": [{
            "text": "X", "score": .50, "box": [.2, .2, .8, .5]}]}
                 for p in yollar}, {})

    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out",
                 cfg=cfg, detector=detector)
    assert c.durum == "METIN_YOK"


def test_gecersiz_config_yapilandirma_arizasi_yazar(tmp_path):
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", cfg={"secim": "not-a-map"})
    assert c.durum == "ARIZA" and c.sinif == "YAPILANDIRMA"
    assert _cikti_json(tmp_path / "out")["sinif"] == "YAPILANDIRMA"


def test_gecersiz_girdi_override_yapilandirma_arizasi_yazar(tmp_path):
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path)),
                       config={"okuma": "not-a-map"}), tmp_path / "out",
                 cfg=main._config())
    assert c.durum == "ARIZA" and c.sinif == "YAPILANDIRMA"


def test_tum_model_cagrilari_patlayinca_metin_yok_degil_ariza(tmp_path):
    def patla(_p):
        raise TimeoutError("cevap yok")
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", patla)
    assert c.durum == "ARIZA" and c.sinif == "MODEL"
    assert c.kanit["sayfa_basarili_n"] == 0


def test_grounded_tek_gecis_ayni_cevaptan_metin_ve_bbox_uretir(
        tmp_path, monkeypatch):
    d = _iyi(tmp_path)
    cagrilar = []

    def sor(p, prompt=None):
        cagrilar.append((p.name, prompt))
        return ("<|ref|>YONETMEN AHMET MEHMET VELI OZTURK " + p.stem
                + "<|/ref|><|det|>[[10,20,900,100]]<|/det|>")

    cfg = main._config()
    cfg["okuma"]["mod"] = "grounded"
    monkeypatch.setenv("MITAS_OKUMA_V2", "1")
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out", sor,
                 cfg=cfg)
    assert c.durum == "OKUNDU"
    assert len(cagrilar) == c.kanit["secilen_kare"]
    assert all("<|grounding|>" in prompt for _, prompt in cagrilar)
    paket = json.loads((tmp_path / "out" / "F1" / "cikis" /
                        "nash.okuma.json").read_text("utf-8"))
    assert paket["producer"]["strategy"] == "text-run-grounded-ocr"
    assert paket["lines"][0]["evidence"]


def test_auto_okuma_rapor_yoksa_free_ocr_fallback(tmp_path):
    cfg, tani = main._okuma_karari({"mod": "auto", "kalite_raporu": str(
        tmp_path / "yok.json")})
    assert cfg["mod"] == "free_ocr" and cfg["max_new_tokens"] == 2048
    assert tani["sebep"] == "rapor_yok_veya_bozuk"


def test_auto_okuma_rapor_onerisini_uygular(tmp_path):
    rapor = tmp_path / "kapi.json"
    rapor.write_text(json.dumps({"recommendation": {
        "mode": "grounded", "max_new_tokens": 512}}), encoding="utf-8")
    cfg, tani = main._okuma_karari({"mod": "auto", "kalite_raporu": str(rapor)})
    assert cfg["mod"] == "grounded" and cfg["max_new_tokens"] == 512
    assert tani["sebep"] == "kalite_raporu"


def test_tembel_okuyucu_ilk_cagriya_kadar_modeli_kurmaz_ve_bir_kez_kurar():
    sayac = {"kur": 0, "cagri": 0}

    class Sor:
        def __call__(self, deger):
            sayac["cagri"] += 1
            return deger.upper()

        def metrics(self):
            return {"model_cagri_n": sayac["cagri"]}

    def kur():
        sayac["kur"] += 1
        return Sor()

    tembel = main._TembelOkuyucu(kur)
    assert sayac["kur"] == 0 and tembel.metrics() == {}
    assert tembel("a") == "A" and tembel("b") == "B"
    assert sayac["kur"] == 1
    assert tembel.metrics() == {"model_cagri_n": 2}


def test_hybrid_paddle_yeterliyse_deepseek_yuklenmez(tmp_path, monkeypatch):
    d = _iyi(tmp_path)
    cfg = main._config()
    cfg["secim"]["strateji"] = "text_run"
    cfg["okuma"]["mod"] = "hybrid"

    def detector(yollar, _ayar):
        return ({p.name: {"boxes": [[0.2, 0.2, 0.8, 0.5]],
                 "lines": [{"text": "YONETMEN AHMET MEHMET VELI " + p.stem,
                            "score": 0.99, "box": [0.2, 0.2, 0.8, 0.5]}]}
                for p in yollar}, {"paddle_peak_vram_mb": 350})

    monkeypatch.setattr(main, "okuyucu_kur", lambda _cfg: pytest.fail(
        "guvenilir Paddle sonucu DeepSeek yuklememeli"))
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out",
                 cfg=cfg, detector=detector)
    assert c.durum == "OKUNDU"
    assert c.kanit["deepseek_fallback_n"] == 0
    assert c.kanit["paddle_satir_n"] == len(c.satirlar)


def test_hybrid_deepseek_oom_olsa_da_paddle_sonucu_korunur(tmp_path, monkeypatch):
    d = _iyi(tmp_path)
    cfg = main._config()
    cfg["secim"]["strateji"] = "text_run"
    cfg["okuma"]["mod"] = "hybrid"
    cfg["okuma"]["paddle_uzlasma_penceresi"] = 0
    cfg["okuma"]["paddle_film_kabul_min_satir"] = 99
    cfg["okuma"]["deepseek_fallback_enabled"] = True

    def detector(yollar, _ayar):
        return ({p.name: {"boxes": [[0.2, 0.2, 0.8, 0.5]],
                 "lines": [{"text": "YONETMEN AHMET MEHMET VELI " + p.stem,
                            "score": 0.80, "box": [0.2, 0.2, 0.8, 0.5]}]}
                for p in yollar}, {})

    monkeypatch.setattr(main, "okuyucu_kur", lambda _cfg: (_ for _ in ()).throw(
        okuyucu.Bellek("OOM")))
    c = main.tek(Girdi(film_id="F1", kareler=str(d)), tmp_path / "out",
                 cfg=cfg, detector=detector)
    assert c.durum == "OKUNDU"
    assert "OOM" in c.kanit["deepseek_fallback_hatasi"]


# ── arıza sınıfları ──────────────────────────────────────────────────────────

def test_garble_ariza_cikti_bozuk_metin_yok_degil(tmp_path):
    """Elimizdeki metin YANLIŞ — aşağı akışa bırakmak künyeyi zehirler (rodeo)."""
    def sor(p):
        return "\n".join(f"A!@#$%^&{i} B!@#$%^&{i} C!@#$%^&{i} D!@#$%^&{i}"
                         for i in range(8))
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", sor)
    assert c.durum == "ARIZA" and c.sinif == "CIKTI_BOZUK"
    assert c.kanit["saglik"] == "garble_yuksek"


def test_cok_kisa_ariza_degil_icerik_korunur(tmp_path):
    """5 satırlık gerçek bir jenerik ARIZA'ya çevrilemez — sağlık bir BAYRAK."""
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", lambda p: "YONETMEN AHMET")
    assert c.durum == "OKUNDU"
    assert c.kanit["saglik"] == "cok_kisa"      # uyari kanitta, hukum degil
    assert [s["text"] for s in c.satirlar] == ["YONETMEN AHMET"]


def test_oom_ariza_bellek(tmp_path):
    def sor(p):
        raise okuyucu.Bellek("CUDA out of memory")
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", sor)
    assert c.durum == "ARIZA" and c.sinif == "BELLEK"


def test_okuyucu_kurulmadiysa_ariza_model(tmp_path, monkeypatch):
    """Model yüklenemiyorsa kule tahmin etmez, açık ARIZA döner.

    Hata AÇIKÇA zorlanır. 'model kurulu değil' varsayımına yaslanmak yasak:
    model kurulunca (2026-08-14) o testler sessizce GERÇEK GPU koşusuna
    dönüştü — takım 1.5 sn'den 26 sn'ye çıktı ve neyi ölçtüğü belirsizleşti.
    """
    monkeypatch.setattr(main, "okuyucu_kur",
                        lambda cfg: (_ for _ in ()).throw(ImportError("model yok")))
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", None)
    assert c.durum == "ARIZA" and c.sinif == "MODEL"
    # Havuz kaniti ARIZA'da da korunur — nerede durdugumuz gorunur.
    assert c.kanit["havuz"]["kare"] == 12


def test_ariza_da_diske_yazilir(tmp_path):
    main.tek(Girdi(film_id="F1", kareler=str(tmp_path / "yok")),
             tmp_path / "out", _sor_iyi)
    assert (tmp_path / "out" / "F1" / "cikis" / "_TAMAM").is_file()
    assert _cikti_json(tmp_path / "out")["sinif"] == "GIRDI_HATASI"


# ── bölüm ────────────────────────────────────────────────────────────────────

def test_giris_bolumu_calisir_ve_ayri_yazar(tmp_path):
    """Kobe'nin aksine Nash'te giriş desteklenir — engeli yok."""
    d = _iyi(tmp_path)
    c = main.tek(Girdi(film_id="F1", kareler=str(d), bolum="giris"),
                 tmp_path / "out", _sor_iyi)
    assert c.durum == "OKUNDU" and c.bolum == "giris"
    assert (tmp_path / "out" / "F1" / "giris" / "nash.json").is_file()
    assert not (tmp_path / "out" / "F1" / "cikis").exists()


# ── toplu kuyruk ─────────────────────────────────────────────────────────────

def test_toplu_tamam_olani_atlar(tmp_path, monkeypatch):
    girdi = tmp_path / "girdi"
    girdi.mkdir()
    for ad in ("A", "B"):
        _iyi(girdi, ad)
    kok = tmp_path / "out"
    monkeypatch.setattr(main, "okuyucu_kur", lambda cfg: _sor_iyi)

    assert len(main.toplu(girdi, kok)) == 2
    # ikinci kosuda ikisi de _TAMAM — hicbiri yeniden islenmez
    assert main.toplu(girdi, kok) == []


def test_toplu_okuyucu_kurulamazsa_her_filme_ariza_yazar(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "okuyucu_kur",
                        lambda cfg: (_ for _ in ()).throw(ImportError("model yok")))
    girdi = tmp_path / "girdi"
    girdi.mkdir()
    _iyi(girdi, "A")
    sonuc = main.toplu(girdi, tmp_path / "out")
    assert len(sonuc) == 1
    assert sonuc[0].durum == "ARIZA" and sonuc[0].sinif == "MODEL"


def test_toplu_gecersiz_configte_her_filme_yapilandirma_yazar(tmp_path, monkeypatch):
    girdi = tmp_path / "girdi"
    girdi.mkdir()
    _iyi(girdi, "A")
    _iyi(girdi, "B")
    monkeypatch.setattr(main, "_config", lambda: {"secim": "not-a-map"})
    sonuc = main.toplu(girdi, tmp_path / "out")
    assert [c.sinif for c in sonuc] == ["YAPILANDIRMA", "YAPILANDIRMA"]
    assert all((tmp_path / "out" / ad / "cikis" / "_TAMAM").exists()
               for ad in ("A", "B"))


def test_start_herhangi_bir_arizada_sifir_disiyla_biter(monkeypatch):
    monkeypatch.setattr(main, "toplu", lambda *_args, **_kwargs: [
        main.Cikti(film_id="A", durum="METIN_YOK"),
        main.ariza("B", "MODEL", "model yok"),
    ])
    assert main.main(["start", "--input", "/girdi"]) == 2


def test_start_ariza_yoksa_sifirla_biter(monkeypatch):
    monkeypatch.setattr(main, "toplu", lambda *_args, **_kwargs: [
        main.Cikti(film_id="A", durum="METIN_YOK"),
    ])
    assert main.main(["start", "--input", "/girdi"]) == 0


def test_cli_gecersiz_film_id_disariya_yazmaz(tmp_path):
    out = tmp_path / "out"
    assert main.main(["tek", "--kareler", str(tmp_path), "--film-id", "../escape",
                      "--out", str(out)]) == 2
    assert not (tmp_path / "escape").exists()


def test_model_yuklerken_oom_BELLEK_olur_MODEL_degil(tmp_path, monkeypatch):
    """Gerçek koşuda yakalandı (LA SEGUA/giris, 2026-08-14): kart başka bir
    süreç tarafından doluyken kule 'model bozuk' diye rapor ediyordu. OOM'un
    çaresi parça küçültmektir; MODEL'e düşerse o bilgi kaybolur."""
    def patla(cfg):
        raise okuyucu.Bellek("CUDA out of memory")
    monkeypatch.setattr(main, "okuyucu_kur", patla)
    c = main.tek(Girdi(film_id="F1", kareler=str(_iyi(tmp_path))),
                 tmp_path / "out", None)
    assert c.durum == "ARIZA" and c.sinif == "BELLEK"
