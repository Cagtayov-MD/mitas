"""Jenerik başlangıç tespiti — TEK MOTOR: tespit_v5.

Tasarım (v5): aday kutu-koşuları (credit_box.kutu_serisi, PaddleOCR det) → her
adayı OCR-içerikle (credit_content) 'gerçekten isim-listesi mi' doğrula →
son-çapa + scroll ağırlıklı `joint` skoruyla en iyi adayı seç → statik-tip
koşularda içerik-çapalı budama/geri-genişletme, scroll-tip koşularda kart→
scroll geri-tarama + şirket-kartı ileri-budaması → hiçbir aday geçemezse
`_scroll_kurtarma` son-çare yolu ya da `kredi_yok`. Girdi: c_0001.png ...
sıralı kare klasörü. Çıktı: `Sonuc` (start_frame, yöntem, güven, notlar, seri).
OCR bu sürümde ANA ayırıcı (v1'deki "OCR yok" tasarımı terk edildi — bkz.
aşağıdaki tarihçe).

ÖNCEDEN BÖYLEYDİK, ARTIK DEĞİLİZ (2026-07-29, söküm öncesi commit 7b0a46f):
Bu dosya üç nesil dedektör taşıyordu — v3 (`tespit`, salt CV: scroll dy +
ızgara/metin-satır skorları, OCR YOK) ve v4 (`tespit_v4`, kutu-sinyali ana
ayırıcı + opsiyonel VLM tie-breaker doğrulayıcısı) artık YOK. Çağatay'ın
tek-motor kararıyla (2026-07-29) sökülmüşlerdir: ikisi de üretimde
ÇAĞRILMIYORDU (yalnız bu paketteki bir ölçüm/deney betiğinin ölçtüğü kod
yoluydu, o betik de kendisi kırıktı — scratchpad'e bağlı sabit bir yola
bağımlıydı, o dizin artık yok — yani ölçtükleri sinyal zaten güvenilmezdi).
`tespit_v5` tek gerçek/canlı yol; ölçülen kapı (110 film) yalnız v5
üzerinden alınıyor. Aynı söküm turunda v4'ün VLM tie-breaker'ı ve az önce
bahsedilen kırık ölçüm betiği de (ilişkili bir deney dizini dahil) ayrıca
kaldırıldı (bkz. commit mesajı).

Kafa karışıklığı için önemli ayrım: bu dosyadaki "kutu" sinyali salt-CV bir
kart-varlığı tespiti (credit_box, ısıl OCR-det) — jeneriğin GERÇEK içeriğinin
CV-KARŞILAŞTIRMA motoru (frame-pool arasında görsel benzerlik/eşleştirme) bu
dosyada DEĞİL, `core/pipelines/ocr/jenerik_frame_pool_detector.detect_frame_dir`
içinde yaşıyor ve `scripts/jenerik_start_eval.py` onu kullanıyor — o motor bu
söküm turunda DOKUNULMADI.
"""
from __future__ import annotations

import difflib
import glob
import os
import re
from dataclasses import dataclass, field

import numpy as np
from PIL import Image


# ── kare yükleme ─────────────────────────────────────────────────────────
def _kare_no(yol: str) -> int:
    """Dosya adından mutlak kare numarası (c_0027.png → 27). Klasörler c_0001'den
    başlamayabilir (BAJA c_0332, HANNA c_0018) — GT mutlak numara kullanıyor."""
    import re as _re
    m = _re.search(r"(\d+)(?=\.[a-zA-Z]+$)", yol)
    return int(m.group(1)) if m else 1


def kareler(dizin: str) -> list[str]:
    g = sorted(glob.glob(os.path.join(dizin, "*.png")))
    if not g:
        g = sorted(glob.glob(os.path.join(dizin, "*.jpg")))
    return g


def _gri(p: str, W: int = 320) -> np.ndarray:
    im = Image.open(p).convert("L")
    if im.width > W:
        im = im.resize((W, int(im.height * W / im.width)), Image.BILINEAR)
    return np.asarray(im, dtype=np.float32)


# ── head-switching bandı tespiti ─────────────────────────────────────────
def head_band_kirp(gri_kareler: list[np.ndarray], ornekle: int = 20) -> int:
    """VHS kafa-anahtarlama bandı: alt kenarda TÜM karelerde parlak/gürültülü
    satır grubu. Yüksekliğini döndür (kırpılacak alt piksel). Yoksa 0.

    Kör 30px yerine: alttan yukarı, satır-varyansı tüm karelerde anormal yüksekse
    (statik gürültü bandı) kırp. Konsey: 480p'de kör 30px agresif."""
    if not gri_kareler:
        return 0
    n = min(ornekle, len(gri_kareler))
    idx = np.linspace(0, len(gri_kareler) - 1, n).astype(int)
    yig = np.stack([gri_kareler[i] for i in idx])  # (n,H,W)
    h = yig.shape[1]
    # her satırın kareler-arası std'si — band satırları kareden kareye çok oynar
    satir_std = yig.std(axis=0).mean(axis=1)  # (H,)
    taban = np.median(satir_std[: int(h * 0.7)])  # üst %70 referans
    band = 0
    for y in range(h - 1, int(h * 0.85), -1):
        if satir_std[y] > taban * 3.0 + 1.0:
            band = h - y
        else:
            break
    return min(band, int(h * 0.12))


# ── dy: satır-profili çapraz-korelasyon ──────────────────────────────────
def dy_cift(a: np.ndarray, b: np.ndarray, max_shift: int = 40) -> tuple[int, float]:
    """İki karenin dikey kayması + korelasyon gücü."""
    pa = a.mean(axis=1)
    pb = b.mean(axis=1)
    pa = pa - pa.mean()
    pb = pb - pb.mean()
    na = np.linalg.norm(pa)
    nb = np.linalg.norm(pb)
    if na < 1e-6 or nb < 1e-6:
        return 0, 0.0
    en = (0, -1.0)
    for s in range(-max_shift, max_shift + 1):
        if s >= 0:
            x, y = pa[s:], pb[: len(pb) - s] if s else pb
        else:
            x, y = pa[: len(pa) + s], pb[-s:]
        m = min(len(x), len(y))
        if m < 40:
            continue
        r = float((x[:m] * y[:m]).sum() / (np.linalg.norm(x[:m]) * np.linalg.norm(y[:m]) + 1e-9))
        if r > en[1]:
            en = (s, r)
    return en


# ── ana dedektör ─────────────────────────────────────────────────────────
@dataclass
class Sonuc:
    start_frame: int
    yontem: str
    guven: float
    dy_medyan: float = 0.0
    notlar: str = ""
    seri: dict = field(default_factory=dict)
    # Dalga-2 teşhis alanları (2026-07-29, katkısal — hepsi DEFAULT'lu, geriye
    # uyumluluk bozulmaz). kredi_yok/kare_yok dönüşlerinde default'ta kalırlar;
    # yalnız tespit_v5'in BAŞARILI (kredi bulunan) dönüş bloğu doldurur.
    tip: str = ""
    scroll_orani: float = 0.0
    ardisik_scroll: int = 0
    son_capa: float = 0.0
    aday_sayisi: int = 0


