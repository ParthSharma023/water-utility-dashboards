#!/usr/bin/env python3
"""Generates synthetic sample data for this dashboard. All data is fabricated.

Produces data-wo-wwtp.js in the exact schema the dashboard pages consume:

    window.WO_ROWS = [
      {"WO": "...", "desc": "...", "created": "YYYY-MM-DD", "sched_end": "YYYY-MM-DD",
       "jobtype": "...", "status": "Open"|"Closed", "loc_id": "....",
       "facility": "...", "obj_code": "...", "obj_desc": "...", "cls": "..."},
      ...
    ]

Every record is generated from templates and seeded randomness: work-order
numbers, location IDs, asset codes, and descriptions correspond to nothing real.
Facility names are public wastewater treatment plant names. The dataset spans
roughly the 30 months ending on the day the script is run, so the dashboards'
relative date filters ("Last 2 weeks", "Last 3 months") always have data.

Usage: python3 generate_sample_data.py
"""

import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20240613
DAYS_OF_HISTORY = 913  # ~30 months
BASE_WO_PER_DAY = 4.2
WO_NUMBER_START = 3_000_000

# Public wastewater treatment plant names with rough relative maintenance volume.
FACILITIES = [
    ("69TH STREET WWTP", 7.7),
    ("69TH STREET SLUDGE WWTP", 3.4),
    ("KEEGANS BAYOU WWTP (CFS)", 2.8),
    ("ALMEDA SIMS WWTP", 2.8),
    ("KINGWOOD CENTRAL WWTP", 2.6),
    ("SIMS SOUTH WWTP", 2.0),
    ("UPPER BRAES BAYOU WWTP", 2.0),
    ("SIMS BAYOU WWTP (CENTRAL AVENUE LIFT STATION)", 2.0),
    ("SOUTHWEST WWTP", 1.9),
    ("ALMEDA SIMS WWTP SLUDGE PLANT", 1.9),
    ("TURKEY CREEK WWTP", 1.85),
    ("SOUTHEAST WWTP", 1.8),
    ("BELTWAY WWTP", 1.5),
    ("NORTHWEST WWTP (CFS)", 1.4),
    ("GREENRIDGE WWTP", 1.4),
    ("WEST DISTRICT WWTP", 1.3),
    ("W.C.I.D. #111 WWTP", 1.26),
    ("KINGWOOD WEST (M.U.D. # 48) WWTP", 1.26),
    ("F.W.S.D. #23 WWTP", 1.2),
    ("NORTHGATE WWTP", 1.2),
    ("CEDAR BAYOU WWTP", 1.1),
    ("METRO CENTRAL WWTP", 1.07),
    ("NORTHEAST WWTP", 1.06),
    ("CHOCOLATE BAYOU WWTP", 1.03),
    ("SAGEMONT WWTP", 1.03),
    ("W.C.I.D. #047 WWTP", 1.03),
    ("EASTHAVEN WWTP", 0.99),
    ("PARK TEN M.U.D. WWTP", 0.93),
    ("WHITE OAK WWTP", 0.91),
    ("IMPERIAL VALLEY WWTP", 0.91),
    ("HOMESTEAD WWTP", 0.9),
    ("NORTHBELT WWTP", 0.9),
    ("CLINTON PARK WWTP", 0.87),
    ("SIMS BAYOU SLUDGE WWTP", 0.79),
    ("M.U.D. #203 WWTP", 0.77),
    ("INT. AIRPORT WWTP", 0.74),
    ("WILLOWBROOK WWTP", 0.74),
    ("FOREST COVE WWTP", 0.73),
    ("WEST LAKE HOUSTON WWTP", 0.69),
    ("WESTWAY M.U.D. WWTP", 0.59),
    ("W.C.I.D. #076 WWTP", 0.4),
    ("TIDWELL TIMBERS WWTP", 0.34),
]

