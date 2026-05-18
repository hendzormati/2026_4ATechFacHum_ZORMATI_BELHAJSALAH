# tests/test_sensors/test_ppg_processor.py
"""Unit tests for PPGProcessor."""

import pytest
import numpy as np
from scipy import signal as scipy_signal
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sensors.ppg_processor import PPGProcessor
import config


class TestPPGProcessorInit:
    """Test PPGProcessor initialization."""

    def test_ppg_processor_init(self) -> None:
        """Verify processor initializes with correct sampling rate."""
        processor = PPGProcessor(sampling_rate=100)
        
        assert processor.sampling_rate == 100
        assert processor._signal_window.maxlen == 1000  # 100 * 10
        assert isinstance(processor._peak_indices, list)
        assert isinstance(processor._ibi_values, list)
        assert len(processor._peak_indices) == 0
        assert len(processor._ibi_values) == 0

    def test_ppg_processor_init_different_rate(self) -> None:
        """Verify processor with different sampling rate."""
        processor = PPGProcessor(sampling_rate=50)
        
        assert processor.sampling_rate == 50
        assert processor._signal_window.maxlen == 500  # 50 * 10

    def test_ppg_processor_filter_coefficients(self) -> None:
        """Verify bandpass filter is properly configured."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Filter should be designed (not None)
        assert processor._b is not None
        assert processor._a is not None
        assert len(processor._b) > 0
        assert len(processor._a) > 0

class TestProcessRaw:
    """Test raw PPG processing and filtering."""

    def test_process_raw_single_value(self) -> None:
        """Single value should be filtered and added to window."""
        processor = PPGProcessor(sampling_rate=100)
        
        filtered = processor.process_raw(512)
        
        assert isinstance(filtered, float)
        assert len(processor._signal_window) == 1

    def test_process_raw_fills_window(self) -> None:
        """Multiple calls should fill signal window."""
        processor = PPGProcessor(sampling_rate=100)
        
        for i in range(50):
            processor.process_raw(512 + i)
        
        assert len(processor._signal_window) == 50

    def test_process_raw_window_maxlen(self) -> None:
        """Window should not exceed maxlen=1000."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Add more than maxlen values
        for i in range(1500):
            processor.process_raw(512 + (i % 100))
        
        assert len(processor._signal_window) == 1000

    def test_process_raw_DC_component_removed(self) -> None:
        """Filter should remove DC offset over many samples."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Add constant signal - bandpass should remove DC
        for _ in range(500):
            processor.process_raw(512)
        
        # After transient, filtered signal should be near zero
        filtered_values = np.array(processor.get_signal_window()[-50:])
        mean_value = np.mean(filtered_values)
        
        # DC removed - mean should be near 0
        assert abs(mean_value) < 10.0

    def test_process_raw_heartbeat_passthrough(self) -> None:
        """Filter should pass heartbeat frequencies."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Generate 1 Hz (60 bpm) sinusoid
        heartbeat_freq = 1.0
        for i in range(500):
            t = i / processor.sampling_rate
            value = 512 + 100 * np.sin(2 * np.pi * heartbeat_freq * t)
            processor.process_raw(int(value))
        
        # After transient (first 100 samples), check amplitude
        filtered_window = np.array(processor.get_signal_window()[-200:])
        amplitude = (np.max(filtered_window) - np.min(filtered_window)) / 2
        
        # Should preserve significant heartbeat amplitude
        assert amplitude > 20.0