def _statik_icerik_onset(g: list[str], idx: list[int], a: int, b: int,
                          adim: int = 2, azami_ileri: int = 30, azami_geri: int = 120
                          ) -> tuple[int, str]:
    """Statik-tip (scroll-dışı) kazanan koşuda içerik-çapalı onset (T5).

    Görev 5: koşu başı sık sık kredi-DIŞI metin taşır (epilog/ara-yazı/stüdyo
    kartı — atlas kanıtı: ERKEN_METIN vakaları KNUTE/TESS/KIZIL_HAYAT/...).
    Koşu sınırını onset saymak yerine İÇERİKTEN al:
      1) İleri-budama: koşu başından ileri, her `adim` örnek-karede bir, en çok
         `azami_ileri` örnek-kare — `kredi_karti_mi` False olduğu sürece ilerle;
         ilk True örnek-karesi aday-onset. Guard: budama koşu uzunluğunun
         yarısını geçemez — geçiyorsa (veya hiç bulunamazsa) DOKUNMA (OCR genel
         başarısızlığı işareti).
      2) Atlanan (adim-1) karede daha erken True olabilir — bulunan karadan 1
         örnek-kare geri de kontrol et, o da True ise onu al.
      3) Geri-genişletme: (budanmış) onset'ten geriye kare-kare (jbayrak şart
         DEĞİL) — `kredi_karti_mi` True ise geri çek; 2 ardışık False'ta dur;
         toplam ≤ `azami_geri` örnek-kare.

    Önbellek: her örnek-kare EN ÇOK BİR KEZ OCR'lanır (PaddleOCR-rec pahalı —
    aynı kare iki kez OCR'lanmasın)."""
    import credit_content as cc
    cache: dict[int, list[str]] = {}

    def satir(fi: int) -> list[str]:
        if fi not in cache:
            try:
                cache[fi] = cc.satirlar(g[idx[fi]])
            except Exception:
                cache[fi] = []
        return cache[fi]

    kosu_uzunluk = b - a
    azami_budama = kosu_uzunluk / 2.0

    bulunan = None
    fi = a
    denenen = 0
    while denenen < azami_ileri and fi <= b:
        if cc.kredi_karti_mi(satir(fi)):
            bulunan = fi
            break
        fi += adim
        denenen += 1

    if bulunan is None or (bulunan - a) > azami_budama:
        return a, "budama-yok(guard/bulunamadı)"

    if bulunan - 1 >= a and cc.kredi_karti_mi(satir(bulunan - 1)):
        bulunan -= 1

    onset = bulunan
    prob = bulunan
    ardisik_false = 0
    denenen = 0
    while denenen < azami_geri and prob - 1 >= 0:
        prob -= 1
        if cc.kredi_karti_mi(satir(prob)):
            onset = prob
            ardisik_false = 0
        else:
            ardisik_false += 1
            if ardisik_false >= 2:
                break
        denenen += 1

    return onset, f"budama={bulunan - a} genislet={bulunan - onset}"


def _ardisik_maks(mask) -> int:
    """Bool dizide en uzun ardışık True koşusunun uzunluğu (T4 scroll-tip ölçütü:
    ardışık scroll ≥16 örnek-kare)."""
    en = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        en = max(en, cur)
    return en


def _gecis_icerik_onayi(g: list[str], idx: list[int], cc_mod, a: int, b: int,
                         ornek: int = 8) -> bool:
    """T4 geri-birleştirme kapısı: ÖNCEKİ aday [a,b] gerçekten kredi içeriği mi.

    Aday zaten bir kutu-koşusu (jbayrak-sürdürülen) — burada yalnız ÇEKİRDEK
    ROL-KEYWORD (yönetmen/senaryo/görüntü/müzik/kurgu/oyuncu/yapımcı ...) arandığı
    doğrulanır. `kredi_karti_mi`'nin genel isim-listesi testi (isim≥3) YETERSİZ
    çıktı: BÜYÜK_TEHDİT/HAYATIMIN_ERKEĞİ regresyonu — mid-film bir "personel
    dosyası" ekran-arayüzü (DESCRIPTION/REMARKS/... gibi ALLCAPS OCR gürültüsü)
    isim≥3'ü rastlantısal geçiyor ama HİÇBİR rol-keyword'ü yok; UYKUNUN'un mid-
    film tarif-kartı ("Tarte aux Pommes") de aynı şekilde reddedilir. Buna karşın
    dört pozitif hedef (MESLEĞE_DÖNÜŞ/KARAVAN/"6"/DİPTEKİLER) örneklenen 8 karenin
    en az birinde gerçek rol-keyword taşıyor (DIRECTED BY / MUSIC BY / EDITOR /
    PRODUCER ...) — ölçüldü. Birden fazla örnek karede dener — tek karenin OCR'ı
    bozuk çıkabilir (geçiş bulanıklığı).

    T6 adım6: cc._ROL yerine cc._ROL_CEKIRDEK — 'produc' (production company
    logo-kuşağı riski, GLM uyarısı) bu kapıda ARTIK tetiklemiyor. T4 kazanımları
    ölçüldü (bkz. commit notu); PRODUCER'a bağımlı bir kazanım geriliyorsa bu
    fonksiyon cc._ROL'e geri alınır.

    T8 Kod-avı #2 (üretim-sertleştirme): TEK rol-kelimesi tek başına ARTIK
    yetmiyor — hardcoded altyazıda geçen tek bir cümle ("He was the director.")
    öncesinde bu kapıyı yanlışlıkla açabiliyordu (110-filmlik ölçüm setinde
    görünmez, üretimde altyazılı kaynaklarda risk). Onay artık İKİ yoldan biri:
    (1) AYNI karede rol-keyword + ≥1 isim-satırı (cc._isim_gibi) BİRLİKTE, ya da
    (2) adayın örneklenen karelerinde toplam ≥2 FARKLI çekirdek-rol bulunması
    (tek kart üzerinde tek role güvenmek yerine rol-çeşitliliği ister — sessiz-
    film kırmızı-çizgi senaryosuyla aynı ilke, bkz. cekirdek_rol_bul_genis).
    Dört mevcut kazanım (MESLEĞE_DÖNÜŞ/KARAVAN/"6"/DİPTEKİLER) ÖLÇÜLDÜ: hepsi
    en az bir örnek karede rol+isim birlikteliğini taşıyor (yol 1) — bu
    sıkılaştırma onları BOZMADI (bkz. T8 commit notu)."""
    n = min(ornek, b - a + 1)
    if n <= 0:
        return False
    roller_tumu: set[str] = set()
    for fi in sorted(set(int(x) for x in np.linspace(a, b, n))):
        try:
            satirlar = cc_mod.satirlar(g[idx[fi]])
        except Exception:
            continue
        roller_kare = {m.lower() for s in satirlar for m in cc_mod._ROL_CEKIRDEK.findall(s)}
        if not roller_kare:
            continue
        if any(cc_mod._isim_gibi(s) for s in satirlar):
            return True
        roller_tumu |= roller_kare
        if len(roller_tumu) >= 2:
            return True
    return False


# Kurtarma-yolu raporlanan güveni (Görev 1b, 2026-07-29 — Seçenek B): son-çare
# yolu hiçbir adayın content-eşiğini (EŞIK=0.6, aşağıda) geçemediği durumda
# devreye girer; bu, "en zayıf kanıt" demektir, "1.00 güven" değil. Dört sınır:
#   (a) >0.0 — 0.0 codebase'de "tespit yok" (kredi_yok/kare_yok/sinyal_yok) için
#       ayrılmış; kurtarma yolu bir TESPİT'tir (start_frame≥0 döner), 0.0 yanlış.
#   (b) <EŞIK(0.6) — içerik eşiği zaten geçilemedi; kurtarma bunu telafi etmiyor,
#       yalnız farklı (daha zayıf) bir kanıt yoluyla erişiyor.
#   (c) <exit_kesim/kes.py'deki GUVEN_ESIK=0.60 — bu filmler otomatik kesime
#       değil insan incelemesine düşmeli (kes.py guven<GUVEN_ESIK ise inceleme
#       kuyruğuna atıyor).
#   (d) normal kazananların ÖLÇÜLEN değer kümesinden ({0.67, 1.0} — 110-film
#       korpusunda gözlenen tek iki kb değeri) net uzak — karıştırılmasın.
# TÜRETİLMİŞ DEĞİL — kalibrasyon verisi yok; _scroll_kurtarma'nın beş sinyali
# (son-%25 sınırı, ≥8sn sürdürülen scroll+kutu, ≥1 _ROL_CEKIRDEK, min_kosu,
# sınır-öncesi geri-yürüme) zaten geçilmiş bir İKİLİ KAPI (var/yok) — sürekli
# bir skor üretmiyor, bu yüzden 0.35 sabit bir düşük-güven damgası, ölçülmüş
# bir olasılık değil.
KURTARMA_GUVEN = 0.35


