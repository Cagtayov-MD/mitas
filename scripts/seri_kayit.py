#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""seri_kayit.py — dizi-modu seri deposu IO katmanı (dizi_SISTEM.md sözleşmesi).

Depo düzeni:
    Database/_SERILER/<seri_anahtar>/
        seri_master.json      # kanonik durum (atomik: tmp + os.replace)
        gecmis.jsonl          # append-only olay günlüğü
        bolumler/bolum_0014.json

KISITLAR:
- SIFIR-DOKUNUŞ: mevcut MITAS modülleri değişmez; bu modül yalnız kendi deposuna yazar.
- Kök MODÜL-İÇİ çözülür (_root) — import-anında SABİTLENMEZ ki testler
  MITAS_SERILER_ROOT env ile tmp_path'e yönlendirebilsin.
- Yazımlar ATOMİK: aynı dizine .tmp yazılır, os.replace ile hedefe taşınır
  (yarım-yazılmış master ASLA görünmez).
- kilitle / versiyon_atla / tanik_ekle SAF: girdi mutasyona uğramaz, kopya döner.
"""
import copy
import hashlib
import json
import os
import re
from pathlib import Path

from credit_crosscheck import fold  # Türkçe-fold (İ/ı/Ş/Ğ/Ü/Ö/Ç → ascii küçük)

# TRT kimlik kalıbı — mitas_pipeline.py:84 TRT_RE ile AYNI regex.
# mitas_pipeline'dan import EDİLMEZ (SIFIR-DOKUNUŞ + ağır modül import zinciri yok).
TRT_RE = re.compile(r"(\d{4})-(\d{3,4})-(\d)-(\d{3,4})-(\d{2})-(\d)")

MASTER_DOSYA = "seri_master.json"
GECMIS_DOSYA = "gecmis.jsonl"
BOLUM_DIZIN = "bolumler"


def _root() -> Path:
    """Depo kökü — HER çağrıda env'den okunur (test tmp_path yönlendirmesi için)."""
    return Path(os.environ.get("MITAS_SERILER_ROOT", r"E:\MITAS\Database\_SERILER"))


# ------------------------------------------------------------------ anahtarlar

def seri_anahtar(klasor_adi: str) -> str:
    """Klasör adından deterministik seri anahtarı.

    Sıra sözleşmedeki gibi: TRT_RE eşleşmeleri silinir → Türkçe-fold + upper →
    alfasayısal-dışı "_" (çoklu "_" teklenir) → 80 karaktere kırp →
    "_" + sha1(ham_ad)[:8]. Sonek HAM addan (temizlik ÖNCESİ) hesaplanır ki
    yalnız TRT-id parseli farklı klasörler bile ayrı anahtar alsın.
    """
    ham_ad = klasor_adi or ""
    temiz = TRT_RE.sub("", ham_ad)
    govde = fold(temiz).upper()               # Türkçe-fold; upper çıktı sarmalayıcısı
    govde = re.sub(r"[^A-Z0-9]+", "_", govde).strip("_")  # yasak karakter + çoklu-"_" tek
    govde = govde[:80].rstrip("_")            # 80 karaktere kırp (kırpma "_" ile bitmesin)
    sonek = hashlib.sha1(ham_ad.encode("utf-8")).hexdigest()[:8]
    return f"{govde}_{sonek}"


def trt_seri_on_ek(trt_id: str):
    """TRT kimliğinden seri ön-eki: ilk 3 parsel (bölüm parseli maskelenir).

    "1900-0138-0-0009-00-1" → "1900-0138-0"; kalıba uymayan girdi → None.
    """
    m = TRT_RE.search(trt_id or "")
    if not m:
        return None
    return "-".join(m.group(1, 2, 3))


# ------------------------------------------------------------------- depo IO

def yol(anahtar: str) -> Path:
    """Serinin depo dizini (var olması garanti edilmez — yazan fonksiyonlar kurar)."""
    return _root() / anahtar


def _atomik_yaz(hedef: Path, veri) -> None:
    """JSON'u AYNI dizine .tmp yazıp os.replace ile hedefe taşır.

    Aynı dizin şart: os.replace ancak aynı dosya sisteminde atomiktir.
    ensure_ascii=False: Türkçe karakterler dosyada kaçışsız kalır.
    """
    hedef.parent.mkdir(parents=True, exist_ok=True)
    tmp = hedef.with_suffix(hedef.suffix + ".tmp")
    tmp.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, hedef)


def yukle(anahtar: str):
    """seri_master.json → dict; depo/dosya yoksa None (hata fırlatmaz)."""
    p = yol(anahtar) / MASTER_DOSYA
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def kaydet(anahtar: str, master: dict, olay: dict = None) -> None:
    """Master'ı atomik yazar; olay dict verilirse gecmis.jsonl'e append eder.

    Günlük append-only: olay verilmeyen kaydet günlüğe satır EKLEMEZ.
    Olay olduğu gibi yazılır (alan enjekte edilmez — ts'yi çağıran verir).
    """
    d = yol(anahtar)
    _atomik_yaz(d / MASTER_DOSYA, master)
    if olay is not None:
        with open(d / GECMIS_DOSYA, "a", encoding="utf-8") as f:
            f.write(json.dumps(olay, ensure_ascii=False) + "\n")


