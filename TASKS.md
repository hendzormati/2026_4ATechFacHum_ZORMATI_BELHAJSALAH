# TASKS.md - IQ Overload Phase 1
 
## Project Status
**Current Phase**: Phase 1 - Implementation  
**Last Updated**: 2026-05-06  
**Sprint Goal**: Complete Phase 1 - Acquisition, Signal Processing & Reporting
 
---
 
## Task Legend
- 🔴 **Not Started**
- 🟡 **In Progress**
- 🟢 **Completed**
- ⚪ **Blocked**
- 🔵 **Testing**
---
 
## Phase 1 - Étape 1: Connexion Continue
 
### T1.1: Create `src/config.py` 🟢
**Priority**: P0 (Critical)  
**Estimated Time**: 1 hour  
**Dependencies**: None
 
**Description:**
Create configuration file with all constants defined in SPECS.md section 2.1.
 
**Acceptance Criteria:**
- [x] All constants from SPECS.md section 2.1 implemented
- [x] `BITALINO_MAC_ADDRESS` configurable
- [x] `PORT_MAPPING` dictionary correct (ports 1,2,3,4,6)
- [x] `PLOT_NAMES` dictionary with French labels
- [x] All threshold constants defined
- [x] Type hints on all constants
- [x] Docstring at module level
**Files to Create:**
- `src/config.py`
**Testing:**
- [x] Import test: `from config import *` works
- [x] Verify all constants accessible
---
 
### T1.2: Modify `src/bitalino_reader.py` - Add RawFrame dataclass 🟢
**Priority**: P0 (Critical)  
**Estimated Time**: 30 minutes  
**Dependencies**: None
 
**Description:**
Add RawFrame dataclass as defined in SPECS.md section 2.2.
 
**Acceptance Criteria:**
- [x] `@dataclass RawFrame` with timestamp, sequence, channels
- [x] Type hints: `timestamp: float`, `sequence: int`, `channels: List[int]`
- [x] Docstring explaining structure
**Files Modified:**
- `src/bitalino_reader.py`
**Testing:**
- [x] Can instantiate RawFrame with valid data
- [x] Attributes accessible correctly
---
 
### T1.3: Modify `src/bitalino_reader.py` - Implement BITalinoReader class 🟢
**Priority**: P0 (Critical)  
**Estimated Time**: 4 hours  
**Dependencies**: T1.1, T1.2
 
**Description:**
Implement BITalinoReader class that inherits from plux.SignalsDev with threading support.
 
**Acceptance Criteria:**
- [x] Inherits from `plux.SignalsDev`
- [x] All attributes from SPECS.md section 2.2
- [x] `__init__()` method with signature from specs
- [x] `connect()` method returns bool
- [x] `start_acquisition()` spawns thread and calls `_acquisition_loop()`
- [x] `stop_acquisition()` sets stop_event and waits for thread
- [x] `get_battery_level()` returns int
- [x] `onRawFrame()` creates RawFrame and puts in queue
- [x] `_acquisition_loop()` calls `plux.loop()` until stop_event
- [x] `_reconnect()` attempts reconnection up to MAX_RECONNECTION_ATTEMPTS
- [x] Proper exception handling in all methods
- [x] Type hints on all methods
- [x] Docstrings on all public methods
**Notes:**
- Used `__new__` override to work around plux C extension initialization on Windows
- `connect()` calls `plux.SignalsDev.__init__(self.address)` for accurate battery reading
**Files Modified:**
- `src/bitalino_reader.py`
**Testing:**
- [x] Unit test: `test_bitalino_reader_init()`
- [x] Unit test: `test_onRawFrame_puts_data_in_queue()`
- [x] Unit test: `test_stop_event_stops_acquisition()`
- [x] Mock test: `test_reconnection_attempts()`
---
 
### T1.4: Create `tests/test_bitalino_reader.py` 🟢
**Priority**: P1 (High)  
**Estimated Time**: 2 hours  
**Dependencies**: T1.3
 
**Description:**
Create comprehensive unit tests for bitalino_reader.py.
 
