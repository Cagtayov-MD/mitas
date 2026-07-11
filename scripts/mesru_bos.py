# -*- coding: utf-8 -*-
"""mesru_bos.py — MEŞRU-BOŞ 6-durum ALAN-DÜZEYİ sınıflandırıcı + mühür (İP-9, 2026-07-11).

NEDEN: KONTROL kuyruğunda "bilgisi gerçekten olmayan" filmler sonsuz yeniden-incelemeye giriyor.
Ama "meşru-boş" ile "teknik-arıza" AYNI kovada — ve OCR tek başına ayıramaz (çöp okumuş olabilir).
Şartname: alan-düzeyi (168 bulgu=105 film, 14 çift-sınıf; (trt,field) tekil — kanıtlı), VL çift-tanık
alan-bağlamlı ikinci-tanık, C_OKUNAMAZ otomatik TEKNIK_ARIZA SAYILMAZ.

6 DURUM (plan rev.4 + qwen/GLM):
  SOURCE_ABSENT             : jenerik fiziksel YOK (kredi hiç görünmüyor) → MEŞRU-BOŞ terminal
  ROLE_ABSENT               : jenerik VAR ama istenen ROL yok (ör. yönetmen kredisi hiç yok) → terminal
  SOURCE_UNREADABLE         : kaynak medya okunamaz (kalite/hasar) → MEŞRU-BOŞ terminal
  OCR_MISSED_VISIBLE_TEXT   : framede NET metin var ama OCR kaçırdı → TEKNIK_ARIZA (terminal DEĞİL, retry)
  EVIDENCE_INSUFFICIENT     : rol videoda olabilir ama örneklenen frame-penceresine girmemiş
                              (frame-coverage-gap) → daha geniş örnekleme gerek, terminal DEĞİL
  NOT_APPLICABLE            : politika-durumu (ör. dizi-bölüm yönetmeni beklenmez) → terminal

KARAR KAPISI (VL çift-tanık): OCR-boş TEK BAŞINA yetkisiz.
  legibility_pozitif (kredi-frame'i OKUNABİLİR-kanıtlı) + VL "rol yok" → SOURCE_ABSENT/ROLE_ABSENT
  legibility_pozitif + VL "metin var" → OCR_MISSED_VISIBLE_TEXT (TEKNIK_ARIZA)
  legibility DÜŞÜK/bilinmez → SOURCE_UNREADABLE (retry-uygun) — otomatik meşru-boş DEĞİL
Mühür (terminal işaret): field+source_hash+evidence_hash+gate_version+approved_by; yeni frame/kanıt
gelince (hash değişince) mühür GEÇERSİZ → yeniden-kapıdan geçer (grandfather YOK).

Saf modül: VL çağrısı ENJEKTE edilir (vl_probe callable) — VRAM-maliyeti önce ÖLÇÜLÜR, sonra bağlanır."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

GATE_VERSION = "2026-07-11.ip9.1"

# durumlar
SOURCE_ABSENT = "SOURCE_ABSENT"
ROLE_ABSENT = "ROLE_ABSENT"
SOURCE_UNREADABLE = "SOURCE_UNREADABLE"
OCR_MISSED_VISIBLE_TEXT = "OCR_MISSED_VISIBLE_TEXT"
EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
NOT_APPLICABLE = "NOT_APPLICABLE"

TERMINAL = {SOURCE_ABSENT, ROLE_ABSENT, NOT_APPLICABLE}          # meşru-boş: kuyruktan çıkar
RETRYABLE = {SOURCE_UNREADABLE, OCR_MISSED_VISIBLE_TEXT, EVIDENCE_INSUFFICIENT}  # iş var


def classify_field(*, ocr_empty: bool, legibility: str, vl_verdict: str | None,
                   coverage_ok: bool = True, policy_na: bool = False) -> dict:
    """Tek (trt,field) bulgusunu 6-duruma sınıfla.
      ocr_empty   : OCR bu rolü boş/garble döndürdü mü
      legibility  : 'high' | 'low' | 'unknown' — kredi-frame'i ne kadar okunabilir
      vl_verdict  : None (VL koşmadı) | 'no_text' (karede metin yok) | 'has_text' (var) |
                    'role_absent' (metin var ama bu rol yok)
      coverage_ok : örneklenen frame penceresi jeneriği kapsıyor mu (False → EVIDENCE_INSUFFICIENT)
      policy_na   : politika gereği bu rol beklenmez (dizi-bölüm vb.)
    Döner: {durum, terminal, needs_vl, gerekce}."""
    if policy_na:
        return _r(NOT_APPLICABLE, "politika: bu rol beklenmiyor")
    if not ocr_empty:
        # OCR bir şey okudu → meşru-boş DEĞİL; bu modülün konusu dışı (dolu-alan)
        return _r(OCR_MISSED_VISIBLE_TEXT if False else "NOT_EMPTY",
                  "OCR dolu — meşru-boş sınıflaması uygulanmaz", terminal=False)
    if not coverage_ok:
        return _r(EVIDENCE_INSUFFICIENT, "frame-coverage-gap: jenerik penceresi eksik örneklendi")
    # OCR boş → VL çift-tanık ŞART (OCR tek başına yetkisiz)
    if vl_verdict is None:
        # VL koşmadı: legibility'ye göre geçici, ama terminal-mühür VL'siz VERİLMEZ
        if legibility == "low":
            return _r(SOURCE_UNREADABLE, "OCR-boş + düşük-okunabilirlik (VL bekliyor)", needs_vl=True)
        return _r(SOURCE_UNREADABLE, "OCR-boş — VL çift-tanık gerekli (terminal değil)", needs_vl=True)
    if vl_verdict == "has_text":
        return _r(OCR_MISSED_VISIBLE_TEXT, "VL: karede metin VAR, OCR kaçırdı → TEKNIK_ARIZA")
    if vl_verdict == "role_absent":
        return _r(ROLE_ABSENT, "VL: jenerik var ama bu rol yok → meşru-boş")
    if vl_verdict == "no_text":
        if legibility == "high":
            return _r(SOURCE_ABSENT, "VL: kredi yok + frame okunabilir → jenerik fiziksel yok")
        return _r(SOURCE_UNREADABLE, "VL: metin yok ama okunabilirlik düşük → kaynak-okunamaz")
    return _r(SOURCE_UNREADABLE, f"VL belirsiz verdict={vl_verdict!r}", needs_vl=True)


def _r(durum, gerekce, *, terminal=None, needs_vl=False):
    return {"durum": durum, "terminal": (durum in TERMINAL) if terminal is None else terminal,
            "needs_vl": needs_vl, "gerekce": gerekce}


# ─────────────────────────── mühür ───────────────────────────
def _hash(*parts) -> str:
    return hashlib.sha256("::".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:16]


def make_seal(*, trt: str, field: str, durum: str, source_hash: str, evidence_hash: str,
              approved_by: str) -> dict:
    """MEŞRU-BOŞ terminal mühür. Yeni kanıt gelince (hash değişince) geçersizleşir → grandfather yok."""
    if durum not in TERMINAL:
        raise ValueError(f"yalnız terminal durum mühürlenebilir: {durum}")
    if not approved_by:
        raise ValueError("mühür insan-onaylı: approved_by zorunlu")
    return {"trt": trt, "field": field, "durum": durum,
            "source_hash": source_hash, "evidence_hash": evidence_hash,
            "gate_version": GATE_VERSION, "approved_by": approved_by,
            "sealed_at": datetime.now().isoformat(timespec="seconds"),
            "seal_id": _hash(trt, field, source_hash, evidence_hash, GATE_VERSION)}


def is_seal_valid(seal: dict, *, current_source_hash: str, current_evidence_hash: str) -> bool:
    """Mühür hâlâ geçerli mi? Kaynak/kanıt hash'i değiştiyse (yeni frame/OCR) GEÇERSİZ."""
    if not seal:
        return False
    return (seal.get("source_hash") == current_source_hash
            and seal.get("evidence_hash") == current_evidence_hash
            and seal.get("gate_version") == GATE_VERSION)


