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

### T2.1: Create `src/visualizer.py` - PlotData dataclass 🟢
**Priority**: P1 (High)  
**Estimated Time**: 30 minutes  
**Dependencies**: T1.1

**Description:**
Create PlotData dataclass for storing rolling window data.

**Acceptance Criteria:**
- [x] `@dataclass PlotData` with timestamps, values, max_size
- [x] Type hints: `timestamps: Deque[float]`, `values: Deque[float]`, `max_size: int`
- [x] Docstring

**Files to Create:**
- `src/visualizer.py`

**Testing:**
- [x] Can instantiate PlotData
- [x] Deque behavior correct

---

### T2.2: Create `src/visualizer.py` - SensorVisualizer class 🟢
**Priority**: P1 (High)  
**Estimated Time**: 4 hours  
**Dependencies**: T2.1

**Description:**
Implement SensorVisualizer class for real-time plotting of 5 sensors.

**Acceptance Criteria:**
- [x] All attributes from SPECS.md section 2.3
- [x] `__init__()` initializes empty plot_data for 5 sensors
- [x] `setup_plots()` creates 5 subplots with matplotlib
- [x] Each subplot has correct title from `config.PLOT_NAMES`
- [x] `update_data()` adds to rolling window, removes old data
- [x] `update_plots()` refreshes all lines
- [x] `start()` uses matplotlib FuncAnimation
- [x] `close()` closes figure
- [x] `_create_subplot()` helper for subplot creation
- [x] `_animation_callback()` for FuncAnimation
- [x] Window size = `config.PLOT_WINDOW_DURATION` seconds
- [x] Type hints on all methods
- [x] Docstrings on all public methods

**Files to Modify:**
- `src/visualizer.py`

**Testing:**
- [x] Unit test: `test_visualizer_init()`
- [x] Unit test: `test_update_data_adds_to_window()`
- [x] Unit test: `test_window_size_respected()`
- [x] Unit test: `test_setup_plots_creates_subplots()`

---

### T2.3: Create `tests/test_visualizer.py` 🟢
**Priority**: P1 (High)  
**Estimated Time**: 1.5 hours  
**Dependencies**: T2.2

**Description:**
Unit tests for visualizer focusing on data management logic.

**Acceptance Criteria:**
- [x] Test initialization
- [x] Test data addition to rolling window
- [x] Test window size constraint
- [x] Test setup_plots creates correct number of subplots
- [x] All tests pass
- [x] Coverage > 70% (visualization logic hard to test)

**Files to Create:**
- `tests/test_visualizer.py`

**Testing:**
- [x] `pytest tests/test_visualizer.py -v` passes

---

### T2.4: Integration Test - Visualizer with Mock Data 🟢
**Priority**: P1 (High)  
**Estimated Time**: 1 hour  
**Dependencies**: T2.2, T2.3

**Description:**
Create integration test script to display visualizer with synthetic data.

**Acceptance Criteria:**
- [x] Script generates synthetic data for 5 sensors
- [x] Data pumped into visualizer at 100 Hz
- [x] Plots update smoothly
- [x] No lag or freezing
- [x] Can run for 60 seconds minimum

**Files to Create:**
- `tests/manual/test_visualizer_integration.py`

**Testing:**
- [x] Visual inspection: 5 plots display correctly
- [x] Visual inspection: data scrolls smoothly

---

### T2.5: Manual Test - Live Data Visualization 🟢
**Priority**: P1 (High)  
**Estimated Time**: 30 minutes  
**Dependencies**: T1.5, T2.4

**Description:**
Connect visualizer to actual BITalino and display live sensor data.

**Acceptance Criteria:**
- [x] All 5 sensor plots display simultaneously
- [x] EMG reacts to muscle contraction within 200ms
- [x] FSR reacts to button press immediately
- [x] No data loss during visualization
- [x] Runs for 5 minutes without lag

**Testing:**
- [x] Manual validation with physical actions
- [x] Observer confirms reactivity

---

## Phase 1 - Étape 3: Calibration

