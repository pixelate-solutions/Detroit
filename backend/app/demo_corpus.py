"""Fictional demo corpus for the Rivergate Fire Department.

Rivergate is a fictional city. Every person, address, incident, case number, and
organisation below is invented for demonstration. Any resemblance to real people or
records is coincidental. A form feed ("\\f") starts a new PDF page.
"""
from __future__ import annotations

# (filename, classification, source_unit, days_ago, text, scanned)
DOCUMENTS: list[tuple[str, str, str, int, str, bool]] = [
    (
        "sop_204_high_rise_operations_rev2023.pdf",
        "internal",
        "Operations Division",
        410,
        """RIVERGATE FIRE DEPARTMENT STANDARD OPERATING PROCEDURE 204
HIGH-RISE AND STANDPIPE OPERATIONS (REVISION 2023-1)
Effective March 1, 2023 | Approved by Fire Chief Helen Brandt

204.1 Scope. This procedure applies to any building with a floor more than 75 feet above the lowest level of fire department vehicle access, and to any building equipped with a Class I standpipe system.

204.2 First-arriving engine. The first-arriving engine company shall connect to the fire department connection (FDC) and supply the standpipe at 150 psi. The engine officer shall confirm the FDC location against the pre-incident plan when one exists.

204.3 Attack line. The attack team shall connect a 1.75-inch hose line to the standpipe outlet one floor below the fire floor. A minimum crew of three is required to advance the attack line.

204.4 Staging. Lobby control shall establish a staging area one floor below the fire floor. Elevators may be used to reach staging only when they are under firefighter service control and stop at least two floors below the reported fire floor.
\fPAGE 2

204.5 Search. The second-arriving company shall search the fire floor and the floor above. The incident commander shall assign a rapid intervention crew before interior operations begin above the seventh floor.

204.6 Accountability. The lobby control officer shall maintain a written roster of every crew that passes the lobby and shall report personnel accountability every 20 minutes.

204.7 Review. The Operations Division shall review this procedure every two years or after any high-rise incident with a firefighter injury.""",
        False,
    ),
    (
        "sop_204_high_rise_operations_rev2025.pdf",
        "internal",
        "Operations Division",
        120,
        """RIVERGATE FIRE DEPARTMENT STANDARD OPERATING PROCEDURE 204
HIGH-RISE AND STANDPIPE OPERATIONS (REVISION 2025-1)
Effective July 1, 2025 | Approved by Fire Chief Helen Brandt

204.1 Scope. This procedure applies to any building with a floor more than 75 feet above the lowest level of fire department vehicle access, and to any building equipped with a Class I standpipe system.

204.2 First-arriving engine. The first-arriving engine company shall connect to the fire department connection (FDC) and supply the standpipe at 175 psi. The engine officer shall confirm the FDC location against the pre-incident plan when one exists.

204.3 Attack line. The attack team shall connect a 2.5-inch hose line with a smooth-bore nozzle to the standpipe outlet one floor below the fire floor. A minimum crew of four is required to advance the attack line.

204.4 Staging. Lobby control shall establish a staging area two floors below the fire floor. Elevators may be used to reach staging only when they are under firefighter service control and stop at least two floors below the reported fire floor.
\fPAGE 2

204.5 Search. The second-arriving company shall search the fire floor and the floor above. The incident commander shall assign a rapid intervention crew before interior operations begin above the fifth floor.

204.6 Accountability. The lobby control officer shall maintain a written roster of every crew that passes the lobby and shall report personnel accountability every 15 minutes.

204.7 Review. The Operations Division shall review this procedure every two years or after any high-rise incident with a firefighter injury. Revision 2025-1 follows the after-action review of Incident 25-04417 and the Q2 2025 high-rise drill.""",
        False,
    ),
    (
        "sop_117_lithium_ion_battery_fires.pdf",
        "internal",
        "Operations Division",
        200,
        """RIVERGATE FIRE DEPARTMENT STANDARD OPERATING PROCEDURE 117
LITHIUM-ION BATTERY AND MICROMOBILITY FIRES
Effective January 15, 2025 | Prepared by Battalion Chief Victor Osei

117.1 Hazard. Lithium-ion batteries in e-bikes, scooters, and power tools can enter thermal runaway, release flammable and toxic gases, and reignite hours after visible flames are knocked down.

117.2 Tactics. Crews shall apply large volumes of water to cool the battery pack and shall not attempt to remove a battery that is venting. Full self-contained breathing apparatus is required until air monitoring shows readings below action levels.

117.3 Overhaul. A battery involved in fire shall be submerged in a water-filled container for at least 24 hours or removed by a hazardous materials contractor. The company officer shall document the battery make, location, and charging condition in the incident report.

117.4 Reignition watch. A fire watch shall remain on scene for at least 60 minutes after the last visible venting, and the officer shall notify the occupant in writing of reignition risk.""",
        False,
    ),
    (
        "sop_310_records_release_and_redaction.pdf",
        "public",
        "Records Unit",
        300,
        """RIVERGATE FIRE DEPARTMENT STANDARD OPERATING PROCEDURE 310
PUBLIC RECORDS RELEASE AND REDACTION
Effective October 1, 2024 | Approved by Fire Chief Helen Brandt

310.1 Purpose. The department responds to public-records requests within five business days and releases records in full unless an exemption applies.

310.2 Classifications. Department records are classified as Public, Internal, Restricted, or Confidential. Fire inspection reports and adopted procedures are Public. Incident reports are Internal until reviewed for release. Open fire investigations and pre-incident plans that describe building security are Restricted. Personnel and medical exposure records are Confidential.

310.3 Redaction. Before release, the Records Unit shall redact patient information, home addresses of employees, security access details, and the names of juvenile subjects.

310.4 Audit. Every view, download, and release of a Restricted or Confidential record is logged with the user, time, and purpose. Logs are retained for seven years and reviewed quarterly by the Records Administrator.""",
        False,
    ),
    (
        "inspection_fi_25_0312_714_marquette.pdf",
        "public",
        "Fire Prevention Bureau",
        170,
        """RIVERGATE FIRE PREVENTION BUREAU FIRE INSPECTION REPORT FI-25-0312
Property: 714 Marquette Street, Rivergate
Occupancy: Three-story apartment building, 12 units
Owner: Marquette Row Holdings LLC
Inspection date: May 14, 2025
Inspector: Jordan Patel

Finding 1. The rear exterior exit stair previously cited for missing treads and an unstable lower landing was inspected. A plywood enclosure prevented a full view of the lower stringer and footing. The property manager stated repairs were completed on May 12, 2025.

Finding 2. Smoke alarms in the common hallway tested operational. Fire extinguisher on the second floor was within inspection date.

Disposition: VIOLATION RESOLVED. Inspection FI-25-0312 is closed. No reinspection scheduled.""",
        False,
    ),
    (
        "inspection_fi_25_0388_714_marquette_reinspection.pdf",
        "public",
        "Fire Prevention Bureau",
        147,
        """RIVERGATE FIRE PREVENTION BUREAU REINSPECTION REPORT FI-25-0388
Property: 714 Marquette Street, Rivergate
Owner: Marquette Row Holdings LLC
Reinspection date: June 5, 2025
Inspector: Lt. Amina Cole, Fire Prevention Supervisor

Reason. Reinspection follows a resident complaint received June 2, 2025 reporting that the rear exit stair remained unsafe.

Finding. Two treads on the rear exterior exit stair are missing and the lower landing is not secured to its footing. Tenants are using stacked crates to reach grade. The rear stair is the second required means of egress for floors two and three.

Determination. The May 14, 2025 closure under FI-25-0312 relied on an obstructed visual inspection and the property manager's statement, and should have been recorded as incomplete. Disposition: VIOLATION REOPENED. Marquette Row Holdings LLC must complete a permitted repair by June 20, 2025. A daily fire watch is required until the stair is repaired.""",
        False,
    ),
    (
        "incident_25_04417_structure_fire_714_marquette.pdf",
        "internal",
        "Battalion 2",
        132,
        """RIVERGATE FIRE DEPARTMENT INCIDENT REPORT 25-04417
Incident type: Structure fire, residential, working fire
Address: 714 Marquette Street, Rivergate
Date: June 20, 2025 | Alarm 02:14 | Controlled 02:51
Reporting officer: Captain Rosa Alvarez, Engine 3

Narrative. Engine 3 arrived to find heavy smoke from a second-floor rear unit. Occupants on floors two and three reported that the rear exit stair was unusable. Ladder 1 placed a ground ladder to the third-floor rear balcony and removed two occupants. Engine 3 advanced a 1.75-inch line through the front stairwell and knocked down the fire in the kitchen.

Injury. During overhaul, the lower landing of the rear exterior stair collapsed under Firefighter Marcus Chen, who sustained a minor ankle injury and was evaluated by Medic 2. He returned to duty June 24.

Contributing factors. The rear stair had been cited under inspection FI-25-0388 and the repair deadline of June 20 had not been met. Cause is under investigation by the Fire Marshal's Office as FIR-25-019.

Units: Engine 3, Engine 5, Ladder 1, Battalion 2, Medic 2. Personnel on scene: 17.""",
        False,
    ),
    (
        "investigation_fir_25_019_714_marquette.pdf",
        "restricted",
        "Fire Marshal's Office",
        118,
        """RIVERGATE FIRE MARSHAL'S OFFICE FIRE INVESTIGATION REPORT FIR-25-019
Status: OPEN INVESTIGATION. Do not release.
Related incident: 25-04417, 714 Marquette Street
Investigator: Fire Marshal Lena Whitfield

Origin. Fire patterns place the area of origin at the kitchen counter of unit 2B, adjacent to a charging e-bike battery.

Cause. A lithium-ion e-bike battery was charging on the counter. The battery casing shows internal failure consistent with thermal runaway. Cause is classified as accidental, pending laboratory analysis of the battery management board.

Code issues. The second means of egress was compromised by the unrepaired rear stair cited under FI-25-0388. The owner, Marquette Row Holdings LLC, has been referred to the City Attorney for review.""",
        False,
    ),
    (
        "pre_incident_plan_pip_0142_harbor_lofts.pdf",
        "restricted",
        "Operations Division",
        95,
        """RIVERGATE FIRE DEPARTMENT PRE-INCIDENT PLAN PIP-0142
Building: Harbor Lofts, 225 Harbor Avenue, Rivergate
Construction: Type I-B, five stories, 38 residential units over ground-floor retail
Fire protection: Fully sprinklered, Class I standpipe in both stairwells

Fire department connection. The FDC is on the Harbor Avenue frontage, 20 feet east of the main entrance. The nearest hydrant is at Harbor Avenue and Fourth Street.

Access. The Knox box is mounted left of the lobby door. Fire alarm control panel is in the lobby. Elevators have firefighter service and recall to the lobby.

Tactical notes. Under SOP 204 Revision 2025-1, stage two floors below the fire floor. Roof access is from stairwell B only. Battery storage room for resident e-bikes is on level P1.""",
        False,
    ),
    (
        "incident_25_05102_ebike_fire_68_east_market.pdf",
        "internal",
        "Battalion 1",
        84,
        """RIVERGATE FIRE DEPARTMENT INCIDENT REPORT 25-05102
Incident type: Fire, lithium-ion battery, contained to object of origin
Address: 68 East Market Street, Rivergate
Date: August 7, 2025 | Alarm 18:42 | Controlled 18:58
Reporting officer: Lieutenant Sam Okonkwo, Engine 5

Narrative. Engine 5 found an e-bike battery venting in the rear storage room of Juniper Table Cooperative. Crews applied water with a 1.75-inch line, then submerged the battery in a water-filled container per SOP 117.

Reignition watch. A fire watch remained for 60 minutes after the last visible venting. The occupant was notified in writing of reignition risk.

Battery details. Make: unknown aftermarket pack, 48-volt. The pack was on a charger connected to a power strip. No injuries.""",
        False,
    ),
    (
        "inspection_fi_25_0290_68_east_market.pdf",
        "public",
        "Fire Prevention Bureau",
        190,
        """RIVERGATE FIRE PREVENTION BUREAU FIRE INSPECTION REPORT FI-25-0290
Property: 68 East Market Street, Rivergate
Occupant: Juniper Table Cooperative (restaurant)
Inspection date: April 29, 2025
Inspector: Jordan Patel

Finding. The rear exit was obstructed by delivery cartons and the illuminated exit sign was not operational. Corrective action was due May 6, 2025.

Reinspection. A reinspection on May 7, 2025 confirmed the aisle was cleared and the exit sign was replaced.

Disposition: VIOLATION RESOLVED. No fine assessed.""",
        False,
    ),
    (
        "training_after_action_q2_2025_high_rise_drill.pdf",
        "internal",
        "Training Division",
        110,
        """RIVERGATE FIRE DEPARTMENT TRAINING AFTER-ACTION REPORT
Q2 2025 High-Rise Drill, Harbor Lofts, 225 Harbor Avenue
Drill date: June 28, 2025
Prepared by: Captain Priya Natarajan, Training Division

Observations. Crews using a 1.75-inch line from the standpipe could not reach target flow at the fourth floor because standpipe pressure dropped below 100 psi at the nozzle. Staging one floor below the fire floor placed crews in heavy simulated smoke.

Recommendations. Increase FDC supply pressure, move to a 2.5-inch attack line with a smooth-bore nozzle, require four-person attack crews, and stage two floors below the fire floor. These recommendations were forwarded to the Operations Division for SOP 204 revision.""",
        False,
    ),
    (
        "apparatus_engine_3_annual_pump_test_2025.pdf",
        "internal",
        "Fleet Services",
        60,
        """RIVERGATE FIRE DEPARTMENT APPARATUS ANNUAL PUMP TEST
Apparatus: Engine 3, 1,500 gpm pumper
Test date: September 2, 2025
Engineer: Daniel Mercer, Fleet Services

Results. Engine 3 delivered 1,500 gpm at 150 psi net pump pressure, 1,050 gpm at 200 psi, and 750 gpm at 250 psi. All results met the service test standard. Pressure governor and transfer valve operated correctly.

Disposition: PASSED. Next test due September 2026.""",
        False,
    ),
    (
        "exposure_record_25_04417_chen.pdf",
        "confidential",
        "Health and Safety Office",
        130,
        """RIVERGATE FIRE DEPARTMENT EXPOSURE AND INJURY RECORD
Confidential personnel medical record. Records Administrator access only.
Employee: Firefighter Marcus Chen
Related incident: 25-04417, 714 Marquette Street, June 20, 2025

Injury. Left ankle sprain from collapse of exterior stair landing during overhaul. Evaluated on scene by Medic 2, cleared by occupational health June 23, returned to duty June 24.

Exposure. Smoke exposure during overhaul with SCBA removed for approximately four minutes. Post-incident decontamination completed at Station 3. Exposure logged for the cancer presumption registry.""",
        False,
    ),
    (
        "board_minutes_2025_06_30.pdf",
        "public",
        "Board of Fire Commissioners",
        122,
        """RIVERGATE BOARD OF FIRE COMMISSIONERS REGULAR MEETING MINUTES
June 30, 2025 | Station 1 Training Room, 6:00 p.m.

Present: Commissioners Ellen Park, Robert Guzman, and Thomas Reyes; Fire Chief Helen Brandt.

Item 4. Chief Brandt reported on Incident 25-04417 at 714 Marquette Street, including a minor firefighter injury, and summarized the Q2 high-rise drill. The board adopted SOP 204 Revision 2025-1, effective July 1, 2025. Vote: 3-0.

Item 5. The Fire Prevention Bureau will require photographs of every resolved egress violation before an inspection is closed. Public comment requested more inspections of older apartment buildings on Marquette Street. Meeting adjourned at 7:12 p.m.""",
        False,
    ),
    (
        "hydrant_flow_test_log_district_2_scanned.pdf",
        "internal",
        "Water Supply Unit",
        45,
        """HYDRANT FLOW TEST LOG - DISTRICT 2
Rivergate Fire Department Water Supply Unit
Test date: September 18, 2025
Tested by: Engineer Daniel Mercer

Hydrant H-2-114, Harbor Avenue and Fourth Street: static 72 psi, residual 58 psi, flow 1,340 gpm. Color code green.
Hydrant H-2-131, Marquette Street and Elm Street: static 64 psi, residual 41 psi, flow 910 gpm. Color code orange.
Hydrant H-2-140, 700 block of Marquette Street: static 61 psi, residual 30 psi, flow 620 gpm. Color code red. Refer to water utility.""",
        True,
    ),
]

