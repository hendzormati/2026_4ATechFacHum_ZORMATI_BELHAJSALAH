"""Real-time sensor visualization module.

Provides live plotting of BITalino sensor data with rolling windows.
"""

from dataclasses import dataclass, field
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import sys
from pathlib import Path

# Add src to path for config import
sys.path.insert(0, str(Path(__file__).parent))

try:
    import config
except ImportError:
    # Default values if config not available
    class config:
        PLOT_WINDOW_DURATION = 10
        PLOT_UPDATE_INTERVAL = 100
        SAMPLING_RATE = 100
        PLOT_NAMES = {
            "EMG": "EMG : Contraction musculaire",
            "EDA": "EDA : Activité électrodermale",
            "ACC": "ACC : Micro-mouvements",
            "FSR": "FSR : Pression appliquée",
            "PPG": "PPG : Rythme cardiaque optique"
        }


@dataclass
class PlotData:
    """Data for a single sensor plot.
    
    Maintains rolling windows of timestamps and sensor values for
    efficient real-time visualization with minimal memory footprint.
    """
    timestamps: Deque[float]  # Rolling window of timestamps (seconds)
    values: Deque[float]  # Rolling window of sensor values (ADC units)
    max_size: int  # Maximum window size in samples
    min_val: float = float('inf')  # Track min value for auto-scaling
    max_val: float = float('-inf')  # Track max value for auto-scaling


