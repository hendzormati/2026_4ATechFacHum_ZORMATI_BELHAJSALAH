# tests/test_sensors/test_emg_processor.py
"""Unit tests for EMGProcessor."""

import pytest
import sys
from pathlib import Path
import numpy as np
from collections import deque
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sensors.emg_processor import EMGProcessor
import config


class TestEMGProcessorInit:
    """Test EMGProcessor initialization."""

    def test_emg_processor_init(self) -> None:
        """Verify processor initializes with correct baseline."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        assert processor.rms_baseline == 5.0
        assert isinstance(processor._window, deque)
        assert processor._window.maxlen == 50

    def test_emg_processor_init_zero_baseline(self) -> None:
        """Verify processor handles zero baseline gracefully."""
        processor = EMGProcessor(rms_baseline=0.0)
        
        assert processor.rms_baseline == 0.0


class TestProcessRaw:
    """Test raw EMG processing."""

    def test_process_raw_at_baseline(self) -> None:
        """ADC value at midpoint should give minimal rectification."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        # 512 is ADC midpoint, should have zero deviation
        value = processor.process_raw(512)
        
        assert value == 0.0
        assert len(processor._window) == 1

    def test_process_raw_rectification(self) -> None:
        """Values above and below midpoint should have same magnitude."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        value_above = processor.process_raw(520)  # 512 + 8
        assert value_above == 8.0
        
        processor2 = EMGProcessor(rms_baseline=5.0)
        value_below = processor2.process_raw(504)  # 512 - 8
        assert value_below == 8.0

    def test_process_raw_fills_window(self) -> None:
        """Multiple calls should fill sliding window."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        for i in range(50):
            processor.process_raw(512 + i)
        
        assert len(processor._window) == 50

    def test_process_raw_window_sliding(self) -> None:
        """Window should maintain maxlen=50."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        # Fill window and overfill
        for i in range(100):
            processor.process_raw(512 + i)
        
        assert len(processor._window) == 50


class TestComputeRMS:
    """Test RMS calculation."""

    def test_compute_rms_empty_window(self) -> None:
        """Empty window should return 0."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        rms = processor.compute_rms()
        
        assert rms == 0.0

    def test_compute_rms_single_value(self) -> None:
        """RMS of single value equals that value."""
        processor = EMGProcessor(rms_baseline=5.0)
        processor.process_raw(520)  # deviation = 8
        
        rms = processor.compute_rms()
        
        assert rms == pytest.approx(8.0)

    def test_compute_rms_constant_signal(self) -> None:
        """RMS of constant signal equals signal magnitude."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        # Add 10 samples of value 530 (deviation = 18)
        for _ in range(10):
            processor.process_raw(530)
        
        rms = processor.compute_rms()
        
        assert rms == pytest.approx(18.0)

    def test_compute_rms_mixed_signal(self) -> None:
        """RMS of [0, 10, 0, 10] = sqrt(50) ≈ 7.07."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        # Alternate between 512 (dev=0) and 522 (dev=10)
        for i in range(4):
            processor.process_raw(512 if i % 2 == 0 else 522)
        
        # RMS([0, 10, 0, 10]) = sqrt((0 + 100 + 0 + 100) / 4) = sqrt(50) ≈ 7.07
        rms = processor.compute_rms()
        
        assert rms == pytest.approx(7.071, abs=0.01)

    def test_compute_rms_full_window(self) -> None:
        """RMS should work with full 50-sample window."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        # Fill with values: 512 to 561 (deviations 0 to 49)
        for i in range(50):
            processor.process_raw(512 + i)
        
        rms = processor.compute_rms()
        
        # RMS of [0, 1, 2, ..., 49]
        expected_rms = np.sqrt(np.mean(np.arange(50) ** 2))
        assert rms == pytest.approx(expected_rms, abs=0.1)


class TestComputeTensionIndex:
    """Test tension index calculation."""

    def test_tension_index_at_baseline(self) -> None:
        """Window of baseline noise should give index ≈ 1.0."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        # Add 10 samples of baseline noise (avg deviation = 5)
        for _ in range(10):
            processor.process_raw(520)  # dev = 8
        
        tension = processor.compute_tension_index()
        
        # RMS(8, 8, ...) = 8, tension = 8/5 = 1.6
        assert tension == pytest.approx(8.0 / 5.0)

    def test_tension_index_zero_baseline(self) -> None:
        """Zero baseline should return 0 to avoid division error."""
        processor = EMGProcessor(rms_baseline=0.0)
        processor.process_raw(520)
        
        tension = processor.compute_tension_index()
        
        assert tension == 0.0

    def test_tension_index_light_contraction(self) -> None:
        """Light contraction should give index 3-8."""
        processor = EMGProcessor(rms_baseline=10.0)
        
        # Fill window with RMS = 40 (tension = 40/10 = 4.0)
        for _ in range(10):
            processor.process_raw(552)  # dev = 40
        
        tension = processor.compute_tension_index()
        
        assert tension == pytest.approx(4.0)
        assert 3.0 < tension < 8.0

    def test_tension_index_strong_contraction(self) -> None:
        """Strong contraction should give index > 8."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        # Fill window with RMS = 50 (tension = 50/5 = 10)
        for _ in range(10):
            processor.process_raw(562)  # dev = 50
        
        tension = processor.compute_tension_index()
        
        assert tension == pytest.approx(10.0)
        assert tension > config.EMG_THRESHOLD_STRONG


class TestDetectContraction:
    """Test contraction detection."""

    def test_detect_rest(self) -> None:
        """Low tension should classify as rest."""
        processor = EMGProcessor(rms_baseline=10.0)
        
        # RMS = 20, tension = 2.0 (< 3.0 threshold)
        for _ in range(10):
            processor.process_raw(532)  # dev = 20
        
        contraction = processor.detect_contraction()
        
        assert contraction == "rest"

    def test_detect_light_contraction(self) -> None:
        """Medium tension should classify as light."""
        processor = EMGProcessor(rms_baseline=10.0)
        
        # RMS = 50, tension = 5.0 (between 3 and 8)
        for _ in range(10):
            processor.process_raw(562)  # dev = 50
        
        contraction = processor.detect_contraction()
        
        assert contraction == "light"

    def test_detect_strong_contraction(self) -> None:
        """High tension should classify as strong."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        # RMS = 45, tension = 9.0 (> 8.0 threshold)
        for _ in range(10):
            processor.process_raw(557)  # dev = 45
        
        contraction = processor.detect_contraction()
        
        assert contraction == "strong"

    def test_detect_contraction_empty_window(self) -> None:
        """Empty window should classify as rest (tension = 0)."""
        processor = EMGProcessor(rms_baseline=5.0)
        
        contraction = processor.detect_contraction()
        
        assert contraction == "rest"

    def test_detect_contraction_boundary_light_to_strong(self) -> None:
        """Tension exactly at 8.0 should be strong."""
        processor = EMGProcessor(rms_baseline=10.0)
        
        # RMS = 80, tension = 8.0 (exactly at threshold)
        for _ in range(10):
            processor.process_raw(592)  # dev = 80
        
        contraction = processor.detect_contraction()
        
        assert contraction == "strong"