**Acceptance Criteria:**
- [x] Test RawFrame creation
- [x] Test BITalinoReader initialization
- [x] Test onRawFrame callback with mocked plux.SignalsDev
- [x] Test stop_event functionality
- [x] Test reconnection logic (mocked)
- [x] All tests pass (23/23)
- [x] Coverage > 80% for bitalino_reader.py
**Notes:**
- `make_reader()` helper uses `patch.object(BITalinoReader, '__new__', ...)` to bypass plux C extension in tests
- `FakeSignalsDev.__new__(*args, **kwargs)` handles patched instantiation correctly
**Files Created:**
- `tests/test_bitalino_reader.py`
**Testing:**
- [x] `pytest tests/test_bitalino_reader.py -v` → 23 passed in 0.20s
---
 
### T1.5: Manual Test - Connection Stability 🟢
**Priority**: P1 (High)  
**Estimated Time**: 30 minutes  
**Dependencies**: T1.3, T1.4
 
**Description:**
Manual validation of connection with actual BITalino hardware.
 
**Acceptance Criteria:**
- [x] Connection established successfully
- [x] Battery level displayed correctly (51%)
- [x] Data flows into queue at ~99 Hz without interruption
- [x] Ctrl+C stops gracefully with clean shutdown
- [x] No exceptions or crashes
- [x] All 5 active ports (A1, A2, A3, A4, A6) display live values per second
**Notes:**
- Queue size consistently 0 — frames consumed as fast as produced (healthy)
- Clean shutdown confirmed: "Acquisition loop completed normally" + "Device stopped and closed"
- `py src\bitalino_reader.py` also verified: battery 51%, live channel data correct
**Testing:**
- [x] Connected to `98:D3:71:FE:4F:90` — battery 51%
- [x] Acquisition rate: ~99 Hz sustained
- [x] Live channel values displayed per second
- [x] Graceful Ctrl+C shutdown confirmed
---

## Phase 1 - Étape 2: Visualizer

### T2.1: Create `src/visualizer.py` - PlotData dataclass 🔴
**Priority**: P1 (High)  
**Estimated Time**: 30 minutes  
**Dependencies**: T1.1

**Description:**
Create PlotData dataclass for storing rolling window data.

**Acceptance Criteria:**
- [ ] `@dataclass PlotData` with timestamps, values, max_size
- [ ] Type hints: `timestamps: Deque[float]`, `values: Deque[float]`, `max_size: int`
- [ ] Docstring

**Files to Create:**
- `src/visualizer.py`

**Testing:**
- [ ] Can instantiate PlotData
- [ ] Deque behavior correct

---

### T2.2: Create `src/visualizer.py` - SensorVisualizer class 🔴
**Priority**: P1 (High)  
**Estimated Time**: 4 hours  
**Dependencies**: T2.1

**Description:**
Implement SensorVisualizer class for real-time plotting of 5 sensors.

**Acceptance Criteria:**
- [ ] All attributes from SPECS.md section 2.3
- [ ] `__init__()` initializes empty plot_data for 5 sensors
- [ ] `setup_plots()` creates 5 subplots with matplotlib
- [ ] Each subplot has correct title from `config.PLOT_NAMES`
- [ ] `update_data()` adds to rolling window, removes old data
- [ ] `update_plots()` refreshes all lines
- [ ] `start()` uses matplotlib FuncAnimation
- [ ] `close()` closes figure
- [ ] `_create_subplot()` helper for subplot creation
- [ ] `_animation_callback()` for FuncAnimation
- [ ] Window size = `config.PLOT_WINDOW_DURATION` seconds
- [ ] Type hints on all methods
- [ ] Docstrings on all public methods

**Files to Modify:**
- `src/visualizer.py`

**Testing:**
- [ ] Unit test: `test_visualizer_init()`
- [ ] Unit test: `test_update_data_adds_to_window()`
- [ ] Unit test: `test_window_size_respected()`
- [ ] Unit test: `test_setup_plots_creates_subplots()`

---

### T2.3: Create `tests/test_visualizer.py` 🔴
**Priority**: P1 (High)  
**Estimated Time**: 1.5 hours  
**Dependencies**: T2.2

**Description:**
Unit tests for visualizer focusing on data management logic.

**Acceptance Criteria:**
- [ ] Test initialization
- [ ] Test data addition to rolling window
- [ ] Test window size constraint
- [ ] Test setup_plots creates correct number of subplots
- [ ] All tests pass
- [ ] Coverage > 70% (visualization logic hard to test)

