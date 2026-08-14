"""Seçilmiş kareler → satırlar. Modeli BİLMEZ — `sor` geri-çağrısını kullanır.

Bu ayrım kasıtlı: burada model yok, dolayısıyla bu dosyanın tamamı GPU'suz
test edilebilir. Modele dokunan tek yer src/model.py.

Kaynak (davranış korundu):
  * fold-dedup            — pilot_hat.oku_deepseek
  * gevezelik süzgeci     — _pipe_hibrit_okuma._model_gevezeligi + _RET_KALIP
  * garble/çöküş dedektörü— _pipe_track_kunye.deepseek_saglik

Jordan dersi: istemde "no commentary" yazması YETMEZ — süzgeç kodda olmak zorunda.
"""
from __future__ import annotations

import difflib
import unicodedata
from pathlib import Path
from typing import Callable


class ModelYok(RuntimeError):
    """Model kurulu değil / yüklenemedi. main.py bunu ARIZA(MODEL)'e çevirir."""


class Bellek(RuntimeError):
    """CUDA OOM. main.py bunu ARIZA(BELLEK)'e çevirir."""


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s
                   if not unicodedata.combining(c)
                   and (c.isalnum() or c.isspace())).strip()


# Modelin "bu goruntude metin yok" tipi RET/BETIMLEME cumleleri — OCR ciktisi
# DEGIL, ekranda YOK. Her biri gercek bir uretim kazasindan geldi.
_RET_KALIP = (
    "没有可识别", "无法识别", "图片中", "该图片", "未检测到",       # ZH ret cumleleri
    "no recognizable", "no text", "cannot identify", "unable to read",
    "the image shows", "this image",
    # deepseek bicim-basliklari (YAZ TATILI 1963-0035, 2026-08-01): model cevabini
    # markdown gibi bicimlendirip baslik satirlari basiyor. O filmde YONETMEN
    # adinin ustunde 'Caption:' / 'Markdown-style Summary:' duruyordu — rol
    # eslemenin baglami bozuluyordu.
    "markdown-style", "markdown style", "caption:", "summary:", "ozet:",
    "here is the", "here's the", "extracted text", "ocr result", "transcription:",
)


def gevezelik_mi(s: str) -> bool:
    """Yazılmaması gereken satır mı? (ekranda olmayan model sözü)

    MUHAFAZAKÂR: gerçek jenerik metnini ASLA atmaz. Yalnız
      (a) köşeli parantezli blok  — '[图片中没有可识别的文字内容]'
      (b) bilinen ret/betimleme kalıbı
      (c) TEK karakterlik CJK gürültüsü ('福' — jenerikte tek karakter kart olmaz)
    düşer. Çok karakterli gerçek CJK jenerik ('客串演出', '导演') KORUNUR.
    """
    t = (s or "").strip()
    if not t:
        return False
    if t.startswith("[") and t.endswith("]"):
        return True
    if any(k in t.lower() for k in _RET_KALIP):
        return True
    cjk = [c for c in t if "一" <= c <= "鿿"]
    return bool(cjk) and len([c for c in t if c.isalnum()]) <= 1


_TR = str.maketrans("ıİIğĞüÜşŞöÖçÇ", "iiigguussoocc")


def fold_tr(s: str) -> str:
    """Türkçe-güvenli normalizasyon (ronaldo.fold_tr ile birebir).

    `fold`'dan AYRI tutuluyor: üretimde de iki ayrı katlama var — dedup
    `pilot_hat.fold` kullanıyor, yapısal veto `ronaldo.fold_tr`. Birleştirmek
    ölçülmemiş bir davranış değişikliği olurdu.
    """
    s = s.translate(_TR).lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join("".join(c if (c.isalnum() or c.isspace()) else " "
                            for c in s).split())


def garble_mi(satir: str) -> bool:
    """Slit çift-basımı / tekrar-desenli çöp (ronaldo.garble_mi ile birebir)."""
    f = fold_tr(satir)
    kelimeler = f.split()
    if len(kelimeler) >= 2 and len(kelimeler) % 2 == 0:
        yarim = len(kelimeler) // 2
        if kelimeler[:yarim] == kelimeler[yarim:]:
            return True
    duz = f.replace(" ", "")
    if len(duz) > 40:
        gramlar: dict[str, int] = {}
        for i in range(len(duz) - 2):
            g = duz[i:i + 3]
            gramlar[g] = gramlar.get(g, 0) + 1
        if max(gramlar.values()) >= len(duz) // 6:
            return True
    return False


