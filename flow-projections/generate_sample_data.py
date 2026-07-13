#!/usr/bin/env python3
"""Generates synthetic sample data for this dashboard. All data is fabricated.

Writes data.js (loaded by index.html) containing:
  - DATA:    flow projections, populations, permits, diurnal curves, map points
  - CASCADE: service area -> major system -> lift station filter hierarchy

Deterministic: seeded RNG, so output is reproducible. Run:
    python3 generate_sample_data.py
"""

import json
import math
import os
import random

# Public infrastructure name structure (service areas, major conveyance systems,
# and which systems serve which service area). These are public facility names;
# every numeric value, coordinate, lift-station name, and flowmeter ID below is fabricated.
SERVICE_AREAS = ["69th", "AS", "BW", "CB", "CH", "CP", "EH", "FD", "FWSD #23", "GR", "HS", "IC", "IV", "KB", "KW", "MC", "MF (MUD203)", "MG (MUD48)", "NE", "NG", "NT", "NW", "PT", "SB", "SE", "SM", "SW", "TK", "TW", "UB", "WB", "WCID #111", "WCID #47", "WCID#76", "WD", "WO"]

MAJOR_SYSTEMS = [" MF01", " MF02", " NG01A", " NG02A", " NG04A", " WCID 51", "54/72in Trunk", "AS-East", "AS-West", "Aldine Bender", "Alief Central", "BW WWTP", "Ballantine System", "Bay Area System", "Berkley", "Bissonet #4", "Bretshire", "Brock-Eppes", "Buena Park Dr System", "Buffalo Bayou-60 System", "CB WWTP", "CHANUTE", "CP WWTP", "Chelford City", "Cherry Oak System", "Chocolate Bayou", "Cook Rd LS", "Dairy Ashford #4", "De Priest", "Dockal", "EH WWTP LS", "EH-WEST System", "East Houston", "FB_WWTP", "Fairway-Findlay", "Fondren 48", "Forest Cove", "Fulton Trunk", "GREENVIEW MANOR", "Galleria-Almeda", "Gessner #2", "Gessner 48", "Gilpin", "Greenridge", "Greens Bayou System", "Gulf Frwy #2", "Gulfton LS", "HC MUD No. 96", "HS_WWTP", "Harvest Moon", "Heather Ridge", "Heddrick LS", "Heights Trunk", "Highland Meadows", "Holman Tunnel", "Holmes Road System", "Horsepen Gully", "IC WWTP", "IV WWTP", "Interwood", "JFK", "Jadewood", "KB West", "KW01", "KW02", "KW03", "KW04", "KW05", "Kingsride Ln -54 System", "Kingwood Central", "Lang System", "Legend Lane System", "Lockwood LS", "Lockwood Trunk", "MC-North", "MC_MUD#48", "MF03", "MUD 107", "MUD 175-1", "Maxey Rd N-54 System", "Maxey System", "Memorial Trunk", "Monroe- 30 North System", "Monroe- 42 South System", "N Eldridge", "NE WWTP System", "NG-West", "NS-Center", "NS-IA", "NS06 Sys", "NS06 System", "NSRT Tunnel", "NT WWTP", "NT03", "NW WWTP", "NW WWTP System", "NWHC MUD No. 25", "Northborough System", "Northwood", "PT-East System", "PT-West System", "Pearland Parkway LS", "Plaza Verde", "Private", "Red Gully", "Richmond # 1 System", "Roark System", "Royal Lakes", "S Post Oak", "S. Kirkwood-WCID # 78", "SW East", "SanJacinto Trunk", "Scarsdale", "Sherwood Oaks System", "Sims_North", "Sims_West", "South East WWTP LS", "Strange's Camp", "TBD-RoadArea", "TC Jester_60 System", "TC_WWTP Gravity", "TSE03B System", "TSM01 System", "TT WWTP", "Texas Ave", "Theta-24 System", "Trail Tree Ln.", "Trunk 36", "Trunk 54", "Trunk 72", "UBT 72", "UBT108 East", "UBT108 West", "UBT72 South", "UBT78 East", "UBT78 West", "W Gulf Bank Rd -36 System", "W Mount Houston System", "W. Tidwell_42 System", "WB WWTP", "WB01 System", "WB02 System", "WC06B", "WCID # 94", "WCID 51", "WCID No. 73 System", "WCID#47WWTP", "WCID76 WWTP", "WD WWTP", "WJ Center", "WJ South", "WO02 System", "Wayne Tunnel", "West Hollow System", "West Lake Houston", "WestWay MUD", "WestWay UD", "Westheimer", "Westpark LS", "Will Clayton", "Wood Forest-54 System", "Woodsman Trail"]

