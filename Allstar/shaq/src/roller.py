"""Görsel rol ipuçları: muhafazakâr, kelime-sınırlı sınıflama."""
from __future__ import annotations

import re

from .normalizasyon import normalize

ROLES = ("YONETMEN_KESIN", "CAST_KESIN", "CAST_ADAY", "CREW_KESIN", "ROL_BELIRSIZ")
_AUX_DIRECTOR = (
    "ART DIRECTOR", "ASSISTANT DIRECTOR", "CASTING DIRECTOR", "SECOND UNIT DIRECTOR",
    "ASSOCIATE DIRECTOR", "DIRECTOR OF PHOTOGRAPHY", "ASSISTANT TO THE DIRECTOR",
    "MUSIC DIRECTOR", "CREATIVE DIRECTOR", "TECHNICAL DIRECTOR", "UNIT DIRECTOR",
    "ACTION DIRECTOR", "ANIMATION DIRECTOR", "VOICE DIRECTOR", "DUBBING DIRECTOR",
    "YARDIMCI YONETMEN", "YARDIMCI YÖNETMEN", "SANAT YONETMENI", "SANAT YÖNETMENİ",
    "GORUNTU YONETMENI", "GÖRÜNTÜ YÖNETMENİ",
)


def _words(line: dict) -> str:
    return f" {normalize(str(line.get('role_hint', '')))} {normalize(line.get('text', ''))} "


def _has(source: str, phrase: str) -> bool:
    return f" {phrase} " in source


def _one(line: dict) -> str:
    source = _words(line)
    if any(_has(source, phrase) for phrase in _AUX_DIRECTOR):
        return "CREW_KESIN"
    director = (_has(source, "DIRECTED BY") or _has(source, "YONETMEN") or
                _has(source, "YÖNETMEN") or _has(source, "DIRECTOR"))
    cast = any(_has(source, phrase) for phrase in ("CAST", "STARRING", "OYUNCULAR", "OYUNCU"))
    if director and cast:
        return "ROL_BELIRSIZ"
    if director:
        return "YONETMEN_KESIN"
    if cast:
        return "CAST_KESIN"
    raw = str(line.get("text", ""))
    if re.search(r"\s(?:AS|OLARAK)\s", normalize(raw)) or " - " in raw:
        return "CAST_ADAY"
    if line.get("role_hint") or any(_has(source, word) for word in
                                    ("ISIK", "IŞIK", "LIGHT", "MAKEUP", "SOUND", "SES", "KURGU", "CAMERA")):
        return "CREW_KESIN"
    return "ROL_BELIRSIZ"


def siniflandir(*lines: dict | None) -> str:
    """İki kanalın rol kanıtını birleştirir; çelişkiyi belirsiz bırakır."""
    findings = {_one(line) for line in lines if line}
    concrete = findings - {"ROL_BELIRSIZ"}
    return concrete.pop() if len(concrete) == 1 else "ROL_BELIRSIZ"


def person_name(line: dict | None, role: str) -> str | None:
    """Yalnız açık cast/yönetmen etiketi sonrası gelen adı çıkarır."""
    if not line or role not in ("CAST_KESIN", "YONETMEN_KESIN"):
        return None
    text = str(line.get("text", "")).strip()
    labels = ((r"(?:CAST|STARRING|OYUNCULAR|OYUNCU)",) if role == "CAST_KESIN"
              else (r"(?:DIRECTED\s+BY|DIRECTOR|YONETMEN|YÖNETMEN)",))
    match = re.match(r"^\s*(?:" + "|".join(labels) + r")\s*[:\-–]?\s*(.+?)\s*$", text, re.IGNORECASE)
    name = match.group(1).strip() if match else ""
    return name or None
