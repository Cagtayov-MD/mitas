# -*- coding: utf-8 -*-
"""kunye_cikar birim testleri — doktrin kuralları (2026-07-24)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "harness" / "kunye_kiyas"))
import kunye_cikar as kc  # noqa: E402


def test_etiket_ayni_satir():
    a = kc._alan_yakala(["Directed by John Smith"], "yonetmen")
    assert a and a[0][0] == "John Smith"


def test_etiket_sonraki_satir():
    a = kc._alan_yakala(["DIRECTED BY", "HAL BARWOOD"], "yonetmen")
    assert a and a[0][0] == "HAL BARWOOD"


def test_turkce_etiket():
    a = kc._alan_yakala(["SENARİST ve YÖNETMEN", "TOLGA ÖRNEK"], "yonetmen")
    assert a and a[0][0] == "TOLGA ÖRNEK"


def test_fransizca_mise_en_scene():
    a = kc._alan_yakala(["MISE EN SCÈNE", "FRANÇOIS TRUFFAUT"], "yonetmen")
    assert a and a[0][0] == "FRANÇOIS TRUFFAUT"


def test_disla_asistan():
    assert kc._alan_yakala(["Assistant Director", "John C. Howard"], "yonetmen") == []


def test_disla_monitorizare():
    assert kc._alan_yakala(["Director Monitorizare & Interventie", "Leonard Pallat"],
                           "yonetmen") == []


def test_boilerplate_suzgeci(tmp_path):
    p = tmp_path / "o.txt"
    p.write_text("Thank You for Watching\nGerçek Satır\n#FilmLover\n", encoding="utf-8")
    assert kc.satirlar(p) == ["Gerçek Satır"]


def test_cift_kaynak_guvenli():
    k = kc._alan_karari([("Visar Morina", "c")], [("VISAR MORINA", "g")])
    assert k["guven"] == "guvenli" and k["isim"] == "Visar Morina"


def test_kara_liste_tek_kaynak_supheli():
    k = kc._alan_karari([("John Ford", "c")], [])
    assert k["guven"] == "supheli"


def test_kara_liste_cift_kaynak_aklanir():
    k = kc._alan_karari([("Steven Spielberg", "c")], [("STEVEN SPIELBERG", "g")])
    assert k["guven"] == "guvenli"


def test_celiski_kara_liste_elenir():
    k = kc._alan_karari([("Stephen Sommers", "c")], [("Ridley Scott", "g")])
    assert k["guven"] == "tek_kaynak" and k["isim"] == "Stephen Sommers"


def test_celiski_iki_temiz_aday():
    k = kc._alan_karari([("Fatih Özcan", "c")], [("Ahmet Yılmaz", "g")])
    assert k["guven"] == "celiskili" and len(k["adaylar"]) == 2


def test_noktali_oyuncu_cifti():
    o = kc._oyuncular(["Jesse James... AUDIE MURPHY", "Kit Dalton... TONY CURTIS"])
    assert len(o) == 2 and o[1]["isim"] == "TONY CURTIS"


def test_etiket_satiri_isim_sanilmaz():
    a = kc._alan_yakala(["Directed by", "Produced by MICHAEL SIEGEL"], "yonetmen")
    assert a == []


def test_placeholder_reddedilir():
    a = kc._alan_yakala(["Directed by [Director's Name]"], "yonetmen")
    assert a == []


def test_lehce_rezyseria():
    a = kc._alan_yakala(["REŻYSERIA", "MARIE NOËLLE"], "yonetmen")
    assert a and a[0][0] == "MARIE NOËLLE"


def test_rol_buyuk_isim_cifti():
    o = kc._oyuncular(["Schuyler KIRK DOUGLAS", "Rena SYLVA ROSCINA"])
    assert len(o) == 2 and o[0]["isim"] == "KIRK DOUGLAS"


def test_erken_gorulme_tekrar_dongusunu_yener():
    # uydurma döngü Bay'i 3 kez basar ama gerçek Gilliam ERKEN görünür → Gilliam kazanır
    adaylar = [("Terry Gilliam", "Directed by / Terry Gilliam", 3),
               ("Michael Bay", "Directed by Michael Bay.", 870),
               ("Michael Bay", "Directed by Michael Bay.", 875),
               ("Michael Bay", "Directed by Michael Bay.", 880)]
    t = kc._tekillestir(adaylar)
    assert t[0][0] == "Terry Gilliam"


def test_ses_yonetmeni_dislanır():
    assert kc._alan_yakala(["SES YONETMENİ ONAN KARAGOZLU"], "yonetmen") == []
    a = kc._alan_yakala(["YONETMEN ENDER MIHLAR"], "yonetmen")
    assert a and a[0][0] == "ENDER MIHLAR"


def test_kisa_kirinti_reddedilir():
    assert kc._alan_yakala(["UN FILM DE", "DE"], "yonetmen") == []


def test_musical_direction_dislanır():
    assert kc._alan_yakala(["Musical Direction JOSEPH GERSHENSON"], "yonetmen") == []
    a = kc._alan_yakala(["Directed by RAY ENRIGHT"], "yonetmen")
    assert a and a[0][0] == "RAY ENRIGHT"


def test_direction_de_production_dislanır():
    sats = ["DIRECTION DE PRODUCTION", "JEAN-JOSÉ RICHER", "MISE EN SCÈNE", "FRANÇOIS TRUFFAUT"]
    a = kc._alan_yakala(sats, "yonetmen")
    assert a and a[0][0] == "FRANÇOIS TRUFFAUT"


def test_muzik_alani_musical_direction_yakalar():
    a = kc._alan_yakala(["Musical Direction... JOSEPH GERSHENSON"], "muzik")
    assert a and "GERSHENSON" in a[0][0]


def test_crew_oyuncu_listesine_sizmaz():
    o = kc._oyuncular(["Gaffer MARK WALTHOUR", "Foley RECORDIST JOHN DOE2", "Dana JERRY HARDIN"])
    assert len(o) == 1 and o[0]["isim"] == "JERRY HARDIN"