# Equipment class -> (relative weight, [(tag, description, max unit number)]).
# A max unit of 0 means the asset is a singular area/system with no unit number.
CLASSES = {
    "SYSTEMS AREA": (20, [
        ("CL2BNA", "CHLORINE BASIN AREA", 0),
        ("HDWKA", "HEADWORKS AREA", 0),
        ("DIGA", "DIGESTER AREA", 0),
        ("DWTRA", "DEWATERING AREA", 0),
        ("AERA", "AERATION AREA", 0),
    ]),
    "PUMP": (19, [
        ("INFPMP", "INFLUENT PUMP", 6),
        ("EFFPMP", "EFFLUENT PUMP", 4),
        ("RASPMP", "RAS PUMP", 6),
        ("WASPMP", "WAS PUMP", 4),
        ("SLGPMP", "SLUDGE PUMP", 4),
        ("SO3PMP", "SODIUM BISULFITE PUMP", 3),
        ("CL2PMP", "CHLORINE PUMP", 3),
        ("DRNPMP", "DRAIN PUMP", 2),
    ]),
    "SYSTEM": (11, [
        ("CL2SYS", "CHLORINATION SYSTEM", 0),
        ("SO3SYS", "DECHLORINATION SYSTEM", 0),
        ("AIRSYS", "PLANT AIR SYSTEM", 0),
        ("W3SYS", "NON-POTABLE WATER SYSTEM", 0),
        ("ODRSYS", "ODOR CONTROL SYSTEM", 0),
    ]),
    "BUILDING": (10, [
        ("CL2B", "CHLORINE BUILDING", 0),
        ("BLWB", "BLOWER BUILDING", 0),
        ("ADMB", "ADMINISTRATION BUILDING", 0),
        ("ELECB", "ELECTRICAL BUILDING", 0),
        ("ANLZB", "ANALYZER BUILDING", 0),
        ("MNTB", "MAINTENANCE BUILDING", 0),
    ]),
    "CLARIFIER": (6, [("CLR", "CLARIFIER", 8)]),
    "BLOWER": (6, [
        ("AERBLW", "AERATION BLOWER", 6),
        ("CHNBLW", "CHANNEL AIR BLOWER", 3),
    ]),
    "BASIN": (3, [
        ("AERBSN", "AERATION BASIN", 6),
        ("CL2BSN", "CHLORINE CONTACT BASIN", 4),
    ]),
    "TANKS": (2.2, [
        ("CL2TK", "CHLORINE TANK", 3),
        ("SO3TK", "BISULFITE TANK", 2),
        ("FUELTK", "FUEL TANK", 2),
    ]),
    "SCADA & INSTRUMENTATION": (2.1, [
        ("CL2ANLZ", "CHLORINE RESIDUAL ANALYZER", 2),
        ("DOANLZ", "DISSOLVED OXYGEN ANALYZER", 3),
        ("FLWMTR", "INFLUENT FLOW METER", 2),
        ("PLC", "PLC CONTROL PANEL", 3),
    ]),
    "MIXER": (2, [("MXR", "ANOXIC ZONE MIXER", 6)]),
    "BELTPRESS": (1.9, [("BLTPRS", "BELT FILTER PRESS", 4)]),
    "SCREEN": (1.6, [("BARSCR", "MECHANICAL BAR SCREEN", 4)]),
    "CONVEYOR": (1.4, [("CNVR", "SCREENINGS CONVEYOR", 5)]),
    "GENERATOR": (1.1, [("GEN", "EMERGENCY GENERATOR", 3)]),
    "CENTRIFUGE": (1.0, [("CNTRFG", "DEWATERING CENTRIFUGE", 4)]),
    "GROUNDS": (0.9, [("GRNDS", "PLANT GROUNDS", 0)]),
    "HVAC": (0.8, [("HVAC", "HVAC UNIT", 4)]),
    "ROOM": (0.75, [
        ("ELECRM", "ELECTRICAL ROOM", 0),
        ("PMPRM", "PUMP ROOM", 0),
    ]),
    "MCC / SWITCHGEAR": (0.75, [
        ("MCC", "MOTOR CONTROL CENTER", 4),
        ("SWGR", "SWITCHGEAR LINEUP", 2),
    ]),
    "FENCE": (0.7, [("FNC", "PERIMETER FENCE", 0)]),
    "VALVES": (0.7, [
        ("PLGVLV", "PLUG VALVE", 8),
        ("CHKVLV", "CHECK VALVE", 8),
    ]),
    "WET WELL": (0.7, [("WETWL", "WET WELL", 2)]),
    "METER": (0.45, [("EFFMTR", "EFFLUENT FLOW METER", 2)]),
    "COMPRESSOR": (0.4, [("AIRCMP", "AIR COMPRESSOR", 3)]),
    "CRANE": (0.3, [("CRN", "BRIDGE CRANE", 2)]),
    "FILTER": (0.2, [("FLTR", "EFFLUENT FILTER", 4)]),
    "DISINFECTION": (0.2, [("UVDIS", "UV DISINFECTION BANK", 3)]),
}

# Solids-handling classes are more common at sludge plants.
SOLIDS_CLASSES = {"CENTRIFUGE", "BELTPRESS", "CONVEYOR", "MIXER"}

# Work-order type codes (None = not recorded, which the pages handle).
JOBTYPES = [
    ("BRKD", 37), ("CM", 34), (None, 13), ("PVM", 5), ("PM", 3.3),
    ("ELEC", 2.2), ("PDM", 1.6), ("INST", 1.4), ("NP", 1.2), ("SHMI", 0.6),
    ("CAL", 0.4), ("CT", 0.2), ("SAFE", 0.1),
]

