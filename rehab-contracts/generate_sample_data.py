#!/usr/bin/env python3
"""Generates synthetic sample data for this dashboard. All data is fabricated.

Produces data.js with two globals consumed by index.html:

  window.DATA_BASINV = {
    byYearWorkType:  [{year, "Work Type", totalQty}, ...]
    byFileWorkType:  [{FILE_NO, "Work Type", totalQty}, ...]
    rows:            [{RPT_DATE, FILE_NO, WO_No, BASIN, UPSTREAM, DOWNSTREAM,
                       QTY, ITEM_DESC, "Work Type", "Cost per Item"}, ...]
    dateMin, dateMax, allFileNos, defaultFileNos
  }
  window.DATA_CONTRACTS = {
    rows: [{FILE_NO, JOB_DESC, CONTRACTOR, CNTRBEGDAT, CNTRENDDAT,
            TOTAL_AMT, amt80, amt90}, ...]
  }

Every contractor name, contract/file number, basin, manhole ID, work order
number, quantity, and dollar amount below is invented. Distributions are
shaped to look like a plausible multi-year sewer rehab program (ramp-up,
seasonality, mixed pay items) but correspond to no real records.
"""

import json
import random
from datetime import date

random.seed(42)

OUT_FILE = "data.js"

# ----------------------------------------------------------------------------
# Fabricated reference lists
# ----------------------------------------------------------------------------

CONTRACTORS = [
    "Bayou Underground Utilities LLC",
    "Gulf Coast Trenchless, Inc.",
    "Lone Star Pipeline Renewal Co.",
    "Meridian Civil Constructors",
    "Cypress Creek Utility Services",
    "Redstone Infrastructure Group",
    "Bluebonnet Sewer Solutions, Inc.",
    "Pelican Bay Contracting LLC",
    "Ironwood Municipal Builders",
    "Sabine River Construction Co.",
    "Prairie View Utility Contractors",
    "Kestrel Pipeline Technologies",
]

JOB_DESCS = [
    "Sanitary Sewer Collection System Rehabilitation and Renewal",
    "Sewer Rehabilitation by Cured-in-Place Pipe (CIPP) Method",
    "Small-Diameter Gravity Sewer Rehabilitation",
    "Wastewater Collection System Renewal (Force Main)",
]

WORK_TYPES = [
    "Pipe Burst (PB)",
    "Cured-in-Place (CIPP)",
    "Point Repairs (PTR)",
    "Footage Beyond Point Repair",
    "Cleaning",
    "TV Inspection",
]

# Pay-item descriptions per work type (generic industry phrasing, invented).
ITEM_DESCS = {
    "Pipe Burst (PB)": [
        'Pipe Bursting 6"-8" Gravity Sewer, HDPE, Up to 15\' Depth',
        'Pipe Bursting 8"-10" Gravity Sewer, HDPE, Up to 20\' Depth',
        'Static Pipe Bursting 6"-8" Sewer to 8.6" OD, Up to 20\' Depth',
    ],
    "Cured-in-Place (CIPP)": [
        'Cured-in-Place Pipe Liner, 8" Gravity Sewer, All Depths',
        'Cured-in-Place Pipe Liner, 10"-12" Gravity Sewer, All Depths',
    ],
    "Point Repairs (PTR)": [
        'Point Repair of 6"-10" Gravity Sewer, Up to 10\' Depth',
        'Point Repair of 6"-10" Gravity Sewer, 10\'-15\' Depth',
        'Point Repair of 12"-18" Gravity Sewer, Up to 15\' Depth',
    ],
    "Footage Beyond Point Repair": [
        'Sewer Replacement Beyond Point Repair, 6"-10", Up to 10\' Depth',
        'Sewer Replacement Beyond Point Repair, 6"-10", 10\'-15\' Depth',
    ],
    "Cleaning": [
        'Cleaning of 6"-10" Gravity Sanitary Sewer, All Depths',
        'Heavy Cleaning of 6"-12" Gravity Sewer, All Depths',
    ],
    "TV Inspection": [
        'CCTV Inspection of 6"-10" Gravity Sanitary Sewer, All Depths',
        'Post-Rehabilitation CCTV Inspection, All Sizes, All Depths',
    ],
}

