"""Master PNG → satırlar. Modeli BİLMEZ — `sor` geri-çağrısını kullanır.

Bu ayrım kasıtlı: burada model yok, dolayısıyla bu dosyanın tamamı GPU'suz
test edilebilir. Modele dokunan tek yer src/model.py.

Kaynak (davranış korundu, uydurma yok):
  * bantlama 1100/120     — _pipe_hibrit_okuma.kol_master:298-313
                            ("pilot_hat.oku_master ile aynı geometri", satır 59)
  * satır ayıklama        — _pipe_hibrit_okuma.satirlari_ayikla
  * kutu_n piksel kanıtı  — _pipe_hibrit_okuma._det_kutu_n + birlesim:393
  * gevezelik süzgeci     — _pipe_hibrit_okuma._RET_KALIP / _model_gevezeligi
  * yapısal veto          — _pipe_hibrit_okuma.yapisal_veto
  * fold-dedup            — pilot_hat.oku_deepseek

Jordan dersi: istemde "no commentary" yazması YETMEZ — süzgeç kodda olmak zorunda.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Callable

# Bant geometrisi — ÜRETİMDEN, uydurma değil (_pipe_hibrit_okuma.py:59).
BANT_H = 1100
BINDIRME = 120
MIN_BANT_H = 40      # bundan kısa son bant atılır (kol_master:305)


class ModelYok(RuntimeError):
    """Model kurulu değil / yüklenemedi. main.py bunu ARIZA(MODEL)'e çevirir."""


class Bellek(RuntimeError):
    """CUDA OOM. main.py bunu ARIZA(BELLEK)'e çevirir."""


class OkumaCoktu(RuntimeError):
    """Bantların HEPSİ okunamadı. main.py bunu ARIZA(OKUMA_COKTU)'ya çevirir.

    Tek tek bant hatası okumayı durdurmaz (sayılır, künyeye yazılır) — ama
    hepsi patladıysa ortada "yazı yok" değil, OKUYAMADIK durumu vardır.
    """


# --------------------------------------------------------------------------- #
# bantlama
# --------------------------------------------------------------------------- #
def bant_sinirlari(yukseklik: int, bant_h: int = BANT_H,
                   bindirme: int = BINDIRME) -> list[int]:
    """Master'ın y-ofsetleri. kol_master'ın döngüsüyle BİREBİR.

    Bindirme neden var: bant sınırına denk gelen bir satır ikiye bölünürse
    hiçbir bantta tam okunmaz. 120 px örtüşme satırın en az bir bantta bütün
    görünmesini garantiler. Bedeli tekrar eden satırlardır — `ayikla` fold-dedup
    ile temizler.
    """
    if yukseklik <= 0:
        return []
    ofsetler: list[int] = []
    y = 0
    while y < yukseklik:
        if min(y + bant_h, yukseklik) - y >= MIN_BANT_H:
            ofsetler.append(y)
        if y + bant_h >= yukseklik:
            break
        y += bant_h - bindirme
    return ofsetler


# --------------------------------------------------------------------------- #
# satır süzgeçleri — hepsi gerçek üretim kazalarından
# --------------------------------------------------------------------------- #
def satirlari_ayikla(cevap: str) -> list[str]:
    """Model cevabını satırlara böl (_pipe_hibrit_okuma.satirlari_ayikla)."""
    out = []
    for ln in (cevap or "").splitlines():
        ln = ln.strip().strip("`").lstrip("#").strip().strip("*").strip()
        if len(ln) >= 2:
            out.append(ln)
    return out


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
    """Türkçe-güvenli normalizasyon (ronaldo.fold_tr ile birebir)."""
    s = s.translate(_TR).lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join("".join(c if (c.isalnum() or c.isspace()) else " "
                            for c in s).split())


