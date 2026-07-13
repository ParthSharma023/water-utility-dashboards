#!/usr/bin/env python3
"""Generates synthetic sample data for this dashboard. All data is fabricated.

Produces data.js containing the five datasets the dashboard pages consume:

  window.DATA_SSO         - event-level SSO records (SSO Analysis page)
  window.DATA_SSO_MONTHLY - event-level records incl. private systems (Monthly Report page)
  window.DATA_GIS         - repeat-SSO location records (RSSO Analysis / Full GIS Data pages)
  window.DATA_SSOTIMELINE - lightweight event timeline (RSSO Analysis page)
  window.DATA_RSSO_TREND  - repeat-SSO summary rows (RSSO Trend page)

Every record is generated from seeded pseudo-random draws: IDs, basins,
addresses, and coordinates are fabricated and correspond to no real asset,
premise, or incident. Distributions are shaped (seasonality, multi-year trend,
cause mix, storm-month spikes) so the charts look like plausible operational
data rather than uniform noise.

Usage:  python3 generate_sample_data.py     (writes ./data.js)
"""

import json
import random
from datetime import date, timedelta

random.seed(20240831)

# ── Row counts (kept modest so data.js stays small) ──────────────────────────
N_SSO = 900           # DATA_SSO
N_MONTHLY = 1000      # DATA_SSO_MONTHLY
N_GIS = 400           # DATA_GIS
N_TIMELINE = 1050     # DATA_SSOTIMELINE
N_RSSO_TREND = 280    # DATA_RSSO_TREND

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# ── Synthetic identifier building blocks ─────────────────────────────────────
BASIN_PREFIXES = ["AK", "BX", "CV", "DK", "EZ", "FQ", "GX", "HV", "JM", "KX",
                  "LP", "MZ", "NQ", "PV", "QT", "RX", "SV", "TZ", "UB", "VN"]

STREET_NAMES = [
    "PECAN HOLLOW", "MAPLE RIDGE", "CINNABAR", "WILLOW CREST", "STONE HARBOR",
    "JUNIPER GLEN", "COPPERFIELD", "BLUE HERON", "SADDLEBROOK", "FOX MEADOW",
    "TIMBER GROVE", "LARKSPUR", "GRANITE FALLS", "SUNFLOWER", "CEDAR BEND",
    "MOSSY GATE", "RIVER BIRCH", "QUAIL RUN", "HAWTHORNE PARK", "IVY TRAIL",
    "BAYBERRY", "WINDING BROOK", "SILVER ELM", "CANDLEWOOD", "HERONWOOD",
    "TALL PINES", "DEER SPRING", "LANTERN HILL", "MARIGOLD", "OTTER POINT",
]
STREET_SUFFIXES = ["ST", "DR", "LN", "RD", "CT", "BLVD", "TRL", "WAY"]

# Treatment-plant service areas (public infrastructure names)
WWTPS = ["69th Street", "Sims Bayou", "Southwest", "Almeda Sims",
         "Keegans Bayou", "Northwest", "West District", "Beltway",
         "Greenridge", "Northeast"]
WWTP_WEIGHTS = [22, 17, 13, 10, 8, 8, 7, 6, 5, 4]

# Consent-decree program zones (synthetic labels)
CD_BASINS = ["Y1-East", "Y1-West", "Y2-East", "Y2-West", "Y3-Central",
             "Y4-North", "Y4-South", "Y5-Batch1", "Non-CD Area"]
CD_WEIGHTS = [22, 16, 15, 12, 12, 9, 7, 5, 2]