# Miscellaneous pay items carried with a null Work Type (support/restoration
# line items that the charts ignore but the payment table and gauge include).
MISC_ITEMS = [
    ("Trench Safety System, All Soil Types, Over 5' Depth", 1, 40, 15, 60),
    ("Cement Stabilized Sand Backfill (per C.Y.)", 2, 90, 45, 75),
    ("Reconnect Service Lateral by Excavation, Complete, All Sizes", 1, 8, 380, 950),
    ("Sanitary Sewer Cleanout on Service Lateral, 4-Inch Detail", 1, 6, 300, 800),
    ("Saw Cut of Concrete/Asphalt Pavement, All Depths, As Needed", 4, 120, 4, 12),
    ("Removal and Replacement of 2\" Hot-Mix Asphalt Pavement (Type D)", 3, 80, 35, 90),
    ("Removal and Replacement of Semi-Rigid Pavement Base", 3, 60, 30, 85),
    ("Manhole Rehabilitation with Structural Liner, Incl. Bench and Invert", 1, 3, 1800, 4200),
    ("Removal and Replacement of Concrete Sidewalk, Incl. Reinforcement", 4, 60, 55, 120),
    ("Traffic Control Plan Implementation", 1, 2, 350, 1400),
    ("Mobilization for Short Segment (Under 350 LF)", 1, 2, 450, 900),
    ("Emergency Mobilization (Within 24 Hours of Approval)", 1, 1, 900, 2200),
    ("Excavated Entry/Exit Pit, Up to 8' Depth", 1, 3, 500, 1500),
    ("Obstruction Removal by Excavation, All Depths", 1, 2, 700, 1900),
    ("Bypass Pumping During Rehabilitation, All Sizes", 1, 4, 400, 1600),
    ("Sliplining of Existing Service Line (per LF)", 5, 60, 18, 45),
]

# Work-type mix (misc/null items dominate row counts, as on a real pay app).
WT_WEIGHTS = [
    (None, 0.560),
    ("Point Repairs (PTR)", 0.078),
    ("Cleaning", 0.078),
    ("TV Inspection", 0.077),
    ("Pipe Burst (PB)", 0.075),
    ("Footage Beyond Point Repair", 0.070),
    ("Cured-in-Place (CIPP)", 0.062),
]

# Program-wide activity level by year (ramp up, peak, wind down).
YEAR_WEIGHT = {
    2019: 0.55, 2020: 0.90, 2021: 1.15, 2022: 1.30,
    2023: 1.10, 2024: 0.95, 2025: 0.80, 2026: 0.60,
}
LAST_REPORT = date(2026, 6, 1)

# ----------------------------------------------------------------------------
# Contracts (file numbers are fabricated: three invented award series)
# ----------------------------------------------------------------------------

def make_contracts():
    contracts = []
    series = [("5102", 14), ("5217", 14), ("5433", 12)]
    for base, count in series:
        for i in range(1, count + 1):
            contracts.append(f"{base}-{i:02d}")
    return contracts


ALL_FILE_NOS = make_contracts()               # 40 contracts
DEFAULT_FILE_NOS = [f"5102-{i:02d}" for i in range(7, 13)]  # 6 pre-checked

# Staggered activity windows (year_start, month_start, months) so the default
# selection collectively spans the whole reporting horizon.
DEFAULT_WINDOWS = {
    "5102-07": (2019, 1, 30),
    "5102-08": (2020, 3, 30),
    "5102-09": (2021, 2, 32),
    "5102-10": (2022, 4, 30),
    "5102-11": (2023, 5, 30),
    "5102-12": (2024, 6, 25),
}