SA_TO_MS = {
    "69th": ["De Priest", "Fulton Trunk", "Galleria-Almeda", "Heddrick LS", "Heights Trunk", "Holman Tunnel", "Lockwood LS", "Lockwood Trunk", "Memorial Trunk", "NS-Center", "NS-IA", "NS06 Sys", "NS06 System", "NSRT Tunnel", "SanJacinto Trunk", "TC Jester_60 System", "Texas Ave", "W Mount Houston System", "Wayne Tunnel"],
    "AS": [" WCID 51", "AS-East", "AS-West", "Holmes Road System", "WCID 51"],
    "BW": ["BW WWTP", "Richmond # 1 System", "Roark System", "S. Kirkwood-WCID # 78", "WCID # 94"],
    "CB": ["CB WWTP", "Strange's Camp", "WCID No. 73 System"],
    "CC": ["Chelford City", "West Hollow System"],
    "CH": ["Chocolate Bayou"],
    "CP": ["CP WWTP"],
    "EH": ["Buena Park Dr System", "EH WWTP LS", "EH-WEST System", "Monroe- 30 North System", "Monroe- 42 South System"],
    "FD": ["Forest Cove", "KW01", "Trail Tree Ln."],
    "FWSD #23": ["Bretshire", "FB_WWTP", "Lockwood Trunk", "Red Gully"],
    "GR": ["Greenridge", "WCID 51"],
    "HS": ["Dockal", "East Houston", "HS_WWTP"],
    "IC": ["CHANUTE", "GREENVIEW MANOR", "HC MUD No. 96", "IC WWTP", "JFK", "Northwood"],
    "IV": ["Aldine Bender", "IV WWTP", "Plaza Verde"],
    "KB": ["Bissonet #4", "KB West", "UBT72 South", "WCID # 94"],
    "KW": ["Forest Cove", "KW01", "KW02", "KW03", "KW04", "KW05", "Kingwood Central"],
    "MC": ["Horsepen Gully", "MC-North"],
    "ME (Blackhawk)": ["Bay Area System"],
    "MF (MUD203)": [" MF01", " MF02", "MF03"],
    "MG (MUD48)": ["MC_MUD#48"],
    "NE": ["Greens Bayou System", "Maxey Rd N-54 System", "Maxey System", "NE WWTP System", "Wood Forest-54 System"],
    "NG": [" NG01A", " NG02A", " NG04A", "NG-West", "Northborough System"],
    "NT": ["Heather Ridge", "Interwood", "NT WWTP", "NT03", "Will Clayton"],
    "NW": ["Cherry Oak System", "Lang System", "NW WWTP", "NW WWTP System", "NWHC MUD No. 25", "TC Jester_60 System", "W. Tidwell_42 System", "WestWay MUD"],
    "PT": ["PT-East System", "PT-West System"],
    "SB": ["54/72in Trunk", "Berkley", "Brock-Eppes", "Fairway-Findlay", "Gulf Frwy #2", "Sims_North", "Sims_West", "TBD-RoadArea"],
    "SE": ["Ballantine System", "Buena Park Dr System", "Pearland Parkway LS", "South East WWTP LS", "TSE03B System"],
    "SM": ["Highland Meadows", "Scarsdale", "TSM01 System"],
    "SW": ["AS-West", "Bissonet #4", "Fondren 48", "Galleria-Almeda", "Gessner 48", "Gulfton LS", "S Post Oak", "SW East", "Trunk 36", "Trunk 54", "Trunk 72", "UBT 72", "WCID 51", "Westheimer", "Westpark LS"],
    "TK": ["Alief Central", "Harvest Moon", "MUD 107", "MUD 175-1", "N Eldridge", "TC_WWTP Gravity"],
    "TW": ["TT WWTP"],
    "UB": ["Alief Central", "Dairy Ashford #4", "Gessner #2", "Royal Lakes", "UBT 72", "UBT108 East", "UBT108 West", "UBT72 South", "UBT78 East", "UBT78 West"],
    "WB": ["WB WWTP", "WB01 System", "WB02 System"],
    "WCID #111": ["Cook Rd LS", "WJ Center", "WJ South", "West Lake Houston"],
    "WCID #47": ["Gilpin", "Sims_North", "Theta-24 System", "WC06B", "WCID#47WWTP"],
    "WCID#76": ["WCID76 WWTP"],
    "WD": ["Buffalo Bayou-60 System", "Kingsride Ln -54 System", "Legend Lane System", "Sherwood Oaks System", "WD WWTP"],
    "WO": ["Jadewood", "W Gulf Bank Rd -36 System", "WO02 System", "Woodsman Trail"],
    "WW": ["WestWay MUD", "WestWay UD"],
}

