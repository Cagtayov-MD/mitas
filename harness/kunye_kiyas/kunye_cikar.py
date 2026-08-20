# -*- coding: utf-8 -*-
"""kunye_cikar — VL transkriptlerinden YAPILANDIRILMIŞ künye (2026-07-24, Kova-3).

Girdi (film başına, /opt/mitas/filmtest/test_film_vl/<slug>/):
  ÇIKIŞ: video_vl_r2/video_vl_okuma.txt (düzeltilmiş profil; yoksa video_vl/).
         Rescue filmlerinde (engine=vlm_rescue) çıkış OKUNMAZ — kaynak yok sayılır.
  GİRİŞ: video_vl_giris/video_vl_okuma.txt (+ varsa video_vl_giris300/).

Doktrin (2026-07-23/24 koşularının kare-kanıtlı dersleri):
  * ÇİFT-KAYNAK TEYİDİ: alan giriş+çıkışta ayni_kisi ile uyuşuyorsa guven="guvenli".
  * KARA LİSTE: modelin kanıtlı ünlü-isim halüsinasyonları ("John Ford" 4 kez) tek
    kaynakta geçerse guven="supheli"; ancak çift-kaynak teyidi aklar (Spielberg/JP2).
  * ÇELİŞKİ: kaynaklar farklı isim veriyorsa kara-listedeki elenir; ikisi de temizse
    guven="celiskili" ve iki aday da raporlanır (karar insana).
  * BOILERPLATE/UYDURMA süzgeci: "Thank You for Watching", example.com, hashtag,
    "John Doe" sınıfı şablonlar satır düzeyinde atılır.
  * Etiket dışlama: assistant/yardımcı/görüntü/first... "yönetmen" DEĞİLDİR;
    "Director Monitorizare" (POROROCA güvenlik-firması tuzağı) dışlanır.

Yalnız transkript verisine dayanır — dış bilgi (IMDb vb.) KULLANILMAZ; bu katman
"kartta ne yazıyor"un damıtılmasıdır, gerçek-dünya doğrulaması ayrı iştir.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import isim_normalize as inorm  # noqa: E402

KOK = Path("/opt/mitas/filmtest/test_film_vl")

# ---------------------------------------------------------------- etiketler
# alan -> (pozitif desen, "aynı satır" yakalama grubu opsiyonel)
ALANLAR: dict[str, str] = {
    "yonetmen": (
        r"(?:directed\s+by|direction|y[öo]netmen(?:\s+ve\s+senarist)?|senarist\s+ve\s+y[öo]netmen"
        r"|y[öo]neten|rejis[öo]r|r[ée]alisation|r[ée]alis[ée]\s+par|mise\s+en\s+sc[èe]ne"
        r"|un\s+film\s+de|regia(?:\s+di)?|regie|dirigid[oa]\s+por|direcci[oó]n"
        r"|re[żz]yseria|written\s+and\s+directed\s+by|a\s+film\s+by)"
    ),
    "senarist": r"(?:written\s+by|screenplay(?:\s+by)?|senarist|senaryo|sc[ée]nario|scenariul|scenariusz|drehbuch)",
    "yapimci": r"(?:produced\s+by|producer[s]?|yap[ıi]mc[ıi]|producteur|produttor[ei]|produzent)",
    "muzik": r"(?:music\s+by|[öo]zg[üu]n\s+m[üu]zik|m[üu]zik|musique|musica|muzyka|score\s+by)",
    "goruntu": r"(?:director\s+of\s+photography|g[öo]r[üu]nt[üu]\s+y[öo]netmeni|cinematograph|image[s]?|zdj[ęe]cia|kamera)",
    "kurgu": r"(?:edited\s+by|editor|kurgu|montage|monta[żj])",
}
# HERHANGİ bir künye etiketi/sözlüğü — "sonraki satır isim mi" adayları bunu İÇEREMEZ
# (v1 bug'ı: "Directed by"nin altındaki "Produced by" isim sanılıyordu).
_ETIKET_SOZLUK = re.compile(
    r"\b(?:by|producer|production|produced|written|starring|editor|edited|camera|sound"
    r"|music|müzik|muzik|ses|casting|costume|makeup|studio|st[üu]dyo|copyright|telif"
    r"|engineering|mixing|additional|supervisor|coordinator|designer|manager|company"
    r"|presents|entertainment|pictures|films?|distribution|gaffer|grip|foley|recordist"
    r"|electric|video|makeup|wardrobe)\b", re.IGNORECASE)
# Etiketin YÖNETMEN sayılmaması gereken bağlamları (tüm alanlar için ortak dışlayıcı)
DISLA = re.compile(
    r"assistant|asistan|yard[ıi]mc[ıi]|first|second|1st|2nd|unit|casting|art\s+direct"
    r"|g[öo]r[üu]nt[üu]|photograph|monitorizare|stunt|dialogue|dubbing|associate"
    r"|executive\s+direct|technical|sanat|\bses\b|sound|musical|m[üu]zikal"
    r"|music\s+direct|m[üu]zik\s+y[öo]net|\bproduction\b|yap[ıi]m\s+m[üu]d", re.IGNORECASE)
# goruntu/kurgu/muzik alanlarının kendi pozitifleri genel DISLA ile çakışır → alan-özel
# (v1.2 dersi: DISLA'ya "musical" eklenince müzik alanının kendi kartı dışlandı, alan
# kontamine kuyruktaki yanlış isme düştü — KANSAS/Bernstein vakası).
DISLA_ALAN = {
    "goruntu": re.compile(r"assistant|asistan|yard[ıi]mc[ıi]|first|second|unit|stunt", re.I),
    "kurgu": re.compile(r"assistant|asistan|yard[ıi]mc[ıi]|sound|ses", re.I),
    "muzik": re.compile(r"assistant|asistan|additional|engineer|mixing|editor", re.I),
}

KARA_LISTE = {  # kanıtlı ünlü-isim halüsinasyon havuzu (normalize edilmiş)
    "john ford", "john carpenter", "ridley scott", "gore verbinski",
    "michael cimino", "john milius", "sergio leone", "steven spielberg",
    "robert wise", "john williams", "michael bay", "asghar farhadi",
}

BOILERPLATE = re.compile(
    r"thank\s+you\s+for\s+watching|for\s+educational\s+purposes|copyright\s+infringement"
    r"|example\.com|examplefilm|@\w+|^#\w+|www\.|end\s+credits$|not\s+intended\s+for"
    r"|john\s+doe|jane\s+smith|robert\s+johnson|\[[^\]]*(?:name|isim)[^\]]*\]|movie\s?watcher"
    r"|film\s?lover|film\s?enthusiast", re.IGNORECASE)

CIFT_NOKTALI = re.compile(  # "Rol .... İSİM"  /  "Rol ... İSİM"
    r"^(?P<rol>[^.]{2,40}?)\s*\.{3,}\s*(?P<isim>.{2,45})$")
ROL_BUYUK_ISIM = re.compile(  # "Schuyler KIRK DOUGLAS" — Titlecase rol + BÜYÜK isim (≥2 kelime)
    r"^(?P<rol>[A-ZÇĞİÖŞÜ][a-zçğıöşü'.\- ]{1,28}?)\s+"
    r"(?P<isim>[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ'.\-]+(?:\s+[A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ'.\-]+){1,3})$")

RESCUE = {"1953-0044_KIZGIN_SILAH", "1973-0174_DERT_BENDE", "1958-0020_OLUM_ASANSORU"}


def satirlar(okuma: Path) -> list[str]:
    """Transkript → temiz satır listesi (başlıklar + boilerplate atılır)."""
    if not okuma.is_file():
        return []
    cikti = []
    for s in okuma.read_text(encoding="utf-8", errors="replace").splitlines():
        s = s.strip()
        if not s or s.startswith(("---", "=====")):
            continue
        if BOILERPLATE.search(s):
            continue
        cikti.append(s)
    return cikti


def _alan_yakala(sats: list[str], alan: str) -> list[tuple[str, str]]:
    """(isim, kanıt-satırı) adayları. Etiket aynı satırda ya da sonraki 1-2 satırda."""
    poz = re.compile(ALANLAR[alan], re.IGNORECASE)
    disla = DISLA_ALAN.get(alan, DISLA)
    bulunan: list[tuple[str, str, int]] = []
    for i, s in enumerate(sats):
        m = poz.search(s)
        if not m or disla.search(s):
            continue
        # aynı satırda etiketten sonra isim var mı
        kalan = s[m.end():].strip(" :.-–—")
        if kalan and len(kalan) >= 4 and inorm.isim_gibi_mi(kalan) \
                and not _ETIKET_SOZLUK.search(kalan) and "[" not in kalan:
            bulunan.append((kalan, s, i))
            continue
        # sonraki 1-2 satırda isim ara (boş etiket kartları: "Directed by\nHAL BARWOOD")
        for j in (i + 1, i + 2):
            if j < len(sats):
                aday = sats[j].strip(" :.-–—")
                if poz.search(aday) or disla.search(aday) or _ETIKET_SOZLUK.search(aday) \
                        or "[" in aday:
                    break
                if len(aday) >= 4 and inorm.isim_gibi_mi(aday):
                    bulunan.append((aday, f"{s} / {aday}", i))
                    break
    return bulunan


def _oyuncular(sats: list[str]) -> list[dict]:
    """Noktalı rol-isim çiftleri + cast-bölümü isimleri (pragmatik v1)."""
    cikti, gorulen = [], []
    for s in sats:
        m = CIFT_NOKTALI.match(s) or ROL_BUYUK_ISIM.match(s)
        if not m:
            continue
        isim = m.group("isim").strip()
        rol = m.group("rol").strip()
        if _ETIKET_SOZLUK.search(s) or len(rol) < 3:
            continue
        if not inorm.isim_gibi_mi(isim) or DISLA.search(rol):
            continue
        if any(inorm.ayni_kisi(isim, g) for g in gorulen):
            continue
        gorulen.append(isim)
        cikti.append({"rol": rol, "isim": isim})
        if len(cikti) >= 20:
            break
    return cikti


def _tekillestir(adaylar: list[tuple[str, str, int]]) -> list[tuple[str, str, int]]:
    """ayni_kisi ile grupla → (temsilci-isim, kanıt, ilk-görülme-indeksi), ERKEN olan önce.

    SIRALAMA erken-görülme'ye göre — tekrar SAYISI DEĞİL: uydurma döngüleri aynı
    ismi onlarca kez basar (DON_KİŞOT "Michael Bay" ×3 vs gerçek Gilliam ×1 dersi);
    gerçek künye kartı okumanın BAŞINDA bir kez görünür."""
    gruplar: list[list[tuple[str, str, int]]] = []
    for sira, t in enumerate(adaylar):
        isim, kanit = t[0], t[1]
        idx = t[2] if len(t) > 2 else sira
        for g in gruplar:
            if inorm.ayni_kisi(isim, g[0][0]):
                g.append((isim, kanit, idx))
                break
        else:
            gruplar.append([(isim, kanit, idx)])
    gruplar.sort(key=lambda g: min(x[2] for x in g))
    return [(g[0][0], g[0][1], min(x[2] for x in g)) for g in gruplar]


def _alan_karari(cikis_a: list, giris_a: list) -> dict:
    """Doktrin uygulaması: çift-kaynak / kara-liste / çelişki."""
    c = _tekillestir(cikis_a)
    g = _tekillestir(giris_a)
    if not c and not g:
        return {"isim": None, "guven": "yok"}
    # çift-kaynak eşleşmesi ara
    for ci, ck, _ in c:
        for gi, gk, _ in g:
            if inorm.ayni_kisi(ci, gi):
                return {"isim": ci, "guven": "guvenli", "kaynak": "giris+cikis",
                        "kanit": {"cikis": ck, "giris": gk}}
    tekler = ([(i, k, "cikis") for i, k, _ in c[:1]] + [(i, k, "giris") for i, k, _ in g[:1]])
    if len(tekler) == 2:  # iki kaynak FARKLI isim → çelişki; kara-listedeki elenir
        temiz = [(i, k, kay) for i, k, kay in tekler
                 if inorm.normalize(i) not in KARA_LISTE]
        if len(temiz) == 1:
            i, k, kay = temiz[0]
            return {"isim": i, "guven": "tek_kaynak", "kaynak": kay, "kanit": k,
                    "not": "diğer kaynağın adayı kara-listeden elendi"}
        return {"isim": None, "guven": "celiskili",
                "adaylar": [{"isim": i, "kaynak": kay, "kanit": k} for i, k, kay in tekler]}
    i, k, kay = tekler[0]
    if inorm.normalize(i) in KARA_LISTE:
        return {"isim": i, "guven": "supheli", "kaynak": kay, "kanit": k,
                "not": "kara-liste ismi, tek kaynak — teyitsiz KULLANMA"}
    return {"isim": i, "guven": "tek_kaynak", "kaynak": kay, "kanit": k}


def film_kunyesi(slug: str) -> dict:
    d = KOK / slug
    cikis_yolu = None
    if slug not in RESCUE:
        for ad in ("video_vl_r2", "video_vl"):
            p = d / ad / "video_vl_okuma.txt"
            if p.is_file():
                cikis_yolu = p
                break
    cikis = satirlar(cikis_yolu) if cikis_yolu else []
    giris = satirlar(d / "video_vl_giris" / "video_vl_okuma.txt")
    giris += satirlar(d / "video_vl_giris300" / "video_vl_okuma.txt")

    kunye: dict = {"slug": slug, "kaynaklar": {
        "cikis": str(cikis_yolu) if cikis_yolu else None,
        "rescue_istisna": slug in RESCUE}}
    for alan in ALANLAR:
        kunye[alan] = _alan_karari(_alan_yakala(cikis, alan), _alan_yakala(giris, alan))
    kunye["oyuncular"] = _oyuncular(cikis) or _oyuncular(giris)
    return kunye


def main() -> int:
    hedefler = sorted(p.name for p in KOK.iterdir()
                      if p.is_dir() and not p.name.startswith("_"))
    ozet = []
    for slug in hedefler:
        k = film_kunyesi(slug)
        (KOK / slug / "kunye.json").write_text(
            json.dumps(k, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        y = k["yonetmen"]
        ozet.append({"slug": slug, "yonetmen": y.get("isim"), "guven": y.get("guven"),
                     "oyuncu_sayisi": len(k["oyuncular"])})
        print(f"{slug:<50} yönetmen={y.get('isim')} [{y.get('guven')}] "
              f"oyuncu={len(k['oyuncular'])}")
    Path("/opt/mitas/outputs/TESTFILM_KUNYE_20260724.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n{len(hedefler)} film → kunye.json + outputs/TESTFILM_KUNYE_20260724.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