# ----------------------------------------------------------------------------
# Row generation helpers
# ----------------------------------------------------------------------------

BASINS = [f"{random.randint(40, 68)}{random.randint(100, 999)}" for _ in range(24)] + [
    f"{p}{random.randint(100, 999)}" for p in ("NB", "EB", "SB", "WB", "CB", "LB")
]

def month_iter(y0, m0, months):
    y, m = y0, m0
    for _ in range(months):
        if date(y, m, 1) > LAST_REPORT:
            return
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1

def pick_work_type():
    r = random.random()
    acc = 0.0
    for wt, w in WT_WEIGHTS:
        acc += w
        if r <= acc:
            return wt
    return None

def lognorm(median, sigma, lo, hi):
    v = median * random.lognormvariate(0, sigma)
    return max(lo, min(hi, v))

def make_line_item(rpt, file_no):
    wt = pick_work_type()
    basin = random.choice(BASINS)
    mh = random.randint(100000, 899999)
    row = {
        "RPT_DATE": rpt,
        "FILE_NO": file_no,
        "WO_No": random.randint(1000, 99999),
        "BASIN": basin,
        "UPSTREAM": None if random.random() < 0.12 else f"MH-{mh}",
        "DOWNSTREAM": f"MH-{mh + 1}",
    }
    if wt is None:
        desc, qlo, qhi, clo, chi = random.choice(MISC_ITEMS)
        qty = float(random.randint(qlo, qhi))
        unit = random.uniform(clo, chi)
        row.update({
            "QTY": qty,
            "ITEM_DESC": desc,
            "Work Type": None,
            "Cost per Item": round(qty * unit, 2),
        })
        return row

    if wt == "Point Repairs (PTR)":
        qty = float(random.choices([1, 2, 3, 4], weights=[70, 18, 8, 4])[0])
        unit = random.uniform(950, 1700)
    elif wt == "Pipe Burst (PB)":
        qty = round(lognorm(230, 0.55, 40, 1300), 1)
        unit = random.uniform(26, 42)
    elif wt == "Cured-in-Place (CIPP)":
        qty = round(lognorm(170, 0.55, 40, 950), 1)
        unit = random.uniform(42, 62)
    elif wt == "Footage Beyond Point Repair":
        qty = round(lognorm(10, 0.9, 2, 350), 1)
        unit = random.uniform(28, 48)
    elif wt == "Cleaning":
        qty = round(lognorm(210, 0.5, 30, 3200), 1)
        unit = random.uniform(1.0, 1.7)
    else:  # TV Inspection
        qty = round(lognorm(215, 0.5, 30, 3200), 1)
        unit = random.uniform(0.9, 1.4)

    row.update({
        "QTY": qty,
        "ITEM_DESC": random.choice(ITEM_DESCS[wt]),
        "Work Type": wt,
        "Cost per Item": round(qty * unit, 2),
    })
    return row

def gen_contract_rows(file_no, window, items_per_month):
    y0, m0, months = window
    rows = []
    for y, m in month_iter(y0, m0, months):
        season = 1.0 + 0.25 * (1 if m in (5, 6, 7, 8, 9) else -1) * random.random()
        lam = items_per_month * YEAR_WEIGHT.get(y, 0.7) * season
        n = max(1, int(random.gauss(lam, lam * 0.3)))
        rpt = f"{y:04d}-{m:02d}-01"
        rows.extend(make_line_item(rpt, file_no) for _ in range(n))
    return rows

# ----------------------------------------------------------------------------
# Build dataset
# ----------------------------------------------------------------------------

rows = []

# Default contracts: richer activity so the landing view is well populated.
for fn, window in DEFAULT_WINDOWS.items():
    rows.extend(gen_contract_rows(fn, window, items_per_month=9))