def _scroll_kurtarma(g: list[str], idx: list[int], cc_mod, scroll: np.ndarray,
                      jbayrak: np.ndarray, n: int, fps: float, stride: int
                      ) -> tuple[int, int] | None:
    """Scroll-kurtarma (T6, plan Görev6/Adım2): HİÇBİR aday içerik-eşiğini
    geçemediyse son çare — filmin son %25'inde ≥8 sn SÜRDÜRÜLEN scroll+kutu
    koşusu VAR mı, ve o koşuda ≥1 _ROL_CEKIRDEK eşleşmesi var mı. Varsa kredi
    kabul (gazete/tabela/tek-intertitle KAYMAZ — gerekçe budur, sahte-pozitif
    riski düşük). `adaylar` listesindeki bir kutu-koşusuna denk gelmeyebilir
    (jbayrak-boşluk-toleransı farklı) — o yüzden ham scroll&jbayrak kesişiminde
    kendi ardışık-koşusunu arar.

    T8 Kod-avı #6 (üretim-sertleştirme): tarama `baslangic` (%75 sınırı)
    NOKTASINDAN başlıyordu — eğer gerçek koşu bu sınırdan ÖNCE başlayıp
    sınırı aşıyorsa (sınır koşunun ORTASINA denk geliyorsa), koşunun
    ölçülen başı (`ks`) yanlışlıkla sınıra sabitlenip koşu kısa/geç
    sayılıyordu (110-filmlik ölçüm setinde görünmez — bu filmlerin hiçbirinde
    gerçek koşu tam sınırda başlamıyor, ama üretimde risk). Şimdi taramadan
    ÖNCE sınırdan geriye yürüyüp `aktif` sürdüğü sürece gerçek koşu başını
    buluyor."""
    baslangic = int(0.75 * (n - 1))
    min_kosu = max(16, int(fps * 8.0 / stride))
    aktif = scroll & jbayrak
    if 0 <= baslangic < n and aktif[baslangic]:
        while baslangic - 1 >= 0 and aktif[baslangic - 1]:
            baslangic -= 1
    en_uzun = (0, -1, -1)  # (uzunluk, start, end)
    i = baslangic
    while i < n:
        if aktif[i]:
            j = i
            while j < n and aktif[j]:
                j += 1
            uzunluk = j - i
            if uzunluk > en_uzun[0]:
                en_uzun = (uzunluk, i, j - 1)
            i = j
        else:
            i += 1
    uzunluk, ks, ke = en_uzun
    if uzunluk < min_kosu:
        return None
    ornek = sorted(set(int(x) for x in np.linspace(ks, ke, min(8, ke - ks + 1))))
    for fi in ornek:
        try:
            satirlar = cc_mod.satirlar(g[idx[fi]])
        except Exception:
            continue
        if any(cc_mod._ROL_CEKIRDEK.search(s) for s in satirlar):
            return ks, ke
    return None


# "kart-başına-tek-isim" dizilerinde stüdyo/yapımcı logo kartları ("FIREWORKS
# ENTERTAINMENT presents", "a JULIAN GRANT production") credit_box.jenerik_
# benzeri'yi (n>=2 ister) hiç geçmiyor olabilir (n==1) — yalnız bu dar yardımcı
# içinde kullanılan tamamlayıcı desen.
_PRESENTS_KALIBI = re.compile(r"presents|production", re.I)


def _rakam_agirlikli_mi(s: str) -> bool:
    """T8 Kod-avı #7: 'Year 1999' tipi montaj/tarih kartları isim-satırı
    SAYILMASIN — satırın alfasayısal karakterlerinin ≥%50'si rakamsa
    diskalifiye (yalnız _kart_dizisi_geri_genislet içinde kullanılır, global
    cc._isim_gibi'ye DOKUNULMADI — blast-radius'u dar tutmak için)."""
    alnum = [c for c in s if c.isalnum()]
    if not alnum:
        return False
    rakam = sum(1 for c in alnum if c.isdigit())
    return (rakam / len(alnum)) >= 0.5


def _farkli_metin_sayisi(metinler: list[str], esik: float = 0.8) -> int:
    """T8 Kod-avı #4: aynı fiziksel kartın ardışık OCR okumaları küçük
    gürültüyle (tek harf farkı vb.) birbirinden farklı string üretebilir —
    ham `len(set(...))` bunları YANLIŞLIKLA ayrı kart sayardı. difflib
    benzerliği ≥`esik` olan metinler AYNI kartın temsilcisiyle birleştirilir;
    yalnız gerçekten FARKLI kart sayısı döner."""
    temsilciler: list[str] = []
    for m in metinler:
        if not any(difflib.SequenceMatcher(None, m, t).ratio() >= esik for t in temsilciler):
            temsilciler.append(m)
    return len(temsilciler)


def _kart_dizisi_geri_genislet(g: list[str], idx: list[int], cc_mod, cb_mod,
                                onset: int, azami_geri: int = 80,
                                bosluk_tol: int = 4, min_metin: int = 4) -> tuple[int, str]:
    """Kart-dizisi geri-genişletme (T6 2.tur, alt-adım3 — konsey kırmızı-takım,
    ROBOCOP sınıfı). Kart-başına-tek-aktör düzeninde (her karede yalnız 1 kutu/
    1 isim) credit_box.kutu_serisi jbayrak'ı hiç kaldırmıyor (jenerik_benzeri
    n>=2 ister) — bu yüzden dizi kendi `adaylar` koşusunu OLUŞTURMUYOR ve
    _statik_icerik_onset'in kredi_karti_mi'si de (isim>=3 tek karede ister)
    tek-satırlı kartları hep reddediyor (atlas kanıtı: ROBOCOP'ta 1093-1127
    arası her kare 1 aktör adı, geri-genişletme hiç ilerlemiyordu).

    Kazanan koşunun (zaten seçilmiş `onset`) HEMEN ÖNCESİNDEN geriye, ham kutu
    sayısı (credit_box, tek_genis elenmişler DAHİL) 1 veya 2 olan VE rec'i
    isim-benzeri (cc._isim_gibi) VEYA 'presents/production' logosu olan
    kareler boyunca yürür; ara boşluk (kalifiye-olmayan kare) `bosluk_tol`'u
    aşınca durur. ≥`min_metin` FARKLI metin biriktiyse onset'i dizinin en
    erken bulunan karesine çeker — BAĞIMSIZ TETİKLEME DEĞİL, yalnız zaten
    kazanmış koşuya bitişik geriye-genişletme (kredisiz-film güvencesi
    buradan geliyor: rastgele bir kart hiçbir yerde tek başına tetiklemez).

    T8 Kod-avı #4+#7 (üretim-sertleştirme): "FARKLI metin" sayacı iki riske
    açıktı — (1) aynı fiziksel kartın gürültülü OCR tekrarları (tek harf
    farkıyla) ayrı kart sanılabiliyordu → artık difflib benzerliği ≥0.8 olan
    metinler AYNI kart sayılır (_farkli_metin_sayisi); (2) 'Year 1999' gibi
    rakam-ağırlıklı satırlar isim sanılabiliyordu → satırın alfasayısal
    karakterlerinin ≥%50'si rakamsa `kart_mi` o satırı hiç değerlendirmez
    (_rakam_agirlikli_mi). İkisi de yalnız bu dar yardımcıda; global
    cc._isim_gibi/kredi_karti_mi DEĞİŞMEDİ."""
    onbellek: dict[int, list[str]] = {}

    def satir(fi: int) -> list[str]:
        if fi not in onbellek:
            try:
                onbellek[fi] = cc_mod.satirlar(g[idx[fi]])
            except Exception:
                onbellek[fi] = []
        return onbellek[fi]

    def kart_mi(fi: int) -> tuple[bool, str]:
        analiz = cb_mod.kutu_analiz(g[idx[fi]])
        if analiz["n"] not in (1, 2):
            return False, ""
        lines = [s for s in satir(fi) if not _rakam_agirlikli_mi(s)]
        if not lines:
            return False, ""
        metin = " / ".join(lines)
        if _PRESENTS_KALIBI.search(metin) or any(cc_mod._isim_gibi(s) for s in lines):
            return True, metin
        return False, ""

    metinler: list[str] = []
    fi = onset - 1
    bosluk = 0
    toplam = 0
    yeni_onset = onset
    while fi >= 0 and toplam < azami_geri and bosluk <= bosluk_tol:
        ok, metin = kart_mi(fi)
        if ok:
            metinler.append(metin)
            yeni_onset = fi
            bosluk = 0
        else:
            bosluk += 1
        fi -= 1
        toplam += 1

    if _farkli_metin_sayisi(metinler) >= min_metin:
        return yeni_onset, f"kart-dizisi_genislet={onset - yeni_onset}"
    return onset, ""