DESC_BY_CLASS = {
    "PUMP": [
        "Pump tripping on overload", "Pump not working in automatic",
        "Replace mechanical seal", "Remove stoppage", "Pump seal leaking",
        "Rebuild pump - low discharge pressure", "Motor running hot",
        "Excessive vibration at pump", "Packing leaking - adjust or replace",
    ],
    "BLOWER": [
        "Blower vibrating excessively", "Replace inlet air filter",
        "Blower tripping on high temperature", "Grease bearings and check alignment",
        "Belt slipping - replace drive belts", "Abnormal noise from blower housing",
    ],
    "CLARIFIER": [
        "Inspect clarifier bullgear for damage", "Skimmer arm bent - repair",
        "Clarifier drive making noise", "Replace squeegees on rake arm",
        "Clean algae buildup on weirs", "Torque overload alarm on drive",
    ],
    "BASIN": [
        "Diffuser membranes need replacement", "Low air flow to basin",
        "Foam buildup - investigate", "Basin isolation gate stuck",
    ],
    "BUILDING": [
        "Roof leaking - repair", "Exhaust fan not running", "Door hinge broken",
        "Replace exterior lighting", "Repair damaged louver",
    ],
    "SYSTEMS AREA": [
        "Area lighting out", "Housekeeping - remove debris from area",
        "Leaking piping in area", "Repair grating and handrail",
        "Wash down area and inspect equipment",
    ],
    "SYSTEM": [
        "System pressure low - investigate", "Leak on chemical feed line",
        "Feed rate erratic - troubleshoot", "Flush and recharge system",
    ],
    "TANKS": [
        "Tank fill line is leaking", "Level indicator reading incorrectly",
        "Inspect tank for corrosion", "Replace fill line gasket",
    ],
    "SCADA & INSTRUMENTATION": [
        "Analyzer stuck at zero", "Analyzer not working - service",
        "Calibrate instrument", "PLC needs to be serviced",
        "Signal fault on transmitter", "Replace probe and recalibrate",
    ],
    "MIXER": [
        "Mixer tripping breaker", "Replace mixer gearbox oil",
        "Mixer shaft seal leaking", "Impeller fouled - clean",
    ],
    "BELTPRESS": [
        "Belt tracking off center", "Replace belt on press",
        "Wash water spray nozzles plugged", "Hydraulic unit leaking",
    ],
    "SCREEN": [
        "Screen rake jammed", "Replace rake teeth", "Screenings not discharging",
        "Adjust limit switches on screen",
    ],
    "CONVEYOR": [
        "Conveyor belt slipping", "Replace conveyor bearing",
        "Screw conveyor plugged - clear", "Belt alignment adjustment",
    ],
    "GENERATOR": [
        "Generator failed weekly exercise test", "Coolant leak at generator",
        "Replace generator batteries", "Block heater not working",
    ],
    "CENTRIFUGE": [
        "High vibration alarm on centrifuge", "Rebuild centrifuge scroll",
        "Torque limit alarm - investigate", "Polymer feed to centrifuge erratic",
    ],
    "GROUNDS": ["Mow and trim plant grounds", "Repair washout at access road",
                "Remove fallen tree limbs", "Grade and re-rock driveway"],
    "HVAC": ["AC unit not cooling", "Replace filters", "Condensate drain clogged",
             "Compressor short cycling"],
    "ROOM": ["Room exhaust fan inoperable", "Lighting out in room",
             "Repair door closer"],
    "MCC / SWITCHGEAR": [
        "Breaker tripping - investigate", "Thermal scan follow-up repair",
        "Replace pilot lights on MCC", "Bucket failure - replace starter",
    ],
    "FENCE": ["Repair hole in perimeter fence", "Gate latch broken",
              "Replace damaged fence section", "Straighten leaning fence posts"],
    "VALVES": ["Valve will not fully close", "Actuator fault on valve",
               "Replace valve packing", "Exercise and lubricate valve"],
    "WET WELL": ["Clean grease buildup from wet well", "Float switch not working",
                 "Level transducer fouled - clean"],
    "METER": ["Meter reading erratic", "Verify meter calibration",
              "No signal from flow meter"],
    "COMPRESSOR": ["Compressor not building pressure", "Air dryer fault",
                   "Replace compressor belt", "Drain trap stuck open"],
    "CRANE": ["Annual crane inspection repairs", "Hoist limit switch fault",
              "Pendant control not responding"],
    "FILTER": ["Backwash cycle not completing", "Replace filter media",
               "Underdrain inspection"],
    "DISINFECTION": ["Replace UV lamps", "Low intensity alarm on bank",
                     "Clean quartz sleeves", "Ballast fault - replace"],
}

PM_DESCS = [
    "Monthly PM inspection", "Quarterly lubrication route",
    "Semi-annual preventive maintenance", "Annual inspection and service",
    "Routine PM - check and adjust", "Thermography route follow-up",
]