**Files to Create:**
- `tests/test_visualizer.py`

**Testing:**
- [ ] `pytest tests/test_visualizer.py -v` passes

---

### T2.4: Integration Test - Visualizer with Mock Data 🔴
**Priority**: P1 (High)  
**Estimated Time**: 1 hour  
**Dependencies**: T2.2, T2.3

**Description:**
Create integration test script to display visualizer with synthetic data.

**Acceptance Criteria:**
- [ ] Script generates synthetic data for 5 sensors
- [ ] Data pumped into visualizer at 100 Hz
- [ ] Plots update smoothly
- [ ] No lag or freezing
- [ ] Can run for 60 seconds minimum

**Files to Create:**
- `tests/manual/test_visualizer_integration.py`

**Testing:**
- [ ] Visual inspection: 5 plots display correctly
- [ ] Visual inspection: data scrolls smoothly

---

### T2.5: Manual Test - Live Data Visualization 🔴
**Priority**: P1 (High)  
**Estimated Time**: 30 minutes  
**Dependencies**: T1.5, T2.4

**Description:**
Connect visualizer to actual BITalino and display live sensor data.

**Acceptance Criteria:**
- [ ] All 5 sensor plots display simultaneously
- [ ] EMG reacts to muscle contraction within 200ms
- [ ] FSR reacts to button press immediately
- [ ] No data loss during visualization
- [ ] Runs for 5 minutes without lag

**Testing:**
- [ ] Manual validation with physical actions
- [ ] Observer confirms reactivity

---

## Phase 1 - Étape 3: Calibration

### T3.1: Create `src/sensors/` directory and `__init__.py` 🔴
**Priority**: P0 (Critical)  
**Estimated Time**: 5 minutes  
**Dependencies**: None

**Description:**
Create sensors package directory.

**Acceptance Criteria:**
- [ ] Directory `src/sensors/` exists
- [ ] `src/sensors/__init__.py` created (can be empty)

**Files to Create:**
- `src/sensors/__init__.py`

---

### T3.2: Create `src/sensors/eda_processor.py` 🔴
**Priority**: P1 (High)  
**Estimated Time**: 1.5 hours  
**Dependencies**: T3.1, T1.1

**Description:**
Implement EDAProcessor class as per SPECS.md section 2.5.

**Acceptance Criteria:**
- [ ] `EDAProcessor` class with baseline_mean, baseline_std
- [ ] `_smoothing_window` deque with maxlen=10
- [ ] `process_raw()` applies moving average filter
- [ ] `compute_eda_index()` uses formula: (current - mean) / std
- [ ] `classify_level()` returns "normal", "moderate", "high", "overload"
- [ ] Type hints on all methods
- [ ] Docstrings on all methods

**Files to Create:**
- `src/sensors/eda_processor.py`

**Testing:**
- [ ] Unit test: `test_eda_processor_init()`
- [ ] Unit test: `test_process_raw_smoothing()`
- [ ] Unit test: `test_compute_eda_index()`
- [ ] Unit test: `test_classify_level()`

---

### T3.3: Create `src/sensors/emg_processor.py` 🔴
**Priority**: P1 (High)  
**Estimated Time**: 2 hours  
**Dependencies**: T3.1, T1.1

**Description:**
Implement EMGProcessor class as per SPECS.md section 2.6.

**Acceptance Criteria:**
- [ ] `EMGProcessor` class with rms_baseline
- [ ] `_window` deque with maxlen=50 (0.5s at 100Hz)
- [ ] `process_raw()` returns rectified EMG value
- [ ] `compute_rms()` calculates RMS over window
- [ ] `compute_tension_index()` = current_rms / rms_baseline
- [ ] `detect_contraction()` returns "rest", "light", "strong"
- [ ] Type hints on all methods
- [ ] Docstrings on all methods

**Files to Create:**
- `src/sensors/emg_processor.py`

**Testing:**
- [ ] Unit test: `test_emg_processor_init()`
- [ ] Unit test: `test_process_raw()`
- [ ] Unit test: `test_compute_rms()`
- [ ] Unit test: `test_compute_tension_index()`
- [ ] Unit test: `test_detect_contraction()`

---