# ── Cause taxonomy: raw cause -> (category, weight) ──────────────────────────
PUBLIC_CAUSES = [
    ("Collection system grease blockage",     "Grease Blockage", 34),
    ("Grease Blockage",                       "Grease Blockage", 18),
    ("Collection system temporary blockage",  "Other Blockage",  12),
    ("Rags/Wipes",                            "Rags/Wipes",      10),
    ("Collection system structural blockage", "Structural",       6),
    ("Collection system structural failure",  "Structural",       4),
    ("Collection system - wet weather",       "Wet Weather",      5),
    ("Power Outage",                          "Lift Station",     2),
    ("Pump/lift station electrical failure",  "Lift Station",     1.2),
    ("Pump/lift station mechanical failure",  "Lift Station",     0.8),
    ("Roots",                                 "Roots",            1.5),
    ("ARV failure on force main",             "ARV Failure-FM",   0.4),
    ("WWTP influent pump station issue",      "WWTP",             0.2),
]
PRIVATE_CAUSES = [
    ("Service Lateral Temporary Blockage",  "Private", 6),
    ("Service Lateral Grease Blockage",     "Private", 4),
    ("Service Lateral Structural Blockage", "Private", 2),
]

# ── Temporal shaping ─────────────────────────────────────────────────────────
# Month-of-year weights (wet spring/fall, holiday-grease winter bump)
SEASON = [1.05, 0.85, 0.90, 1.00, 1.15, 1.10, 0.95, 0.90, 1.15, 1.05, 1.00, 1.10]
# Multi-year trend: rising through 2022, then declining as rehab work lands
YEAR_TREND = {2020: 1.00, 2021: 1.08, 2022: 1.12, 2023: 0.98,
              2024: 0.90, 2025: 0.84, 2026: 0.80}
# Storm months: wet-weather SSOs spike hard in these periods
STORM_MONTHS = {(2021, 2): 5.0, (2022, 8): 3.5, (2023, 5): 3.0,
                (2024, 5): 4.0, (2025, 6): 3.5}


def month_range(start_y, start_m, end_y, end_m):
    out = []
    y, m = start_y, start_m
    while (y, m) <= (end_y, end_m):
        out.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def pick_month(months, category=None):
    """Weighted month pick with seasonality, trend, and storm spikes."""
    weights = []
    for (y, m) in months:
        w = SEASON[m - 1] * YEAR_TREND.get(y, 0.8)
        if category == "Wet Weather":
            w *= STORM_MONTHS.get((y, m), 0.35)
        elif category == "Grease Blockage" and m in (11, 12, 1):
            w *= 1.35
        weights.append(w)
    return random.choices(months, weights=weights)[0]


def day_in_month(y, m):
    last = (date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)).day
    return date(y, m, random.randint(1, last))


def iso(d):
    return d.isoformat()


def mdy(d):
    return f"{d.month}/{d.day}/{d.year}"


def year_month(d):
    return f"{d.year}-{MONTHS[d.month - 1]}"


def make_basin():
    return random.choice(BASIN_PREFIXES) + f"{random.randint(1, 340):03d}"


def make_manhole(basin=None):
    return (basin or make_basin()) + f"{random.randint(1, 199):03d}"


def make_address():
    return (f"{random.randint(100, 15999)} "
            f"{random.choice(STREET_NAMES)} {random.choice(STREET_SUFFIXES)}")


# Coordinate clusters inside a generic metro bounding box (no real premises)
CLUSTERS = [(random.uniform(29.62, 30.00), random.uniform(-95.60, -95.15))
            for _ in range(9)]


def make_latlon():
    if random.random() < 0.7:
        clat, clon = random.choice(CLUSTERS)
        return (round(random.gauss(clat, 0.035), 6),
                round(random.gauss(clon, 0.045), 6))
    return (round(random.uniform(29.58, 30.05), 6),
            round(random.uniform(-95.65, -95.10), 6))


def weighted(pairs):
    """pairs: list of (value..., weight) tuples; returns tuple minus weight."""
    vals = [p[:-1] for p in pairs]
    wts = [p[-1] for p in pairs]
    v = random.choices(vals, weights=wts)[0]
    return v if len(v) > 1 else v[0]


def pick_cause(pool):
    cause, cat = weighted(pool)
    return cause, cat


