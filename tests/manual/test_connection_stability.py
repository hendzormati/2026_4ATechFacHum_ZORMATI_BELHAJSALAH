"""Manual test for BITalino connection stability.

Run this script to validate connection stability for 10 minutes.
Monitor that:
- Connection established
- Battery level displayed
- Data flows continuously without drops
- Ctrl+C stops gracefully
"""

import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"

os.chdir(SRC_DIR)
sys.path.insert(0, str(SRC_DIR))
os.add_dll_directory(str(SRC_DIR))

import queue
import time
from datetime import datetime
from bitalino_reader import BITalinoReader


def main():
    """Run 10-minute connection stability test."""
    print("=" * 70)
    print("BITalino Connection Stability Test")
    print("=" * 70)
    
    # Configuration
    address = "98:D3:71:FE:4F:90"
    sampling_rate = 100
    active_ports = [1, 2, 3, 4, 6]
    resolution = 16
    test_duration = 600  # 10 minutes in seconds
    
    # Create queue and reader
    data_queue = queue.Queue(maxsize=1000)
    reader = BITalinoReader(
        address=address,
        sampling_rate=sampling_rate,
        active_ports=active_ports,
        resolution=resolution,
        data_queue=data_queue
    )
    
    try:
        # Connect
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Connecting to {address}...")
        if not reader.connect():
            print("✗ Failed to connect")
            return 1
        
        
        # Start acquisition
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting acquisition...")
        reader.start_acquisition()
        print("✓ Acquisition started")
        
        # Run for test_duration seconds
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Running stability test for {test_duration}s...")
        print("-" * 70)
        
        start_time = time.time()
        frame_count = 0
        last_print_time = start_time
        
        while time.time() - start_time < test_duration:
            try:
                # Get frame from queue with timeout
                frame = reader.data_queue.get(timeout=0.5)
                frame_count += 1
                
                # Print every 1 second
                current_time = time.time()
                if current_time - last_print_time >= 1.0:
                    elapsed = int(current_time - start_time)
                    rate = frame_count / (current_time - start_time)
                    channels_str = " | ".join(
                        f"A{active_ports[i]}: {frame.channels[i]:5d}"
                        for i in range(len(frame.channels))
                    )
                    print(
                        f"[{elapsed:3d}s] "
                        f"Frames: {frame_count:6d} | "
                        f"Rate: {rate:6.1f} Hz | "
                        f"{channels_str}"
                    )
                    last_print_time = current_time
                    
            except queue.Empty:
                print(f"⚠ Queue timeout - no data received")
                continue
        
        # Test completed successfully
        print("-" * 70)
        elapsed = time.time() - start_time
        print(f"\n✓ Test completed successfully!")
        print(f"  Duration: {elapsed:.1f} seconds")
        print(f"  Total frames received: {frame_count}")
        print(f"  Average rate: {frame_count / elapsed:.1f} Hz")
        print(f"  Expected frames: {int(test_duration * sampling_rate)}")
        
        if frame_count < test_duration * sampling_rate * 0.9:
            print(f"⚠ Warning: Frame count below 90% of expected")
        
    except KeyboardInterrupt:
        print("\n\n⏹ Interrupted by user (Ctrl+C)")
        elapsed = time.time() - start_time
        print(f"  Ran for: {elapsed:.1f} seconds")
        print(f"  Frames received: {frame_count}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        # Clean shutdown
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Stopping acquisition...")
        try:
            reader.stop_acquisition()
            print("✓ Acquisition stopped cleanly")
        except Exception as e:
            print(f"⚠ Error during shutdown: {e}")
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Test complete")
        print("=" * 70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())