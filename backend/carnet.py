"""Carnet PDF des souvenirs d'un résident (fonction hors bêta, activable par
l'administrateur via l'interrupteur « carnet_pdf »)."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path


def _register_pdf_fonts():
    """Polices de la charte Racontelle Care, avec repli sur les polices intégrées."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    fonts_dir = Path(__file__).parent.parent / "frontend" / "assets" / "fonts"
    pairs = {
        "Allura": ("Allura-Regular.ttf", "Times-Italic"),
        "Cormorant": ("CormorantGaramond-Regular.ttf", "Times-Roman"),
        "Cormorant-SemiBold": ("CormorantGaramond-SemiBold.ttf", "Times-Bold"),
        "Montserrat": ("Montserrat-Bold.ttf", "Helvetica-Bold"),
    }
    resolved = {}
    for name, (file_name, fallback) in pairs.items():
        try:
            pdfmetrics.registerFont(TTFont(name, str(fonts_dir / file_name)))
            resolved[name] = name
        except Exception:
            resolved[name] = fallback
    return resolved


def build_carnet_pdf(resident: dict, capsules: list[dict]) -> bytes:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfgen import canvas

    fonts = _register_pdf_fonts()
    ink = HexColor("#2F3E52")  # bleu encre : couleur prioritaire Racontelle Care
    rose = HexColor("#E7A7A5")
    brown = HexColor("#A67C63")
    muted = HexColor("#7C8698")

    def wrap(text: str, font: str, size: float, max_width: float):
        lines, line = [], ""
        for word in text.split():
            trial = (line + " " + word).strip()
            if pdfmetrics.stringWidth(trial, font, size) <= max_width:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines or [""]

    buffer = io.BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 22 * mm
    max_w = width - 2 * margin

    def footer():
        page.setFont(fonts["Montserrat"], 8)
        page.setFillColor(muted)
        page.drawCentredString(width / 2, 12 * mm, "Écouter · Préserver · Transmettre — Racontelle Care")

    def new_page():
        footer()
        page.showPage()

    y = height - 30 * mm
    page.setFont(fonts["Allura"], 42)
    page.setFillColor(ink)
    page.drawString(margin, y, "Racontelle Care")
    y -= 9 * mm
    page.setFont(fonts["Montserrat"], 8)
    page.setFillColor(muted)
    page.drawString(margin, y, "ÉCOUTER · PRÉSERVER · TRANSMETTRE")
    y -= 4 * mm
    page.setStrokeColor(rose)
    page.setLineWidth(1.2)
    page.line(margin, y, width - margin, y)
    y -= 14 * mm
    page.setFont(fonts["Cormorant-SemiBold"], 26)
    page.setFillColor(ink)
    page.drawString(margin, y, f"Le carnet de {resident['display_name']}")
    y -= 8 * mm
    page.setFont(fonts["Cormorant"], 12)
    page.setFillColor(muted)
    page.drawString(margin, y, f"Souvenirs racontés à voix haute · édité le {datetime.now(timezone.utc).strftime('%d/%m/%Y')}")
    y -= 14 * mm

    if not capsules:
        page.setFont(fonts["Cormorant"], 13)
        page.setFillColor(ink)
        page.drawString(margin, y, "Aucun souvenir pour le moment.")

    for index, capsule in enumerate(capsules, start=1):
        transcription = (capsule.get("transcription") or "").strip()
        title = capsule.get("title") or "Souvenir vocal"
        date_label = str(capsule.get("recorded_at", ""))[:10]
        duration = int(capsule.get("duration_sec") or 0)
        lines = wrap(f"« {transcription} »" if transcription else "(enregistrement non transcrit)", fonts["Cormorant"], 12.5, max_w - 8 * mm)
        needed = 10 * mm + 8 * mm + len(wrap(title, fonts["Cormorant-SemiBold"], 14, max_w - 8 * mm)) * 6 * mm + len(lines) * 5.6 * mm + 10 * mm
        if y - needed < 20 * mm:
            new_page()
            y = height - 24 * mm
        page.setFont(fonts["Montserrat"], 8.5)
        page.setFillColor(brown)
        page.drawString(margin + 6 * mm, y - 7 * mm, f"{index}. {date_label} · {duration // 60:02d}:{duration % 60:02d}")
        y -= 14 * mm
        page.setFont(fonts["Cormorant-SemiBold"], 14)
        page.setFillColor(ink)
        for tline in wrap(title, fonts["Cormorant-SemiBold"], 14, max_w - 12 * mm):
            page.drawString(margin + 6 * mm, y, tline)
            y -= 6 * mm
        y -= 1.5 * mm
        page.setStrokeColor(rose)
        page.setLineWidth(2)
        page.line(margin + 6 * mm, y + 3 * mm, margin + 6 * mm, y - len(lines) * 5.6 * mm + 1.5 * mm)
        page.setFont(fonts["Cormorant"], 12.5)
        page.setFillColor(ink)
        for tline in lines:
            page.drawString(margin + 10 * mm, y, tline)
            y -= 5.6 * mm
        y -= 9 * mm

    footer()
    page.save()
    return buffer.getvalue()
