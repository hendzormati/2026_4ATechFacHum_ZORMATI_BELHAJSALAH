# tests/test_calibration.py
"""Tests for calibration module."""

import pytest
import json
import tempfile
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import numpy as np
from datetime import datetime

from calibration import (
    CalibrationManager,
    BaselineData,
    EDABaseline,
    EMGBaseline,
    ACCBaseline,
    FSRBaseline,
    PPGBaseline,
)
import config


@pytest.fixture
def synthetic_eda_data() -> np.ndarray:
    """Synthetic EDA data: stable signal at 512 ± 10."""
    np.random.seed(42)
    baseline = 512.0
    noise = np.random.normal(0, 5, 2000)
    return baseline + noise


@pytest.fixture
def synthetic_emg_data() -> np.ndarray:
    """Synthetic EMG data: baseline rest noise."""
    np.random.seed(42)
    baseline = 510.0
    noise = np.random.normal(0, 3, 2000)
    return baseline + noise


@pytest.fixture
def synthetic_acc_data() -> np.ndarray:
    """Synthetic ACC data: minimal movement."""
    np.random.seed(42)
    baseline = 515.0
    noise = np.random.normal(0, 2, 2000)
    return baseline + noise


@pytest.fixture
def synthetic_fsr_data() -> np.ndarray:
    """Synthetic FSR data: no pressure."""
    np.random.seed(42)
    baseline = 10.0
    noise = np.random.normal(0, 1, 2000)
    return np.clip(baseline + noise, 0, 100)


@pytest.fixture
def synthetic_ppg_data() -> np.ndarray:
    """Synthetic PPG data: heartbeat signal."""
    np.random.seed(42)
    heartbeat_freq = 1.0
    ppg_values = []
    for i in range(2000):
        t = i / 100.0
        value = 520.0 + 100.0 * np.sin(2 * np.pi * heartbeat_freq * t)
        ppg_values.append(value)
    return np.array(ppg_values)


class TestCalibrationManagerInit:
    """Test CalibrationManager initialization."""

    def test_calibration_manager_init(self) -> None:
        """Verify manager initializes with correct parameters."""
        manager = CalibrationManager(duration=20, sampling_rate=100)
        
        assert manager.duration == 20
        assert manager.sampling_rate == 100
        assert manager.samples_required == 2000
        assert manager.baseline is None
        assert len(manager._raw_data) == 5
        assert all(len(v) == 0 for v in manager._raw_data.values())

    def test_calibration_manager_init_different_params(self) -> None:
        """Verify manager with different parameters."""
        manager = CalibrationManager(duration=10, sampling_rate=50)
        
        assert manager.duration == 10
        assert manager.sampling_rate == 50
        assert manager.samples_required == 500

# tests/test_calibration.py - REPLACE TestAddSample and complete rest of file

class TestAddSample:
    """Test sample addition."""

    def test_add_sample_single(self) -> None:
        """Add single sample for one sensor."""
        manager = CalibrationManager(duration=20, sampling_rate=100)
        
        manager.add_sample("EDA", 512.0)
        
        assert len(manager._raw_data["EDA"]) == 1
        assert manager._raw_data["EDA"][0] == 512.0

    def test_add_sample_multiple_sensors(self) -> None:
        """Add samples for multiple sensors."""
        manager = CalibrationManager(duration=20, sampling_rate=100)
        
        manager.add_sample("EDA", 512.0)
        manager.add_sample("EMG", 510.0)
        manager.add_sample("ACC", 515.0)
        manager.add_sample("FSR", 10.0)
        manager.add_sample("PPG", 520.0)
        
        assert len(manager._raw_data["EDA"]) == 1
        assert len(manager._raw_data["EMG"]) == 1
        assert len(manager._raw_data["ACC"]) == 1
        assert len(manager._raw_data["FSR"]) == 1
        assert len(manager._raw_data["PPG"]) == 1

    def test_add_sample_invalid_sensor(self) -> None:
        """Invalid sensor name should be ignored."""
        manager = CalibrationManager(duration=20, sampling_rate=100)
        
        manager.add_sample("INVALID", 500.0)
        
        # Invalid sensor should not be added to dictionary
        assert "INVALID" not in manager._raw_data

    def test_add_sample_many(self) -> None:
        """Add many samples."""
        manager = CalibrationManager(duration=20, sampling_rate=100)
        
        for i in range(100):
            manager.add_sample("EDA", 512.0 + i)
        
        assert len(manager._raw_data["EDA"]) == 100


