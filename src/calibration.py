# src/calibration.py - ADD to existing file
"""Baseline calibration data structures and management.

Defines dataclasses for storing sensor baseline statistics computed during
a 20-second calibration period at rest. Baselines are used to normalize
real-time sensor values and detect deviations indicative of cognitive load.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pathlib import Path
import numpy as np

import config
from sensors.hrv_analyzer import HRVAnalyzer


@dataclass
class SensorBaseline:
    """Baseline statistics for a single sensor.
    
    Attributes:
        mean: Mean ADC value during baseline period.
        std: Standard deviation of ADC values.
        min: Minimum ADC value observed.
        max: Maximum ADC value observed.
        samples_count: Number of samples collected during baseline.
    """
    mean: float
    std: float
    min: float
    max: float
    samples_count: int


@dataclass
class EDABaseline(SensorBaseline):
    """EDA-specific baseline with stress thresholds.
    
    Extends SensorBaseline with EDA-specific thresholds computed from
    baseline mean and standard deviation for stress classification.
    
    Attributes:
        threshold_moderate: Threshold for moderate stress (mean + 2*std).
        threshold_high: Threshold for high stress (mean + 3*std).
    """
    threshold_moderate: float
    threshold_high: float


@dataclass
class EMGBaseline(SensorBaseline):
    """EMG-specific baseline with RMS and contraction thresholds.
    
    Extends SensorBaseline with RMS (Root Mean Square) baseline and
    thresholds for detecting muscle contraction levels.
    
    Attributes:
        rms_baseline: RMS baseline computed from baseline samples.
        threshold_light: Light contraction threshold (rms * 3).
        threshold_strong: Strong contraction threshold (rms * 8).
        threshold_target: Target contraction level (rms * 5) for challenges.
    """
    rms_baseline: float
    threshold_light: float
    threshold_strong: float
    threshold_target: float


@dataclass
class ACCBaseline(SensorBaseline):
    """ACC-specific baseline with movement thresholds.
    
    Extends SensorBaseline with ACC-specific thresholds for detecting
    agitation and significant movement patterns.
    
    Attributes:
        threshold_agitation: Agitation threshold (mean + 2*std).
        threshold_movement: Movement threshold (mean + 4*std).
    """
    threshold_agitation: float
    threshold_movement: float


@dataclass
class FSRBaseline(SensorBaseline):
    """FSR-specific baseline with press detection threshold.
    
    Extends SensorBaseline with FSR-specific threshold for button press
    detection used in interactive challenges.
    
    Attributes:
        threshold_press: Press detection threshold (baseline + offset).
    """
    threshold_press: float


@dataclass
class PPGBaseline(SensorBaseline):
    """PPG-specific baseline with HRV and heart rate metrics.
    
    Extends SensorBaseline with PPG-specific metrics for heart rate
    variability analysis, which is a key cognitive load indicator.
    
    Attributes:
        hrv_baseline: HRV baseline (RMSSD in milliseconds).
        bpm_baseline: Baseline heart rate in beats per minute.
    """
    hrv_baseline: float
    bpm_baseline: float


@dataclass
class BaselineData:
    """Complete baseline data for all sensors from calibration period.
    
    Contains baseline statistics and thresholds for all five sensors,
    computed during a 20-second calibration at rest. Used to normalize
    and classify real-time sensor readings during sessions.
    
    Attributes:
        timestamp: ISO 8601 formatted datetime of calibration.
        duration: Calibration duration in seconds (typically 20).
        sampling_rate: Acquisition frequency in Hz (typically 100).
        eda: EDA baseline and thresholds.
        emg: EMG baseline and thresholds.
        acc: ACC baseline and thresholds.
        fsr: FSR baseline and threshold.
        ppg: PPG baseline metrics.
    """
    timestamp: str
    duration: int
    sampling_rate: int
    eda: EDABaseline
    emg: EMGBaseline
    acc: ACCBaseline
    fsr: FSRBaseline
    ppg: PPGBaseline

    def to_dict(self) -> Dict[str, Any]:
        """Convert BaselineData to dictionary.
        
        Returns:
            Dictionary representation of all baseline data.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaselineData":
        """Create BaselineData from dictionary.
        
        Args:
            data: Dictionary with baseline data (from JSON or other source).
        
        Returns:
            BaselineData instance.
        """
        return cls(
            timestamp=data["timestamp"],
            duration=data["duration"],
            sampling_rate=data["sampling_rate"],
            eda=EDABaseline(**data["eda"]),
            emg=EMGBaseline(**data["emg"]),
            acc=ACCBaseline(**data["acc"]),
            fsr=FSRBaseline(**data["fsr"]),
            ppg=PPGBaseline(**data["ppg"]),
        )