# ── Configuration ────────────────────────────────────────────────────────────

SEED = 42
YEARS = [2020, 2024, 2025, 2030, 2035, 2040, 2045, 2050, 2055,
         2060, 2065, 2070, 2080, 2090, 2100, 2110, 2120]
POP_YEARS = [y for y in YEARS if y != 2024]
DIURNAL_YEARS = [2020, 2045, 2070, 2120]

# Relative size of each service area (fabricated weights; jittered below).
SA_SCALE = {
    "69th": 90, "SW": 30, "SB": 28, "UB": 22, "NW": 14, "AS": 14, "KB": 12,
    "WD": 11, "KW": 9, "BW": 8, "NE": 7, "SE": 6, "IC": 5, "GR": 4.5,
    "EH": 3.5, "IV": 3.5, "CH": 3, "HS": 2.5, "NG": 2.5, "NT": 2.5,
    "MC": 2, "WB": 2, "SM": 2, "TK": 2, "WCID #111": 1.5, "FWSD #23": 1.2,
    "WCID #47": 1.2, "PT": 1, "WO": 0.8, "FD": 0.8, "CP": 0.7, "MG (MUD48)": 0.5,
    "CB": 0.5, "TW": 0.4, "MF (MUD203)": 0.4, "WCID#76": 0.3,
    "CC": 0.4, "ME (Blackhawk)": 0.3, "WW": 0.2,
}

CITY_TOTAL_2020 = 265.0        # target citywide 2020 flow, MGD
BBOX = (29.58, 30.04, -95.66, -95.10)   # lat_min, lat_max, lon_min, lon_max

rng = random.Random(SEED)

# ── Synthetic lift-station names ─────────────────────────────────────────────

LS_FIRST = ["OAK", "CEDAR", "HICKORY", "PINE", "MAPLE", "DOGWOOD", "PECAN",
            "CYPRESS", "JUNIPER", "LAUREL", "ASPEN", "BIRCH", "HOLLY", "SYCAMORE",
            "MEADOW", "RIVER", "LAKE", "SPRING", "STONE", "CLEAR", "SHADY",
            "SUNNY", "GOLDEN", "SILVER", "COPPER", "AMBER", "CRESTED", "FALLING",
            "HIDDEN", "WHISPERING", "ROLLING", "WINDING", "BLUFF", "PRAIRIE",
            "HERON", "MOCKINGBIRD", "PELICAN", "FOX", "EGRET", "KESTREL", "OSPREY",
            "BRIAR", "FERN", "IVY", "COTTONWOOD", "ORCHARD", "HARVEST", "SADDLE",
            "CANYON", "SUMMIT", "VALLEY", "GARDEN", "HARBOR", "BAYOU", "TIMBER"]
LS_SECOND = ["CREEK", "RIDGE", "GROVE", "PARK", "HOLLOW", "MEADOW", "TRAIL",
             "BEND", "CROSSING", "POINT", "GLEN", "VISTA", "SPRINGS", "LANDING",
             "TERRACE", "HILL", "BROOK", "FOREST", "GARDENS", "PLACE", "COVE",
             "BLUFF", "CHASE", "FIELD", "GATE", "HAVEN", "KNOLL", "SHORE", "WAY"]
LS_SUFFIX = ["", "", "", "", " #1", " #2", " #3", " RD.", " LN.", " DR."]