### T3.4: Create `src/sensors/acc_processor.py` 🔴
**Priority**: P1 (High)  
**Estimated Time**: 1.5 hours  
**Dependencies**: T3.1, T1.1

**Description:**
Implement ACCProcessor class for single-axis accelerometer (SPECS.md section 2.7).

**Acceptance Criteria:**
- [ ] `ACCProcessor` class with baseline_mean, baseline_std
- [ ] `_smoothing_window` deque with maxlen=20
- [ ] `process_raw()` applies smoothing filter (single axis)
- [ ] `compute_acc_index()` = current / baseline_mean
- [ ] `detect_movement()` returns "rest", "agitation", "movement"
- [ ] Type hints on all methods
- [ ] Docstrings on all methods

**Files to Create:**
- `src/sensors/acc_processor.py`

**Testing:**
- [ ] Unit test: `test_acc_processor_init()`
- [ ] Unit test: `test_process_raw()`
- [ ] Unit test: `test_compute_acc_index()`
- [ ] Unit test: `test_detect_movement()`

---

### T3.5: Create `src/sensors/fsr_processor.py` 🔴
**Priority**: P1 (High)  
**Estimated Time**: 1 hour  
**Dependencies**: T3.1, T1.1

**Description:**
Implement FSRProcessor class as per SPECS.md section 2.8.

**Acceptance Criteria:**
- [ ] `FSRProcessor` class with baseline_value, threshold_press
- [ ] `_last_state` tracks button state
- [ ] `process_raw()` returns pressure value
- [ ] `is_pressed()` detects current press state
- [ ] `detect_press_event()` detects rising edge (new press)
- [ ] Type hints on all methods
- [ ] Docstrings on all methods

**Files to Create:**
- `src/sensors/fsr_processor.py`

**Testing:**
- [ ] Unit test: `test_fsr_processor_init()`
- [ ] Unit test: `test_process_raw()`
- [ ] Unit test: `test_is_pressed()`
- [ ] Unit test: `test_detect_press_event()`

---

### T3.6: Create `src/sensors/ppg_processor.py` 🔴
**Priority**: P1 (High)  
**Estimated Time**: 3 hours  
**Dependencies**: T3.1, T1.1

**Description:**
Implement PPGProcessor class as per SPECS.md section 2.9.

**Acceptance Criteria:**
- [ ] `PPGProcessor` class with sampling_rate
- [ ] `_signal_window` deque with maxlen = sampling_rate × 10
- [ ] `process_raw()` applies bandpass filter (0.5-4 Hz, Butterworth order 4)
- [ ] `detect_peaks()` uses adaptive threshold for R-peak detection
- [ ] `compute_ibi()` calculates Inter-Beat Intervals in ms
- [ ] `compute_bpm()` returns BPM or None
- [ ] Uses `scipy.signal` for filtering
- [ ] Type hints on all methods
- [ ] Docstrings on all methods

**Files to Create:**
- `src/sensors/ppg_processor.py`

**Testing:**
- [ ] Unit test: `test_ppg_processor_init()`
- [ ] Unit test: `test_process_raw_filtering()`
- [ ] Unit test: `test_detect_peaks()`
- [ ] Unit test: `test_compute_ibi()`
- [ ] Unit test: `test_compute_bpm()`

---

### T3.7: Create `src/sensors/hrv_analyzer.py` 🔴
**Priority**: P1 (High)  
**Estimated Time**: 2 hours  
**Dependencies**: T3.1, T1.1

**Description:**
Implement HRVAnalyzer class as per SPECS.md section 2.10.

**Acceptance Criteria:**
- [ ] `@dataclass HRVMetrics` with rmssd, sdnn, mean_ibi, mean_hr
- [ ] `HRVAnalyzer` class with window_size parameter
- [ ] `compute_rmssd()` implements RMSSD formula (SPECS section 5.6)
- [ ] `compute_sdnn()` calculates standard deviation of IBIs
- [ ] `compute_metrics()` returns HRVMetrics or None
- [ ] `compute_hrv_drop()` calculates percentage drop
- [ ] Requires minimum 5 IBIs for valid calculation
- [ ] Type hints on all methods
- [ ] Docstrings on all methods

**Files to Create:**
- `src/sensors/hrv_analyzer.py`

