from __future__ import annotations

from collections import defaultdict
import re

from .eslesme import match_known
from .hafiza import SeriesMemory
from .modeller import AnnotatedObservation, Observation
from .normalizasyon import normal, similarity
from .roller import RoleSpec, detect_role


def _is_stop_metadata(text: str, cfg: dict) -> bool:
    n = normal(text)
    for phrase in (cfg.get("metadata") or {}).get("stop_phrases") or []:
        p = normal(str(phrase))
        if p and p in n:
            return True
    # "MART 1989" gibi tarih kartlari kredi sahibi degildir.
    if re.fullmatch(r"[A-ZÇĞİÖŞÜ]{3,12}\s+(?:19|20)\d{2}", n):
        return True
    return False


def annotate_sources(source_observations: dict[str, list[Observation]], memory: SeriesMemory,
                     roles: dict[str, RoleSpec], cfg: dict) -> list[AnnotatedObservation]:
    mcfg = cfg["matching"]
    role_threshold = float(mcfg["role_threshold"])
    known_threshold = float(mcfg["known_threshold"])
    known_margin = float(mcfg["known_margin"])
    title_threshold = float(mcfg.get("series_title_threshold", 0.78))
    title_max_sequence = int(mcfg.get("series_title_max_sequence", 6))
    result: list[AnnotatedObservation] = []

    # Birçok jenerikte oyuncu başlığı hiç yazılmaz; ilk açık rol başlığına kadar
    # isim bloğu OYUNCULAR kabul edilir. Bu yalnız bölüm-içi bağlamdır; ham metin
    # hiçbir zaman değiştirilmez.
    default_role = "OYUNCULAR" if "OYUNCULAR" in memory.roles else None

    for source, observations in source_observations.items():
        current_role = default_role
        local: list[AnnotatedObservation] = []
        for obs in observations:
            # Dizi adı jenerikte kredi satırı değildir. Özellikle OCR'ın
            # "IZ PESINDE" / "12 PEŞİNDE" gibi varyantlarını ilk birkaç satırda
            # kişi saymamak için profile başlığıyla karşılaştırılır.
            if (memory.title and obs.sequence <= title_max_sequence and
                    similarity(obs.raw_text, memory.title) >= title_threshold):
                local.append(AnnotatedObservation(
                    obs, role=None, is_metadata=True, review_reason="DIZI_BASLIGI"))
                continue

            # Açıklama/teşekkür/tarih gibi kredi dışı satırlar son görülen rolün
            # devamı değildir. Burada bağlamı kesmek kritik; aksi halde örn.
            # "İÇİŞLERİ BAKANLIĞI'na" son teknik birimin yeni üyesi sanılabilir.
            if _is_stop_metadata(obs.raw_text, cfg):
                current_role = None
                local.append(AnnotatedObservation(
                    obs, role=None, is_metadata=True, review_reason="KREDI_DISI_METIN"))
                continue

            role, _ = detect_role(obs.raw_text, roles, role_threshold)
            if role:
                current_role = role
                local.append(AnnotatedObservation(obs, role=role, is_role_heading=True))
                continue

            item = AnnotatedObservation(obs, role=current_role)
            km = match_known(obs.raw_text, memory, current_role, known_threshold, known_margin)
            if not km.person and current_role is not None:
                km = match_known(obs.raw_text, memory, None, known_threshold, known_margin)
            if km.person:
                item.known_person_id = km.person.person_id
                item.known_name = km.person.canonical_name
                item.known_role = km.person.role
                item.known_score = km.score
                # Global eşleşme başka bir doğrulanmış role gittiyse kişinin gerçek
                # profile rolü kazanır; OCR satır sırası tek başına role zorlamaz.
                item.role = km.person.role
            local.append(item)

        # Rolü gerçekten belirlenemeyen satırlar ancak iki tarafta aynı rol varsa
        # o role taşınır. Metadata ve başlıklar bu geçişe katılmaz.
        for i, item in enumerate(local):
            if item.is_metadata or item.is_role_heading or item.known_person_id or item.role in memory.roles:
                continue
            prev_role = next((local[j].known_role or local[j].role for j in range(i - 1, -1, -1)
                              if not local[j].is_metadata and
                              (local[j].known_role or local[j].role) in memory.roles), None)
            next_role = next((local[j].known_role or local[j].role for j in range(i + 1, len(local))
                              if not local[j].is_metadata and
                              (local[j].known_role or local[j].role) in memory.roles), None)
            if prev_role and prev_role == next_role:
                item.role = prev_role
            else:
                item.review_reason = "ROL_BELIRSIZ"
        result.extend(local)
    return result


def summarize_known(items: list[AnnotatedObservation]) -> dict[str, dict[str, list[AnnotatedObservation]]]:
    by_role: dict[str, dict[str, list[AnnotatedObservation]]] = defaultdict(lambda: defaultdict(list))
    for item in items:
        if item.known_person_id and item.known_role:
            by_role[item.known_role][item.known_person_id].append(item)
    return by_role