def garble_mi(satir: str) -> bool:
    """Slit çift-basımı / tekrar-desenli çöp (ronaldo.garble_mi ile birebir).

    Master'da özellikle önemli: kayan jenerik yanlış hizalanırsa aynı kelime
    dizisi iki kez basılır ve model onu sadakatle okur.
    """
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

    Satır YOK EDİLMEZ — `elenen`e düşürülür ve künyede sayılır. Yanlış eleme
    yapıyorsak GÖRÜNÜR olsun (Nash'in aynı kararı).
    """
    if s.startswith("[") or s.startswith("("):
        return "anlatim_parantez"       # model sahneyi ANLATIYOR
    if "**" in s:
        return "markdown"
    # HTML/tablo artefakti — modelin "belgeyi markdown'a cevir" refleksi.
    if s.startswith("<") or any(t in s.lower() for t in ("<td>", "<tr>", "<table")):
        return "html_artefakt"
    harfler = [c for c in s if c.isalpha()]
    if not harfler:
        return "harfsiz"                # '- 1' liste-numarasi copu
    if sum(1 for c in harfler if "一" <= c <= "鿿") / len(harfler) > 0.3:
        return "cjk_betimleme"
    if any(k in _PROSA_FIIL for k in fold_tr(s).split()):
        return "duzyazi_fiil"
    if garble_mi(s):
        return "garble_desen"
    return None


# --------------------------------------------------------------------------- #
# okuma
# --------------------------------------------------------------------------- #
def oku(bant_yollari: list[Path], sor: Callable[[Path], str],
        kutu_say: Callable[[Path], int | None] | None = None) -> dict:
    """Bantları oku → {satirlar, elenen, bant_n, hata_n, kutu_durum}.

    `sor`   : model geri-çağrısı (src/model.yukle üretir)
    `kutu_say`: bandın PİKSELİNDE yazı kutusu var mı (Paddle det). None dönerse
                HÜKÜM VERİLMEZ — motor yoksa kalkan sessizce açık kalmaz,
                `kutu_durum` alanında raporlanır.

    PİKSEL KANITI (HAKEM v1, Çağatay 2026-07-31): kutu sayısı 0 iken satır
    üretilmişse o satırlar UYDURMADIR — deepseek boş karede '- 1' listesi
    uyduruyor (ölçüldü). Model ne derse desin piksel son sözü söyler.

    Tek bandın hatası okumayı durdurmaz; hata SAYILIR ve künyeye yazılır.
    """
    satirlar: list[str] = []
    satir_kaynaklari: list[dict] = []
    elenen: list[dict] = []
    gorulen: set[str] = set()
    hata_n = 0
    kutu_bilinmeyen = 0
    ilk_hata = ""

    for bant_index, p in enumerate(bant_yollari):
        try:
            ham = satirlari_ayikla(sor(p))
        except (ModelYok, Bellek):
            raise
        except Exception as e:
            hata_n += 1
            if not ilk_hata:
                ilk_hata = f"{type(e).__name__}: {e}"[:200]
            continue
        if not ham:
            continue

        n_kutu = kutu_say(p) if kutu_say else None
        if n_kutu is None:
            kutu_bilinmeyen += 1
        elif n_kutu == 0:
            # Piksel kanıtı: ekranda yazı YOK, model uydurmuş.
            elenen.extend({"bant": p.name, "satir": s, "sebep": "piksel0"}
                          for s in ham)
            continue

        for s in ham:
            if gevezelik_mi(s):
                elenen.append({"bant": p.name, "satir": s, "sebep": "gevezelik"})
                continue
            sebep = yapisal_veto(s)
            if sebep:
                elenen.append({"bant": p.name, "satir": s, "sebep": sebep})
                continue
            # fold-dedup: bantlar 120 px örtüştüğü için sınırdaki satır iki
            # bantta da okunur. Aynı satır iki kez künyeye girmez.
            f = fold_tr(s)
            if f in gorulen:
                continue
            gorulen.add(f)
            satirlar.append(s)
            satir_kaynaklari.append({"text": s, "bant": p.name,
                                     "bant_index": bant_index})

    # HER BANT PATLADIYSA BU "YAZI YOK" DEĞİLDİR — okuyamadık.
    # Bu satır gerçek bir kazadan yazıldı (2026-08-15, ilk uçtan uca koşu):
    # CUDA kütüphane çarpışması yüzünden 3 bandın 3'ü de patladı, tek tek
    # sayılıp yutuldu ve kule "METIN_YOK" dedi — yani içerik gerçeği. Sözleşmenin
    # yasakladığı tam şey: ARIZA sessizce içerik gerçeğine dönüştü.
    if bant_yollari and hata_n == len(bant_yollari):
        raise OkumaCoktu(f"{hata_n}/{len(bant_yollari)} bandin hepsi okunamadi"
                         + (f" — ornek: {ilk_hata}" if ilk_hata else ""))

    return {"satirlar": satirlar, "satir_kaynaklari": satir_kaynaklari,
            "elenen": elenen,
            "bant_n": len(bant_yollari), "hata_n": hata_n,
            "kutu_durum": ("yok" if kutu_say is None else
                           ("kismi" if kutu_bilinmeyen else "tam")),
            "elenen_n": len(elenen)}
