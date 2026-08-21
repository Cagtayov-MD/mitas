"""VLM kanalı: derleyicinin 4 kuralı, bos_bildirim desenleri, dejenerasyon
dedektörü, kesin tekrar penceresi, kare aralığı, OOM retry yolu.

GPU/model KULLANMAZ — Motor sahte (mock) nesnelerle değiştirilir. Gerçek
model yolu ``olcum/kos_vlm.py`` ile ayrıca koşulur (kanıt oradadır)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE))
sys.path.insert(0, str(KULE / "src"))

from kanal_vlm import (  # noqa: E402
    BellekHatasi, ModelHatasi, Motor, bos_bildirim, dejenerasyon_isaretle,
    imza, kos, protokol_basligi,
)


# ---------------------------------------------------------------------------
# Yardımcılar — sahte manifest + sahte motor
# ---------------------------------------------------------------------------

def _manifest(n: int, fps: float = 2.0) -> dict:
    return {
        "kare_dizini": "/yok",
        "fps": fps,
        "kare_sayisi": n,
        "kareler": [{"sira": i, "dosya": f"k_{i:05d}.jpg",
                     "kaynak_sn": round((i - 1) / fps, 3), "sha256": f"x{i}",
                     "genislik": 720, "yukseklik": 540}
                    for i in range(1, n + 1)],
    }


def _cfg(**ek) -> dict:
    cfg = {
        "grup": {"kare_sayisi": 8, "bindirme_kare": 1},
        "model": {"yol": "model/qwen3-vl-8b", "dtype": "bfloat16"},
        "uretim": {"do_sample": False, "max_new_tokens": 512},
    }
    cfg.update(ek)
    return cfg


class SahteMotor:
    """Grup sırasına göre önceden yazılmış cevapları veren motor."""

    def __init__(self, cevaplar: list[str]) -> None:
        self.cevaplar = list(cevaplar)
        self.cagrilar: list[list[str]] = []
        self.retry_sayisi = 0
        self.gorsel = {"min_pixels": 200704, "max_pixels": 3211264}
        self.kapatildi = False

    def sor(self, kare_yollari):
        self.cagrilar.append(list(kare_yollari))
        i = len(self.cagrilar) - 1
        return self.cevaplar[i] if i < len(self.cevaplar) else ""

    def uretim_kwargs(self):
        return {"do_sample": False, "max_new_tokens": 512}

    def kapat(self):
        self.kapatildi = True


def _metinler(sonuc) -> list[str]:
    return [s["metin"] for s in sonuc["satirlar"]]


def _sebepler(sonuc, sebep) -> list[str]:
    return [e["metin"] for e in sonuc["elenen"] if e["sebep"] == sebep]


# ---------------------------------------------------------------------------
# KURAL 1 — protokol başlıkları ve altyazı bölgesi
# ---------------------------------------------------------------------------

def test_protokol_basligi_koseli_parantezli_ve_ciplak_tanir():
    assert protokol_basligi("[CREDITS]") == "credits"
    assert protokol_basligi("[SUBTITLES]") == "subtitles"
    assert protokol_basligi("CREDITS") == "credits"
    assert protokol_basligi("Subtitles:") == "subtitles"
    assert protokol_basligi("Yönetmen: TEOMAN TARHAN") is None
    assert protokol_basligi("SERPİL TEZCAN") is None


def test_kural1_basliklar_satir_degildir_ve_altyazi_bolgesi_elenir():
    ham = ("[CREDITS]\n"
           "Yönetmen\n"
           "TEOMAN TARHAN\n"
           "[SUBTITLES]\n"
           "Merhaba, nasilsin?\n"
           "Iyiyim tesekkurler.\n")
    sonuc = kos(_manifest(8), "/yok", _cfg(), motor=SahteMotor([ham]))

    assert _metinler(sonuc) == ["Yönetmen", "TEOMAN TARHAN"]
    assert _sebepler(sonuc, "protokol_basligi") == ["[CREDITS]", "[SUBTITLES]"]
    assert _sebepler(sonuc, "altyazi") == ["Merhaba, nasilsin?", "Iyiyim tesekkurler."]


def test_kural1_altyazi_bolgesi_yeni_credits_basligiyla_kapanir():
    ham = "[SUBTITLES]\nbir altyazi\n[CREDITS]\nKurgu\nAYSE SELEN\n"
    sonuc = kos(_manifest(8), "/yok", _cfg(), motor=SahteMotor([ham]))
    assert _metinler(sonuc) == ["Kurgu", "AYSE SELEN"]
    assert _sebepler(sonuc, "altyazi") == ["bir altyazi"]


# ---------------------------------------------------------------------------
# KURAL 2 — bos_bildirim (KANARYA BULGUSU 2, gerçek metinle)
# ---------------------------------------------------------------------------

GERCEK_BOS_BILDIRIM = ("There is no visible credit text in the provided images. "
                       "The images are entirely black…")


def test_kural2_gercek_kanarya_bildirimi_kredi_satiri_sayilmaz():
    """gt_dizi/pastane/cikis_referans_8b.txt'te bu satır künye gibi yazılmıştı."""
    assert bos_bildirim(GERCEK_BOS_BILDIRIM)
    sonuc = kos(_manifest(8), "/yok", _cfg(),
                motor=SahteMotor([f"Yapım\nTEOMAN TARHAN\n{GERCEK_BOS_BILDIRIM}\n"]))
    assert _metinler(sonuc) == ["Yapım", "TEOMAN TARHAN"]
    assert _sebepler(sonuc, "bos_bildirim") == [GERCEK_BOS_BILDIRIM]
    # Ham cevap DOKUNULMAMIŞ olarak durur.
    assert GERCEK_BOS_BILDIRIM in sonuc["gruplar"][0]["ham_metin"]


