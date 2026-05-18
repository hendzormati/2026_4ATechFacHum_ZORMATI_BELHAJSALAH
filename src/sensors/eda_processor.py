"""EDA (Electrodermal Activity) signal processor.

Processes raw EDA signals and computes stress indices based on
electrodermal activity measurements from the skin.
"""

from collections import deque
from typing import Deque
import numpy as np
import sys
from pathlib import Path

# Add src to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import config
except ImportError:
    # Default config values
    class config:
        EDA_THRESHOLD_MODERATE = 2.0
        EDA_THRESHOLD_HIGH = 3.0


class EDAProcessor:
    """Process EDA (Electrodermal Activity) signal.
    
    Converts raw ADC values to normalized stress indices using baseline
    statistics. Applies moving average smoothing to reduce noise.
    """
    
    def __init__(self, baseline_mean: float, baseline_std: float) -> None:
        """Initialize EDA processor with baseline statistics.
        
        Args:
            baseline_mean: Mean EDA value during calibration (ADC units)
            baseline_std: Standard deviation of EDA during calibration
            
        Raises:
            ValueError: If baseline_std is zero or negative
        """
        if baseline_std <= 0:
            raise ValueError(f"baseline_std must be positive, got {baseline_std}")
        
        self.baseline_mean = baseline_mean
        self.baseline_std = baseline_std
        
        # Smoothing window: 10 samples at 100 Hz = 0.1 second
        # Fixed maxlen prevents unbounded memory growth
        self._smoothing_window: Deque[float] = deque(maxlen=10)
    
    def process_raw(self, raw_value: int) -> float:
        """Convert raw ADC value to smoothed EDA value.
        
        Applies moving average filter over a 0.1 second window to
        reduce high-frequency noise while preserving stress responses.
        
        Args:
            raw_value: Raw ADC value from BITalino (0-1023 or 0-65535)
            
        Returns:
            float: Smoothed EDA value in arbitrary ADC units
            
        Note:
            The returned value is the rolling mean of the last 10 samples.
            First 9 samples will have partial window sizes.
        """
        # Add to smoothing window
        self._smoothing_window.append(float(raw_value))
        
        # Compute rolling average (handles partial windows)
        if len(self._smoothing_window) > 0:
            smoothed_value = np.mean(list(self._smoothing_window))
        else:
            smoothed_value = float(raw_value)
        
        return smoothed_value
    
    def compute_eda_index(self, eda_value: float) -> float:
        """Compute normalized EDA stress index.
        
        Formula: eda_index = (eda_value - baseline_mean) / baseline_std
        
        This normalizes the EDA value to a z-score, allowing comparison
        across different individuals and conditions.
        
        Args:
            eda_value: Smoothed EDA value (from process_raw)
            
        Returns:
            float: Normalized EDA index
            
        Example:
            >>> processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
            >>> processor.compute_eda_index(510.0)  # At baseline
            0.0
            >>> processor.compute_eda_index(520.0)  # +1 std
            1.0
            >>> processor.compute_eda_index(540.0)  # +3 std
            3.0
        """
        eda_index = (eda_value - self.baseline_mean) / self.baseline_std
        return eda_index
    
    def classify_level(self, eda_index: float) -> str:
        """Classify EDA stress level based on index.
        
        Uses thresholds defined in config to classify the stress state.
        Classification thresholds (in standard deviations from baseline):
        
        - < 1.0: "normal" (resting)
        - 1.0 - 2.0: "moderate" (slight stress, manageable)
        - 2.0 - 3.0: "high" (significant stress, sustained)
        - >= 3.0: "overload" (extreme stress, potential overload)
        
        Args:
            eda_index: Normalized EDA index (from compute_eda_index)
            
        Returns:
            str: One of ["normal", "moderate", "high", "overload"]
            
        Example:
            >>> processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
            >>> processor.classify_level(0.5)
            'normal'
            >>> processor.classify_level(1.5)
            'moderate'
            >>> processor.classify_level(2.5)
            'high'
            >>> processor.classify_level(3.5)
            'overload'
        """
        threshold_moderate = config.EDA_THRESHOLD_MODERATE  # 2.0 by default
        threshold_high = config.EDA_THRESHOLD_HIGH  # 3.0 by default
        
        if eda_index < threshold_moderate:
            return "normal"
        elif eda_index < threshold_high:
            return "moderate"
        elif eda_index < threshold_high * 1.5:  # Intermediate check
            return "high"
        else:
            return "overload"
    
    def reset(self) -> None:
        """Reset the smoothing window.
        
        Useful for clearing state between sessions or after mode changes.
        """
        self._smoothing_window.clear()
    
    def get_window_size(self) -> int:
        """Get current number of samples in smoothing window.
        
        Returns:
            int: Number of samples in window (0-10)
        """
        return len(self._smoothing_window)