class TestDetectPeaks:
    """Test peak detection."""

    def test_detect_peaks_empty_window(self) -> None:
        """Empty window should return no peaks."""
        processor = PPGProcessor(sampling_rate=100)
        
        peaks = processor.detect_peaks()
        
        assert peaks == []

    def test_detect_peaks_insufficient_data(self) -> None:
        """Fewer than 10 samples should return no peaks."""
        processor = PPGProcessor(sampling_rate=100)
        
        for i in range(5):
            processor.process_raw(512 + i)
        
        peaks = processor.detect_peaks()
        
        assert peaks == []

    def test_detect_peaks_synthetic_heartbeat(self) -> None:
        """Should detect peaks in clear heartbeat signal."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Generate clean 1 Hz heartbeat for 10 seconds
        heartbeat_freq = 1.0
        for i in range(1000):
            t = i / processor.sampling_rate
            value = 512 + 100 * np.sin(2 * np.pi * heartbeat_freq * t)
            processor.process_raw(int(value))
        
        peaks = processor.detect_peaks()
        
        # Should detect approximately 10 peaks (1 per second, 10 seconds)
        # Allow some margin for filter transient effects
        assert len(peaks) >= 5

    def test_detect_peaks_stores_indices(self) -> None:
        """detect_peaks() should store indices in _peak_indices."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Add data
        for i in range(200):
            processor.process_raw(512 + 50 * np.sin(2 * np.pi * i / 20))
        
        peaks = processor.detect_peaks()
        stored_peaks = processor.get_peak_indices()
        
        assert peaks == stored_peaks

    def test_detect_peaks_adaptive_threshold(self) -> None:
        """Adaptive threshold should adjust to signal amplitude."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Large amplitude signal at 1 Hz
        for i in range(200):
            processor.process_raw(int(512 + 100 * np.sin(2 * np.pi * i / 100)))
        
        peaks = processor.detect_peaks()
        
        # Should detect multiple peaks
        assert len(peaks) >= 2


class TestIntegration:
    """Integration tests for PPGProcessor."""

    def test_full_ppg_pipeline_stable_hr(self) -> None:
        """Complete pipeline: raw → filtered → peaks → IBI → BPM."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Generate 60 bpm heartbeat signal (1 Hz)
        heartbeat_freq = 1.0
        # Use longer signal (15 seconds) to ensure stable peak detection
        for i in range(1500):
            t = i / processor.sampling_rate
            # Simulate PPG photon count variation
            value = 512 + 100 * np.sin(2 * np.pi * heartbeat_freq * t)
            processor.process_raw(int(value))
        
        # Detect peaks
        peaks = processor.detect_peaks()
        assert len(peaks) >= 5, f"Expected >= 5 peaks, got {len(peaks)}"
        
        # Compute IBIs
        ibi = processor.compute_ibi()
        assert len(ibi) >= 4, f"Expected >= 4 IBIs, got {len(ibi)}"
        
        # Compute BPM
        bpm = processor.compute_bpm()
        assert bpm is not None, "BPM should not be None"
        assert 55 <= bpm <= 65, f"Expected BPM ~60, got {bpm}"

    def test_full_ppg_pipeline_elevated_hr(self) -> None:
        """Test pipeline with elevated heart rate (stress)."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Generate 120 bpm heartbeat signal (2 Hz)
        heartbeat_freq = 2.0
        # Use longer signal to ensure stable detection
        for i in range(1500):
            t = i / processor.sampling_rate
            value = 512 + 100 * np.sin(2 * np.pi * heartbeat_freq * t)
            processor.process_raw(int(value))
        
        peaks = processor.detect_peaks()
        ibi = processor.compute_ibi()
        bpm = processor.compute_bpm()
        
        assert len(peaks) >= 10, f"Expected >= 10 peaks, got {len(peaks)}"
        assert len(ibi) >= 9, f"Expected >= 9 IBIs, got {len(ibi)}"
        assert bpm is not None, "BPM should not be None"
        assert 100 <= bpm <= 140, f"Expected BPM ~120, got {bpm}"

    def test_realistic_ppg_with_noise(self) -> None:
        """Test with realistic noisy signal."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Heartbeat + respiration + noise
        heartbeat_freq = 1.2  # ~72 bpm
        respiration_freq = 0.3  # ~18 breaths/min
        
        np.random.seed(42)
        for i in range(1500):
            t = i / processor.sampling_rate
            heartbeat = 100 * np.sin(2 * np.pi * heartbeat_freq * t)
            respiration = 30 * np.sin(2 * np.pi * respiration_freq * t)
            noise = np.random.normal(0, 5)
            value = 512 + heartbeat + respiration + noise
            processor.process_raw(int(np.clip(value, 0, 65535)))
        
        peaks = processor.detect_peaks()
        ibi = processor.compute_ibi()
        bpm = processor.compute_bpm()
        
        # Should detect peaks despite noise
        assert len(peaks) >= 8, f"Expected >= 8 peaks, got {len(peaks)}"
        
        # Should extract reasonable BPM
        if bpm is not None:
            assert 60 <= bpm <= 85, f"Expected BPM ~72, got {bpm}"
        
        # Should have IBIs
        assert len(ibi) >= 7, f"Expected >= 7 IBIs, got {len(ibi)}"

