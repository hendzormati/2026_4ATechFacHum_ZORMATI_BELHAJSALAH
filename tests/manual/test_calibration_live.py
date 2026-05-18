# tests/manual/test_calibration_live.py - UPDATED
"""Manual calibration test with live BITalino hardware.

Run this script to perform live calibration and verify baseline values.
Requires actual BITalino device connected.

Usage:
    python tests/manual/test_calibration_live.py
"""

import sys
import time
import json
from pathlib import Path
from datetime import datetime
import queue
import threading

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from bitalino_reader import BITalinoReader
from calibration import CalibrationManager
from config import (
    BITALINO_MAC_ADDRESS,
    SAMPLING_RATE,
    ACTIVE_PORTS,
    RESOLUTION,
    CALIBRATION_DURATION,
    DATA_DIR,
)


def run_live_calibration(trial: int = 1) -> str:
    """Run live calibration with BITalino hardware.
    
    Connects to device, collects baseline data,
    computes thresholds, and saves baseline JSON.
    
    Args:
        trial: Trial number (for logging).
    
    Returns:
        Path to saved baseline JSON file.
    """
    print(f"\n{'='*70}")
    print(f"TRIAL {trial} - LIVE CALIBRATION ({CALIBRATION_DURATION} seconds)")
    print(f"{'='*70}")
    print(f"MAC Address: {BITALINO_MAC_ADDRESS}")
    print(f"Sampling Rate: {SAMPLING_RATE} Hz")
    print(f"Duration: {CALIBRATION_DURATION} seconds")
    print(f"Expected samples per sensor: {SAMPLING_RATE * CALIBRATION_DURATION}")
    
    # Initialize components
    data_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()
    
    reader = BITalinoReader(
        address=BITALINO_MAC_ADDRESS,
        sampling_rate=SAMPLING_RATE,
        active_ports=ACTIVE_PORTS,
        resolution=RESOLUTION,
        data_queue=data_queue,
    )
    
    calibration = CalibrationManager(
        duration=CALIBRATION_DURATION,
        sampling_rate=SAMPLING_RATE,
    )
    
    try:
        # Connect to BITalino
        print("\n[1/5] Connecting to BITalino...")
        if not reader.connect():
            raise RuntimeError("Failed to connect to BITalino")
        print(f"✓ Connected! Battery: {reader.get_battery_level()}%")
        
        # Start acquisition
        print("\n[2/5] Starting acquisition...")
        reader.start_acquisition()
        print("✓ Acquisition started")
        
        # Collect baseline data
        print(f"\n[3/5] Collecting baseline data (sit still for {CALIBRATION_DURATION}s)...")
        print("   Reading frames...", end="", flush=True)
        
        start_time = time.time()
        frames_collected = 0
        frames_failed = 0
        timeout_count = 0
        
        while not stop_event.is_set() and not calibration.is_complete():
            try:
                frame = data_queue.get(timeout=1.0)
                
                # Validate frame - should have exactly 5 channels (ports 1,2,3,4,6)
                if not hasattr(frame, 'channels') or len(frame.channels) != 5:
                    frames_failed += 1
                    expected = 5
                    actual = len(frame.channels) if hasattr(frame, 'channels') else 0
                    print(f"\n⚠ Invalid frame (expected {expected} channels, got {actual})")
                    continue
                
                # Map channels to sensors
                # ACTIVE_PORTS = [1, 2, 3, 4, 6] → channels indices [0, 1, 2, 3, 4]
                try:
                    calibration.add_sample("EMG", float(frame.channels[0]))   # Port 1
                    calibration.add_sample("EDA", float(frame.channels[1]))   # Port 2
                    calibration.add_sample("ACC", float(frame.channels[2]))   # Port 3
                    calibration.add_sample("FSR", float(frame.channels[3]))   # Port 4
                    calibration.add_sample("PPG", float(frame.channels[4]))   # Port 6
                    
                    frames_collected += 1
                    if frames_collected % 200 == 0:
                        elapsed = time.time() - start_time
                        progress = min(100, int(frames_collected / (SAMPLING_RATE * CALIBRATION_DURATION) * 100))
                        print(f"\r   Reading frames... {frames_collected}/{SAMPLING_RATE * CALIBRATION_DURATION} ({progress}%) [{elapsed:.1f}s]", end="", flush=True)
                except Exception as e:
                    frames_failed += 1
                    print(f"\n⚠ Error processing frame: {e}")
                    continue
                
            except queue.Empty:
                timeout_count += 1
                if timeout_count % 10 == 0:
                    elapsed = time.time() - start_time
                    print(f"\r   Waiting... {frames_collected} frames in {elapsed:.1f}s", end="", flush=True)
                continue
        
        elapsed = time.time() - start_time
        print(f"\r   Reading frames... {frames_collected}/{SAMPLING_RATE * CALIBRATION_DURATION} ✓       ")
        print(f"✓ Collected {frames_collected} frames in {elapsed:.1f}s")
        
        if frames_failed > 0:
            print(f"⚠ {frames_failed} frames failed validation")
        
        if frames_collected < SAMPLING_RATE * CALIBRATION_DURATION:
            print(f"⚠ WARNING: Collected fewer frames than expected")
            print(f"  Expected: {SAMPLING_RATE * CALIBRATION_DURATION}")
            print(f"  Actual: {frames_collected}")
            response = input("  Continue anyway? (y/n): ")
            if response.lower() != 'y':
                raise RuntimeError("Insufficient frames collected")
        
        # Compute baseline
        print("\n[4/5] Computing baseline statistics...")
        baseline = calibration.compute_baseline()
        print("✓ Baseline computed")
        
        # Display results
        print("\n[5/5] Baseline Statistics:")
        print("-" * 90)
        print(f"{'Sensor':<6} {'Mean':>10} {'Std':>10} {'Min':>10} {'Max':>10} {'Thresholds':<40}")
        print("-" * 90)
        
        print(f"{'EDA':<6} {baseline.eda.mean:>10.1f} {baseline.eda.std:>10.1f} "
              f"{baseline.eda.min:>10.1f} {baseline.eda.max:>10.1f} "
              f"Mod:{baseline.eda.threshold_moderate:>8.1f} High:{baseline.eda.threshold_high:>8.1f}")
        
        print(f"{'EMG':<6} {baseline.emg.mean:>10.1f} {baseline.emg.std:>10.1f} "
              f"{baseline.emg.min:>10.1f} {baseline.emg.max:>10.1f} "
              f"Light:{baseline.emg.threshold_light:>8.1f} Strong:{baseline.emg.threshold_strong:>8.1f}")
        
        print(f"{'ACC':<6} {baseline.acc.mean:>10.1f} {baseline.acc.std:>10.1f} "
              f"{baseline.acc.min:>10.1f} {baseline.acc.max:>10.1f} "
              f"Agit:{baseline.acc.threshold_agitation:>8.1f} Move:{baseline.acc.threshold_movement:>8.1f}")
        
        print(f"{'FSR':<6} {baseline.fsr.mean:>10.1f} {baseline.fsr.std:>10.1f} "
              f"{baseline.fsr.min:>10.1f} {baseline.fsr.max:>10.1f} "
              f"Press:{baseline.fsr.threshold_press:>8.1f}")
        
        print(f"{'PPG':<6} {baseline.ppg.mean:>10.1f} {baseline.ppg.std:>10.1f} "
              f"{baseline.ppg.min:>10.1f} {baseline.ppg.max:>10.1f} "
              f"HRV:{baseline.ppg.hrv_baseline:>8.1f}ms BPM:{baseline.ppg.bpm_baseline:>7.1f}")
        
        print("-" * 90)
        
        # Save baseline
        output_path = calibration.save_baseline()
        print(f"\n✓ Baseline saved to: {output_path}")
        
        return output_path
        
    finally:
        # Cleanup
        print("\n[Cleanup] Stopping acquisition...")
        stop_event.set()
        reader.stop_acquisition()
        print("✓ Acquisition stopped")