### T3.1: Create `src/sensors/` directory and `__init__.py` 🟢
**Priority**: P0 (Critical)  
**Estimated Time**: 5 minutes  
**Dependencies**: None

**Description:**
Create sensors package directory.

**Acceptance Criteria:**
- [x] Directory `src/sensors/` exists
- [x] `src/sensors/__init__.py` created (can be empty)

**Files to Create:**
- `src/sensors/__init__.py`

---

### T3.2: Create `src/sensors/eda_processor.py` 🟢
**Priority**: P1 (High)  
**Estimated Time**: 1.5 hours  
**Dependencies**: T3.1, T1.1

**Description:**
Implement EDAProcessor class as per SPECS.md section 2.5.

**Acceptance Criteria:**
- [x] `EDAProcessor` class with baseline_mean, baseline_std
- [x] `_smoothing_window` deque with maxlen=10
- [x] `process_raw()` applies moving average filter
- [x] `compute_eda_index()` uses formula: (current - mean) / std
- [x] `classify_level()` returns "normal", "moderate", "high", "overload"
- [x] Type hints on all methods
- [x] Docstrings on all methods

**Files to Create:**
- `src/sensors/eda_processor.py`

**Testing:**
- [x] Unit test: `test_eda_processor_init()`
- [x] Unit test: `test_process_raw_smoothing()`
- [x] Unit test: `test_compute_eda_index()`
- [x] Unit test: `test_classify_level()`

---

### T3.3: Create `src/sensors/emg_processor.py` 🟢
**Priority**: P1 (High)  
**Estimated Time**: 2 hours  
**Dependencies**: T3.1, T1.1

**Description:**
Implement EMGProcessor class as per SPECS.md section 2.6.

**Acceptance Criteria:**
- [x] `EMGProcessor` class with rms_baseline
- [x] `_window` deque with maxlen=50 (0.5s at 100Hz)
- [x] `process_raw()` returns rectified EMG value
- [x] `compute_rms()` calculates RMS over window
- [x] `compute_tension_index()` = current_rms / rms_baseline
- [x] `detect_contraction()` returns "rest", "light", "strong"
- [x] Type hints on all methods
- [x] Docstrings on all methods

**Files to Create:**
- `src/sensors/emg_processor.py`

**Testing:**
- [x] Unit test: `test_emg_processor_init()`
- [x] Unit test: `test_process_raw()`
- [x] Unit test: `test_compute_rms()`
- [x] Unit test: `test_compute_tension_index()`
- [x] Unit test: `test_detect_contraction()`

---

### T3.4: Create `src/sensors/acc_processor.py` 🟢
**Priority**: P1 (High)  
**Estimated Time**: 1.5 hours  
**Dependencies**: T3.1, T1.1

**Description:**
Implement ACCProcessor class for single-axis accelerometer (SPECS.md section 2.7).

**Acceptance Criteria:**
- [x] `ACCProcessor` class with baseline_mean, baseline_std
- [x] `_smoothing_window` deque with maxlen=20
- [x] `process_raw()` applies smoothing filter (single axis)
- [x] `compute_acc_index()` = current / baseline_mean
- [x] `detect_movement()` returns "rest", "agitation", "movement"
- [x] Type hints on all methods
- [x] Docstrings on all methods

**Files to Create:**
- `src/sensors/acc_processor.py`

**Testing:**
- [x] Unit test: `test_acc_processor_init()`
- [x] Unit test: `test_process_raw()`
- [x] Unit test: `test_compute_acc_index()`
- [x] Unit test: `test_detect_movement()`

---

### T3.5: Create `src/sensors/fsr_processor.py` 🟢
**Priority**: P1 (High)  
**Estimated Time**: 1 hour  
**Dependencies**: T3.1, T1.1

**Description:**
Implement FSRProcessor class as per SPECS.md section 2.8.

**Acceptance Criteria:**
- [x] `FSRProcessor` class with baseline_value, threshold_press
- [x] `_last_state` tracks button state
- [x] `process_raw()` returns pressure value
- [x] `is_pressed()` detects current press state
- [x] `detect_press_event()` detects rising edge (new press)
- [x] Type hints on all methods
- [x] Docstrings on all methods

