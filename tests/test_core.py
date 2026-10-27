"""Unit tests for the measurement science, timing, diagnosis and policy (no video decoding needed)."""
import numpy as np
import pytest

from vibralens import config, diagnose, markers, policy, signal as sig, video


# ---------------- signal maths (workflow.md Â§A5.4) ----------------
@pytest.mark.parametrize("f0,A", [(24.3, 0.02), (24.77, 0.05), (49.6, 0.01), (12.1, 0.1)])
def test_tone_and_band_velocity(f0, A):
    rng = np.random.default_rng(0)
    fs, dur = 240.0, 10.0
    t = np.arange(0, dur, 1 / fs) + rng.normal(0, 3e-4, int(dur * fs))
    t.sort()
    x = A * np.sin(2 * np.pi * f0 * t) + 0.3 * A * np.sin(2 * np.pi * 2 * f0 * t) + 0.05 * t + rng.normal(0, A * 0.05, t.size)
    x[rng.random(t.size) < 0.01] = np.nan
    _, xu = sig.to_slots(t, x, fs)
    xu = xu[sig.longest_segment(xu)]
    fp, ap = sig.tone(xu, fs, f_hint=f0)
    v = sig.velocity_rms(xu, fs)
    hi = 0.4 * fs
    v_true = np.sqrt((2 * np.pi * f0 * A) ** 2 / 2 + ((2 * np.pi * 2 * f0 * 0.3 * A) ** 2 / 2 if 2 * f0 <= hi else 0))
    assert abs(fp - f0) < 0.02
    assert abs(ap - A) / A < 0.02
    assert abs(v - v_true) / v_true < 0.05


def test_rms_relation():
    # 2.8 mm/s RMS at 25 Hz -> 25.2 um peak displacement
    assert round(2.8 * np.sqrt(2) / (2 * np.pi * 25) * 1000, 1) == 25.2


def test_long_gap_splits_segment():
    fs = 240.0
    t = np.arange(0, 8, 1 / fs)
    x = np.sin(2 * np.pi * 20 * t)
    x[960:980] = np.nan                     # 20-frame gap > max_gap -> must not be interpolated
    _, xu = sig.to_slots(t, x, fs)
    seg = sig.longest_segment(xu)
    assert np.isnan(xu[965])
    assert (seg.stop - seg.start) / fs > 3.9


def test_noise_correction_and_dl():
    rng = np.random.default_rng(1)
    fs = 240.0
    t = np.arange(0, 10, 1 / fs)
    x = 0.01 * np.sin(2 * np.pi * 24.3 * t) + rng.normal(0, 0.004, t.size)
    v, nev = sig.velocity_rms(x, fs), sig.noise_equivalent_velocity(x, fs)
    vc = sig.corrected_band_rms(v, nev)
    true = 2 * np.pi * 24.3 * 0.01 / np.sqrt(2)
    assert abs(vc - true) / true < 0.15 and v > vc
    assert sig.tonal_dl(x, fs, 24.3) < true


def test_result_classes():
    assert sig.result_class(2, 1, 0.2, "PROBABLE", True, [])[0] == "BELOW_DETECTION_LIMIT"
    assert sig.result_class(50, 0.1, 0.2, "PROBABLE", True, [])[0] == "LOWER_BOUND"
    assert sig.result_class(50, 0.5, 0.01, "PROBABLE", True, [])[0] == "LOWER_BOUND"
    assert sig.result_class(50, 0.5, 0.2, "PROBABLE", True, [])[0] == "RELIABLE"
    assert sig.result_class(50, 0.5, 0.2, "PROBABLE", False, [])[0] == "INCONCLUSIVE"
    assert sig.result_class(50, 0.5, 0.2, "PROBABLE", True, ["x"])[0] == "INCONCLUSIVE"


# ---------------- timing (workflow.md Â§B5.1) ----------------
def test_timing_status_rules():
    assert video.timing_status(240, 240, None)[:3] == ("PROBABLE", 240, 1.0)
    st, fps, scale, _ = video.timing_status(240, 30, None)
    assert (st, fps, scale) == ("PROBABLE", 240, 1 / 8)
    assert video.timing_status(None, 30, None)[0] == "UNRELIABLE"          # cannot know if slowed
    assert video.timing_status(None, 240, None)[0] == "PROBABLE"
    assert video.timing_status(240, 100, None)[0] == "UNRELIABLE"          # inconsistent tag
    prof = {"capture_fps": 240, "stored_fps": 30}
    assert video.timing_status(None, 30, prof)[:3] == ("PROBABLE", 240.0, 0.125)
    assert video.timing_status(240, 240, prof)[0] == "CONFIRMED"


