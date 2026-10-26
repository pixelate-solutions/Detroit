"""Generate and ingest the fictional Rivergate demo corpus through the public upload API."""
from __future__ import annotations

import argparse
import io
import os
import sys
import textwrap
from pathlib import Path

import httpx
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


DOCUMENTS = [
    (
        "01_ordinance_2023_17.pdf",
        """RIVERGATE ORDINANCE 2023-17 — HARBOR MIXED-USE DISTRICT
Adopted October 16, 2023 | Effective November 1, 2023

The Rivergate City Council establishes the Harbor Mixed-Use District (HMU) for parcels along Harbor Avenue between First Street and Ninth Street.

Section 4. Building standards. A principal building must maintain a front setback of at least 25 feet from the Harbor Avenue right-of-way. Maximum building height is three stories or 42 feet, whichever is less.

Section 5. Ground-floor use. New buildings fronting Harbor Avenue must devote at least 60 percent of the ground-floor frontage to retail, restaurant, or public-serving uses. Retail and restaurant operations must close by 10:00 p.m.

Section 6. Parking. One off-street parking space is required for each residential unit. The Planning Commission may approve shared parking by special land-use review.

Approved by Mayor Elena Marquez. Filed as Case ZO-23-017 by the Rivergate Planning Department.""",
    ),
    (
        "02_zoning_amendment_2024_08.pdf",
        """RIVERGATE ORDINANCE 2024-08 — FIRST AMENDMENT TO ORDINANCE 2023-17
Adopted June 3, 2024 | Effective June 20, 2024

Section 4 of Ordinance 2023-17 is amended. The minimum front setback in the Harbor Mixed-Use District is reduced from 25 feet to 15 feet when the applicant installs the city-approved streetscape package, including street trees, pedestrian lighting, and an eight-foot sidewalk.

Maximum height may be increased from three stories to four stories only after conditional-use approval by the Rivergate Planning Commission. The 42-foot numeric limit is replaced with a 56-foot limit for an approved four-story building.

All provisions of Ordinance 2023-17 not expressly changed by this amendment remain in effect. Filed as Case ZO-24-008. Sponsored by Council Member Diane Brooks.""",
    ),
    (
        "03_zoning_amendment_2025_03.pdf",
        """RIVERGATE ORDINANCE 2025-03 — SECOND AMENDMENT TO ORDINANCE 2023-17
Adopted February 10, 2025 | Effective March 1, 2025

This ordinance further amends the Harbor Mixed-Use District created by Ordinance 2023-17 and previously amended by Ordinance 2024-08.

Section 4. Maximum height is now five stories or 68 feet by right. Planning Commission conditional-use approval for a fourth story is no longer required. The 15-foot setback option and its required city streetscape package established by Ordinance 2024-08 remain in force; otherwise the original 25-foot setback applies.

Section 5. The closing time for retail and restaurant operations is extended from 10:00 p.m. to 11:00 p.m. The 60 percent public-serving ground-floor frontage requirement remains unchanged.

All other provisions remain in effect. Filed as Case ZO-25-003.""",
    ),
    (
        "04_inspection_ce_25_104_resolved.pdf",
        """RIVERGATE CODE ENFORCEMENT — FINAL INSPECTION REPORT
Property: 714 Marquette Street, Rivergate
Parcel: 18-447-009
Case: CE-25-104
Inspection date: May 14, 2025
Inspector: Jordan Patel

The rear exterior stair previously cited for missing treads and an unstable landing was inspected. A wooden enclosure prevented a full view of the lower stringer. The property manager stated repairs were completed on May 12.

Disposition: VIOLATION RESOLVED. Case CE-25-104 is closed. No further inspection is scheduled. Owner of record: Marquette Row Holdings LLC, 88 Riverview Plaza, Rivergate.""",
    ),
    (
        "05_citizen_complaint_714_marquette.pdf",
        """RIVERGATE 311 CITIZEN COMPLAINT
Property: 714 Marquette Street, Rivergate
Complaint ID: CR-25-882
Received: June 2, 2025

Resident Tasha Green reports that the rear stair at 714 Marquette Street remains unsafe. Two treads are still missing, the lower landing shifts under weight, and tenants are using stacked milk crates to reach the yard. The resident states that no repair crew has visited since April.

The complaint includes photographs dated May 31, 2025. Referred to Code Enforcement for follow-up under prior Case CE-25-104.""",
    ),
    (
        "06_followup_ce_25_104.pdf",
        """RIVERGATE CODE ENFORCEMENT — SUPERVISOR FOLLOW-UP
Property: 714 Marquette Street, Rivergate
Parcel: 18-447-009
Case: CE-25-104
Visit date: June 5, 2025
Supervisor: Amina Cole

An unannounced visit confirmed that two rear stair treads are absent and the lower landing is not secured to its footing. Conditions shown in Complaint CR-25-882 remain present.

The May 14 closure was based on an obstructed visual inspection and the property manager's statement. Disposition: CASE REOPENED. Marquette Row Holdings LLC must complete a permitted repair by June 20, 2025. Civil fine: $250.""",
    ),
    (
        "07_rivermark_building_permit.pdf",
        """RIVERGATE BUILDING PERMIT APPLICATION BP-25-441
Project: Harbor Lofts, 225 Harbor Avenue, Rivergate
Parcel: 18-201-114
Applicant: Rivermark Development LLC
Registered business address: 440 Lantern Avenue, Suite 600, Rivergate
Authorized agent: Marcus Vale

Scope: Construct a four-story mixed-use building with 38 apartments and 4,800 square feet of ground-floor retail. Applicant elects the streetscape package under Ordinance 2024-08 and proposes a 15-foot front setback.

Estimated construction value: $8,400,000. Application received January 8, 2025 by the Rivergate Building Department.""",
    ),
    (
        "08_northline_city_contract.pdf",
        """CITY OF RIVERGATE CONTRACT PW-2025-19
Vendor: Northline Civic Services Inc.
Vendor registered address: 440 Lantern Avenue, Suite 600, Rivergate
City department: Department of Public Works

Northline Civic Services Inc. will provide seasonal catch-basin cleaning in Wards 2 and 3 from April 1 through October 31, 2025. Contract ceiling: $286,000. Procurement method: competitive sealed bid RFP-24-77.

City signatory: Public Works Director Simone Hart. Vendor signatory: Evelyn Cross, President. Approved by Rivergate City Council on March 17, 2025.""",
    ),
    (
        "09_clearcurrent_contract_original.pdf",
        """CITY OF RIVERGATE PROFESSIONAL SERVICES AGREEMENT IT-2024-31 — ORIGINAL
Effective date: July 1, 2024
Vendor: ClearCurrent Systems LLC
Address: 92 Foundry Road, Rivergate

ClearCurrent Systems LLC will replace and monitor 320 municipal water-meter endpoints. The term ends June 30, 2025. Total not-to-exceed compensation is $418,000. The city will pay $1,200 per installed endpoint plus a $34,000 monitoring fee.

The vendor must respond to a critical outage within eight business hours. Either party may terminate on 30 days written notice. All field work must be complete by March 31, 2025.

Signed by Rivergate Chief Information Officer Lila Okafor and ClearCurrent manager Owen Price.""",
    ),
    (
        "10_clearcurrent_contract_amendment.pdf",
        """CITY OF RIVERGATE PROFESSIONAL SERVICES AGREEMENT IT-2024-31 — AMENDMENT 1
Effective date: May 12, 2025
Vendor: ClearCurrent Systems LLC
Address: 92 Foundry Road, Rivergate

The scope is expanded from 320 to 410 municipal water-meter endpoints. The term is extended through December 31, 2025. Total not-to-exceed compensation increases from $418,000 to $552,000. The per-endpoint rate remains $1,200; the monitoring fee increases to $60,000 for the extended term.

The vendor must now respond to a critical outage within four clock hours, including weekends and holidays. Either party may terminate on 15 days written notice. Remaining field work must be complete by September 30, 2025.

All unchanged terms of Agreement IT-2024-31 remain effective. Signed by Rivergate Chief Information Officer Lila Okafor and ClearCurrent manager Owen Price.""",
    ),
    (
        "11_council_minutes_march_17_2025.pdf",
        """RIVERGATE CITY COUNCIL REGULAR MEETING MINUTES
March 17, 2025 | Council Chamber, 6:00 p.m.

Present: Mayor Elena Marquez; Council Members Diane Brooks, Samuel Reed, Imani West, and Peter Lang.

Item 7B. Council approved Contract PW-2025-19 with Northline Civic Services Inc. for catch-basin cleaning, not to exceed $286,000. Vote: 4-1. Council Member West requested quarterly completion maps.

Item 8A. The Planning Department reported that Harbor Mixed-Use applications received after March 1 will be reviewed under Ordinances 2023-17, 2024-08, and 2025-03 together.

Public comment included a request for safer crossings at Ninth Street and Harbor Avenue. Meeting adjourned at 8:14 p.m.""",
    ),
    (
        "12_solar_permit_public_library.pdf",
        """RIVERGATE ELECTRICAL PERMIT EP-25-188
Site: East Branch Library, 1600 Maple Street, Rivergate
Parcel: 18-811-020
Applicant: Sunward Electric Cooperative

Install a 72-kilowatt rooftop photovoltaic array, two inverters, and a battery disconnect. Owner: City of Rivergate. Contractor: Sunward Electric Cooperative, license EC-44881.

Permit issued April 22, 2025. Final electrical inspection is required before interconnection. Project manager: Noah Kim.""",
    ),
    (
        "13_restaurant_inspection.pdf",
        """RIVERGATE PROPERTY MAINTENANCE INSPECTION CE-25-211
Property: 68 East Market Street, Rivergate
Parcel: 18-302-601
Occupant: Juniper Table Cooperative
Inspection date: April 29, 2025
Inspector: Jordan Patel

The rear exit was obstructed by delivery cartons and the illuminated exit sign was not operational. Corrective action is due May 6, 2025. A reinspection on May 7 confirmed the aisle was cleared and the exit sign replaced.

Disposition: VIOLATION RESOLVED. No fine assessed.""",
    ),
    (
        "14_procurement_memo_catch_basins.pdf",
        """RIVERGATE PROCUREMENT DIVISION MEMORANDUM
To: Department of Public Works
From: Priya Shah, Procurement Manager
Date: March 4, 2025
Subject: Bid evaluation for RFP-24-77 catch-basin cleaning

Five responses were received. Northline Civic Services Inc. submitted the lowest responsive bid at $286,000 and documented sufficient equipment capacity. The evaluation panel recommends award subject to council approval.

The vendor disclosure lists its registered office as 440 Lantern Avenue, Suite 600, Rivergate. Staff found no debarment record. Contract number PW-2025-19 has been reserved.""",
    ),
    (
        "15_harbor_lofts_planning_review.pdf",
        """RIVERGATE PLANNING DEPARTMENT STAFF REVIEW ZP-25-041
Project: Harbor Lofts, 225 Harbor Avenue, Rivergate
Applicant: Rivermark Development LLC
Parcel: 18-201-114

The January submission proposed four stories and a 15-foot setback with the required streetscape package. Ordinance 2025-03 became effective before final action and now allows up to five stories by right. The four-story proposal complies without conditional-use review.

Ground-floor plans reserve 64 percent of Harbor Avenue frontage for retail, exceeding the 60 percent requirement. The applicant acknowledges the 11:00 p.m. operating limit. Staff recommends approval.""",
    ),
    (
        "16_council_minutes_may_12_2025.pdf",
        """RIVERGATE CITY COUNCIL SPECIAL MEETING MINUTES
May 12, 2025 | Council Chamber, 5:30 p.m.

Present: Mayor Elena Marquez and all council members.

Council unanimously approved Amendment 1 to Agreement IT-2024-31 with ClearCurrent Systems LLC. Staff explained that the additional 90 water-meter endpoints and extended monitoring increase the ceiling to $552,000. Chief Information Officer Lila Okafor stated that the four-hour outage response commitment addresses winter reliability concerns.

Council also accepted a state grant for East Branch Library solar work under Permit EP-25-188.""",
    ),
    (
        "17_internal_email_marquette_case.pdf",
        """INTERNAL CORRESPONDENCE — RIVERGATE CODE ENFORCEMENT
From: Amina Cole, Code Enforcement Supervisor
To: Jordan Patel, Inspector
Date: June 6, 2025
Subject: CE-25-104 closure review

Jordan, please attach the June 5 photographs and Complaint CR-25-882 to Case CE-25-104. Because the enclosure blocked the lower stringer, the May 14 inspection should have been marked incomplete rather than resolved. We have reopened the case for 714 Marquette Street.

Please schedule a June 23 reinspection and do not close the matter without a clear view of the footing and every tread. I will notify Marquette Row Holdings LLC of the $250 civil fine.""",
    ),
    (
        "18_demolition_permit.pdf",
        """RIVERGATE DEMOLITION PERMIT DP-25-066
Site: 940 Furnace Avenue, Rivergate
Parcel: 18-990-031
Applicant: Great Lakes Deconstruction Cooperative
Owner: Rivergate Land Bank Authority

Scope: Demolish one fire-damaged residential structure, remove foundation walls, backfill with clean soil, and seed the lot. Asbestos survey AS-25-019 found no regulated material.

Permit issued June 9, 2025. Work must be complete by July 18, 2025. Dust suppression and sidewalk protection are required.""",
    ),
    (
        "19_parks_tree_contract.pdf",
        """CITY OF RIVERGATE CONTRACT PR-2025-07
Vendor: Canopy Works Cooperative
Address: 301 Orchard Lane, Rivergate
Department: Parks and Recreation

Canopy Works Cooperative will plant 180 street trees in Wards 1 and 4 and maintain them for two growing seasons. Contract value: $198,500. Species must follow the Rivergate Urban Forestry Manual.

Term: March 15, 2025 through November 30, 2027. City project manager: Celeste Ward. Vendor signatory: Robin Ellis.""",
    ),
]


