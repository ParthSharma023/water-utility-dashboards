#!/usr/bin/env python3
"""Generates synthetic sample data for this dashboard. All data is fabricated.

Produces data.js in the schema the dashboard consumes:

    window.DATA = {
      rows: [ { i: "YYYY-MM-DD",         // date the work order was initiated
                v: "YYYY-MM-DD" | null,  // date the closure was verified
                c: "YYYY-MM-DD" | null,  // date the repair was completed
                cd: "A".."K" },          // council district
              ... ],
      councilDistricts: ["A", ..., "K"],
      lastUpdated: "YYYY-MM-DD",
    }

A row with c == null (and v == null) is an active (still open) work order.

The generator is deterministic: a fixed RNG seed and a fixed report window,
so re-running it always produces the same file. Distributions are shaped to
look like real utility repair activity:

  * weekday/weekend cycle (crews initiate far fewer orders on weekends)
  * annual seasonality peaking in late summer (heat + dry soil movement)
  * short winter freeze spikes and a late-summer drought bump
  * a mild upward trend across the window
  * log-normal time-to-complete with a heavy tail, plus a small share of
    long-running "stuck" orders and never-closed abandoned ones

Run:  python3 generate_sample_data.py
"""

import json
import math
import random
from datetime import date, timedelta

SEED = 20260708
OUT_FILE = "data.js"

# Fixed report window (~2 years). Fixed so output is fully deterministic.
END_DATE = date(2026, 7, 8)          # acts as the "data export" date
START_DATE = END_DATE - timedelta(days=729)

BASE_RATE = 13.0                      # average orders initiated per day
TREND_END_FACTOR = 1.10               # mild growth across the window

# Mon..Sun multipliers: field crews and call intake drop off on weekends.
WEEKDAY_FACTOR = [1.12, 1.18, 1.20, 1.14, 1.06, 0.62, 0.42]

# Council district mix (synthetic weights, letters only).
DISTRICTS = list("ABCDEFGHIJK")
DISTRICT_WEIGHTS = [5, 9, 11, 15, 11, 7, 10, 8, 11, 3, 10]

# Short-lived demand events: (first_day, last_day, peak_multiplier).
EVENTS = [
    (date(2025, 1, 20), date(2025, 1, 27), 3.0),   # hard freeze
    (date(2025, 8, 18), date(2025, 10, 10), 1.35), # drought stress
    (date(2026, 1, 6), date(2026, 1, 11), 2.2),    # hard freeze
]

P_ABANDONED = 0.025      # never closed at all
P_STUCK = 0.05           # closed, but only after a very long delay
STUCK_RANGE = (30, 180)  # days


def seasonal_factor(d: date) -> float:
    """Annual cycle peaking around early September (day-of-year ~250)."""
    doy = d.timetuple().tm_yday
    return 1.0 + 0.30 * math.cos(2.0 * math.pi * (doy - 250) / 365.0)


def event_factor(d: date) -> float:
    f = 1.0
    for first, last, peak in EVENTS:
        if first <= d <= last:
            span = (last - first).days
            # ramp up to the peak mid-event, back down at the edges
            pos = (d - first).days / span
            f *= 1.0 + (peak - 1.0) * math.sin(math.pi * pos) ** 0.5
    return f


def poisson(rng: random.Random, lam: float) -> int:
    """Knuth's algorithm; lam stays small (< 60) here."""
    limit = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def completion_delay(rng: random.Random) -> int:
    """Days from initiation to completed repair."""
    if rng.random() < P_STUCK:
        return rng.randint(*STUCK_RANGE)
    # log-normal: median ~4 days, p90 ~25, heavy tail
    return min(int(rng.lognormvariate(1.4, 1.5)), 300)


def verify_delay(rng: random.Random) -> int:
    """Days from completed repair to verified closure (usually same day)."""
    r = rng.random()
    if r < 0.90:
        return 0
    if r < 0.95:
        return 1
    if r < 0.98:
        return rng.randint(2, 5)
    return rng.randint(6, 30)


def main() -> None:
    rng = random.Random(SEED)
    total_days = (END_DATE - START_DATE).days
    rows = []

    d = START_DATE
    while d <= END_DATE:
        progress = (d - START_DATE).days / total_days
        trend = 1.0 + (TREND_END_FACTOR - 1.0) * progress
        lam = (BASE_RATE * trend * WEEKDAY_FACTOR[d.weekday()]
               * seasonal_factor(d) * event_factor(d))
        for _ in range(poisson(rng, lam)):
            cd = rng.choices(DISTRICTS, weights=DISTRICT_WEIGHTS, k=1)[0]
            if rng.random() < P_ABANDONED:
                completed = verified = None
            else:
                completed = d + timedelta(days=completion_delay(rng))
                if completed > END_DATE:
                    # not finished by the export date -> still open
                    completed = verified = None
                else:
                    verified = min(completed + timedelta(days=verify_delay(rng)),
                                   END_DATE)
            rows.append({
                "i": d.isoformat(),
                "v": verified.isoformat() if verified else None,
                "c": completed.isoformat() if completed else None,
                "cd": cd,
            })
        d += timedelta(days=1)

    rows.sort(key=lambda r: r["i"], reverse=True)
    payload = {
        "rows": rows,
        "councilDistricts": DISTRICTS,
        "lastUpdated": END_DATE.isoformat(),
    }

    with open(OUT_FILE, "w") as f:
        f.write("// SYNTHETIC SAMPLE DATA - generated by "
                "generate_sample_data.py. No real records.\n")
        f.write("window.DATA = ")
        json.dump(payload, f, separators=(",", ":"))
        f.write(";\n")

    active = sum(1 for r in rows if r["c"] is None)
    print(f"wrote {OUT_FILE}: {len(rows)} rows "
          f"({START_DATE} .. {END_DATE}), {active} active")


if __name__ == "__main__":
    main()