**Files to Create:**
- `src/sensors/fsr_processor.py`

**Testing:**
- [x] Unit test: `test_fsr_processor_init()`
- [x] Unit test: `test_process_raw()`
- [x] Unit test: `test_is_pressed()`
- [x] Unit test: `test_detect_press_event()`

---

### T3.6: Create `src/sensors/ppg_processor.py` 🟢
**Priority**: P1 (High)  
**Estimated Time**: 3 hours  
**Dependencies**: T3.1, T1.1

**Description:**
Implement PPGProcessor class as per SPECS.md section 2.9.

**Acceptance Criteria:**
- [x] `PPGProcessor` class with sampling_rate
- [x] `_signal_window` deque with maxlen = sampling_rate × 10
- [x] `process_raw()` applies bandpass filter (0.5-4 Hz, Butterworth order 4)
- [x] `detect_peaks()` uses adaptive threshold for R-peak detection
- [x] `compute_ibi()` calculates Inter-Beat Intervals in ms
- [x] `compute_bpm()` returns BPM or None
- [x] Uses `scipy.signal` for filtering
- [x] Type hints on all methods
- [x] Docstrings on all methods

**Files to Create:**
- `src/sensors/ppg_processor.py`

**Testing:**
- [x] Unit test: `test_ppg_processor_init()`
- [x] Unit test: `test_process_raw_filtering()`
- [x] Unit test: `test_detect_peaks()`
- [x] Unit test: `test_compute_ibi()`
- [x] Unit test: `test_compute_bpm()`

---

### T3.7: Create `src/sensors/hrv_analyzer.py` 🟢
**Priority**: P1 (High)  
**Estimated Time**: 2 hours  
**Dependencies**: T3.1, T1.1

**Description:**
Implement HRVAnalyzer class as per SPECS.md section 2.10.

**Acceptance Criteria:**
- [x] `@dataclass HRVMetrics` with rmssd, sdnn, mean_ibi, mean_hr
- [x] `HRVAnalyzer` class with window_size parameter
- [x] `compute_rmssd()` implements RMSSD formula (SPECS section 5.6)
- [x] `compute_sdnn()` calculates standard deviation of IBIs
- [x] `compute_metrics()` returns HRVMetrics or None
- [x] `compute_hrv_drop()` calculates percentage drop
- [x] Requires minimum 5 IBIs for valid calculation
- [x] Type hints on all methods
- [x] Docstrings on all methods

**Files to Create:**
- `src/sensors/hrv_analyzer.py`

**Testing:**
- [x] Unit test: `test_compute_rmssd()`
- [x] Unit test: `test_compute_sdnn()`
- [x] Unit test: `test_compute_metrics()`
- [x] Unit test: `test_compute_hrv_drop()`
- [x] Unit test: `test_insufficient_data()`

---

### T3.10: Create `src/calibration.py` - Baseline dataclasses 🟢
**Priority**: P1 (High)  
**Estimated Time**: 1 hour  
**Dependencies**: T1.1

**Description:**
Create all baseline dataclasses as per SPECS.md section 2.4.

**Acceptance Criteria:**
- [x] `@dataclass SensorBaseline` with mean, std, min, max, samples_count
- [x] `@dataclass EDABaseline` extends SensorBaseline
- [x] `@dataclass EMGBaseline` extends SensorBaseline
- [x] `@dataclass ACCBaseline` extends SensorBaseline
- [x] `@dataclass FSRBaseline` extends SensorBaseline
- [x] `@dataclass PPGBaseline` extends SensorBaseline
- [x] `@dataclass BaselineData` with all sensor baselines
- [x] All with proper type hints
- [x] Docstrings on all dataclasses

**Files to Create:**
- `src/calibration.py`

**Testing:**
- [x] Can instantiate all dataclasses
- [x] Dataclasses serializable with `asdict()`

---

### T3.11: Create `src/calibration.py` - CalibrationManager class 🟢
**Priority**: P1 (High)  
**Estimated Time**: 4 hours  
**Dependencies**: T3.10, T3.7

