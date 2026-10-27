"""Deterministic diagnosis: ISO 20816-3 applicability + estimated zone, suspected fault pattern, confidence.
workflow.md §A3, §B5.5.  The LLM never changes anything computed here.

ISO 20816-3 scope/exclusions/band: read in the official preview (clause 1, 4.3).
Zone boundary values (Annex A): from secondary sources only -> labelled as such."""
from __future__ import annotations

from . import config

ZONES = {  # (A/B, B/C, C/D) mm/s RMS  -- secondary sources, see workflow.md §A3
    (1, "rigid"): (2.3, 4.5, 7.1), (1, "flexible"): (3.5, 7.1, 11.0),
    (2, "rigid"): (1.4, 2.8, 4.5), (2, "flexible"): (2.3, 4.5, 7.1),
}
COVERED = {"electric_motor", "fan_blower", "compressor", "conveyor", "rolls_mills", "turbofan", "variable_speed_coupling"}
EXCLUDED = {
    "rotordynamic_pump": "rotordynamic or close-coupled pump: assessed under ISO 10816-7 (not implemented)",
    "reciprocating_engine": "reciprocating machine: assessed under ISO 10816-6 (not implemented)",
    "submerged_pump": "submerged motor-pump: outside ISO 20816-3",
    "screw_compressor": "rotary positive-displacement compressor: outside ISO 20816-3",
}
LEVELS = ["Low", "Moderate", "High"]


def iso_assessment(meas: dict, asset: dict) -> dict:
    out = {"applicable": False, "zone": None, "label": None, "group": None, "confidence": None,
           "standard": "ISO 20816-3:2022", "note": "zone limits from secondary sources (Annex A not verified)"}
    mtype, kw, rpm = asset.get("machine_type"), asset.get("rated_kw"), asset.get("rated_rpm")
    coupling, support = asset.get("coupling", "unknown"), asset.get("support", "unknown")
    if not config.AMPLITUDE_VALIDATED:
        out["label"] = "ISO zone not shown: absolute amplitude not yet validated (frequency + trend mode)"
        return out
    if meas.get("result_class") not in ("RELIABLE", "LOWER_BOUND"):
        out["label"] = "ISO zone not assessed: measurement is " + str(meas.get("result_class")).lower().replace("_", " ")
        return out
    if not mtype or mtype == "unknown" or kw in (None, ""):
        out["label"] = "ISO zone not assessed: machine type/power unknown"
        return out
    if mtype in EXCLUDED:
        out["label"] = "ISO 20816-3 not applicable (" + EXCLUDED[mtype] + ")"
        return out
    if mtype not in COVERED:
        out["label"] = "ISO 20816-3 not applicable (machine type not covered)"
        return out
    kw = float(kw)
    if kw <= 15:
        out["label"] = "ISO 20816-3 not applicable (rated power 15 kW or less)"
        return out
    if rpm and not (120 <= float(rpm) <= 30000):
        out["label"] = "ISO 20816-3 not applicable (speed outside 120-30,000 rpm)"
        return out
    if mtype == "electric_motor" and coupling != "flexible":
        out["label"] = "ISO 20816-3 zone not assessed: motor is not flexibly coupled (assess with the driven machine's part)"
        return out
    if mtype == "fan_blower" and kw <= 300 and support != "rigid":
        out["label"] = "ISO 20816-3 not applicable (fan <= 300 kW not rigidly supported, Note 3)"
        return out
    group = 1 if kw > 300 else 2
    v = meas["v_band_rms_mm_s"]
    lb = meas["result_class"] == "LOWER_BOUND"

    def zone(lim):
        return "A" if v < lim[0] else "B" if v < lim[1] else "C" if v < lim[2] else "D"

    supports = [support] if support in ("rigid", "flexible") else ["rigid", "flexible"]
    zones = {s: zone(ZONES[(group, s)]) for s in supports}
    band = f"{meas['band_hz'][0]:.0f}-{meas['band_hz'][1]:.0f} Hz"
    if len(zones) == 1:
        z = next(iter(zones.values()))
        text = (f"At least Zone {z} (lower bound)" if lb else f"Estimated Zone {z}")
    else:
        text = ("At least " if lb else "Estimated ") + " / ".join(f"Zone {z} if {s}" for s, z in zones.items())
    out.update(applicable=True, group=group, zone=zones, confidence="Moderate" if not lb else "Low",
               label=f"{text}: partial-band ({band}) measurement, not a compliance test")
    out["boundary_bc"] = {s: ZONES[(group, s)][1] for s in supports}
    return out


