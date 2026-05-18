"""Integration test for visualizer with synthetic sensor data.

Run this script to see the visualizer displaying 5 sensors with synthetic data
in real-time for 60 seconds. Data is generated at 100 Hz to simulate actual
BITalino acquisition.

Usage:
    python tests/manual/test_visualizer_integration.py
"""

import sys
from pathlib import Path
import time
import threading
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Set matplotlib to interactive mode BEFORE importing visualizer
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
plt.ion()  # Enable interactive mode

from visualizer import SensorVisualizer


def generate_synthetic_data(sensor: str, elapsed_time: float) -> float:
    """Generate synthetic sensor data that simulates real readings.
    
    Args:
        sensor: Sensor name
        elapsed_time: Time since start in seconds
        
    Returns:
        Synthetic sensor value (ADC units)
    """
    # Base values for each sensor
    base_values = {
        "EMG": 510.0,
        "EDA": 512.0,
        "ACC": 515.0,
        "FSR": 10.0,
        "PPG": 520.0
    }
    
    base = base_values.get(sensor, 512.0)
    
    # Add different patterns to each sensor to make visualization interesting
    if sensor == "EMG":
        # Simulate muscle contractions
        noise = np.random.normal(0, 2)
        contraction = 20 * np.sin(elapsed_time * 0.5) if elapsed_time % 10 < 5 else 0
        return base + noise + contraction
    
    elif sensor == "EDA":
        # Simulate stress response (gradual rise)
        stress = 15 * np.sin(elapsed_time * 0.1)
        noise = np.random.normal(0, 1)
        return base + stress + noise
    
    elif sensor == "ACC":
        # Simulate movements
        movement = 10 * np.sin(elapsed_time * 0.3)
        jitter = np.random.normal(0, 1)
        return base + movement + jitter
    
    elif sensor == "FSR":
        # Simulate button presses
        press = 15.0 if (int(elapsed_time * 2) % 4 < 1) else 0
        noise = np.random.normal(0, 0.5)
        return max(0, base + press + noise)
    
    elif sensor == "PPG":
        # Simulate heart rate signal
        hr_wave = 8 * np.sin(elapsed_time * 1.2)  # Heart rate variation
        noise = np.random.normal(0, 3)
        return base + hr_wave + noise
    
    return base


def data_generation_thread(visualizer: SensorVisualizer, stop_event: threading.Event):
    """Thread that generates and feeds synthetic data to visualizer.
    
    Args:
        visualizer: SensorVisualizer instance
        stop_event: Event to signal thread to stop
    """
    sampling_rate = 100  # Hz
    frame_interval = 1.0 / sampling_rate
    
    start_time = time.time()
    frame_count = 0
    
    print("[Data Generation] Starting synthetic data generation...")
    
    while not stop_event.is_set():
        current_time = time.time()
        elapsed = current_time - start_time
        
        # Generate data for all sensors
        sensors = ["EMG", "EDA", "ACC", "FSR", "PPG"]
        for sensor in sensors:
            value = generate_synthetic_data(sensor, elapsed)
            visualizer.update_data(sensor, elapsed, value)
        
        frame_count += 1
        
        # Print progress every 1 second
        if frame_count % sampling_rate == 0:
            expected_frames = int(elapsed * sampling_rate)
            print(f"  [{int(elapsed):3d}s] Generated {frame_count:6d} frames "
                  f"({frame_count / (elapsed + 0.001):.1f} Hz)")
        
        # Sleep to maintain 100 Hz rate
        next_frame_time = start_time + (frame_count * frame_interval)
        sleep_time = next_frame_time - current_time
        if sleep_time > 0:
            time.sleep(sleep_time)
    
    print(f"[Data Generation] Stopped after {frame_count} frames ({elapsed:.1f}s)")


def main():
    """Run integration test with visualizer and synthetic data."""
    print("=" * 70)
    print("IQ Overload - Visualizer Integration Test")
    print("=" * 70)
    print("\nConfiguration:")
    print("  Window duration: 10 seconds")
    print("  Sampling rate: 100 Hz")
    print("  Test duration: 60 seconds")
    print("  Sensors: EMG, EDA, ACC, FSR, PPG")
    print("\nInstructions:")
    print("  - Watch the 5 plots update in real-time")
    print("  - Close the window to stop the test")
    print("  - Data is generated at 100 Hz to simulate BITalino")
    print("\n" + "=" * 70)
    
    # Create visualizer
    visualizer = SensorVisualizer(window_duration=10, sampling_rate=100)
    
    # Setup plots
    print("\n[Visualizer] Setting up plots...")
    visualizer.setup_plots()
    plt.show(block=False)
    print("[Visualizer] Plots created and displayed")
    
    # Create stop event
    stop_event = threading.Event()
    
    # Start data generation thread
    print("[Thread] Starting data generation thread...")
    data_thread = threading.Thread(
        target=data_generation_thread,
        args=(visualizer, stop_event),
        daemon=True
    )
    data_thread.start()
    
    # Main loop
    frame_count = 0
    start_time = time.time()
    test_duration = 60  # seconds
    
    print(f"\n[Main] Starting display loop for {test_duration} seconds...")
    print("  Close the plot window to stop the test.\n")
    
    try:
        # Update plots periodically
        while time.time() - start_time < test_duration:
            # Update plots
            visualizer.update_plots()
            
            # Redraw
            try:
                visualizer.fig.canvas.draw()
                visualizer.fig.canvas.flush_events()
            except:
                # Window closed
                print("\n[Main] Plot window closed by user")
                break
            
            frame_count += 1
            
            # Small sleep to prevent CPU spinning
            time.sleep(0.05)  # ~20 Hz update rate for visualization
        
        # Test completed successfully
        elapsed = time.time() - start_time
        print(f"\n[Main] Test completed!")
        print(f"  Duration: {elapsed:.1f} seconds")
        print(f"  Visualization updates: {frame_count}")
        print(f"  Update rate: {frame_count / (elapsed + 0.001):.1f} Hz")
        
    except KeyboardInterrupt:
        print("\n\n[Main] Interrupted by user (Ctrl+C)")
        
    finally:
        # Stop data thread
        print("\n[Main] Stopping data generation thread...")
        stop_event.set()
        data_thread.join(timeout=2.0)
        
        # Close visualizer
        print("[Main] Closing visualizer...")
        visualizer.close()
        plt.close('all')
        
        print("[Main] Integration test complete")
        print("=" * 70)


if __name__ == "__main__":
    main()