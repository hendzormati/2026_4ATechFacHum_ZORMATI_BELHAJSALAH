# tests/test_sensors/test_hrv_analyzer.py
"""Unit tests for HRVAnalyzer."""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from sensors.hrv_analyzer import HRVAnalyzer, HRVMetrics
import config


class TestHRVMetricsDataclass:
    """Test HRVMetrics dataclass."""

    def test_hrv_metrics_creation(self) -> None:
        """Verify HRVMetrics can be instantiated."""
        metrics = HRVMetrics(
            rmssd=45.5,
            sdnn=50.2,
            mean_ibi=900.0,
            mean_hr=66.67
        )
        
        assert metrics.rmssd == 45.5
        assert metrics.sdnn == 50.2
        assert metrics.mean_ibi == 900.0
        assert metrics.mean_hr == 66.67

    def test_hrv_metrics_realistic_values(self) -> None:
        """Test with realistic HRV values."""
        # Relaxed state: high RMSSD, high SDNN, stable HR
        relaxed = HRVMetrics(
            rmssd=60.0,
            sdnn=70.0,
            mean_ibi=1000.0,
            mean_hr=60.0
        )
        
        assert relaxed.rmssd > 50.0
        assert relaxed.sdnn > 60.0
        
        # Stressed state: low RMSSD, low SDNN, elevated HR
        stressed = HRVMetrics(
            rmssd=20.0,
            sdnn=25.0,
            mean_ibi=500.0,
            mean_hr=120.0
        )
        
        assert stressed.rmssd < 30.0
        assert stressed.mean_hr > 100.0


class TestHRVAnalyzerInit:
    """Test HRVAnalyzer initialization."""

    def test_hrv_analyzer_init_default(self) -> None:
        """Verify analyzer initializes with default window."""
        analyzer = HRVAnalyzer()
        
        assert analyzer.window_size == 60
        assert analyzer._min_ibi_count == 5

    def test_hrv_analyzer_init_custom_window(self) -> None:
        """Verify analyzer with custom window size."""
        analyzer = HRVAnalyzer(window_size=120)
        
        assert analyzer.window_size == 120


class TestComputeRMSSD:
    """Test RMSSD calculation."""

    def test_compute_rmssd_no_data(self) -> None:
        """Empty IBI list should return None."""
        analyzer = HRVAnalyzer()
        
        rmssd = analyzer.compute_rmssd([])
        
        assert rmssd is None

    def test_compute_rmssd_insufficient_data(self) -> None:
        """Fewer than 5 IBIs should return None."""
        analyzer = HRVAnalyzer()
        
        rmssd = analyzer.compute_rmssd([800.0, 810.0, 790.0, 820.0])
        
        assert rmssd is None

    def test_compute_rmssd_exactly_min(self) -> None:
        """Exactly 5 IBIs should be computed."""
        analyzer = HRVAnalyzer()
        
        # IBIs: [800, 820, 810, 830, 815] ms
        # Diffs: [20, -10, 20, -15]
        # Diffs^2: [400, 100, 400, 225]
        # Mean: 281.25
        # RMSSD: sqrt(281.25) ≈ 16.77
        ibi_values = [800.0, 820.0, 810.0, 830.0, 815.0]
        
        rmssd = analyzer.compute_rmssd(ibi_values)
        
        assert rmssd is not None
        assert rmssd == pytest.approx(16.77, abs=0.1)

    def test_compute_rmssd_stable_heart_rate(self) -> None:
        """Constant IBIs should give zero RMSSD."""
        analyzer = HRVAnalyzer()
        
        # All IBIs = 1000 ms, differences = 0
        ibi_values = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0]
        
        rmssd = analyzer.compute_rmssd(ibi_values)
        
        assert rmssd == pytest.approx(0.0)

    def test_compute_rmssd_variable_ibis(self) -> None:
        """Variable IBIs should produce non-zero RMSSD."""
        analyzer = HRVAnalyzer()
        
        # IBIs with variation
        ibi_values = [900.0, 950.0, 880.0, 970.0, 920.0]
        
        rmssd = analyzer.compute_rmssd(ibi_values)
        
        assert rmssd is not None
        assert rmssd > 0.0
        assert rmssd < 100.0  # Should be reasonable for HR variation

    def test_compute_rmssd_large_variation(self) -> None:
        """Large IBI variations should produce larger RMSSD."""
        analyzer = HRVAnalyzer()
        
        # Large variations
        ibi_values = [800.0, 1200.0, 700.0, 1100.0, 750.0]
        
        rmssd = analyzer.compute_rmssd(ibi_values)
        
        assert rmssd is not None
        assert rmssd > 100.0  # Should be significant

    def test_compute_rmssd_relaxed_state(self) -> None:
        """Simulate relaxed state: high, stable RMSSD."""
        analyzer = HRVAnalyzer()
        
        # Stable ~60 bpm with small variation (healthy relaxation)
        ibi_values = [990.0, 1005.0, 995.0, 1008.0, 992.0, 1010.0]
        
        rmssd = analyzer.compute_rmssd(ibi_values)
        
        assert rmssd is not None
        assert rmssd > 5.0  # Good parasympathetic tone