def _scroll_sirket_budama(g: list[str], idx: list[int], cc_mod, onset: int, n: int,
                           azami_ileri: int = 30) -> tuple[int, str]:
    """Scroll-tip koşuda şirket/stüdyo-kartı ileri-budaması (alt-adım2, T8
    sonrası — Çağatay politikası 2026-07-23: GEÇ kalma artık en kötü hata
    sınıfı, İLERİ-çekme EN RİSKLİ işlem; şüphede İLERİ ÇEKME, erken kalmak
    tercih edilir). Scroll-tip koşu sık sık şirket/stüdyo satırıyla başlar
    (Görsel kanıt: YÜREKTEN_SEVMEK v5-karesi 'Filmed entirely on the Stages
    of Zoetrope Studios', gt-karesi 'CAST OF CHARACTERS'; İKİ_KAFADAR benzer
    — logo/prodüksiyon-adı montajı).

    Onset'ten ileri, en çok `azami_ileri` örnek-kare: OCR satırları BOŞ,
    (BİRLEŞİK kare metni şirket-kalıbına uyuyor), VEYA hiçbir satır isim-
    satırı (cc._isim_gibi) DEĞİLSE o kareyi atla (boş kare RİSKSİZ atlanır —
    atlanacak bir isim-satırı zaten yok); İLK isim-satırlı VE şirket-kalıbına
    UYMAYAN karede DUR ve ÇAPALA. KATI GARD: böyle bir kare ASLA atlanmaz —
    bulunduğu anda döngü kesin durur. BİRLEŞİK metin kontrolü şart: OCR
    satır sınırları cümleyi rastgele böler (YÜREKTEN_SEVMEK ölçümü —
    'Filmed entirely on the Stages' / 'of Zoetrope Studios' İKİ ayrı satıra
    düşüyor; 'studios' kelimesi olmayan ilk parça, Title-Case kelime sayımıyla
    yanlışlıkla isim-satırı sayılıyordu); satır-satır değil BİRLEŞTİRİLMİŞ
    metinde arandığında şirket-kalıbı doğru yakalanıyor. TÜM-YA-DA-HİÇ:
    bütçe (`azami_ileri`) içinde uygun bir çapa bulunamazsa onset HİÇ
    değiştirilmez — belirsizlikte ileri gitmemek yanlış ileri çekmekten
    daha güvenli."""
    onbellek: dict[int, list[str]] = {}

    def satir(fi: int) -> list[str]:
        if fi not in onbellek:
            try:
                onbellek[fi] = cc_mod.satirlar(g[idx[fi]])
            except Exception:
                onbellek[fi] = []
        return onbellek[fi]

    ileri_sinir = min(n - 1, onset + azami_ileri)
    fi = onset
    capa_bulundu = False
    while fi < ileri_sinir:
        satirlar_fi = satir(fi)
        # YABANCI-ALFABE GARDI (KANDAHAR/ARKADAŞIMIN_EVİ_NEREDE regresyonu,
        # ölçüldü ve GERİ ALINDI önce): cc._isim_gibi Latin-odaklı (büyük/
        # küçük-harf ayrımı Arapça/Farsça'da YOK) — Arapça/Farsça/Kiril kredi
        # içeriğinde isim_var HEP False dönüyor, bu da GERÇEK isim satırlarının
        # "şirket-kartı" sanılıp yanlışlıkla İLERİ atlanmasına yol açıyordu
        # (KANDAHAR +5→+23, ARKADAŞIMIN kredi-var kaybı — iki GEÇ regresyonu).
        # Çağatay politikası: yanlış ileri-çekme en kötü hata sınıfı — bu
        # yüzden Latin harfi TAŞIMAYAN dolu kare "bilinmiyor" sayılır ve
        # İLERİ GİTMEYİ DURDURUR (ne atlanır ne çapalanır — mevcut onset
        # olduğu gibi kalır, şüphede erken kalmak tercih edilir).
        if satirlar_fi and not any(c.isalpha() and ord(c) < 0x250 for s in satirlar_fi for c in s):
            break
        # boş kare RİSKSİZ atlanır — atlanacak bir isim-satırı yoktur zaten
        # (geçiş bulanıklığı/kısa kare-arası boşluk, kart-dizisi/statik-içerik
        # geri-genişletmelerindeki aynı bosluk-toleransı ilkesi). Yalnız
        # BÜTÇE (azami_ileri) sınırı ileri gitmeyi durdurur.
        sirket_mi = bool(satirlar_fi) and cc_mod._SIRKET_KALIBI.search(" ".join(satirlar_fi))
        isim_var = any(cc_mod._isim_gibi(s) for s in satirlar_fi)
        if isim_var and not sirket_mi:
            capa_bulundu = True
            break  # isim-satırlı VE şirket-kalıbı DEĞİL — ASLA atlanmaz, dur
        fi += 1  # şirket-kalıbı VEYA hiçbiri isim-değil — atla

    if capa_bulundu and fi > onset:
        return fi, f"sirket-budama={fi - onset}"
    return onset, ""


