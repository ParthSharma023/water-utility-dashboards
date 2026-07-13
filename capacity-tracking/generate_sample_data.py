#!/usr/bin/env python3
"""Generates synthetic sample data for this dashboard. All data is fabricated.

Writes data.js with the exact globals the dashboard pages consume:
  window.DATA_ROWS    - per-record array (table, map, slicers, KPIs)
  window.DATA_ANNUAL  - WWESU by year x WCR category (pre-aggregated)
  window.DATA_DONUT   - WWESU by WCR category (pre-aggregated)
  window.DATA_KPIS    - paid / not-paid rollups
  window.DATA_REFRESH - display date for the refresh badge

Every record is generated from seeded random draws: addresses, record
numbers, coordinates, basin codes, and demand values correspond to no
real property, permit, or person. Run: python3 generate_sample_data.py
"""

import json
import math
import random

SEED = 42
N_ROWS = 3000
OUT = "data.js"
REFRESH_DATE = "07/01/2026"

rnd = random.Random(SEED)

# ── Service areas ─────────────────────────────────────────────────────────────
# City treatment plants (public infrastructure names) plus fictional contract
# utility districts. Weights skew volume toward a few large plants, mirroring
# how development activity concentrates in practice.
PLANTS = [
    # (name, weight, is_contract_district)
    ("69th Street",        22, False),
    ("Sims Bayou",         10, False),
    ("Southwest",           7, False),
    ("Northwest",           6, False),
    ("West District",       5, False),
    ("Almeda Sims",         5, False),
    ("Chocolate Bayou",     4, False),
    ("Sagemont",            4, False),
    ("Keegans Bayou",       3, False),
    ("Upper Brays",         3, False),
    ("Turkey Creek",        3, False),
    ("Northeast",           3, False),
    ("Metro Central",       2, False),
    ("Greenridge",          2, False),
    ("Homestead",           2, False),
    ("Northgate",           2, False),
    ("Park Ten",            2, False),
    ("Kingwood Central",    2, False),
    ("Kingwood West",       1, False),
    ("White Oak",           1, False),
    ("Willowbrook",         1, False),
    ("Forest Cove",         1, False),
    # Fictional contract districts (numbers are made up)
    ("MUD #12",             2, True),
    ("MUD #57",             2, True),
    ("MUD #101",            1, True),
    ("FWSD #6",             1, True),
    ("WCID #89",            1, True),
]

# Metro-scale bounding box; every coordinate is a random point inside it.
LAT_MIN, LAT_MAX = 29.55, 30.08
LON_MIN, LON_MAX = -95.70, -95.10

# One synthetic "center" per service area so the map clusters organically
# instead of showing uniform noise.
plant_centers = {}
for name, _, _ in PLANTS:
    plant_centers[name] = (
        rnd.uniform(LAT_MIN + 0.05, LAT_MAX - 0.05),
        rnd.uniform(LON_MIN + 0.05, LON_MAX - 0.05),
    )

# Meter-basin codes per service area: 2-letter prefix + running number.
def basin_prefix(name):
    letters = [c for c in name.upper() if c.isalpha()]
    return (letters[0] + (letters[-1] if len(letters) > 1 else "X")) if letters else "ZZ"

plant_basins = {}
for name, _, _ in PLANTS:
    n_basins = rnd.randint(3, 12)
    prefix = basin_prefix(name)
    plant_basins[name] = [f"{prefix}{i:03d}" for i in range(1, n_basins + 1)]

plant_names = [p[0] for p in PLANTS]
plant_weights = [p[1] for p in PLANTS]
plant_is_district = {p[0]: p[2] for p in PLANTS}

# ── Addresses (fabricated) ────────────────────────────────────────────────────
STREETS = [
    "Bayou Ridge", "Cypress Hollow", "Pecan Grove", "Magnolia Bend", "Heron Lake",
    "Willow Marsh", "Sandpiper", "Cottonwood Trace", "Bluestem Prairie", "Egret Point",
    "Live Oak Meadow", "Palmetto Creek", "Sweetgum Valley", "Kestrel Ridge", "Mesquite Flats",
    "Juniper Crossing", "Tallow Grove", "Ironwood Glen", "Cedar Elm", "Prairie Falcon",
    "Longleaf Pine", "Marsh Wren", "Dogwood Hollow", "Wisteria Park", "Pintail Cove",
    "Sycamore Landing", "Hackberry Hill", "Loblolly Trace", "Bluebonnet Field", "Armadillo Run",
    "Redbud Terrace", "Osprey Nest", "Chinquapin Oak", "Yaupon Thicket", "Killdeer Meadow",
    "Sawgrass Bend", "Persimmon Grove", "Buttonbush Bayou", "Anhinga Trail", "Wax Myrtle",
]
SUFFIXES = ["Dr", "Ln", "Rd", "St", "Blvd", "Ct", "Way", "Pkwy", "Trl", "Cir"]

def make_address():
    return f"{rnd.randint(100, 19999)} {rnd.choice(STREETS)} {rnd.choice(SUFFIXES)}"

# ── Temporal distribution ─────────────────────────────────────────────────────
# Activity ramps up through 2021-2022, dips, recovers in 2024; 2026 is a
# partial year (records through June only).
YEAR_WEIGHTS = {
    2017: 6, 2018: 6, 2019: 9, 2020: 10, 2021: 13,
    2022: 14, 2023: 12, 2024: 13, 2025: 11, 2026: 6,
}
MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def make_date():
    year = rnd.choices(list(YEAR_WEIGHTS), weights=list(YEAR_WEIGHTS.values()))[0]
    month = rnd.randint(1, 6) if year == 2026 else rnd.randint(1, 12)
    day = rnd.randint(1, MONTH_DAYS[month - 1])
    return year, month, day

