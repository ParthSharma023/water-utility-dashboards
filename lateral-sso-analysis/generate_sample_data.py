#!/usr/bin/env python3
"""Generates synthetic sample data for this dashboard. All data is fabricated.

Produces data.js with the exact schema the dashboard pages consume:

  window.DATA = {
    ssoByMonth:        [...],  # monthly public/private lateral SSO counts + 12M moving avgs
    changeDetail:      [...],  # per-CD-year totals by system with year-over-year % change
    causeTrendByMonth: [...],  # monthly public SSO cause/location breakdown + 12M moving avgs
    causeTrendByYear:  [...],  # per-CD-year cause breakdown with percentages
    trackingByMonth:   [...],  # monthly SSO categories, blockage counts, inspection counts
  }

The reporting calendar ("Program Year") starts in April: Program Year 1 = Apr 2021 - Mar 2022.
All series are generated from a seeded RNG with trend + seasonality + noise so the
charts look plausible. No real records are used.

Usage: python3 generate_sample_data.py
"""

import json
import math
import random
from datetime import date
from pathlib import Path

SEED = 20210401
START = date(2021, 4, 1)   # first month of Program Year 1
N_MONTHS = 61              # Apr 2021 .. Apr 2026 inclusive

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

rng = random.Random(SEED)


# ── Calendar helpers ──────────────────────────────────────────────────────────

def month_at(i):
    """Return the first-of-month date for month index i (0 = START)."""
    y, m = divmod(START.year * 12 + (START.month - 1) + i, 12)
    return date(y, m + 1, 1)


def calendar_fields(i):
    d = month_at(i)
    prog_year_no = i // 12 + 1
    cd_month_no = i % 12 + 1
    return {
        "monthStart": d.isoformat(),
        "progYear": f"Program Year {prog_year_no}",
        "progYearNo": prog_year_no,
        "cdMonth": MONTH_NAMES[d.month - 1],
        "cdMonthNo": cd_month_no,
    }


def seasonal(i):
    """Seasonal multiplier: wet-season peaks in early summer and September."""
    m = month_at(i).month
    s = 1.0 + 0.14 * math.sin(2 * math.pi * (m - 3) / 12)
    if m in (5, 6, 9):
        s += 0.09
    return s


def moving_avg(series, window=12):
    """Trailing moving average; None until a full window is available."""
    out = []
    for i in range(len(series)):
        if i < window - 1:
            out.append(None)
        else:
            out.append(round(sum(series[i - window + 1:i + 1]) / window, 4))
    return out


# ── Core monthly series ───────────────────────────────────────────────────────
# Public counts ramp up mid-program (more detection/reporting) then ease off;
# private counts drift down early and rebound late.

def gen_core_series():
    public, private = [], []
    for i in range(N_MONTHS):
        pub_base = 38 + 52 * math.exp(-((i - 40) / 17) ** 2)
        pub = pub_base * seasonal(i) + rng.gauss(0, 6)
        public.append(max(8, round(pub)))

        priv_base = 196 - 0.95 * i + 0.021 * i * i
        priv = priv_base * seasonal(i) + rng.gauss(0, 13)
        private.append(max(60, round(priv)))
    return public, private


def build_sso_by_month(public, private):
    pub_ma = moving_avg(public)
    priv_ma = moving_avg(private)
    rows = []
    for i in range(N_MONTHS):
        cal = calendar_fields(i)
        rows.append({
            "progYear": cal["progYear"],
            "progYearNo": cal["progYearNo"],
            "cdMonth": cal["cdMonth"],
            "cdMonthNo": cal["cdMonthNo"],
            "monthStart": cal["monthStart"],
            "publicCount": public[i],
            "privateCount": private[i],
            "totalCount": public[i] + private[i],
            "publicMovingAvg": pub_ma[i],
            "privateMovingAvg": priv_ma[i],
        })
    return rows


