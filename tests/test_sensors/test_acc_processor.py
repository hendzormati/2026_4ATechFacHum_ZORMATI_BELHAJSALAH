# tests/test_sensors/test_acc_processor.py
"""Unit tests for ACCProcessor."""

import pytest
import numpy as np
from collections import deque
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sensors.acc_processor import ACCProcessor
import config


class TestACCProcessorInit:
    """Test ACCProcessor initialization."""

    def test_acc_processor_init(self) -> None:
        """Verify processor initializes with correct baseline."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        assert processor.baseline_mean == 512.0
        assert processor.baseline_std == 5.0
        assert isinstance(processor._smoothing_window, deque)
        assert processor._smoothing_window.maxlen == 20

    def test_acc_processor_init_zero_std(self) -> None:
        """Verify processor handles zero std gracefully."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=0.0)
        
        assert processor.baseline_std == 0.0


class TestProcessRaw:
    """Test raw ACC processing and smoothing."""

    def test_process_raw_single_value(self) -> None:
        """Single value should be added to window."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        value = processor.process_raw(515)
        
        assert len(processor._smoothing_window) == 1
        assert value == 515.0

    def test_process_raw_returns_smoothed(self) -> None:
        """Should return moving average of window."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        processor.process_raw(510)
        value = processor.process_raw(514)  # avg of [510, 514] = 512
        
        assert value == pytest.approx(512.0)

    def test_process_raw_smoothing(self) -> None:
        """Multiple values should be smoothed."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Add values: 500, 510, 520, 530
        processor.process_raw(500)
        processor.process_raw(510)
        processor.process_raw(520)
        value = processor.process_raw(530)
        
        # Smoothed: (500 + 510 + 520 + 530) / 4 = 515
        assert value == pytest.approx(515.0)

    def test_process_raw_window_sliding(self) -> None:
        """Window should maintain maxlen=20."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Add 30 values
        for i in range(30):
            processor.process_raw(500 + i)
        
        assert len(processor._smoothing_window) == 20

    def test_process_raw_fills_window(self) -> None:
        """Multiple calls should fill window."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        for i in range(20):
            processor.process_raw(512 + i)
        
        assert len(processor._smoothing_window) == 20


class TestComputeAccIndex:
    """Test ACC index calculation."""

    def test_acc_index_at_baseline(self) -> None:
        """Smoothed value at baseline mean should give index 0."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Fill window with baseline value
        for _ in range(10):
            processor.process_raw(512)
        
        acc_value = processor._get_smoothed_value()
        acc_index = processor.compute_acc_index(acc_value)
        
        assert acc_index == pytest.approx(0.0)

    def test_acc_index_one_std_above(self) -> None:
        """Value at mean + 1*std should give index 1.0."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Value: 517 = 512 + 5
        acc_index = processor.compute_acc_index(517.0)
        
        assert acc_index == pytest.approx(1.0)

    def test_acc_index_two_std_above(self) -> None:
        """Value at mean + 2*std should give index 2.0."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Value: 522 = 512 + (2*5)
        acc_index = processor.compute_acc_index(522.0)
        
        assert acc_index == pytest.approx(2.0)

    def test_acc_index_below_baseline(self) -> None:
        """Value below baseline should give negative index."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Value: 507 = 512 - 5
        acc_index = processor.compute_acc_index(507.0)
        
        assert acc_index == pytest.approx(-1.0)

    def test_acc_index_zero_std(self) -> None:
        """Zero std should return 0 to avoid division error."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=0.0)
        
        acc_index = processor.compute_acc_index(520.0)
        
        assert acc_index == 0.0

    def test_acc_index_with_smoothed_window(self) -> None:
        """Should work with values from smoothed window."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Fill window with values averaging to 525 (baseline + 13)
        for _ in range(10):
            processor.process_raw(525)
        
        acc_value = processor._get_smoothed_value()
        acc_index = processor.compute_acc_index(acc_value)
        
        # Index should be (525 - 512) / 5 = 2.6
        assert acc_index == pytest.approx(2.6)


class TestDetectMovement:
    """Test movement detection."""

    def test_detect_rest(self) -> None:
        """Low acceleration should classify as rest."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Value at baseline (index = 0 < threshold 2.0)
        value = processor.process_raw(512)
        
        movement = processor.detect_movement(value)
        
        assert movement == "rest"

    def test_detect_rest_with_noise(self) -> None:
        """Acceleration near baseline should classify as rest."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Value at baseline + 1.5*std = 519.5 (index = 1.5 < threshold 2.0)
        for _ in range(10):
            processor.process_raw(519)  # approx 519.5 after smoothing
        
        movement = processor.detect_movement()
        
        assert movement == "rest"

    def test_detect_agitation(self) -> None:
        """Medium acceleration should classify as agitation."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Value at baseline + 3*std = 527 (index = 3.0, between thresholds 2 and 4)
        for _ in range(10):
            processor.process_raw(527)
        
        movement = processor.detect_movement()
        
        assert movement == "agitation"

    def test_detect_movement(self) -> None:
        """High acceleration should classify as movement."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Value at baseline + 5*std = 537 (index = 5.0 >= threshold 4.0)
        for _ in range(10):
            processor.process_raw(537)
        
        movement = processor.detect_movement()
        
        assert movement == "movement"

    def test_detect_movement_explicit_value(self) -> None:
        """Should accept explicit acc_value parameter."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Test with explicit value (doesn't need to fill window first)
        value = 532.0  # baseline + 4*std, at threshold
        movement = processor.detect_movement(value)
        
        assert movement == "movement"

    def test_detect_movement_boundary_rest_to_agitation(self) -> None:
        """Value at agitation threshold should be agitation."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Exactly at threshold: baseline + 2*std = 522 (index = 2.0)
        value = 522.0
        movement = processor.detect_movement(value)
        
        assert movement == "agitation"

    def test_detect_movement_boundary_agitation_to_movement(self) -> None:
        """Value at movement threshold should be movement."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Exactly at threshold: baseline + 4*std = 532 (index = 4.0)
        value = 532.0
        movement = processor.detect_movement(value)
        
        assert movement == "movement"

    def test_detect_movement_empty_window(self) -> None:
        """Empty window should classify as rest."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        movement = processor.detect_movement()
        
        assert movement == "rest"


class TestIntegration:
    """Integration tests for ACCProcessor."""

    def test_rest_period(self) -> None:
        """Test stable rest - minimal acceleration."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Simulate rest: stable values near baseline
        for _ in range(20):
            processor.process_raw(512 + np.random.randint(-2, 3))
        
        movement = processor.detect_movement()
        acc_index = processor.compute_acc_index(processor._get_smoothed_value())
        
        assert movement == "rest"
        assert abs(acc_index) < 1.0

    def test_agitation_period(self) -> None:
        """Test agitation - fidgeting with small movements."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Simulate agitation: oscillating around baseline + 3*std
        baseline_plus_3std = 512.0 + (3.0 * 5.0)
        for _ in range(20):
            processor.process_raw(int(baseline_plus_3std + np.random.randint(-3, 4)))
        
        movement = processor.detect_movement()
        acc_index = processor.compute_acc_index(processor._get_smoothed_value())
        
        assert movement == "agitation"
        assert 2.0 < acc_index < 4.0

    def test_movement_period(self) -> None:
        """Test significant movement."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Simulate movement: large accelerations
        baseline_plus_5std = 512.0 + (5.0 * 5.0)
        for _ in range(20):
            processor.process_raw(int(baseline_plus_5std + np.random.randint(-5, 6)))
        
        movement = processor.detect_movement()
        acc_index = processor.compute_acc_index(processor._get_smoothed_value())
        
        assert movement == "movement"
        assert acc_index > 4.0

    def test_progressive_movement_increase(self) -> None:
        """Test gradual increase in acceleration."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Fill with initial rest
        for _ in range(20):
            processor.process_raw(512)
        
        assert processor.detect_movement() == "rest"
        
        # Increase acceleration gradually
        processor2 = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        for i in range(20):
            # Linear progression from baseline to baseline + 5*std
            value = 512 + i
            processor2.process_raw(value)
        
        movement = processor2.detect_movement()
        acc_index = processor2.compute_acc_index(processor2._get_smoothed_value())
        
        # Final window should show high acceleration
        assert acc_index > 1.0

    def test_realistic_stress_movement(self) -> None:
        """Simulate realistic fidgeting during stress."""
        processor = ACCProcessor(baseline_mean=512.0, baseline_std=5.0)
        
        # Stress-induced micro-movements
        stress_values = np.random.normal(loc=525, scale=8, size=20)
        stress_values = np.clip(stress_values, 0, 65535).astype(int)
        
        for val in stress_values:
            processor.process_raw(val)
        
        movement = processor.detect_movement()
        acc_index = processor.compute_acc_index(processor._get_smoothed_value())
        
        # Should be in agitation or movement range
        assert movement in ["agitation", "movement"]
        assert acc_index > 1.5