# src/sensors/ppg_processor.py - COMPLETE REWRITE
"""PPG (Photoplethysmography) signal processor.

Processes optical heart rate signal to detect R-peaks (systolic peaks) and
calculate Heart Rate Variability. PPG is used to derive HRV, a key cognitive
load indicator showing parasympathetic nervous system response.
"""

import numpy as np
from collections import deque
from typing import List, Optional
from scipy import signal

import config


class PPGProcessor:
    """Process PPG (Photoplethysmography) signal from port 6.
    
    Detects heartbeat peaks in infrared light absorption and calculates
    inter-beat intervals (IBIs) for HRV analysis. Key indicator of stress
    response through heart rate variability changes.
    """

    def __init__(self, sampling_rate: int) -> None:
        """Initialize PPG processor.
        
        Creates a bandpass Butterworth filter (0.5-4 Hz) to isolate heartbeat
        frequencies from noise and respiration artifacts.
        
        Args:
            sampling_rate: Acquisition frequency in Hz (typically 100).
        """
        self.sampling_rate = sampling_rate
        self._signal_window: deque = deque(maxlen=sampling_rate * 10)  # 10s
        self._peak_indices: List[int] = []
        self._ibi_values: List[float] = []  # Inter-Beat Intervals in ms
        
        # Design bandpass filter: 0.5-4 Hz for heart rate (30-240 bpm)
        # Nyquist frequency = sampling_rate / 2
        nyquist = sampling_rate / 2.0
        low_freq = 0.5 / nyquist
        high_freq = 4.0 / nyquist
        
        # Butterworth bandpass filter, order 4
        self._b, self._a = signal.butter(
            4, [low_freq, high_freq], btype='band'
        )
        
        # Initialize filter state (zi shape: max(len(b), len(a)) - 1)
        self._zi = signal.lfilter_zi(self._b, self._a)

    def process_raw(self, raw_value: int) -> float:
        """Convert raw ADC value to filtered PPG signal.
        
        Applies bandpass Butterworth filter (0.5-4 Hz) to attenuate noise,
        respiration artifacts, and slow drifts. Uses lfilter with persistent
        state for continuous filtering.
        
        Args:
            raw_value: Raw 16-bit ADC value (0-65535).
        
        Returns:
            Filtered PPG value (floating point).
        """
        # Convert to float
        float_value = float(raw_value)
        
        # Apply IIR filter with state preservation
        filtered, self._zi = signal.lfilter(
            self._b, self._a, [float_value], zi=self._zi
        )
        
        filtered_value = float(filtered[0])
        self._signal_window.append(filtered_value)
        
        return filtered_value

    def detect_peaks(self) -> List[int]:
        """Detect R-peaks in current window using adaptive threshold.
        
        Implements adaptive thresholding: peak must exceed
        (mean + std_dev) of window. This auto-adjusts to signal amplitude
        and noise level without manual tuning.
        
        Returns:
            List of peak indices relative to current window position.
            Empty if insufficient data or no peaks found.
        """
        if len(self._signal_window) < 10:
            return []
        
        signal_array = np.array(list(self._signal_window))
        
        # Adaptive threshold: mean + 1.0*std
        threshold = np.mean(signal_array) + 1.0 * np.std(signal_array)
        
        # Find samples above threshold
        above_threshold = signal_array > threshold
        
        # Find peaks: local maxima among above-threshold samples
        peaks = []
        for i in range(1, len(signal_array) - 1):
            if (above_threshold[i] and
                signal_array[i] > signal_array[i-1] and
                signal_array[i] > signal_array[i+1]):
                peaks.append(i)
        
        # Store peak indices for IBI calculation
        self._peak_indices = peaks
        
        return peaks

    def compute_ibi(self) -> List[float]:
        """Compute Inter-Beat Intervals from detected peaks.
        
        Calculates time differences between consecutive peaks and converts
        to milliseconds. IBIs are the fundamental input for HRV metrics.
        
        Formula: IBI[i] = (peak[i+1] - peak[i]) / sampling_rate * 1000
        
        Returns:
            List of IBI values in milliseconds. Empty if fewer than 2 peaks.
        """
        if len(self._peak_indices) < 2:
            return []
        
        ibi_list = []
        for i in range(len(self._peak_indices) - 1):
            peak_diff = self._peak_indices[i + 1] - self._peak_indices[i]
            # Convert samples to milliseconds
            ibi_ms = (peak_diff / self.sampling_rate) * 1000.0
            ibi_list.append(ibi_ms)
        
        self._ibi_values = ibi_list
        return ibi_list

    def compute_bpm(self) -> Optional[float]:
        """Compute current BPM from recent IBIs.
        
        Requires minimum 3 IBIs (4 peaks) for reliable estimate.
        BPM = 60000 / mean_ibi
        
        Returns:
            BPM (beats per minute) or None if insufficient data.
        """
        if len(self._ibi_values) < 3:
            return None
        
        mean_ibi = np.mean(self._ibi_values)
        
        if mean_ibi == 0.0:
            return None
        
        bpm = 60000.0 / mean_ibi
        
        # Sanity check: normal human heart rate 40-200 bpm
        if 40.0 <= bpm <= 200.0:
            return bpm
        
        return None

    def get_peak_indices(self) -> List[int]:
        """Get most recently detected peak indices.
        
        Returns:
            List of peak indices from last detect_peaks() call.
        """
        return self._peak_indices

    def get_ibi_values(self) -> List[float]:
        """Get most recently computed IBIs.
        
        Returns:
            List of IBI values in milliseconds from last compute_ibi() call.
        """
        return self._ibi_values

    def get_signal_window(self) -> List[float]:
        """Get current filtered signal window.
        
        Returns:
            List of filtered PPG values (last 10 seconds worth).
        """
        return list(self._signal_window)