def tespit_v5(dizin: str, fps: float = 25.0, stride: int = 2, ocr_stride: int = 2) -> Sonuc:
    """v5: TAM FİLM için. Aday kutu-koşuları → OCR-içerik ile 'isim-listesi mi'
    doğrula → son-çapa+scroll ile seç → yoksa KREDİ YOK.

    Konsey (GLM, 2026-07-21): kutu var/yok yetmez. Tam filmde sahne-tabelası
    (BILLY saloon), ara-yazı (MODERN Chaplin), gazete kutu üretir ama İSİM-LİSTESİ
    DEĞİL. Krediyi ayıran: metin içeriği (rec) + scroll + son-çapa. Eski filmlerin
    ~%40'ı kapanış-kredisiz → güvenle 'YOK' dönülmeli."""
    import credit_box as cb
    import credit_content as cc
    g = kareler(dizin)
    if len(g) < 10:
        return Sonuc(-1, "kare_yok", 0.0, notlar=f"{len(g)} kare")

    idx = list(range(0, len(g), stride))
    gk = [_gri(g[i]) for i in idx]
    band = head_band_kirp(gk)
    if band:
        gk = [k[: k.shape[0] - band] for k in gk]
    # T4: max_shift 40→60 — hızlı-akan jenerikte kayma sınıra yapışıp korelasyonu
    # düşürüyordu (GLM tur-2 aliasing uyarısı). Yalnız v5'in KENDİ çağrısı;
    # dy_cift'in varsayılan max_shift=40'ı DEĞİŞMEDİ — hata_atlasi.py hâlâ
    # varsayılanla çağırıyor, imza/davranış korunuyor.
    MAX_SHIFT_V5 = 60
    dys = []
    corrs = []
    for i in range(len(gk) - 1):
        s, r = dy_cift(gk[i], gk[i + 1], max_shift=MAX_SHIFT_V5)
        dys.append(s)
        corrs.append(r)
    dys = np.array(dys, dtype=np.float32)
    corrs = np.array(corrs, dtype=np.float32)
    n = len(gk)
    scroll = np.zeros(n, bool)
    for i in range(len(dys)):
        # aliasing gardı: dy sınıra yapışmışsa (gerçek kayma max_shift'i aşıyor,
        # arama sınırda kırpılıyor) VE korelasyon yine de güçlüyse scroll say.
        scroll[i] = (dys[i] > 3 and corrs[i] >= 0.85) or (
            abs(dys[i]) >= MAX_SHIFT_V5 - 2 and corrs[i] >= 0.85)

    alt_g = [g[i] for i in idx]
    jbayrak, say = cb.kutu_serisi(alt_g, stride=ocr_stride)

    # ── aday koşuları bul (sürdürülen kutu-jenerik, boşluk-toleranslı) ──
    min_kosu = max(6, int(fps * 1.0 / stride))
    bosluk_tol = max(4, int(fps * 0.8 / stride))
    adaylar = []
    i = 0
    while i < n:
        if jbayrak[i]:
            j = i
            bosluk = 0
            son = i
            while j < n and bosluk <= bosluk_tol:
                if jbayrak[j]:
                    bosluk = 0
                    son = j
                else:
                    bosluk += 1
                j += 1
            if son - i + 1 >= min_kosu:
                adaylar.append((i, son))
            i = j
        else:
            i += 1

    if not adaylar:
        return Sonuc(-1, "kredi_yok", 0.0,
                     notlar=f"kutu-koşusu yok; maxkutu={int(say.max())}",
                     seri={"adaylar": []})

    # ── her adayı OCR-içerikle değerlendir ──
    EŞIK = 0.6     # ≥2 sürdürülen-yoğun kare (gazete 1 karede kalır → elenir)
    # SON-ERİŞİM kuralı (konsey + gözlem): GERÇEK kapanış kredisi filmin SONUNA kadar
    # uzanır. Film-ortası metin insertı (MODERN arananıyor-afişi) daha erken biter,
    # ardından FİLM DEVAM EDER. Aday sonu son %18'e ulaşmıyorsa kredi değildir.
    SON_ERISIM = 0.82
    # SON_ERISIM gevşetmesi (T6, plan Görev6/Adım3): bazı gerçek kapanış kredileri
    # filmin en son birkaç saniyesine ULAŞMADAN biter (DOĞUM_GÜNÜN atlas kanıtı —
    # son_capa=0.74, yayın-sonu boş/logo kareleri kutu üretmiyor). Yalnız filmin
    # SON metin-koşusu (sonrasında başka aday YOK) VE kb≥0.9 (çok yüksek içerik
    # güveni) VE ≥1 _ROL_CEKIRDEK VARSA eşik 0.82→0.70'e gevşer. 0.70'i AŞAN
    # gevşetme YASAK (plan: film-ortası insert kapısı, kırmızı-çizgi riski).
    SON_ERISIM_GEVSEK = 0.70
    en_iyi = None
    kayitlar = []   # teşhis: aday başına {a,b,kare_a,kare_b,son_ok,kb,joint,roller} (T2)
    for widx, (a, b) in enumerate(adaylar):
        kare_a, kare_b = _kare_no(g[idx[a]]), _kare_no(g[idx[b]])
        son_capa_orani = b / max(1, n - 1)
        son_ok = son_capa_orani >= SON_ERISIM
        is_last = (widx == len(adaylar) - 1)
        gevsetme_aday = (not son_ok) and is_last and son_capa_orani >= SON_ERISIM_GEVSEK
        if not son_ok and not gevsetme_aday:
            # SON_ERISIM'e takıldı → içerik OCR'ı hiç ÇALIŞTIRMA (maliyet artmasın)
            kayitlar.append({"a": a, "b": b, "kare_a": kare_a, "kare_b": kare_b,
                              "son_ok": False, "kb": None, "joint": None, "roller": []})
            continue                     # filmin sonuna ulaşmıyor → kredi değil
        # en yoğun kutulu kareler + eşit örnekler (dense kredi karesini yakala)
        say_c = max(1, (b - a + 1))
        yogun = list(np.argsort(say[a:b + 1])[-5:] + a)
        esit = list(np.linspace(a, b, min(5, say_c)).astype(int))
        ornek = sorted(set(int(x) for x in yogun + esit))
        satir_onbellek: dict[int, list[str]] = {}

        def _satir_al(fi: int) -> list[str]:
            if fi not in satir_onbellek:
                try:
                    satir_onbellek[fi] = cc.satirlar(g[idx[fi]])
                except Exception:
                    satir_onbellek[fi] = []
            return satir_onbellek[fi]

        kare_satirlari = [_satir_al(fi) for fi in ornek]
        kb_max = cc.kredi_skoru_coklu(kare_satirlari)
        core_roller = cc.cekirdek_rol_bul(kare_satirlari)
        # Seyrek-kredi yolu (T6, plan Görev6/Adım4): bazı jenerikler kare-başına
        # 1-3 isim gösterir (KÜÇÜK_SİMBA/ROBOCOP/TAKTİKLER_SAVAŞI atlas kanıtı) —
        # varsayılan yogun_esik=4 hiç yakalamıyor. Ama gerçek kredi ile gazete/tabela
        # ayrımı hala gerekiyor: yalnız koşuda ≥2 FARKLI ÇEKİRDEK-rol varsa (tek
        # 'Yönetmen' intertitle'ı YETMEZ — sessiz-film kırmızı-çizgi senaryosu)
        # yogun_esik=2 ile yeniden skorla, büyük olanı al.
        # Dar örneklem (5 yoğun+5 eşit) rol-çeşitliliğini kaçırabilir (ROBOCOP
        # ölçümü: 'music'/'written' örneklemin dışında kaldı) — aday zaten
        # REDDEDİLECEKSE (kb_max<EŞIK) ve <2 çekirdek-rol bulunduysa, SADECE bu
        # durumda geniş örneklemle rol-çeşitliliğini yeniden ara (maliyet yalnız
        # başarısız adaylarda artar).
        #
        # mini-tur3 alt-adım1: genişletme KARARI (yalnız burada, ≥2 sayımında)
        # cekirdek_rol_bul_genis kullanır — STRICT core_roller (SON_ERISIM_GEVSEK
        # kapısında aşağıda kullanılıyor) DEĞİŞMEZ. Gerekçe credit_content.py'de
        # cekirdek_rol_bul_genis docstring'inde: 'produc' ailesini ham
        # _ROL_CEKIRDEK'e eklemek DÖNÜŞÜ_OLMAYAN_NEHİR'i bozdu (ölçüldü); kanonik
        # tek-rol ("producer") + yalnız-bu-karar-noktasına sınırlama düzeltti.
        core_roller_genis = cc.cekirdek_rol_bul_genis(kare_satirlari)
        if len(core_roller_genis) < 2 and kb_max < EŞIK and (b - a + 1) > len(ornek):
            genis_idx = sorted(set(int(x) for x in np.linspace(a, b, min(16, say_c))))
            genis_satirlari = [_satir_al(fi) for fi in genis_idx]
            core_roller_genis = cc.cekirdek_rol_bul_genis(genis_satirlari)
            if len(core_roller_genis) >= 2:
                kare_satirlari = genis_satirlari
                core_roller = cc.cekirdek_rol_bul(genis_satirlari)
        if len(core_roller_genis) >= 2:
            kb_seyrek = cc.kredi_skoru_coklu(kare_satirlari, yogun_esik=2)
            kb_max = max(kb_max, kb_seyrek)
        # İKİNCİ-ŞANS KİRİL REC (T6 2.tur, alt-adım1b, konsey kırmızı-takım):
        # içerik-eşiği hâlâ geçilmediyse VE 7 dilin (EN/TR/IT/FR/DE/ES/HU)
        # HİÇBİRİNDE çekirdek-rol bulunamadıysa — güçlü "yanlış dil modeliyle
        # okundu" sinyali (VANYA_DAYI/MELEKLERİ_GÖRMEK atlas kanıtı: Rusça/
        # Kazakça kredi, lang='en' modeliyle rastgele Latin harf yığını üretmiş).
        # cc.cop_desenli_mi (sesli-harf-oranı istatistiği) ÖLÇÜLDÜ: tek başına
        # ayırt edici DEĞİL — Kiril→Latin harf-şekli ikamesi doğal sesli-
        # yoğunluğunu KORUYOR (MELEKLERİ_GÖRMEK örneğinde gerçek-İngilizceyle
        # aynı aralığa düşüyor, %90 vs %94). Asıl güvenilir sinyal core_roller
        # boşluğu (nadir — 7 dilin hiçbiri tutmuyor, film-özel değil); cop_desenli_mi
        # yalnız EK bir zayıf süzgeç olarak kullanılır (net-temiz İngilizce'yi
        # dışlar, maliyeti sınırlar).
        if kb_max < EŞIK and not core_roller and cc.cop_desenli_mi(kare_satirlari, esik=0.92):
            kare_satirlari_kiril = [cc.satirlar_ru(g[idx[fi]]) for fi in ornek]
            kb_kiril, roller_kiril = cc.kredi_skoru_kiril(kare_satirlari_kiril)
            # GÜVENLİK (ölçüldü, ASRİ_ZAMANLAR/Modern-Times regresyonu): salt
            # yoğunluk (kb_kiril) TEK BAŞINA yetersiz — Türkçe ara-yazı ("BU KADAR
            # ÇABALAMANIN ANLAMI NE?") kısa/az-satırlı olduğu için EN yolunda
            # yogun_esik=4'ü geçemiyordu ama Kiril yolunun seyrek yogun_esik=2'si
            # bunu yanlışlıkla kredi sayıyordu. Codebase'in genel ilkesiyle aynı
            # (T6 seyrek-yol/SON_ERISIM gevşetmesi/scroll-kurtarma): risk taşıyan
            # her gevşetme yalnız GERÇEK bir _ROL_KIRIL eşleşmesiyle (roller_kiril
            # dolu) kazanılır.
            if roller_kiril and kb_kiril > kb_max:
                kb_max = kb_kiril
                core_roller = roller_kiril
                kare_satirlari = kare_satirlari_kiril
        # İKİNCİ-ŞANS ARAPÇA/FARSÇA REC (alt-adım4 — Çağatay politikası:
        # tespit-yok = cast komple kayıp, artık zorunlu deneme). Kiril'den
        # FARKLI tetikleyici: Arapça/Farsça glyph'lerde EN-rec çoğu zaman
        # RASTGELE METİN değil, HİÇ (veya neredeyse hiç) METİN üretmiyor
        # (KANDAHAR atlas+ölçüm kanıtı: 10 örnek kareden 8'i tam boş, 2'si
        # 'PT'/'年号'/'是'/'5555'/'bA21' gibi anlamsız 1-4 karakterlik kırıntı
        # — katı "== 0" şartı bunu kaçırır). cc.cop_desenli_mi burada anlamsız
        # (bu kırıntılarda len>=4 alpha token hiç oluşmuyor, her zaman False
        # döner) — tetikleyici "kareler EN-rec ile NEREDEYSE tamamen boş"
        # (≤2/10 karede iz). AYNI güvenlik ilkesi: yalnız GERÇEK bir
        # cc._ROL_ARAP eşleşmesi (roller_arap dolu) kb'yi override eder.
        en_bos_kare = sum(1 for sl in kare_satirlari if not sl)
        if kb_max < EŞIK and not core_roller and en_bos_kare >= max(1, len(kare_satirlari) - 2):
            kare_satirlari_arap = [cc.satirlar_ar(g[idx[fi]]) for fi in ornek]
            kb_arap, roller_arap = cc.kredi_skoru_arap(kare_satirlari_arap)
            if roller_arap and kb_arap > kb_max:
                kb_max = kb_arap
                core_roller = roller_arap
                kare_satirlari = kare_satirlari_arap
        if gevsetme_aday and not (kb_max >= 0.9 and core_roller):
            # gevşetme hakkı kazanılmadı (kb<0.9 VEYA çekirdek-rol yok) — normal
            # SON_ERISIM'e takılmış gibi davran (kb'yi teşhis için sakla).
            kayitlar.append({"a": a, "b": b, "kare_a": kare_a, "kare_b": kare_b,
                              "son_ok": False, "kb": round(kb_max, 3), "joint": None,
                              "roller": []})
            continue
        scroll_var = bool(scroll[a:b + 1].any())
        yogunluk = min(1.0, float(say[a:b + 1].max()) / 8.0)
        joint = kb_max * (1.0 + 0.3 * scroll_var + 0.35 * son_capa_orani + 0.15 * yogunluk)
        roller = sorted(set(core_roller) | {m.lower()
                          for sl in kare_satirlari for s in sl for m in cc._ROL.findall(s)})
        kayitlar.append({"a": a, "b": b, "kare_a": kare_a, "kare_b": kare_b,
                          "son_ok": True, "kb": round(kb_max, 3), "joint": round(joint, 3),
                          "roller": roller})
        if kb_max >= EŞIK and (en_iyi is None or joint > en_iyi[0]):
            en_iyi = (joint, a, b, kb_max, scroll_var, roller, son_capa_orani)

    kurtarma_yolu = False
    if en_iyi is None:
        kurtarma = _scroll_kurtarma(g, idx, cc, scroll, jbayrak, n, fps, stride)
        if kurtarma is not None:
            ks, ke = kurtarma
            kare_ks, kare_ke = _kare_no(g[idx[ks]]), _kare_no(g[idx[ke]])
            kayitlar.append({"a": ks, "b": ke, "kare_a": kare_ks, "kare_b": kare_ke,
                              "son_ok": True, "kb": 1.0, "joint": 1.0,
                              "roller": ["scroll_kurtarma"]})
            # UYARI (Görev 1b): buradaki kb=1.0/joint=1.0 ÖLÇÜLMÜŞ DEĞİL — yalnız
            # `en_iyi` tuple'ının şeklini ve aşağıdaki `yabanci_yol` türetimini
            # ("scroll_kurtarma" in roller_kazanan) korumak için konmuş yer-tutucu.
            # Raporlanan güven bu değerden DEĞİL, `kurtarma_yolu` bayrağıyla
            # KURTARMA_GUVEN'e düşürülüyor (aşağıda dönüş bloğunda). Unpack
            # sonrasına `kb`'ye bağlı YENİ bir karar eklenecekse önce
            # `kurtarma_yolu` kontrol edilmeli — aksi halde bu yer-tutucu 1.0
            # gerçek ölçümmüş gibi kullanılır.
            kurtarma_son_capa = ke / max(1, n - 1)      # GERÇEK ölçüm (son_capa_orani ile aynı formül)
            en_iyi = (1.0, ks, ke, 1.0, True, ["scroll_kurtarma"], kurtarma_son_capa)
            kurtarma_yolu = True
        else:
            degerlendirilmis = [k for k in kayitlar if k["son_ok"]]
            if not degerlendirilmis:
                sebep = "tüm adaylar SON_ERISIM'e takıldı"
            else:
                en_iyi_kb = max(k["kb"] for k in degerlendirilmis)
                sebep = f"içerik-eşiği geçilemedi (en iyi kb={en_iyi_kb:.2f})"
            return Sonuc(-1, "kredi_yok", 0.0, notlar=sebep, seri={"adaylar": kayitlar})

    joint, a, b, kb, scroll_var, roller_kazanan, son_capa_kazanan = en_iyi
    # alt-adım2 güvenlik gardı (KANDAHAR/ARKADAŞIMIN_EVİ_NEREDE regresyonu,
    # ölçüldü ve GİDERİLDİ): kazanan aday Kiril/Arapça ikinci-şans REC'i ya
    # da scroll_kurtarma (son-çare, içerik-anlamsız-onset) yoluyla kazanmışsa
    # `roller_kazanan` YABANCI-ALFABE token'lar taşır (ör. Farsça 'بازيگران')
    # veya literal 'scroll_kurtarma' işaretidir — bu durumda cc._isim_gibi'nin
    # (Latin-odaklı) o filmin GERÇEK kredi içeriğini "isim değil" sanıp
    # _scroll_sirket_budama'yı yanlışlıkla İLERİ çekmesi riski YÜKSEK (ölçüldü:
    # KANDAHAR +5→+23, ARKADAŞIMIN kredi-var kaybı). Bu bayrak True ise
    # ileri-budama HİÇ ÇAĞRILMAZ (aşağıda kullanılıyor).
    yabanci_yol = ("scroll_kurtarma" in roller_kazanan) or any(
        r and not any(c.isalpha() and ord(c) < 0x250 for c in r) for r in roller_kazanan)
    # kazanan koşuda scroll-aktif kare oranı — statik/scroll ayrımı (T5) +
    # ardışık-scroll uzunluğu (T4 scroll-tip ölçütü, yalnız notlarda/teşhiste
    # kullanılır — bkz. aşağıdaki geri-birleştirme yorumu).
    scroll_orani = float(scroll[a:b + 1].mean()) if b >= a else 0.0
    ardisik_scroll = _ardisik_maks(scroll[a:b + 1]) if b >= a else 0

    # ── T4: geri-birleştirme — SON_ERISIM'e takılmış ÖNCEKİ adaylarla birleş ──
    # ÖNCE denenir (kazanan koşunun KENDİ başlangıcı `a`'dan) — içerik-çapalı
    # budama/genişletme yalnız birleştirme uygulanamazsa devreye girer (budama
    # onset'i `a`'dan uzaklaştırır; boşluk hesabı candidate-candidate mesafesine
    # değil budanmış noktaya göre yapılırsa DİPTEKİLER gibi vakalarda boşluk
    # yapay şekilde şişer — DİPTEKİLER'in gerçek boşluğu 28 örnek-kare ama budama
    # sonrası nokta kullanılırsa ~51 ölçülüyor, KISA_BOSLUK'u yanlışlıkla aşıyor).
    #
    # Atlas kanıtı (2. tur): MESLEĞE_DÖNÜŞ / KARAVAN / "6" / DİPTEKİLER aynı
    # kalıbı gösteriyor — gerçek-onset SON_ERISIM'e takılmış bir ÖNCEKİ adayın
    # içinde/başında, kazanan koşuyla arasında KISA bir boşluk var (16-38
    # örnek-kare, ölçüldü). Plan taslağı bu köprülemeyi "scroll-tip" (scroll_oran
    # ≥0.3 VEYA ardışık≥16) koşularla sınırlıyordu; ÖLÇÜM bunu çürüttü: bu dört
    # hedefin scroll_oran'ı 0.07-0.24, ardışık-maks 3-5 — İKİSİ DE eşiğin altında
    # (yalnız MESLEĞE_DÖNÜŞ=0.95 ve TAKKELİ_MELEK=0.86 "scroll-tip" eşiğini
    # geçiyor). Güvenlik scroll oranından değil aşağıdaki İKİ kapıdan geliyor:
    #   (1) KISA boşluk — HARİKA_KÖPEK_5'in önceki adayına boşluk ~84 örnek-kare,
    #       bloklanır (negatif-guard, sahne+tabela riski, atlas kanıtlı).
    #   (2) içerik-kapısı — İNİŞLİ_ÇIKIŞLI'nın boşluğu KISA (14) ama içerik
    #       CJK/şarkı-adı karışığı, kredi_karti_mi hiçbir örnekte geçmiyor →
    #       bloklanır.
    # Bu yüzden birleştirme "scroll-tip" şartı ARANMADAN, kazanan her koşu için
    # denenir; gerekçe atlasa da düşülmüştür (bkz. commit notu).
    KISA_BOSLUK = max(20, int(fps * 3.6 / stride))  # ~45 örnek-kare (38 geçmeli/84 engellenmeli — ölçüldü)
    TOPLAM_BUTCE = 120  # plan T4 — _statik_icerik_onset.azami_geri ile AYNI birim/büyüklük
    # T8 Kod-avı #1 (üretim-sertleştirme, 2026-07-23): `butce` yalnız ARA-BOŞLUKLARDAN
    # düşüyordu — bitişik/küçük-boşluklu (bosluk≈0) aday ZİNCİRİNDE her adayın KENDİ
    # uzunluğu bütçeye hiç yansımıyordu, onset teorik olarak sınırsız geriye
    # kaçabilirdi (110-filmlik ölçüm setinde görünmüyor, 2400-filmlik üretimde risk).
    # TOPLAM_MESAFE, `a`dan (kazanan koşu başı) toplam geri-yürüyüşü MUTLAK sınırlar —
    # `butce`den BAĞIMSIZ. 200 = ölçülen en büyük gerçek kazanım MESLEĞE_DÖNÜŞ'ün
    # ihtiyacı (a-a_prev=160 örnek-kare) üstünde güvenlik payı; KARAVAN(88)/
    # DİPTEKİLER(78)/"6"(60) rahatça altında kalıyor (ölçüldü, bkz. T8 commit notu).
    TOPLAM_MESAFE = 200
    onset_birlesik, birlesme_notu = None, None
    try:
        w = adaylar.index((a, b))
    except ValueError:
        w = -1
    onset_z = a
    birlesenler = []
    if w > 0:
        butce = TOPLAM_BUTCE
        k = w
        while k > 0 and butce > 0:
            a_prev, b_prev = adaylar[k - 1]
            bosluk = onset_z - b_prev - 1
            if bosluk < 0 or bosluk > KISA_BOSLUK or bosluk > butce:
                break
            if (a - a_prev) > TOPLAM_MESAFE:
                break
            if not _gecis_icerik_onayi(g, idx, cc, a_prev, b_prev):
                break
            onset_z = a_prev
            butce -= bosluk
            k -= 1
            birlesenler.append(f"[{_kare_no(g[idx[a_prev]])}-{_kare_no(g[idx[b_prev]])}]")

    # alt-adım3 (köprü kapısında producer+isim çifti — Çağatay politika
    # güncellemesi 2026-07-23: GEÇ kalma artık en kötü hata sınıfı, PRENSESİN
    # +37 GEÇ hedefi). Görsel kanıt: PRENSESİN_AŞKI'nin gerçek onsetinde
    # ('Executive Producers / PETER LOCKE / DONALD KUSHNER') box-koşusu yalnız
    # ~3 sn sürüyor — min_kosu eşiğini hiç geçemiyor, `adaylar`e HİÇ KAYDOLMUYOR,
    # yukarıdaki köprü onu hiç GÖRMÜYOR (ne registrasyon ne _gecis_icerik_onayi
    # bu içeriğe erişebiliyor). Kayıt-dışı ham tarama: onset_z'den geriye, AYNI
    # KISA_BOSLUK/TOPLAM_MESAFE bütçesiyle sınırlı VE bir önceki kayıtlı adayın
    # kendi kare-aralığına ASLA taşmadan (b_bariyer — o aralık ya zaten birleşti
    # ya da _gecis_icerik_onayi'nin daha sıkı kapısınca reddedildi, ham tarama
    # onu ATLAMAZ), HER örnek-karede doğrudan bakar: cc._PRODUC_GENIS (kanonik
    # 'producer' ailesi) VE AYNI karede ≥1 isim-satırı (cc._isim_gibi) varsa
    # köprü-noktası kabul. Yalnız zaten kazanmış (en_iyi bulunmuş) koşuya
    # bitişik — kredisiz-film güvencesi buradan gelir, bağımsız tetikleme YOK.
    b_bariyer = -1
    for cand_a, cand_b in adaylar:
        if cand_b < onset_z:
            b_bariyer = max(b_bariyer, cand_b)
    ham_butce = max(0, min(KISA_BOSLUK, TOPLAM_MESAFE - (a - onset_z)))
    ham_sinir = max(0, b_bariyer + 1, onset_z - ham_butce)
    fi = onset_z - 1
    while fi >= ham_sinir:
        try:
            satirlar_fi = cc.satirlar(g[idx[fi]])
        except Exception:
            satirlar_fi = []
        if satirlar_fi and cc._PRODUC_GENIS.search(" ".join(satirlar_fi)) \
                and any(cc._isim_gibi(s) for s in satirlar_fi):
            onset_z = fi
            birlesenler.append(f"kopru-ham=[{_kare_no(g[idx[fi]])}]")
            break
        fi -= 1

    if onset_z < a:
        onset_birlesik = onset_z
        birlesme_notu = f"geri-birlesme={','.join(birlesenler)}"

    ek_not = ""
    if onset_birlesik is not None:
        onset = onset_birlesik
        ek_not = birlesme_notu
    elif scroll_orani >= 0.3:
        # SCROLL-tip koşu — Görev 4'ün alanı (geri-tarama), burada DOKUNMA.
        # Mevcut davranış: scroll varsa kart→scroll geri-tarama.
        onset = a
        if scroll_var and onset < len(scroll):
            alt = max(0, onset - int(fps * 1.5 / stride))
            while onset - 1 >= alt and onset - 1 < len(scroll) and scroll[onset - 1] and jbayrak[onset - 1]:
                onset -= 1
        # alt-adım2 (şirket/stüdyo-kartı ileri-budaması) — yalnız `yabanci_yol`
        # DEĞİLSE çağrılır (yukarıdaki gard: Kiril/Arapça/scroll_kurtarma
        # yoluyla kazanılmış adaylarda bu bütünüyle atlanır, şüphede ileri
        # çekme yapılmaz).
        if not yabanci_yol:
            onset, ek_not = _scroll_sirket_budama(g, idx, cc, onset, n)
    else:
        # STATİK-tip koşu (T5) — koşu sınırı değil İÇERİK çapası: ileri-budama
        # (koşu başı kredi-dışı metni atla) + geri-genişletme (kartın gerçek
        # başlangıcına geri çek). Atlas kanıtı: ERKEN_METIN (KNUTE/TESS/...).
        onset, ek_not = _statik_icerik_onset(g, idx, a, b)
        # Kart-dizisi geri-genişletme (T6 2.tur, alt-adım3 — konsey kırmızı-
        # takım, ROBOCOP sınıfı): _statik_icerik_onset'in kredi_karti_mi'si tek
        # karede isim>=3 ister; kart-başına-tek-aktör dizilerinde (her karede
        # 1 isim) bu hiç tutmuyor. SADECE (zaten budanmış) `onset`in kendisine
        # bitişik geriye bakar — bağımsız tetikleme değil. DİKKAT (ölçüldü,
        # regresyon bulundu): `a` (ham koşu başı) değil `onset` (budama-sonrası
        # gerçek çapa) referans alınmalı — yoksa budama zaten `a`dan ileri
        # taşımışken bu fonksiyon "değişmedi" (kart_onset==a) dönse bile
        # a<onset olduğundan yanlışlıkla "genişledi" sanılıp budama iptal olur.
        kart_onset, kart_not = _kart_dizisi_geri_genislet(g, idx, cc, cb, onset)
        if kart_onset < onset:
            onset = kart_onset
            ek_not = (ek_not + " " if ek_not else "") + kart_not

    # Görev 1b (Seçenek B, 2026-07-29): _scroll_kurtarma son-çare yoluyla kazanılan
    # adayın kb/joint'i GERÇEK ÖLÇÜM DEĞİL (bkz. KURTARMA_GUVEN tanımı ve yukarıdaki
    # yer-tutucu uyarısı) — bu yüzden `guven` burada kb'den DEĞİL kurtarma_yolu
    # bayrağından türetilir, ve notlar'da uydurma kb/joint sayıları yerine
    # "kb=yok joint=yok" yazılır (okuyanı 1.00 güvenle yanıltmasın).
    if kurtarma_yolu:
        yontem = "kutu+scroll+kurtarma"
        guven = KURTARMA_GUVEN
        notlar = (f"yol=scroll_kurtarma aday={len(adaylar)} "
                  f"seçilen=[{_kare_no(g[idx[a]])}-{_kare_no(g[idx[b]])}] "
                  f"kb=yok joint=yok (içerik-eşiği geçilemedi) "
                  f"scroll_oran={scroll_orani:.2f} ardisik={ardisik_scroll} "
                  f"guven={guven:.2f}"
                  + (f" {ek_not}" if ek_not else ""))
    else:
        yontem = "kutu+scroll+içerik" if scroll_var else "kutu+içerik"
        guven = round(kb, 2)
        notlar = (f"aday={len(adaylar)} seçilen=[{_kare_no(g[idx[a]])}-{_kare_no(g[idx[b]])}] "
                  f"kb={kb:.2f} joint={joint:.2f} scroll_oran={scroll_orani:.2f} "
                  f"ardisik={ardisik_scroll} guven={guven:.2f}"
                  + (f" {ek_not}" if ek_not else ""))

    # Dalga-2 teşhis alanı `tip` (2026-07-29, SALT RAPORLAMA — karar dalı DEĞİL):
    # EŞİK burada BİLEREK 0.30 (yukarıdaki `elif scroll_orani >= 0.3:` karar dalı)
    # DEĞİL, 0.50 — 110-film korpusunda scroll_orani dağılımı bimodal: düşük küme
    # ≤0.42, sonra 0.42→0.55 arası BOŞLUK, sonra yoğun küme 0.55-1.00. 0.50 tam bu
    # boşluğa denk gelip sağlam ayrım verir; 0.30 düşük kümenin ortasında kalır
    # (0.27/0.32/0.32/0.34/0.35 komşularıyla kırılgan) ve %42 "scroll" oranı verir
    # (ölçülen doğru oran ~%36). `tip` yalnız teşhis/izleme amaçlı — onset seçimini
    # yöneten karar dalına (scroll-tip geri-tarama + şirket-budama vs statik-tip
    # içerik-onset) DOKUNMAZ, o dal kendi (ampirik kalibre) 0.3 eşiğini kullanmaya
    # devam eder.
    tip = "scroll" if scroll_orani >= 0.50 else "statik"

    return Sonuc(
        start_frame=_kare_no(g[idx[onset]]),
        yontem=yontem,
        guven=guven,
        dy_medyan=float(np.median(dys[a:b])) if a < len(dys) else 0.0,
        notlar=notlar,
        seri={"adaylar": kayitlar},
        tip=tip,
        scroll_orani=scroll_orani,
        ardisik_scroll=ardisik_scroll,
        son_capa=son_capa_kazanan,
        aday_sayisi=len(adaylar),
    )


