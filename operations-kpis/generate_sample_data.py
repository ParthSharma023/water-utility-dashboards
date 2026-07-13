#!/usr/bin/env python3
"""Generates synthetic sample data for this dashboard. All data is fabricated.

Produces data.js with four datasets consumed by the dashboard pages:

  window.DATA_REFRESH  - refresh stamp (not rendered, kept for schema parity)
  window.DATA_SSO      - sanitary sewer overflow (SSO) incidents + monthly rollup
  window.DATA_SEWER    - monthly CCTV sewer-main inspection progress vs. target
  window.DATA_LEAK     - water leak repair work orders + monthly rollup

Every record is generated from seeded random distributions: incident IDs,
service request numbers, street names/numbers, plant codes, manhole numbers
and timestamps are all invented. Distributions are shaped (seasonality,
improving compliance trends, long-tailed durations) so the charts look like
real operational data, but no row corresponds to a real event or place.

Usage: python3 generate_sample_data.py   (writes ./data.js)
"""

import json
import math
import random
from datetime import datetime, timedelta

random.seed(42)

OUT_FILE = "data.js"

# ──────────────────────────────────────────────────────────────────────────────
# Shared synthetic vocabularies (all invented)
# ──────────────────────────────────────────────────────────────────────────────

STREET_NAMES = [
    "AMBERFIELD", "BARLEY CREEK", "BLUFFSTONE", "BRIARHOLLOW", "CANDLE PINES",
    "CEDARMONT", "CLEARBROOK", "COPPER RIDGE", "CRESTHAVEN", "DEERPATH",
    "DRIFTWOOD GLEN", "EASTMERE", "ELMRIDGE", "FALLOW GROVE", "FERNGATE",
    "FOXBORO", "GLENSHIRE", "GRAYHAWK", "HARVEST BEND", "HAZELCROFT",
    "HERONWOOD", "HICKORY PLAINS", "INDIGO SPRINGS", "IRONGATE", "JADE MEADOW",
    "JUNIPER HOLLOW", "KESTREL POINT", "KINGFISHER", "LARKSPUR VALE", "LIMESTONE",
    "MALLARD COVE", "MAPLE SUMMIT", "MEADOWLARK", "MILLBROOK", "MOSSY OAK",
    "NIGHTINGALE", "NORTHBRIDGE", "OAKHURST GLEN", "ORCHID TRACE", "PALEBROOK",
    "PECAN HOLLOW", "PINE TERRACE", "QUAIL RUN", "RAVENCREST", "REDBUD PARK",
    "RIVERBIRCH", "ROSEGATE", "SADDLEBROOK", "SAGE MEADOW", "SILVERLEAF",
    "SPRINGWATER", "STONEBRIAR", "SUNFLOWER RIDGE", "TANGLEWOOD PARK",
    "THISTLEDOWN", "TIMBER COVE", "VIOLET MARSH", "WESTFIELD GLEN",
    "WILLOWMERE", "WINDCHIME", "WREN HOLLOW", "YELLOWSTONE PARK",
]
SUFFIXES = ["ST", "DR", "RD", "LN", "CT", "BLVD", "WAY", "TRL"]
PREDIRS = [None] * 92 + ["N", "S", "E", "W"] * 2
AREAS = ["NE", "NW", "SE", "SW", "CENTRAL"]
AREA_WEIGHTS = [0.24, 0.18, 0.28, 0.22, 0.08]
CITY = "FAIRVIEW"  # fictional

# Synthetic collection-basin / plant codes, e.g. "BC012"
PLANT_PREFIXES = ["BC", "RV", "LK", "MW", "HC", "PT", "GB", "WF"]
PLANT_CODES = [
    f"{random.choice(PLANT_PREFIXES)}{random.randint(1, 180):03d}" for _ in range(40)
]

SSO_CAUSES = [
    ("Rags/Wipes", 0.40),
    ("Grease Blockage", 0.30),
    ("Collection system structural failure", 0.09),
    ("Collection system structural blockage", 0.07),
    ("Collection system temporary blockage", 0.06),
    ("Roots", 0.02),
    ("Collection system - wet weather", 0.02),
    ("Power Outage", 0.01),
    ("Pump/Lift Station Mechanical Failure", 0.01),
    (None, 0.02),
]

BLOCKAGE_PRIVATE = ["Private Lateral", "Private Lateral", "Private Lateral", "Community Line"]
BLOCKAGE_PUBLIC = ["Gravity Main", "Gravity Main", "City Service Lead", "Lift Station", "Force Main"]

DISTRICTS = [None] * 28 + list("DIBCEGKH") * 8 + list("AFJ") * 3
PRIORITIES = [None] * 63 + ["High"] * 34 + ["MediumHigh"] * 2 + ["Medium"] * 1


