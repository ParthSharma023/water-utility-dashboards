#!/usr/bin/env python3
"""Generates synthetic sample data for this dashboard. All data is fabricated.

Produces data.js with the three datasets the pages consume:
  window.DATA       - one row per manhole inspection (assessment-grade.html)
  window.DATA_DC45  - one row per defect observation (defect-causes-45.html)
  window.DATA_NA    - qr45 / remediation / detail tables (index.html)

Every identifier (manhole number, basin, inspection ID, work order) is
generated from a seeded RNG; none corresponds to a real asset or record.

Usage: python3 generate_sample_data.py
"""

import json
import random
from datetime import date, timedelta

rng = random.Random(45045)

OUT_PATH = "data.js"
N_ROWS = 1000            # total manhole inspections in window.DATA
QR45_SHARE = 0.57        # share of inspections in the historical QR 4/5 program

# ── Defect catalog (MACP-style codes and descriptions) ─────────────────────────
# (code, description, [candidate components], family, fixing method, weight)
COVER_CORRODED = ("Cover Condition - Corroded", "Cover Condition - Corroded",
                  ["Cover Condition"], "Structural", "No Action", 0)
FRAME_MISSING = ("Frame Condition - Missing", "Frame Condition - Missing",
                 ["Frame Condition"], "Structural", "No Action", 0)