@pytest.mark.parametrize("satir", [
    "There is no visible credit text in the provided images.",
    "There are no credits in these frames.",
    "No visible text.",
    "I cannot transcribe the text in these images.",
    "I'm sorry, I can't help with that.",
    "I’m sorry, but the images are entirely black.",   # tipografik kesme imi
    "Unable to read the credits.",
    "The images are entirely black.",
    "Görüntüde görünür bir yazı yok.",
    "Karelerde metin bulunamadı.",
    "YAZI YOK",
    "NO TEXT",
    "N/A",
])
def test_kural2_bos_bildirim_desenleri(satir):
    assert bos_bildirim(satir)


@pytest.mark.parametrize("satir", [
    "Yönetmen: TEOMAN TARHAN",
    "SERPİL TEZCAN",
    "Görüntü Yönetmeni",
    "Kadayıf Erdal—ERHAN TUNA",
    "Yapım Koordinatörü: Yılmaz Erdoğan",
    "Işık / ÖZER MOTAN",
])
def test_kural2_gercek_kredi_satirlari_bildirim_sayilmaz(satir):
    assert not bos_bildirim(satir)


def test_kural2_uzun_duzyazi_iki_cumleli_ise_elenir_kisa_ise_kalir():
    uzun = ("The credits appear to be scrolling upward across the frame. "
            "Some of the text is partially cut off at the edges.")
    assert len(uzun) > 80 and bos_bildirim(uzun)
    # 80 karakterden uzun ama TEK cümle → kredi olabilir, ELENMEZ.
    tek_cumle = "Yapım Koordinatörü ve Yapım Direktörü olarak görev alan kişiler " \
                "aşağıda listelenmiştir"
    assert len(tek_cumle) > 80 and not bos_bildirim(tek_cumle)


# ---------------------------------------------------------------------------
# KURAL 3 — kesin tekrar penceresi (bulanık eleme YOK)
# ---------------------------------------------------------------------------