def make_ls_pool(n, used):
    """Generate n unique synthetic lift-station names not already in `used`."""
    pool = []
    while len(pool) < n:
        name = (rng.choice(LS_FIRST) + " " + rng.choice(LS_SECOND)
                + rng.choice(LS_SUFFIX))
        if name not in used:
            used.add(name)
            pool.append(name)
    return pool


def make_flowmeter_ids(n):
    """Generate n unique synthetic flowmeter IDs (e.g. FM-1042)."""
    ids = set()
    while len(ids) < n:
        ids.add(f"FM-{rng.randint(1000, 9999)}")
    return sorted(ids)

# ── Growth / trend helpers ───────────────────────────────────────────────────


def growth_series(v2020, rate, damp_after=2070, damp=0.45, jitter=0.015):
    """Compound growth with damping late in the horizon and mild year-to-year jitter."""
    vals = []
    for y in YEARS:
        t = y - 2020
        if y <= damp_after:
            g = (1 + rate) ** t
        else:
            g = (1 + rate) ** (damp_after - 2020) * (1 + rate * damp) ** (y - damp_after)
        vals.append(v2020 * g * (1 + rng.uniform(-jitter, jitter)))
    return vals


def diurnal_shape(weekend):
    """24-hour multiplier curve (mean ~1.0): overnight trough, AM peak, PM shoulder."""
    shape = []
    for h in range(24):
        if weekend:
            v = (1.0
                 - 0.34 * math.exp(-((h - 4.5) ** 2) / 7.0)      # deeper, later trough
                 + 0.24 * math.exp(-((h - 11.0) ** 2) / 9.0)     # late-morning peak
                 + 0.12 * math.exp(-((h - 20.0) ** 2) / 8.0))    # evening shoulder
        else:
            v = (1.0
                 - 0.36 * math.exp(-((h - 3.5) ** 2) / 6.0)      # pre-dawn trough
                 + 0.28 * math.exp(-((h - 8.5) ** 2) / 6.5)      # morning peak
                 + 0.16 * math.exp(-((h - 20.5) ** 2) / 9.0))    # evening peak
        shape.append(v)
    mean = sum(shape) / 24
    return [v / mean for v in shape]

# ── 1. Per-service-area flow, population, permit ─────────────────────────────

all_sas = list(SA_TO_MS.keys())          # 39 incl. 3 non-selectable areas
raw = {sa: SA_SCALE[sa] * rng.uniform(0.75, 1.3) for sa in all_sas}
scale = CITY_TOTAL_2020 / sum(raw.values())

by_sa, sa_meta = {}, {}
for sa in all_sas:
    total_2020 = raw[sa] * scale
    res_f = rng.uniform(0.34, 0.50)                      # residential share
    trade_f = rng.uniform(0.10, 0.30)                    # commercial/industrial share
    base_f = 1 - res_f - trade_f                         # baseflow (I/I) share
    rate = rng.uniform(0.002, 0.009)                     # annual growth
    res = growth_series(total_2020 * res_f, rate * rng.uniform(1.0, 1.3))
    trade = growth_series(total_2020 * trade_f, rate * rng.uniform(0.7, 1.1))
    base = growth_series(total_2020 * base_f, rate * rng.uniform(0.5, 0.9))
    total = [r + t + b for r, t, b in zip(res, trade, base)]

    gpcd = rng.uniform(50, 70)                           # gal/capita/day
    pop2020 = res[0] * 1e6 / gpcd
    pop_rate = rate * rng.uniform(0.9, 1.2)
    pop_all = growth_series(pop2020, pop_rate, jitter=0.008)
    pop = [round(v) for v, y in zip(pop_all, YEARS) if y != 2024]

    if sa in SERVICE_AREAS:                              # permitted capacity, MGD
        headroom = rng.uniform(0.62, 0.92)               # 2120 flow as share of permit
        permit_raw = max(total) / headroom
        step = 10 if permit_raw > 60 else 5 if permit_raw > 20 else 0.5
        permit = round(math.ceil(permit_raw / step) * step, 2)
    else:
        permit = None                                    # non-selectable areas

    by_sa[sa] = {"total": [round(v, 3) for v in total],
                 "res":   [round(v, 3) for v in res],
                 "trade": [round(v, 3) for v in trade],
                 "base":  [round(v, 3) for v in base],
                 "permit": permit,
                 "pop": pop}
    sa_meta[sa] = {"total": total, "res": res, "trade": trade, "base": base}