class TestComputeIBI:
    """Test IBI calculation."""

    def test_compute_ibi_no_peaks(self) -> None:
        """No peaks should return empty IBI list."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Set peaks manually to empty
        processor._peak_indices = []
        
        ibi = processor.compute_ibi()
        
        assert ibi == []

    def test_compute_ibi_single_peak(self) -> None:
        """Single peak should return no IBIs."""
        processor = PPGProcessor(sampling_rate=100)
        
        processor._peak_indices = [50]
        
        ibi = processor.compute_ibi()
        
        assert ibi == []

    def test_compute_ibi_two_peaks(self) -> None:
        """Two peaks should produce one IBI."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Peaks 100 samples apart at 100 Hz = 1 second = 1000 ms
        processor._peak_indices = [50, 150]
        
        ibi = processor.compute_ibi()
        
        assert len(ibi) == 1
        assert ibi[0] == pytest.approx(1000.0)  # 100 samples / 100 Hz * 1000 ms

    def test_compute_ibi_multiple_peaks(self) -> None:
        """Multiple peaks should produce corresponding IBIs."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Peaks spaced at 100 samples = 1 second apart
        processor._peak_indices = [50, 150, 250, 350]
        
        ibi = processor.compute_ibi()
        
        assert len(ibi) == 3
        for ib in ibi:
            assert ib == pytest.approx(1000.0)

    def test_compute_ibi_variable_spacing(self) -> None:
        """Variable peak spacing should produce variable IBIs."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Peaks with variable spacing
        # Peak 0->1: 80 samples = 800 ms
        # Peak 1->2: 100 samples = 1000 ms
        # Peak 2->3: 120 samples = 1200 ms
        processor._peak_indices = [50, 130, 230, 350]
        
        ibi = processor.compute_ibi()
        
        assert len(ibi) == 3
        assert ibi[0] == pytest.approx(800.0)
        assert ibi[1] == pytest.approx(1000.0)
        assert ibi[2] == pytest.approx(1200.0)

    def test_compute_ibi_stores_values(self) -> None:
        """compute_ibi() should store values in _ibi_values."""
        processor = PPGProcessor(sampling_rate=100)
        
        processor._peak_indices = [50, 150, 250]
        ibi = processor.compute_ibi()
        stored_ibi = processor.get_ibi_values()
        
        assert ibi == stored_ibi

    def test_compute_ibi_different_sampling_rates(self) -> None:
        """Should handle different sampling rates correctly."""
        processor_100 = PPGProcessor(sampling_rate=100)
        processor_50 = PPGProcessor(sampling_rate=50)
        
        # Same heart rate (1 Hz), but different sample spacing
        processor_100._peak_indices = [50, 150]  # 100 samples apart
        processor_50._peak_indices = [25, 75]    # 50 samples apart
        
        ibi_100 = processor_100.compute_ibi()
        ibi_50 = processor_50.compute_ibi()
        
        # Both should represent 1 second = 1000 ms
        assert ibi_100[0] == pytest.approx(1000.0)
        assert ibi_50[0] == pytest.approx(1000.0)


class TestComputeBPM:
    """Test BPM calculation."""

    def test_compute_bpm_no_ibi(self) -> None:
        """No IBIs should return None."""
        processor = PPGProcessor(sampling_rate=100)
        
        processor._ibi_values = []
        
        bpm = processor.compute_bpm()
        
        assert bpm is None

    def test_compute_bpm_insufficient_ibi(self) -> None:
        """Fewer than 3 IBIs should return None."""
        processor = PPGProcessor(sampling_rate=100)
        
        processor._ibi_values = [1000.0, 1020.0]  # Only 2 IBIs
        
        bpm = processor.compute_bpm()
        
        assert bpm is None

    def test_compute_bpm_60bpm(self) -> None:
        """60 bpm = 1000 ms IBI."""
        processor = PPGProcessor(sampling_rate=100)
        
        # 60 bpm = 1000 ms IBI
        processor._ibi_values = [1000.0, 1000.0, 1000.0]
        
        bpm = processor.compute_bpm()
        
        assert bpm == pytest.approx(60.0)

    def test_compute_bpm_120bpm(self) -> None:
        """120 bpm = 500 ms IBI."""
        processor = PPGProcessor(sampling_rate=100)
        
        # 120 bpm = 500 ms IBI
        processor._ibi_values = [500.0, 500.0, 500.0]
        
        bpm = processor.compute_bpm()
        
        assert bpm == pytest.approx(120.0)

    def test_compute_bpm_variable_hr(self) -> None:
        """Variable IBIs should produce average BPM."""
        processor = PPGProcessor(sampling_rate=100)
        
        # IBIs: 1000, 1100, 900 ms (avg = 1000, mean bpm = 60)
        processor._ibi_values = [1000.0, 1100.0, 900.0]
        
        bpm = processor.compute_bpm()
        
        # Mean IBI = 1000, BPM = 60
        assert bpm == pytest.approx(60.0)

    def test_compute_bpm_sanity_check_low(self) -> None:
        """BPM below 40 should return None."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Very long IBI = very low BPM (>2500 ms = 24 bpm)
        processor._ibi_values = [3000.0, 3000.0, 3000.0]
        
        bpm = processor.compute_bpm()
        
        assert bpm is None

    def test_compute_bpm_sanity_check_high(self) -> None:
        """BPM above 200 should return None."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Very short IBI = very high BPM (<300 ms = 200 bpm)
        processor._ibi_values = [250.0, 250.0, 250.0]
        
        bpm = processor.compute_bpm()
        
        assert bpm is None

    def test_compute_bpm_valid_range(self) -> None:
        """BPM 40-200 should be returned."""
        processor = PPGProcessor(sampling_rate=100)
        
        # 40 bpm = 1500 ms
        processor._ibi_values = [1500.0, 1500.0, 1500.0]
        bpm = processor.compute_bpm()
        assert bpm == pytest.approx(40.0)
        
        # 200 bpm = 300 ms
        processor._ibi_values = [300.0, 300.0, 300.0]
        bpm = processor.compute_bpm()
        assert bpm == pytest.approx(200.0)