# Other active contracts (22 of the remaining 34) with lighter activity.
other_fns = [fn for fn in ALL_FILE_NOS if fn not in DEFAULT_FILE_NOS]
active_others = random.sample(other_fns, 22)
for fn in active_others:
    y0 = random.randint(2019, 2024)
    m0 = random.randint(1, 12)
    months = random.randint(18, 34)
    rows.extend(gen_contract_rows(fn, (y0, m0, months), items_per_month=3.2))

rows.sort(key=lambda r: (r["RPT_DATE"], r["FILE_NO"]))

# ----------------------------------------------------------------------------
# Contract funding table: size each award so cumulative payments land at a
# believable 55-92% utilization (drives the expenditure gauge).
# ----------------------------------------------------------------------------

spend = {}
windows = dict(DEFAULT_WINDOWS)
for r in rows:
    spend[r["FILE_NO"]] = spend.get(r["FILE_NO"], 0.0) + r["Cost per Item"]

contract_rows = []
for fn in ALL_FILE_NOS:
    if fn in spend:
        util = random.uniform(0.55, 0.92)
        total = spend[fn] / util
        first = min(r["RPT_DATE"] for r in rows if r["FILE_NO"] == fn)
        y, m = int(first[:4]), int(first[5:7])
        beg = date(y, m, random.randint(1, 28))
    else:
        total = random.uniform(800_000, 4_200_000)
        beg = date(random.randint(2024, 2026), random.randint(1, 12),
                   random.randint(1, 28))
    dur_days = random.randint(540, 1100)
    end = date.fromordinal(beg.toordinal() + dur_days)
    contract_rows.append({
        "FILE_NO": fn,
        "JOB_DESC": random.choice(JOB_DESCS),
        "CONTRACTOR": random.choice(CONTRACTORS),
        "CNTRBEGDAT": beg.isoformat(),
        "CNTRENDDAT": end.isoformat(),
        "TOTAL_AMT": round(total, 2),
        "amt80": round(total * 0.8),
        "amt90": round(total * 0.9),
    })

# ----------------------------------------------------------------------------
# Aggregates (kept for schema parity with the original data contract)
# ----------------------------------------------------------------------------

by_year_wt, by_file_wt = {}, {}
for r in rows:
    wt = r["Work Type"]
    if wt is None:
        continue
    yk = (int(r["RPT_DATE"][:4]), wt)
    fk = (r["FILE_NO"], wt)
    by_year_wt[yk] = by_year_wt.get(yk, 0) + r["QTY"]
    by_file_wt[fk] = by_file_wt.get(fk, 0) + r["QTY"]

byYearWorkType = [
    {"year": y, "Work Type": wt, "totalQty": round(q)}
    for (y, wt), q in sorted(by_year_wt.items())
]
byFileWorkType = [
    {"FILE_NO": fn, "Work Type": wt, "totalQty": round(q)}
    for (fn, wt), q in sorted(by_file_wt.items())
]

data_basinv = {
    "byYearWorkType": byYearWorkType,
    "byFileWorkType": byFileWorkType,
    "rows": rows,
    "dateMin": min(r["RPT_DATE"] for r in rows),
    "dateMax": max(r["RPT_DATE"] for r in rows),
    "allFileNos": ALL_FILE_NOS,
    "defaultFileNos": DEFAULT_FILE_NOS,
}
data_contracts = {"rows": contract_rows}

# ----------------------------------------------------------------------------
# Emit data.js
# ----------------------------------------------------------------------------

with open(OUT_FILE, "w") as f:
    f.write("// SYNTHETIC SAMPLE DATA - generated by generate_sample_data.py. "
            "No real records.\n")
    f.write("window.DATA_BASINV = ")
    f.write(json.dumps(data_basinv, separators=(",", ":")))
    f.write(";\nwindow.DATA_CONTRACTS = ")
    f.write(json.dumps(data_contracts, separators=(",", ":")))
    f.write(";\n")

print(f"Wrote {OUT_FILE}: {len(rows)} payment rows, "
      f"{len(contract_rows)} contracts, "
      f"{len(byYearWorkType)} year/work-type aggregates")