@pytest.mark.parametrize("tag,pts", [(240, 0), (240, float('nan')), (float('inf'), 240), (-1, 240)])
def test_invalid_timing_is_rejected(tag, pts):
    assert video.timing_status(tag, pts, None)[0] == "UNRELIABLE"


def test_rejected_video_always_blocks_agent():
    p = video._reject({"flags": [], "reasons": []}, "unsupported_codec", "unsupported")
    s = policy.new_session("s", "w", {"asset_id": "a"}, "P1", "radial", 40, "u")
    s.update(stage="probed", probe=p)
    assert policy.options(s, False)[0][0] == "request_recapture"


def test_slot_stats_detects_jitter_and_drops():
    fs = 240.0
    t = np.arange(0, 5, 1 / fs)
    assert video.slot_stats(t, fs)[1] < 0.01
    t2 = np.delete(t, np.arange(0, len(t), 10))                            # 10% dropped
    assert video.slot_stats(t2, fs)[2] > 0.08


# ---------------- camera compensation (workflow.md Â§B5.2) ----------------
def _square(c, s, ang=0.0):
    pts = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]], float) * s / 2
    R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
    return pts @ R.T + c


def test_similarity_compensation_removes_roll_zoom_translation():
    n, fs, f0, amp = 1200, 240.0, 24.3, 0.4
    t = np.arange(n) / fs
    rng = np.random.default_rng(2)
    Cm, Cr = np.zeros((n, 4, 2)), np.zeros((n, 4, 2))
    for i in range(n):
        ang = np.deg2rad(0.5) * np.sin(2 * np.pi * 1.3 * t[i])          # camera roll
        z = 1 + 0.01 * np.sin(2 * np.pi * 0.7 * t[i])                     # zoom / focus breathing
        tr = np.array([3 * np.sin(2 * np.pi * 2.1 * t[i]), 2 * np.cos(2 * np.pi * 1.7 * t[i])])
        R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]]) * z
        m = _square(np.array([300 + amp * np.sin(2 * np.pi * f0 * t[i]), 300.0]), 150)
        r = _square(np.array([650.0, 300.0]), 150)
        Cm[i] = m @ R.T + tr + rng.normal(0, 0.01, (4, 2))
        Cr[i] = r @ R.T + tr + rng.normal(0, 0.01, (4, 2))
    cen, res, cam = markers.compensate(Cm, Cr)
    x = cen[:, 0] - cen[:, 0].mean()
    raw = Cm.mean(1)[:, 0]
    a_comp = sig.tone(x, fs, f_hint=f0)[1]
    assert abs(a_comp - amp) / amp < 0.05
    assert np.nanmedian(res) < 0.05
    assert np.std(raw - raw.mean()) > 5 * np.std(x)                      # camera motion was large and is removed


def test_valid_quads_rejects_bad():
    good = np.array([_square(np.array([100.0, 100.0]), 80)] * 10)
    bad = good.copy()
    bad[3] = [[0, 0], [80, 0], [0, 80], [80, 80]]                          # self-intersecting
    bad[5] *= 1.5                                                          # area jump
    ok = markers.valid_quads(bad)
    assert ok.sum() == 8 and not ok[3] and not ok[5]


# ---------------- ISO applicability (workflow.md Â§B5.5; scope from the official preview) ----------------
M = {"result_class": "RELIABLE", "v_band_rms_mm_s": 3.0, "band_hz": [10, 96]}


@pytest.fixture
def validated(monkeypatch):
    monkeypatch.setattr(config, "AMPLITUDE_VALIDATED", True)


def test_iso_not_shown_without_validation(monkeypatch):
    monkeypatch.setattr(config, "AMPLITUDE_VALIDATED", False)
    r = diagnose.iso_assessment(M, {"machine_type": "electric_motor", "coupling": "flexible", "rated_kw": 45})
    assert not r["applicable"] and "not yet validated" in r["label"]