def render_pdf(text: str) -> bytes:
    output = io.BytesIO()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=15, leading=19,
        alignment=TA_CENTER, spaceAfter=18,
    )
    body_style = ParagraphStyle(
        "DocBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=15,
        spaceAfter=10,
    )
    document = SimpleDocTemplate(
        output, pagesize=LETTER, leftMargin=0.82 * inch, rightMargin=0.82 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        title=text.splitlines()[0], author="Fictional City of Rivergate",
    )
    title, _, remainder = text.strip().partition("\n")
    paragraphs = [part.strip() for part in remainder.strip().split("\n\n") if part.strip()]
    story = [Paragraph(title, title_style), Spacer(1, 4)]
    for paragraph in paragraphs:
        story.append(Paragraph(paragraph.replace("\n", "<br/>"), body_style))
    document.build(story)
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--email",
        default=os.getenv("DETROIT_RECORDS_SEED_EMAIL") or os.getenv("CIVICLENS_SEED_EMAIL"),
        help="Email for an existing Detroit Records account",
    )
    parser.add_argument("--force", action="store_true", help="Upload even when documents already exist")
    args = parser.parse_args()
    base_url = args.api_url.rstrip("/")
    password = os.getenv("DETROIT_RECORDS_SEED_PASSWORD") or os.getenv("CIVICLENS_SEED_PASSWORD")
    if not args.email or not password:
        print(
            "Create a Detroit Records account, then set DETROIT_RECORDS_SEED_EMAIL and "
            "DETROIT_RECORDS_SEED_PASSWORD before seeding.",
            file=sys.stderr,
        )
        return 2
    try:
        with httpx.Client(base_url=base_url, timeout=300.0, trust_env=False) as client:
            login = client.post("/api/auth/login", json={"email": args.email, "password": password})
            if login.status_code >= 400:
                print(f"Seed sign-in failed: {login.status_code} {login.text}", file=sys.stderr)
                return 2
            existing = client.get("/api/documents")
            existing.raise_for_status()
            current_documents = existing.json().get("documents", [])
            existing_filenames = {item.get("filename") for item in current_documents}
            missing = DOCUMENTS if args.force else [item for item in DOCUMENTS if item[0] not in existing_filenames]
            if not missing:
                print(f"Seed skipped: all {len(DOCUMENTS)} Rivergate demo documents are already present.")
                return 0
            if existing_filenames and not args.force:
                print(f"Resuming seed: {len(existing_filenames)} files exist; {len(missing)} remain.")
            for index, (filename, text) in enumerate(missing, start=1):
                print(f"[{index:02d}/{len(missing)}] ingesting {filename}…", flush=True)
                response = client.post(
                    "/api/documents/upload",
                    files={"file": (filename, render_pdf(text), "application/pdf")},
                )
                if response.status_code >= 400:
                    print(f"Seed stopped: {response.status_code} {response.text}", file=sys.stderr)
                    return 1
                result = response.json()
                print(
                    f"     document {result['document_id']}: {result['chunk_count']} chunks, "
                    f"{result['entity_count']} entities, {result['relation_count']} relations"
                )
    except httpx.HTTPError as exc:
        print(f"Cannot reach the local Detroit Records API at {base_url}: {exc}", file=sys.stderr)
        print("Start the backend first with: uvicorn app.main:app --app-dir backend --port 8000", file=sys.stderr)
        return 1
    print("Rivergate demo corpus is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