# Duzyazi fiil imzasi — model EKRANI OKUMAK yerine SAHNEYI ANLATIYORSA bu
# kelimeler gecer. Jenerik satirlarinda gecmez. (_pipe_hibrit_okuma ile birebir.)
_PROSA_FIIL = {
    "is", "are", "was", "were", "has", "have", "had", "he", "she", "it",
    "its", "there", "appears", "appear", "seems", "seem", "looks",
    "showing", "shows", "suggests", "suggesting",
    "captures", "capturing", "depicts", "depicting", "likely",
    "gorunuyor", "goruluyor", "gosteriyor", "bulunuyor", "olabilir", "vardir",
}


def yapisal_veto(s: str) -> str | None:
    """Ekranda OLMAYAN satır mı? Sebep döner, temizse None.

    `_pipe_hibrit_okuma.yapisal_veto`'nun birebir taşınmışı. Orada kanonik
    çıktıya (kunye.txt) uygulanıyor, ham çıktıya değil. Nash ham katmandır —
    ama ekranda olmayan bir paragrafı "okundu" diye raporlamak kulenin kendi
    sözleşmesine aykırıdır. Bu yüzden burada uygulanır, AMA satır yok
    edilmez: `elenen`e düşürülür (track_kunye'nin dusuk_guven.txt deseni).
    Yanlış eleme yapıyorsak GÖRÜNÜR olsun.
    """
    if s.startswith("[") or s.startswith("("):
        return "anlatim_parantez"       # model sahneyi ANLATIYOR
    # MADDE İMİ KURALI ÜRETİMDEN ALINDI, SONRA ÖLÇÜMLE KALDIRILDI (2026-08-14).
    #
    # Üretimde (_pipe_hibrit_okuma.yapisal_veto) '- ' ile başlayan satır komple
    # eleniyor; gerekçe ALİE vakası: '- A river flowing...'. Genelleme
    # "jenerikte madde imi olmaz" idi ve YANLIŞ çıktı.
    #
    # Sadakat sondajı ölçtü: KERMİT BATAKLIKTA / cikis_0384 — Muppet Workshop
    # künyesi ekranda GERÇEKTEN madde imli bir isim listesi. Kural o karede
    # İKİ motorda da 14 GERÇEK İSMİ eledi (Heather Asch, Rollie Krewson,
    # Polly Smith…). Ölçülen zarar somut; ALİE'nin varsayılan zararı ise
    # düzyazı/garble kurallarıyla zaten büyük ölçüde örtülü.
    #
    # Yeni davranış: madde imi `_kirp`'te SOYULUR, satır kalır; kalan içerik
    # öteki kurallardan geçer. AÇIK BORÇ: ALİE sınıfı ('- ' + düzyazı ama
    # fiilsiz) için daha iyi bir ayraç gerekiyor — bu ölçülmeden eklenmez.
    if "**" in s:
        return "markdown"
    # HTML/tablo artefakti — modelin "belgeyi markdown'a cevir" refleksi.
    # Sadakat sondajinda gorulldu (BOZGUNCULAR cikis_0647, 2026-08-14): bos
    # karede model '<table><tr><td>Category</td><td>Value</td>...' uydurdu.
    # Ust satirdaki markdown kuralinin ayni sinifi; jenerik satiri '<' ile
    # baslamaz, '<td>' icermez.
    if s.startswith("<") or any(t in s.lower() for t in ("<td>", "<tr>", "<table")):
        return "html_artefakt"
    harfler = [c for c in s if c.isalpha()]
    if not harfler:
        return "harfsiz"                # '- 1' liste-numarasi copu (olculdu: %32)
    if sum(1 for c in harfler if "一" <= c <= "鿿") / len(harfler) > 0.3:
        return "cjk_betimleme"
    if any(k in _PROSA_FIIL for k in fold_tr(s).split()):
        return "duzyazi_fiil"
    if garble_mi(s):
        return "garble_desen"
    return None


