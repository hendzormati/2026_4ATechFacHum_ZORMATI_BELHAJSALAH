# src/sensors/acc_processor.py
"""ACC (Accelerometer) signal processor.

Processes raw accelerometer data to detect micro-movements and agitation.
ACC indicates stress through involuntary movements and body tension.
Single-axis simplified implementation for Phase 1.
"""

import numpy as np
from collections import deque
from typing import Optional

import config


class ACCProcessor:
    """Process ACC (Accelerometer) signal from port 3.
    
    Detects micro-movements and agitation patterns indicative of cognitive
    load. Single-axis implementation analyzes acceleration magnitude relative
    to baseline rest state.
    """

    def __init__(self, baseline_mean: float, baseline_std: float) -> None:
        """Initialize ACC processor with baseline statistics.
        
        Args:
            baseline_mean: Mean acceleration value during rest (calibration).
            baseline_std: Standard deviation of acceleration during rest.
        """
        self.baseline_mean = baseline_mean
        self.baseline_std = baseline_std
        self._smoothing_window: deque = deque(maxlen=20)  # 0.2s at 100Hz

    def process_raw(self, raw_value: int) -> float:
        """Convert raw ADC value to smoothed acceleration magnitude.
        
        Applies moving average filter over 20 samples (0.2 seconds) to reduce
        noise while preserving movement information. Single-axis implementation
        treats raw value directly as magnitude.
        
        Args:
            raw_value: Raw 16-bit ADC value (0-65535).
        
        Returns:
            Smoothed acceleration value (magnitude, always positive).
        """
        # Add raw value to smoothing window
        self._smoothing_window.append(float(raw_value))
        
        # Return current smoothed value (moving average)
        return self._get_smoothed_value()

    def _get_smoothed_value(self) -> float:
        """Get current moving average of acceleration.
        
        Returns:
            Moving average of window, or 0 if window empty.
        """
        if len(self._smoothing_window) == 0:
            return 0.0
        
        window_array = np.array(list(self._smoothing_window))
        return float(np.mean(window_array))

    def compute_acc_index(self, acc_value: float) -> float:
        """Compute ACC index: normalized deviation from baseline.
        
        Formula: (acc_value - baseline_mean) / baseline_std
        
        This normalizes the smoothed acceleration relative to resting variation.
        Positive values indicate above-rest acceleration.
        
        Args:
            acc_value: Smoothed acceleration value.
        
        Returns:
            Normalized ACC index (typically -1 to 5 for normal range).
        """
        if self.baseline_std == 0.0:
            return 0.0
        
        return (acc_value - self.baseline_mean) / self.baseline_std

    def detect_movement(self, acc_value: Optional[float] = None) -> str:
        """Detect movement level based on acceleration.
        
        Classification uses standard deviation-based thresholds:
        - rest: < baseline_mean + (2 × baseline_std)
        - agitation: baseline_mean + (2×std) to baseline_mean + (4×std)
        - movement: >= baseline_mean + (4 × baseline_std)
        
        Args:
            acc_value: Optional smoothed acceleration value. If None, uses
                      current window average.
        
        Returns:
            One of "rest", "agitation", "movement".
        """
        if acc_value is None:
            acc_value = self._get_smoothed_value()
        
        # Compute normalized deviation
        acc_index = self.compute_acc_index(acc_value)
        
        # Apply thresholds
        if acc_index < config.ACC_THRESHOLD_AGITATION:
            return "rest"
        elif acc_index < config.ACC_THRESHOLD_MOVEMENT:
            return "agitation"
        else:
            return "movement"