def build_change_detail(public, private):
    years = {}
    for i in range(N_MONTHS):
        n = i // 12 + 1
        y = years.setdefault(n, {"pub": 0, "priv": 0, "months": 0})
        y["pub"] += public[i]
        y["priv"] += private[i]
        y["months"] += 1

    rows = []
    for n in sorted(years):
        cur = years[n]
        prev = years.get(n - 1)
        for system, count in (
            ("Combined", cur["pub"] + cur["priv"]),
            ("Private", cur["priv"]),
            ("Public", cur["pub"]),
        ):
            pct = None
            # % change only for complete years with a complete prior year
            if prev and prev["months"] == 12 and cur["months"] == 12:
                prev_count = {
                    "Combined": prev["pub"] + prev["priv"],
                    "Private": prev["priv"],
                    "Public": prev["pub"],
                }[system]
                if prev_count > 0:
                    pct = round((count - prev_count) / prev_count, 4)
            rows.append({
                "progYear": f"Program Year {n}",
                "progYearNo": n,
                "system": system,
                "lateralSSOCount": count,
                "pctChange": pct,
            })
    return rows


# ── Cause trend (public SSO with blockage) ────────────────────────────────────
# Invariant per month: gravityMain + cityServiceLead == structural + grease + others

def build_cause_trend(public):
    rows = []
    struct_series, grease_series = [], []
    for i in range(N_MONTHS):
        cal = calendar_fields(i)
        bt = max(4, public[i] - rng.randint(0, 4))  # blockage subset of public SSO

        grease_share = min(0.72, max(0.5, 0.62 - 0.0007 * i + rng.gauss(0, 0.03)))
        others_share = min(0.05, max(0.0, rng.gauss(0.022, 0.012)))
        grease = round(bt * grease_share)
        others = round(bt * others_share)
        struct = bt - grease - others
        if struct < 0:
            grease += struct
            struct = 0

        grav_share = min(0.38, max(0.12, 0.24 + rng.gauss(0, 0.045)))
        grav = round(bt * grav_share)
        city = bt - grav

        struct_series.append(struct)
        grease_series.append(grease)
        rows.append({
            "monthStart": cal["monthStart"],
            "progYear": cal["progYear"],
            "progYearNo": cal["progYearNo"],
            "cdMonth": cal["cdMonth"],
            "cdMonthNo": cal["cdMonthNo"],
            "gravityMainCount": grav,
            "cityServiceLeadCount": city,
            "structuralCount": struct,
            "greaseRagWipeCount": grease,
            "othersCount": others,
            "structuralMovingAvg": None,
            "greaseRagWipeMovingAvg": None,
        })

    struct_ma = moving_avg(struct_series)
    grease_ma = moving_avg(grease_series)
    for i, row in enumerate(rows):
        row["structuralMovingAvg"] = struct_ma[i]
        row["greaseRagWipeMovingAvg"] = grease_ma[i]
    return rows


def build_cause_trend_by_year(cause_rows):
    years = {}
    for r in cause_rows:
        y = years.setdefault(r["progYearNo"], {
            "bt": 0, "grav": 0, "grease": 0, "struct": 0, "others": 0,
        })
        y["bt"] += r["gravityMainCount"] + r["cityServiceLeadCount"]
        y["grav"] += r["gravityMainCount"]
        y["grease"] += r["greaseRagWipeCount"]
        y["struct"] += r["structuralCount"]
        y["others"] += r["othersCount"]

    rows = []
    for n in sorted(years):
        y = years[n]
        total = y["bt"]
        rows.append({
            "progYear": f"Program Year {n}",
            "progYearNo": n,
            "publicSSOCount": total,
            "gravityMainCount": y["grav"],
            "pctOfTotal": round(y["grav"] / total, 4) if total else None,
            "greaseRagWipeCount": y["grease"],
            "greaseRagWipePct": round(y["grease"] / total, 4) if total else None,
            "structuralCount": y["struct"],
            "structuralPct": round(y["struct"] / total, 4) if total else None,
            "othersCount": y["others"],
            "othersPct": round(y["others"] / total, 4) if total else None,
            "total": total,
        })
    return rows