def test_kural3_pencere_icindeki_kesin_tekrar_duser_ilk_grup_kaydiyla():
    g1 = "Yönetmen\nTEOMAN TARHAN\n"
    g2 = "TEOMAN TARHAN\nKurgu\n"          # bindirmeden gelen gerçek tekrar
    sonuc = kos(_manifest(15), "/yok", _cfg(), motor=SahteMotor([g1, g2]))
    assert _metinler(sonuc) == ["Yönetmen", "TEOMAN TARHAN", "Kurgu"]
    dusen = [e for e in sonuc["elenen"] if e["sebep"] == "kesin_tekrar"]
    assert len(dusen) == 1
    assert dusen[0]["metin"] == "TEOMAN TARHAN"
    assert dusen[0]["ilk_grup"] == 0 and dusen[0]["grup_no"] == 1


def test_kural3_pencere_disina_cikan_tekrar_yeniden_kabul_edilir():
    dolgu = "\n".join(f"Satir {i}" for i in range(1, 13))     # 12 satır = pencere
    ham = f"AYNI SATIR\n{dolgu}\nAYNI SATIR\n"
    sonuc = kos(_manifest(8), "/yok", _cfg(), motor=SahteMotor([ham]))
    assert _metinler(sonuc).count("AYNI SATIR") == 2
    assert not _sebepler(sonuc, "kesin_tekrar")


def test_kural3_bulanik_eleme_yok_ahmat_ile_ahmet_iki_ayri_adaydir():
    sonuc = kos(_manifest(8), "/yok", _cfg(), motor=SahteMotor(["Ahmat\nAhmet\n"]))
    assert _metinler(sonuc) == ["Ahmat", "Ahmet"]


def test_kural3_imza_yalniz_bosluk_ve_buyuk_kucuk_farkini_yok_sayar():
    assert imza("  TEOMAN   TARHAN ") == imza("teoman tarhan")
    assert imza("YETİM") != imza("YETIM")        # diakritik KATLANMAZ


def test_kural3_pencere_sifirsa_tekrar_elemesi_kapanir():
    ham = "AYNI\nAYNI\n"
    sonuc = kos(_manifest(8), "/yok", _cfg(derleyici={"kesin_tekrar_penceresi": 0}),
                motor=SahteMotor([ham]))
    assert _metinler(sonuc) == ["AYNI", "AYNI"]


# ---------------------------------------------------------------------------
# KURAL 4 — dejenerasyon dedektörü (gerçek Yılmaz Erdoğan zinciriyle)
# ---------------------------------------------------------------------------

GERCEK_ZINCIR = [
    "Yapım Koordinatörü: Yılmaz Erdoğan",
    "Yapım Direktörü: Yılmaz Erdoğan",
    "Yapım Müdürü: Yılmaz Erdoğan",
    "Yapım Sorumlusu: Yılmaz Erdoğan",
    "Yapım Ekibi: Yılmaz Erdoğan",
    "Yapım Destek: Yılmaz Erdoğan",
]


def test_kural4_gercek_kanarya_zinciri_isaretlenir_ama_SILINMEZ():
    """KANARYA BULGUSU 1: ekranda HİÇ olmayan bir isim 10 kez çoğaltılmıştı."""
    sonuc = kos(_manifest(8), "/yok", _cfg(),
                motor=SahteMotor(["\n".join(GERCEK_ZINCIR)]))
    # Silme YOK — hepsi çıktıda duruyor (Nash dersi: yok etme, düşür).
    assert _metinler(sonuc) == GERCEK_ZINCIR
    assert all(s["dejenerasyon"] for s in sonuc["satirlar"])
    assert sonuc["kanit"]["dejenerasyon_satir"] == len(GERCEK_ZINCIR)


