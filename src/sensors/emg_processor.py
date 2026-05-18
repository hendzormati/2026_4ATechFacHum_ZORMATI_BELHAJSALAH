"""EMG (Electromyography) signal processor.

Processes raw EMG data, computes RMS-based metrics, and detects muscle contractions.
EMG indicates stress through muscle tension and jaw clenching.
"""

import numpy as np
from collections import deque
from typing import Optional

import config


class EMGProcessor:
    """Process EMG (Electromyography) signal from port 1.
    
    Detects muscle tension through RMS calculation and classifies contraction
    levels based on baseline RMS noise. EMG is a key indicator of cognitive
    load and stress-induced muscle tension.
    """

    def __init__(self, rms_baseline: float) -> None:
        """Initialize EMG processor with baseline RMS noise level.
        
        Args:
            rms_baseline: Baseline RMS value computed during calibration.
                         Represents normal muscle resting noise level.
        """
        self.rms_baseline = rms_baseline
        self._window: deque = deque(maxlen=50)  # 0.5s at 100Hz

    def process_raw(self, raw_value: int) -> float:
        """Convert raw ADC value to rectified EMG amplitude.
        
        Rectification (taking absolute value) is the first step in EMG
        processing. Subsequent RMS calculation amplifies contractions.
        
        Args:
            raw_value: Raw 16-bit ADC value (0-65535).
        
        Returns:
            Rectified EMG value (always positive).
        """
        # EMG values oscillate around ~512 (midpoint of 16-bit ADC)
        # Rectify by taking absolute deviation from baseline
        baseline_offset = 512
        deviation = abs(raw_value - baseline_offset)
        
        # Add to sliding window
        self._window.append(float(deviation))
        
        return deviation

    def compute_rms(self) -> float:
        """Compute RMS (Root Mean Square) of current window.
        
        RMS amplifies muscle contraction signals and is more robust than
        peak detection for detecting sustained tension.
        
        Formula: sqrt(mean(window^2))
        
        Returns:
            RMS value. Returns 0 if window empty.
        """
        if len(self._window) == 0:
            return 0.0
        
        window_array = np.array(list(self._window))
        rms = float(np.sqrt(np.mean(window_array ** 2)))
        return rms

    def compute_tension_index(self) -> float:
        """Compute EMG tension index: current_rms / rms_baseline.
        
        Normalized metric comparing current muscle tension to baseline noise.
        Values > 1.0 indicate muscle contraction above rest level.
        
        Formula: compute_rms() / rms_baseline
        
        Returns:
            Tension index (typically 0.5-15 for full range of contractions).
        """
        current_rms = self.compute_rms()
        
        if self.rms_baseline == 0.0:
            return 0.0
        
        return current_rms / self.rms_baseline

    def detect_contraction(self) -> str:
        """Detect muscle contraction level based on RMS.
        
        Classification uses multipliers of baseline RMS:
        - rest: < 3× baseline (normal resting noise)
        - light: 3-8× baseline (light voluntary contraction)
        - strong: > 8× baseline (strong contraction or sustained stress)
        
        Returns:
            One of "rest", "light", "strong".
        """
        tension = self.compute_tension_index()
        
        if tension < config.EMG_THRESHOLD_LIGHT:
            return "rest"
        elif tension < config.EMG_THRESHOLD_STRONG:
            return "light"
        else:
            return "strong"