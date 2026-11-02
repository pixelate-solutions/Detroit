"""Seed the fictional Rivergate Fire Department demo: accounts, records, and a sample audit trail.

Usage (from the backend directory):
    python -m app.seed_demo            # idempotent; skips records that already exist
    python -m app.seed_demo --reset    # delete backend/data first
"""
from __future__ import annotations

import argparse
import io
import json
import secrets
import shutil
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

YEAR_OFFSET = 365


def render_pdf(text: str) -> bytes:
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=13.5, leading=18,
        alignment=TA_CENTER, spaceAfter=14,
    )
    body_style = ParagraphStyle(
        "DocBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=10,
    )
    lines = text.strip().split("\n")
    title_lines = []
    for line in lines[:2]:
        if line.strip() and line.upper() == line:
            title_lines.append(line)
        else:
            break
    title_lines = title_lines or lines[:1]
    remainder = "\n".join(lines[len(title_lines):])
    document = SimpleDocTemplate(
        output, pagesize=LETTER, leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        title=title_lines[0], author="Rivergate Fire Department (fictional)",
    )
    story = [Paragraph("<br/>".join(title_lines), title_style), Spacer(1, 4)]
    for page_index, page in enumerate(remainder.split("\f")):
        if page_index:
            story.append(PageBreak())
        for paragraph in [part.strip() for part in page.strip().split("\n\n") if part.strip()]:
            if paragraph.startswith("PAGE "):
                continue
            story.append(Paragraph(paragraph.replace("\n", "<br/>"), body_style))
    story.append(Spacer(1, 18))
    story.append(Paragraph("<font color='#888888' size='8'>FICTIONAL DEMONSTRATION RECORD. Not a real document.</font>", body_style))
    document.build(story)
    return output.getvalue()


