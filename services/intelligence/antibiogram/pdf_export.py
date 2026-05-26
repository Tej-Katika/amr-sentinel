"""ReportLab antibiogram PDF.

Layout: organisms = rows, antibiotics = columns, %S = cell, color-coded:
    >= 80%   green
    60-79%   yellow
    <  60%   red
    n < 30   gray (insufficient data)
"""
from __future__ import annotations

from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .generator import Antibiogram


def render_pdf(antibiogram: Antibiogram, facility_name: str | None = None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(letter),
        leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    story: list = []

    title = f"Cumulative Antibiogram — {facility_name or antibiogram.facility_id}"
    story.append(Paragraph(title, styles["Title"]))
    subtitle = (
        f"Period: {antibiogram.period_start} to {antibiogram.period_end} "
        f"&nbsp;|&nbsp; Stratification: {antibiogram.stratification} "
        f"&nbsp;|&nbsp; Generated: {antibiogram.generated_at}"
    )
    story.append(Paragraph(subtitle, styles["Normal"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Cells show % susceptible. Counts <30 isolates are reported as 'n/a' per CLSI M39.",
        styles["Italic"],
    ))
    story.append(Spacer(1, 12))

    # Build the matrix
    organisms: dict[str, list] = {}
    antibiotics: list[tuple[str, str]] = []  # (atc, name)
    abx_seen: set[str] = set()

    for cell in antibiogram.cells:
        organisms.setdefault(cell.organism_name, [])
        if cell.antibiotic_atc not in abx_seen:
            antibiotics.append((cell.antibiotic_atc, cell.antibiotic_name))
            abx_seen.add(cell.antibiotic_atc)

    cell_lookup = {(c.organism_name, c.antibiotic_atc): c for c in antibiogram.cells}

    # Header row
    header = ["Organism (n)", *(name for _, name in antibiotics)]
    rows = [header]
    style_cmds: list = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",      (1, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.gray),
    ]

    for r, organism in enumerate(sorted(organisms.keys()), start=1):
        max_n = max(
            (cell_lookup[(organism, atc)].n_total for atc, _ in antibiotics if (organism, atc) in cell_lookup),
            default=0,
        )
        row = [f"{organism} ({max_n})"]
        for c, (atc, _) in enumerate(antibiotics, start=1):
            cell = cell_lookup.get((organism, atc))
            if cell is None or cell.percent_susceptible is None:
                row.append("n/a")
                style_cmds.append(("BACKGROUND", (c, r), (c, r), colors.lightgrey))
            else:
                pct = cell.percent_susceptible
                row.append(f"{pct}%\n(n={cell.n_total})")
                style_cmds.append(("BACKGROUND", (c, r), (c, r), _color_for(pct)))
        rows.append(row)

    table = Table(rows, repeatRows=1)
    table.setStyle(TableStyle(style_cmds))
    story.append(table)

    doc.build(story)
    return buf.getvalue()


def _color_for(pct: float) -> colors.Color:
    if pct >= 80:
        return colors.HexColor("#a8e6a3")
    if pct >= 60:
        return colors.HexColor("#fff2a8")
    return colors.HexColor("#f7b6b6")
