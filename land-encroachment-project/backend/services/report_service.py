from __future__ import annotations

import os
from datetime import datetime


def generate_report(settings, plot_id: str, analysis_result: dict) -> str:
    try:
        return _generate_reportlab_report(settings, plot_id, analysis_result)
    except ModuleNotFoundError:
        return _generate_basic_pdf_report(settings, plot_id, analysis_result)


def generate_registration_report(
    settings,
    *,
    request_reference: str,
    payload: dict,
    extracted: dict,
    official_parcel: dict,
    validation: dict,
    outcome,
) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    os.makedirs(settings.reports_folder, exist_ok=True)
    file_name = f"registration_{request_reference}.pdf"
    report_path = os.path.join(settings.reports_folder, file_name)
    pdf = canvas.Canvas(report_path, pagesize=A4)
    width, height = A4

    y = height - 50

    def draw_line(label: str, value: object, *, bold: bool = False, gap: int = 20) -> None:
        nonlocal y
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", 11)
        pdf.drawString(50, y, f"{label}: {value}")
        y -= gap

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, "Land Registration Verification Record")
    y -= 32

    draw_line("Request reference", request_reference)
    draw_line("Generated at", f"{datetime.utcnow().isoformat()}Z")
    draw_line("Source mode", "Officer structured entry")
    y -= 6

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, y, "Applicant Details")
    y -= 22
    draw_line("Seller name", payload.get("seller_name") or "--")
    draw_line("Buyer name", payload.get("buyer_name") or "--")
    draw_line("Village", payload.get("village") or "--")
    draw_line("District", payload.get("district") or "--")
    draw_line("Officer notes", payload.get("officer_notes") or "--")
    y -= 6

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, y, "Registered Parcel Input")
    y -= 22
    draw_line("Survey number", extracted.get("survey_number") or "--")
    draw_line("Area", extracted.get("area") or "--")
    draw_line("Coordinate pairs", len(extracted.get("coordinates") or []))
    y -= 6

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, y, "Matched Official Record")
    y -= 22
    draw_line("Parcel ID", official_parcel.get("parcel_id") or "--")
    draw_line("Survey number", official_parcel.get("survey_number") or "--")
    draw_line("Owner name", official_parcel.get("owner_name") or "--")
    draw_line("Official area", official_parcel.get("area") or "--")
    y -= 6

    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, y, "Verification Decision")
    y -= 22
    draw_line("Risk score", outcome.risk_score, bold=True)
    draw_line("Risk level", outcome.risk_level, bold=True)
    draw_line("Verification status", outcome.verification_status, bold=True)
    draw_line("Recommendation", outcome.recommendation)
    draw_line("Area mismatch", "Yes" if validation.get("area_mismatch") else "No")
    draw_line("Boundary expansion", "Yes" if validation.get("boundary_expansion") else "No")
    draw_line(
        "Government overlap",
        "Yes" if validation.get("government_land_overlap") else "No",
    )
    draw_line("Encroachment area", validation.get("encroachment_area") or 0)

    pdf.save()
    return report_path


def _generate_reportlab_report(settings, plot_id: str, analysis_result: dict) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    os.makedirs(settings.reports_folder, exist_ok=True)
    report_path = os.path.join(settings.reports_folder, f"{plot_id}_report.pdf")
    pdf = canvas.Canvas(report_path, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, height - 50, f"Encroachment Report: {plot_id}")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, height - 85, f"Risk level: {analysis_result['risk']}")
    pdf.drawString(50, height - 105, f"Change: {analysis_result['change']:.2f}%")
    pdf.drawString(50, height - 125, f"Confidence: {analysis_result['confidence']:.2f}%")
    pdf.drawString(
        50,
        height - 145,
        f"Boundary violation: {analysis_result.get('boundary_violation', False)}",
    )
    pdf.drawString(
        50,
        height - 165,
        f"Generated at: {datetime.utcnow().isoformat()}Z",
    )

    image_specs = [
        ("Before", analysis_result.get("before_image")),
        ("After", analysis_result.get("after_image")),
        ("Output", analysis_result.get("output_image")),
    ]

    y = height - 225
    for label, filename in image_specs:
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y, label)
        if filename:
            image_path = os.path.join(settings.data_folder, filename)
            if os.path.exists(image_path):
                pdf.drawImage(
                    ImageReader(image_path),
                    50,
                    y - 140,
                    width=160,
                    height=120,
                    preserveAspectRatio=True,
                )
        y -= 170

    pdf.save()
    return report_path


def _generate_basic_pdf_report(settings, plot_id: str, analysis_result: dict) -> str:
    os.makedirs(settings.reports_folder, exist_ok=True)
    report_path = os.path.join(settings.reports_folder, f"{plot_id}_report.pdf")

    lines = [
        f"Encroachment Report: {plot_id}",
        "",
        f"Location: {analysis_result.get('location_name', 'N/A')}",
        f"Area: {analysis_result.get('area', 'N/A')}",
        f"Risk level: {analysis_result.get('risk', 'N/A')}",
        f"Change: {float(analysis_result.get('change', 0)):.2f}%",
        f"Confidence: {float(analysis_result.get('confidence', 0)):.2f}%",
        f"Boundary violation: {analysis_result.get('boundary_violation', False)}",
        f"Survey no: {analysis_result.get('survey_no', 'N/A')}",
        f"Owner: {analysis_result.get('owner_name', 'N/A')}",
        f"Village: {analysis_result.get('village', 'N/A')}",
        f"District: {analysis_result.get('district', 'N/A')}",
        "",
        f"Generated at: {datetime.utcnow().isoformat()}Z",
        "",
        "Note: This report was generated using the built-in PDF fallback.",
        "Install reportlab for image-rich PDF output.",
    ]

    _write_minimal_pdf(report_path, lines)
    return report_path


def _write_minimal_pdf(report_path: str, lines: list[str]) -> None:
    safe_lines = [_pdf_escape(line) for line in lines]

    content = ["BT", "/F1 12 Tf", "50 780 Td", "14 TL"]
    first = True
    for line in safe_lines:
        if first:
            content.append(f"({line}) Tj")
            first = False
        else:
            content.append("T*")
            content.append(f"({line}) Tj")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", errors="replace")

    objects = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objects.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
    )
    objects.append(
        f"4 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1")
        + stream
        + b"\nendstream endobj\n"
    )
    objects.append(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
      offsets.append(len(pdf))
      pdf.extend(obj)

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF".encode(
            "latin-1"
        )
    )

    with open(report_path, "wb") as handle:
        handle.write(pdf)


def _pdf_escape(value: str) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .encode("latin-1", errors="replace")
        .decode("latin-1")
    )
