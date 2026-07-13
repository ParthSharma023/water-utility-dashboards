#!/usr/bin/env python3
"""Generates synthetic sample data for this dashboard. All data is fabricated.

Produces data-wo-ls.js: a window.WO_ROWS array of lift-station work orders in
the exact schema the dashboard pages consume:

    WO         work order number (7-digit, increasing with date)
    desc       event/work description
    created    creation date (YYYY-MM-DD)
    sched_end  scheduled end date (YYYY-MM-DD)
    jobtype    job type code (BRKD, CM, PVM, PDM, ELEC, ... or null)
    status     "Open" | "Closed"
    loc_id     4-digit location id of the lift station
    facility   lift station name
    obj_code   asset/object code (loc_id + "14" + equipment suffix)
    obj_desc   asset/object description
    cls        equipment class (LEVEL SYSTEM, LIFT PUMP 01, WET WELL, ...)

The generator is seeded, so output is reproducible for a given run date.
Dates span the ~15 months up to the run date because the dashboards default
to relative date windows ("last 2 weeks", "last 3 months").

Realism knobs:
  - facility activity follows a lognormal (few busy stations, long tail)
  - wet-weather season (May-Jul) and January freeze bump alarm volume
  - telemetry level alarms dominate, and close out fast; corrective work
    stays open longer (P(open) decays with age per equipment class)
  - each station has 2-7 pumps; low-numbered pumps get most of the work
"""

import json
import math
import random
from datetime import date, timedelta

SEED = 20250613
OUT_FILE = "data-wo-ls.js"
N_FACILITIES = 120
BASE_PER_MONTH = 210        # average work orders per month before seasonality
N_MONTHS = 15               # months of history to generate

rng = random.Random(SEED)

# ── Facilities ────────────────────────────────────────────────────────────────
NAME_A = [
    "AMBER", "ASHFORD", "BIRCH", "BRAMBLE", "CEDAR", "CLEARWATER", "COPPER",
    "CRESTMONT", "DEERFIELD", "DRIFTWOOD", "ELMWOOD", "FALLBROOK", "FERN",
    "FOXTAIL", "GLENBROOK", "HARBORLIGHT", "HAZELCREST", "HICKORY", "IVYSTONE",
    "JUNIPER", "KESTREL", "LARKSPUR", "LAUREL", "MAPLEWOOD", "MARINER",
    "MEADOWLARK", "MOSSBANK", "NORTHGATE", "OAKMONT", "ORCHID", "PEBBLEBROOK",
    "PINEHURST", "QUAIL RUN", "RAVENWOOD", "RIVERBEND", "ROSEGATE", "SADDLEHORN",
    "SAGEBRUSH", "SILVERLEAF", "SPRINGWATER", "STONEBRIDGE", "SUMMERFIELD",
    "SUNDANCE", "SYCAMORE", "TALLOW", "THORNBURY", "TIMBERLINE", "TRAILWOOD",
    "WALNUT BEND", "WESTBURY OAKS", "WHISPER HOLLOW", "WILLOWMIST", "WINDMILL",
    "WINTERBERRY", "WREN VALLEY", "YAUPON",
]
NAME_B = ["", "", "", "", " CREEK", " GLEN", " GROVE", " HOLLOW", " LAKE",
          " PARK", " POINT", " RIDGE", " SPRINGS", " TRACE", " VIEW"]
SUFFIX = ["", "", "", "", "", " RD.", " DR.", " ST.", " LN.", " BLVD."]


def make_facilities():
    """120 unique synthetic lift stations with ids, activity weights, pumps."""
    names = set()
    while len(names) < N_FACILITIES:
        base = rng.choice(NAME_A) + rng.choice(NAME_B) + rng.choice(SUFFIX)
        name = base + " LIFT STATION"
        if name in names:
            name = base + " #2 LIFT STATION"
        names.add(name)

    loc_ids = rng.sample(range(1, 1000), N_FACILITIES)
    facilities = []
    for name, loc in zip(sorted(names), loc_ids):
        facilities.append({
            "facility": name,
            "loc_id": f"{loc:04d}",
            # lognormal weight: a handful of chronic stations, long quiet tail
            "weight": rng.lognormvariate(0, 0.9),
            "n_pumps": rng.choices([2, 3, 4, 5, 6, 7],
                                   weights=[62, 18, 10, 6, 3, 1])[0],
        })
    return facilities