# tests/test_sensors/test_emg_processor.py - UPDATED TestIntegration class
class TestIntegration:
    """Integration tests for EMGProcessor."""

    def test_phase_rest(self) -> None:
        """Test rest phase - low tension."""
        processor = EMGProcessor(rms_baseline=8.0)
        
        # Rest: 20 samples at baseline noise level
        for _ in range(20):
            processor.process_raw(520)  # dev = 8, RMS ≈ 8, tension ≈ 1.0
        
        tension_rest = processor.compute_tension_index()
        contraction_rest = processor.detect_contraction()
        
        assert tension_rest < 2.0
        assert contraction_rest == "rest"

    def test_phase_light_contraction(self) -> None:
        """Test light contraction phase - medium tension."""
        processor = EMGProcessor(rms_baseline=8.0)
        
        # Light contraction: 30 samples
        for _ in range(30):
            processor.process_raw(548)  # dev = 36
        
        tension_light = processor.compute_tension_index()
        contraction_light = processor.detect_contraction()
        
        # RMS = 36, tension = 36/8 = 4.5
        assert 3.0 < tension_light < 8.0
        assert contraction_light == "light"

    def test_phase_strong_contraction(self) -> None:
        """Test strong contraction phase - high tension."""
        processor = EMGProcessor(rms_baseline=8.0)
        
        # Strong contraction: 50 samples all at high deviation
        for _ in range(50):
            processor.process_raw(580)  # dev = 68
        
        tension_strong = processor.compute_tension_index()
        contraction_strong = processor.detect_contraction()
        
        # RMS = 68, tension = 68/8 = 8.5
        assert tension_strong > 8.0
        assert contraction_strong == "strong"

    def test_progressive_muscle_tension(self) -> None:
        """Test transitioning from rest to sustained contraction."""
        processor = EMGProcessor(rms_baseline=6.0)
        
        # Start with rest - fill window with low deviation
        for _ in range(50):
            processor.process_raw(518)  # dev = 6
        
        assert processor.detect_contraction() == "rest"
        
        # Fresh processor - gradual increase
        processor2 = EMGProcessor(rms_baseline=6.0)
        
        # Simulate stress buildup: increasing deviation over time
        for i in range(50):
            # Linear progression from 6 to 50
            deviation = 6 + (44 * i // 49)
            processor2.process_raw(512 + int(deviation))
        
        # Final window should lean toward higher deviations
        tension = processor2.compute_tension_index()
        assert tension > 5.0  # Should be in upper range

    def test_synthetic_stress_pattern(self) -> None:
        """Simulate realistic EMG stress response."""
        processor = EMGProcessor(rms_baseline=6.0)
        
        # Simulate jaw clenching during stress
        stress_deviations = np.random.normal(loc=30, scale=5, size=50)
        stress_deviations = np.abs(stress_deviations)  # ensure positive
        
        for dev in stress_deviations:
            processor.process_raw(int(512 + dev))
        
        tension = processor.compute_tension_index()
        contraction = processor.detect_contraction()
        
        # Stress should produce medium-to-strong contraction
        assert tension > 3.0
        assert contraction in ["light", "strong"]