def test_kural4_normal_jenerik_isaretlenmez():
    """Ardışık FARKLI roller — yanlış pozitif olmamalı."""
    normal = ["Yönetmen", "TEOMAN TARHAN", "Görüntü Yönetmeni", "ÖZER MOTAN",
              "Kurgu", "AYŞE SELEN", "Müzik", "SERPİL TEZCAN"]
    sonuc = kos(_manifest(8), "/yok", _cfg(), motor=SahteMotor(["\n".join(normal)]))
    assert not any(s["dejenerasyon"] for s in sonuc["satirlar"])
    assert sonuc["kanit"]["dejenerasyon_satir"] == 0


def test_kural4_zincir_esikten_kisaysa_isaretlenmez():
    """3 satırlık benzer dizi zincir eşiğinin (4) altında — işaretlenmez."""
    satirlar = [{"metin": m} for m in GERCEK_ZINCIR[:3]]
    assert dejenerasyon_isaretle(satirlar) == 0
    assert not any(s["dejenerasyon"] for s in satirlar)


def test_kural4_zincir_tam_esikte_isaretlenir():
    satirlar = [{"metin": m} for m in GERCEK_ZINCIR[:4]]
    assert dejenerasyon_isaretle(satirlar) == 4


def test_kural4_zincir_disindaki_satirlar_temiz_kalir():
    karisik = ["Yönetmen", "TEOMAN TARHAN", *GERCEK_ZINCIR, "Kurgu", "AYŞE SELEN"]
    satirlar = [{"metin": m} for m in karisik]
    dejenerasyon_isaretle(satirlar)
    isaretli = [s["metin"] for s in satirlar if s["dejenerasyon"]]
    assert isaretli == GERCEK_ZINCIR


def test_kural4_her_satir_dejenerasyon_alani_tasir():
    """Şema tutarlılığı — birleştirici .get() yapmak zorunda kalmasın."""
    sonuc = kos(_manifest(8), "/yok", _cfg(), motor=SahteMotor(["Yönetmen\nX\n"]))
    assert all("dejenerasyon" in s for s in sonuc["satirlar"])


# ---------------------------------------------------------------------------
# Kare aralığı / gruplama / faz
# ---------------------------------------------------------------------------

def test_kare_araligi_ve_saniyeler_gruptan_dogru_turer():
    sonuc = kos(_manifest(15), "/yok", _cfg(), motor=SahteMotor(["A\n", "B\n"]))
    a, b = sonuc["satirlar"]
    assert a["kare_araligi"] == [1, 8] and a["grup_no"] == 0
    assert a["ilk_sn"] == 0.0 and a["son_sn"] == 3.5        # (8-1)/2
    assert b["kare_araligi"] == [8, 15] and b["grup_no"] == 1
    assert b["ilk_sn"] == 3.5


def test_faz_kaydirma_ilk_kareleri_disarida_birakir():
    sonuc0 = kos(_manifest(20), "/yok", _cfg(), faz=0, motor=SahteMotor(["A\n"] * 5))
    sonuc4 = kos(_manifest(20), "/yok", _cfg(), faz=4, motor=SahteMotor(["A\n"] * 5))
    assert sonuc0["gruplar"][0]["kare_araligi"] == [1, 8]
    assert sonuc4["gruplar"][0]["kare_araligi"] == [5, 12]
    assert sonuc0["faz"] == 0 and sonuc4["faz"] == 4
    assert sonuc0["kanit"]["faz"] == 0 and sonuc4["kanit"]["faz"] == 4


def test_kare_yollari_dosya_adindan_kurulur_indeks_aritmetigiyle_degil():
    """Kare dizini yolunda ``sira`` ARDIŞIK OLMAYABİLİR — eşleme sözlükten."""
    manifest = _manifest(8)
    manifest["kareler"][3]["sira"] = 40           # boşluklu numaralandırma
    manifest["kareler"][3]["dosya"] = "k_00040.jpg"
    motor = SahteMotor(["A\n"])
    kos(manifest, "/kok", _cfg(), motor=motor)
    assert motor.cagrilar[0][3] == "/kok/k_00040.jpg"