class TestComputeSDNN:
    """Test SDNN calculation."""

    def test_compute_sdnn_no_data(self) -> None:
        """Empty IBI list should return None."""
        analyzer = HRVAnalyzer()
        
        sdnn = analyzer.compute_sdnn([])
        
        assert sdnn is None

    def test_compute_sdnn_insufficient_data(self) -> None:
        """Fewer than 5 IBIs should return None."""
        analyzer = HRVAnalyzer()
        
        sdnn = analyzer.compute_sdnn([800.0, 810.0, 790.0, 820.0])
        
        assert sdnn is None

    def test_compute_sdnn_stable_heart_rate(self) -> None:
        """Constant IBIs should give zero SDNN."""
        analyzer = HRVAnalyzer()
        
        ibi_values = [1000.0, 1000.0, 1000.0, 1000.0, 1000.0]
        
        sdnn = analyzer.compute_sdnn(ibi_values)
        
        assert sdnn == pytest.approx(0.0)

    def test_compute_sdnn_variable_ibis(self) -> None:
        """Variable IBIs should produce non-zero SDNN."""
        analyzer = HRVAnalyzer()
        
        # Mean = 920, std should be computed
        ibi_values = [900.0, 950.0, 880.0, 970.0, 920.0]
        
        sdnn = analyzer.compute_sdnn(ibi_values)
        
        assert sdnn is not None
        assert sdnn > 0.0
        
        # Verify against numpy
        expected_sdnn = np.std(ibi_values)
        assert sdnn == pytest.approx(expected_sdnn)

    def test_compute_sdnn_exactly_min(self) -> None:
        """Exactly 5 IBIs should be computed."""
        analyzer = HRVAnalyzer()
        
        ibi_values = [800.0, 820.0, 810.0, 830.0, 815.0]
        sdnn = analyzer.compute_sdnn(ibi_values)
        
        assert sdnn is not None
        expected = np.std(ibi_values)
        assert sdnn == pytest.approx(expected)


class TestComputeMetrics:
    """Test HRVMetrics calculation."""

    def test_compute_metrics_insufficient_data(self) -> None:
        """Fewer than 5 IBIs should return None."""
        analyzer = HRVAnalyzer()
        
        ibi_values = [900.0, 950.0]
        
        metrics = analyzer.compute_metrics(ibi_values)
        
        assert metrics is None

    def test_compute_metrics_valid_data(self) -> None:
        """Valid IBI data should return HRVMetrics."""
        analyzer = HRVAnalyzer()
        ibi_values = [900.0, 950.0, 880.0, 970.0, 920.0]
        
        metrics = analyzer.compute_metrics(ibi_values)
        
        assert metrics is not None
        assert isinstance(metrics, HRVMetrics)
        assert metrics.rmssd > 0.0
        assert metrics.sdnn > 0.0
        # Mean of [900, 950, 880, 970, 920] = 924
        assert metrics.mean_ibi == pytest.approx(924.0)
        # BPM = 60000 / 924 ≈ 64.9
        assert metrics.mean_hr == pytest.approx(60000.0 / 924.0)

    def test_compute_metrics_relaxed_state(self) -> None:
        """Relaxed state: lower HR (60 bpm), high HRV."""
        analyzer = HRVAnalyzer()
        # ~60 bpm = 1000 ms IBI with high variation
        ibi_values = [950.0, 1050.0, 980.0, 1020.0, 1000.0]
        
        metrics = analyzer.compute_metrics(ibi_values)
        
        assert metrics is not None
        assert 55 <= metrics.mean_hr <= 65
        assert metrics.rmssd > 20.0  # High HRV (relaxed)

    def test_compute_metrics_stressed_state(self) -> None:
        """Stressed state: elevated HR, moderate variation."""
        analyzer = HRVAnalyzer()
        # ~120 bpm = 500 ms IBI
        # Successive diffs: [10, -5, 5, -10]
        # RMSSD = sqrt(mean([100, 25, 25, 100])) = sqrt(62.5) ≈ 7.9
        ibi_values = [495.0, 505.0, 500.0, 505.0, 495.0]
        
        metrics = analyzer.compute_metrics(ibi_values)
        
        assert metrics is not None
        assert 115 <= metrics.mean_hr <= 125
        assert metrics.rmssd == pytest.approx(7.9, abs=0.5)