DEFECT_POOL = [
    # code, description, components, family, method, weight
    ("HVV",  "Hole Void Visible",            ["Channel", "Cone Interior", "Wall Interior", "Chimney Interior"], "Structural", "Patching/Sealing/Grouting", 13),
    ("MML",  "Missing Mortar Large",         ["Wall Interior", "Cone Interior", "Chimney Interior"], "Structural", "Brick/Mortar replacement", 12),
    ("MB",   "Missing Brick",                ["Cone Interior", "Chimney Interior", "Wall Interior"], "Structural", "Brick/Mortar replacement", 11),
    ("FM",   "Fracture Multiple",            ["Cone Interior", "Wall Interior", "Chimney Interior"], "Structural", "Patching/Sealing/Grouting", 11),
    ("B",    "Broken",                       ["Chimney Interior", "Wall Interior", "Cone Interior"], "Structural", "Patching/Sealing/Grouting", 10),
    ("LFD",  "Lining Feature Detached",      ["Wall Interior", "Cone Interior"], "Structural", "Relining/Reattach", 10),
    ("HSV",  "Hole Soil Visible",            ["Wall Interior", "Cone Interior", "Chimney Interior"], "Structural", "Patching/Sealing/Grouting", 8),
    ("SRV",  "Surface Damage Reinforcement Visible", ["Wall Interior", "Cone Interior"], "Structural", "Patching/Sealing/Grouting", 7),
    ("DSZ",  "Deposits Settled Other",       ["Channel"], "O&M", "Obstruction/Debris Removal", 7),
    ("Frame Offset Distance gt 4in", "Frame Offset Distance gt 4in", ["Frame Offset Distance"], "Structural", "Fix Frame Offset", 6),
    ("Frame Condition - Broken", "Frame Condition - Broken", ["Frame Condition"], "Structural", "Replace Manhole Frame", 5),
    ("SAM",  "Surface Damage Aggregate Missing", ["Wall Interior", "Channel", "Bench"], "Structural", "Patching/Sealing/Grouting", 5),
    ("H",    "Hole",                         ["Channel"], "Structural", "Patching/Sealing/Grouting", 4),
    ("SMW",  "Surface Damage Missing Wall",  ["Channel", "Bench"], "Structural", "Patching/Sealing/Grouting", 4),
    ("Seal Condition - Loose", "Seal Condition - Loose", ["Seal Condition"], "Structural", "Patching/Sealing/Grouting", 4),
    ("Seal Condition - Cracked", "Seal Condition - Cracked", ["Seal Condition"], "Structural", "Patching/Sealing/Grouting", 3),
    ("DSF",  "Deposits Settled Fine",        ["Channel"], "O&M", "Obstruction/Debris Removal", 3),
    ("Cover Insert Condition - Leaking", "Cover Insert Condition - Leaking", ["Cover Insert Condition"], "O&M", "Install Manhole Insert", 3),
    ("LFDL", "Lining Feature Delaminating",  ["Wall Interior", "Cone Interior"], "Structural", "Relining/Reattach", 2),
    ("DSC",  "Deposits Settled Hard/Compacted", ["Channel"], "O&M", "Obstruction/Debris Removal", 2),
    ("OBZ",  "Obstruction Other",            ["Channel"], "O&M", "Obstruction/Debris Removal", 2),
    ("Frame Condition - Cracked", "Frame Condition - Cracked", ["Frame Condition"], "Structural", "Replace Manhole Frame", 2),
    ("OBI",  "Obstruction Intruding Through Wall", ["Wall Interior", "Cone Interior"], "O&M", "Point Repair", 2),
    ("BSV",  "Broken Soil Visible",          ["Wall Interior", "Chimney Interior"], "Structural", "Patching/Sealing/Grouting", 2),
    ("SRP",  "Surface Damage Reinforcement Projecting", ["Wall Interior", "Cone Interior"], "Structural", "Patching/Sealing/Grouting", 1.5),
    ("DSGV", "Deposits Settled Gravel",      ["Channel"], "O&M", "Obstruction/Debris Removal", 1.5),
    ("Adjustment Ring Condition - Leaking", "Adjustment Ring Condition - Leaking", ["Adjustment Ring Condition"], "O&M", "Replace Adjustment Ring Condition", 1),
    ("Adjustment Ring Condition - Broken", "Adjustment Ring Condition - Broken", ["Adjustment Ring Condition"], "Structural", "Replace Adjustment Ring Condition", 1),
    ("Cover Condition - Broken", "Cover Condition - Broken", ["Cover Condition"], "Structural", "Replace Manhole Cover", 1),
    ("Cover Condition - Missing", "Cover Condition - Missing", ["Cover Condition"], "Structural", "Replace Manhole Cover", 1),
    ("Cover Condition - Cracked", "Cover Condition - Cracked", ["Cover Condition"], "Structural", "Replace Manhole Cover", 0.5),
    ("Oversized", "Oversized",               ["Cover Frame Fit"], "Structural", "Replace Manhole Cover", 1),
    ("Cover Insert Condition - InsertFell", "Cover Insert Condition - InsertFell", ["Cover Insert Condition"], "O&M", "Retrieve Manhole Insert", 1),
    ("JOM",  "Joint Offset Medium",          ["Chimney Interior"], "Structural", "Patching/Sealing/Grouting", 0.6),
    ("DAGS", "Deposits Attached Grease",     ["Channel"], "O&M", "Obstruction/Debris Removal", 0.6),
    ("IRB",  "Infiltration Runner Barrel",   ["Wall Interior"], "O&M", "Patching/Sealing/Grouting", 0.4),
    ("IG",   "Infiltration Gusher",          ["Wall Interior", "Cone Interior"], "O&M", "Patching/Sealing/Grouting", 0.3),
    ("X",    "Collapse",                     ["Bench"], "Structural", "Bench Replacement", 0.1),
]
POOL_WEIGHTS = [d[5] for d in DEFECT_POOL]

DEFECT_CATS = ["Others", "Cover Corroded - Only", "Cover Corroded & Frame Missing", "Frame Missing - Only"]

# ── Helpers ────────────────────────────────────────────────────────────────────
def rand_date(start, end):
    """Random date between two date objects, inclusive."""
    span = (end - start).days
    return start + timedelta(days=rng.randint(0, span))

def iso(d):
    return d.isoformat()

# ── Basins and manholes ────────────────────────────────────────────────────────
BASIN_PREFIXES = ["AL", "BK", "CW", "DR", "EV", "FN", "GH", "HM", "JR", "KT"]
basins = []
used_nums = set()
while len(basins) < 44:
    code = f"{rng.choice(BASIN_PREFIXES)}{rng.randint(1, 329):03d}"
    if code not in used_nums:
        used_nums.add(code)
        basins.append(code)
# Skewed basin sizes so the Basin Status table looks organic
basin_weights = [rng.uniform(0.4, 1.0) ** 2 for _ in basins]

