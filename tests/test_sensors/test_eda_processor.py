"""Unit tests for EDAProcessor.

Tests EDA signal processing, smoothing, index calculation, and level
classification against specification requirements.
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sensors.eda_processor import EDAProcessor


class TestEDAProcessorInitialization:
    """Test EDAProcessor initialization and validation."""
    
    def test_eda_processor_init_valid(self):
        """Test initialization with valid baseline parameters."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        assert processor.baseline_mean == 510.0
        assert processor.baseline_std == 10.0
        assert processor.get_window_size() == 0
    
    def test_eda_processor_init_zero_std_raises_error(self):
        """Test that zero std raises ValueError."""
        with pytest.raises(ValueError, match="baseline_std must be positive"):
            EDAProcessor(baseline_mean=510.0, baseline_std=0.0)
    
    def test_eda_processor_init_negative_std_raises_error(self):
        """Test that negative std raises ValueError."""
        with pytest.raises(ValueError, match="baseline_std must be positive"):
            EDAProcessor(baseline_mean=510.0, baseline_std=-5.0)
    
    def test_eda_processor_init_various_baselines(self):
        """Test initialization with various baseline values."""
        test_cases = [
            (100.0, 5.0),
            (512.0, 10.0),
            (1000.0, 50.0),
            (0.1, 0.01),
        ]
        
        for mean, std in test_cases:
            processor = EDAProcessor(baseline_mean=mean, baseline_std=std)
            assert processor.baseline_mean == mean
            assert processor.baseline_std == std


class TestProcessRawSmoothing:
    """Test raw EDA value processing and smoothing filter."""
    
    def test_process_raw_single_value(self):
        """Test processing a single raw value."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        result = processor.process_raw(510)
        assert result == pytest.approx(510.0)
        assert processor.get_window_size() == 1
    
    def test_process_raw_multiple_values(self):
        """Test processing multiple raw values with moving average."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Add 5 identical values
        for i in range(5):
            result = processor.process_raw(510)
            assert result == pytest.approx(510.0)
        
        assert processor.get_window_size() == 5
    
    def test_process_raw_smoothing_reduces_noise(self):
        """Test that smoothing filter reduces high-frequency noise."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Simulate alternating values: 500, 520, 500, 520, ...
        values = [500, 520, 500, 520, 500, 520, 500, 520]
        results = []
        
        for val in values:
            result = processor.process_raw(val)
            results.append(result)
        
        # First result should be 500
        assert results[0] == pytest.approx(500.0)
        
        # Second result should be average of [500, 520] = 510
        assert results[1] == pytest.approx(510.0)
        
        # After stabilizing, should stay near 510 due to averaging
        average_of_last_3 = sum(results[-3:]) / 3
        assert average_of_last_3 == pytest.approx(510.0, abs=1.0)
    
    def test_process_raw_window_maxlen_10(self):
        """Test that smoothing window respects maxlen=10."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Add 20 values
        for i in range(20):
            processor.process_raw(510 + i)
        
        # Window should never exceed 10
        assert processor.get_window_size() == 10
    
    def test_process_raw_partial_window(self):
        """Test smoothing with partial window (< 10 samples)."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Add 3 values: 500, 520, 510
        result1 = processor.process_raw(500)
        result2 = processor.process_raw(520)
        result3 = processor.process_raw(510)
        
        # result1 = 500 (only 1 sample)
        assert result1 == pytest.approx(500.0)
        
        # result2 = (500+520)/2 = 510
        assert result2 == pytest.approx(510.0)
        
        # result3 = (500+520+510)/3 = 510
        assert result3 == pytest.approx(510.0)
    
    def test_process_raw_converts_int_to_float(self):
        """Test that raw int values are converted to float."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        result = processor.process_raw(512)
        assert isinstance(result, float)
        assert result == pytest.approx(512.0)
    
    def test_process_raw_sequential_increments(self):
        """Test processing values that gradually increment."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Add values: 500, 505, 510, 515, 520
        values = [500, 505, 510, 515, 520]
        results = []
        
        for val in values:
            result = processor.process_raw(val)
            results.append(result)
        
        # Results should trend upward
        assert results[-1] > results[0]
        
        # Last result should be close to 510 (average of window)
        assert results[-1] == pytest.approx(510.0, abs=1.0)


class TestComputeEDAIndex:
    """Test EDA index calculation (z-score normalization)."""
    
    def test_compute_eda_index_at_baseline(self):
        """Test that index is 0 when value equals baseline mean."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        index = processor.compute_eda_index(510.0)
        assert index == pytest.approx(0.0)
    
    def test_compute_eda_index_plus_one_std(self):
        """Test that index is 1.0 when value = baseline + 1×std."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # 510 + 10 = 520
        index = processor.compute_eda_index(520.0)
        assert index == pytest.approx(1.0)
    
    def test_compute_eda_index_plus_two_std(self):
        """Test that index is 2.0 when value = baseline + 2×std."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # 510 + 20 = 530
        index = processor.compute_eda_index(530.0)
        assert index == pytest.approx(2.0)
    
    def test_compute_eda_index_plus_three_std(self):
        """Test that index is 3.0 when value = baseline + 3×std."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # 510 + 30 = 540
        index = processor.compute_eda_index(540.0)
        assert index == pytest.approx(3.0)
    
    def test_compute_eda_index_minus_one_std(self):
        """Test that index is -1.0 when value = baseline - 1×std."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # 510 - 10 = 500
        index = processor.compute_eda_index(500.0)
        assert index == pytest.approx(-1.0)
    
    def test_compute_eda_index_negative_values(self):
        """Test index calculation with negative indices (below baseline)."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # 510 - 30 = 480 → index = -3
        index = processor.compute_eda_index(480.0)
        assert index == pytest.approx(-3.0)
    
    def test_compute_eda_index_fractional_std(self):
        """Test index calculation with fractional standard deviations."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # 510 + 5 = 515 → index = 0.5
        index = processor.compute_eda_index(515.0)
        assert index == pytest.approx(0.5)
    
    def test_compute_eda_index_with_small_std(self):
        """Test index calculation with small standard deviation."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=2.0)
        
        # 510 + 2 = 512 → index = 1.0
        index = processor.compute_eda_index(512.0)
        assert index == pytest.approx(1.0)
        
        # 510 + 10 = 520 → index = 5.0
        index = processor.compute_eda_index(520.0)
        assert index == pytest.approx(5.0)
    
    def test_compute_eda_index_with_large_std(self):
        """Test index calculation with large standard deviation."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=50.0)
        
        # 510 + 50 = 560 → index = 1.0
        index = processor.compute_eda_index(560.0)
        assert index == pytest.approx(1.0)
        
        # 510 + 250 = 760 → index = 5.0
        index = processor.compute_eda_index(760.0)
        assert index == pytest.approx(5.0)


