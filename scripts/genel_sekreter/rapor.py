"""Rapor üretici — Markdown + XML dosya yazma ve GUNLUK.md güncelleme.

Salt-okur modüller dışarı yazmaz — sadece bu modül yazma yapar.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path
from xml.dom import minidom

from genel_sekreter.config import RAPORLAR_DIR, KONTROL_RAPORLAR_DIR, GUNLUK_PATH


def _rapor_dosya_adi(modul_adi: str, tarih: date) -> str:
    return f"GS_{modul_adi}_{tarih.isoformat()}.md"


def emit_rapor(modul_adi: str, icerik_md: str, tarih: date | None = None) -> Path:
    """Markdown raporu dosyaya yaz ve yolunu döndür."""
    if tarih is None:
        tarih = date.today()
    RAPORLAR_DIR.mkdir(parents=True, exist_ok=True)
    dosya_yolu = RAPORLAR_DIR / _rapor_dosya_adi(modul_adi, tarih)

    ust_bilgi = (
        f"---\n"
        f"modul: {modul_adi}\n"
        f"tarih: {tarih.isoformat()}\n"
        f"uretim: {datetime.now().isoformat(timespec='seconds')}\n"
        f"---\n\n"
    )
    dosya_yolu.write_text(ust_bilgi + icerik_md, encoding="utf-8")
    return dosya_yolu


def emit_kontrol_xml(film_bilgileri: list[dict], tarih: date | None = None) -> Path:
    """KONTROL filmler için XML rapor üret.

    Her film:
      <film_report>
        <title>...</title>
        <trt_id>...</trt_id>
        <problem>...</problem>
        <root_cause>...</root_cause>
        <evidence>...</evidence>
        <category>BUG|QUALITY|MISSING_DATA</category>
        <severity>HIGH|MEDIUM|LOW</severity>
      </film_report>
    """
    if tarih is None:
        tarih = date.today()
    KONTROL_RAPORLAR_DIR.mkdir(parents=True, exist_ok=True)

    root = ET.Element("kontrol_rapor")
    root.set("tarih", tarih.isoformat())
    root.set("toplam_film", str(len(film_bilgileri)))

    for fb in film_bilgileri:
        film = ET.SubElement(root, "film_report")
        ET.SubElement(film, "title").text = fb.get("title", "?")
        ET.SubElement(film, "trt_id").text = fb.get("trt_id", "?")
        ET.SubElement(film, "problem").text = fb.get("problem", "?")
        ET.SubElement(film, "root_cause").text = fb.get("root_cause", "?")
        ET.SubElement(film, "evidence").text = fb.get("evidence", "?")
        ET.SubElement(film, "category").text = fb.get("category", "UNKNOWN")
        ET.SubElement(film, "severity").text = fb.get("severity", "MEDIUM")

    rough = ET.tostring(root, encoding="unicode", xml_declaration=True)
    pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding=None)
    # minidom fazladan xml declaration ekler, temizle
    lines = pretty.split("\n")
    if lines and lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="utf-8"?>'

    dosya_yolu = KONTROL_RAPORLAR_DIR / f"kontrol_{tarih.isoformat()}.xml"
    dosya_yolu.write_text("\n".join(lines), encoding="utf-8")
    return dosya_yolu


def gunluk_append(baslik: str, icerik: str) -> None:
    """GUNLUK.md'ye yeni kayıt ekle (en yeni EN ÜSTTE, header'dan sonra)."""
    if not GUNLUK_PATH.is_file():
        return
    mevcut = GUNLUK_PATH.read_text(encoding="utf-8")
    match = re.search(r"^---\s*$", mevcut, re.MULTILINE)
    if not match:
        return
    yeni_kayit = f"\n## {baslik}\n\n{icerik}\n\n---\n"
    eklenme_noktasi = match.end()
    guncel = mevcut[:eklenme_noktasi] + yeni_kayit + mevcut[eklenme_noktasi:]
    GUNLUK_PATH.write_text(guncel, encoding="utf-8")