**Testing:**
- [ ] Unit test: `test_compute_rmssd()`
- [ ] Unit test: `test_compute_sdnn()`
- [ ] Unit test: `test_compute_metrics()`
- [ ] Unit test: `test_compute_hrv_drop()`
- [ ] Unit test: `test_insufficient_data()`

---

### T3.8: Create `tests/test_sensors/` directory 🔴
**Priority**: P1 (High)  
**Estimated Time**: 5 minutes  
**Dependencies**: T3.2-T3.7

**Description:**
Create test directory for sensor processors.

**Acceptance Criteria:**
- [ ] Directory `tests/test_sensors/` exists
- [ ] `tests/test_sensors/__init__.py` created

**Files to Create:**
- `tests/test_sensors/__init__.py`

---

### T3.9: Create all sensor processor tests 🔴
**Priority**: P1 (High)  
**Estimated Time**: 4 hours  
**Dependencies**: T3.2-T3.8

**Description:**
Create comprehensive unit tests for all sensor processors.

**Acceptance Criteria:**
- [ ] `tests/test_sensors/test_eda_processor.py` complete
- [ ] `tests/test_sensors/test_emg_processor.py` complete
- [ ] `tests/test_sensors/test_acc_processor.py` complete
- [ ] `tests/test_sensors/test_fsr_processor.py` complete
- [ ] `tests/test_sensors/test_ppg_processor.py` complete
- [ ] `tests/test_sensors/test_hrv_analyzer.py` complete
- [ ] All tests pass
- [ ] Coverage > 80% for each sensor processor

**Files to Create:**
- `tests/test_sensors/test_eda_processor.py`
- `tests/test_sensors/test_emg_processor.py`
- `tests/test_sensors/test_acc_processor.py`
- `tests/test_sensors/test_fsr_processor.py`
- `tests/test_sensors/test_ppg_processor.py`
- `tests/test_sensors/test_hrv_analyzer.py`

**Testing:**
- [ ] `pytest tests/test_sensors/ -v` passes

---

### T3.10: Create `src/calibration.py` - Baseline dataclasses 🔴
**Priority**: P1 (High)  
**Estimated Time**: 1 hour  
**Dependencies**: T1.1

**Description:**
Create all baseline dataclasses as per SPECS.md section 2.4.

**Acceptance Criteria:**
- [ ] `@dataclass SensorBaseline` with mean, std, min, max, samples_count
- [ ] `@dataclass EDABaseline` extends SensorBaseline
- [ ] `@dataclass EMGBaseline` extends SensorBaseline
- [ ] `@dataclass ACCBaseline` extends SensorBaseline
- [ ] `@dataclass FSRBaseline` extends SensorBaseline
- [ ] `@dataclass PPGBaseline` extends SensorBaseline
- [ ] `@dataclass BaselineData` with all sensor baselines
- [ ] All with proper type hints
- [ ] Docstrings on all dataclasses

**Files to Create:**
- `src/calibration.py`

**Testing:**
- [ ] Can instantiate all dataclasses
- [ ] Dataclasses serializable with `asdict()`

---

### T3.11: Create `src/calibration.py` - CalibrationManager class 🔴
**Priority**: P1 (High)  
**Estimated Time**: 4 hours  
**Dependencies**: T3.10, T3.7

**Description:**
Implement CalibrationManager class as per SPECS.md section 2.4.

**Acceptance Criteria:**
- [ ] `CalibrationManager` class with duration, sampling_rate
- [ ] `_raw_data` dict accumulates samples by sensor
- [ ] `add_sample()` adds sample to raw_data
- [ ] `is_complete()` checks if enough samples collected
- [ ] `compute_baseline()` calls all `_compute_*_baseline()` methods
- [ ] `_compute_eda_baseline()` calculates EDA thresholds (SPECS 5.8)
- [ ] `_compute_emg_baseline()` calculates RMS and thresholds (SPECS 5.8)
- [ ] `_compute_acc_baseline()` calculates ACC thresholds (SPECS 5.8)
- [ ] `_compute_fsr_baseline()` calculates FSR threshold (SPECS 5.8)
- [ ] `_compute_ppg_baseline()` uses HRVAnalyzer for baseline HRV
- [ ] `save_baseline()` saves to JSON with timestamp in filename
- [ ] `load_baseline()` loads from JSON
- [ ] Type hints on all methods
- [ ] Docstrings on all methods

