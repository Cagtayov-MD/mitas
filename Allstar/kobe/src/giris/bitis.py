"""(c) BİTİŞ ŞELALESİ — giriş jeneriğinin BİTİŞ sınırını düzeltir.

Teşhis (36 film, insan GT'si, 2026-08-17): çıkış detektöründen gelen bitiş
(sinir.bul) 36 filmin 20'sinde ÇOK ERKEN kesiyor — footage-üstü jenerik
aralıklı akar, detektör ilk sessizlikte durur.

Şelale (kalibrasyon: 18 eğitim / 18 sınav filmi, eğitim-sınav değerleri
birbirini teyit etti — ort|Δ| 58 vs 60, ezber yok):

  1. TERS-MOTOR ADAYI (Çağatay fikri, 2026-08-17): çıkış motoru TERS kare
     dizisinde koşulursa ters-zamanda jenerik pencere sonuna yaslanır;
     motorun başlangıç kararı gerçek zamanda jeneriğin BİTİŞİ olur.
     Aday main.py'de hesaplanır ve buraya ENJEKTE edilir — bu modül çıkış
     motorunu import ETMEZ (izolasyon: giriş çıkışın motorunu tanımaz;
     yönlendirme main.py'de). Ateşlendiğinde en güvenilir adaydır
     (20/20 filmde karar, çoğu ±30 kare) ama her filmde ateşlenmez.
  2. SAĞDAN-SOLA KURALI (Çağatay fikri, 2026-08-17): pencerenin sonundan
     geriye doğru ilk KALIN içerik bloğu — "60 karelik pencerede ≥K gerçek
     kredi-içerik karesi" (W=30, K=12). Tek tük izciler (diyalogdaki
     isimler, şarkı sözü) K eşiğini geçemediği için bloğun sağ ucunda durur.
  3. YOĞUN İÇERİK KURTARMASI: sınır motoru hiçbir koşuyu kabul
     etmemişse ama sağdan-sola kuralı kalın bir kredi-içerik bloğu
     bulmuşsa, ``KREDI_YOK`` denmez. Başlangıç 1, bitiş bu bloğun sağ
     ucu olur. Blob/tabela kalkanı gevşetilmez; bağımsız OCR-içerik
     kanıtı ilk sezgisel reddi geçersiz kılar.
  4. SINIR'İN KENDİ BİTİŞİ: hiçbiri sonuç vermezse dokunulmaz.

Başlangıç bu dosyanın işi DEĞİL — o politika sabittir (daima 1, Çağatay
2026-08-17: "geriye dönük kabul, hatta hep 1'den başla").
"""
from __future__ import annotations

import bisect
import re
from pathlib import Path

from giris import havuz

# Kalibrasyon (2026-08-17): W=30 penceresinde K=12 içerik karesi.
# Eğitim yarı seçimi, sınav yarı teyidi — değiştirilirse ölçümle birlikte
# değiştirilmeli (olcum/giris/veri/bitis_kanit + bitis_kalibrasyonu.md).
KURAL_W, KURAL_K = 30, 12


def _kare_no(yol: str) -> int:
    m = re.search(r"(\d+)(?=\.[a-zA-Z]+$)", yol)
    return int(m.group(1)) if m else 1


def sagdan_sola(icerik_kareleri: list[int], w: int = KURAL_W, k: int = KURAL_K,
                son_kare: int | None = None) -> int | None:
    """En sağdaki i öyle ki [i-w, i] aralığında ≥k içerik karesi var.

    Sağdan sola: izci kareler k eşiğini geçemediği için ilk 'kalın' bloğun
    SAĞ ucunda durur — o uç jeneriğin bitişidir. Blok yoksa None."""
    ks = sorted(icerik_kareleri)
    if not ks:
        return None
    baslangic = son_kare if son_kare is not None else ks[-1]
    for i in range(baslangic, w - 1, -1):
        if bisect.bisect_right(ks, i) - bisect.bisect_left(ks, i - w) >= k:
            return i
    return None


def duzelt(b: dict, dizin: str | Path, config: dict | None = None,
           ters_aday: int | None = None) -> dict:
    """sinir.bul() çıktısının bitişini şelaleyle düzelt. Karar sözlüğünü
    yerinde güncelleyip döndürür; kanıta hangi kaynağın kazandığı yazılır.

    `ters_aday`: main.py'de hesaplanan ters-motor bitişi (kare no) — None
    ise motor ateşlenmemiştir, kurala düşülür. `config.giris.bitis_selale
    = false` tüm düzeltmeyi kapatır (sinir'in ham kararı kalır)."""
    g = (config or {}).get("giris", {})
    if not g.get("bitis_selale", True):
        return b

    # Sınır motorunun sezgisel blob kalkanı gerçek bir statik açılış
    # kartını reddedebilir. Bu durumda genel blob eşiğini düşürmek
    # tabela/altyazı yanlış-pozitiflerini de açar. Onun yerine zaten bitiş
    # için kalibre edilmiş bağımsız OCR-içerik kanıtına bak: 30 karelik
    # pencerede en az 12 gerçek kredi karesi varsa "kredi yok" deneme.
    if not b.get("bulundu"):
        ks = [_kare_no(y) for y in havuz.icerik_kareleri(dizin)]
        w = int(g.get("bitis_kural_w", KURAL_W))
        k = int(g.get("bitis_kural_k", KURAL_K))
        r = sagdan_sola(ks, w, k)
        if r is None:
            return b
        b.update({"bulundu": True,
                  "baslangic_kare": 1, "baslangic_sn": 0.0,
                  "bitis_kare": int(r), "bitis_sn": round(int(r) / 2.0, 2)})
        kanit = b.setdefault("kanit", {})
        kanit.update({"sinir_kaynagi": "bitis-kaniti",
                      "bitis_kaynagi": "kural",
                      "bitis_sinir_ham": None,
                      "bitis_icerik_kare_sayisi": len(ks),
                      "bitis_kural_w": w, "bitis_kural_k": k})
        return b

    ham = b.get("bitis_kare")
    kaynak, bit = "sinir", b.get("bitis_kare")
    if ters_aday is not None:
        kaynak, bit = "ters-motor", int(ters_aday)
    else:
        ks = [_kare_no(y) for y in havuz.icerik_kareleri(dizin)]
        r = sagdan_sola(ks, int(g.get("bitis_kural_w", KURAL_W)),
                        int(g.get("bitis_kural_k", KURAL_K)))
        if r is not None:
            kaynak, bit = "kural", r

    if kaynak == "sinir":
        return b                      # düzeltilecek bir şey yok
    b["bitis_kare"] = int(bit)
    b["bitis_sn"] = round(int(bit) / 2.0, 2)   # fps=2 (sinir._DETECT_FPS ile aynı)
    kanit = b.setdefault("kanit", {})
    kanit["bitis_kaynagi"] = kaynak
    kanit["bitis_sinir_ham"] = ham
    return b