# Short display titles and record types for the library view.
TITLES: dict[str, tuple[str, str]] = {
    "sop_204_high_rise_operations_rev2023.pdf": ("SOP 204: High-Rise and Standpipe Operations (Rev. 2023-1)", "sop"),
    "sop_204_high_rise_operations_rev2025.pdf": ("SOP 204: High-Rise and Standpipe Operations (Rev. 2025-1)", "sop"),
    "sop_117_lithium_ion_battery_fires.pdf": ("SOP 117: Lithium-Ion Battery and Micromobility Fires", "sop"),
    "sop_310_records_release_and_redaction.pdf": ("SOP 310: Public Records Release and Redaction", "sop"),
    "inspection_fi_25_0312_714_marquette.pdf": ("Fire Inspection FI-25-0312: 714 Marquette Street", "inspection_report"),
    "inspection_fi_25_0388_714_marquette_reinspection.pdf": ("Reinspection FI-25-0388: 714 Marquette Street", "inspection_report"),
    "incident_25_04417_structure_fire_714_marquette.pdf": ("Incident Report 25-04417: Structure Fire, 714 Marquette Street", "incident_report"),
    "investigation_fir_25_019_714_marquette.pdf": ("Fire Investigation FIR-25-019: 714 Marquette Street", "investigation"),
    "pre_incident_plan_pip_0142_harbor_lofts.pdf": ("Pre-Incident Plan PIP-0142: Harbor Lofts", "pre_incident_plan"),
    "incident_25_05102_ebike_fire_68_east_market.pdf": ("Incident Report 25-05102: E-Bike Battery Fire, 68 East Market Street", "incident_report"),
    "inspection_fi_25_0290_68_east_market.pdf": ("Fire Inspection FI-25-0290: 68 East Market Street", "inspection_report"),
    "training_after_action_q2_2025_high_rise_drill.pdf": ("After-Action Report: Q2 2025 High-Rise Drill", "training_record"),
    "apparatus_engine_3_annual_pump_test_2025.pdf": ("Engine 3 Annual Pump Test, 2025", "maintenance_record"),
    "exposure_record_25_04417_chen.pdf": ("Exposure and Injury Record: Incident 25-04417", "personnel_record"),
    "board_minutes_2025_06_30.pdf": ("Board of Fire Commissioners Minutes, June 30, 2025", "meeting_minutes"),
    "hydrant_flow_test_log_district_2_scanned.pdf": ("Hydrant Flow Test Log, District 2 (scanned)", "maintenance_record"),
}