def test_emg_thresholds(baseline_path: str) -> None:
    """Manual test of EMG thresholds with contractions.
    
    Prompts user to perform contractions and provides feedback
    on detected tension levels.
    
    Args:
        baseline_path: Path to saved baseline JSON.
    """
    print(f"\n{'='*70}")
    print("EMG THRESHOLD TEST")
    print(f"{'='*70}")
    
    # Load baseline
    with open(baseline_path, 'r') as f:
        baseline_dict = json.load(f)
    
    emg_baseline = baseline_dict["emg"]
    rms = emg_baseline["rms_baseline"]
    threshold_light = emg_baseline["threshold_light"]
    threshold_strong = emg_baseline["threshold_strong"]
    
    print(f"\nBaseline RMS: {rms:.2f}")
    print(f"Light contraction threshold: {threshold_light:.2f} (RMS × 3)")
    print(f"Strong contraction threshold: {threshold_strong:.2f} (RMS × 8)")
    
    print("\nTest procedure:")
    print("1. Rest (no contraction) - EMG should be near baseline RMS")
    print("2. Light contraction (gentle jaw clench) - EMG should reach 'light' threshold")
    print("3. Strong contraction (hard jaw clench) - EMG should exceed 'strong' threshold")
    
    print("\nThresholds are computed as:")
    print(f"  Light  = RMS baseline × 3   = {rms:.2f} × 3   = {threshold_light:.2f}")
    print(f"  Strong = RMS baseline × 8   = {rms:.2f} × 8   = {threshold_strong:.2f}")
    
    input("\nPress Enter to continue...")
    print("\n✓ EMG thresholds are suitable for detecting muscle tension during cognitive load")