# Structure types: (name, strType, weight)
PUBLIC_STRUCTS = [
    ("Manhole",        "Main",    42),
    ("City Cleanout",  "Lateral", 26),
    ("Private Cleanout", "Lateral", 12),
    ("Service Lateral", "Lateral",  7),
    ("Gravity Main",   "Main",     2.5),
    ("Force Main",     "Main",     1.2),
    ("Private Sample Well", "Lateral", 0.7),
    ("Lift Station",   "Main",     0.4),
    ("Building Backup", "Lateral", 0.2),
]


# ═════════════════════════════════════════════════════════════════════════════
# DATA_SSO - event-level records for the SSO Analysis page
# ═════════════════════════════════════════════════════════════════════════════
def gen_data_sso():
    months = month_range(2020, 1, 2026, 6)
    cat_weights = [
        ("Grease Blockage", 48), ("Structural", 24), ("Rags/Wipes", 18),
        ("Other Blockage", 3.5), ("Wet Weather", 2.5), ("Lift Station", 2),
        ("Roots", 0.8), ("ARV Failure-FM", 0.5), ("Private", 0.4), ("WWTP", 0.3),
    ]
    rows = []
    for _ in range(N_SSO):
        cat = weighted([(c, w) for c, w in cat_weights])
        y, m = pick_month(months, cat)
        d = day_in_month(y, m)
        struct, str_type = weighted(PUBLIC_STRUCTS)
        rows.append({
            "startDate": iso(d),
            "year": str(y),
            "yearMonth": year_month(d),
            "excursionCategory": cat,
            "basin": make_basin() if random.random() > 0.04 else None,
            "cdBasin": weighted([(b, w) for b, w in zip(CD_BASINS, CD_WEIGHTS)]),
            "strType": str_type,
            "structureType": struct,
        })
    rows.sort(key=lambda r: r["startDate"])
    chiclet = [
        {"label": "Grease Blockage", "short": "Grease"},
        {"label": "Other Blockage", "short": "Blockage"},
        {"label": "Roots", "short": "Roots"},
        {"label": "Wet Weather", "short": "W-Weather"},
        {"label": "Structural", "short": "Structural"},
        {"label": "Rags/Wipes", "short": "Rag/Wipes"},
        {"label": "ARV Failure", "short": "ARV Failure"},
        {"label": "Lift Station", "short": "Lift Station"},
        {"label": "Private", "short": "Private"},
    ]
    return {"rows": rows, "chiclet": chiclet}


# ═════════════════════════════════════════════════════════════════════════════
# DATA_SSO_MONTHLY - event-level records incl. private systems
# ═════════════════════════════════════════════════════════════════════════════
def gen_data_monthly():
    months = month_range(2020, 7, 2026, 6)
    systems = [("Public", 38), ("Public System", 20),
               ("Private", 26), ("Private System", 16)]
    rows = []
    for i in range(N_MONTHLY):
        system = weighted(systems)
        is_private = system.startswith("Private")
        if is_private:
            cause, cat = pick_cause(PRIVATE_CAUSES)
            struct, str_type = weighted([
                ("Private Cleanout", "Lateral", 80),
                ("Service Lateral", "Lateral", 12),
                ("Private Sample Well", "Lateral", 4),
                ("Private Grease Trap", "Lateral", 2),
                ("Building Backup", "Lateral", 2),
            ])
        else:
            cause, cat = pick_cause(PUBLIC_CAUSES)
            struct, str_type = weighted(PUBLIC_STRUCTS)
        y, m = pick_month(months, cat if cat != "Private" else None)
        d = day_in_month(y, m)
        basin = make_basin() if random.random() > 0.05 else None
        has_mh = (not is_private) and struct in ("Manhole", "City Cleanout") \
            and random.random() < 0.85
        has_geo = random.random() < (0.7 if not is_private else 0.4)
        lat, lon = make_latlon() if has_geo else (None, None)
        rows.append({
            "startDate": iso(d),
            "yearMonth": year_month(d),
            "system": system,
            "excursionCause": cause,
            "excursionCategory": cat,
            "basin": basin,
            "strType": str_type,
            "structureType": struct,
            "manhole": make_manhole(basin) if has_mh else None,
            "address": make_address(),
            "incidentId": str(100000 + i * 7 + random.randint(0, 6)),
            "killFish": random.random() < 0.015,
            "mediaNotif": random.random() < 0.03,
            "lat": lat,
            "lon": lon,
        })
    rows.sort(key=lambda r: r["startDate"])
    return {"rows": rows}