# ── Tracking page (SSO categories, blockage SRs, inspections) ────────────────

def build_tracking(public, private):
    rows = []
    for i in range(N_MONTHS):
        cal = calendar_fields(i)
        total = public[i] + private[i]

        # Repeat-SSO share grows over the program as repeat sites are identified
        rsso_pub_share = min(0.30, max(0.02, 0.05 + 0.15 * i / 60 + rng.gauss(0, 0.02)))
        rsso_priv_share = min(0.45, max(0.03, 0.06 + 0.30 * i / 60 + rng.gauss(0, 0.03)))
        rsso_pub = round(public[i] * rsso_pub_share)
        rsso_priv = round(private[i] * rsso_priv_share)

        blockage_sr = max(350, round(390 + 1.25 * private[i] + rng.gauss(0, 42)))
        blockage_lat = round(total * rng.uniform(0.84, 0.94))
        blockage_main = round(total * rng.uniform(0.03, 0.09))

        # Inspection program mix shifts over time: jetting declines,
        # TV/CCTV ramp up as camera crews come online.
        insp = {
            "inspJet": max(450, round(1040 - 4.6 * i + rng.gauss(0, 62))),
            "inspTV": max(40, round(88 + 2.4 * i + rng.gauss(0, 18))),
            "inspTrace": max(30, round(74 + 0.55 * i + rng.gauss(0, 14))),
            "inspDye": max(15, round(52 + 0.55 * i + rng.gauss(0, 12))),
            "inspCCTV": max(0, round(7 + 1.05 * i + rng.gauss(0, 7))),
            "inspVacuum": rng.randint(0, 6) + i // 15,
            "inspSmoke": 1 if (i > 30 and rng.random() < 0.08) else 0,
        }
        # Inspections linked to an SSO event: a subset of all inspections
        insp_sso = {
            "inspSSO" + k[len("insp"):]: round(v * rng.uniform(0.55, 0.85))
            for k, v in insp.items()
        }

        row = {
            "monthStart": cal["monthStart"],
            "progYear": cal["progYear"],
            "progYearNo": cal["progYearNo"],
            "cdMonth": cal["cdMonth"],
            "cdMonthNo": cal["cdMonthNo"],
            "publicSSO": public[i] - rsso_pub,
            "rssoPublic": rsso_pub,
            "privateSSO": private[i] - rsso_priv,
            "rssoPrivate": rsso_priv,
            "blockageSRCount": blockage_sr,
            "blockageLatCount": blockage_lat,
            "blockageMainCount": blockage_main,
        }
        row.update(insp)
        row.update(insp_sso)
        rows.append(row)
    return rows


# ── Output ────────────────────────────────────────────────────────────────────

def js_array(rows):
    return json.dumps(rows, indent=2)


def main():
    public, private = gen_core_series()

    sso_by_month = build_sso_by_month(public, private)
    change_detail = build_change_detail(public, private)
    cause_by_month = build_cause_trend(public)
    cause_by_year = build_cause_trend_by_year(cause_by_month)
    tracking = build_tracking(public, private)

    out = (
        "// SYNTHETIC SAMPLE DATA - generated by generate_sample_data.py. No real records.\n"
        "\n"
        "window.DATA = {\n"
        f"  ssoByMonth: {js_array(sso_by_month)},\n\n"
        f"  changeDetail: {js_array(change_detail)},\n\n"
        f"  causeTrendByMonth: {js_array(cause_by_month)},\n\n"
        f"  causeTrendByYear: {js_array(cause_by_year)},\n\n"
        f"  trackingByMonth: {js_array(tracking)}\n"
        "};\n"
    )

    target = Path(__file__).resolve().parent / "data.js"
    target.write_text(out)
    n_rows = (len(sso_by_month) + len(change_detail) + len(cause_by_month)
              + len(cause_by_year) + len(tracking))
    print(f"Wrote {target} ({len(out):,} bytes, {n_rows} records)")


if __name__ == "__main__":
    main()
