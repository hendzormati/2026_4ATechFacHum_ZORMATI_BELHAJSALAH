# src/sensors/hrv_analyzer.py
"""Heart Rate Variability (HRV) analyzer.

Computes HRV metrics from inter-beat intervals (IBIs) to quantify parasympathetic
nervous system activity. HRV is a key indicator of stress response and cognitive load.
Low HRV indicates stress/overload; high HRV indicates relaxation.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional

import config


@dataclass
class HRVMetrics:
    """Heart Rate Variability metrics.
    
    Attributes:
        rmssd: Root Mean Square of Successive Differences in milliseconds.
               Measures beat-to-beat variability (parasympathetic marker).
        sdnn: Standard Deviation of NN intervals in milliseconds.
              Measures overall HRV across the window.
        mean_ibi: Mean inter-beat interval in milliseconds.
        mean_hr: Mean heart rate in beats per minute (60000 / mean_ibi).
    """
    rmssd: float
    sdnn: float
    mean_ibi: float
    mean_hr: float


class HRVAnalyzer:
    """Analyze Heart Rate Variability from inter-beat interval data.
    
    Implements standard HRV metrics used in clinical and research settings.
    Requires minimum 5 IBIs for reliable calculation.
    """

    def __init__(self, window_size: int = 60) -> None:
        """Initialize HRV analyzer.
        
        Args:
            window_size: Analysis window in seconds. Larger windows give
                        more stable metrics but lag real-time detection.
                        Default 60s matches config.HRV_WINDOW_SIZE.
        """
        self.window_size = window_size
        self._min_ibi_count = 5

    def compute_rmssd(self, ibi_values: List[float]) -> Optional[float]:
        """Compute RMSSD (Root Mean Square of Successive Differences).
        
        Measures beat-to-beat variability, primarily reflecting parasympathetic
        (vagal) nervous system tone. High RMSSD indicates relaxation; low RMSSD
        indicates stress/cognitive load.
        
        Formula:
            successive_diffs = [ibi[i+1] - ibi[i] for i in range(len(ibi)-1)]
            rmssd = sqrt(mean(diff^2 for diff in successive_diffs))
        
        Args:
            ibi_values: List of inter-beat intervals in milliseconds.
        
        Returns:
            RMSSD in milliseconds, or None if insufficient data (<5 IBIs).
        """
        if len(ibi_values) < self._min_ibi_count:
            return None
        
        ibi_array = np.array(ibi_values)
        
        # Calculate successive differences
        successive_diffs = np.diff(ibi_array)
        
        # RMSSD = sqrt(mean(diff^2))
        rmssd = float(np.sqrt(np.mean(successive_diffs ** 2)))
        
        return rmssd

    def compute_sdnn(self, ibi_values: List[float]) -> Optional[float]:
        """Compute SDNN (Standard Deviation of NN intervals).
        
        Measures overall variability across the entire window.
        Reflects both parasympathetic and sympathetic influences.
        
        Formula: sdnn = std(ibi_values)
        
        Args:
            ibi_values: List of inter-beat intervals in milliseconds.
        
        Returns:
            SDNN in milliseconds, or None if insufficient data (<5 IBIs).
        """
        if len(ibi_values) < self._min_ibi_count:
            return None
        
        ibi_array = np.array(ibi_values)
        sdnn = float(np.std(ibi_array))
        
        return sdnn

    def compute_metrics(self, ibi_values: List[float]) -> Optional[HRVMetrics]:
        """Compute all HRV metrics from IBI data.
        
        Args:
            ibi_values: List of inter-beat intervals in milliseconds.
        
        Returns:
            HRVMetrics object with all metrics, or None if insufficient data.
        """
        if len(ibi_values) < self._min_ibi_count:
            return None
        
        ibi_array = np.array(ibi_values)
        
        # Compute RMSSD
        rmssd = self.compute_rmssd(ibi_values)
        if rmssd is None:
            return None
        
        # Compute SDNN
        sdnn = self.compute_sdnn(ibi_values)
        if sdnn is None:
            return None
        
        # Compute mean IBI
        mean_ibi = float(np.mean(ibi_array))
        
        # Compute mean heart rate (BPM)
        if mean_ibi > 0:
            mean_hr = 60000.0 / mean_ibi
        else:
            return None
        
        return HRVMetrics(
            rmssd=rmssd,
            sdnn=sdnn,
            mean_ibi=mean_ibi,
            mean_hr=mean_hr
        )

    def compute_hrv_drop(
        self,
        current_rmssd: float,
        baseline_rmssd: float
    ) -> float:
        """Compute HRV drop percentage from baseline.
        
        Quantifies how much HRV has decreased from calibration baseline.
        Used as key metric for cognitive load detection:
        - 20-40% drop: significant cognitive load
        - >40% drop: cognitive overload
        
        Formula: drop% = ((baseline - current) / baseline) × 100
        
        Args:
            current_rmssd: Current RMSSD value in milliseconds.
            baseline_rmssd: Baseline RMSSD from calibration in milliseconds.
        
        Returns:
            HRV drop as percentage (0-100+). Negative value means HRV increased.
        """
        if baseline_rmssd == 0.0:
            return 0.0
        
        drop_percent = ((baseline_rmssd - current_rmssd) / baseline_rmssd) * 100.0
        
        return drop_percent