# tests/conftest.py
"""Shared pytest fixtures for all tests.

Provides reusable test data, mock objects, and temporary resources
for unit and integration tests across the project.
"""

import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
# ============================================================================
# MOCK plux MODULE (Before any imports that depend on it)
# ============================================================================

# Mock plux before importing bitalino_reader
sys.modules['plux'] = MagicMock()

# Now we can safely import modules that depend on plux
from bitalino_reader import RawFrame
from calibration import (
    BaselineData,
    EDABaseline,
    EMGBaseline,
    ACCBaseline,
    FSRBaseline,
    PPGBaseline,
)


# ============================================================================
# FIXTURES: Temporary Resources
# ============================================================================

@pytest.fixture
def temp_dir() -> Path:
    """Provide a temporary directory for test outputs.
    
    Automatically cleaned up after test completion.
    
    Returns:
        Path object pointing to temporary directory.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# FIXTURES: Synthetic Sensor Data (2000 samples = 20 seconds at 100 Hz)
# ============================================================================

@pytest.fixture
def synthetic_eda_data() -> np.ndarray:
    """Generate synthetic EDA data: stable signal with minor noise.
    
    Simulates resting EDA with mean ~512 ADC units and low variation.
    Suitable for baseline computation and EDA processor testing.
    
    Returns:
        Numpy array of 2000 EDA samples.
    """
    np.random.seed(42)
    baseline = 512.0
    noise = np.random.normal(0, 5, 2000)
    data = baseline + noise
    return np.clip(data, 0, 65535)


@pytest.fixture
def synthetic_emg_data() -> np.ndarray:
    """Generate synthetic EMG data: baseline rest noise.
    
    Simulates resting EMG with minimal muscle tension.
    Mean ~510 ADC units with small standard deviation.
    
    Returns:
        Numpy array of 2000 EMG samples.
    """
    np.random.seed(42)
    baseline = 510.0
    noise = np.random.normal(0, 3, 2000)
    data = baseline + noise
    return np.clip(data, 0, 65535)


@pytest.fixture
def synthetic_acc_data() -> np.ndarray:
    """Generate synthetic ACC data: minimal movement at rest.
    
    Simulates accelerometer at rest with low variation.
    Mean ~515 ADC units.
    
    Returns:
        Numpy array of 2000 ACC samples.
    """
    np.random.seed(42)
    baseline = 515.0
    noise = np.random.normal(0, 2, 2000)
    data = baseline + noise
    return np.clip(data, 0, 65535)


@pytest.fixture
def synthetic_fsr_data() -> np.ndarray:
    """Generate synthetic FSR data: no pressure applied.
    
    Simulates force sensor at rest with baseline offset.
    Mean ~10 ADC units (no applied force).
    
    Returns:
        Numpy array of 2000 FSR samples.
    """
    np.random.seed(42)
    baseline = 10.0
    noise = np.random.normal(0, 1, 2000)
    data = baseline + noise
    return np.clip(data, 0, 100)


@pytest.fixture
def synthetic_ppg_data() -> np.ndarray:
    """Generate synthetic PPG data: realistic heartbeat signal.
    
    Simulates optical heart rate sensor with 60 bpm heartbeat.
    Uses sinusoidal pattern at 1 Hz with DC offset.
    
    Returns:
        Numpy array of 2000 PPG samples.
    """
    np.random.seed(42)
    heartbeat_freq = 1.0  # 60 bpm
    ppg_values = []
    for i in range(2000):
        t = i / 100.0  # 100 Hz sampling
        # Sinusoidal heartbeat with DC offset
        value = 520.0 + 100.0 * np.sin(2 * np.pi * heartbeat_freq * t)
        ppg_values.append(value)
    return np.array(ppg_values)


# ============================================================================
# FIXTURES: Complete Baseline Data
# ============================================================================

@pytest.fixture
def synthetic_baseline_data() -> BaselineData:
    """Generate complete synthetic baseline data for all sensors.
    
    Represents a realistic 20-second calibration at rest.
    All thresholds computed with realistic values.
    
    Returns:
        BaselineData object with all sensor baselines and thresholds.
    """
    return BaselineData(
        timestamp="2024-01-15T14:30:00",
        duration=20,
        sampling_rate=100,
        eda=EDABaseline(
            mean=512.0,
            std=10.0,
            min=480.0,
            max=540.0,
            samples_count=2000,
            threshold_moderate=532.0,  # mean + 2*std
            threshold_high=542.0,      # mean + 3*std
        ),
        emg=EMGBaseline(
            mean=510.0,
            std=8.0,
            min=490.0,
            max=530.0,
            samples_count=2000,
            rms_baseline=6.0,
            threshold_light=18.0,   # rms * 3
            threshold_strong=48.0,  # rms * 8
            threshold_target=30.0,  # rms * 5
        ),
        acc=ACCBaseline(
            mean=515.0,
            std=5.0,
            min=500.0,
            max=530.0,
            samples_count=2000,
            threshold_agitation=525.0,  # mean + 2*std
            threshold_movement=535.0,   # mean + 4*std
        ),
        fsr=FSRBaseline(
            mean=10.0,
            std=2.0,
            min=5.0,
            max=15.0,
            samples_count=2000,
            threshold_press=30.0,  # mean + 20
        ),
        ppg=PPGBaseline(
            mean=520.0,
            std=15.0,
            min=480.0,
            max=560.0,
            samples_count=2000,
            hrv_baseline=45.0,  # RMSSD in ms
            bpm_baseline=72.0,  # Beats per minute
        ),
    )


# ============================================================================
# FIXTURES: Mock Objects
# ============================================================================

@pytest.fixture
def mock_raw_frame() -> RawFrame:
    """Generate a realistic mock RawFrame for testing.
    
    Represents a single frame from BITalino acquisition.
    Contains realistic ADC values for all 6 channels.
    
    Returns:
        RawFrame with realistic sensor values.
    """
    return RawFrame(
        timestamp=time.time(),
        sequence=0,
        channels=[510, 512, 515, 10, 0, 520],  # EMG, EDA, ACC, FSR, _, PPG
    )


@pytest.fixture
def mock_raw_frame_stressed() -> RawFrame:
    """Generate a RawFrame representing stressed state.
    
    All sensors elevated compared to baseline:
    - EMG: high tension
    - EDA: elevated
    - ACC: movement
    - FSR: pressure applied
    - PPG: elevated heart rate
    
    Returns:
        RawFrame with stress-elevated sensor values.
    """
    return RawFrame(
        timestamp=time.time(),
        sequence=1000,
        channels=[540, 530, 535, 35, 0, 560],  # All elevated
    )


# ============================================================================
# FIXTURES: Data Collections (Multiple Frames)
# ============================================================================

@pytest.fixture
def synthetic_baseline_frames(synthetic_baseline_data: BaselineData) -> list:
    """Generate sequence of frames representing baseline calibration.
    
    Creates 2000 frames (20 seconds at 100 Hz) with values distributed
    around baseline means with appropriate noise.
    
    Args:
        synthetic_baseline_data: BaselineData fixture for reference values.
    
    Returns:
        List of 2000 RawFrame objects.
    """
    np.random.seed(42)
    frames = []
    
    for i in range(2000):
        emg = int(np.clip(
            np.random.normal(synthetic_baseline_data.emg.mean, 3),
            0, 65535
        ))
        eda = int(np.clip(
            np.random.normal(synthetic_baseline_data.eda.mean, 5),
            0, 65535
        ))
        acc = int(np.clip(
            np.random.normal(synthetic_baseline_data.acc.mean, 2),
            0, 65535
        ))
        fsr = int(np.clip(
            np.random.normal(synthetic_baseline_data.fsr.mean, 1),
            0, 100
        ))
        ppg = int(np.clip(
            synthetic_baseline_data.ppg.mean + 
            100 * np.sin(2 * np.pi * (i / 100.0)),
            0, 65535
        ))
        
        frame = RawFrame(
            timestamp=time.time() + (i / 100.0),
            sequence=i,
            channels=[emg, eda, acc, fsr, 0, ppg],
        )
        frames.append(frame)
    
    return frames


@pytest.fixture
def synthetic_stressed_frames(synthetic_baseline_data: BaselineData) -> list:
    """Generate sequence of frames representing stressed state.
    
    Creates 2000 frames with elevated values across all sensors,
    simulating cognitive load/stress.
    
    Args:
        synthetic_baseline_data: BaselineData fixture for reference values.
    
    Returns:
        List of 2000 RawFrame objects in stressed state.
    """
    np.random.seed(42)
    frames = []
    
    for i in range(2000):
        # Elevated baselines
        emg = int(np.clip(
            np.random.normal(530, 5),  # Higher than baseline
            0, 65535
        ))
        eda = int(np.clip(
            np.random.normal(525, 8),  # Higher than baseline
            0, 65535
        ))
        acc = int(np.clip(
            np.random.normal(530, 5),  # Higher than baseline
            0, 65535
        ))
        fsr = int(np.clip(
            np.random.normal(25, 3),  # Pressure applied
            0, 100
        ))
        ppg = int(np.clip(
            520 + 100 * np.sin(2 * np.pi * (2.0 * i / 100.0)),  # 120 bpm
            0, 65535
        ))
        
        frame = RawFrame(
            timestamp=time.time() + (i / 100.0),
            sequence=i + 2000,
            channels=[emg, eda, acc, fsr, 0, ppg],
        )
        frames.append(frame)
    
    return frames