def fault_pattern(meas: dict, view: str = "radial", conflict: bool = False) -> dict:
    """Heuristic pattern on displacement harmonics; always 'suspected'."""
    if meas.get("result_class") in (None, "INCONCLUSIVE", "BELOW_DETECTION_LIMIT"):
        return {"pattern": None, "withheld_reason": "no valid measurement", "evidence": [], "confidence": None}
    if conflict or meas.get("f1x_source", "").startswith("assumed"):
        return {"pattern": None, "evidence": [], "confidence": None,
                "withheld_reason": "shaft speed (1x) is assumed or conflicting; confirm the rpm first"}
    a = {k: (v or 0.0) for k, v in meas["amp_mm"].items()}
    a1, a2, a3, ah = a["1"], a["2"], a["3"], a["0.5"]
    # compare in velocity terms (energy at higher orders matters more for velocity)
    v1, v2, v3 = a1, 2 * a2, 3 * a3
    tot = v1 ** 2 + v2 ** 2 + v3 ** 2 + 1e-30
    ev = [f"2x is {100*a2/a1:.0f}% of 1x, 3x is {100*a3/a1:.0f}% of 1x, 0.5x is {100*ah/a1:.0f}% of 1x (displacement)"]
    if meas.get("unexplained_peaks_hz"):
        ev.append(f"peaks not explained by shaft orders: {meas['unexplained_peaks_hz']} Hz")
    harmonics_strong = sum(x > 0.2 * a1 for x in (a2, a3)) >= 2 or ah > 0.2 * a1
    if harmonics_strong and a3 > 0.2 * a1:
        p = "looseness pattern"
    elif a2 >= 0.5 * a1:
        p = "misalignment pattern" if view == "axial" else "1x+2x pattern (misalignment or looseness; axial view needed)"
    elif v1 ** 2 / tot >= 0.8:
        p = "imbalance pattern" if view != "axial" else "1x axial pattern (check misalignment / bent shaft)"
    else:
        p = "mixed pattern"
    conf = "Moderate" if meas.get("snr_1x", 0) >= 10 and not meas.get("unexplained_peaks_hz") else "Low"
    # A spectral pattern is not a fault by itself: every healthy machine has some 1x (residual imbalance).
    # It is only called "suspected <fault>" once there is severity evidence (zone C/D or a significant
    # comparable increase) -> see suspect().
    return {"pattern": f"Spectrum shape: {p.replace(' pattern', '')}-type", "pattern_type": p, "evidence": ev,
            "confidence": conf, "withheld_reason": None, "suspected": False,
            "ambiguous_axial": p.startswith("1x+2x")}


def suspect(fault: dict, why: str) -> dict:
    """Upgrade a spectral pattern to a suspected fault when there is severity evidence."""
    if fault.get("pattern_type"):
        fault = {**fault, "suspected": True, "pattern": f"Suspected {fault['pattern_type']}",
                 "evidence": fault["evidence"] + [why]}
    return fault


def confidence(probe: dict, quality: dict, meas: dict) -> dict:
    lvl = 2
    reasons = []
    for f, why in [("timing_not_confirmed", "timing from file metadata only (phone model not verified)"),
                   ("dropped_frames", "some frames dropped"), ("low_bitrate", "strong video compression"),
                   ("rolling_shutter_risk", "markers at different heights in the picture")]:
        if f in (probe.get("flags", []) + quality.get("flags", [])):
            lvl -= 1; reasons.append(why)
    if meas.get("f1x_source", "").startswith("assumed"):
        lvl -= 1; reasons.append("shaft speed assumed from the largest peak")
    if meas.get("snr_1x", 0) < config.T["snr_reliable"]:
        lvl -= 1; reasons.append("weak signal")
    return {"frequency": LEVELS[max(lvl, 0)], "reasons": reasons}


def diagnose(probe: dict, quality: dict, meas: dict, asset: dict, view: str = "radial", conflict: bool = False) -> dict:
    iso = iso_assessment(meas, asset)
    fault = fault_pattern(meas, view, conflict)
    if iso.get("applicable") and set((iso.get("zone") or {}).values()) & {"C", "D"}:
        fault = suspect(fault, "estimated level in ISO zone C/D")
    conf = confidence(probe, quality, meas)
    limitations = [
        f"Measured band {meas['band_hz'][0]:.0f}-{meas['band_hz'][1]:.0f} Hz only (ISO uses 10-1000 Hz); "
        "content above the camera's limit is missing or folded in.",
        "Single camera view: motion towards/away from the camera is not measured.",
        "Fault patterns are screening heuristics, not a confirmed diagnosis.",
    ]
    if not config.AMPLITUDE_VALIDATED:
        limitations.insert(0, "Absolute vibration level is not yet validated against an accelerometer; "
                              "use frequency and relative change between comparable recordings.")
    return {"iso": iso, "fault": fault, "confidence": conf, "limitations": limitations,
            "display_mode": "absolute" if config.AMPLITUDE_VALIDATED else "trend"}