if __name__ == "__main__":
    import sys

    # v3 (`tespit`) ve v4 (`tespit_v4`) 2026-07-29'da Çağatay'ın tek-motor
    # kararıyla söküldü (söküm öncesi commit 7b0a46f) — üretimde hiç
    # çağrılmıyorlardı, tek ölçen yolları da zaten kırıktı (bkz. modül
    # docstring'i). Bayrak hâlâ kas hafızasıyla yazılabilir diye sessizce
    # yok saymak yerine AÇIKÇA reddediyoruz.
    if "--v3" in sys.argv or "--v4" in sys.argv:
        print(
            "credit_onset.py --v3/--v4: bu motorlar 2026-07-29'da Çağatay'ın "
            "tek-motor kararıyla söküldü (söküm öncesi commit 7b0a46f). Tek "
            "yaşayan yol tespit_v5 (bayraksız veya --v5). CV karşılaştırma "
            "motoru hâlâ core/pipelines/ocr/jenerik_frame_pool_detector."
            "detect_frame_dir içinde yaşıyor — scripts/jenerik_start_eval.py "
            "onu kullanıyor.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    # --v5 kabul edilir ve yok sayılır (kas hafızası uyumu) — tek motor zaten
    # tespit_v5, bayrak yalnız eski çağrı alışkanlığını kırmamak için tolere edilir.
    yollar = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not yollar:
        print("kullanım: credit_onset.py [--v5] <kare-klasörü>", file=sys.stderr)
        raise SystemExit(2)

    r = tespit_v5(yollar[0])
    print(f"start={r.start_frame} yöntem={r.yontem} {r.notlar}")
