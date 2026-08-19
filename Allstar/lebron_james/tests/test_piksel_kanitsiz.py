"""PİKSEL KANITI — kalkan artık SİLMİYOR, işaretliyor (Çağatay 2026-08-20).

Tarihçe iki ölçümden ibaret, ikisi de gerçek:

  2026-07-31 — kalkan kondu: kutu sayısı 0 iken deepseek boş bantta '- 1'
  listesi uyduruyordu. Piksel son sözü söylesin dendi, satırlar atıldı.

  2026-08-20 — kalkanın gerçek içeriği de yediği ölçüldü: İZ PEŞİNDE girişinde
  derleyici 88 kareyi 595 piksele çökertti, model o bulanık masterdan
  'GULF KARAT' (= GÜLER KARAMAN) okudu, kalkan bunu uydurma sayıp sildi ve
  kule METIN_YOK yazdı. Bir DERLEME ARIZASI, 'bu jenerikte yazı yoktu'
  cevabına dönüştü.

Karar: satır SİLİNMEZ, `piksel_kanitsiz` damgası taşır. Kayıp geri gelmez,
işaret geri alınabilir. Aşağı akıştaki güven katmanı damgalı satırı düşük
güvenle değerlendirir — düşük güvenli satır, kayıp satır değildir.

Aynı ders bu fonksiyonun içinde zaten yazılıydı (2026-08-15, tüm bantlar
patlayınca): "ARIZA sessizce içerik gerçeğine dönüşemez." Kalkan yolunda o
delik açık kalmıştı.
"""
import sys
from pathlib import Path

KULE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KULE / "src"))

from okuyucu import oku  # noqa: E402


def _sor_sabit(metin):
    return lambda p: metin


def test_kutusuz_bantta_satir_SILINMEZ(tmp_path):
    """IZ PESINDE vakasi: kutu yok ama model gercek isim okumus."""
    b = tmp_path / "bant_000.png"
    b.write_bytes(b"x")
    r = oku([b], _sor_sabit("GULF KARAT"), kutu_say=lambda p: 0)
    assert r["satirlar"] == ["GULF KARAT"]


def test_kutusuz_satir_DAMGALANIR(tmp_path):
    b = tmp_path / "bant_000.png"
    b.write_bytes(b"x")
    r = oku([b], _sor_sabit("GULF KARAT"), kutu_say=lambda p: 0)
    assert r["satir_kaynaklari"][0]["piksel_kanitsiz"] is True
    assert r["piksel_kanitsiz_n"] == 1


def test_kutulu_satir_damgasiz(tmp_path):
    """Regresyon: piksel kaniti olan satir eskisi gibi temiz gecer."""
    b = tmp_path / "bant_000.png"
    b.write_bytes(b"x")
    r = oku([b], _sor_sabit("GÜLER KARAMAN"), kutu_say=lambda p: 3)
    assert r["satirlar"] == ["GÜLER KARAMAN"]
    assert r["satir_kaynaklari"][0]["piksel_kanitsiz"] is False
    assert r["piksel_kanitsiz_n"] == 0


def test_kutu_motoru_yoksa_hukum_verilmez(tmp_path):
    """Regresyon: kutu_say None ise kalkan sessizce acilmaz."""
    b = tmp_path / "bant_000.png"
    b.write_bytes(b"x")
    r = oku([b], _sor_sabit("GÜLER KARAMAN"), kutu_say=None)
    assert r["satirlar"] == ["GÜLER KARAMAN"]
    assert r["kutu_durum"] == "yok"


def test_gevezelik_hala_elenir(tmp_path):
    """Regresyon: piksel kalkani gevsedi diye ONEK filtreleri gevsemez."""
    b = tmp_path / "bant_000.png"
    b.write_bytes(b"x")
    r = oku([b], _sor_sabit("I cannot read the text in this image"),
            kutu_say=lambda p: 0)
    assert r["satirlar"] == []
    assert r["elenen"] and r["elenen"][0]["sebep"] == "gevezelik"