# ── Equipment classes ─────────────────────────────────────────────────────────
# (class, weight%, obj_code suffix, decay_tau_days for staying open)
CLASSES = [
    ("LEVEL SYSTEM",          39.5, "LVLSYS",  12),
    ("LIFT STATION FACILITY", 13.0, None,      35),   # suffix chosen per-row
    ("LIFT PUMP",             16.0, None,      50),   # pump number per-row
    ("AUTOMATION",            11.0, "AUTO",    25),
    ("(Blank)",                7.0, "GEN01",   30),
    ("WET WELL",               5.5, "WETWLL",  30),
    ("FORCE MAIN",             2.1, "FRCMN",   45),
    ("GROUNDS",                2.0, "GRNDS",   30),
    ("FENCE",                  0.9, "FENCE",   40),
    ("MCC/SWITCHGEAR",         0.8, "MCCSWG",  45),
    ("DRY PIT AREA",           0.5, "DRYPIT",  40),
    ("PIPING",                 0.5, "PIPING",  40),
    ("FORCE MAIN AREA",       0.45, "FMAREA",  40),
    ("FORCE MAIN ARV",        0.35, "FMARV01", 40),
    ("HVAC EQUIPMENT",         0.2, "HVAC01",  40),
    ("ODOR CONTROL UNIT",      0.2, "ODRCTL",  40),
]
CLASS_NAMES = [c[0] for c in CLASSES]
CLASS_WEIGHTS = [c[1] for c in CLASSES]
CLASS_SUFFIX = {c[0]: c[2] for c in CLASSES}
CLASS_TAU = {c[0]: c[3] for c in CLASSES}