**Description:**
Implement CalibrationManager class as per SPECS.md section 2.4.

**Acceptance Criteria:**
- [x] `CalibrationManager` class with duration, sampling_rate
- [x] `_raw_data` dict accumulates samples by sensor
- [x] `add_sample()` adds sample to raw_data
- [x] `is_complete()` checks if enough samples collected
- [x] `compute_baseline()` calls all `_compute_*_baseline()` methods
- [x] `_compute_eda_baseline()` calculates EDA thresholds (SPECS 5.8)
- [x] `_compute_emg_baseline()` calculates RMS and thresholds (SPECS 5.8)
- [x] `_compute_acc_baseline()` calculates ACC thresholds (SPECS 5.8)
- [x] `_compute_fsr_baseline()` calculates FSR threshold (SPECS 5.8)
- [x] `_compute_ppg_baseline()` uses HRVAnalyzer for baseline HRV
- [x] `save_baseline()` saves to JSON with timestamp in filename
- [x] `load_baseline()` loads from JSON
- [x] Type hints on all methods
- [x] Docstrings on all methods

**Files to Modify:**
- `src/calibration.py`

**Testing:**
- [x] Unit test: `test_calibration_manager_init()`
- [x] Unit test: `test_add_sample()`
- [x] Unit test: `test_is_complete()`
- [x] Unit test: `test_compute_eda_baseline()`
- [x] Unit test: `test_compute_emg_baseline()`
- [x] Unit test: `test_compute_all_baselines()`
- [x] Unit test: `test_save_and_load_baseline()`

---

### T3.12: Create `tests/test_calibration.py` 🟢
**Priority**: P1 (High)  
**Estimated Time**: 3 hours  
**Dependencies**: T3.11

**Description:**
Comprehensive tests for calibration module.

**Acceptance Criteria:**
- [x] Tests for all public methods
- [x] Tests use synthetic data fixtures
- [x] Tests verify threshold calculations correct
- [x] Tests verify JSON save/load roundtrip
- [x] All tests pass
- [x] Coverage > 85% for calibration.py

**Files to Create:**
- `tests/test_calibration.py`

**Testing:**
- [x] `pytest tests/test_calibration.py -v` passes

---

### T3.13: Create `tests/conftest.py` with shared fixtures 🟢
**Priority**: P1 (High)  
**Estimated Time**: 2 hours  
**Dependencies**: T3.11

**Description:**
Create shared pytest fixtures as per SPECS.md section 6.10.

**Acceptance Criteria:**
- [x] `temp_dir` fixture provides temporary directory
- [x] `synthetic_baseline_data` fixture returns complete BaselineData
- [x] `mock_raw_frame` fixture returns realistic RawFrame
- [x] `synthetic_eda_data` fixture (numpy array, 2000 samples)
- [x] `synthetic_emg_data` fixture (numpy array, 2000 samples)
- [x] `synthetic_acc_data` fixture (numpy array, 2000 samples)
- [x] `synthetic_fsr_data` fixture (numpy array, 2000 samples)
- [x] `synthetic_ppg_data` fixture (numpy array, 2000 samples)
- [x] All fixtures properly seeded for reproducibility

**Files to Create:**
- `tests/conftest.py`

**Testing:**
- [x] Fixtures usable in all test files
- [x] Data realistic and valid

---

### T3.14: Manual Test - Calibration with Live Data 🟢
**Priority**: P1 (High)  
**Estimated Time**: 1 hour  
**Dependencies**: T3.11, T3.12

**Description:**
Run calibration with actual BITalino hardware.

**Acceptance Criteria:**
- [x] 20-second calibration completes successfully
- [x] Baseline JSON file generated in `data/`
- [x] Values in JSON coherent with visual inspection of sensor plots
- [x] EMG thresholds distinguish rest/light/strong contraction
- [x] Reproducible across 3 calibration runs

**Testing:**
- [x] Manual validation: sit still for 20 seconds
- [x] Inspect JSON values
- [x] Test EMG thresholds with contractions

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