# ─────────────────────────── mevcut-verdict köprüsü (168 bulgu) ───────────────────────────
def from_kokneden_verdict(verdict: str, gorsel_gozlem: str, kanit_ocr: str) -> dict:
    """KOKNEDEN_MASTER.csv'deki mevcut verdict'i 6-duruma ön-eşle (VL-öncesi deterministik kısım).
    D_JENERIKTE_YOK / C_OKUNAMAZ grandfather'sız yeniden-kapılanır: çoğu VL çift-tanık ister."""
    g = (gorsel_gozlem or "").lower()
    if verdict == "D_JENERIKTE_YOK":
        # görsel gözlem "hiç mevcut değil" diyorsa güçlü SOURCE/ROLE_ABSENT adayı — ama VL teyidi şart
        if "hic mevcut degil" in g or "fiziksel olarak yok" in g or "hiç mevcut değil" in g:
            return {"on_durum": ROLE_ABSENT, "needs_vl": True,
                    "not": "görsel: rol fiziksel yok — VL çift-tanık teyidi gerek"}
        return {"on_durum": SOURCE_ABSENT, "needs_vl": True, "not": "jenerik-yok adayı, VL gerek"}
    if verdict == "C_OKUNAMAZ":
        # KRİTİK (şartname): C_OKUNAMAZ otomatik TEKNIK_ARIZA SAYILMAZ. legibility'ye göre ayrılır.
        return {"on_durum": SOURCE_UNREADABLE, "needs_vl": True,
                "not": "okunamaz — VL 'metin var mı' teyidi: var→TEKNIK_ARIZA, yok→kaynak-okunamaz"}
    return {"on_durum": "DIGER", "needs_vl": False, "not": f"kapsam-dışı verdict={verdict}"}
