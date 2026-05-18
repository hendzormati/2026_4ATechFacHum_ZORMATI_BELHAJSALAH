"""
Configuration module for IQ Overload application.

Centralizes all constants and configuration parameters for BITalino connection,
sensor acquisition, visualization, calibration, and cognitive load analysis.

All paths are relative to project root. All timing values are in seconds unless
specified otherwise. All frequencies are in Hz.
"""

from typing import Dict, List

# ============================================================================
# BITALINO CONFIGURATION
# ============================================================================

BITALINO_MAC_ADDRESS: str = "98:D3:71:FE:4F:90"
"""MAC address of the BITalino device."""

SAMPLING_RATE: int = 100
"""Acquisition frequency in Hz."""

ACTIVE_PORTS: List[int] = [1, 2, 3, 4, 6]
"""Active sensor ports: EMG (1), EDA (2), ACC (3), FSR (4), PPG (6)."""

RESOLUTION: int = 16
"""ADC resolution in bits."""

MAX_RECONNECTION_ATTEMPTS: int = 3
"""Maximum number of automatic reconnection attempts."""

RECONNECTION_DELAY: float = 2.0
"""Delay between reconnection attempts in seconds."""

# ============================================================================
# PORT MAPPING
# ============================================================================

PORT_MAPPING: Dict[int, str] = {
    1: "EMG",
    2: "EDA",
    3: "ACC",
    4: "FSR",
    6: "PPG",
}
"""Maps BITalino port numbers to sensor names."""

# ============================================================================
# CALIBRATION SETTINGS
# ============================================================================

CALIBRATION_DURATION: int = 20
"""Baseline calibration duration in seconds."""

CALIBRATION_SAMPLES: int = SAMPLING_RATE * CALIBRATION_DURATION
"""Total number of samples during calibration (2000 at 100 Hz)."""

# ============================================================================
# VISUALIZATION SETTINGS
# ============================================================================

PLOT_WINDOW_DURATION: int = 10
"""Rolling window duration for sensor plots in seconds."""

PLOT_UPDATE_INTERVAL: int = 1000
"""Matplotlib animation update interval in milliseconds."""

PLOT_NAMES: Dict[str, str] = {
    "EMG": "EMG : Contraction musculaire",
    "EDA": "EDA : Activité électrodermale",
    "ACC": "ACC : Micro-mouvements",
    "FSR": "FSR : Pression appliquée",
    "PPG": "PPG : Rythme cardiaque optique",
}
"""Display names for each sensor."""

# ============================================================================
# COGNITIVE LOAD INDEX (CCI) WEIGHTS
# ============================================================================

CCI_WEIGHTS: Dict[str, float] = {
    "eda": 0.35,
    "hrv": 0.35,
    "acc": 0.15,
    "emg": 0.15,
}
"""Weights for CCI composite score calculation."""

# ============================================================================
# SENSOR THRESHOLDS (baseline-relative)
# ============================================================================

EDA_THRESHOLD_NORMAL: float = 1.0
"""EDA normal threshold: within 1 std from baseline."""

EDA_THRESHOLD_MODERATE: float = 2.0
"""EDA moderate stress threshold: mean + 2*std."""

EDA_THRESHOLD_HIGH: float = 3.0
"""EDA high stress threshold: mean + 3*std (overload beyond this)."""

EMG_THRESHOLD_LIGHT: float = 3.0
"""EMG light contraction threshold: rms_baseline * 3."""

EMG_THRESHOLD_STRONG: float = 8.0
"""EMG strong contraction threshold: rms_baseline * 8."""

EMG_THRESHOLD_TARGET: float = 5.0
"""EMG target contraction threshold for challenges: rms_baseline * 5."""

ACC_THRESHOLD_AGITATION: float = 2.0
"""ACC agitation threshold: mean + 2*std."""

ACC_THRESHOLD_MOVEMENT: float = 4.0
"""ACC significant movement threshold: mean + 4*std."""

FSR_THRESHOLD_PRESS: int = 20
"""FSR press detection threshold: baseline + 20 ADC units."""

# ============================================================================
# CCI OVERLOAD DETECTION
# ============================================================================

CCI_OVERLOAD_THRESHOLD: float = 7.0
"""CCI threshold for cognitive overload detection (0-10 scale)."""

CCI_OVERLOAD_DURATION: float = 3.0
"""Minimum duration above threshold to detect tipping point (seconds)."""

CCI_BASELINE_MULTIPLIER: float = 2.0
"""Round-based detection: tipping point if CCI_mean > round1_mean * factor."""

# ============================================================================
# HEART RATE VARIABILITY (HRV) SETTINGS
# ============================================================================

HRV_WINDOW_SIZE: int = 60
"""Analysis window for HRV metrics in seconds."""

HRV_DROP_SIGNIFICANT: float = 20.0
"""Significant HRV drop threshold in percent."""

HRV_DROP_OVERLOAD: float = 40.0
"""HRV drop threshold indicating cognitive overload in percent."""

# ============================================================================
# DATA STORAGE PATHS
# ============================================================================

DATA_DIR: str = "data"
"""Directory for session data (baseline, CSV, events)."""

REPORTS_DIR: str = "reports"
"""Directory for generated HTML reports."""

BASELINE_PREFIX: str = "baseline_"
"""Prefix for baseline JSON files: baseline_YYYYMMDD_HHMMSS.json."""

SESSION_PREFIX: str = "session_"
"""Prefix for session data directories: session_YYYYMMDD_HHMMSS."""

REPORT_PREFIX: str = "report_"
"""Prefix for report HTML files: report_YYYYMMDD_HHMMSS.html."""