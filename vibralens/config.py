"""Central configuration. All thresholds are initial values (workflow.md Â§A5.5, Â§B5.3):
they are tuned on the development recordings and then frozen before the reported evaluation."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("VL_DATA_DIR", ROOT / "data_local"))
PHONE_PROFILES = Path(os.environ.get("VL_PHONE_PROFILES", ROOT / "phone_profiles.json"))

BACKEND = os.environ.get("VL_BACKEND", "local")            # "local" (filesystem) | "aws" (S3 + DynamoDB)
AWS_REGION = os.environ.get("VL_AWS_REGION", "ap-south-1")
BUCKET = os.environ.get("VL_BUCKET", "")
TABLE_PREFIX = os.environ.get("VL_TABLE_PREFIX", "vl_")
SNS_TOPIC_ARN = os.environ.get("VL_SNS_TOPIC_ARN", "")
PUBLIC_BASE_URL = os.environ.get("VL_PUBLIC_BASE_URL", "http://localhost:8000")
ORIGIN_SECRET = os.environ.get("VL_ORIGIN_SECRET", "")   # set on AWS: only CloudFront may reach the origin

# Agent: empty model id -> deterministic rule planner only.
BEDROCK_MODEL_ID = os.environ.get("VL_BEDROCK_MODEL_ID", "")
BEDROCK_REGION = os.environ.get("VL_BEDROCK_REGION", AWS_REGION)

# Gate G3 (workflow.md Â§A8). Until real-world amplitude validation passes, the app runs in
# "frequency + relative-trend" mode: no absolute mm/s values and no ISO zones are shown.
AMPLITUDE_VALIDATED = os.environ.get("VL_AMPLITUDE_VALIDATED", "false").lower() == "true"

MACHINE_ID, REF_ID = 1, 7

T = {
    # timing
    "tag_ratio_tol": 0.02, "jitter_max_frac": 0.10, "dropped_warn": 0.01, "dropped_max": 0.05,
    "min_capture_fps": 100.0,
    # capture quality
    "marker_px_min": 80.0, "detect_rate_min": 0.90, "blur_min": 0.12, "exposure_mean_min": 40.0,
    "clip_frac_max": 0.60, "exposure_mean_max": 235.0, "tilt_ratio_min": 0.87, "camera_motion_rms_max_px": 2.0,
    "ref_fit_residual_max_px": 0.10, "ref_moving_ratio": 0.30, "row_offset_max_frac": 0.10,
    "scale_osc_max": 0.002, "dup_frac_max": 0.10, "interp_ratio_warn": 1.6,
    # measurement
    "px_amp_reliable": 0.30, "bpp_reliable": 0.05, "snr_detect": 3.0, "snr_reliable": 10.0,
    "min_segment_s": 4.0, "max_gap_frames": 3, "f_lo": 10.0, "f_hi_frac": 0.40, "f_hi_max": 1000.0,
    "f1x_search": (8.0, 60.0), "rpm_tol": 0.05, "harmonic_tol": 0.02, "analysis_max_s": 10.0,
    # agent limits
    "max_recaptures": 3, "max_evidence_requests": 2, "max_llm_turns": 12,
    "user_wait_hours": 24, "approval_hours": 72,
    # comparison
    "cmp_fs_tol": 0.05, "cmp_f1x_tol": 0.05, "cmp_scale_tol": 0.30, "relative_change_heuristic": 0.50,
}

# Upload limits (workflow.md Â§B7.3)
MAX_VIDEO_BYTES = 300 * 1024 * 1024
MAX_PHOTO_BYTES = 15 * 1024 * 1024
MAX_DURATION_S, MAX_FRAMES, MAX_W, MAX_H = 30.0, 8000, 3840, 2160
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime"}
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png"}
JOBS_PER_HOUR = 20

