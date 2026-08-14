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


def _kirp(ln: str) -> str:
    """Model çıktısındaki markdown süslerini soy (pilot_hat ile birebir)."""
    return ln.strip().strip("`").lstrip("#").strip().strip("*").strip()


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
    onceki: set[str] = set()
    sayfa_hata_n = 0
    gevezelik_elenen = 0

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
            if gevezelik_mi(ln):
                gevezelik_elenen += 1
                continue
            kayitlar.append({"kaynak": p.name, "sayfa_sira": sayfa_sira,
                             "satir_sira": satir_sira, "text": ln})
            satir_sira += 1
        onceki = yeni or onceki

    return kayitlar, {"sayfa_hata_n": sayfa_hata_n,
                      "gevezelik_elenen": gevezelik_elenen}


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