# ═════════════════════════════════════════════════════════════════════════════
# DATA_GIS - repeat-SSO location records
# ═════════════════════════════════════════════════════════════════════════════
def gen_data_gis():
    months = month_range(2021, 1, 2025, 12)
    count_dist = [(1, 40), (2, 30), (3, 14), (4, 8), (5, 4),
                  (6, 2), (7, 1), (8, 0.6), (9, 0.4)]
    root_causes = ["Grease", "Rags/wipes", "Roots", "Structural defect", "Debris"]
    actions = ["PM", "CTV", "Point Repair", "Heavy Cleaning", "SSES Study"]
    comments = ["In Progress", "Complete", "Scheduled", "Pending Review"]
    rows = []
    for i in range(N_GIS):
        count = weighted(count_dist)
        cause, cat = pick_cause(PUBLIC_CAUSES)
        y, m = pick_month(months, cat)
        latest = day_in_month(y, m)
        # earlier SSO dates fall in the 2-year window before the latest one
        history = sorted(latest - timedelta(days=random.randint(30, 720))
                         for _ in range(count - 1))
        dates = history + [latest]
        first = dates[0]
        basin = make_basin()
        struct, _ = weighted([("Manhole", "Main", 97), ("Cleanout", "Lateral", 1.2),
                              ("Gravity Main", "Main", 1.0), ("Force Main", "Main", 0.5),
                              ("Lift Station", "Main", 0.3)])
        has_geo = random.random() < 0.75
        lat, lon = make_latlon() if has_geo else (None, None)
        has_contract = count >= 3 and random.random() < 0.7
        rows.append({
            "lat": lat,
            "lon": lon,
            "incidentId": str(300000 + i * 11 + random.randint(0, 10)),
            "basin": basin,
            "manhole": make_manhole(basin),
            "wwtp": weighted([(w, wt) for w, wt in zip(WWTPS, WWTP_WEIGHTS)]),
            "address": make_address(),
            "fullAddress": None,  # filled below from address
            "system": weighted([("Public", 55), ("Public System", 45)]),
            "structureType": struct,
            "excursionCause": cause,
            "excursionCategory": cat,
            "startDate": iso(latest),
            "endDate": iso(latest + timedelta(days=random.choice([0, 0, 1])))
                       if random.random() < 0.75 else None,
            "countSSOLast2Years": count,
            "totalVolLost2Years": int(10 ** random.uniform(2.0, 4.7))
                                  if random.random() < 0.75 else None,
            "isWetWeather": "YES" if cat == "Wet Weather" else "NO",
            "firstSSODate": iso(first),
            "listSSODates": " ; ".join(mdy(d) for d in dates),
            "pmDNS": str(random.randint(6, 52)) if random.random() < 0.35 else None,
            "pmUPS": str(random.randint(6, 52)) if random.random() < 0.35 else None,
            "contractStatus": random.choice(["Y", "N"]) if has_contract else None,
            "correctiveAction": random.choice(actions)
                                if count >= 2 and random.random() < 0.5 else None,
            "workIssuedDate": iso(latest + timedelta(days=random.randint(20, 200)))
                              if has_contract and random.random() < 0.4 else None,
            "contractNumber": (f"5{random.randint(10000, 99999)}-0{random.randint(1, 3)}"
                               if random.random() < 0.8 else "Pending")
                              if has_contract else None,
            "comments": random.choice(comments)
                        if has_contract and random.random() < 0.8 else None,
            "latestSSODate": iso(latest),
            "rootCause": random.choice(root_causes)
                         if count >= 2 and random.random() < 0.6 else None,
            "ctvList": random.choice(["FY21", "FY22", "FY23", "FY21, FY22"])
                       if random.random() < 0.25 else None,
            "isIn2YearsFrame": "True",
        })
    for r in rows:
        r["fullAddress"] = r["address"] + ", TX"
    rows.sort(key=lambda r: r["startDate"])
    return {"rows": rows}