# One or two contract work orders per basin (synthetic contract numbering)
basin_wo = {}
for b in basins:
    contract = rng.choice([4180, 4181, 4270, 4271])
    group = rng.randint(100, 139)
    seq = rng.randint(1, 18)
    wo = f"{contract}-{group}-{seq}"
    roll = rng.random()
    if roll < 0.20:
        wo += f"-{b}"
    elif roll < 0.28:
        wo += f" Submittal {rng.randint(1, 9)}"
    basin_wo[b] = wo

mh_seq = {b: 0 for b in basins}
def new_manhole():
    b = rng.choices(basins, weights=basin_weights)[0]
    mh_seq[b] += rng.randint(1, 4)
    mhnbr = f"{b}{mh_seq[b]:03d}"
    return b, mhnbr

insp_ids = rng.sample(range(10000, 130000), N_ROWS)

# ── Reviewed-date profile (monthly weights, Jul 2024 - Mar 2026) ──────────────
review_months = []
for yr in (2024, 2025, 2026):
    for mo in range(1, 13):
        if yr == 2024 and mo < 7:
            continue
        if yr == 2026 and mo > 3:
            break
        review_months.append((yr, mo))
# Ramp up through 2024-2025, holiday dip, strong start of 2026
month_weights = [2, 4, 7, 9, 8, 6,             # Jul-Dec 2024
                 8, 10, 12, 13, 12, 11, 12, 13, 11, 9, 7, 5,  # 2025
                 9, 11, 6]                     # Jan-Mar 2026
def rand_review_date():
    yr, mo = rng.choices(review_months, weights=month_weights)[0]
    day = rng.randint(1, 28)
    return date(yr, mo, day)

# ── Build inspections ─────────────────────────────────────────────────────────
def pick_defects():
    """Return (defect list, defect category) for one QR 4/5 inspection."""
    roll = rng.random()
    if roll < 0.245:
        return [COVER_CORRODED], "Cover Corroded - Only"
    if roll < 0.310:
        return [FRAME_MISSING], "Frame Missing - Only"
    if roll < 0.540:
        defects = [COVER_CORRODED, FRAME_MISSING]
        if rng.random() < 0.35:
            defects += rng.choices(DEFECT_POOL, weights=POOL_WEIGHTS, k=1)
        return defects, "Cover Corroded & Frame Missing"
    k = rng.choices([1, 2, 3, 4], weights=[45, 30, 17, 8])[0]
    defects = []
    for d in rng.choices(DEFECT_POOL, weights=POOL_WEIGHTS, k=k):
        if d not in defects:
            defects.append(d)
    if rng.random() < 0.25:
        defects.insert(0, COVER_CORRODED)
    return defects, "Others"

data_rows, qr45_rows, remediation_rows, detail_rows, dc45_rows = [], [], [], [], []
n_qr45 = int(N_ROWS * QR45_SHARE)

# Contractor program years are front-loaded; AI-reviewed inspections are recent
CONTRACTOR_YEARS = [(2021, 0.12), (2022, 0.34), (2023, 0.38), (2024, 0.16)]