def _kirp(ln: str) -> str:
    """Model çıktısındaki markdown süslerini soy.

    pilot_hat.oku_deepseek ile aynı, ARTI madde imi soyma (2026-08-14 ölçümü,
    `yapisal_veto` içindeki gerekçe): '- **Heather Asch' → 'Heather Asch'.
    İmi elemek yerine soymak, ekranda gerçekten madde imli olan künye
    listelerini korur. Sıra önemli: önce im, sonra kalan yıldızlar.
    """
    s = ln.strip().strip("`").lstrip("#").strip().strip("*").strip()
    for im in ("- ", "* ", "• ", "-", "•"):
        if s.startswith(im):
            s = s[len(im):].strip()
            break
    return s.strip("*").strip()


def oku(sayfalar: list[Path], sor: Callable[[Path], str],
        dedup_esigi: float = 0.92) -> tuple[list[dict], dict]:
    """Sayfaları sırayla oku → (kayıtlar, kanıt).

    `sor(png) -> str` modele soran geri-çağrı. Bellek dışındaki istisnalar
    sayfa bazında yutulur ama SAYILIR: bugün üretimde patlayan sayfa `continue`
    ile sessizce atlanıyor ve 12 sayfadan 9'u okunmuş çıktı "tam" görünüyor.

    Dedup pilot_hat ile birebir: yalnız BİR ÖNCEKİ sayfanın satırlarına bakılır
    (`onceki`), tüm geçmişe değil — jenerikte aynı isim gerçekten iki kez
    geçebilir, uzak tekrar korunmalı.
    """
    kayitlar: list[dict] = []
    elenen: list[dict] = []
    onceki: set[str] = set()
    sayfa_hata_n = 0

    for sayfa_sira, p in enumerate(sayfalar, start=1):
        try:
            cevap = sor(p)
        except Bellek:
            raise
        except Exception:
            sayfa_hata_n += 1
            continue
        yeni: set[str] = set()
        satir_sira = 0
        for ham in (cevap or "").splitlines():
            ln = _kirp(ham)
            f = fold(ln)
            if not ln or len(f) < 2:
                continue
            yeni.add(f)
            if f in onceki:
                continue
            if any(difflib.SequenceMatcher(None, f, o).ratio() >= dedup_esigi
                   for o in onceki):
                continue
            sebep = "gevezelik" if gevezelik_mi(ln) else yapisal_veto(ln)
            if sebep:
                # YOK EDILMEZ, DUSURULUR — yanlis eleme gorunur olsun.
                elenen.append({"kaynak": p.name, "text": ln, "sebep": sebep})
                continue
            kayitlar.append({"kaynak": p.name, "sayfa_sira": sayfa_sira,
                             "satir_sira": satir_sira, "text": ln})
            satir_sira += 1
        onceki = yeni or onceki

    sebepler: dict[str, int] = {}
    for e in elenen:
        sebepler[e["sebep"]] = sebepler.get(e["sebep"], 0) + 1
    return kayitlar, {"sayfa_hata_n": sayfa_hata_n,
                      "elenen_n": len(elenen), "elenme_sebepleri": sebepler,
                      "elenen": elenen[:50]}


def saglik(metinler: list[str], ayar: dict | None = None) -> tuple[bool, str]:
    """Ucuz çöküş dedektörü — rodeo sınıfı boş/garble döküm işaretlenir.

    Sağlıksız çıktı ARIZA(CIKTI_BOZUK) olur: model konuştu ama kullanılamaz.
    'Model hiç yazı bulamadı' ile 'model çöktü' ayrı şeylerdir.
    """
    a = ayar or {}
    if not metinler:
        return False, "bos_cikti"
    birlesik = "\n".join(metinler)
    if len(birlesik) < int(a.get("min_uzunluk", 200)):
        return False, "cok_kisa"
    alnum = sum(1 for c in birlesik if c.isalnum())
    if alnum / max(1, len(birlesik)) < float(a.get("min_alnum_oran", 0.30)):
        return False, "garble_yuksek"
    return True, "ok"
