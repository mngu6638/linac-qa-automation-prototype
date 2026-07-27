"""
Unified DOCX -> PDF conversion utilities.

This module centralizes PDF conversion so QA reports and service reports
follow exactly the same conversion behavior.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from docx2pdf import convert as docx2pdf_convert
from docx import Document
from docx.document import Document as _DocumentClass
from docx.table import Table as _DocxTable
from docx.text.paragraph import Paragraph as _DocxParagraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph as RLParagraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _candidate_soffice_paths() -> List[str]:
    try:
        app_dir = Path(getattr(settings, "APP_DIR", settings.BASE_DIR))
    except ImproperlyConfigured:
        app_dir = Path.cwd()
    candidates = [
        app_dir / "_internal" / "libreoffice" / "program" / "soffice.exe",
        app_dir / "libreoffice" / "program" / "soffice.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "LibreOffice" / "program" / "soffice.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "LibreOffice" / "program" / "soffice.exe",
    ]
    return [str(p) for p in candidates if p.exists()]


def _convert_with_soffice(input_docx: str, output_pdf: str, soffice_bin: str) -> Tuple[bool, str | None]:
    out_dir = os.path.dirname(output_pdf)
    basename = os.path.splitext(os.path.basename(input_docx))[0]
    expected_pdf = os.path.join(out_dir, f"{basename}.pdf")
    try:
        result = subprocess.run(
            [
                soffice_bin,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                out_dir,
                input_docx,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except Exception as exc:
        return False, f"LibreOffice conversion error: {exc}"

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        return False, f"LibreOffice conversion failed (code {result.returncode}): {stderr or stdout or 'unknown error'}"

    if not os.path.exists(expected_pdf) or os.path.getsize(expected_pdf) == 0:
        return False, "LibreOffice reported success but no PDF was generated."

    if os.path.normcase(expected_pdf) != os.path.normcase(output_pdf):
        try:
            shutil.move(expected_pdf, output_pdf)
        except Exception as exc:
            return False, f"Failed moving generated PDF: {exc}"
    return True, None


def _convert_with_word_com(input_docx: str, output_pdf: str) -> Tuple[bool, str | None]:
    try:
        import pythoncom
        import win32com.client
    except Exception as exc:
        return False, f"pywin32 COM modules not available: {exc}"

    progids = [
        "Word.Application",
        "Word.Application.16",
        "Word.Application.15",
        "Word.Application.14",
        "Word.Application.12",
    ]

    pythoncom.CoInitialize()
    word = None
    try:
        last_exc = None
        for progid in progids:
            try:
                word = win32com.client.DispatchEx(progid)
                break
            except Exception as exc:
                last_exc = exc
                continue

        if word is None:
            return False, f"Word COM unavailable: {last_exc}"

        word.Visible = False
        word.DisplayAlerts = 0
        doc = word.Documents.Open(os.path.abspath(input_docx), ReadOnly=1)
        try:
            # FileFormat 17 = wdFormatPDF
            doc.SaveAs(os.path.abspath(output_pdf), FileFormat=17)
        finally:
            doc.Close(False)

        if os.path.exists(output_pdf) and os.path.getsize(output_pdf) > 0:
            return True, None
        return False, "Word COM reported success but no PDF was generated."
    except Exception as exc:
        return False, f"Word COM conversion failed: {exc}"
    finally:
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _iter_block_items(doc: _DocumentClass):
    """Yield paragraph/table blocks in original document order."""
    parent_elm = doc.element.body
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield _DocxParagraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield _DocxTable(child, doc)


def _detect_first_column_spans(table_data):
    """
    Detect first-column row spans for repeated equipment names.
    Returns list of (start_row, end_row) using ReportLab row coordinates.
    """
    spans = []
    if len(table_data) <= 2:
        return spans

    start = None
    current = None
    for row_idx in range(1, len(table_data)):
        cell = (table_data[row_idx][0] or "").strip()
        if not cell:
            if current is not None:
                continue
            continue

        if current is None:
            current = cell
            start = row_idx
            continue

        if cell == current:
            continue

        if start is not None and row_idx - 1 > start:
            spans.append((start, row_idx - 1))
        current = cell
        start = row_idx

    if current is not None and start is not None and len(table_data) - 1 > start:
        spans.append((start, len(table_data) - 1))

    return spans


def _convert_with_reportlab(input_docx: str, output_pdf: str) -> Tuple[bool, str | None]:
    """
    Native fallback renderer:
    populated DOCX (template already applied) -> basic PDF.
    """
    try:
        doc = Document(input_docx)
        pdf = SimpleDocTemplate(
            output_pdf,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
        )
        styles = getSampleStyleSheet()
        body_style = ParagraphStyle(
            "DocxBody",
            parent=styles["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            leading=14,
            spaceAfter=2,
        )
        story = []

        for block in _iter_block_items(doc):
            if isinstance(block, _DocxParagraph):
                text = (block.text or "").strip()
                if text:
                    escaped = (
                        text.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )
                    story.append(RLParagraph(escaped, body_style))
                else:
                    story.append(Spacer(1, 4))
                continue

            if isinstance(block, _DocxTable):
                data = []
                max_cols = 0
                for row in block.rows:
                    vals = [(" ".join(p.text.strip() for p in c.paragraphs) or "").strip() for c in row.cells]
                    max_cols = max(max_cols, len(vals))
                    data.append(vals)

                if not data or max_cols == 0:
                    continue

                # Normalize row lengths for ReportLab table.
                normalized = [r + [""] * (max_cols - len(r)) for r in data]
                available_width = A4[0] - (30 * mm)
                col_width = available_width / max_cols

                # Preserve merged-equipment visual layout for service report table.
                span_rules = []
                for start_row, end_row in _detect_first_column_spans(normalized):
                    for row_idx in range(start_row + 1, end_row + 1):
                        normalized[row_idx][0] = ""
                    span_rules.append(("SPAN", (0, start_row), (0, end_row)))

                table = Table(normalized, colWidths=[col_width] * max_cols, repeatRows=1)
                table.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                            ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
                            ("FONTSIZE", (0, 0), (-1, -1), 10),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                            *span_rules,
                        ]
                    )
                )
                story.append(table)
                story.append(Spacer(1, 8))

        if not story:
            story.append(RLParagraph("Report generated.", body_style))

        pdf.build(story)
        if os.path.exists(output_pdf) and os.path.getsize(output_pdf) > 0:
            return True, None
        return False, "Native PDF renderer produced no output file."
    except Exception as exc:
        return False, f"Native PDF renderer failed: {exc}"


def convert_docx_to_pdf(input_docx: str, output_pdf: str, allow_native_fallback: bool = True) -> Tuple[bool, List[str]]:
    """
    Convert DOCX to PDF with a unified strategy.

    Strategy order:
    1) Bundled/known LibreOffice path
    2) docx2pdf (Word automation helper)
    3) Direct Word COM automation
    4) PATH-discovered LibreOffice
    """
    errors: List[str] = []

    # 1) Prefer explicit bundled/known soffice locations.
    for soffice_path in _candidate_soffice_paths():
        ok, err = _convert_with_soffice(input_docx, output_pdf, soffice_path)
        if ok:
            return True, []
        if err:
            errors.append(err)

    # 2) docx2pdf
    try:
        docx2pdf_convert(input_docx, output_pdf)
        if os.path.exists(output_pdf) and os.path.getsize(output_pdf) > 0:
            return True, []
        errors.append("docx2pdf produced no output file.")
    except Exception as exc:
        errors.append(f"docx2pdf failed: {exc}")

    # 3) Direct Word COM fallback.
    ok, err = _convert_with_word_com(input_docx, output_pdf)
    if ok:
        return True, []
    if err:
        errors.append(err)

    # 4) PATH-based LibreOffice.
    soffice = (
        shutil.which("soffice")
        or shutil.which("soffice.exe")
        or shutil.which("libreoffice")
        or shutil.which("libreoffice.exe")
    )
    if soffice:
        ok, err = _convert_with_soffice(input_docx, output_pdf, soffice)
        if ok:
            return True, []
        if err:
            errors.append(err)
    else:
        errors.append("LibreOffice/soffice not found.")

    if allow_native_fallback:
        # 5) Native fallback renderer (does not require external Office software).
        ok, err = _convert_with_reportlab(input_docx, output_pdf)
        if ok:
            return True, []
        if err:
            errors.append(err)

    return False, errors
