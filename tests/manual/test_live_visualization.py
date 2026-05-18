"""Manual test for live BITalino data visualization.

Connect to actual BITalino hardware and display real-time sensor data
in 5 plots. Test sensor reactivity to physical actions.

Usage:
    python tests/manual/test_live_visualization.py

Instructions:
    1. Make sure BITalino is powered on and paired
    2. Run this script
    3. Watch the plots update in real-time
    4. Test sensor reactivity:
       - EMG: Flex a muscle (should spike within 200ms)
       - FSR: Press the button (should show immediate spike)
       - ACC: Move the device (should show movement)
       - EDA: Keep still (should show baseline with slow changes)
       - PPG: Keep still (should show heart rate pulses)
    5. Close the window to stop after 5 minutes
"""

import sys
from pathlib import Path
import time
import threading
import queue

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Set matplotlib to interactive mode
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
plt.ion()

try:
    import config
except ImportError:
    # Default config
    class config:
        BITALINO_MAC_ADDRESS = "98:D3:71:FE:4F:90"
        SAMPLING_RATE = 100
        ACTIVE_PORTS = [1, 2, 3, 4, 6]
        RESOLUTION = 16

from bitalino_reader import BITalinoReader
from visualizer import SensorVisualizer


def main():
    """Run live visualization test with actual BITalino."""
    print("=" * 70)
    print("IQ Overload - Live Data Visualization Test")
    print("=" * 70)
    print("\nConfiguration:")
    print(f"  MAC Address: {config.BITALINO_MAC_ADDRESS}")
    print(f"  Sampling Rate: {config.SAMPLING_RATE} Hz")
    print(f"  Active Ports: {config.ACTIVE_PORTS}")

    
        # Create queue for BITalino data
    # Increased size: at 100 Hz, 1000 frames = only 10 seconds of buffering
    # With slow matplotlib drawing, we need more buffer
    data_queue = queue.Queue(maxsize=5000)
    
    # Create BITalino reader
    print("\n[BITalino] Initializing reader...")
    reader = BITalinoReader(
        address=config.BITALINO_MAC_ADDRESS,
        sampling_rate=config.SAMPLING_RATE,
        active_ports=config.ACTIVE_PORTS,
        resolution=config.RESOLUTION,
        data_queue=data_queue
    )
    
    # Connect
    print("[BITalino] Connecting to device...")
    if not reader.connect():
        print("✗ Failed to connect to BITalino")
        return 1
    
    battery = reader.get_battery_level()
    print(f"✓ Connected (Battery: {battery}%)")
    
    # Create visualizer
    print("\n[Visualizer] Setting up plots...")
    visualizer = SensorVisualizer(window_duration=10, sampling_rate=config.SAMPLING_RATE)
    visualizer.setup_plots()
    plt.show(block=False)
    print("✓ Plots created and displayed")
    
    # Start acquisition
    print("\n[Acquisition] Starting BITalino acquisition...")
    try:
        reader.start_acquisition()
    except Exception as e:
        print(f"✗ Failed to start acquisition: {e}")
        return 1
    print("✓ Acquisition started at 100 Hz")
    
        # Main loop
    frame_count = 0
    dropped_frames = 0
    start_time = time.time()
    test_duration = 300  # 5 minutes
    last_print_time = start_time
    last_data_print = start_time
    first_frame_time = None  # For relative time calculation
    
    # Port to sensor mapping
    port_map = {
        1: "EMG",   # Port 1
        2: "EDA",   # Port 2
        3: "ACC",   # Port 3
        4: "FSR",   # Port 4
        6: "PPG"    # Port 6
    }
    
    print(f"\n[Main] Starting live visualization for {test_duration}s...")
    print("  Close the plot window to stop early.\n")
    print("[Data] Sample output (first few frames):")
    
    try:
        while time.time() - start_time < test_duration:
            try:
                # Get frame from queue with timeout
                frame = data_queue.get(timeout=0.5)
                frame_count += 1
                
                # Initialize relative time on first frame
                if first_frame_time is None:
                    first_frame_time = frame.timestamp
                
                # Calculate relative time (seconds since first frame)
                relative_time = frame.timestamp - first_frame_time
                
                                # Print periodic frame info
                wall_time = time.time()
                if wall_time - last_data_print < 0.5:  # Print every 0.5 seconds, not just first 5
                    if frame_count <= 5:
                        print(f"  Frame {frame_count}: seq={frame.sequence}, rel_time={relative_time:.3f}s, "
                              f"channels={frame.channels}")
                
                                # Convert raw values to sensor readings
                # channels array has exactly 5 elements: [EMG, EDA, ACC, FSR, PPG]
                # Use relative time for plotting (0-10 second window)
                if len(frame.channels) >= 5:
                    visualizer.update_data("EMG", relative_time, frame.channels[0])
                    visualizer.update_data("EDA", relative_time, frame.channels[1])
                    visualizer.update_data("ACC", relative_time, frame.channels[2])
                    visualizer.update_data("FSR", relative_time, frame.channels[3])
                    visualizer.update_data("PPG", relative_time, frame.channels[4])
                
                                # Update plots every 200ms (approximately 5 Hz updates)
                # This is much slower than data rate but keeps matplotlib responsive
                if frame_count % 20 == 0:
                    # Debug: print deque contents
                    emg_points = len(visualizer.plot_data["EMG"].values)
                    eda_points = len(visualizer.plot_data["EDA"].values)
    
                    visualizer.update_plots()
                    try:
                        visualizer.fig.canvas.draw()
                        visualizer.fig.canvas.flush_events()
                    except Exception as e:
                        # Window closed
                        print(f"\n[Main] Plot window closed by user ({e})")
                        break
                
                                # Print stats every 2 seconds
                wall_time = time.time()
                if wall_time - last_print_time >= 2.0:
                    elapsed = wall_time - start_time
                    rate = frame_count / elapsed
                    # Also print deque sizes
                    emg_pts = len(visualizer.plot_data["EMG"].values)
                    eda_pts = len(visualizer.plot_data["EDA"].values)
                    acc_pts = len(visualizer.plot_data["ACC"].values)
                    print(f"  [{int(elapsed):3d}s] Frames: {frame_count:6d} | "
                          f"Rate: {rate:6.1f} Hz | Queue: {data_queue.qsize():4d} | "
                          f"Deques: EMG={emg_pts:4d} EDA={eda_pts:4d} ACC={acc_pts:4d}")
                    last_print_time = wall_time
                    last_data_print = wall_time
                
            except queue.Empty:
                # No data available right now
                # Try drawing what we have (less frequently)
                if frame_count % 20 == 0:  # Every 200ms
                    try:
                        visualizer.update_plots()
                        visualizer.fig.canvas.draw()
                        visualizer.fig.canvas.flush_events()
                    except:
                        print("\n[Main] Plot window closed by user")
                        break
                continue
            except Exception as e:
                print(f"⚠ Error processing frame: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Test completed
        elapsed = time.time() - start_time
        print(f"\n[Main] Live visualization completed!")
        print(f"  Duration: {elapsed:.1f} seconds")
        print(f"  Total frames: {frame_count}")
        print(f"  Average rate: {frame_count / (elapsed + 0.001):.1f} Hz")
        print(f"  Queue timeouts: {dropped_frames}")
        
        # Verify data collection
        if frame_count > 0:
            print("  ✓ Data successfully collected from BITalino")
        else:
            print("  ✗ No data collected!")
        
    except KeyboardInterrupt:
        print("\n\n[Main] Interrupted by user (Ctrl+C)")
        elapsed = time.time() - start_time
        print(f"  Ran for: {elapsed:.1f} seconds")
        print(f"  Frames received: {frame_count}")
        
    finally:
        # Stop acquisition
        print("\n[Acquisition] Stopping BITalino acquisition...")
        try:
            reader.stop_acquisition()
            print("✓ Acquisition stopped cleanly")
        except Exception as e:
            print(f"⚠ Error stopping: {e}")
        
        # Close visualizer
        print("[Visualizer] Closing visualizer...")
        visualizer.close()
        plt.close('all')
        
        print("[Main] Live visualization test complete")
        print("=" * 70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())