def test_ham_cevap_saklanir_ve_sha256_esler():
    import hashlib
    ham = "Yönetmen\nTEOMAN TARHAN\n"
    sonuc = kos(_manifest(8), "/yok", _cfg(), motor=SahteMotor([ham]))
    g = sonuc["gruplar"][0]
    assert g["ham_metin"] == ham                  # DEĞİŞTİRİLMEDEN
    assert g["ham_sha256"] == hashlib.sha256(ham.encode()).hexdigest()


def test_kanit_alanlari_eksiksiz():
    sonuc = kos(_manifest(15), "/yok", _cfg(), motor=SahteMotor(["A\n", "B\n"]))
    k = sonuc["kanit"]
    for alan in ("kanal", "faz", "model_yolu", "model_indeks_sha256",
                 "istem_sha256", "recete", "grup_sayisi", "sure_sn",
                 "vram_tepe", "retry_sayisi", "elenen_sebep"):
        assert alan in k, alan
    assert k["grup_sayisi"] == 2
    assert k["recete"]["kare_sayisi"] == 8 and k["recete"]["bindirme_kare"] == 1
    assert k["recete"]["uretim"]["do_sample"] is False


def test_istem_sha256_olculmus_istemi_kilitler():
    """İstem sessizce değişirse bu hash değişir — %91'in geldiği istem budur."""
    import hashlib

    from kanal_vlm import ISTEM
    beklenen = hashlib.sha256(ISTEM.encode()).hexdigest()
    sonuc = kos(_manifest(8), "/yok", _cfg(), motor=SahteMotor(["A\n"]))
    assert sonuc["kanit"]["istem_sha256"] == beklenen
    assert ISTEM.startswith("Transcribe ONLY literally visible credit text")
    assert "Turkish dotted i" in ISTEM


def test_kendi_motorunu_kuran_kos_sonunda_kapatir(monkeypatch):
    import kanal_vlm
    sahte = SahteMotor(["A\n"])
    monkeypatch.setattr(kanal_vlm, "Motor", lambda *a, **k: sahte)
    kos(_manifest(8), "/yok", _cfg())
    assert sahte.kapatildi, "kos() kendi kurdugu motoru kapatmali (OCR GPU isteyecek)"


def test_disaridan_verilen_motor_kapatilmaz():
    """Toplu koşuda model BİR KEZ yüklenir; kos() onu kapatmamalı."""
    sahte = SahteMotor(["A\n"])
    kos(_manifest(8), "/yok", _cfg(), motor=sahte)
    assert not sahte.kapatildi


def test_bos_cevap_cokmez_sifir_satir_uretir():
    sonuc = kos(_manifest(8), "/yok", _cfg(), motor=SahteMotor([""]))
    assert sonuc["satirlar"] == []
    assert sonuc["gruplar"][0]["ham_metin"] == ""


# ---------------------------------------------------------------------------
# OOM retry yolu — GPU'suz, sahte torch/model ile
# ---------------------------------------------------------------------------

class _SahteOOM(RuntimeError):
    """torch.cuda.OutOfMemoryError'ın testteki karşılığı."""


def _oom_motoru(patlama_sayisi: int, monkeypatch) -> Motor:
    """``patlama_sayisi`` kez OOM atıp sonra başarılı olan bir Motor."""
    m = Motor("model/yok")
    m.model, m.islemci = object(), object()      # yukle() çağrılmasın
    monkeypatch.setattr(Motor, "_oom_mu", staticmethod(
        lambda e: isinstance(e, _SahteOOM) or "out of memory" in str(e).lower()))
    monkeypatch.setattr(Motor, "bosalt", staticmethod(lambda: None))
    monkeypatch.setattr("kanal_vlm.time.sleep", lambda s: None)

    kalan = {"n": patlama_sayisi}

    def sahte_uret(self, yollar):
        if kalan["n"] > 0:
            kalan["n"] -= 1
            raise _SahteOOM("CUDA out of memory")
        return "Yönetmen\n"

    monkeypatch.setattr(Motor, "_uret", sahte_uret)
    return m