def render_scanned_pdf(text: str) -> bytes:
    """Render text into an image-only PDF so ingestion has to OCR it."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    width, height = 1700, 2200
    image = Image.new("L", (width, height), 246)
    draw = ImageDraw.Draw(image)
    font = None
    for candidate in (
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ):
        if Path(candidate).is_file():
            font = ImageFont.truetype(candidate, 34)
            break
    font = font or ImageFont.load_default(size=34)
    y = 150
    import textwrap

    for paragraph in text.strip().split("\n"):
        for line in textwrap.wrap(paragraph, 70) or [""]:
            draw.text((140, y), line, fill=30, font=font)
            y += 50
        y += 14
    image = image.rotate(0.6, fillcolor=246).filter(ImageFilter.GaussianBlur(0.6))
    output = io.BytesIO()
    image.convert("RGB").save(output, format="PDF", resolution=200)
    return output.getvalue()


def ocr_available() -> bool:
    return bool(shutil.which("tesseract") and shutil.which("pdftoppm"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Delete the local data directory before seeding")
    args = parser.parse_args()

    from .config import settings

    if args.reset and settings.data_dir.exists():
        shutil.rmtree(settings.data_dir)
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        settings.upload_dir.mkdir(parents=True, exist_ok=True)

    from .ai import ai
    from .auth import create_user, user_by_email
    from .database import connect, initialize_database, transaction
    from .demo_corpus import DOCUMENTS, TITLES
    from .ingestion import ingest_path
    from .main import DEMO_ACCOUNTS

    initialize_database()
    print(f"AI provider: {ai.mode} ({ai.health().get('llm_model')})")

    users = {}
    for account in DEMO_ACCOUNTS:
        user = user_by_email(account["email"]) or create_user(
            account["email"], account["display_name"], secrets.token_urlsafe(18), account["role"]
        )
        users[account["role"]] = user
    print(f"Demo accounts ready: {', '.join(a['display_name'] for a in DEMO_ACCOUNTS)}")

    with connect() as connection:
        existing = {row["filename"] for row in connection.execute("SELECT filename FROM documents")}
    now = datetime.now(timezone.utc)
    added = 0
    for filename, classification, unit, days_ago, text, scanned in DOCUMENTS:
        if filename in existing:
            continue
        if scanned and not ocr_available():
            print(f"  skip {filename}: needs Tesseract + Poppler for OCR (brew install tesseract poppler)")
            continue
        path = settings.upload_dir / f"{uuid.uuid4().hex}.pdf"
        path.write_bytes(render_scanned_pdf(text) if scanned else render_pdf(text))
        # Record contents are dated 2025; file each one a few days after its own date.
        uploaded = (now - timedelta(days=days_ago + YEAR_OFFSET, hours=(days_ago * 7) % 9)).isoformat()
        title, doc_type = TITLES.get(filename, (None, None))
        result = ingest_path(path, filename, classification, unit, uploaded, title, doc_type)
        added += 1
        print(
            f"  [{classification:>12}] {result['title'][:64]:<64} "
            f"{result['chunk_count']} chunks, {result['entity_count']} entities{', OCR' if result['ocr_used'] else ''}"
        )
    print(f"Ingested {added} records.")

    with connect() as connection:
        audit_rows = connection.execute("SELECT count(*) FROM audit_log").fetchone()[0]
        docs = {row["filename"]: (row["id"], row["title"]) for row in connection.execute("SELECT id, filename, title FROM documents")}
    if audit_rows == 0 and docs:
        _backfill_audit(transaction, users, docs, now)
        print("Backfilled a sample audit trail.")
    print("Done. Start the server with CIVIC_RECORDS_DEMO=1 (see README).")
    return 0


def _backfill_audit(transaction, users: dict, docs: dict, now: datetime) -> None:
    def doc(name: str) -> tuple[int, str]:
        return docs.get(name, (None, name))

    officer, admin, ff, pio = users["fire_officer"], users["records_admin"], users["firefighter"], users["public_info"]
    events = [
        (YEAR_OFFSET + 190, admin, "document.ingest", "document", *doc("inspection_fi_25_0290_68_east_market.pdf"), "allowed", {"classification": "public"}),
        (YEAR_OFFSET + 147, admin, "document.ingest", "document", *doc("inspection_fi_25_0388_714_marquette_reinspection.pdf"), "allowed", {"classification": "public"}),
        (YEAR_OFFSET + 131, officer, "document.ingest", "document", *doc("incident_25_04417_structure_fire_714_marquette.pdf"), "allowed", {"classification": "internal"}),
        (YEAR_OFFSET + 118, admin, "document.ingest", "document", *doc("investigation_fir_25_019_714_marquette.pdf"), "allowed", {"classification": "restricted"}),
        (6, officer, "ask", "conversation", None, "Which hose size does SOP 204 require for standpipe operations?", "allowed", {"cited_documents": [doc("sop_204_high_rise_operations_rev2025.pdf")[0]]}),
        (5, officer, "document.view", "document", *doc("pre_incident_plan_pip_0142_harbor_lofts.pdf"), "allowed", {}),
        (4, ff, "document.view", "document", *doc("investigation_fir_25_019_714_marquette.pdf"), "denied", {}),
        (4, ff, "search", "", None, "e-bike battery fire Marquette", "allowed", {"results": 6}),
        (3, pio, "document.download", "document", *doc("incident_25_04417_structure_fire_714_marquette.pdf"), "denied", {}),
        (3, pio, "search", "", None, "714 Marquette inspection", "allowed", {"results": 3}),
        (2, admin, "document.view", "document", *doc("exposure_record_25_04417_chen.pdf"), "allowed", {}),
        (2, admin, "compare", "", None, "SOP 204 Revision 2023-1 vs Revision 2025-1", "allowed", {}),
        (1, officer, "ask", "conversation", None, "What did the Q2 high-rise drill recommend?", "allowed", {}),
        (1, ff, "document.view", "document", *doc("sop_117_lithium_ion_battery_fires.pdf"), "allowed", {}),
    ]
    with transaction() as connection:
        for days_ago, user, action, resource_type, resource_id, detail, outcome, metadata in events:
            if outcome == "denied" and action.startswith("document"):
                detail = f"Denied: {detail}"
            created = now - timedelta(days=days_ago, hours=(days_ago * 5) % 11, minutes=(days_ago * 17) % 60)
            connection.execute(
                """INSERT INTO audit_log(id, created_at, user_id, user_email, user_role, action, resource_type,
                                         resource_id, detail, outcome, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()), created.isoformat(), user["id"], user["email"], user["role"], action,
                    resource_type, None if resource_id is None else str(resource_id), detail, outcome,
                    json.dumps(metadata),
                ),
            )


if __name__ == "__main__":
    sys.exit(main())