# ── Descriptions: (text, jobtype) pools per class ─────────────────────────────
# "{n}" is replaced with a pump number, "{ft}" with a level in feet.
DESC_POOLS = {
    "LEVEL SYSTEM": [
        ("Telemetry: high wet well level", "BRKD", 20),
        ("Telemetry: high wet well level with 2 pumps running", "BRKD", 14),
        ("Telemetry: high wet well level with no pumps on", "BRKD", 8),
        ("Telemetry: irregular cycle pattern", "BRKD", 22),
        ("Telemetry: no communication", "BRKD", 14),
        ("Telemetry: flat line reading", "BRKD", 6),
        ("Telemetry: low wet well level", "BRKD", 4),
        ("Telemetry: high well at {ft}ft", "BRKD", 6),
        ("Telemetry: power failure alarm", "ELEC", 3),
        ("Telemetry: pump fail alarm", "BRKD", 3),
    ],
    "LIFT STATION FACILITY": [
        ("ELECTRICAL PROBLEM", "ELEC", 14),
        ("MAINTENANCE PROBLEM", "CM", 12),
        ("Housekeeping", "PVM", 12),
        ("Wash down wet well and site", "PVM", 8),
        ("Site inspection", "PVM", 8),
        ("Replace site lighting", "CM", 6),
        ("Control panel repair", "ELEC", 6),
        ("Breaker keeps tripping", "ELEC", 5),
        ("Station on generator power - check ATS", "BRKD", 4),
        ("Hatch lid damaged - needs replacement", "CM", 4),
    ],
    "LIFT PUMP": [
        ("Repair pump #{n} as needed", "CM", 16),
        ("Pump #{n} tripping breaker", "ELEC", 10),
        ("Pump #{n} not pumping to capacity", "CM", 10),
        ("Pull and inspect pump #{n}", "CM", 10),
        ("Replace seal on pump #{n}", "CM", 8),
        ("Pump #{n} running hot", "BRKD", 8),
        ("Pump #{n} seal fail alarm", "BRKD", 8),
        ("Pump #{n} excessive vibration", "PDM", 6),
        ("Quarterly pump PM inspection", "PVM", 8),
        ("Pump #{n} will not reset", "BRKD", 6),
    ],
    "AUTOMATION": [
        ("RTU not reporting", "BRKD", 18),
        ("Replace level transducer", "CM", 14),
        ("Calibrate level sensors", "CM", 10),
        ("Antenna alignment - weak signal", "CM", 8),
        ("PLC battery replacement", "PVM", 8),
        ("Radio communication failure", "BRKD", 12),
        ("Monthly SCADA polling check", "PDM", 6),
    ],
    "(Blank)": [
        ("Generator PM service", "PVM", 14),
        ("Load bank test generator", "PDM", 10),
        ("Transfer switch inspection", "PVM", 8),
        ("Generator failed weekly exercise", "BRKD", 10),
        ("Refuel portable generator", "CM", 6),
    ],
    "WET WELL": [
        ("Vac truck wet well cleaning", "PVM", 16),
        ("Clean and degrease wet well", "PVM", 12),
        ("Replace float switch", "CM", 10),
        ("Wet well level float hung up", "BRKD", 10),
        ("Remove debris from wet well", "CM", 8),
    ],
    "FORCE MAIN": [
        ("Force main inspection", "PVM", 10),
        ("Possible force main leak", "BRKD", 8),
        ("Locate force main for contractor", "NP", 8),
        ("Force main pressure test", "CM", 6),
    ],
    "GROUNDS": [
        ("Grounds maintenance", "PVM", 12),
        ("Mow and trim site", "PVM", 10),
        ("Remove trash and debris from site", "CM", 8),
        ("Wash down driveway and pad", "PVM", 4),
    ],
    "FENCE": [
        ("Repair fence", "CM", 10),
        ("Replace gate lock", "CM", 8),
        ("Fence damaged - secure site", "BRKD", 6),
    ],
    "MCC/SWITCHGEAR": [
        ("MCC bucket replacement", "ELEC", 8),
        ("Annual switchgear PM", "PVM", 8),
        ("Replace motor starter", "ELEC", 8),
        ("Thermal scan of MCC", "PDM", 6),
    ],
    "DRY PIT AREA": [
        ("Dry pit sump pump repair", "CM", 8),
        ("Dry pit ventilation issue", "CM", 6),
        ("Water accumulating in dry pit", "BRKD", 6),
    ],
    "PIPING": [
        ("Replace check valve", "CM", 8),
        ("Valve exercise PM", "PVM", 8),
        ("Discharge piping leak", "BRKD", 6),
    ],
    "FORCE MAIN AREA": [
        ("Force main easement mowing", "PVM", 8),
        ("Erosion at force main crossing", "CM", 6),
        ("ARV site maintenance", "PVM", 6),
    ],
    "FORCE MAIN ARV": [
        ("Replace air release valve", "CM", 8),
        ("ARV blowing water", "BRKD", 6),
        ("ARV inspection", "PVM", 6),
    ],
    "HVAC EQUIPMENT": [
        ("Exhaust fan not working", "CM", 8),
        ("Replace ventilation fan belt", "PVM", 6),
    ],
    "ODOR CONTROL UNIT": [
        ("Odor control media replacement", "PVM", 8),
        ("Odor complaint - inspect unit", "CM", 8),
    ],
}


def month_volume(year, month):
    """Seasonal work-order volume: wet-season (May-Jul) and freeze (Jan) bumps."""
    seasonal = 1.0
    if month in (5, 6, 7):
        seasonal += 0.30
    elif month in (8, 9):
        seasonal += 0.12
    elif month == 1:
        seasonal += 0.15
    noise = rng.uniform(0.88, 1.12)
    return max(1, round(BASE_PER_MONTH * seasonal * noise))


def pick_pump(n_pumps):
    """Pump numbers weighted low: pumps 1-2 carry most duty."""
    weights = [42, 38, 12, 5, 2, 0.7, 0.3][:n_pumps]
    return rng.choices(range(1, n_pumps + 1), weights=weights)[0]