for i in range(N_ROWS):
    basin, mhnbr = new_manhole()
    upsmh = f"MH_{mhnbr}"
    iid = insp_ids[i]
    in_qr45 = i < n_qr45

    if in_qr45:
        yr = rng.choices([y for y, _ in CONTRACTOR_YEARS], weights=[w for _, w in CONTRACTOR_YEARS])[0]
        insp_date = rand_date(date(yr, 1, 1) if yr > 2021 else date(2021, 5, 1),
                              date(yr, 12, 28) if yr < 2024 else date(2024, 3, 15))
        source = "Contractor" if rng.random() < 0.76 else "AI Review"
    else:
        insp_date = rand_date(date(2024, 1, 10), date(2026, 1, 7))
        r = rng.random()
        source = "AI Review" if r < 0.95 else ("Contractor-NoVideo" if r < 0.99 else "Contractor")

    if source.startswith("Contractor"):
        link = str(iid)
    else:
        link = f"https://example.com/inspections/{rng.getrandbits(48):012x}"

    reviewed = rng.random() < 0.54
    review_dt = rand_review_date() if reviewed else None
    ag = rng.choices([0, 1, 2, 3, 4, 5], weights=[6, 55, 13, 10, 13, 4])[0] if reviewed else None

    defect_cat = None
    defect_type = None
    qr = None
    date_remediated = None

    if in_qr45:
        defects, defect_cat = pick_defects()
        grades = [4 if rng.random() < 0.58 else 5 for _ in defects]
        qr = max(grades)
        defect_type = "|".join(d[1] for d in defects)

        remediation = "No"
        r = rng.random()
        if r < 0.050:
            remediation = "contractor error-Frame Not Missing"
        elif r < 0.063:
            remediation = "Repaired"
        elif r < 0.072:
            remediation = "Rescored"
        if remediation != "No":
            rem_date = min(insp_date + timedelta(days=rng.randint(30, 500)), date(2024, 2, 14))
            remediation_rows.append({"Date": iso(rem_date), "InspectionID": str(iid), "Remediation": remediation})
            if remediation == "Repaired":
                date_remediated = iso(rem_date)

        qr45_rows.append({
            "Date": iso(insp_date), "UPSMH_ID": upsmh, "InspectionID": str(iid),
            "Source": source, "Inspection_Link": link, "DefectCat": defect_cat,
            "DefectType": defect_type, "Remediation": remediation,
        })

        for (code, desc, comps, family, method, _w), grade in zip(defects, grades):
            comp = rng.choice(comps)
            detail_rows.append({
                "InspectionID": str(iid), "ComponentDescription": comp, "Defect": code,
                "Description": desc, "Grade": grade, "Family": family,
                "WorkType_PerComponent": f"{iid}-{comp}-No Action",
                "No_Action_Fixing_Method": method,
                "No_Action_Work_ID": f"{iid}-{method}",
            })
            dc45_rows.append({"Defect": code, "ComponentDescription": comp, "Description": desc})
    else:
        qr = rng.choices([4, 5, 3, 2, -1], weights=[55, 40, 2, 2, 1])[0]
        if reviewed and rng.random() < 0.55:
            defect_cat = rng.choices(DEFECT_CATS, weights=[45, 25, 23, 7])[0]
        if reviewed and rng.random() < 0.60:
            picks = rng.choices(DEFECT_POOL, weights=POOL_WEIGHTS, k=rng.randint(1, 3))
            defect_type = "|".join(d[1] for d in picks)

    data_rows.append({
        "ID": iid if in_qr45 else None,
        "Date": iso(insp_date),
        "MHNbr": mhnbr,
        "UPSMH_ID": upsmh,
        "Basin": basin,
        "MACP QuickRating": qr,
        "AssessmentGrade": ag,
        "reviewedDate": iso(review_dt) if review_dt else None,
        "isReviewDone": "Yes" if reviewed else "No",
        "Source": source,
        "DefectCat": defect_cat,
        "DefectType": defect_type,
        "DateRemediated": date_remediated,
        "CtrWOBasin": basin_wo[basin],
        "inspection_link": link,
    })

last_update = max(r["reviewedDate"] for r in data_rows if r["reviewedDate"])

# ── Write data.js ──────────────────────────────────────────────────────────────
def js(obj):
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("// SYNTHETIC SAMPLE DATA - generated by generate_sample_data.py. No real records.\n")
    f.write("window.DATA = " + js({"rows": data_rows, "lastUpdate": last_update}) + ";\n")
    f.write("window.DATA_DC45 = " + js({"rows": dc45_rows}) + ";\n")
    f.write("window.DATA_NA = " + js({
        "qr45": qr45_rows, "remediation": remediation_rows, "detail": detail_rows,
    }) + ";\n")

print(f"Wrote {OUT_PATH}")
print(f"  DATA.rows:            {len(data_rows)}")
print(f"  DATA_DC45.rows:       {len(dc45_rows)}")
print(f"  DATA_NA.qr45:         {len(qr45_rows)}")
print(f"  DATA_NA.remediation:  {len(remediation_rows)}")
print(f"  DATA_NA.detail:       {len(detail_rows)}")
print(f"  lastUpdate:           {last_update}")