class TestComputeHRVDrop:
    """Test HRV drop percentage calculation."""

    def test_hrv_drop_no_change(self) -> None:
        """Same baseline and current should give 0% drop."""
        analyzer = HRVAnalyzer()
        
        drop = analyzer.compute_hrv_drop(
            current_rmssd=50.0,
            baseline_rmssd=50.0
        )
        
        assert drop == pytest.approx(0.0)

    def test_hrv_drop_50_percent(self) -> None:
        """50% drop: baseline 100, current 50."""
        analyzer = HRVAnalyzer()
        
        drop = analyzer.compute_hrv_drop(
            current_rmssd=50.0,
            baseline_rmssd=100.0
        )
        
        assert drop == pytest.approx(50.0)

    def test_hrv_drop_complete(self) -> None:
        """Complete drop: current = 0."""
        analyzer = HRVAnalyzer()
        
        drop = analyzer.compute_hrv_drop(
            current_rmssd=0.0,
            baseline_rmssd=50.0
        )
        
        assert drop == pytest.approx(100.0)

    def test_hrv_drop_increase(self) -> None:
        """Increase in HRV (negative drop)."""
        analyzer = HRVAnalyzer()
        
        drop = analyzer.compute_hrv_drop(
            current_rmssd=60.0,
            baseline_rmssd=50.0
        )
        
        assert drop == pytest.approx(-20.0)

    def test_hrv_drop_significant_stress(self) -> None:
        """Significant HRV drop (stress indicator)."""
        analyzer = HRVAnalyzer()
        
        # Baseline 45 ms, stressed state 27 ms = 40% drop
        drop = analyzer.compute_hrv_drop(
            current_rmssd=27.0,
            baseline_rmssd=45.0
        )
        
        assert drop == pytest.approx(40.0)

    def test_hrv_drop_overload_threshold(self) -> None:
        """HRV drop > 40% (config.HRV_DROP_OVERLOAD)."""
        analyzer = HRVAnalyzer()
        
        # 50% drop = overload
        drop = analyzer.compute_hrv_drop(
            current_rmssd=25.0,
            baseline_rmssd=50.0
        )
        
        assert drop > config.HRV_DROP_OVERLOAD

    def test_hrv_drop_zero_baseline(self) -> None:
        """Zero baseline should return 0 to avoid division error."""
        analyzer = HRVAnalyzer()
        
        drop = analyzer.compute_hrv_drop(
            current_rmssd=50.0,
            baseline_rmssd=0.0
        )
        
        assert drop == 0.0


class TestIntegration:
    """Integration tests for HRVAnalyzer."""

    def test_full_hrv_analysis_relaxed(self) -> None:
        """Complete analysis: relaxed state."""
        analyzer = HRVAnalyzer()
        
        # Stable 60 bpm with good HRV
        ibi_values = [1000.0, 1010.0, 990.0, 1005.0, 995.0, 1008.0]
        
        metrics = analyzer.compute_metrics(ibi_values)
        
        assert metrics is not None
        assert 55 <= metrics.mean_hr <= 65
        assert metrics.rmssd > 5.0
        
        # Compare to baseline (same values)
        drop = analyzer.compute_hrv_drop(
            current_rmssd=metrics.rmssd,
            baseline_rmssd=metrics.rmssd
        )
        
        assert drop == pytest.approx(0.0)


    def test_full_hrv_analysis_stress_transition(self) -> None:
        """Simulate transition from relaxed to stressed."""
        analyzer = HRVAnalyzer()
        
        # Baseline: relaxed state (high HRV with variable intervals)
        # Intervals: 1000 ± 100 ms (high variation)
        baseline_ibi = [900.0, 1100.0, 950.0, 1050.0, 1000.0, 1080.0, 920.0]
        baseline_metrics = analyzer.compute_metrics(baseline_ibi)
        assert baseline_metrics is not None
        baseline_rmssd = baseline_metrics.rmssd
        baseline_hr = baseline_metrics.mean_hr
        
        # Current: stressed (low HRV with tight intervals)
        # Intervals: 500 ± 10 ms (low variation)
        stressed_ibi = [490.0, 510.0, 495.0, 505.0, 500.0, 505.0, 495.0]
        stressed_metrics = analyzer.compute_metrics(stressed_ibi)
        assert stressed_metrics is not None
        
        # HR should roughly double (60 → 120 bpm)
        assert stressed_metrics.mean_hr > baseline_hr * 1.8, \
            f"Expected HR > {baseline_hr * 1.8}, got {stressed_metrics.mean_hr}"
        
        # HRV should decrease significantly (high to low)
        assert stressed_metrics.rmssd < baseline_rmssd, \
            f"Expected stressed RMSSD < baseline, got {stressed_metrics.rmssd} vs {baseline_rmssd}"
        
        # HRV drop should be significant (>50% reduction)
        drop = analyzer.compute_hrv_drop(
            current_rmssd=stressed_metrics.rmssd,
            baseline_rmssd=baseline_rmssd
        )
        assert drop > 50.0, f"Expected drop > 50%, got {drop}%"
    def test_realistic_hrv_window(self) -> None:
        """Analyze realistic 60-second window of IBIs."""
        analyzer = HRVAnalyzer(window_size=60)
        
        # Generate 60 IBIs (typical 1 Hz acquisition)
        # Normal human heart rate: 60 ± 15 bpm = 1000 ± 250 ms IBI
        np.random.seed(42)
        ibi_values = np.random.normal(1000.0, 50.0, 60).tolist()
        
        metrics = analyzer.compute_metrics(ibi_values)
        
        assert metrics is not None
        assert 55 <= metrics.mean_hr <= 65
        assert metrics.rmssd > 20.0  # Healthy HRV
        assert metrics.sdnn > 40.0