GENERIC_DESCS = [
    "Investigate abnormal noise", "Repair leak", "Unit out of service - troubleshoot",
    "Electrical troubleshooting", "Replace worn components",
    "Corrective repair after inspection", "Operator reported issue - investigate",
]


def weighted_choice(rng, pairs):
    total = sum(w for _, w in pairs)
    roll = rng.uniform(0, total)
    acc = 0.0
    for value, weight in pairs:
        acc += weight
        if roll <= acc:
            return value
    return pairs[-1][0]


def daily_volume(rng, day, start, end):
    """Expected WO count for a day: seasonality, mild growth, weekday effect."""
    doy = day.timetuple().tm_yday
    seasonal = 1.0 + 0.28 * math.sin(2 * math.pi * (doy - 120) / 365.0)
    progress = (day - start).days / max(1, (end - start).days)
    trend = 0.9 + 0.25 * progress
    weekday = day.weekday()
    weekday_factor = 1.15 if weekday < 5 else (0.55 if weekday == 5 else 0.4)
    mu = BASE_WO_PER_DAY * seasonal * trend * weekday_factor
    n = int(round(rng.gauss(mu, math.sqrt(mu))))
    return max(0, n)


def open_probability(age_days):
    if age_days < 7:
        return 0.92
    if age_days < 14:
        return 0.85
    if age_days < 30:
        return 0.70
    if age_days < 60:
        return 0.45
    if age_days < 120:
        return 0.22
    if age_days < 365:
        return 0.07
    return 0.03


def main():
    rng = random.Random(SEED)
    end = date.today()
    start = end - timedelta(days=DAYS_OF_HISTORY)

    # Synthetic 4-digit location IDs, one per facility (generated, not real).
    loc_codes = rng.sample(range(1000, 9900), len(FACILITIES))
    loc_ids = {name: f"{code:04d}" for (name, _), code in zip(FACILITIES, loc_codes)}

    class_pairs = [(name, spec[0]) for name, spec in CLASSES.items()]
    sludge_class_pairs = [
        (name, weight * (4.0 if name in SOLIDS_CLASSES else 1.0))
        for name, weight in class_pairs
    ]
    zone_codes = ["01", "02", "03", "05", "07", "08", "10", "12"]

    rows = []
    wo_number = WO_NUMBER_START
    day = start
    while day <= end:
        for _ in range(daily_volume(rng, day, start, end)):
            facility = weighted_choice(rng, FACILITIES)
            loc_id = loc_ids[facility]
            is_sludge = "SLUDGE" in facility
            cls = weighted_choice(rng, sludge_class_pairs if is_sludge else class_pairs)
            tag, obj_name, max_unit = rng.choice(CLASSES[cls][1])

            if max_unit > 0:
                unit = rng.randint(1, max_unit)
                obj_code = f"{loc_id}{rng.choice(zone_codes)}{tag}{unit:02d}"
                obj_desc = f"{obj_name} {unit:02d}"
            else:
                obj_code = f"{loc_id}{rng.choice(zone_codes)}{tag}"
                obj_desc = obj_name

            jobtype = weighted_choice(rng, JOBTYPES)
            if jobtype in ("PM", "PVM", "PDM") and rng.random() < 0.7:
                desc = rng.choice(PM_DESCS)
            elif rng.random() < 0.85:
                desc = rng.choice(DESC_BY_CLASS.get(cls, GENERIC_DESCS))
            else:
                desc = rng.choice(GENERIC_DESCS)

            age = (end - day).days
            status = "Open" if rng.random() < open_probability(age) else "Closed"

            if jobtype in ("PM", "PVM", "PDM"):
                sched_end = day + timedelta(days=rng.randint(7, 45))
            elif rng.random() < 0.65:
                sched_end = day
            else:
                sched_end = day + timedelta(days=rng.randint(1, 21))

            wo_number += rng.randint(2, 18)
            rows.append({
                "WO": str(wo_number),
                "desc": desc,
                "created": day.isoformat(),
                "sched_end": sched_end.isoformat(),
                "jobtype": jobtype,
                "status": status,
                "loc_id": loc_id,
                "facility": facility,
                "obj_code": obj_code,
                "obj_desc": obj_desc,
                "cls": cls,
            })
        day += timedelta(days=1)

    out_path = Path(__file__).resolve().parent / "data-wo-wwtp.js"
    payload = json.dumps(rows, separators=(",", ":"))
    out_path.write_text(
        "// SYNTHETIC SAMPLE DATA - generated by generate_sample_data.py. No real records.\n"
        f"window.WO_ROWS={payload};\n"
    )
    open_count = sum(1 for r in rows if r["status"] == "Open")
    print(f"Wrote {len(rows)} synthetic work orders ({open_count} open) "
          f"spanning {start} to {end} -> {out_path.name} "
          f"({out_path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
