"""Sıralama kusuru geri gelemesin — kulenin en sessiz arızası.

Kaynak motor (harness/master_dup/lebron_james.py:178) klasörü düz
`sorted(glob("*.png"))` ile okuyordu: SÖZLÜK sırası. Üretim ise nat_sort_key
kullanıyordu. Sıfır dolgulu adlarda ikisi aynıdır — bu yüzden fark bugüne
kadar görünmedi. Dolgusuz adda kareler yanlış sırada bağlanır ve master
SESSİZCE bozulur: patlamaz, YANLIŞ OLUR.

Kule "bana klasör göster" dediği için girdinin adlandırmasını seçemez.
Bu test o kapıyı kilitler. GPU/Paddle gerektirmez.
"""
from yukleyici import kareler, nat_sort_key


def _kur(dizin, adlar):
    for a in adlar:
        (dizin / a).write_bytes(b"")
    return dizin


def test_dolgusuz_adlar_dogal_sirada(tmp_path):
    """kare_9 < kare_10 — sözlük sırası bunu TERS verir."""
    _kur(tmp_path, ["kare_1.png", "kare_2.png", "kare_9.png",
                    "kare_10.png", "kare_11.png"])
    assert [p.name for p in kareler(tmp_path)] == [
        "kare_1.png", "kare_2.png", "kare_9.png", "kare_10.png", "kare_11.png"]


def test_sozluk_sirasi_ile_farki_gosterir(tmp_path):
    """Kusurun gerçekten var olduğunun kanıtı — iki sıralama ayrışıyor."""
    _kur(tmp_path, ["kare_9.png", "kare_10.png"])
    dogal = [p.name for p in kareler(tmp_path)]
    sozluk = sorted(p.name for p in tmp_path.glob("*.png"))
    assert dogal == ["kare_9.png", "kare_10.png"]
    assert sozluk == ["kare_10.png", "kare_9.png"]
    assert dogal != sozluk


def test_sifir_dolgulu_adlarda_ikisi_ayni(tmp_path):
    """Üretim adları (c_01113.png, exit_000566.png) sıfır dolgulu.

    Sadakat kapısının dayandığı varsayım budur: düzeltme bu adlarda çıktıyı
    DEĞİŞTİRMEZ. Bu test o varsayımı kanıta çevirir.
    """
    adlar = ["c_00009.png", "c_00010.png", "c_01113.png", "c_01200.png"]
    _kur(tmp_path, adlar)
    dogal = [p.name for p in kareler(tmp_path)]
    sozluk = sorted(p.name for p in tmp_path.glob("*.png"))
    assert dogal == sozluk == adlar


def test_son_sayiya_gore_siralanir():
    """db_compose_master.nat_sort_key: addaki SON sayı anahtardır."""
    assert nat_sort_key("a_2026_kare_3.png") < nat_sort_key("a_1999_kare_7.png")


def test_sayisiz_ad_cokmez(tmp_path):
    _kur(tmp_path, ["kapak.png", "kare_2.png"])
    assert [p.name for p in kareler(tmp_path)] == ["kapak.png", "kare_2.png"]


def test_jpg_de_toplanir(tmp_path):
    _kur(tmp_path, ["k_1.png", "k_2.jpg", "k_3.jpeg"])
    assert len(kareler(tmp_path)) == 3


def test_olmayan_dizin_bos_liste(tmp_path):
    assert kareler(tmp_path / "yok") == []
