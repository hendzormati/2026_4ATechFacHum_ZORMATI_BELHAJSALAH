"""Unit tests for visualizer module."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

# Set matplotlib to non-interactive backend BEFORE importing visualizer
import matplotlib
matplotlib.use('Agg')

from collections import deque
from visualizer import SensorVisualizer, PlotData


class TestPlotData:
    """Tests for PlotData dataclass."""
    
    def test_plotdata_creation(self):
        """Test PlotData can be created with valid data."""
        max_size = 1000
        plot_data = PlotData(
            timestamps=deque(maxlen=max_size),
            values=deque(maxlen=max_size),
            max_size=max_size
        )
        
        assert plot_data.max_size == 1000
        assert isinstance(plot_data.timestamps, deque)
        assert isinstance(plot_data.values, deque)
    
    def test_plotdata_deque_maxlen(self):
        """Test PlotData deques respect maxlen."""
        max_size = 100
        plot_data = PlotData(
            timestamps=deque(maxlen=max_size),
            values=deque(maxlen=max_size),
            max_size=max_size
        )
        
        assert plot_data.timestamps.maxlen == max_size
        assert plot_data.values.maxlen == max_size
    
    def test_plotdata_deque_behavior(self):
        """Test deque sliding window behavior."""
        plot_data = PlotData(
            timestamps=deque(maxlen=5),
            values=deque(maxlen=5),
            max_size=5
        )
        
        # Add more items than maxlen
        for i in range(10):
            plot_data.timestamps.append(float(i))
            plot_data.values.append(float(i * 10))
        
        # Only last 5 items should remain
        assert len(plot_data.timestamps) == 5
        assert len(plot_data.values) == 5
        assert list(plot_data.timestamps) == [5.0, 6.0, 7.0, 8.0, 9.0]
        assert list(plot_data.values) == [50.0, 60.0, 70.0, 80.0, 90.0]


class TestSensorVisualizerInitialization:
    """Tests for SensorVisualizer initialization."""
    
    def test_visualizer_init_default(self):
        """Test SensorVisualizer initializes with correct defaults."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        
        assert viz.window_duration == 10
        assert viz.sampling_rate == 100
        assert len(viz.plot_data) == 5
        assert viz.fig is None
        assert len(viz.axes) == 0
        assert len(viz.lines) == 0
    
    def test_visualizer_all_sensors_initialized(self):
        """Test all 5 sensors are initialized."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        
        expected_sensors = ["EMG", "EDA", "ACC", "FSR", "PPG"]
        for sensor in expected_sensors:
            assert sensor in viz.plot_data
            assert isinstance(viz.plot_data[sensor], PlotData)
    
    def test_visualizer_plot_data_maxsize(self):
        """Test plot_data deques have correct max_size."""
        window_duration = 10
        sampling_rate = 100
        expected_max = window_duration * sampling_rate  # 1000
        
        viz = SensorVisualizer(window_duration=window_duration, sampling_rate=sampling_rate)
        
        for sensor, plot_data in viz.plot_data.items():
            assert plot_data.max_size == expected_max
            assert plot_data.timestamps.maxlen == expected_max
            assert plot_data.values.maxlen == expected_max
    
    def test_visualizer_different_configs(self):
        """Test SensorVisualizer with different configurations."""
        viz1 = SensorVisualizer(window_duration=5, sampling_rate=50)
        assert viz1.plot_data["EMG"].max_size == 250
        
        viz2 = SensorVisualizer(window_duration=20, sampling_rate=200)
        assert viz2.plot_data["EMG"].max_size == 4000


class TestUpdateData:
    """Tests for update_data method."""
    
    def test_update_data_adds_to_window(self):
        """Test update_data adds single data point."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        
        viz.update_data("EMG", 0.5, 512.0)
        
        assert len(viz.plot_data["EMG"].timestamps) == 1
        assert len(viz.plot_data["EMG"].values) == 1
        assert viz.plot_data["EMG"].timestamps[0] == 0.5
        assert viz.plot_data["EMG"].values[0] == 512.0
    
    def test_update_data_multiple_points(self):
        """Test update_data with multiple points."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        
        for i in range(5):
            viz.update_data("EDA", float(i), 500.0 + i)
        
        assert len(viz.plot_data["EDA"].timestamps) == 5
        assert len(viz.plot_data["EDA"].values) == 5
        assert list(viz.plot_data["EDA"].values) == [500.0, 501.0, 502.0, 503.0, 504.0]
    
    def test_update_data_all_sensors(self):
        """Test update_data for all sensors."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        
        sensors = ["EMG", "EDA", "ACC", "FSR", "PPG"]
        for sensor in sensors:
            viz.update_data(sensor, 1.0, 512.0)
        
        for sensor in sensors:
            assert len(viz.plot_data[sensor].timestamps) == 1
            assert viz.plot_data[sensor].values[0] == 512.0
    
    def test_update_data_invalid_sensor(self):
        """Test update_data with invalid sensor name."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        
        # Should not raise, just return
        viz.update_data("INVALID", 0.0, 512.0)
        
        # No assertion, just verify it doesn't crash


class TestWindowSizeConstraint:
    """Tests for window size constraints."""
    
    def test_window_size_respected(self):
        """Test rolling window respects max size."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        max_size = 1000
        
        # Add more samples than window size
        for i in range(2000):
            viz.update_data("EMG", float(i) * 0.01, 512.0 + i % 100)
        
        # Should only have max_size samples
        assert len(viz.plot_data["EMG"].timestamps) == max_size
        assert len(viz.plot_data["EMG"].values) == max_size
    
    def test_sliding_window_old_data_removed(self):
        """Test old data is removed as new data arrives."""
        viz = SensorVisualizer(window_duration=1, sampling_rate=10)  # 10 samples max
        
        # Add first 5 samples
        for i in range(5):
            viz.update_data("ACC", float(i), float(i))
        
        assert len(viz.plot_data["ACC"].values) == 5
        assert list(viz.plot_data["ACC"].values) == [0.0, 1.0, 2.0, 3.0, 4.0]
        
        # Add 10 more samples (exceed max_size)
        for i in range(5, 15):
            viz.update_data("ACC", float(i), float(i))
        
        # Only last 10 samples should remain
        assert len(viz.plot_data["ACC"].values) == 10
        assert list(viz.plot_data["ACC"].values) == [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0]
    
    def test_window_size_different_rates(self):
        """Test window size calculation with different sampling rates."""
        # 20 seconds at 50 Hz = 1000 samples
        viz1 = SensorVisualizer(window_duration=20, sampling_rate=50)
        assert viz1.plot_data["EMG"].max_size == 1000
        
        # 5 seconds at 200 Hz = 1000 samples
        viz2 = SensorVisualizer(window_duration=5, sampling_rate=200)
        assert viz2.plot_data["EMG"].max_size == 1000


