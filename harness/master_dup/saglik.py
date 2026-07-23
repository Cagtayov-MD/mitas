#!/usr/bin/env python3
"""Sağlık sınıflandırıcısı (Görev M7/M8, MITAS_Master_Dup_Kok_Sebep_Plani_v1.md).

SAĞLIK TANIMI (K4 kalibrasyonu SONRASI -- M8 konsey kararı, "K4" maddesi):
  1. üretim OK       -> manifest.status == "OK", istisna yok, kept_blocks >= 1
  2. dup_oran <= 0.10 -> metrik.json (dup_metrik.py M1, F1/F1b/F1c SONRASI)
  3. boy makul       -> 300 <= H <= 45000 (canavar/boş master değil) -- İSTİSNA
     (K4-ii, "tek-kart istisnası"): kept_blocks <= 3 VE status == "OK" VE
     det-metin-var (PaddleOCR det en az 1 kutu + o kutulardan en az birinde
     rec conf >= 0.6) ise boy kontrolü ATLANIR (kısa-ama-tam jenerik kartları
     "canavar/boş" ile karıştırmama -- bkz. ex_dup_siniflandirma.md boy_anormal
     çapraz-kontrolü: ben-hur/solaris gibi kısa ama İÇERİK OLARAK eksiksiz
     kartlar bu kritere yanlışlıkla takılıyordu). Det TEMBEL çalışır: yalnız
     boy zaten eşik-dışıysa VE kept_blocks<=3 ise (aksi halde PaddleOCR hiç
     çağrılmaz) -- sonuç film başına bir kez bellek-içi önbelleklenir.
  4. doku_kapsami >= 0.05 -> kapkara/boş master değil

K4-i (M8): eskiden 4. kriter olan "imha-imzası YOK" SAĞLIK FORMÜLÜNDEN
ÇIKARILDI (Ex_Frame'de 6/6 gerçek-vaka yanlış-pozitif çıktı -- bkz.
ex_dup_siniflandirma.md "Sınıf B" bölümü: imha_imzasi alan 10 filmin 6'sı
görsel incelemede metin HER YERDE tam okunaklı çıktı, "13px'e ezik" B-paterni
YOK). Teşhis DEĞERİ hâlâ var (M4b B-tespiti için sinyal) -- bu yüzden
sağlığı ETKİLEMEZ ama her film için ayrı `teshis_bayraklari` alanında VE
toplu `teshis_dagilimi`nde raporlanmaya devam eder. `--imha-saglik-etkiler`
bayrağıyla eski (K4-öncesi) davranış karşılaştırma amacıyla geri getirilebilir.

Girdi: BİR masters kökü -- her alt-klasör <FİLM>/{manifest.json, metrik.json,
reading_master.png} şemasında olmalı (uret.py VE uret_ex.py'nin ortak çıktı
şeması -- bu yüzden bu sınıflandırıcı hem `data/master_dup/masters_v2/` hem
`data/master_ex/` üzerinde DEĞİŞİKLİKSİZ çalışır). Alt-klasör adı "_" ile
başlıyorsa (ör. `_siniflandirma`, `_pencere_tmp`) film SAYILMAZ, atlanır --
bunlar tanık-kırpım/geçici scratch dizinleridir, film evrenine dahil değildir.

Çıktı: film başına {saglikli: bool, ihlaller: [...], teshis_bayraklari: [...]}
+ toplu sağlık oranı + ihlal-sınıfı dağılımı (hangi kriter kaç filmi
düşürüyor) + teşhis-bayrağı dağılımı (sağlığı etkilemeyen ama raporlanan
sinyaller).

CLI:
  saglik.py <masters_kok> [--json cikti.json] [--dup-esik 0.10] ...
  saglik.py data/master_ex --json data/master_ex/saglik_ex.json
  saglik.py data/master_dup/masters_v2 --json data/master_dup/saglik_v2.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import dup_metrik  # K3 (Görev M8): protected-çift muafiyetiyle dup_oran yeniden-ölçüm

DUP_ESIK_VARSAYILAN = 0.10
H_MIN_VARSAYILAN = 300
H_MAKS_VARSAYILAN = 45000
DOKU_ESIK_VARSAYILAN = 0.05
STATIK_ORAN_ESIK_VARSAYILAN = 0.70
CILIZ_H_ESIK_VARSAYILAN = 25
CILIZ_MIN_SAYI_VARSAYILAN = 2
TEK_KART_KEPT_MAKS_VARSAYILAN = 3
TEK_KART_REC_ESIK_VARSAYILAN = 0.6

IHLAL_ETIKETLERI = {
    "manifest_yok": "manifest.json yok/okunamadı",
    "uretim_basarisiz": "üretim OK değil (status != OK, PNG eksik, ya da kept_blocks < 1)",
    "dup_oran_yuksek": "dup_oran eşik üstü (ya da metrik.json yok)",
    "boy_anormal": "H eşik dışı (canavar/boş boy) -- tek-kart istisnası uygulanmadıysa",
    "doku_kapsami_dusuk": "doku_kapsami eşik altı (kapkara/boş master)",
}

# K4-i: imha_imzasi artık SAĞLIĞI ETKİLEMEZ -- yalnız teşhis bayrağı (ayrı sözlük,
# IHLAL_ETIKETLERI'nden bilinçli olarak çıkarıldı ki ihlal_dagilimi/saglikli
# hesaplarına asla karışmasın; --imha-saglik-etkiler eski davranışı geri getirir).
TESHIS_ETIKETLERI = {
    "imha_imzasi": "statik-sayfa alanı > eşik VE >=N cılız blok (footage-üstü ezilme şüphesi) -- SAĞLIĞI ETKİLEMEZ, teşhis amaçlı",
}


# --------------------------------------------------------------------------- #
# db_compose_master.py'nin det/rec yardımcılarını SALT-OKUNUR import (K4-ii,
# tek-kart istisnası). harness/master_dup/uret.py zaten aynı zinciri
# (uret.py -> master_png_monitor.py -> db_compose_master.py) kuruyor; burada
# TEKRAR YAZMAK yerine uret.py'nin _dc() erişimcisi yeniden kullanılıyor --
# OCR başlatma/çağrı mantığı üretimle (F1b/F1c) TUTARLI kalır.
# --------------------------------------------------------------------------- #
_URET_MOD = None
_DET_METIN_VAR_CACHE: dict[str, bool] = {}


def _uret_mod():
    global _URET_MOD
    if _URET_MOD is None:
        uret_path = Path(__file__).resolve().parent / "uret.py"
        spec = importlib.util.spec_from_file_location("uret_core_saglik", str(uret_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _URET_MOD = mod
    return _URET_MOD


TEK_KART_DET_DENEME_VARSAYILAN = 3  # bkz. modül içi not: paylaşılan det motoru kararsız

# M9 (det-None stabilite fix'i, docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md M7/M8
# takibi): mavzer/solaris (H=25/31px) 4 art arda tam-427 ölçümünde True/False
# arasında SIÇRADI -- ikisi de bu eşiğin ALTINDA. ipek-yolu/kasabanin-gulu/
# yilmayan-adam (H=43-73px) İSE 4/4 tutarlı kaldı -- eşiğin ÜSTÜNDE kararlı.
# Bu ayrım kırılma noktasını işaret ediyor: paylaşılan PaddleOCR TextDetection
# motoru bu kadar kısa/dar kırpımlarda (h VEYA w < 32px) içeriden istisna atıp
# sessizce None dönmeye YATKIN -- motora hiç girilmez, deterministik "metin-yok"
# sayılır (None-belirsizliği ölçüm katmanında burada kapanır).
DET_MIN_KIRPIM_PX = 32


def det_metin_var(
    png_path: Path,
    *,
    rec_esik: float = TEK_KART_REC_ESIK_VARSAYILAN,
    deneme: int = TEK_KART_DET_DENEME_VARSAYILAN,
) -> bool:
    """PaddleOCR det (TEMBEL init) + en az 1 kutuda rec conf>=rec_esik -> True.

    Yalnız tek-kart istisnası adayı filmlerde (boy zaten eşik-dışı VE
    kept_blocks<=N) çağrılır -- diğer tüm filmlerde PaddleOCR'a HİÇ dokunulmaz
    (maliyet: yalnız gerçekten tartışmalı ~17-20 film, ~427 değil). Sonuç film
    başına bir kez film-yolu anahtarıyla bellek-içi önbelleklenir (aynı süreçte
    tekrar çağrılırsa OCR yeniden koşulmaz).

    NEDEN `deneme` (RETRY) VAR (K4 ölçümü sırasında bulundu, systematic-
    debugging ile teşhis edildi): `db_compose_master.py`'nin paylaşılan
    `_F1B_DET_ENGINE` PaddleOCR TextDetection nesnesi çok kısa (H<~50px)
    kırpımlarda ARA SIRA (aynı bayt-birebir PNG'de, süreçten sürece, hatta
    aynı süreç içinde tekrar çağrıldığında) sessizce istisna fırlatıp None
    dönüyor -- 4 art arda tam-427 ölçümünde `mavzer`/`solaris` (H=25/31px)
    True/False arasında SIÇRADI, `ipek-yolu`/`kasabanin-gulu`/`yilmayan-adam`
    (H=43-73px) İSE 4/4 tutarlı None kaldı (muhtemelen ger perçek kutusuz).
    Kesin C++/thread-havuzu kök sebebi bu dosyanın kapsamı dışında (composer
    SALT-OKUNUR, K4 yalnız saglik.py değiştirir) -- gözlemlenen davranış:
    motor metni VARKEN ara sıra KAÇIRIYOR, metin YOKKEN sahte metin UYDURMUYOR
    (bkz. ipek-yolu/kasabanin-gulu/yilmayan-adam'ın 4/4 tutarlı boş çıkması).
    Bu asimetri güvenli bir yön verir: art arda `deneme` kez dene, HERHANGİ
    biri metin bulursa True kabul et (yanlış-negatifi azalt); tüm denemeler
    boşsa False (gerçek metin yokluğu ile motor-kararsızlığını normal
    şartlarda ayırt edemeyiz, ama biriktirilmiş 4-tekrar kanıtı gerçek-boş
    filmlerin HİÇ sıçramadığını gösteriyor -- bkz. dup_dokumu K4 raporu).

    M9 GÜNCELLEMESİ (docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md M7/M8 takibi,
    saglik/dup_metrik ölçüm yolundaki det-None salınımı fix'i): yukarıdaki
    SIÇRAMA sınırı tam olarak `DET_MIN_KIRPIM_PX` (32px) civarında -- mavzer/
    solaris (25/31px, sıçrayan) bu eşiğin ALTINDA, ipek-yolu/kasabanin-gulu/
    yilmayan-adam (43-73px, 4/4 tutarlı) ÜSTÜNDE. Artık h VEYA w < 32px ise
    det'e HİÇ girilmez (deterministik False) -- motorun bilinen-kararsız
    rejimine hiç girilmediği için salınım kalkar (mavzer/solaris artık HER
    ölçümde tutarlı False = tek-kart istisnası uygulanmaz = boy_anormal).
    32px ÜSTÜ kırpımlarda ise `_f1b_det_boxes`'ın None dönüşü (composer'ın
    "istisna/kapı geçmedi" durumu -- bkz. o fonksiyonun docstring'i) artık BİR
    kez daha denenir; hâlâ None ise bu tur için deterministik boş-kutu-listesi
    sayılır (None bir daha asla dışarı sızmaz, `boxes` bundan sonra hep liste)."""
    key = str(png_path)
    if key in _DET_METIN_VAR_CACHE:
        return _DET_METIN_VAR_CACHE[key]
    sonuc = False
    try:
        from PIL import Image
        import numpy as np

        if not png_path.is_file():
            sonuc = False
        else:
            gray = np.array(Image.open(png_path).convert("L"))
            h_px, w_px = gray.shape[:2]
            if h_px < DET_MIN_KIRPIM_PX or w_px < DET_MIN_KIRPIM_PX:
                # M9: kısa/dar kırpım -- det motoru bu boyutlarda kararsız
                # (bkz. modül-üstü not); HİÇ ÇAĞRILMAZ, deterministik metin-yok.
                sonuc = False
            else:
                dc = _uret_mod()._dc()
                for _ in range(max(1, deneme)):
                    boxes = dc._f1b_det_boxes(gray)
                    if boxes is None:
                        # M9: istisna durumu (_f1b_det_boxes içeride yakalayıp
                        # None döndürdü) -- 1 yeniden-deneme; hâlâ None ise bu
                        # turu deterministik "kutu yok" say (None-belirsizliği
                        # kalksın -- bundan sonra `boxes` her zaman bir liste).
                        boxes = dc._f1b_det_boxes(gray)
                        if boxes is None:
                            boxes = []
                    if boxes:
                        for box in dc._f1b_boxes_sorted(boxes):
                            _text, conf = dc._f1c_rec_text(gray, box)
                            if conf >= rec_esik:
                                sonuc = True
                                break
                    if sonuc:
                        break
    except Exception:
        sonuc = False
    _DET_METIN_VAR_CACHE[key] = sonuc
    return sonuc


# --------------------------------------------------------------------------- #
# K3 (Görev M8): protected-çift muafiyeti -- composer'ın manifest.blocks'a
# kaydettiği `korunan_esleme` (bkz. db_compose_master.py _k3_protected_evidence)
# alanlarını final master PNG'deki y-aralıklarına çevirip dup_metrik.olc()'a
# geçirir; olc() bu aralıklarla ÇOĞUNLUKLA örtüşen "es" (tekrar) bloklarını
# dup_oran hesabından düşer (composer'ın SKIP/KORU kararı ETKİLENMEZ -- yalnız
# bu ölçüm katmanında, meşru-farklı-metin/Sınıf-C metrik yanlış-pozitifi
# düzeltilir).
# --------------------------------------------------------------------------- #
def korunan_araliklari(manifest: dict, sep_px: int) -> list[tuple[int, int]]:
    """manifest.blocks (kept/skip'siz, h alanı olan) için final PNG y-aralığını
    kümülatif olarak hesaplar (h + sep_px ayraç); `korunan_esleme` taşıyanları
    [(y0,y1), ...] olarak döner."""
    y = 0
    araliklar: list[tuple[int, int]] = []
    for b in manifest.get("blocks") or []:
        if not isinstance(b, dict) or "skip" in b or b.get("h") is None:
            continue
        h = int(b["h"])
        if b.get("korunan_esleme"):
            araliklar.append((y, y + h))
        y += h + sep_px
    return araliklar


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def degerlendir(
    film_dir: Path,
    *,
    dup_esik: float = DUP_ESIK_VARSAYILAN,
    h_min: int = H_MIN_VARSAYILAN,
    h_maks: int = H_MAKS_VARSAYILAN,
    doku_esik: float = DOKU_ESIK_VARSAYILAN,
    statik_oran_esik: float = STATIK_ORAN_ESIK_VARSAYILAN,
    ciliz_h_esik: int = CILIZ_H_ESIK_VARSAYILAN,
    ciliz_min_sayi: int = CILIZ_MIN_SAYI_VARSAYILAN,
    tek_kart_istisna: bool = True,
    tek_kart_kept_maks: int = TEK_KART_KEPT_MAKS_VARSAYILAN,
    tek_kart_rec_esik: float = TEK_KART_REC_ESIK_VARSAYILAN,
    imha_saglik_etkiler: bool = False,
    k3_protected_muafiyet: bool = True,
) -> dict:
    """Tek film klasörünü değerlendirir (K4 SONRASI: 4 sağlık kriteri VE 1
    teşhis-amaçlı bayrak -- bkz. modül docstring'i)."""
    film = film_dir.name
    ihlaller: list[str] = []
    teshis_bayraklari: list[str] = []
    detay: dict = {}

    manifest = _load_json(film_dir / "manifest.json")
    if manifest is None:
        return {
            "film": film, "saglikli": False, "ihlaller": ["manifest_yok"],
            "teshis_bayraklari": [], "detay": {},
        }

    metrik = _load_json(film_dir / "metrik.json")
    png_var = (film_dir / "reading_master.png").is_file()

    status = manifest.get("status")
    kept_blocks = manifest.get("kept_blocks")
    detay["status"] = status
    detay["kept_blocks"] = kept_blocks
    detay["png_var"] = png_var

    # --- Kriter 1: üretim OK ---
    if status != "OK" or not png_var or not kept_blocks or kept_blocks < 1:
        ihlaller.append("uretim_basarisiz")

    # metrik alanları (dup_oran, doku_kapsami, boy)
    dup_oran = metrik.get("dup_oran") if metrik else None
    doku_kapsami = metrik.get("doku_kapsami") if metrik else None
    boy = (metrik.get("boy") if metrik else None) or manifest.get("size")

    # K3 (Görev M8): protected-çift muafiyeti -- yalnız GEREKTİĞİNDE (dup_oran
    # zaten eşik üstüyse VE manifest'te en az bir korunan_esleme bloğu varsa)
    # dup_metrik.olc() korunan aralıklarla YENİDEN çağrılır (tembel -- 427
    # filmin çoğunda hiç tetiklenmez, composer manifest'i işaretlemediyse).
    dup_oran_ham = dup_oran
    korunan_uygulandi = False
    if k3_protected_muafiyet and dup_oran is not None and dup_oran > dup_esik and png_var:
        korunan = korunan_araliklari(manifest, _uret_mod()._dc().SEP_PX)
        if korunan:
            try:
                yeni_metrik = dup_metrik.olc(film_dir / "reading_master.png", korunan_araliklari=korunan)
                if yeni_metrik.get("dup_oran") is not None:
                    dup_oran = yeni_metrik["dup_oran"]
                    korunan_uygulandi = True
            except Exception:
                pass  # yeniden-ölçüm başarısızsa ham değer kullanılmaya devam eder

    detay["dup_oran"] = dup_oran
    detay["dup_oran_ham"] = dup_oran_ham
    detay["korunan_cift_uygulandi"] = korunan_uygulandi
    detay["doku_kapsami"] = doku_kapsami
    detay["boy"] = boy

    # --- Kriter 2: dup_oran (K3 muafiyeti sonrası) ---
    if dup_oran is None or dup_oran > dup_esik:
        ihlaller.append("dup_oran_yuksek")

    # --- Kriter 3: boy (+ K4-ii tek-kart istisnası) ---
    h = boy[1] if boy and len(boy) == 2 else None
    boy_ok = h is not None and (h_min <= h <= h_maks)
    tek_kart_istisnasi_uygulandi = False
    det_metin_var_sonuc = None
    if (
        not boy_ok
        and tek_kart_istisna
        and status == "OK"
        and kept_blocks is not None
        and kept_blocks <= tek_kart_kept_maks
    ):
        # Tembel: PaddleOCR yalnız burada, yalnız gerçek adaylarda çağrılır.
        det_metin_var_sonuc = det_metin_var(film_dir / "reading_master.png", rec_esik=tek_kart_rec_esik)
        if det_metin_var_sonuc:
            boy_ok = True
            tek_kart_istisnasi_uygulandi = True
    detay["tek_kart_istisnasi_uygulandi"] = tek_kart_istisnasi_uygulandi
    detay["det_metin_var"] = det_metin_var_sonuc
    if not boy_ok:
        ihlaller.append("boy_anormal")

    # --- Teşhis (SAĞLIĞI ETKİLEMEZ): imha-imzası -- statik-sayfa alanı + cılız
    # blok birlikteliği (K4-i, bkz. modül docstring'i) ---
    blocks = manifest.get("blocks") or []
    kept = [b for b in blocks if isinstance(b, dict) and b.get("h") is not None and not b.get("skip")]
    total_h = h if h is not None else (sum(b["h"] for b in kept) if kept else None)
    if kept and total_h:
        static_h = sum(b["h"] for b in kept if b.get("kind") == "static_page")
        static_oran = static_h / total_h
        ciliz_sayisi = sum(1 for b in kept if b["h"] < ciliz_h_esik)
    else:
        static_oran = 0.0
        ciliz_sayisi = 0
    detay["static_oran"] = round(static_oran, 4)
    detay["ciliz_blok_sayisi"] = ciliz_sayisi
    imha_supheli = (static_oran > statik_oran_esik) and (ciliz_sayisi >= ciliz_min_sayi)
    if imha_supheli:
        teshis_bayraklari.append("imha_imzasi")
        if imha_saglik_etkiler:  # --imha-saglik-etkiler: K4-öncesi davranışla karşılaştırma
            ihlaller.append("imha_imzasi")

    # --- Kriter 4: doku_kapsami ---
    if doku_kapsami is None or doku_kapsami < doku_esik:
        ihlaller.append("doku_kapsami_dusuk")

    return {
        "film": film,
        "saglikli": len(ihlaller) == 0,
        "ihlaller": ihlaller,
        "teshis_bayraklari": teshis_bayraklari,
        "detay": detay,
    }


def olc_kok(masters_kok: Path, **kwargs) -> dict:
    # "_" ile başlayan alt-klasörler (ör. _siniflandirma tanık-kırpım dizini,
    # _pencere_tmp geçici kare dizini) film SAYILMAZ -- evren dışı bırakılır
    # (aksi halde n sahte biçimde 427'nin üstüne çıkar, sağlık oranı seyrelir).
    filmler = sorted(
        p for p in masters_kok.iterdir() if p.is_dir() and not p.name.startswith("_")
    )
    sonuclar = [degerlendir(p, **kwargs) for p in filmler]
    n = len(sonuclar)
    saglikli_n = sum(1 for s in sonuclar if s["saglikli"])
    dagilim: dict[str, int] = {}
    teshis_dagilim: dict[str, int] = {}
    for s in sonuclar:
        for ihlal in s["ihlaller"]:
            dagilim[ihlal] = dagilim.get(ihlal, 0) + 1
        for bayrak in s.get("teshis_bayraklari", []):
            teshis_dagilim[bayrak] = teshis_dagilim.get(bayrak, 0) + 1
    return {
        "masters_kok": str(masters_kok),
        "n": n,
        "saglikli_sayi": saglikli_n,
        "saglik_orani": round(saglikli_n / n, 4) if n else 0.0,
        "ihlal_dagilimi": dagilim,
        "teshis_dagilimi": teshis_dagilim,
        "sonuclar": sonuclar,
    }


def en_kotu_n(sonuc: dict, n: int = 15) -> list[dict]:
    """Sağlıksız filmleri ihlal-sayısına (çoktan aza) göre sıralar; en kötü N'i döner."""
    sagliksiz = [s for s in sonuc["sonuclar"] if not s["saglikli"]]
    sagliksiz.sort(key=lambda s: (-len(s["ihlaller"]), s["detay"].get("dup_oran") or 0.0, s["film"]))
    return sagliksiz[:n]


def _cli(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("masters_kok", type=Path, help="masters kökü (ör. data/master_ex veya data/master_dup/masters_v2)")
    ap.add_argument("--json", dest="json_cikti", default=None, help="Sonucu JSON olarak bu yola yaz")
    ap.add_argument("--dup-esik", type=float, default=DUP_ESIK_VARSAYILAN)
    ap.add_argument("--h-min", type=int, default=H_MIN_VARSAYILAN)
    ap.add_argument("--h-maks", type=int, default=H_MAKS_VARSAYILAN)
    ap.add_argument("--doku-esik", type=float, default=DOKU_ESIK_VARSAYILAN)
    ap.add_argument("--statik-oran-esik", type=float, default=STATIK_ORAN_ESIK_VARSAYILAN)
    ap.add_argument("--ciliz-h-esik", type=int, default=CILIZ_H_ESIK_VARSAYILAN)
    ap.add_argument("--ciliz-min-sayi", type=int, default=CILIZ_MIN_SAYI_VARSAYILAN)
    ap.add_argument("--no-tek-kart-istisna", dest="tek_kart_istisna", action="store_false",
                     help="K4-ii tek-kart istisnasını kapat (karşılaştırma/eski davranış)")
    ap.add_argument("--tek-kart-kept-maks", type=int, default=TEK_KART_KEPT_MAKS_VARSAYILAN)
    ap.add_argument("--tek-kart-rec-esik", type=float, default=TEK_KART_REC_ESIK_VARSAYILAN)
    ap.add_argument("--imha-saglik-etkiler", action="store_true",
                     help="K4-i öncesi davranış: imha_imzasi'nı yeniden sağlık ihlaline çevir (karşılaştırma amaçlı)")
    ap.add_argument("--no-k3-protected-muafiyet", dest="k3_protected_muafiyet", action="store_false",
                     help="K3 protected-çift muafiyetini kapat (karşılaştırma/K1-sonrası-K3-öncesi ölçüm)")
    ap.add_argument("--en-kotu", type=int, default=15, help="konsolda gösterilecek en kötü N (varsayılan 15)")
    args = ap.parse_args(argv)

    if not args.masters_kok.is_dir():
        print(f"Kök bulunamadı: {args.masters_kok}", file=sys.stderr)
        return 1

    sonuc = olc_kok(
        args.masters_kok,
        dup_esik=args.dup_esik, h_min=args.h_min, h_maks=args.h_maks,
        doku_esik=args.doku_esik, statik_oran_esik=args.statik_oran_esik,
        ciliz_h_esik=args.ciliz_h_esik, ciliz_min_sayi=args.ciliz_min_sayi,
        tek_kart_istisna=args.tek_kart_istisna, tek_kart_kept_maks=args.tek_kart_kept_maks,
        tek_kart_rec_esik=args.tek_kart_rec_esik, imha_saglik_etkiler=args.imha_saglik_etkiler,
        k3_protected_muafiyet=args.k3_protected_muafiyet,
    )
    print(f"{sonuc['saglikli_sayi']}/{sonuc['n']} sağlıklı (%{sonuc['saglik_orani'] * 100:.1f})")
    print("İhlal dağılımı:", json.dumps(sonuc["ihlal_dagilimi"], ensure_ascii=False))
    print("Teşhis dağılımı (sağlığı etkilemez):", json.dumps(sonuc["teshis_dagilimi"], ensure_ascii=False))
    print(f"\nEn kötü {args.en_kotu}:")
    for s in en_kotu_n(sonuc, args.en_kotu):
        print(f"  {s['film'][:55]:55} ihlaller={s['ihlaller']} dup={s['detay'].get('dup_oran')} "
              f"boy={s['detay'].get('boy')} static_oran={s['detay'].get('static_oran')} "
              f"ciliz={s['detay'].get('ciliz_blok_sayisi')}")

    if args.json_cikti:
        Path(args.json_cikti).write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n-> {args.json_cikti}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