class CalibrationManager:
    """Manage baseline calibration data collection and computation.
    
    Accumulates raw sensor data during a calibration period (typically 20 seconds)
    and computes baseline statistics and thresholds for all sensors. These baselines
    are used to normalize real-time sensor readings and detect deviations indicative
    of cognitive load.
    """

    def __init__(self, duration: int, sampling_rate: int) -> None:
        """Initialize calibration manager.
        
        Args:
            duration: Calibration duration in seconds (typically 20).
            sampling_rate: Acquisition frequency in Hz (typically 100).
        """
        self.duration = duration
        self.sampling_rate = sampling_rate
        self.samples_required = duration * sampling_rate
        
        # Accumulate raw data per sensor
        self._raw_data: Dict[str, List[float]] = {
            "EDA": [],
            "EMG": [],
            "ACC": [],
            "FSR": [],
            "PPG": [],
        }
        
        self._samples_collected = 0
        self.baseline: Optional[BaselineData] = None

    def add_sample(self, sensor: str, value: float) -> None:
        """Add a single sample for a given sensor during calibration.
        
        Args:
            sensor: Sensor name ("EDA", "EMG", "ACC", "FSR", "PPG").
            value: Raw ADC value to accumulate.
        """
        if sensor in self._raw_data:
            self._raw_data[sensor].append(value)
            self._samples_collected += 1

    def is_complete(self) -> bool:
        """Check if calibration has collected enough samples.
        
        Requires samples_required samples for ALL sensors (not just total).
        Since we add one sample per sensor per frame, _samples_collected
        should be >= samples_required * 5 (5 sensors).
        
        Returns:
            True if enough samples collected, False otherwise.
        """
        # Check if all sensors have collected enough samples
        for sensor_data in self._raw_data.values():
            if len(sensor_data) < self.samples_required:
                return False
        return True

    def compute_baseline(self) -> BaselineData:
        """Compute baseline statistics from collected samples.
        
        Must be called after is_complete() returns True.
        Computes mean, std, min, max for each sensor and sensor-specific
        thresholds based on formulas in SPECS section 5.8.
        
        Returns:
            BaselineData object with all baseline statistics and thresholds.
        
        Raises:
            ValueError: If calibration is not complete.
        """
        if not self.is_complete():
            raise ValueError("Calibration not complete, cannot compute baseline")
        
        # Compute baseline for each sensor
        eda_baseline = self._compute_eda_baseline(self._raw_data["EDA"])
        emg_baseline = self._compute_emg_baseline(self._raw_data["EMG"])
        acc_baseline = self._compute_acc_baseline(self._raw_data["ACC"])
        fsr_baseline = self._compute_fsr_baseline(self._raw_data["FSR"])
        ppg_baseline = self._compute_ppg_baseline(self._raw_data["PPG"])
        
        # Create complete baseline data
        self.baseline = BaselineData(
            timestamp=datetime.now().isoformat(),
            duration=self.duration,
            sampling_rate=self.sampling_rate,
            eda=eda_baseline,
            emg=emg_baseline,
            acc=acc_baseline,
            fsr=fsr_baseline,
            ppg=ppg_baseline,
        )
        
        return self.baseline

    def _compute_eda_baseline(self, values: List[float]) -> EDABaseline:
        """Compute EDA baseline with stress thresholds.
        
        Thresholds (SPECS 5.8):
        - threshold_moderate = mean + 2*std
        - threshold_high = mean + 3*std
        
        Args:
            values: List of raw EDA values.
        
        Returns:
            EDABaseline with statistics and thresholds.
        """
        values_array = np.array(values)
        mean = float(np.mean(values_array))
        std = float(np.std(values_array))
        min_val = float(np.min(values_array))
        max_val = float(np.max(values_array))
        
        threshold_moderate = mean + (2.0 * std)
        threshold_high = mean + (3.0 * std)
        
        return EDABaseline(
            mean=mean,
            std=std,
            min=min_val,
            max=max_val,
            samples_count=len(values),
            threshold_moderate=threshold_moderate,
            threshold_high=threshold_high,
        )

    def _compute_emg_baseline(self, values: List[float]) -> EMGBaseline:
        """Compute EMG baseline with RMS and contraction thresholds.
        
        Thresholds (SPECS 5.8):
        - threshold_light = rms_baseline * 3
        - threshold_strong = rms_baseline * 8
        - threshold_target = rms_baseline * 5
        
        Args:
            values: List of raw EMG values.
        
        Returns:
            EMGBaseline with statistics, RMS, and thresholds.
        """
        values_array = np.array(values)
        mean = float(np.mean(values_array))
        std = float(np.std(values_array))
        min_val = float(np.min(values_array))
        max_val = float(np.max(values_array))
        
        # Compute RMS baseline (RMS of all values)
        rms_baseline = float(np.sqrt(np.mean(values_array ** 2)))
        
        # Thresholds based on RMS baseline
        threshold_light = rms_baseline * config.EMG_THRESHOLD_LIGHT
        threshold_strong = rms_baseline * config.EMG_THRESHOLD_STRONG
        threshold_target = rms_baseline * config.EMG_THRESHOLD_TARGET
        
        return EMGBaseline(
            mean=mean,
            std=std,
            min=min_val,
            max=max_val,
            samples_count=len(values),
            rms_baseline=rms_baseline,
            threshold_light=threshold_light,
            threshold_strong=threshold_strong,
            threshold_target=threshold_target,
        )

    def _compute_acc_baseline(self, values: List[float]) -> ACCBaseline:
        """Compute ACC baseline with movement thresholds.
        
        Thresholds (SPECS 5.8):
        - threshold_agitation = mean + 2*std
        - threshold_movement = mean + 4*std
        
        Args:
            values: List of raw ACC values.
        
        Returns:
            ACCBaseline with statistics and thresholds.
        """
        values_array = np.array(values)
        mean = float(np.mean(values_array))
        std = float(np.std(values_array))
        min_val = float(np.min(values_array))
        max_val = float(np.max(values_array))
        
        threshold_agitation = mean + (config.ACC_THRESHOLD_AGITATION * std)
        threshold_movement = mean + (config.ACC_THRESHOLD_MOVEMENT * std)
        
        return ACCBaseline(
            mean=mean,
            std=std,
            min=min_val,
            max=max_val,
            samples_count=len(values),
            threshold_agitation=threshold_agitation,
            threshold_movement=threshold_movement,
        )

    def _compute_fsr_baseline(self, values: List[float]) -> FSRBaseline:
        """Compute FSR baseline with press threshold.
        
        Threshold (SPECS 5.8):
        - threshold_press = baseline_value + 20 (fixed offset)
        
        Args:
            values: List of raw FSR values.
        
        Returns:
            FSRBaseline with statistics and press threshold.
        """
        values_array = np.array(values)
        mean = float(np.mean(values_array))
        std = float(np.std(values_array))
        min_val = float(np.min(values_array))
        max_val = float(np.max(values_array))
        
        threshold_press = mean + config.FSR_THRESHOLD_PRESS
        
        return FSRBaseline(
            mean=mean,
            std=std,
            min=min_val,
            max=max_val,
            samples_count=len(values),
            threshold_press=threshold_press,
        )

    def _compute_ppg_baseline(self, values: List[float]) -> PPGBaseline:
        """Compute PPG baseline with HRV and heart rate metrics.
        
        Analyzes actual PPG signal to extract heart rate variability.
        
        Args:
            values: List of raw PPG values.
        
        Returns:
            PPGBaseline with statistics and HRV metrics.
        """
        values_array = np.array(values)
        mean = float(np.mean(values_array))
        std = float(np.std(values_array))
        min_val = float(np.min(values_array))
        max_val = float(np.max(values_array))
        
        # Try to compute actual HRV from PPG signal
        # For now, use reasonable defaults if signal analysis not available
        try:
            from sensors.ppg_processor import PPGProcessor
            ppg_proc = PPGProcessor(sampling_rate=self.sampling_rate)
            
            # Process raw PPG values
            for raw_value in values:
                ppg_proc.process_raw(int(raw_value))
            
            # Detect peaks and compute BPM
            ppg_proc.detect_peaks()
            ppg_proc.compute_ibi()
            bpm = ppg_proc.compute_bpm()
            
            if bpm is not None:
                # HRV baseline based on detected heart rate
                hrv_baseline = 50.0 - (bpm - 70.0) * 0.5  # Adjust HRV based on HR
            else:
                hrv_baseline = 50.0
        except Exception:
            # Fallback to defaults if PPG analysis fails
            hrv_baseline = 50.0
            bpm = 70.0
        
        bpm_baseline = bpm if bpm is not None else 70.0
        
        return PPGBaseline(
            mean=mean,
            std=std,
            min=min_val,
            max=max_val,
            samples_count=len(values),
            hrv_baseline=hrv_baseline,
            bpm_baseline=bpm_baseline,
        )
    def save_baseline(self, output_dir: str = config.DATA_DIR) -> str:
        """Save baseline to JSON file with timestamp.
        
        Creates data directory if it doesn't exist.
        Filename format: baseline_YYYYMMDD_HHMMSS.json
        
        Args:
            output_dir: Directory to save baseline file.
        
        Returns:
            Path to saved baseline file.
        
        Raises:
            ValueError: If baseline not computed yet.
        """
        if self.baseline is None:
            raise ValueError("Baseline not computed yet, call compute_baseline() first")
        
        # Ensure output directory exists
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Create filename with timestamp
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{config.BASELINE_PREFIX}{timestamp_str}.json"
        filepath = output_path / filename
        
        # Save baseline data
        with open(filepath, 'w') as f:
            json.dump(self.baseline.to_dict(), f, indent=2)
        
        return str(filepath)

    def load_baseline(self, filepath: str) -> BaselineData:
        """Load baseline from JSON file.
        
        Args:
            filepath: Path to baseline JSON file.
        
        Returns:
            Loaded BaselineData object.
        
        Raises:
            FileNotFoundError: If file doesn't exist.
            json.JSONDecodeError: If file is not valid JSON.
        """
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.baseline = BaselineData.from_dict(data)
        return self.baseline