def weighted_choice(pairs):
    r = random.random()
    acc = 0.0
    for value, w in pairs:
        acc += w
        if r <= acc:
            return value
    return pairs[-1][0]


def month_range(start, end):
    """First-of-month datetimes from start to end inclusive."""
    months = []
    d = datetime(start.year, start.month, 1)
    while d <= end:
        months.append(d)
        d = datetime(d.year + (d.month // 12), (d.month % 12) + 1, 1)
    return months


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def daytime_dt(month_start, days_in_month):
    """Random timestamp inside the month, biased toward working hours."""
    day = random.randint(0, days_in_month - 1)
    hour = min(23, max(0, int(random.gauss(12, 4))))
    minute = random.randint(0, 59)
    return month_start + timedelta(days=day, hours=hour, minutes=minute)


def days_in_month(d):
    nxt = datetime(d.year + (d.month // 12), (d.month % 12) + 1, 1)
    return (nxt - d).days


# ──────────────────────────────────────────────────────────────────────────────
# 1) SSO incidents  (DATA_SSO.rows + DATA_SSO.byMonth)
# ──────────────────────────────────────────────────────────────────────────────

SSO_START = datetime(2024, 7, 1)
SSO_END = datetime(2026, 6, 1)  # last generated month


def sso_within48_prob(month):
    """Compliance trend: high-80s in early 2024 rising to ~97% by 2026."""
    t = (month.year - 2024) * 12 + (month.month - 1)  # 0 .. 29
    base = 0.84 + 0.145 * (1 - math.exp(-t / 11.0))  # 0.84 → ~0.975
    wobble = 0.02 * math.sin(t * 1.7) + random.uniform(-0.015, 0.015)
    dip = -0.05 if (month.year, month.month) in [(2024, 5), (2025, 1), (2026, 1)] else 0.0
    return min(0.995, max(0.70, base + wobble + dip))


def sso_monthly_count(month):
    """Volume with summer seasonality and mild wet-season bumps."""
    seasonal = 1.0 + 0.25 * math.sin((month.month - 4) / 12.0 * 2 * math.pi)
    base = 36 * seasonal
    if month.month in (5, 6):  # storm season bump
        base *= 1.15
    return max(28, int(random.gauss(base, 6)))


def gen_sso():
    rows = []
    inckey = 41000
    sr_nbr = 91000000
    for month in month_range(SSO_START, SSO_END):
        dim = days_in_month(month)
        n = sso_monthly_count(month)
        if month == SSO_END:  # partial final month
            n = int(n * 0.45)
        p48 = sso_within48_prob(month)
        for _ in range(n):
            inckey += random.randint(1, 3)
            sr_nbr += random.randint(2, 40)

            is_public = random.random() < 0.40
            prob = "Public" if is_public else "Private"
            reviewed = random.random() < (0.96 if is_public else 0.42)
            has_sr = random.random() < 0.97

            incident = daytime_dt(month, dim)
            sr_init = incident - timedelta(hours=random.uniform(0.3, 8.0)) if has_sr else None

            cause = weighted_choice(SSO_CAUSES)
            area = random.choices(AREAS, weights=AREA_WEIGHTS)[0]
            sso_type = random.choices(["Non-Observed", "Active", None], weights=[0.72, 0.22, 0.06])[0]

            if reviewed:
                # Slightly lower compliance for private laterals
                p = p48 if is_public else max(0.55, p48 - 0.06)
                within = random.random() < p
                if within:
                    hours = min(47.5, max(0.2, random.lognormvariate(math.log(11), 0.95)))
                else:
                    hours = 48 + random.expovariate(1 / 26.0)
                    if random.random() < 0.03:
                        hours += random.uniform(150, 500)  # rare long-tail case
                hours = round(hours, 2)
                start_resp = sr_init if sr_init else incident
                sso_start = incident
                sso_end = start_resp + timedelta(hours=hours)
                blockage = random.choice(BLOCKAGE_PRIVATE if not is_public else BLOCKAGE_PUBLIC)
                gpm = round(random.uniform(0.5, 30), 1) if random.random() < 0.17 else 0.0
                volume = round(random.lognormvariate(math.log(750), 1.2), 1) if random.random() < 0.11 else 0.0
                row_hours = hours
                within48 = 1 if hours <= 48 else 0
            else:
                sso_start = None
                sso_end = None
                blockage = None
                gpm = None
                volume = 0.0
                row_hours = None
                within48 = 0

            rows.append({
                "INCKEY": inckey,
                "STAT": "CLOSED" if random.random() > 0.001 else "OPEN",
                "SSOTYPE": sso_type,
                "SSOTYPE1": sso_type,
                "AREA_DESCRIPT": area,
                "STNO": str(random.randint(100, 15999)),
                "PREDIR": random.choice(PREDIRS),
                "STNAME": random.choice(STREET_NAMES),
                "SUFFIX": random.choice(SUFFIXES),
                "CITY": CITY,
                "TREATMENTPLANT": random.choice(PLANT_CODES),
                "MANHOLENUMBER": (
                    f"{area[:2]}{random.randint(1, 399):03d}{random.randint(1, 99):03d}"
                    if random.random() < 0.18 else None
                ),
                "SSOTOTALVOLUME": volume,
                "GPM": gpm,
                "IncidentDatetime": iso(incident),
                "ServiceRqNbr": float(sr_nbr) if has_sr else None,
                "SRInitDateTime": iso(sr_init) if sr_init else None,
                "SSOStartDateTime": iso(sso_start) if sso_start else None,
                "SSOEndDateTime": iso(sso_end) if sso_end else None,
                "SSOProb": prob,
                "SSO_Cause": cause,
                "BLockageLocation": blockage,
                "ResponseHours": row_hours,
                "Within48": within48,
                "Within48Text": "Within 48 Hours" if within48 == 1 else "Over 48 Hours",
                "SSOReviewed": 1 if reviewed else 0,
                "SSO Review Status": "Reviewed" if reviewed else "Not Yet Reviewed",
                "SSO Associated with SR": "Yes" if has_sr else "No",
                "IncidentMonth": iso(datetime(month.year, month.month, 1)),
            })
    return rows


def sso_by_month(rows):
    """Monthly rollup over PUBLIC SSOs (matches what the overview chart plots)."""
    agg = {}
    for r in rows:
        if r["SSOProb"] != "Public":
            continue
        key = r["IncidentDatetime"][:7]
        a = agg.setdefault(key, {"total": 0, "resolved": 0, "w48": 0})
        a["total"] += 1
        if r["ResponseHours"] is not None:
            a["resolved"] += 1
            if r["Within48"] == 1:
                a["w48"] += 1
    out = []
    for key in sorted(agg):
        a = agg[key]
        out.append({
            "month": f"{key}-01",
            "SSO_Total": a["total"],
            "Resolved_Total": a["resolved"],
            "Within48_Count": a["w48"],
            "Pct_Within48": round(a["w48"] / a["resolved"], 4) if a["resolved"] else None,
        })
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 2) Sewer-main CCTV assessment  (DATA_SEWER.rows)
#    July-start fiscal years; cumulative resets each July.
#    Annual goal = 10% of a 5,200-mile system = 520 miles.
# ──────────────────────────────────────────────────────────────────────────────

ANNUAL_GOAL = 520.0


def gen_sewer():
    rows = []
    # FY2025 finishes ~5% over goal; FY2026 runs through April, tracking ahead.
    fy_specs = [
        (datetime(2024, 7, 1), 12, 1.05),   # complete fiscal year
        (datetime(2025, 7, 1), 10, 1.04),   # in-progress fiscal year
    ]
    for fy_start, months_with_data, finish_ratio in fy_specs:
        # Draw monthly weights, then scale so the FY lands near finish_ratio.
        weights = []
        for i in range(months_with_data):
            seasonal = 1.0 + 0.18 * math.sin((i - 2) / 12.0 * 2 * math.pi)
            weights.append(max(0.35, random.gauss(seasonal, 0.28)))
        expected_total = ANNUAL_GOAL * finish_ratio * (months_with_data / 12.0)
        scale = expected_total / sum(weights)

        cumulative = 0.0
        for i in range(12):
            month = month_range(fy_start, fy_start + timedelta(days=360))[i]
            target = round(ANNUAL_GOAL / 12 * (i + 1), 1)
            if i < months_with_data:
                monthly = round(weights[i] * scale, 1)
                cumulative = round(cumulative + monthly, 1)
                rows.append({
                    "Month": iso(month),
                    "Monthly Inspection": monthly,
                    "Cumulative Inspection": cumulative,
                    "Percent": round(cumulative / ANNUAL_GOAL, 3),
                    "Cumulative Target": target,
                    "Annual Goal": ANNUAL_GOAL,
                })
            else:
                # Future months: targets known, inspections not yet recorded.
                rows.append({
                    "Month": iso(month),
                    "Monthly Inspection": None,
                    "Cumulative Inspection": None,
                    "Percent": None,
                    "Cumulative Target": target,
                    "Annual Goal": ANNUAL_GOAL,
                })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# 3) Leak repair work orders  (DATA_LEAK.rows + DATA_LEAK.byMonth)
# ──────────────────────────────────────────────────────────────────────────────

LEAK_START = datetime(2023, 7, 1)
LEAK_END = datetime(2026, 6, 1)
LEAK_LAST_DAY = datetime(2026, 6, 10)


def leak_within7_prob(month):
    """Compliance trend: ~0.62 in 2023 (with a rough patch in late summer),
    climbing to ~0.93 by 2026."""
    t = (month.year - 2023) * 12 + (month.month - 1)  # 6 .. 41
    base = 0.60 + 0.33 * (1 - math.exp(-t / 16.0))
    if (month.year, month.month) in [(2023, 8), (2023, 9), (2023, 10)]:
        base -= 0.18  # summer backlog episode
    if (month.year, month.month) == (2024, 2):
        base -= 0.08  # freeze-event backlog
    return min(0.96, max(0.38, base + random.uniform(-0.03, 0.03)))


def leak_monthly_count(month):
    seasonal = 1.0 + 0.30 * math.sin((month.month - 5.5) / 12.0 * 2 * math.pi)
    base = 31 * seasonal
    if month.month in (8, 9):  # dry-soil season: mains shift, leaks spike
        base *= 1.35
    return max(20, int(random.gauss(base, 5)))


def gen_leak():
    rows = []
    wo = 2000000
    for month in month_range(LEAK_START, LEAK_END):
        dim = days_in_month(month)
        n = leak_monthly_count(month)
        if month == LEAK_END:
            n = int(n * 0.33)  # partial final month
        p7 = leak_within7_prob(month)
        for _ in range(n):
            wo += random.randint(3, 60)
            init = daytime_dt(month, dim)
            if month == LEAK_END:
                init = min(init, LEAK_LAST_DAY)

            if random.random() < p7:
                days = min(6.99, max(0.05, random.lognormvariate(math.log(3.0), 0.8)))
            else:
                days = 7 + random.lognormvariate(math.log(18), 0.9)
                days = min(days, 320)
            days = round(days, 3)
            completed = init + timedelta(days=days)

            # Recent WOs whose completion falls after the extract date stay open.
            if completed > LEAK_LAST_DAY + timedelta(days=3):
                completed_iso, days_val, within7 = None, None, 0
            else:
                completed_iso = iso(completed)
                days_val = days
                within7 = 1 if days <= 7 else 0

            rows.append({
                "actkey": wo,
                "initdttm": iso(init),
                "completed_date": completed_iso,
                "stno": str(random.randint(100, 15999)),
                "stname": random.choice(STREET_NAMES),
                "district": random.choice(DISTRICTS),
                "priority": random.choice(PRIORITIES),
                "prob": None,
                "res": None,
                "responsibility": "WRepair" if random.random() < 0.70 else "WRContract",
                "wotype": None,
                "DaysToComplete": days_val,
                "CompletedWithin7": within7,
                "InitMonth": iso(datetime(month.year, month.month, 1)),
            })
    return rows


def leak_by_month(rows):
    """Monthly rollup keyed on initiation month."""
    agg = {}
    for r in rows:
        key = r["initdttm"][:7]
        a = agg.setdefault(key, {"init": 0, "comp": 0, "w7": 0})
        a["init"] += 1
        if r["completed_date"] is not None:
            a["comp"] += 1
            if r["CompletedWithin7"] == 1:
                a["w7"] += 1
    out = []
    for key in sorted(agg):
        a = agg[key]
        out.append({
            "month": f"{key}-01",
            "Initiated": a["init"],
            "Completed": a["comp"],
            "CompletedWithin7": a["w7"],
            "Pct_Within7": round(a["w7"] / a["comp"], 4) if a["comp"] else None,
        })
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Emit data.js
# ──────────────────────────────────────────────────────────────────────────────

def dump_rows(rows):
    """One compact JSON object per line: small file, diff-friendly."""
    lines = ",\n".join("    " + json.dumps(r, separators=(",", ":")) for r in rows)
    return "[\n" + lines + "\n  ]"


def main():
    sso_rows = gen_sso()
    sewer_rows = gen_sewer()
    leak_rows = gen_leak()

    parts = [
        "// SYNTHETIC SAMPLE DATA - generated by generate_sample_data.py. No real records.\n",
        'window.DATA_REFRESH = {"date": "06/15/2026"};\n',
        "window.DATA_SSO = {\n  \"rows\": " + dump_rows(sso_rows)
        + ",\n  \"byMonth\": " + dump_rows(sso_by_month(sso_rows)) + "\n};\n",
        "window.DATA_SEWER = {\n  \"rows\": " + dump_rows(sewer_rows) + "\n};\n",
        "window.DATA_LEAK = {\n  \"rows\": " + dump_rows(leak_rows)
        + ",\n  \"byMonth\": " + dump_rows(leak_by_month(leak_rows)) + "\n};\n",
    ]
    with open(OUT_FILE, "w") as f:
        f.write("\n".join(parts))

    print(f"Wrote {OUT_FILE}:")
    print(f"  DATA_SSO.rows    = {len(sso_rows):>6,}")
    print(f"  DATA_SEWER.rows  = {len(sewer_rows):>6,}")
    print(f"  DATA_LEAK.rows   = {len(leak_rows):>6,}")


if __name__ == "__main__":
    main()