class TestComputeAllBaselines:
    """Test complete baseline computation."""

    def test_compute_baseline_incomplete(self) -> None:
        """Cannot compute baseline if not complete."""
        manager = CalibrationManager(duration=20, sampling_rate=100)
        
        # Add only partial data
        for i in range(100):
            manager.add_sample("EDA", 512.0)
        
        with pytest.raises(ValueError):
            manager.compute_baseline()

    def test_compute_baseline_complete(
        self,
        synthetic_eda_data: np.ndarray,
        synthetic_emg_data: np.ndarray,
        synthetic_acc_data: np.ndarray,
        synthetic_fsr_data: np.ndarray,
        synthetic_ppg_data: np.ndarray,
    ) -> None:
        """Compute complete baseline with all sensors."""
        manager = CalibrationManager(duration=20, sampling_rate=100)
        
        # Add complete synthetic data
        for eda, emg, acc, fsr, ppg in zip(
            synthetic_eda_data,
            synthetic_emg_data,
            synthetic_acc_data,
            synthetic_fsr_data,
            synthetic_ppg_data,
        ):
            manager.add_sample("EDA", float(eda))
            manager.add_sample("EMG", float(emg))
            manager.add_sample("ACC", float(acc))
            manager.add_sample("FSR", float(fsr))
            manager.add_sample("PPG", float(ppg))
        
        assert manager.is_complete() is True
        
        baseline = manager.compute_baseline()
        
        assert isinstance(baseline, BaselineData)
        assert baseline.duration == 20
        assert baseline.sampling_rate == 100
        assert isinstance(baseline.eda, EDABaseline)
        assert isinstance(baseline.emg, EMGBaseline)
        assert isinstance(baseline.acc, ACCBaseline)
        assert isinstance(baseline.fsr, FSRBaseline)
        assert isinstance(baseline.ppg, PPGBaseline)
        
        # Verify baseline is stored
        assert manager.baseline is not None
        assert manager.baseline == baseline


