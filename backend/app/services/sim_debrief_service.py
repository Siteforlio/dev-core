# backend/app/services/sim_debrief_service.py
"""Generates a PDF report from a SimulationDebrief.
Uses reportlab if available; falls back to plain-text bytes if not."""
import io

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    REPORTLAB = True
except ImportError:
    REPORTLAB = False


def generate_pdf(debrief: dict) -> bytes:
    """Return PDF bytes for a SimulationDebrief dict."""
    if not REPORTLAB:
        # Fallback: plain-text report as UTF-8 bytes
        lines = [
            f"Simulation Debrief Report",
            f"Session: {debrief.get('session_id', 'N/A')}",
            f"Scenario: {debrief.get('scenario_type', 'N/A')}",
            f"Overall Score: {debrief.get('overall_score', 'N/A')}/10",
            f"Hire Signal: {debrief.get('hire_signal', 'N/A')}",
            "",
            "Summary:",
            debrief.get("summary", ""),
            "",
            "Core Scores:",
        ]
        for k, v in (debrief.get("core_scores") or {}).items():
            lines.append(f"  {k}: {v}/10")
        lines.append("")
        lines.append("Scenario Scores:")
        for k, v in (debrief.get("scenario_scores") or {}).items():
            lines.append(f"  {k}: {v}/10")
        lines.append("")
        lines.append("Strengths:")
        for s in debrief.get("strengths", []):
            lines.append(f"  • {s}")
        lines.append("")
        lines.append("Areas to Improve:")
        for i in debrief.get("improvements", []):
            lines.append(f"  • {i}")
        lines.append("")
        lines.append("Focus Areas:")
        for f in debrief.get("focus_areas", []):
            lines.append(f"  → {f}")
        return "\n".join(lines).encode("utf-8")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Simulation Debrief Report", styles["Title"]))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"Scenario: {debrief.get('scenario_type', 'N/A')}", styles["Normal"]))
    story.append(Paragraph(
        f"Overall Score: {debrief.get('overall_score', 'N/A')}/10 — {debrief.get('hire_signal', '')}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.3*cm))

    if debrief.get("summary"):
        story.append(Paragraph("Summary", styles["Heading2"]))
        story.append(Paragraph(debrief["summary"], styles["Normal"]))
        story.append(Spacer(1, 0.3*cm))

    # Score table
    score_data = [["Dimension", "Score"]]
    for k, v in (debrief.get("core_scores") or {}).items():
        score_data.append([k.replace("_", " ").title(), f"{v}/10"])
    for k, v in (debrief.get("scenario_scores") or {}).items():
        score_data.append([k.replace("_", " ").title(), f"{v}/10"])

    if len(score_data) > 1:
        story.append(Paragraph("Scores", styles["Heading2"]))
        t = Table(score_data, colWidths=[10*cm, 4*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#050d18")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f4f8")]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*cm))

    for heading, key in [("Strengths", "strengths"), ("Areas to Improve", "improvements"), ("Focus Areas", "focus_areas")]:
        items = debrief.get(key, [])
        if items:
            story.append(Paragraph(heading, styles["Heading2"]))
            for item in items:
                story.append(Paragraph(f"• {item}", styles["Normal"]))
            story.append(Spacer(1, 0.2*cm))

    doc.build(story)
    return buf.getvalue()