def test_oom_bir_kez_yeniden_denenir_ve_basarili_olur(monkeypatch):
    m = _oom_motoru(1, monkeypatch)
    assert m.sor(["a.jpg"]) == "Yönetmen\n"
    assert m.retry_sayisi == 1


def test_oom_ikinci_kez_de_olursa_BellekHatasi(monkeypatch):
    m = _oom_motoru(2, monkeypatch)
    with pytest.raises(BellekHatasi):
        m.sor(["a.jpg"])
    assert m.retry_sayisi == 1, "yalniz BİR kez yeniden denenmeli"


def test_oom_sonrasi_daha_az_kareyle_sessizce_denenmez(monkeypatch):
    """Reçete sessizce değişirse sonuç ÖLÇÜLEMEZ olur — retry AYNI kare setiyle."""
    m = _oom_motoru(1, monkeypatch)
    gorulen: list[list[str]] = []
    ozgun = Motor._uret

    def izle(self, yollar):
        gorulen.append(list(yollar))
        return ozgun(self, yollar)

    monkeypatch.setattr(Motor, "_uret", izle)
    m.sor(["a.jpg", "b.jpg", "c.jpg"])
    assert len(gorulen) == 2
    assert gorulen[0] == gorulen[1] == ["a.jpg", "b.jpg", "c.jpg"]


def test_oom_disi_hata_ModelHatasina_cevrilir_ve_yeniden_denenmez(monkeypatch):
    m = Motor("model/yok")
    m.model, m.islemci = object(), object()
    cagri = {"n": 0}

    def patla(self, yollar):
        cagri["n"] += 1
        raise ValueError("beklenmedik")

    monkeypatch.setattr(Motor, "_uret", patla)
    with pytest.raises(ModelHatasi):
        m.sor(["a.jpg"])
    assert cagri["n"] == 1 and m.retry_sayisi == 0


def test_retry_sayisi_kanita_yazilir():
    class RetryliMotor(SahteMotor):
        def sor(self, yollar):
            self.retry_sayisi += 1          # koşu sırasında OOM olmuş gibi
            return super().sor(yollar)

    sonuc = kos(_manifest(8), "/yok", _cfg(), motor=RetryliMotor(["A\n"]))
    assert sonuc["kanit"]["retry_sayisi"] == 1


def test_uretim_kwargs_greedyde_ornekleme_ayarlarini_dusurur():
    m = Motor("model/yok", uretim={"do_sample": False, "temperature": 0.3,
                                    "top_p": 0.9, "max_new_tokens": 512})
    kw = m.uretim_kwargs()
    assert kw["do_sample"] is False and kw["max_new_tokens"] == 512
    assert "temperature" not in kw and "top_p" not in kw


def test_model_yoksa_ModelHatasi():
    with pytest.raises(ModelHatasi):
        Motor("/olmayan/model/yolu").yukle()


def test_kapat_modeli_birakir():
    m = Motor("model/yok")
    m.model, m.islemci = object(), object()
    m.kapat()
    assert m.model is None and m.islemci is None


# ---------------------------------------------------------------------------
# İzolasyon — bu modül bölüm/sözleşme bilmez (PLAN §1, Kobe kanunu)
# ---------------------------------------------------------------------------

def test_modul_sozlesmeyi_ice_aktarmaz():
    kaynak = (KULE / "src" / "kanal_vlm.py").read_text(encoding="utf-8")
    assert "import sozlesme" not in kaynak and "from sozlesme" not in kaynak


def test_kos_bolum_parametresi_almaz():
    import inspect
    assert "bolum" not in inspect.signature(kos).parameters