class SensorVisualizer:
    """Real-time visualizer for BITalino sensor data.
    
    Displays 5 sensor plots simultaneously with rolling window updates.
    Supports both fixed and auto-scaling modes for y-axis.
    """
    
    # Default y-axis ranges for each sensor (can be overridden)
    SENSOR_RANGES = {
        "EMG": (400, 620),      # ADC 0-1023 typically 400-620
        "EDA": (480, 540),      # ADC 0-1023 typically 480-540
        "ACC": (300, 700),      # ADC 0-1023 typically 300-700
        "FSR": (0, 30),         # Low range sensor, 0-30
        "PPG": (300, 700)       # ADC 0-1023 typically 300-700
    }
    
    def __init__(
        self,
        window_duration: int,
        sampling_rate: int,
        auto_scale: bool = True
    ) -> None:
        """Initialize visualizer with empty plot data.
        
        Args:
            window_duration: Length of rolling window in seconds
            sampling_rate: Sampling frequency in Hz
            auto_scale: If True, automatically adjust y-axis to show all data
                       If False, use fixed SENSOR_RANGES
        """
        self.window_duration = window_duration
        self.sampling_rate = sampling_rate
        self.auto_scale = auto_scale
        self._update_interval = config.PLOT_UPDATE_INTERVAL
        
        # Calculate max samples for window
        max_samples = window_duration * sampling_rate
        
        # Initialize plot data for each sensor
        self.plot_data: Dict[str, PlotData] = {}
        for sensor in ["EMG", "EDA", "ACC", "FSR", "PPG"]:
            self.plot_data[sensor] = PlotData(
                timestamps=deque(maxlen=max_samples),
                values=deque(maxlen=max_samples),
                max_size=max_samples
            )
        
                # Matplotlib objects (initialized in setup_plots)
        self.fig: Optional[plt.Figure] = None
        self.axes: Dict[str, plt.Axes] = {}
        self.lines: Dict[str, plt.Line2D] = {}
        self.title_texts: Dict[str, plt.Text] = {}  # For dynamic titles with min/max
        self._animation: Optional[animation.FuncAnimation] = None
        self._start_time: float = 0.0
    
    def setup_plots(self) -> None:
        """Create matplotlib figure with 5 subplots.
        
        Configures axes labels, titles, and layout for each sensor.
        """
        # Create figure with 5 subplots (5 rows, 1 column)
        self.fig, axes = plt.subplots(5, 1, figsize=(12, 10))
        self.fig.suptitle("IQ Overload - Real-time Sensor Data", fontsize=14, fontweight='bold')
        
        # Create subplot for each sensor
        sensors = ["EMG", "EDA", "ACC", "FSR", "PPG"]
        for i, sensor in enumerate(sensors):
            ax = self._create_subplot(i, sensor, self.plot_data[sensor])
            self.axes[sensor] = ax
            
            # Create empty line object
            line, = ax.plot([], [], lw=2, color='#1f77b4')
            self.lines[sensor] = line
        
                # Adjust layout with more space for title
        self.fig.tight_layout()
        self.fig.subplots_adjust(top=0.92, hspace=0.4)
    
    def _create_subplot(
        self, 
        position: int, 
        sensor: str, 
        plot_data: PlotData
    ) -> plt.Axes:
        """Create a single subplot with proper configuration.
        
        Args:
            position: Subplot position index
            sensor: Sensor name
            plot_data: PlotData object for this sensor
            
        Returns:
            Configured matplotlib Axes object
        """
        ax = self.fig.get_axes()[position]
        
        # Get title from config
        title = config.PLOT_NAMES.get(sensor, sensor)
        ax.set_title(title, fontsize=11, fontweight='bold')
        
        # Configure axes
        ax.set_xlabel("Time (s)", fontsize=10)
        ax.set_ylabel("Value (ADC)", fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # Set x-axis limits
        ax.set_xlim(0, self.window_duration)
        
        # Set y-axis limits
        if self.auto_scale:
            # Start with a reasonable default, will auto-adjust
            ax.set_ylim(0, 1024)
        else:
            # Use fixed sensor ranges
            if sensor in self.SENSOR_RANGES:
                y_min, y_max = self.SENSOR_RANGES[sensor]
                ax.set_ylim(y_min, y_max)
            else:
                ax.set_ylim(0, 1024)
        
        return ax
    
    def update_data(self, sensor: str, timestamp: float, value: float) -> None:
        """Add new data point to rolling window.
        
        Args:
            sensor: Sensor name
            timestamp: Time of sample (relative to start)
            value: Sensor value (ADC units)
        """
        if sensor not in self.plot_data:
            return
        
        plot_data = self.plot_data[sensor]
        plot_data.timestamps.append(timestamp)
        plot_data.values.append(value)
        
        # Update min/max for auto-scaling
        if self.auto_scale:
            plot_data.min_val = min(plot_data.min_val, value)
            plot_data.max_val = max(plot_data.max_val, value)
    
    def update_plots(self) -> None:
        """Refresh all plots with current data.
        
        Updates line positions and axis limits based on accumulated data.
        Only displays the most recent window_duration worth of data to avoid
        matplotlib rendering issues with large datasets.
        """
        for sensor in self.plot_data:
            plot_data = self.plot_data[sensor]
            line = self.lines[sensor]
            ax = self.axes[sensor]
            
            # Convert deques to lists for plotting
            if len(plot_data.timestamps) > 0:
                times = list(plot_data.timestamps)
                values = list(plot_data.values)
                
                # Get current time and window boundaries
                current_time = times[-1] if times else 0
                window_start = max(0, current_time - self.window_duration)
                
                # Filter data to only show points within the rolling window
                # This prevents matplotlib from trying to render thousands of points
                visible_indices = [
                    i for i, t in enumerate(times)
                    if window_start <= t <= current_time
                ]
                
                if visible_indices:
                    # Extract only visible data points
                    visible_times = [times[i] for i in visible_indices]
                    visible_values = [values[i] for i in visible_indices]
                    line.set_data(visible_times, visible_values)
                else:
                    # No data in window, clear the line
                    line.set_data([], [])
                
                # Update x-axis limits to show rolling window
                x_min = window_start
                x_max = current_time if current_time > window_start else window_start + 0.1
                ax.set_xlim(x_min, x_max)
                
                # Update y-axis limits
                if self.auto_scale and visible_indices:
                    # Auto-scale with 10% padding
                    visible_vals = [values[i] for i in visible_indices]
                    y_min = min(visible_vals)
                    y_max = max(visible_vals)
                    
                    # Add padding for better visualization
                    y_range = max(y_max - y_min, 1)  # Avoid zero range
                    padding = y_range * 0.1
                    ax.set_ylim(y_min - padding, y_max + padding)
    
    def start(self) -> None:
        """Start visualization loop (blocks until window closed).
        
        Uses matplotlib animation with periodic updates.
        """
        if self.fig is None:
            self.setup_plots()
        
        self._start_time = 0
        
        # Create animation
        self._animation = animation.FuncAnimation(
            self.fig,
            self._animation_callback,
            interval=self._update_interval,
            blit=True
        )
        
        plt.show()
    
    def close(self) -> None:
        """Close the matplotlib figure."""
        if self.fig is not None:
            plt.close(self.fig)
            self.fig = None
            self.axes.clear()
            self.lines.clear()
    
    def _animation_callback(self, frame: int) -> List[plt.Line2D]:
        """Callback for matplotlib FuncAnimation.
        
        Args:
            frame: Frame number
            
        Returns:
            List of artists to redraw
        """
        self.update_plots()
        
        # Return list of line artists for blit
        return list(self.lines.values())