class TestSetupPlots:
    """Tests for setup_plots method - focus on data structures not matplotlib."""
    
    def test_setup_plots_attribute_creation(self):
        """Test setup_plots initializes figure and axes attributes."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        
        # Before setup_plots
        assert viz.fig is None
        assert len(viz.axes) == 0
        assert len(viz.lines) == 0
        
        # Call setup_plots
        viz.setup_plots()
        
        # After setup_plots
        assert viz.fig is not None
        assert len(viz.axes) == 5
        assert len(viz.lines) == 5
        
        # All sensors should have axes and lines
        for sensor in ["EMG", "EDA", "ACC", "FSR", "PPG"]:
            assert sensor in viz.axes
            assert sensor in viz.lines


class TestUpdatePlots:
    """Tests for update_plots method."""
    
    def test_update_plots_with_data(self):
        """Test update_plots works with data."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        viz.setup_plots()
        
        # Add some data
        for i in range(5):
            viz.update_data("EMG", float(i), 512.0 + i)
        
        # Should not crash
        viz.update_plots()
    
    def test_update_plots_empty_data(self):
        """Test update_plots handles empty data gracefully."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        viz.setup_plots()
        
        # Update plots with no data - should not crash
        viz.update_plots()


class TestClose:
    """Tests for close method."""
    
    def test_close_without_setup(self):
        """Test close works when setup_plots not called."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        
        # Should not crash
        viz.close()
        
        assert viz.fig is None
    
    def test_close_after_setup(self):
        """Test close clears resources after setup."""
        viz = SensorVisualizer(window_duration=10, sampling_rate=100)
        viz.setup_plots()
        
        # Verify resources exist
        assert viz.fig is not None
        assert len(viz.axes) > 0
        assert len(viz.lines) > 0
        
        # Close
        viz.close()
        
        # Verify resources cleared
        assert viz.fig is None
        assert len(viz.axes) == 0
        assert len(viz.lines) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])