city = {}
for key in ("total", "res", "trade", "base"):
    city[key] = [round(sum(sa_meta[sa][key][i] for sa in all_sas), 3)
                 for i in range(len(YEARS))]
city["permit"] = None
city["pop"] = [sum(by_sa[sa]["pop"][i] for sa in all_sas) for i in range(len(POP_YEARS))]

# ── 2. Per-major-system flow (Dirichlet-style split of each service area) ────

ms_meta = {ms: {"total": [0.0] * len(YEARS), "res": [0.0] * len(YEARS),
                "trade": [0.0] * len(YEARS), "base": [0.0] * len(YEARS)}
           for ms in MAJOR_SYSTEMS}
ms_share_in_sa = {}                                      # (sa, ms) -> weight
for sa in all_sas:
    systems = SA_TO_MS[sa]
    if not systems:
        continue
    weights = [rng.gammavariate(1.4, 1.0) for _ in systems]
    wsum = sum(weights)
    for ms, w in zip(systems, weights):
        share = w / wsum
        ms_share_in_sa[(sa, ms)] = share
        for key in ("total", "res", "trade", "base"):
            for i in range(len(YEARS)):
                ms_meta[ms][key][i] += sa_meta[sa][key][i] * share

# "Private" connections: small standalone system not in any cascade
for i in range(len(YEARS)):
    v = 0.35 * (1.003 ** (YEARS[i] - 2020))
    ms_meta["Private"]["total"][i] = v
    ms_meta["Private"]["res"][i] = v * 0.6
    ms_meta["Private"]["trade"][i] = v * 0.15
    ms_meta["Private"]["base"][i] = v * 0.25

by_ms = {ms: {"total": [round(v, 3) for v in m["total"]],
              "res":   [round(v, 3) for v in m["res"]],
              "trade": [round(v, 3) for v in m["trade"]],
              "base":  [round(v, 3) for v in m["base"]],
              "permit": None}
         for ms, m in ms_meta.items()}

# ── 3. Synthetic lift stations and flowmeters ────────────────────────────────

used_ls = set()
ls_by_ms_by_sa = {}                                      # CASCADE payload
for sa in all_sas:
    systems = SA_TO_MS[sa]
    pool = make_ls_pool(max(4, min(30, 3 * len(systems))), used_ls)
    ls_by_ms_by_sa[sa] = {
        ms: sorted(rng.sample(pool, min(len(pool), rng.randint(2, 8))))
        for ms in systems}

CASCADE = {sa: {"ms": SA_TO_MS[sa], "ls_by_ms": ls_by_ms_by_sa[sa]}
           for sa in all_sas}
ls_names = sorted(used_ls)

flowmeters = make_flowmeter_ids(420)
fm_by_ms = {ms: rng.sample(flowmeters, rng.randint(2, 5)) for ms in MAJOR_SYSTEMS}

# ── 4. Map points (random synthetic geometry inside a metro bounding box) ────

lat_min, lat_max, lon_min, lon_max = BBOX


def spread_centers(n, min_dist=0.045):
    """Seeded rejection sampling: n reasonably spaced centers in the bbox."""
    centers = []
    while len(centers) < n:
        c = (rng.uniform(lat_min + 0.02, lat_max - 0.02),
             rng.uniform(lon_min + 0.02, lon_max - 0.02))
        if all(abs(c[0] - o[0]) + abs(c[1] - o[1]) > min_dist for o in centers):
            centers.append(c)
        else:
            min_dist *= 0.995                            # relax if the box fills up
    return centers


sa_center = dict(zip(all_sas, spread_centers(len(all_sas))))
ms_center_design = {}
for sa in all_sas:
    clat, clon = sa_center[sa]
    for ms in SA_TO_MS[sa]:
        ms_center_design[(sa, ms)] = (clat + rng.uniform(-0.030, 0.030),
                                      clon + rng.uniform(-0.030, 0.030))