@pytest.mark.parametrize("asset,expect", [
    ({"machine_type": "fan_blower", "rated_kw": 0.06, "support": "flexible"}, "15 kW"),
    ({"machine_type": "rotordynamic_pump", "rated_kw": 45}, "10816-7"),
    ({"machine_type": "reciprocating_engine", "rated_kw": 30}, "10816-6"),
    ({"machine_type": "unknown", "rated_kw": 45}, "unknown"),
    ({"machine_type": "electric_motor", "rated_kw": None}, "unknown"),
    ({"machine_type": "electric_motor", "rated_kw": 45, "coupling": "rigid"}, "not flexibly coupled"),
    ({"machine_type": "fan_blower", "rated_kw": 90, "support": "flexible"}, "Note 3"),
])
def test_iso_not_applicable(validated, asset, expect):
    r = diagnose.iso_assessment(M, asset)
    assert not r["applicable"] and expect in r["label"]


def test_iso_zone_group2_rigid_and_unknown_support(validated):
    a = {"machine_type": "electric_motor", "coupling": "flexible", "rated_kw": 45, "rated_rpm": 1480, "support": "rigid"}
    r = diagnose.iso_assessment(M, a)
    assert r["applicable"] and r["group"] == 2 and r["zone"] == {"rigid": "C"} and "Estimated Zone C" in r["label"]
    a["support"] = "unknown"
    r = diagnose.iso_assessment(M, a)
    assert r["zone"] == {"rigid": "C", "flexible": "B"}                    # both shown, none picked silently
    r = diagnose.iso_assessment({**M, "result_class": "LOWER_BOUND"}, {**a, "support": "rigid"})
    assert r["label"].startswith("At least Zone C") and r["confidence"] == "Low"


def test_fault_withheld_when_1x_assumed():
    m = {"result_class": "RELIABLE", "f1x_source": "assumed (largest peak)", "amp_mm": {"0.5": 0, "1": 0.05, "2": 0.005, "3": 0}}
    assert diagnose.fault_pattern(m)["pattern"] is None


def test_fault_imbalance_pattern():
    m = {"result_class": "RELIABLE", "f1x_source": "rpm", "snr_1x": 50, "unexplained_peaks_hz": [],
         "amp_mm": {"0.5": 0.0, "1": 0.05, "2": 0.004, "3": 0.001}}
    f = diagnose.fault_pattern(m)
    assert "imbalance" in f["pattern"] and not f["suspected"] and not f["pattern"].startswith("Suspected")
    assert diagnose.suspect(f, "x")["pattern"] == "Suspected imbalance pattern"


# ---------------- policy (workflow.md Â§B6.2) ----------------
def _sess(**kw):
    s = policy.new_session("s1", "w", {"asset_id": "a"}, "P1", "radial", 40, "u1")
    s.update(kw)
    return s


def test_policy_recapture_order_and_limit():
    s = _sess(stage="assessed", probe={"flags": []}, quality={"flags": ["ref_missing", "marker_too_small"]})
    o = policy.options(s, False)
    assert o[0] == ("request_recapture", {"reason_code": "marker_too_small"})   # most fundamental first
    s["recaptures"] = config.T["max_recaptures"]
    assert policy.options(s, False) == [("finish", {"outcome": "inconclusive"})]


def test_policy_timing_unreliable_never_measures():
    s = _sess(stage="probed", probe={"flags": ["timing_unreliable"]})
    assert policy.options(s, False)[0][0] == "request_recapture"


def test_policy_asks_rpm_once_then_diagnoses():
    s = _sess(stage="measured", quality={"flags": []}, measurement={"result_class": "LOWER_BOUND", "f1x_source": "assumed"})
    assert policy.options(s, False)[0] == ("ask_user", {"kind": "rpm"})
    s["asked"].append("rpm")
    assert policy.options(s, False)[0][0] == "diagnose"


def test_policy_work_order_only_with_comparable_increase():
    s = _sess(stage="diagnosed", compared=True, diagnosis={"iso": {"applicable": False}, "fault": {}},
              measurement={"result_class": "LOWER_BOUND"}, comparison={"comparable": False, "significant_increase": True})
    assert policy.options(s, True)[0][0] == "finish"
    s["comparison"] = {"comparable": True, "significant_increase": True}
    assert policy.options(s, True) == [("draft_work_order", {})]