def bolum_kaydet(anahtar: str, bolum_no: int, okuma: dict) -> Path:
    """BolumOkuma anlık görüntüsü → bolumler/bolum_%04d.json (atomik, idempotent).

    Aynı bölüm ikinci kez yazılırsa üzerine-yazma — dosya adı deterministik.
    """
    p = yol(anahtar) / BOLUM_DIZIN / ("bolum_%04d.json" % bolum_no)
    _atomik_yaz(p, okuma)
    return p


def bolum_okumalari(anahtar: str) -> list:
    """Kayıtlı bölüm okumaları, bolum_no artan sıralı; depo yoksa boş liste.

    Sıralama dosya adına değil içerikteki bolum_no'ya dayanır — %04d dolgusu
    9999 üstünde bozulursa bile sıra doğru kalsın.
    """
    d = yol(anahtar) / BOLUM_DIZIN
    if not d.is_dir():
        return []
    okumalar = [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(d.glob("bolum_*.json"))]
    okumalar.sort(key=lambda o: o.get("bolum_no", 0))
    return okumalar


# ------------------------------------------------------------- master mantığı

def bos_master(seri_anahtar: str, seri_adi: str, kaynak_klasor: str, simdi: str) -> dict:
    """seri_master.json şemasına (surum_sema=1) uygun boş iskelet.

    durum=BUILDING, master_surum=0 (kilit sürüm 1'i basar), koleksiyonlar boş.
    """
    return {
        "surum_sema": 1,
        "seri_anahtar": seri_anahtar,
        "seri_adi": seri_adi,
        "kaynak_klasor": kaynak_klasor,
        "trt_on_ekler": [],
        "durum": "BUILDING",
        "master_surum": 0,
        "kilit_bolumler": [],
        "surum_gecmisi": [],
        "alanlar": {},
        "oyuncular": {},
        "teknik_ekip": {},
        "aday_havuzu": {},
        "konuk_gecmisi": {},
        "bekleyen_degisimler": [],
        "format_kopusu": {"ardisik": 0, "ilk_bolum": None},
        "tanik_kayitlari": {},
        "guncelleme": {"ts": simdi, "modul": "seri_kayit", "bolum": None},
    }


def kilitle(master: dict, bolumler, simdi: str) -> dict:
    """Tohum kilidi — SAF: kopya döner, girdi mutasyonsuz.

    durum=LOCKED, master_surum=1, kilit_bolumler=tohum, sürüm-günlüğüne "kilit" olayı.
    """
    m = copy.deepcopy(master)
    m["durum"] = "LOCKED"
    m["master_surum"] = 1
    m["kilit_bolumler"] = list(bolumler)
    m["surum_gecmisi"].append(
        {"surum": 1, "olay": "kilit", "bolumler": list(bolumler), "ts": simdi})
    return m


def versiyon_atla(master: dict, degisiklik: dict, gecerli_bolum: int, simdi: str) -> dict:
    """Kalıcı-değişim sürüm atlaması — SAF: kopya döner.

    master_surum+1; günlük kaydına degisiklik alanları AYNEN açılır (**degisiklik),
    "surum"/"olay"/"gecerli_bolumden"/"ts" çerçevesi modülce basılır.
    """
    m = copy.deepcopy(master)
    m["master_surum"] = m["master_surum"] + 1
    kayit = {"surum": m["master_surum"], "olay": "kalici_degisim",
             "gecerli_bolumden": gecerli_bolum}
    kayit.update(copy.deepcopy(degisiklik))   # çağıranın dict'i de mutasyonsuz kalsın
    kayit["ts"] = simdi
    m["surum_gecmisi"].append(kayit)
    return m


def tanik_ekle(master: dict, trt_id: str, bolum_no: int, content_hash: str, simdi: str):
    """İdempotency tanık kaydı — SAF: (yeni_master, durum) döner.

    durum: "YENI" (id ilk kez) | "AYNI" (aynı id + aynı hash: üzerine yaz,
    idempotent — ts tazelenir) | "DUPLICATE_CONFLICT" (aynı id FARKLI hash:
    mevcut kayıt EZİLMEZ — "okunamadı > yanlış oku", çelişkiyi çağıran çözer).
    """
    m = copy.deepcopy(master)
    kayitlar = m.setdefault("tanik_kayitlari", {})
    mevcut = kayitlar.get(trt_id)
    if mevcut is not None and mevcut.get("content_hash") != content_hash:
        return m, "DUPLICATE_CONFLICT"
    durum = "AYNI" if mevcut is not None else "YENI"
    kayitlar[trt_id] = {"bolum_no": bolum_no, "content_hash": content_hash, "ts": simdi}
    return m, durum