def build_row(day, fac, today):
    cls = rng.choices(CLASS_NAMES, weights=CLASS_WEIGHTS)[0]

    if cls == "LIFT PUMP":
        pump = pick_pump(fac["n_pumps"])
        cls = f"LIFT PUMP {pump:02d}"
        suffix = f"LFTPMP{pump:02d}"
        obj_desc = (f"DRY WEATHER LIFT PUMP {pump:02d}"
                    if rng.random() < 0.15 else f"LIFT PUMP {pump:02d}")
        pool = DESC_POOLS["LIFT PUMP"]
        tau = CLASS_TAU["LIFT PUMP"]
    elif cls == "LIFT STATION FACILITY":
        suffix = "LFTSTN" if rng.random() < 0.6 else "FAC"
        obj_desc = ("LIFT STATION BUILDING"
                    if rng.random() < 0.1 else "LIFT STATION FACILITY")
        pool = DESC_POOLS[cls]
        tau = CLASS_TAU[cls]
        pump = None
    elif cls == "(Blank)":
        suffix = CLASS_SUFFIX[cls]
        obj_desc = f"GENERATOR (FIXED) ASSET ID# {rng.randint(100000, 199999)}"
        pool = DESC_POOLS[cls]
        tau = CLASS_TAU[cls]
        pump = None
    elif cls == "WET WELL":
        suffix = CLASS_SUFFIX[cls]
        obj_desc = "WETWELL" if rng.random() < 0.7 else "WET WELL"
        pool = DESC_POOLS[cls]
        tau = CLASS_TAU[cls]
        pump = None
    else:
        suffix = CLASS_SUFFIX[cls]
        obj_desc = cls
        pool = DESC_POOLS[cls]
        tau = CLASS_TAU[cls]
        pump = None

    text, jobtype, _ = rng.choices(pool, weights=[p[2] for p in pool])[0]
    if "{n}" in text:
        text = text.replace("{n}", str(pump if pump else pick_pump(fac["n_pumps"])))
    if "{ft}" in text:
        text = text.replace("{ft}", str(rng.randint(8, 16)))

    # ~7% of job types were never coded in the source system
    if rng.random() < 0.07:
        jobtype = None

    # open probability decays with age; telemetry alarms close fastest
    age = (today - day).days
    p_open = 0.88 * math.exp(-age / tau) + 0.008
    status = "Open" if rng.random() < p_open else "Closed"

    sched_end = day
    if rng.random() > 0.85:
        sched_end = day + timedelta(days=rng.randint(1, 21))

    return {
        "WO": None,  # assigned after date sort
        "desc": text,
        "created": day.isoformat(),
        "sched_end": sched_end.isoformat(),
        "jobtype": jobtype,
        "status": status,
        "loc_id": fac["loc_id"],
        "facility": fac["facility"],
        "obj_code": f"{fac['loc_id']}14{suffix}",
        "obj_desc": obj_desc,
        "cls": cls,
    }


def main():
    today = date.today()
    facilities = make_facilities()
    fac_weights = [f["weight"] for f in facilities]

    # walk months backwards from the run date
    rows = []
    month_starts = []
    y, m = today.year, today.month
    for _ in range(N_MONTHS):
        month_starts.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12

    for (yy, mm) in month_starts:
        first = date(yy, mm, 1)
        last = (date(yy + (mm == 12), (mm % 12) + 1, 1) - timedelta(days=1))
        if last > today:
            last = today
        n_days = (last - first).days + 1
        n = month_volume(yy, mm)
        if (yy, mm) == (today.year, today.month):
            n = round(n * n_days / 30)  # partial current month
        for _ in range(n):
            day = first + timedelta(days=rng.randrange(n_days))
            fac = rng.choices(facilities, weights=fac_weights)[0]
            rows.append(build_row(day, fac, today))

    rows.sort(key=lambda r: r["created"])
    wo = 1_900_000 + rng.randint(0, 5000)
    for r in rows:
        wo += rng.randint(1, 28)
        r["WO"] = str(wo)

    payload = json.dumps(rows, separators=(",", ":"))
    with open(OUT_FILE, "w") as f:
        f.write("// SYNTHETIC SAMPLE DATA - generated by "
                "generate_sample_data.py. No real records.\n")
        f.write(f"window.WO_ROWS={payload};\n")

    n_open = sum(1 for r in rows if r["status"] == "Open")
    print(f"Wrote {OUT_FILE}: {len(rows)} rows "
          f"({n_open} open), {len(facilities)} facilities, "
          f"{rows[0]['created']} .. {rows[-1]['created']}")


if __name__ == "__main__":
    main()