**Files to Modify:**
- `src/calibration.py`

**Testing:**
- [ ] Unit test: `test_calibration_manager_init()`
- [ ] Unit test: `test_add_sample()`
- [ ] Unit test: `test_is_complete()`
- [ ] Unit test: `test_compute_eda_baseline()`
- [ ] Unit test: `test_compute_emg_baseline()`
- [ ] Unit test: `test_compute_all_baselines()`
- [ ] Unit test: `test_save_and_load_baseline()`

---

### T3.12: Create `tests/test_calibration.py` 🔴
**Priority**: P1 (High)  
**Estimated Time**: 3 hours  
**Dependencies**: T3.11

**Description:**
Comprehensive tests for calibration module.

**Acceptance Criteria:**
- [ ] Tests for all public methods
- [ ] Tests use synthetic data fixtures
- [ ] Tests verify threshold calculations correct
- [ ] Tests verify JSON save/load roundtrip
- [ ] All tests pass
- [ ] Coverage > 85% for calibration.py

**Files to Create:**
- `tests/test_calibration.py`

**Testing:**
- [ ] `pytest tests/test_calibration.py -v` passes

---

### T3.13: Create `tests/conftest.py` with shared fixtures 🔴
**Priority**: P1 (High)  
**Estimated Time**: 2 hours  
**Dependencies**: T3.11

**Description:**
Create shared pytest fixtures as per SPECS.md section 6.10.

**Acceptance Criteria:**
- [ ] `temp_dir` fixture provides temporary directory
- [ ] `synthetic_baseline_data` fixture returns complete BaselineData
- [ ] `mock_raw_frame` fixture returns realistic RawFrame
- [ ] `synthetic_eda_data` fixture (numpy array, 2000 samples)
- [ ] `synthetic_emg_data` fixture (numpy array, 2000 samples)
- [ ] `synthetic_acc_data` fixture (numpy array, 2000 samples)
- [ ] `synthetic_fsr_data` fixture (numpy array, 2000 samples)
- [ ] `synthetic_ppg_data` fixture (numpy array, 2000 samples)
- [ ] All fixtures properly seeded for reproducibility

**Files to Create:**
- `tests/conftest.py`

**Testing:**
- [ ] Fixtures usable in all test files
- [ ] Data realistic and valid

---

### T3.14: Manual Test - Calibration with Live Data 🔴
**Priority**: P1 (High)  
**Estimated Time**: 1 hour  
**Dependencies**: T3.11, T3.12

**Description:**
Run calibration with actual BITalino hardware.

**Acceptance Criteria:**
- [ ] 20-second calibration completes successfully
- [ ] Baseline JSON file generated in `data/`
- [ ] Values in JSON coherent with visual inspection of sensor plots
- [ ] EMG thresholds distinguish rest/light/strong contraction
- [ ] Reproducible across 3 calibration runs

**Testing:**
- [ ] Manual validation: sit still for 20 seconds
- [ ] Inspect JSON values
- [ ] Test EMG thresholds with contractions

---

## Phase 1 - Étape 4: Cognitive Load Analysis

### T4.1: Create `src/cognitive_load.py` - Dataclasses 🔴
**Priority**: P1 (High)  
**Estimated Time**: 30 minutes  
**Dependencies**: T1.1

**Description:**
Create CCISnapshot and TippingPoint dataclasses (SPECS section 2.11).

**Acceptance Criteria:**
- [ ] `@dataclass CCISnapshot` with timestamp, cci, eda_index, hrv_drop, acc_index, emg_tension
- [ ] `@dataclass TippingPoint` with timestamp, cci_value, duration_above_threshold
- [ ] Type hints on all fields
- [ ] Docstrings

**Files to Create:**
- `src/cognitive_load.py`

**Testing:**
- [ ] Can instantiate both dataclasses
- [ ] Dataclasses serializable

---

### T4.2: Create `src/cognitive_load.py` - CognitiveLoadAnalyzer class 🔴
**Priority**: P1 (High)  
**Estimated Time**: 3 hours  
**Dependencies**: T4.1

**Description:**
Implement CognitiveLoadAnalyzer class (SPECS section 2.11).