# ═════════════════════════════════════════════════════════════════════════════
# DATA_SSOTIMELINE - lightweight event timeline
# ═════════════════════════════════════════════════════════════════════════════
def gen_data_timeline():
    months = month_range(2021, 1, 2025, 12)
    systems = [("Public", 45), ("Public System", 15),
               ("Private", 25), ("Private System", 15)]
    rows = []
    for _ in range(N_TIMELINE):
        system = weighted(systems)
        pool = PRIVATE_CAUSES if system.startswith("Private") else PUBLIC_CAUSES
        cause, cat = pick_cause(pool)
        y, m = pick_month(months, cat if cat != "Private" else None)
        d = day_in_month(y, m)
        rows.append({
            "startDate": iso(d),
            "period": year_month(d),
            "system": system,
            "cause": cause,
            "manhole": make_manhole() if random.random() < 0.4 else None,
        })
    rows.sort(key=lambda r: r["startDate"])
    return {"rows": rows}


# ═════════════════════════════════════════════════════════════════════════════
# DATA_RSSO_TREND - repeat-SSO summary rows
# ═════════════════════════════════════════════════════════════════════════════
def gen_data_rsso_trend():
    months = month_range(2021, 1, 2025, 6)
    causes = [("Grease Blockage", 60), ("Wet Weather", 13), ("Structural", 8),
              ("Rags/Wipes", 6), ("Power Outage", 4), ("Temporary Blockage", 4),
              ("Lift Station", 3), ("Roots", 2)]
    count_dist = [(2, 58), (3, 20), (4, 8), (5, 5), (6, 3),
                  (7, 2), (8, 2), (9, 1), (10, 1)]
    rows = []
    for _ in range(N_RSSO_TREND):
        cause = weighted(causes)
        count = weighted(count_dist)
        y, m = pick_month(months, cause if cause == "Wet Weather" else None)
        last = day_in_month(y, m)
        history = sorted(last - timedelta(days=random.randint(30, 720))
                         for _ in range(count - 1))
        dates = history + [last]
        basin = make_basin()
        rows.append({
            "manhole": make_manhole(basin),
            "address": make_address(),
            "basin": basin,
            "wwtp": weighted([(w.upper(), wt)
                              for w, wt in zip(WWTPS, WWTP_WEIGHTS)]),
            "startDate": iso(last),
            "excursionCause": cause,
            "firstSSODate": iso(dates[0]),
            "lastSSODate": iso(last),
            "ssoCount": count,
            "ssoStartDateList": " ; ".join(mdy(d) for d in dates),
        })
    rows.sort(key=lambda r: r["startDate"])
    return {"rows": rows}


# ═════════════════════════════════════════════════════════════════════════════
def main():
    datasets = {
        "DATA_RSSO_TREND": gen_data_rsso_trend(),
        "DATA_GIS": gen_data_gis(),
        "DATA_SSOTIMELINE": gen_data_timeline(),
        "DATA_SSO": gen_data_sso(),
        "DATA_SSO_MONTHLY": gen_data_monthly(),
    }
    parts = ["// SYNTHETIC SAMPLE DATA - generated by generate_sample_data.py. "
             "No real records.\n"]
    for name, payload in datasets.items():
        blob = json.dumps(payload, separators=(",", ":"))
        parts.append(f"window.{name} = {blob};\n")
    out = "".join(parts)
    with open("data.js", "w") as f:
        f.write(out)
    for name, payload in datasets.items():
        print(f"{name}: {len(payload['rows'])} rows")
    print(f"data.js written ({len(out) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
