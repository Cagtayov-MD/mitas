"""50-film manifest builder.

`E:/filmtest/aaaa` dizinini scan eder, mevcut 24-film manifest'inden
ID lookup yapar, yeni filmler için tutarlı slug üretir, JSON manifest
dump eder.

Kullanım:
    python -m scripts.build_50film_manifest

Çıktı: outputs/ocr_50films_aaaa_v21_paddle_20260525_manifest.json

§22.6 (mutfak/OCR-OPUS.md) protokolüne uyumlu.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

VIDEO_DIR = Path("E:/filmtest/aaaa")
OLD_MANIFEST = Path("outputs/ocr_24films_aaaa_film_credits_manifest_20260525.json")
NEW_MANIFEST = Path("outputs/ocr_50films_aaaa_v21_paddle_20260525_manifest.json")

VIDEO_EXTS = {".mp4", ".mxf"}

_TR_MAP = str.maketrans({
    "Ü": "u", "ü": "u",
    "Ö": "o", "ö": "o",
    "Ç": "c", "ç": "c",
    "Ğ": "g", "ğ": "g",
    "Ş": "s", "ş": "s",
    "İ": "i", "ı": "i",
    "'": "_",
    " ": "_",
    "~": "_",
    "-": "_",
})


def slugify_title(raw: str) -> str:
    """ELEŞTİREL_DÜŞÜNME → elestirel_dusunme"""
    s = raw.translate(_TR_MAP).lower()
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def extract_year(stem: str) -> str:
    # "_" word-char olduğu için \b çalışmaz; ayraçlı pattern.
    m = re.search(r"(?:^|[_ ])((?:19[5-9]\d)|(?:20[0-2]\d))(?:[-_])", stem)
    return m.group(1) if m else "unknown"


def extract_title(stem: str) -> str:
    """Dosya adının SON '-0-' veya '-1-' sonrasını film adı olarak al.

    Dosya formatı çoğunlukla: <...>-<num>-<num>-...-<0|1>-<FILM_ADI>
    Bazı dosyalarda son separator '-0-' (MARIE_CURRIE, ESKİ_ŞEHİR).
    Bazılarında '-1-'. En SAĞ matchı al.

    Fallback: tüm stem.
    """
    matches = list(re.finditer(r"-[01]-", stem))
    if matches:
        cand = stem[matches[-1].end():]
        # parantezli ek bilgiyi at: BEN_VE_BABAM_VATAN_(O_GECE_BERABER_BÜYÜDÜK)
        cand = re.sub(r"\(.+?\)", "", cand).strip().rstrip("_")
        if cand:
            return cand
    return stem


def derived_id(path: Path) -> str:
    stem = path.stem
    year = extract_year(stem)
    title = extract_title(stem)
    slug = slugify_title(title)
    if not slug:
        slug = "unknown"
    return f"{year}_{slug}_end_credits"


def load_old_lookup() -> dict[str, str]:
    """Eski 24-film manifest'inden {posix_path → id} lookup üret."""
    data = json.loads(OLD_MANIFEST.read_text(encoding="utf-8"))
    return {item["path"]: item["id"] for item in data["items"]}


def build_item(path: Path, old_lookup: dict[str, str]) -> dict:
    posix_path = path.as_posix()
    item_id = old_lookup.get(posix_path) or derived_id(path)
    return {
        "id": item_id,
        "path": posix_path,
        "kind": "film_credits",
        "opening_window_min": 3,
        "closing_window_min": 5,
        "max_opening_min": 8,
        "max_closing_min": 15,
        "dynamic_window": true_or_false(),
        "expected_language": "tr",
        "fps": 6,
        "notes": "50-film V2.1 regression pilot (24 eski + 26 yeni)",
    }


def true_or_false() -> bool:
    # JSON `true` için Python `True` kullan; ayrı fonksiyon sadece tutarlılık.
    return True


def main() -> None:
    if not VIDEO_DIR.is_dir():
        raise SystemExit(f"Video dir yok: {VIDEO_DIR}")
    if not OLD_MANIFEST.is_file():
        raise SystemExit(f"Eski manifest yok: {OLD_MANIFEST}")

    old_lookup = load_old_lookup()
    videos = sorted(
        p for p in VIDEO_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS
    )
    items = [build_item(p, old_lookup) for p in videos]

    # ID uniqueness check
    ids = [item["id"] for item in items]
    if len(set(ids)) != len(ids):
        dupes = {i for i in ids if ids.count(i) > 1}
        raise SystemExit(f"Duplicate IDs: {dupes}")

    NEW_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "_comment": (
            "50-film V2.1 regression pilot manifest. Eski 24 film için ID'ler "
            "outputs/ocr_24films_aaaa_film_credits_manifest_20260525.json'dan "
            "reuse edildi (delta karşılaştırma için aynı item_dir). "
            "Yeni 26 film için ID otomatik üretildi: <year>_<slug>_end_credits."
        ),
        "schema_version": "2.0.0",
        "items": items,
    }
    NEW_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Özet stdout
    reused = sum(1 for it in items if it["path"] in old_lookup)
    new_count = len(items) - reused
    print(f"Toplam: {len(items)} item")
    print(f"  Reused ID (eski 24): {reused}")
    print(f"  Yeni slug (yeni {new_count})")
    print(f"Manifest: {NEW_MANIFEST}")


if __name__ == "__main__":
    main()