**Acceptance Criteria:**
- [ ] `CognitiveLoadAnalyzer` class with cci_weights, overload_threshold, overload_duration
- [ ] `_cci_history` deque with maxlen=3600
- [ ] `compute_cci()` implements formula from SPECS 5.1
- [ ] `_normalize_cci()` clamps to 0-10 range
- [ ] `update()` computes CCI, stores in history, returns CCISnapshot
- [ ] `detect_tipping_point()` implements duration-based detection (SPECS 5.9)
- [ ] `get_tipping_point()` returns detected tipping point or None
- [ ] `get_cci_history()` returns list of snapshots
- [ ] `get_current_cci()` returns most recent CCI
- [ ] Type hints on all methods
- [ ] Docstrings on all methods

**Files to Modify:**
- `src/cognitive_load.py`

**Testing:**
- [ ] Unit test: `test_compute_cci()`
- [ ] Unit test: `test_cci_normalization()`
- [ ] Unit test: `test_detect_tipping_point_duration()`
- [ ] Unit test: `test_no_tipping_point_if_below_threshold()`
- [ ] Unit test: `test_cci_history()`

---

### T4.3: Create `tests/test_cognitive_load.py` 🔴
**Priority**: P1 (High)  
**Estimated Time**: 2 hours  
**Dependencies**: T4.2

**Description:**
Comprehensive tests for cognitive_load module.

**Acceptance Criteria:**
- [ ] Test CCI formula correctness with known values
- [ ] Test normalization/clamping
- [ ] Test tipping point detection after sustained high CCI
- [ ] Test no false positives below threshold
- [ ] Test history tracking
- [ ] All tests pass
- [ ] Coverage > 85% for cognitive_load.py

**Files to Create:**
- `tests/test_cognitive_load.py`

**Testing:**
- [ ] `pytest tests/test_cognitive_load.py -v` passes

---

### T4.4: Manual Test - CCI Reactivity 🔴
**Priority**: P1 (High)  
**Estimated Time**: 30 minutes  
**Dependencies**: T4.2, T4.3

**Description:**
Verify CCI increases during mental load.

**Acceptance Criteria:**
- [ ] Create integration script combining calibration + processors + CCI
- [ ] CCI increases visibly during mental arithmetic task
- [ ] Tipping point detected after sustained stress (> 3 seconds)
- [ ] CCI drops when task ends

**Testing:**
- [ ] Manual validation: perform mental calculations
- [ ] Observer records CCI values
- [ ] Verify tipping point detection timing

---

## Phase 1 - Étape 5: Reporting

### T5.1: Create `src/report/` directory structure 🔴
**Priority**: P1 (High)  
**Estimated Time**: 5 minutes  
**Dependencies**: None

**Description:**
Create report package directory structure.

**Acceptance Criteria:**
- [ ] Directory `src/report/` exists
- [ ] `src/report/__init__.py` created
- [ ] Directory `src/report/templates/` exists

**Files to Create:**
- `src/report/__init__.py`
- `src/report/templates/` (directory)

---

### T5.2: Create `src/report/reporter.py` - Dataclasses 🔴
**Priority**: P1 (High)  
**Estimated Time**: 30 minutes  
**Dependencies**: T5.1, T1.1

**Description:**
Create SessionEvent and SessionMetadata dataclasses (SPECS section 2.12).

**Acceptance Criteria:**
- [ ] `@dataclass SessionEvent` with timestamp, event_type, data
- [ ] `@dataclass SessionMetadata` with all session info fields
- [ ] Type hints on all fields
- [ ] Docstrings

**Files to Create:**
- `src/report/reporter.py`

**Testing:**
- [ ] Can instantiate both dataclasses

---

### T5.3: Create `src/report/reporter.py` - SessionReporter class 🔴
**Priority**: P1 (High)  
**Estimated Time**: 6 hours  
**Dependencies**: T5.2, T4.2

**Description:**
Implement SessionReporter class (SPECS section 2.12).

**Acceptance Criteria:**
- [ ] `SessionReporter` class with session_id, output_dir
- [ ] `_metadata`, `_baseline_data`, `_sensor_data`, `_cci_data`, `_events` attributes
- [ ] `set_metadata()` stores metadata
- [ ] `set_baseline()` stores baseline
- [ ] `log_sensor_data()` accumulates sensor