N_POINTS = 4200
pts = {"lats": [], "lons": [], "sa": [], "ms": [], "ls": [], "fm": []}
for sa in all_sas:
    systems = SA_TO_MS[sa]
    if not systems:
        continue
    n_sa = max(18, round(N_POINTS * raw[sa] * scale / CITY_TOTAL_2020))
    weights = [ms_share_in_sa[(sa, ms)] for ms in systems]
    for _ in range(n_sa):
        ms = rng.choices(systems, weights=weights)[0]
        clat, clon = ms_center_design[(sa, ms)]
        lat = min(lat_max, max(lat_min, rng.gauss(clat, 0.011)))
        lon = min(lon_max, max(lon_min, rng.gauss(clon, 0.011)))
        ls_list = ls_by_ms_by_sa[sa][ms]
        pts["lats"].append(round(lat, 5))
        pts["lons"].append(round(lon, 5))
        pts["sa"].append(sa)
        pts["ms"].append(ms)
        pts["ls"].append(rng.choice(ls_list) if ls_list else None)
        pts["fm"].append(rng.choice(fm_by_ms[ms]))


def mean_center(keys, key_field):
    out = {}
    for k in keys:
        idx = [i for i, v in enumerate(pts[key_field]) if v == k]
        if idx:
            out[k] = [round(sum(pts["lats"][i] for i in idx) / len(idx), 4),
                      round(sum(pts["lons"][i] for i in idx) / len(idx), 4)]
    return out


map_sa_centers = mean_center(all_sas, "sa")
map_ms_centers = mean_center(MAJOR_SYSTEMS, "ms")

# ── 5. Diurnal curves (hourly MGD for 2020 / 2045 / 2070 / 2120, WD & WE) ────

year_idx = {y: YEARS.index(y) for y in DIURNAL_YEARS}
sa_phase = {sa: rng.uniform(-1.2, 1.2) for sa in all_sas}
ms_phase = {ms: rng.uniform(-1.5, 1.5) for ms in MAJOR_SYSTEMS}


def curve(avg_flow, shape, phase, nd=3):
    shifted = [shape[int(h - round(phase)) % 24] for h in range(24)]
    return [round(avg_flow * s * (1 + rng.uniform(-0.02, 0.02)), nd) for s in shifted]


diurnal_total = {}
for suffix, weekend in (("_WD", False), ("_WE", True)):
    shape = diurnal_shape(weekend)
    wk_factor = 0.93 if weekend else 1.0                 # weekends run slightly lower
    for y in DIURNAL_YEARS:
        i = year_idx[y]
        sheet = {"city": curve(city["total"][i] * wk_factor, shape, 0.0),
                 "by_sa": {sa: curve(sa_meta[sa]["total"][i] * wk_factor,
                                     shape, sa_phase[sa]) for sa in all_sas},
                 "by_ms": {ms: curve(ms_meta[ms]["total"][i] * wk_factor,
                                     shape, ms_phase[ms], nd=2)
                           for ms in MAJOR_SYSTEMS}}
        diurnal_total[f"All_TotalFlow{y}{suffix}"] = sheet

# ── 6. Assemble and write data.js ────────────────────────────────────────────

DATA = {
    "years": YEARS,
    "pop_years": POP_YEARS,
    "service_areas": SERVICE_AREAS,
    "major_systems": MAJOR_SYSTEMS,
    "ls_names": ls_names,
    "flowmeters": flowmeters,
    "city": city,
    "by_sa": by_sa,
    "by_ms": by_ms,
    "diurnal_total": diurnal_total,
    "map_points": pts,
    "map_sa_centers": map_sa_centers,
    "map_ms_centers": map_ms_centers,
}

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.js")
with open(out_path, "w") as f:
    f.write("// SYNTHETIC SAMPLE DATA - generated by generate_sample_data.py. No real records.\n")
    f.write("const DATA = " + json.dumps(DATA, separators=(",", ":")) + ";\n")
    f.write("const CASCADE = " + json.dumps(CASCADE, separators=(",", ":")) + ";\n")

size_kb = os.path.getsize(out_path) / 1024
print(f"Wrote {out_path} ({size_kb:.0f} KB)")
print(f"  service areas: {len(by_sa)}  major systems: {len(by_ms)}")
print(f"  lift stations: {len(ls_names)}  flowmeters: {len(flowmeters)}")
print(f"  map points: {len(pts['lats'])}  diurnal sheets: {len(diurnal_total)}")
print(f"  city 2020 total: {city['total'][0]:.1f} MGD -> 2120: {city['total'][-1]:.1f} MGD")