class TestSaveAndLoadBaseline:
    """Test baseline persistence."""

    def test_save_baseline_without_compute(self) -> None:
        """Cannot save baseline if not computed."""
        manager = CalibrationManager(duration=20, sampling_rate=100)
        
        with pytest.raises(ValueError):
            manager.save_baseline()

    def test_save_baseline_creates_file(
        self,
        synthetic_eda_data: np.ndarray,
        synthetic_emg_data: np.ndarray,
        synthetic_acc_data: np.ndarray,
        synthetic_fsr_data: np.ndarray,
        synthetic_ppg_data: np.ndarray,
    ) -> None:
        """Save baseline creates JSON file."""
        manager = CalibrationManager(duration=20, sampling_rate=100)
        
        # Add complete data
        for eda, emg, acc, fsr, ppg in zip(
            synthetic_eda_data,
            synthetic_emg_data,
            synthetic_acc_data,
            synthetic_fsr_data,
            synthetic_ppg_data,
        ):
            manager.add_sample("EDA", float(eda))
            manager.add_sample("EMG", float(emg))
            manager.add_sample("ACC", float(acc))
            manager.add_sample("FSR", float(fsr))
            manager.add_sample("PPG", float(ppg))
        
        baseline = manager.compute_baseline()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = manager.save_baseline(tmpdir)
            
            # Verify file exists
            assert Path(filepath).exists()
            
            # Verify file is valid JSON
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert data["timestamp"] is not None
            assert data["duration"] == 20
            assert data["sampling_rate"] == 100
            assert "eda" in data
            assert "emg" in data

    def test_load_baseline_from_file(
        self,
        synthetic_eda_data: np.ndarray,
        synthetic_emg_data: np.ndarray,
        synthetic_acc_data: np.ndarray,
        synthetic_fsr_data: np.ndarray,
        synthetic_ppg_data: np.ndarray,
    ) -> None:
        """Load baseline from saved JSON file."""
        manager = CalibrationManager(duration=20, sampling_rate=100)
        
        # Add complete data
        for eda, emg, acc, fsr, ppg in zip(
            synthetic_eda_data,
            synthetic_emg_data,
            synthetic_acc_data,
            synthetic_fsr_data,
            synthetic_ppg_data,
        ):
            manager.add_sample("EDA", float(eda))
            manager.add_sample("EMG", float(emg))
            manager.add_sample("ACC", float(acc))
            manager.add_sample("FSR", float(fsr))
            manager.add_sample("PPG", float(ppg))
        
        baseline = manager.compute_baseline()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save baseline
            filepath = manager.save_baseline(tmpdir)
            
            # Load baseline in new manager
            manager2 = CalibrationManager(duration=20, sampling_rate=100)
            loaded_baseline = manager2.load_baseline(filepath)
            
            # Verify loaded baseline matches original
            assert loaded_baseline.duration == baseline.duration
            assert loaded_baseline.sampling_rate == baseline.sampling_rate
            assert loaded_baseline.eda.mean == pytest.approx(baseline.eda.mean)
            assert loaded_baseline.emg.rms_baseline == pytest.approx(
                baseline.emg.rms_baseline
            )
            assert loaded_baseline.fsr.threshold_press == pytest.approx(
                baseline.fsr.threshold_press
            )

    def test_save_and_load_roundtrip(
        self,
        synthetic_eda_data: np.ndarray,
        synthetic_emg_data: np.ndarray,
        synthetic_acc_data: np.ndarray,
        synthetic_fsr_data: np.ndarray,
        synthetic_ppg_data: np.ndarray,
    ) -> None:
        """Complete save/load roundtrip."""
        manager1 = CalibrationManager(duration=20, sampling_rate=100)
        
        # Add complete data
        for eda, emg, acc, fsr, ppg in zip(
            synthetic_eda_data,
            synthetic_emg_data,
            synthetic_acc_data,
            synthetic_fsr_data,
            synthetic_ppg_data,
        ):
            manager1.add_sample("EDA", float(eda))
            manager1.add_sample("EMG", float(emg))
            manager1.add_sample("ACC", float(acc))
            manager1.add_sample("FSR", float(fsr))
            manager1.add_sample("PPG", float(ppg))
        
        baseline1 = manager1.compute_baseline()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save
            filepath = manager1.save_baseline(tmpdir)
            
            # Load
            manager2 = CalibrationManager(duration=20, sampling_rate=100)
            baseline2 = manager2.load_baseline(filepath)
            
            # Verify complete match
            assert baseline2.to_dict() == baseline1.to_dict()
    """Test complete baseline computation."""

    def test_compute_baseline_incomplete(self) -> None:
        """Cannot compute baseline if not complete."""
        manager = CalibrationManager(duration=20, sampling_rate=100)
        
        # Add only partial data
        for i in range(100):
            manager.add_sample("EDA", 512.0)
        
        with pytest.raises(ValueError):
            manager.compute_baseline()

    def test_compute_baseline_complete(
        self,
        synthetic_eda_data: np.ndarray,
        synthetic_emg_data: np.ndarray,
        synthetic_acc_data: np.ndarray,
        synthetic_fsr_data: np.ndarray,
        synthetic_ppg_data: np.ndarray,
    ) -> None:
        """Compute complete baseline with all sensors."""
        manager = CalibrationManager(duration=20, sampling_rate=100)