# ── Demand (WWESU) distribution ───────────────────────────────────────────────
# Heavily skewed: most reservations are small (single connections), a thin
# tail of large master-planned developments drives most of the volume.
def make_esu():
    bucket = rnd.random()
    if bucket < 0.024:                      # Major (>= 100 ESU)
        return min(round(100 * rnd.paretovariate(1.2), 2), 25000.0)
    if bucket < 0.090:                      # Minor (15-100 ESU)
        return round(15.01 + 85 * rnd.random() ** 2, 2)
    if bucket < 0.170:                      # zero-demand records
        return 0.0
    return round(min(max(rnd.lognormvariate(0.1, 1.1), 0.05), 14.99), 4)

def wcr_cat(esu):
    return "Major" if esu >= 100 else ("Minor" if esu >= 15 else "Small")

# ── Build rows ────────────────────────────────────────────────────────────────
rows = []
projectnum_seq = {}  # (yy, mm) -> running sequence

for _ in range(N_ROWS):
    year, month, day = make_date()
    plant = rnd.choices(plant_names, weights=plant_weights)[0]

    # Record number: YYMM + zero-padded sequence, unique by construction.
    key = (year % 100, month)
    projectnum_seq[key] = projectnum_seq.get(key, rnd.randint(100, 400)) + rnd.randint(1, 9)
    projectnum = int(f"{key[0]:02d}{key[1]:02d}{projectnum_seq[key]:04d}")

    esu = make_esu()

    # Credits offset previously-reserved capacity; occasionally they exceed
    # the new reservation, producing a small negative net MGD.
    credit_roll = rnd.random()
    if credit_roll < 0.80 or esu == 0:
        credits = 0.0
    elif credit_roll < 0.95:
        credits = round(esu * rnd.uniform(0.05, 0.5), 4)
    else:
        credits = round(esu * rnd.uniform(1.0, 2.0), 4)
    net_mgd = round((esu - credits) * 250 / 1e6, 6)

    # ~12% of records never geocoded (exercises the "No map" path).
    if rnd.random() < 0.12:
        lat = lon = None
    else:
        c_lat, c_lon = plant_centers[plant]
        lat = round(min(max(rnd.gauss(c_lat, 0.022), LAT_MIN), LAT_MAX), 6)
        lon = round(min(max(rnd.gauss(c_lon, 0.022), LON_MIN), LON_MAX), 6)

    # Contract districts carry their own service-area label; a sliver of
    # records are unassigned (excluded from the WWTP slicer by the UI).
    if rnd.random() < 0.01:
        service_ar = "Unassigned"
    elif plant_is_district[plant]:
        service_ar = plant
    else:
        service_ar = None
    wwtpsa_final = service_ar if service_ar else plant

    rows.append({
        "PROJECTNUM": projectnum,
        "ADDRESS": make_address(),
        "RESPOND_DT": f"{year:04d}-{month:02d}-{day:02d}",
        "WWSERVICEU": esu,
        "Net_Addl_MGD": net_mgd,
        "PAID": "YES" if rnd.random() < 0.6 else "NO",
        "WCR_Cat": wcr_cat(esu),
        "WWTPSA_Final": wwtpsa_final,
        "METERBASIN": rnd.choice(plant_basins[plant]) if rnd.random() > 0.03 else None,
        "SERVICE_AR": service_ar,
        "LONGITUDE": lon,
        "LATITUDE": lat,
    })

rows.sort(key=lambda r: r["RESPOND_DT"])

# ── Pre-aggregations (same shapes as the original pipeline output) ───────────
annual = {}
for r in rows:
    key = (int(r["RESPOND_DT"][:4]), r["WCR_Cat"])
    annual[key] = annual.get(key, 0.0) + r["WWSERVICEU"]
annual_rows = [
    {"year": y, "wcr_cat": c, "wwserviceu": round(v, 0)}
    for (y, c), v in sorted(annual.items())
]

donut = {}
for r in rows:
    donut[r["WCR_Cat"]] = donut.get(r["WCR_Cat"], 0.0) + r["WWSERVICEU"]
donut_rows = [
    {"wcr_cat": c, "wwserviceu": round(v, 0)} for c, v in sorted(donut.items())
]

def rollup(paid):
    sub = [r for r in rows if r["PAID"] == paid]
    return (
        len(sub),
        round(sum(r["WWSERVICEU"] for r in sub), 0),
        round(sum(r["Net_Addl_MGD"] for r in sub), 4),
    )

no_count, no_esu, no_mgd = rollup("NO")
yes_count, yes_esu, yes_mgd = rollup("YES")
kpis = {
    "not_paid_count": no_count, "not_paid_esu": no_esu, "not_paid_net_mgd": no_mgd,
    "paid_count": yes_count, "paid_esu": yes_esu, "paid_net_mgd": yes_mgd,
}

# ── Write output ──────────────────────────────────────────────────────────────
def js(v):
    return json.dumps(v, separators=(",", ":"))

out = (
    "// SYNTHETIC SAMPLE DATA - generated by generate_sample_data.py. No real records.\n"
    + "window.DATA_ROWS = " + js(rows) + ";\n"
    + "window.DATA_ANNUAL = " + js(annual_rows) + ";\n"
    + "window.DATA_DONUT = " + js(donut_rows) + ";\n"
    + "window.DATA_KPIS = " + js(kpis) + ";\n"
    + "window.DATA_REFRESH = " + js(REFRESH_DATE) + ";\n"
)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(out)

print(f"Wrote {OUT}")
print(f"  Rows:    {len(rows)}")
print(f"  Annual:  {len(annual_rows)}")
print(f"  Donut:   {len(donut_rows)}")
print(f"  KPIs:    {kpis}")
print(f"  Refresh: {REFRESH_DATE}")
