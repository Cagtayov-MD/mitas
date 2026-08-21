from __future__ import annotations

import json
import os
from collections import OrderedDict
from pathlib import Path


ACTOR_ROLES = ("OYUNCULAR", "KONUK OYUNCULAR", "BOLUM OYUNCULARI")
ACTOR_TYPE = {
    "OYUNCULAR": "ANA",
    "KONUK OYUNCULAR": "KONUK",
    "BOLUM OYUNCULARI": "BÖLÜM",
}


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def build_actor_roster(annotated: list, decisions: list[dict]) -> list[dict]:
    """Bu bölümde görülen oyuncuları tek listede MEVCUT/YENI olarak göster.

    Profile'da olup bu bölümde gözlenmeyen kişiyi listeye zorla eklemeyiz; OCR
    eksikliği "bu bölümde vardı" gerçeğine çevrilmez. Ham kanıt kanit.json'da
    ayrıca korunur.
    """
    rows: OrderedDict[tuple[str, str], dict] = OrderedDict()

    # Önce doğrulanmış profile eşleşmeleri: aynı kişi üç kulede görünse de tek satır.
    for item in annotated:
        role = item.known_role
        if item.is_metadata or role not in ACTOR_ROLES or not item.known_person_id:
            continue
        key = (role, item.known_person_id)
        row = rows.setdefault(key, {
            "name": item.known_name,
            "role": role,
            "type": ACTOR_TYPE[role],
            "status": "MEVCUT",
            "support_sources": [],
            "support_count": 0,
        })
        source = item.observation.source
        if source not in row["support_sources"]:
            row["support_sources"].append(source)
            row["support_count"] = len(row["support_sources"])

    # Sonra bu bölümde en az iki bağımsız kaynakla doğrulanan yeni oyuncular.
    for decision in decisions:
        role = decision.get("role")
        if role not in ACTOR_ROLES:
            continue
        key = (role, f"NEW:{decision['new_name']}")
        rows[key] = {
            "name": decision["new_name"],
            "role": role,
            "type": ACTOR_TYPE[role],
            "status": "YENİ",
            "support_sources": list(decision.get("support_sources") or []),
            "support_count": int(decision.get("support_count") or 0),
        }

    return list(rows.values())


def build_public_changes(series_id: str, episode_id: str, title: str,
                         decisions: list[dict], actors: list[dict] | None = None) -> dict:
    return {
        "schema_version": "kyle.delta/v1",
        "series_id": series_id,
        "episode_id": episode_id,
        "title": title,
        "change_count": len(decisions),
        "actors": actors or [],
        "changes": decisions,
    }


def _group_non_actor_changes(changes: list[dict]) -> list[tuple[str, list[dict]]]:
    grouped: OrderedDict[str, list[dict]] = OrderedDict()
    for change in changes:
        if change.get("role") in ACTOR_ROLES:
            continue
        grouped.setdefault(change.get("role") or "BELIRSIZ", []).append(change)
    return list(grouped.items())


def write_pdf(path: Path, public: dict) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    font_name = "Helvetica"
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).exists():
            pdfmetrics.registerFont(TTFont("KyleDejaVu", candidate))
            font_name = "KyleDejaVu"
            break

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("KyleTitle", parent=styles["Title"], fontName=font_name, fontSize=17, leading=21)
    body_style = ParagraphStyle("KyleBody", parent=styles["BodyText"], fontName=font_name, fontSize=10, leading=14)
    section_style = ParagraphStyle("KyleSection", parent=body_style, fontSize=13, leading=17, spaceAfter=6)
    red_style = ParagraphStyle("KyleRed", parent=section_style, textColor=colors.HexColor("#B00020"))
    blue_style = ParagraphStyle("KyleBlue", parent=section_style, textColor=colors.HexColor("#0B57D0"))
    amber_style = ParagraphStyle("KyleAmber", parent=section_style, textColor=colors.HexColor("#9A6700"))

    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    story = [
        Paragraph("Bölüm Jenerik Değişiklik Raporu", title_style),
        Paragraph(f"{public['title']} - Bölüm {public['episode_id']}", body_style),
        Spacer(1, 16),
    ]

    def cell(value):
        return Paragraph(str(value), body_style)

    actors = public.get("actors") or []
    if actors:
        story.append(Paragraph("OYUNCULAR", section_style))
        actor_rows = [[cell("İsim"), cell("Tür"), cell("Durum"), cell("Kaynak")]]
        for actor in actors:
            actor_rows.append([
                cell(actor["name"]),
                cell(actor["type"]),
                cell(actor["status"]),
                cell(f"{actor['support_count']} ({', '.join(actor['support_sources'])})"),
            ])
        table = Table(actor_rows, colWidths=[205, 65, 70, 140], repeatRows=1)
        style_cmds = [
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D0D0")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAEAEA")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]
        for row_idx, actor in enumerate(actors, start=1):
            if actor["status"] == "YENİ":
                style_cmds.append(("TEXTCOLOR", (2, row_idx), (2, row_idx), colors.HexColor("#B00020")))
        table.setStyle(TableStyle(style_cmds))
        story.extend([table, Spacer(1, 18)])

    changes = public.get("changes") or []
    non_actor_groups = _group_non_actor_changes(changes)
    if not changes:
        story.append(Paragraph("Yeni kayıt veya doğrulanmış kadro değişikliği bulunmadı.", body_style))

    # Bir rol için birden fazla yeni kişi varsa tek başlık/tek tablo. Aynı birim
    # için tekrar tekrar alarm bloğu basılmaz.
    for _, group in non_actor_groups:
        first = group[0]
        sev = first.get("severity")
        style = red_style if sev == "KIRMIZI" else blue_style if sev == "MAVI" else amber_style
        types = list(dict.fromkeys(x.get("type", "") for x in group))
        story.append(Paragraph(
            f"{first.get('role_label', first['role'])} - {' / '.join(types)}", style))

        new_lines = []
        for change in group:
            src = f"{change['support_count']} ({', '.join(change['support_sources'])})"
            new_lines.append(f"{change['new_name']} — {src}")
        rows = [[cell("YENİ"), cell("<br/>".join(new_lines))]]

        previous = []
        for change in group:
            for name in change.get("previous_names") or []:
                if name not in previous:
                    previous.append(name)
        if previous:
            rows.append([cell("ÖNCEKİ"), cell(", ".join(previous))])

        expected_values = [x.get("expected_count") for x in group if x.get("expected_count") is not None]
        observed_values = [x.get("observed_count") for x in group if x.get("observed_count") is not None]
        if expected_values:
            rows.append([cell("Beklenen kişi"), cell(expected_values[0])])
        if observed_values:
            rows.append([cell("Bu bölüm"), cell(max(observed_values))])

        reasons = list(dict.fromkeys(x.get("reason", "") for x in group if x.get("reason")))
        if reasons:
            rows.append([cell("Neden"), cell("<br/>".join(reasons))])

        table = Table(rows, colWidths=[110, 370])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D0D0")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F5F5")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([table, Spacer(1, 14)])

    doc.build(story)
