from __future__ import annotations

import json
import os
from pathlib import Path


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def build_public_changes(series_id: str, episode_id: str, title: str, decisions: list[dict]) -> dict:
    return {
        "schema_version": "kyle.delta/v1",
        "series_id": series_id,
        "episode_id": episode_id,
        "title": title,
        "change_count": len(decisions),
        "changes": decisions,
    }


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
    red_style = ParagraphStyle("KyleRed", parent=body_style, textColor=colors.HexColor("#B00020"), fontSize=13, leading=17)
    blue_style = ParagraphStyle("KyleBlue", parent=body_style, textColor=colors.HexColor("#0B57D0"), fontSize=13, leading=17)
    amber_style = ParagraphStyle("KyleAmber", parent=body_style, textColor=colors.HexColor("#9A6700"), fontSize=13, leading=17)

    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    story = [
        Paragraph("Bölüm Jenerik Değişiklik Raporu", title_style),
        Paragraph(f"{public['title']} - Bölüm {public['episode_id']}", body_style),
        Spacer(1, 16),
    ]
    changes = public.get("changes") or []
    if not changes:
        story.append(Paragraph("Yeni kayıt veya doğrulanmış kadro değişikliği bulunmadı.", body_style))
    for change in changes:
        sev = change.get("severity")
        style = red_style if sev == "KIRMIZI" else blue_style if sev == "MAVI" else amber_style
        story.append(Paragraph(f"{change.get('role_label', change['role'])} - {change['type']}", style))
        def cell(value):
            return Paragraph(str(value), body_style)
        rows = [
            [cell("YENİ"), cell(change["new_name"])],
            [cell("Kaynak desteği"), cell(f"{change['support_count']} ({', '.join(change['support_sources'])})")],
        ]
        if change.get("previous_names"):
            rows.append([cell("ÖNCEKİ"), cell(", ".join(change["previous_names"]))])
        if change.get("expected_count") is not None:
            rows.append([cell("Beklenen kişi"), cell(change["expected_count"])])
        if change.get("observed_count") is not None:
            rows.append([cell("Bu bölüm"), cell(change["observed_count"])])
        rows.append([cell("Neden"), cell(change.get("reason", ""))])
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
