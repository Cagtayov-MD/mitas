#!/usr/bin/env python3
"""Katman-0 sadakat ölçümü — ham-kare vs master-PNG metin-recall.

Bugüne kadar `dup_metrik.py` (M1) master-PNG'yi YALNIZ KENDİ İÇİNDE
("bu görüntüde tekrar var mı") ölçüyordu. Bu, üretilen künyenin KAYNAK
karelerdeki OKUNABİLİR metni ne kadar SADIK içerdiğini hiç sormuyor —
tam da bu yüzden `acemiler-cetesi`/`benimle-dans-et` gibi gerçek "mod
hatası" (kayan jenerik statik-sayfa olarak derlendi) vakalarında dup_oran
~0 çıkıp defekt tamamen gözden kaçıyordu (bkz. mod_denetim.py + M10 bulgusu).

Bu modül BAĞIMSIZ bir ikinci-katman ölçüm ekler: "var olan" (ham karelerin
OCR birleşimi) ile "yakalanan" (master PNG'nin OCR'ı) arasındaki metin-
recall'i. Kayıp/ezik/mod-hatası kusurlarının HEPSİ bu tek metrikte görünür
— dup_oran'ın GÖREMEDİĞİ boşluğu kapatan tamamlayıcı bir kabul-kapısıdır.

NOT (isim çakışması UYARISI): `uret.py`'deki `sadakat_kaniti()` FARKLI bir
kavramı ölçer — "bu harness üretim kompozisyon mantığını birebir mi
çağırıyor" (script-üretim sadakati). Buradaki "sadakat" ise "master PNG
kaynak metni sadık mı taşıyor" (içerik/metin sadakati) — isim benzerliği
kasıtlı (ikisi de "üretilen şey kaynağa ne kadar sadık" sorusuna cevap
arıyor) ama ölçtükleri şey ayrı.

ALGORİTMA
  1. "var olan" — ham kareler (/home/cagatay/Ex_Frame/<slug>-exit_frames/
     exit_*.png) örneklenir (kayan jenerikte ardışık kareler örtüştüğünden
     TÜMÜ gerekmez — bkz. MALİYET altında), her örnek karede üretimle AYNI
     OCR motoru (db_compose_master.py F1b det + F1c rec — `uret.py`/
     `saglik.py` üzerinden SALT-OKUNUR import, bkz. `k3_recall_testi.py`
     ile AYNI erişim deseni) çalıştırılır, kutu-metinleri kelimelere
     bölünür, normalize edilir (küçük-harf + noktalama/boşluk sadeleştir —
     `_f1c_normalize_text`, zaten `_f1c_rec_boxes` içinde uygulanıyor),
     >=3 karakterli tokenlar benzersiz kümede toplanır.
  2. "yakalanan" — master PNG (data/master_ex/<slug>/reading_master.png)
     üzerinde AYNI OCR motoru + AYNI normalize/filtre. Master boyu 31px'ten
     45000px'e kadar değişebildiği için (bkz. saglik.py H_MAKS) TEK parçada
     değil, örtüşmeli yatay BANTLAR halinde taranır (`master_bantlari`) —
     PaddleOCR det üretimde hep kart-boyu (ör. 480px) kırpımlarla çağrılıyor,
     binlerce piksellik tek görüntüde davranışı doğrulanmamış; bant örtüşmesi
     (200px) tipik satır yüksekliğinin (bkz. dup_metrik VARSAYILAN_SATIR_
     YUKSEKLIGI=48) kat kat üstünde -- bir satırın HER İKİ bantta da kesilip
     kaybolması pratikte olmaz. Örtüşme kasıtlı olduğundan (algılama-bağlamı
     için) ama SAYIM çakışmasız olmalı: her kutu yalnız KENDİ bandının
     çakışmasız "çekirdeğine" (bkz. `bant_cekirdekleri` — dup_metrik.py'nin
     pencere/hücre ayrımıyla aynı fikir) düşerse `occ`'a girer -- aksi halde
     örtüşme bölgesindeki bir satır iki bantta da sayılıp `okunabilirlik`i
     çarpıtırdı (bkz. GLM konsey incelemesi, sadakat_raporu.md §4).
  3. text_recall = |yakalanan ∩ var| / |var| (var boşsa durum='kunye_yok',
     recall=None — ölçülecek bir şey yok, 0 ile karıştırılmaz). SET-tabanlı
     olduğu için bant-çekirdek filtresinden BAĞIMSIZ olarak zaten doğruydu.
  4. okunabilirlik = master'da bulunan TÜM token-OKUNUŞLARININ (kutu-bazlı
     güven; AYNI fiziksel satırın komşu bant örtüşmesinden çifte sayılması
     §2'deki çekirdek-filtresiyle önlenir, ama görüntüde GERÇEKTEN birden
     fazla yerde geçen bir kelime -- ör. iki farklı rolde aynı isim -- kasıtlı
     olarak tekilleştirilmez, "ezik metin" sinyali tekrar sayısıyla orantılı
     güçlenmeli) conf>=0.6 oranı (aynı eşik: saglik.py TEK_KART_REC_ESIK_VARSAYILAN).

MALİYET YÖNETİMİ: ham-kare OCR pahalı. Kare-örnekleme (`orneklenmis_kareler`)
film başına taban ~HEDEF_ORNEK_KARE_VARSAYILAN (20) kareye sabitlenir
(linspace — mod_denetim.py'nin kendi örnekleme desenini yeniden kullanır);
master bantlama da toplam OCR-çağrı sayısını master boyuyla orantılı ama
sınırlı tutar. Hedef: film başına <60sn (bkz. sadakat_raporu.md'de ölçülmüş
gerçek süreler — bazı aşırı-uzun masterlarda aşılabilir, rapor bunu açıkça
not eder).

UYARLAMALI ÖRNEKLEME (6-film doğrulamasında BULUNDU, bkz. `hedef_kare_uyarla`):
düz sabit-20 hedefi, ÇOK-kareli (uzun/hızlı-kayan) filmlerde "var" (referans)
kümesini master'dan DAHA DAR örnekleyebiliyordu (olum-emri kanıtı: 272 kareden
20-örnek var_token=972 ÜRETTİ AMA master'ın TÜM kareden derlenmiş yakalanan_
token'ı 1068 ÇIKTI — referans master'dan daha zengin olamayacağına göre bu,
referansın eksik örneklendiğinin kanıtı). Düzeltme: hedef n'in karekökÜyle
hafif (alt-doğrusal) ölçekleniyor, tavanla (40) sınırlanıyor — kısa filmlerde
davranış değişmez.

KÜRESEL KISITLAR: venv python /opt/mitas/venvs/ocr/bin/python; pkill yasak;
git add -A yasak; PaddleOCR çıktısı gürültülü (2>/dev/null önerilir);
harness/kunye_kiyas SALT-OKUNUR (bu modül ona hiç dokunmuyor zaten).

CLI:
  sadakat.py --film solaris                       # tek slug, ekrana yazdır
  sadakat.py --dogrulama --json cikti.json         # 6 bilinen doğrulama filmi
  sadakat.py --ornek 40 --tohum 42 --json cikti.json  # N-film rastgele örneklem
  sadakat.py --tumu --json cikti.json              # TÜM evren (pahalı — dikkat)
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saglik  # noqa: E402  (uret._dc() erişimi için — k3_recall_testi.py ile AYNI desen)

# --------------------------------------------------------------------------- #
# sabit yollar / parametreler
# --------------------------------------------------------------------------- #
EX_KARE_ROOT = Path("/home/cagatay/Ex_Frame")
EX_SUFFIX = "-exit_frames"
MASTER_KOK = Path("/opt/mitas/data/master_ex")

HEDEF_ORNEK_KARE_VARSAYILAN = 20
HEDEF_ORNEK_KARE_TAVAN = 40
MIN_TOKEN_UZUNLUK = 3
OKUNABILIRLIK_CONF_ESIK = 0.6  # saglik.py TEK_KART_REC_ESIK_VARSAYILAN ile AYNI eşik

MASTER_BANT_YUKSEKLIK = 1200
MASTER_BANT_ORTUSME = 200

DOGRULAMA_SETI = [
    "benimle-dans-et",  # mod-hatası, kayan-statik -> recall DÜŞÜK beklenir
    "olum-emri",        # hızlı-kayan (Nyquist) -> recall DÜŞÜK, kayıp beklenir
    "solaris",          # temiz tek-kart -> recall YÜKSEK beklenir
    "baba-2",           # atlas-onarımlı -> recall makul beklenir
    "hizli-silah",      # atlas-onarımlı -> recall makul/yüksek beklenir
    "acemiler-cetesi",  # mod-hatası, dup_oran=0 (dup_metrik'in KAÇIRDIĞI vaka)
]


# --------------------------------------------------------------------------- #
# ham kare listesi / örnekleme
# --------------------------------------------------------------------------- #
def ham_kareler(slug: str) -> list[str]:
    d = EX_KARE_ROOT / f"{slug}{EX_SUFFIX}"
    return sorted(str(p) for p in d.glob("exit_*.png"))


def orneklenmis_kareler(kareler: list[str], hedef: int = HEDEF_ORNEK_KARE_VARSAYILAN) -> list[str]:
    """n<=hedef ise TÜMÜNÜ kullan (kaçırmamak için); n>hedef ise linspace ile
    tüm aralığa yayılmış benzersiz `hedef` kare seç (mod_denetim.py'nin
    `kayma_olc` örnekleme deseniyle AYNI — tutarlılık + kanıtlanmış yaklaşım)."""
    n = len(kareler)
    if n <= hedef:
        return list(kareler)
    idx = sorted(set(np.linspace(0, n - 1, hedef).round().astype(int).tolist()))
    return [kareler[i] for i in idx]


def hedef_kare_uyarla(
    n: int, taban: int = HEDEF_ORNEK_KARE_VARSAYILAN, tavan: int = HEDEF_ORNEK_KARE_TAVAN
) -> int:
    """DÜZ sabit hedef (20), TOPLAM kare sayısı çok büyüdüğünde (uzun/hızlı-kayan
    jenerik) "var" kümesini yapay biçimde daraltıp recall'i güvenilmez kılabilir.

    KANIT (sadakat_raporu.md 6-film doğrulaması, olum-emri): 272 ham kareden
    sabit-20 linspace örneklemesiyle var_token=972 çıktı, AMA master (TÜM 272
    kareden derlendi) yakalanan_token=1068 üretti -- yani master'ın kendi OCR
    okuması bizim "referans" kümemizden DAHA ZENGİN çıktı. Bu, referansın
    (var) master'dan daha eksik örneklendiğinin doğrudan kanıtı -- düşük
    recall'in bir kısmı gerçek içerik kaybı değil, ölçüm-tarafı eksik-
    örnekleme olabilir.

    Düzeltme: hedefi n'in karekökÜyle HAFİF ölçekle (sqrt -- n arttıkça alt-
    doğrusal büyür, maliyet patlamaz), `tavan` ile sınırla. Kısa filmlerde
    (n<=taban) davranış DEĞİŞMEZ (zaten tüm kareler kullanılıyor)."""
    if n <= taban:
        return n
    return min(tavan, max(taban, round((n ** 0.5) * 2)))


# --------------------------------------------------------------------------- #
# master bantlama (45000px'e kadar çıkabilen master için sabit-bellek OCR)
# --------------------------------------------------------------------------- #
def master_bantlari(
    h: int, bant_h: int = MASTER_BANT_YUKSEKLIK, ortusme: int = MASTER_BANT_ORTUSME
) -> list[tuple[int, int]]:
    """[0,h) aralığını örtüşmeli (ortusme px) bantlara böler; son bant TAM h'de
    biter (görüntü boyunu eksiksiz kaplar). h<=bant_h ise tek bant döner."""
    if h <= 0:
        return []
    if h <= bant_h:
        return [(0, h)]
    adim = max(1, bant_h - ortusme)
    bantlar: list[tuple[int, int]] = []
    y = 0
    while y < h:
        y2 = min(y + bant_h, h)
        bantlar.append((y, y2))
        if y2 >= h:
            break
        y += adim
    return bantlar


def bant_cekirdekleri(bantlar: list[tuple[int, int]], ortusme: int = MASTER_BANT_ORTUSME) -> list[tuple[int, int]]:
    """Örtüşmeli bantlardan ÇAKIŞMASIZ 'çekirdek' (muhasebe) aralığı türetir --
    dup_metrik.py'nin pencere/hücre ayrımıyla AYNI fikir: geniş örtüşmeli pencere
    algılama/bağlam için kullanılır, dar çakışmasız çekirdek İSE SAYIM için
    (bkz. GLM konsey incelemesi: bir metin satırı iki bandın örtüşme bölgesine
    düşerse HER İKİ bantta da algılanıp `occ` listesine İKİ KEZ eklenebiliyordu
    -- `okunabilirlik`i sistematik çarpıtıyordu; `text_recall` set-tabanlı
    olduğundan ETKİLENMEZ). Örtüşen şerit ÖNCEKİ bandın çekirdeğine verilir
    (sonraki bant çekirdeği o kadar geriden başlar); çekirdekler [0,h)'yi
    BOŞLUKSUZ ve ÇAKIŞMASIZ döşer."""
    n = len(bantlar)
    cekirdekler: list[tuple[int, int]] = []
    for i, (y0, y1) in enumerate(bantlar):
        c1 = (y1 - ortusme) if i < n - 1 else y1
        cekirdekler.append((y0, max(y0, c1)))
    return cekirdekler


# --------------------------------------------------------------------------- #
# görüntü okuma + OCR (üretimle AYNI F1b det / F1c rec motoru)
# --------------------------------------------------------------------------- #
def _gri_yukle(path) -> np.ndarray | None:
    return cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)


def _det_rec_kutulari(gray: np.ndarray | None, dc) -> list[tuple[str, float, float]]:
    """gray görüntüde det+rec çalıştırır -> [(kutu-metni normalize, güven, cy_norm), ...].

    Ham KUTU-seviyesi çıktı (kelimelere bölünmemiş, `cy_norm`=kutu dikey merkezi
    0-1 normalize edilmiş -- `dc._f1b_det_boxes`'ın döndürdüğü şema, `box[1]`).
    `det_rec_tokenlari` (konumsuz, ham kareler için) VE `master_tokenlari`
    (konum bantlarını çekirdek-filtrelemek için, bkz. o fonksiyon) BUNUN
    üzerine inşa edilir -- OCR çağrısı TEK yerde (kod tekrarı yok)."""
    if gray is None or gray.size == 0:
        return []
    try:
        boxes = dc._f1b_det_boxes(gray)
    except Exception:
        boxes = None
    if not boxes:
        return []
    boxes_sorted = dc._f1b_boxes_sorted(boxes)
    try:
        rec = dc._f1c_rec_boxes(gray, boxes_sorted)
    except Exception:
        rec = []
    return [(text, float(conf), float(box[1])) for (text, conf), box in zip(rec, boxes_sorted)]


def det_rec_tokenlari(gray: np.ndarray | None, dc) -> list[tuple[str, float]]:
    """gray görüntüde det+rec çalıştırır -> [(normalize-token, kutu-güveni), ...].

    Kutu metni (zaten `_f1c_rec_boxes` içinde normalize edilmiş) boşlukla
    kelimelere bölünür; >=MIN_TOKEN_UZUNLUK karakterli olanlar tutulur. Bir
    kutunun TEK güveni, o kutudan çıkan HER kelimeye aynen atanır (PaddleOCR
    rec kutu-başına tek skor döner, kelime-başına değil). Konum bilgisi
    (`cy_norm`) burada atılır -- ham kareler bantlanmıyor, çekirdek-filtreye
    gerek yok (bkz. `master_tokenlari`)."""
    out: list[tuple[str, float]] = []
    for text, conf, _cy_norm in _det_rec_kutulari(gray, dc):
        for tok in text.split():
            if len(tok) >= MIN_TOKEN_UZUNLUK:
                out.append((tok, conf))
    return out


def var_kunye_tokenlari(slug: str, dc, hedef_kare: int = HEDEF_ORNEK_KARE_VARSAYILAN) -> dict:
    """Ham örnek karelerin OCR birleşimi -> {'var': set, 'frame_sayisi', 'ornek_kare'}.

    `hedef_kare` TABAN olarak kullanılır -- gerçek örnek sayısı `hedef_kare_uyarla`
    ile toplam kare sayısına göre yukarı ölçeklenebilir (bkz. o fonksiyonun
    docstring'i -- uzun/hızlı filmlerde referans kümesini zenginleştirir)."""
    kareler = ham_kareler(slug)
    hedef_efektif = hedef_kare_uyarla(len(kareler), taban=hedef_kare)
    ornek = orneklenmis_kareler(kareler, hedef_efektif)
    var: set[str] = set()
    for p in ornek:
        gray = _gri_yukle(p)
        for tok, _conf in det_rec_tokenlari(gray, dc):
            var.add(tok)
    return {"var": var, "frame_sayisi": len(kareler), "ornek_kare": len(ornek)}


def master_tokenlari(slug: str, dc) -> dict:
    """Master PNG'nin bantlanmış OCR'ı -> {'yakalanan': set, 'occ': [(tok,conf),...], 'boy': (w,h)|None}.

    Her bandın kutuları yalnız o bandın ÇEKİRDEK (çakışmasız) aralığına düşerse
    `occ`'a eklenir (bkz. `bant_cekirdekleri`) -- örtüşme bölgesindeki bir
    satırın komşu bantta TEKRAR sayılıp `okunabilirlik`i çarpıtmasını önler.
    `yakalanan` zaten SET olduğu için bu fix'ten önce de/sonra da aynı kalır
    (yalnız `occ`/okunabilirlik etkilenir)."""
    png = MASTER_KOK / slug / "reading_master.png"
    if not png.is_file():
        return {"yakalanan": set(), "occ": [], "boy": None}
    gray = _gri_yukle(png)
    if gray is None:
        return {"yakalanan": set(), "occ": [], "boy": None}
    h, w = gray.shape[:2]
    bantlar = master_bantlari(h)
    cekirdekler = bant_cekirdekleri(bantlar)
    son_bant = len(bantlar) - 1
    occ: list[tuple[str, float]] = []
    for i, ((y0, y1), (c0, c1)) in enumerate(zip(bantlar, cekirdekler)):
        bant_h = y1 - y0
        for text, conf, cy_norm in _det_rec_kutulari(gray[y0:y1, :], dc):
            y_tam = y0 + cy_norm * bant_h
            # Çekirdek aralığı [c0,c1) yarı-açık: komşu bantlar arasındaki paylaşılan
            # sınırda ÇİFTE SAYIM olmasın diye. TEK istisna: son bandın ÜST sınırı
            # (c1==h) bir SONRAKİ banda devredilemez -- orada kapalı aralık kullanılır,
            # yoksa tam y_tam==h'e denk gelen (kuramsal ama olası) bir kutu HİÇBİR
            # bantta sayılmadan sessizce kaybolurdu.
            icinde = (c0 <= y_tam < c1) or (i == son_bant and y_tam == c1)
            if not icinde:
                continue  # bu kutu bu bandın ÇEKİRDEĞİ dışında -- komşu bant zaten sayacak
            for tok in text.split():
                if len(tok) >= MIN_TOKEN_UZUNLUK:
                    occ.append((tok, conf))
    return {"yakalanan": {t for t, _ in occ}, "occ": occ, "boy": (int(w), int(h))}


# --------------------------------------------------------------------------- #
# ana ölçüm
# --------------------------------------------------------------------------- #
def sadakat_olc(slug: str, *, hedef_kare: int = HEDEF_ORNEK_KARE_VARSAYILAN, dc=None) -> dict:
    """Bkz. modül docstring'i. Dönüş: {text_recall, okunabilirlik, var_token,
    yakalanan_token, kesisim_token, durum, frame_sayisi, ornek_kare,
    master_boy, sure_s}."""
    t0 = time.time()
    if dc is None:
        dc = saglik._uret_mod()._dc()

    kareler = ham_kareler(slug)
    if not kareler:
        return {
            "slug": slug, "text_recall": None, "okunabilirlik": None,
            "var_token": 0, "yakalanan_token": 0, "durum": "kare_yok",
            "sure_s": round(time.time() - t0, 2),
        }

    var_sonuc = var_kunye_tokenlari(slug, dc, hedef_kare)
    var: set[str] = var_sonuc["var"]

    png_path = MASTER_KOK / slug / "reading_master.png"
    if not png_path.is_file():
        return {
            "slug": slug, "text_recall": None, "okunabilirlik": None,
            "var_token": len(var), "yakalanan_token": 0, "durum": "master_yok",
            "frame_sayisi": var_sonuc["frame_sayisi"], "ornek_kare": var_sonuc["ornek_kare"],
            "sure_s": round(time.time() - t0, 2),
        }

    if not var:
        # Ham karelerde bile anlamlı token bulunamadı -- recall tanımsız
        # (0 ile karıştırılmaz). Yine de master'ı teşhis amaçlı ölçüp
        # yakalanan_token'ı raporla (tam kör olmayalım).
        m = master_tokenlari(slug, dc)
        return {
            "slug": slug, "text_recall": None, "okunabilirlik": None,
            "var_token": 0, "yakalanan_token": len(m["yakalanan"]), "durum": "kunye_yok",
            "frame_sayisi": var_sonuc["frame_sayisi"], "ornek_kare": var_sonuc["ornek_kare"],
            "master_boy": list(m["boy"]) if m["boy"] else None,
            "sure_s": round(time.time() - t0, 2),
        }

    m = master_tokenlari(slug, dc)
    yakalanan: set[str] = m["yakalanan"]
    occ: list[tuple[str, float]] = m["occ"]
    boy = m["boy"]

    kesisim = yakalanan & var
    recall = len(kesisim) / len(var)
    okunur = (sum(1 for _, c in occ if c >= OKUNABILIRLIK_CONF_ESIK) / len(occ)) if occ else None

    return {
        "slug": slug,
        "text_recall": round(recall, 4),
        "okunabilirlik": round(okunur, 4) if okunur is not None else None,
        "var_token": len(var),
        "yakalanan_token": len(yakalanan),
        "kesisim_token": len(kesisim),
        "durum": "olculdu",
        "frame_sayisi": var_sonuc["frame_sayisi"],
        "ornek_kare": var_sonuc["ornek_kare"],
        "master_boy": list(boy) if boy else None,
        "sure_s": round(time.time() - t0, 2),
    }


# --------------------------------------------------------------------------- #
# evren / rastgele örneklem
# --------------------------------------------------------------------------- #
def tum_slugler() -> list[str]:
    if not EX_KARE_ROOT.is_dir():
        return []
    return sorted(
        p.name[: -len(EX_SUFFIX)] for p in EX_KARE_ROOT.iterdir()
        if p.is_dir() and p.name.endswith(EX_SUFFIX)
    )


def rastgele_ornek(n: int = 40, tohum: int = 42) -> list[str]:
    """Deterministik rastgele örneklem (sabit tohum -> tekrar-üretilebilir).
    Evren `tum_slugler()`'ın kendisi sıralı olduğundan dosya-sistemi
    sıralamasından bağımsız aynı sonucu verir."""
    tum = tum_slugler()
    rnd = random.Random(tohum)
    return sorted(rnd.sample(tum, min(n, len(tum))))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--film", default=None, help="tek slug ölç")
    grp.add_argument("--dogrulama", action="store_true", help="6 bilinen doğrulama filmini ölç")
    grp.add_argument("--ornek", type=int, default=None, metavar="N", help="N-film rastgele örneklem")
    grp.add_argument("--tumu", action="store_true", help="TÜM evren (pahalı -- dikkatli kullan)")
    ap.add_argument("--tohum", type=int, default=42, help="--ornek için rastgele tohum (varsayılan 42)")
    ap.add_argument("--hedef-kare", type=int, default=HEDEF_ORNEK_KARE_VARSAYILAN)
    ap.add_argument("--json", dest="json_cikti", default=None, help="Sonucu JSON olarak bu yola yaz")
    args = ap.parse_args(argv)

    if args.film:
        slugs = [args.film]
    elif args.dogrulama:
        slugs = DOGRULAMA_SETI
    elif args.ornek:
        slugs = rastgele_ornek(args.ornek, args.tohum)
    else:
        slugs = tum_slugler()

    if not slugs:
        print("Eşleşen slug yok.", file=sys.stderr)
        return 1

    dc = saglik._uret_mod()._dc()

    sonuclar = []
    t_baslangic = time.time()
    for i, s in enumerate(slugs):
        r = sadakat_olc(s, hedef_kare=args.hedef_kare, dc=dc)
        sonuclar.append(r)
        print(
            f"[{i + 1}/{len(slugs)}] {s[:38]:<39} recall={r['text_recall']} "
            f"okunabilirlik={r['okunabilirlik']} durum={r['durum']:<10} "
            f"var={r['var_token']:<4} yakalanan={r['yakalanan_token']:<4} "
            f"{r['sure_s']}s",
            flush=True,
        )

    out = {
        "n": len(sonuclar),
        "tohum": args.tohum if args.ornek else None,
        "hedef_kare": args.hedef_kare,
        "sure_toplam_s": round(time.time() - t_baslangic, 1),
        "sonuclar": sonuclar,
    }
    olculen = [r for r in sonuclar if r["text_recall"] is not None]
    if olculen:
        recalls = sorted(r["text_recall"] for r in olculen)
        n = len(recalls)
        medyan = recalls[n // 2] if n % 2 else (recalls[n // 2 - 1] + recalls[n // 2]) / 2
        print(
            f"\n{len(olculen)}/{len(sonuclar)} ölçülebilir -- "
            f"recall medyan={medyan:.3f} ort={sum(recalls) / n:.3f} min={recalls[0]:.3f} max={recalls[-1]:.3f}"
        )

    if args.json_cikti:
        Path(args.json_cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {args.json_cikti}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