# tests/test_sensors/test_ppg_processor.py - REPLACE entire TestIntegration class

class TestIntegration:
    """Integration tests for PPGProcessor."""

    def test_full_ppg_pipeline_60bpm(self) -> None:
        """Complete pipeline: raw → filtered → peaks → IBI → BPM."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Generate 60 bpm heartbeat signal (1 Hz)
        heartbeat_freq = 1.0
        # Use longer signal (15 seconds) to ensure stable peak detection
        for i in range(1500):
            t = i / processor.sampling_rate
            # Simulate PPG photon count variation
            value = 512 + 100 * np.sin(2 * np.pi * heartbeat_freq * t)
            processor.process_raw(int(value))
        
        # Detect peaks
        peaks = processor.detect_peaks()
        assert len(peaks) >= 5, f"Expected >= 5 peaks, got {len(peaks)}"
        
        # Compute IBIs
        ibi = processor.compute_ibi()
        assert len(ibi) >= 4, f"Expected >= 4 IBIs, got {len(ibi)}"
        
        # Compute BPM
        bpm = processor.compute_bpm()
        assert bpm is not None, "BPM should not be None"
        assert 55 <= bpm <= 65, f"Expected BPM ~60, got {bpm}"

    def test_full_ppg_pipeline_elevated_hr(self) -> None:
        """Test pipeline with elevated heart rate (stress)."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Generate 120 bpm heartbeat signal (2 Hz)
        heartbeat_freq = 2.0
        # Use longer signal to ensure stable detection
        for i in range(1500):
            t = i / processor.sampling_rate
            value = 512 + 100 * np.sin(2 * np.pi * heartbeat_freq * t)
            processor.process_raw(int(value))
        
        peaks = processor.detect_peaks()
        ibi = processor.compute_ibi()
        bpm = processor.compute_bpm()
        
        assert len(peaks) >= 10, f"Expected >= 10 peaks, got {len(peaks)}"
        assert len(ibi) >= 9, f"Expected >= 9 IBIs, got {len(ibi)}"
        assert bpm is not None, "BPM should not be None"
        assert 100 <= bpm <= 140, f"Expected BPM ~120, got {bpm}"

    def test_realistic_ppg_with_noise(self) -> None:
        """Test with realistic noisy signal."""
        processor = PPGProcessor(sampling_rate=100)
        
        # Heartbeat + respiration + noise
        heartbeat_freq = 1.2  # ~72 bpm
        respiration_freq = 0.3  # ~18 breaths/min
        
        np.random.seed(42)
        for i in range(1500):
            t = i / processor.sampling_rate
            heartbeat = 100 * np.sin(2 * np.pi * heartbeat_freq * t)
            respiration = 30 * np.sin(2 * np.pi * respiration_freq * t)
            noise = np.random.normal(0, 5)
            value = 512 + heartbeat + respiration + noise
            processor.process_raw(int(np.clip(value, 0, 65535)))
        
        peaks = processor.detect_peaks()
        ibi = processor.compute_ibi()
        bpm = processor.compute_bpm()
        
        # Should detect peaks despite noise
        assert len(peaks) >= 8, f"Expected >= 8 peaks, got {len(peaks)}"
        
        # Should extract reasonable BPM
        if bpm is not None:
            assert 60 <= bpm <= 85, f"Expected BPM ~72, got {bpm}"
        
        # Should have IBIs
        assert len(ibi) >= 7, f"Expected >= 7 IBIs, got {len(ibi)}"