class TestClassifyLevel:
    """Test EDA stress level classification."""
    
    def test_classify_level_normal(self):
        """Test classification of normal (low stress) levels."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Index < 2.0 should be "normal"
        assert processor.classify_level(0.0) == "normal"
        assert processor.classify_level(0.5) == "normal"
        assert processor.classify_level(1.0) == "normal"
        assert processor.classify_level(1.5) == "normal"
        assert processor.classify_level(1.99) == "normal"
    
    def test_classify_level_moderate(self):
        """Test classification of moderate stress levels."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # 2.0 <= index < 3.0 should be "moderate"
        assert processor.classify_level(2.0) == "moderate"
        assert processor.classify_level(2.25) == "moderate"
        assert processor.classify_level(2.5) == "moderate"
        assert processor.classify_level(2.75) == "moderate"
        assert processor.classify_level(2.99) == "moderate"
    
    def test_classify_level_high(self):
        """Test classification of high stress levels."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # 3.0 <= index < 4.5 should be "high"
        assert processor.classify_level(3.0) == "high"
        assert processor.classify_level(3.5) == "high"
        assert processor.classify_level(4.0) == "high"
        assert processor.classify_level(4.49) == "high"
    
    def test_classify_level_overload(self):
        """Test classification of overload (extreme stress) levels."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # index >= 4.5 should be "overload"
        assert processor.classify_level(4.5) == "overload"
        assert processor.classify_level(5.0) == "overload"
        assert processor.classify_level(10.0) == "overload"
        assert processor.classify_level(100.0) == "overload"
    
    def test_classify_level_negative_indices(self):
        """Test classification with negative indices (below baseline)."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Negative indices should be classified as "normal"
        assert processor.classify_level(-1.0) == "normal"
        assert processor.classify_level(-5.0) == "normal"
    
    def test_classify_level_boundary_2_0(self):
        """Test classification at boundary: index = 2.0."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Exactly at threshold should be in the higher category
        assert processor.classify_level(2.0) == "moderate"
        assert processor.classify_level(1.99) == "normal"
    
    def test_classify_level_boundary_3_0(self):
        """Test classification at boundary: index = 3.0."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Exactly at threshold should be in the higher category
        assert processor.classify_level(3.0) == "high"
        assert processor.classify_level(2.99) == "moderate"
    
    def test_classify_level_boundary_4_5(self):
        """Test classification at boundary: index = 4.5."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Exactly at threshold should be in the higher category
        assert processor.classify_level(4.5) == "overload"
        assert processor.classify_level(4.49) == "high"
    
    def test_classify_level_all_transitions(self):
        """Test complete progression through all stress levels."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        progression = [
            (0.5, "normal"),
            (1.5, "normal"),
            (2.5, "moderate"),
            (3.5, "high"),
            (5.0, "overload"),
        ]
        
        for index, expected_level in progression:
            level = processor.classify_level(index)
            assert level == expected_level, \
                f"Index {index} classified as '{level}', expected '{expected_level}'"


class TestReset:
    """Test reset functionality."""
    
    def test_reset_clears_smoothing_window(self):
        """Test that reset() clears the smoothing window."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Add some values
        for i in range(5):
            processor.process_raw(510)
        
        assert processor.get_window_size() == 5
        
        # Reset
        processor.reset()
        
        assert processor.get_window_size() == 0
    
    def test_reset_allows_fresh_processing(self):
        """Test that processing works correctly after reset."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Add values
        for i in range(5):
            processor.process_raw(510)
        
        # Reset
        processor.reset()
        
        # Process new value - should start fresh
        result = processor.process_raw(520)
        assert result == pytest.approx(520.0)
        assert processor.get_window_size() == 1


class TestIntegration:
    """Integration tests combining multiple methods."""
    
    def test_full_workflow_raw_to_classification(self):
        """Test complete workflow from raw value to classification."""
        processor = EDAProcessor(baseline_mean=510.0, baseline_std=10.0)
        
        # Simulate sensor reading at different stress levels
        # Note: Each test case uses a fresh processor to avoid smoothing lag
        test_cases = [
            # (raw_value, expected_classification)
            (510, "normal"),      # At baseline
            (520, "normal"),      # +1 std, still normal
            (530, "moderate"),    # +2 std, moderate
            (540, "high"),        # +3 std, high
            (560, "overload"),    # +5 std, overload
        ]
        
        for raw_value, expected_level in test_cases:
            # Reset processor for each test to avoid smoothing lag
            processor.reset()
            
            # Fill smoothing window with target value (simulate steady state)
            for _ in range(10):
                smoothed = processor.process_raw(raw_value)
            
            # Compute index
            eda_index = processor.compute_eda_index(smoothed)
            
            # Classify
            level = processor.classify_level(eda_index)
            
            # Verify
            assert level == expected_level, \
                f"Raw {raw_value} → smoothed {smoothed:.1f} → index {eda_index:.2f} " \
                f"→ level '{level}', expected '{expected_level}'"
    
    def test_multiple_processors_independent(self):
        """Test that multiple processor instances are independent."""
        proc1 = EDAProcessor(baseline_mean=500.0, baseline_std=5.0)
        proc2 = EDAProcessor(baseline_mean=520.0, baseline_std=10.0)
        
        # Process same value in both
        val = 510
        smoothed1 = proc1.process_raw(val)
        smoothed2 = proc2.process_raw(val)
        
        index1 = proc1.compute_eda_index(smoothed1)
        index2 = proc2.compute_eda_index(smoothed2)
        
        # Indices should be different due to different baselines
        assert index1 != index2
        
        # Windows should be independent
        for _ in range(5):
            proc1.process_raw(510)
        
        assert proc1.get_window_size() == 6  # One from earlier + 5 new
        assert proc2.get_window_size() == 1  # Still just the one value
    
    def test_continuous_monitoring_scenario(self):
        """Simulate continuous EDA monitoring during a session."""
        processor = EDAProcessor(baseline_mean=512.0, baseline_std=8.0)
        
        # Simulate: rest (512) → stress (540) → sustained relief
        # Smoothing window = 10 samples, so need sustained changes
        session_values = [
            # Rest phase (t=0-2s, 200 ms intervals)
            512, 511, 513, 512, 510,
            # Stress onset (t=2-4s) - aggressive rise
            520, 530, 540, 545, 550,
            # Peak stress (t=4-6s) - sustained high
            550, 555, 555, 550, 545,
            # Relief phase (t=6-10s) - longer to clear smoothing window
            535, 525, 520, 515, 513,
            512, 512, 511, 510, 512,
        ]
        
        classifications = []
        smoothed_values = []
        
        for raw_val in session_values:
            smoothed = processor.process_raw(raw_val)
            index = processor.compute_eda_index(smoothed)
            level = processor.classify_level(index)
            classifications.append(level)
            smoothed_values.append(smoothed)
        
        # Verify progression: normal → moderate/high → return towards normal
        # Smoothing causes lag, so check broader ranges
        assert classifications[0] == "normal"  # Start at rest
        assert "moderate" in classifications[5:15] or "high" in classifications[5:15]  # Stress detected
        
        # Check that smoothed values decrease during relief phase
        # (even if not back to normal classification due to window lag)
        relief_phase_smoothed = smoothed_values[-10:]  # Last 10 samples
        peak_phase_smoothed = smoothed_values[10:15]  # Peak samples
        
        # Average smoothed value should decrease during relief
        assert sum(relief_phase_smoothed[-5:]) < sum(peak_phase_smoothed) / len(peak_phase_smoothed) * 5