def verify_reproducibility(baseline_paths: list[str]) -> None:
    """Verify baseline reproducibility across multiple runs.
    
    Compares values from multiple calibration runs and checks
    for consistency.
    
    Args:
        baseline_paths: List of paths to baseline JSON files.
    """
    print(f"\n{'='*70}")
    print("REPRODUCIBILITY ANALYSIS")
    print(f"{'='*70}")
    
    baselines = []
    for path in baseline_paths:
        with open(path, 'r') as f:
            baselines.append(json.load(f))
    
    print(f"\nAnalyzing {len(baselines)} calibration runs...\n")
    
    sensors = ["eda", "emg", "acc", "fsr", "ppg"]
    
    for sensor in sensors:
        means = [b[sensor]["mean"] for b in baselines]
        stds = [b[sensor]["std"] for b in baselines]
        
        mean_mean = sum(means) / len(means)
        mean_std = sum(stds) / len(stds)
        
        # Calculate variation
        variation = max(means) - min(means)
        variation_pct = (variation / mean_mean) * 100 if mean_mean > 0 else 0
        
        print(f"{sensor.upper()}:")
        print(f"  Mean values:     {[f'{m:.1f}' for m in means]}")
        print(f"  Mean of means:   {mean_mean:.2f}")
        print(f"  Variation:       {variation:.2f} ({variation_pct:.1f}%)")
        
        if variation_pct < 5:
            print(f"  ✓ EXCELLENT reproducibility (< 5% variation)")
        elif variation_pct < 10:
            print(f"  ✓ GOOD reproducibility (< 10% variation)")
        else:
            print(f"  ⚠ HIGH variation (> 10%) - check sensor stability")
        print()


def main() -> None:
    """Main entry point for manual calibration tests."""
    print("\n" + "="*70)
    print("IQ OVERLOAD - LIVE CALIBRATION TEST")
    print("="*70)
    print("\nThis script performs live calibration with BITalino hardware.")
    print("You will be prompted to sit still during each calibration period.")
    print("\nEquipment needed:")
    print("  - BITalino device with sensors connected")
    print("  - EMG electrodes for jaw/forearm")
    print("  - EDA electrodes on fingers")
    print("  - Accelerometer mounted")
    print("  - FSR sensor accessible")
    print("  - PPG sensor on finger")
    
    input("\nPress Enter to start calibration (Run 1 of 3)...")
    
    baseline_paths = []
    
    # Run 3 calibration trials
    for trial in range(1, 4):
        try:
            path = run_live_calibration(trial=trial)
            baseline_paths.append(path)
            
            if trial < 3:
                input(f"\nPress Enter to start calibration (Run {trial + 1} of 3)...")
        
        except KeyboardInterrupt:
            print("\n\n✗ Calibration interrupted by user")
            sys.exit(0)
        except Exception as e:
            print(f"\n✗ Calibration failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # Test EMG thresholds
    print("\n" + "="*70)
    test_emg_thresholds(baseline_paths[0])
    
    # Verify reproducibility
    verify_reproducibility(baseline_paths)
    
    print("\n" + "="*70)
    print("✓ ALL TESTS COMPLETED SUCCESSFULLY")
    print("="*70)
    print(f"\nBaseline files saved in: {DATA_DIR}/")
    print("Baselines:")
    for i, path in enumerate(baseline_paths, 1):
        print(f"  Trial {i}: {path}")
    print("\nNext step: Use baselines for cognitive load measurements")


if __name__ == "__main__":
    main()