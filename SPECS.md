# SPECS.md - IQ Overload Phase 1

## 1. Architecture Globale

### 1.1 Diagramme des modules

```
┌─────────────────────────────────────────────────────────────────┐
│                           app.py                                │
│                  (Point d'entrée, orchestration)                │
└─────────────────────────────────────────────────────────────────┘
           │
           ├──────────────┬──────────────┬──────────────┬──────────
           │              │              │              │
           ▼              ▼              ▼              ▼
    ┌──────────┐   ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ config.py│   │bitalino_ │  │visualizer│  │calibration│
    │          │   │reader.py │  │   .py    │  │   .py    │
    └──────────┘   └──────────┘  └──────────┘  └──────────┘
                         │              │              │
                         │              │              │
                         ▼              │              ▼
                   ┌──────────┐        │        ┌──────────────┐
                   │  Queue   │◄───────┴────────│  sensors/    │
                   │(thread-  │                 │  *_processor │
                   │  safe)   │                 │      .py     │
                   └──────────┘                 └──────────────┘
                         │                              │
                         │                              │
                         ▼                              ▼
                   ┌──────────────┐            ┌──────────────┐
                   │cognitive_load│            │ hrv_analyzer │
                   │     .py      │◄───────────│     .py      │
                   └──────────────┘            └──────────────┘
                         │
                         │
                         ▼
                   ┌──────────────┐
                   │  reporter.py │
                   └──────────────┘
                         │
                         ▼
                   ┌──────────────┐
                   │ report.html  │
                   └──────────────┘
```

### 1.2 Flux de données

**Thread 1: Acquisition BITalino**
```
plux.SignalsDev.onRawFrame()
    → RawFrame(nSeq, data[6])
    → sensors/*_processor.process()
    → ProcessedFrame(timestamp, sensor_values)
    → Queue.put(ProcessedFrame)
```

**Thread 2: Main/Visualizer**
```
Queue.get(timeout=0.1)
    → ProcessedFrame
    → visualizer.update_plots(frame)
    → cognitive_load.update_cci(frame)
    → (optional) reporter.log_frame(frame)
```

**Thread 3: Calibration (temporaire, 20s)**
```
Queue.get()
    → accumulate frames (20s)
    → compute baseline statistics
    → save baseline_YYYYMMDD_HHMMSS.json
    → terminate thread
```

### 1.3 Stratégie de threading

| Thread | Responsabilité | Création | Terminaison |
|--------|---------------|----------|-------------|
| **Main Thread** | UI, orchestration, visualizer | au lancement | Ctrl+C ou fermeture fenêtre |
| **BITalino Thread** | acquisition capteurs (100 Hz) | app.start() | app.stop() ou reconnection failure |
| **Calibration Thread** | calcul baseline (20s) | app.calibrate() | après 20 secondes |

**Communication inter-threads:**
- `queue.Queue[ProcessedFrame]` (thread-safe) : BITalino → Main
- `threading.Event` pour arrêt propre des threads
- Pas de locks partagés (architecture producteur-consommateur pure)

---

## 2. Spec détaillée des modules

### 2.1 `src/config.py`

**Responsabilité:** Centraliser toutes les constantes de configuration.

```python
from typing import List

# BITalino Configuration
BITALINO_MAC_ADDRESS: str = "98:D3:71:FE:4F:90"
SAMPLING_RATE: int = 100  # Hz
ACTIVE_PORTS: List[int] = [1, 2, 3, 4, 6]  # EMG, EDA, ACC, FSR, PPG
RESOLUTION: int = 16  # bits
MAX_RECONNECTION_ATTEMPTS: int = 3
RECONNECTION_DELAY: float = 2.0  # seconds

# Port mapping
PORT_MAPPING: dict = {
    1: "EMG",
    2: "EDA",
    3: "ACC",
    4: "FSR",
    6: "PPG"
}

# Calibration
CALIBRATION_DURATION: int = 20  # seconds
CALIBRATION_SAMPLES: int = SAMPLING_RATE * CALIBRATION_DURATION

# Visualization
PLOT_WINDOW_DURATION: int = 10  # seconds
PLOT_UPDATE_INTERVAL: int = 1000  # milliseconds
PLOT_NAMES: dict = {
    "EMG": "EMG : Contraction musculaire",
    "EDA": "EDA : Activité électrodermale",
    "ACC": "ACC : Micro-mouvements",
    "FSR": "FSR : Pression appliquée",
    "PPG": "PPG : Rythme cardiaque optique"
}

# Cognitive Load Index weights
CCI_WEIGHTS: dict = {
    "eda": 0.35,
    "hrv": 0.35,
    "acc": 0.15,
    "emg": 0.15
}

# Thresholds (will be computed during calibration, these are fallbacks)
EDA_THRESHOLD_MODERATE: float = 2.0  # in std deviations
EDA_THRESHOLD_HIGH: float = 3.0
EMG_THRESHOLD_LIGHT: float = 3.0  # multiplier of baseline noise
EMG_THRESHOLD_STRONG: float = 8.0
EMG_THRESHOLD_TARGET: float = 5.0
ACC_THRESHOLD_AGITATION: float = 2.0  # in std deviations
ACC_THRESHOLD_MOVEMENT: float = 4.0
FSR_THRESHOLD_PRESS: int = 20  # units above baseline

# CCI Overload detection
CCI_OVERLOAD_THRESHOLD: float = 7.0
CCI_OVERLOAD_DURATION: float = 3.0  # seconds
CCI_BASELINE_MULTIPLIER: float = 2.0  # for round-based detection

# HRV
HRV_WINDOW_SIZE: int = 60  # seconds
HRV_DROP_SIGNIFICANT: float = 20.0  # percent
HRV_DROP_OVERLOAD: float = 40.0  # percent

# Data paths
DATA_DIR: str = "data"
REPORTS_DIR: str = "reports"
BASELINE_PREFIX: str = "baseline_"
SESSION_PREFIX: str = "session_"
REPORT_PREFIX: str = "report_"
```

**Pas de classes, que des constantes.**

---

### 2.2 `src/bitalino_reader.py` (modifié)

**Responsabilité:** Connexion continue au BITalino, acquisition des données brutes à 100 Hz, gestion de la reconnexion.

**Modifications par rapport à l'existant:**
- Remplacer `loop()` par une boucle infinie contrôlée par `threading.Event`
- Ajouter une queue pour transmettre les données
- Gérer la reconnexion automatique

```python
import plux
import threading
import queue
from typing import List, Optional
from dataclasses import dataclass
import time

@dataclass
class RawFrame:
    """Raw data frame from BITalino."""
    timestamp: float  # Unix timestamp in seconds
    sequence: int  # Frame sequence number
    channels: List[int]  # Raw ADC values, indexed by port number
```

**Classe: `BITalinoReader`**

**Hérite de:** `plux.SignalsDev`

**Attributs:**
- `address: str` - MAC address du BITalino
- `sampling_rate: int` - Fréquence d'échantillonnage (Hz)
- `active_ports: List[int]` - Ports actifs
- `resolution: int` - Résolution ADC
- `data_queue: queue.Queue[RawFrame]` - Queue thread-safe pour les données
- `stop_event: threading.Event` - Signal d'arrêt
- `is_connected: bool` - État de connexion
- `reconnection_attempts: int` - Compteur de tentatives de reconnexion
- `_start_time: float` - Timestamp de début d'acquisition

**Méthodes publiques:**

```python
def __init__(
    self, 
    address: str, 
    sampling_rate: int, 
    active_ports: List[int],
    resolution: int,
    data_queue: queue.Queue[RawFrame]
) -> None:
    """Initialize BITalino reader with configuration."""
```

```python
def connect(self) -> bool:
    """
    Establish connection to BITalino device.
    Returns True if successful, False otherwise.
    """
```

```python
def start_acquisition(self) -> None:
    """
    Start continuous data acquisition in a separate thread.
    Calls plux.SignalsDev.start() and enters acquisition loop.
    """
```

```python
def stop_acquisition(self) -> None:
    """
    Stop acquisition gracefully and close connection.
    Sets stop_event and waits for thread to finish.
    """
```

```python
def get_battery_level(self) -> int:
    """
    Get current battery level percentage.
    Returns battery level (0-100).
    """
```

```python
def onRawFrame(self, nSeq: int, data: List[int]) -> bool:
    """
    Callback invoked by plux at each frame (100 Hz).
    Puts RawFrame into data_queue.
    Returns True to stop acquisition, False to continue.
    """
```

**Méthodes privées:**

```python
def _acquisition_loop(self) -> None:
    """
    Main acquisition loop running in separate thread.
    Calls plux.loop() until stop_event is set.
    """
```

```python
def _reconnect(self) -> bool:
    """
    Attempt to reconnect to BITalino.
    Returns True if successful, False after max attempts.
    """
```

**Dépendances:**
- `plux` (binaire existant)
- `config.py` (constantes)
- `queue.Queue` (stdlib)
- `threading` (stdlib)

---

### 2.3 `src/visualizer.py`

**Responsabilité:** Affichage dynamique des 6 courbes de capteurs en temps réel.

```python
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque
from typing import Dict, Deque
from dataclasses import dataclass
import numpy as np

@dataclass
class PlotData:
    """Data for a single sensor plot."""
    timestamps: Deque[float]  # Rolling window of timestamps
    values: Deque[float]  # Rolling window of sensor values
    max_size: int  # Maximum window size
```

**Classe: `SensorVisualizer`**

**Attributs:**
- `window_duration: int` - Durée de la fenêtre glissante (secondes)
- `sampling_rate: int` - Fréquence d'échantillonnage
- `plot_data: Dict[str, PlotData]` - Données par capteur (clés: "EMG", "EDA", etc.)
- `fig: plt.Figure` - Figure matplotlib
- `axes: Dict[str, plt.Axes]` - Axes par capteur
- `lines: Dict[str, plt.Line2D]` - Lignes de courbes par capteur
- `_update_interval: int` - Intervalle de rafraîchissement (ms)

**Méthodes publiques:**

```python
def __init__(self, window_duration: int, sampling_rate: int) -> None:
    """Initialize visualizer with empty plot data."""
```

```python
def setup_plots(self) -> None:
    """
    Create matplotlib figure with 5 subplots (1 per sensor).
    Configure axes labels, titles, and layout.
    """
```

```python
def update_data(self, sensor: str, timestamp: float, value: float) -> None:
    """
    Add new data point to the rolling window for a given sensor.
    Automatically removes old data outside window_duration.
    """
```

```python
def update_plots(self) -> None:
    """
    Refresh all plots with current data in plot_data.
    Called periodically by matplotlib animation or main loop.
    """
```

```python
def start(self) -> None:
    """
    Start the visualization loop (blocks until window closed).
    Uses matplotlib animation with interval=_update_interval.
    """
```

```python
def close(self) -> None:
    """Close the matplotlib figure."""
```

**Méthodes privées:**

```python
def _create_subplot(
    self, 
    position: int, 
    sensor: str, 
    ylabel: str
) -> plt.Axes:
    """
    Create a single subplot with proper configuration.
    Returns the axes object.
    """
```

```python
def _animation_callback(self, frame: int) -> List[plt.Line2D]:
    """
    Callback for matplotlib FuncAnimation.
    Updates all lines and returns list of artists.
    """
```

**Dépendances:**
- `matplotlib`
- `config.py` (PLOT_NAMES, PLOT_WINDOW_DURATION)
- `numpy`

---

### 2.4 `src/calibration.py`

**Responsabilité:** Acquérir les données de référence au repos pendant 20 secondes et calculer les statistiques baseline.

```python
from dataclasses import dataclass, asdict
from typing import List, Dict
import numpy as np
import json
from datetime import datetime
from pathlib import Path

@dataclass
class SensorBaseline:
    """Baseline statistics for a single sensor."""
    mean: float
    std: float
    min: float
    max: float
    samples_count: int

@dataclass
class EDABaseline(SensorBaseline):
    """EDA-specific baseline with thresholds."""
    threshold_moderate: float  # mean + 2*std
    threshold_high: float  # mean + 3*std

@dataclass
class EMGBaseline(SensorBaseline):
    """EMG-specific baseline with RMS and thresholds."""
    rms_baseline: float
    threshold_light: float  # rms * 3
    threshold_strong: float  # rms * 8
    threshold_target: float  # rms * 5

@dataclass
class ACCBaseline(SensorBaseline):
    """ACC-specific baseline with magnitude statistics."""
    threshold_agitation: float  # mean + 2*std
    threshold_movement: float  # mean + 4*std

@dataclass
class FSRBaseline(SensorBaseline):
    """FSR-specific baseline with press threshold."""
    threshold_press: float  # baseline + fixed offset

@dataclass
class PPGBaseline(SensorBaseline):
    """PPG-specific baseline with HRV."""
    hrv_baseline: float  # RMSSD in ms
    bpm_baseline: float  # Beats per minute

@dataclass
class BaselineData:
    """Complete baseline data for all sensors."""
    timestamp: str  # ISO format
    duration: int  # seconds
    sampling_rate: int
    eda: EDABaseline
    emg: EMGBaseline
    acc: ACCBaseline
    fsr: FSRBaseline
    ppg: PPGBaseline
```

**Classe: `CalibrationManager`**

**Attributs:**
- `duration: int` - Durée de calibration (secondes)
- `sampling_rate: int` - Fréquence d'échantillonnage
- `samples_required: int` - Nombre d'échantillons requis
- `_raw_data: Dict[str, List[float]]` - Données brutes accumulées par capteur
- `_samples_collected: int` - Compteur d'échantillons
- `baseline: Optional[BaselineData]` - Résultat de la calibration

**Méthodes publiques:**

```python
def __init__(self, duration: int, sampling_rate: int) -> None:
    """Initialize calibration manager."""
```

```python
def add_sample(self, sensor: str, value: float) -> None:
    """
    Add a single sample for a given sensor during calibration phase.
    """
```

```python
def is_complete(self) -> bool:
    """
    Check if calibration has collected enough samples.
    """
```

```python
def compute_baseline(self) -> BaselineData:
    """
    Compute baseline statistics from collected samples.
    Must be called after is_complete() returns True.
    Returns BaselineData object.
    """
```

```python
def save_baseline(self, output_dir: str) -> str:
    """
    Save baseline to JSON file with timestamp.
    Returns filepath of saved file.
    """
```

```python
def load_baseline(self, filepath: str) -> BaselineData:
    """
    Load baseline from JSON file.
    Returns BaselineData object.
    """
```

**Méthodes privées:**

```python
def _compute_eda_baseline(self, values: np.ndarray) -> EDABaseline:
    """Compute EDA baseline with thresholds."""
```

```python
def _compute_emg_baseline(self, values: np.ndarray) -> EMGBaseline:
    """Compute EMG baseline with RMS and thresholds."""
```

```python
def _compute_acc_baseline(self, values: np.ndarray) -> ACCBaseline:
    """Compute ACC baseline with magnitude thresholds."""
```

```python
def _compute_fsr_baseline(self, values: np.ndarray) -> FSRBaseline:
    """Compute FSR baseline with press threshold."""
```

```python
def _compute_ppg_baseline(self, values: np.ndarray) -> PPGBaseline:
    """Compute PPG baseline with HRV and BPM."""
```

**Dépendances:**
- `numpy`
- `config.py` (CALIBRATION_DURATION, thresholds multipliers)
- `sensors/hrv_analyzer.py` (pour calcul HRV initial)

---

### 2.5 `src/sensors/eda_processor.py`

**Responsabilité:** Traiter le signal EDA brut et calculer les indices de stress.

```python
import numpy as np
from typing import Optional
from collections import deque

class EDAProcessor:
    """Process EDA (Electrodermal Activity) signal."""
    
    def __init__(self, baseline_mean: float, baseline_std: float) -> None:
        """Initialize with baseline statistics."""
        self.baseline_mean = baseline_mean
        self.baseline_std = baseline_std
        self._smoothing_window = deque(maxlen=10)  # 0.1s smoothing at 100Hz
    
    def process_raw(self, raw_value: int) -> float:
        """
        Convert raw ADC value to smoothed EDA value.
        Applies moving average filter.
        Returns smoothed EDA value in arbitrary units.
        """
    
    def compute_eda_index(self, eda_value: float) -> float:
        """
        Compute EDA index: (current - baseline_mean) / baseline_std.
        Returns normalized stress index.
        """
    
    def classify_level(self, eda_index: float) -> str:
        """
        Classify EDA level based on index.
        Returns: "normal", "moderate", "high", "overload".
        """
```

**Dépendances:**
- `numpy`
- `config.py` (EDA thresholds)

---

### 2.6 `src/sensors/emg_processor.py`

**Responsabilité:** Traiter le signal EMG brut et détecter les contractions musculaires.

```python
import numpy as np
from typing import Optional
from collections import deque

class EMGProcessor:
    """Process EMG (Electromyography) signal."""
    
    def __init__(self, rms_baseline: float) -> None:
        """Initialize with baseline RMS noise level."""
        self.rms_baseline = rms_baseline
        self._window = deque(maxlen=50)  # 0.5s window at 100Hz for RMS
    
    def process_raw(self, raw_value: int) -> float:
        """
        Convert raw ADC value to EMG amplitude.
        Returns rectified EMG value.
        """
    
    def compute_rms(self) -> float:
        """
        Compute RMS (Root Mean Square) of current window.
        Returns RMS value.
        """
    
    def compute_tension_index(self) -> float:
        """
        Compute EMG tension index: current_rms / rms_baseline.
        Returns normalized tension index.
        """
    
    def detect_contraction(self) -> str:
        """
        Detect contraction level based on RMS.
        Returns: "rest", "light", "strong".
        """
```

**Dépendances:**
- `numpy`
- `config.py` (EMG thresholds)

---

### 2.7 `src/sensors/acc_processor.py`

**Responsabilité:** Traiter le signal ACC (accéléromètre) et détecter l'agitation motrice.

```python
import numpy as np
from typing import Optional
from collections import deque

class ACCProcessor:
    """Process ACC (Accelerometer) signal - single axis."""
    
    def __init__(self, baseline_mean: float, baseline_std: float) -> None:
        """Initialize with baseline statistics."""
        self.baseline_mean = baseline_mean
        self.baseline_std = baseline_std
        self._smoothing_window = deque(maxlen=20)  # 0.2s smoothing
    
    def process_raw(self, raw_value: int) -> float:
        """
        Convert raw ADC value to acceleration magnitude (single axis).
        Applies smoothing filter.
        Returns smoothed acceleration value.
        """
    
    def compute_acc_index(self, acc_value: float) -> float:
        """
        Compute ACC index: current / baseline_mean.
        Returns normalized agitation index.
        """
    
    def detect_movement(self, acc_index: float) -> str:
        """
        Classify movement level.
        Returns: "rest", "agitation", "movement".
        """
```

**Dépendances:**
- `numpy`
- `config.py` (ACC thresholds)

---

### 2.8 `src/sensors/fsr_processor.py`

**Responsabilité:** Traiter le signal FSR (capteur de pression) et détecter les appuis.

```python
import numpy as np
from typing import Optional

class FSRProcessor:
    """Process FSR (Force Sensitive Resistor) signal."""
    
    def __init__(self, baseline_value: float, threshold_press: float) -> None:
        """Initialize with baseline and press threshold."""
        self.baseline_value = baseline_value
        self.threshold_press = threshold_press
        self._last_state = False  # False = not pressed, True = pressed
    
    def process_raw(self, raw_value: int) -> float:
        """
        Convert raw ADC value to pressure value.
        Returns pressure value in arbitrary units.
        """
    
    def is_pressed(self, fsr_value: float) -> bool:
        """
        Detect if FSR is currently pressed.
        Returns True if pressed, False otherwise.
        """
    
    def detect_press_event(self, fsr_value: float) -> bool:
        """
        Detect rising edge (new press event).
        Returns True on transition from not_pressed to pressed.
        """
```

**Dépendances:**
- `config.py` (FSR_THRESHOLD_PRESS)

---

### 2.9 `src/sensors/ppg_processor.py`

**Responsabilité:** Traiter le signal PPG (photopléthysmographie) et détecter les battements cardiaques.

```python
import numpy as np
from typing import List, Optional
from collections import deque

class PPGProcessor:
    """Process PPG (Photoplethysmography) signal."""
    
    def __init__(self, sampling_rate: int) -> None:
        """Initialize PPG processor."""
        self.sampling_rate = sampling_rate
        self._signal_window = deque(maxlen=sampling_rate * 10)  # 10s window
        self._peak_indices: List[int] = []
        self._ibi_values: List[float] = []  # Inter-Beat Intervals in ms
    
    def process_raw(self, raw_value: int) -> float:
        """
        Convert raw ADC value to PPG signal.
        Applies bandpass filter (0.5-4 Hz for heart rate).
        Returns filtered PPG value.
        """
    
    def detect_peaks(self) -> List[int]:
        """
        Detect R-peaks in current window using adaptive threshold.
        Returns list of peak indices.
        """
    
    def compute_ibi(self) -> List[float]:
        """
        Compute Inter-Beat Intervals from detected peaks.
        Returns list of IBI values in milliseconds.
        """
    
    def compute_bpm(self) -> Optional[float]:
        """
        Compute current BPM from recent IBIs.
        Returns BPM or None if not enough data.
        """
```

**Dépendances:**
- `numpy`
- `scipy.signal` (pour filtrage)

---

### 2.10 `src/sensors/hrv_analyzer.py`

**Responsabilité:** Calculer les métriques HRV (Heart Rate Variability) à partir des IBI.

```python
import numpy as np
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class HRVMetrics:
    """Heart Rate Variability metrics."""
    rmssd: float  # Root Mean Square of Successive Differences (ms)
    sdnn: float  # Standard Deviation of NN intervals (ms)
    mean_ibi: float  # Mean IBI (ms)
    mean_hr: float  # Mean heart rate (BPM)

class HRVAnalyzer:
    """Analyze Heart Rate Variability from IBI data."""
    
    def __init__(self, window_size: int = 60) -> None:
        """
        Initialize HRV analyzer.
        window_size: analysis window in seconds.
        """
        self.window_size = window_size
    
    def compute_rmssd(self, ibi_values: List[float]) -> Optional[float]:
        """
        Compute RMSSD (Root Mean Square of Successive Differences).
        ibi_values: list of IBI in milliseconds.
        Returns RMSSD in ms, or None if insufficient data.
        """
    
    def compute_sdnn(self, ibi_values: List[float]) -> Optional[float]:
        """
        Compute SDNN (Standard Deviation of NN intervals).
        Returns SDNN in ms, or None if insufficient data.
        """
    
    def compute_metrics(self, ibi_values: List[float]) -> Optional[HRVMetrics]:
        """
        Compute all HRV metrics.
        Returns HRVMetrics object or None if insufficient data.
        """
    
    def compute_hrv_drop(
        self, 
        current_rmssd: float, 
        baseline_rmssd: float
    ) -> float:
        """
        Compute HRV drop percentage.
        Returns: (baseline - current) / baseline * 100.
        """
```
**Dépendances:**
- `numpy`
- `config.py` (HRV_WINDOW_SIZE)

---

### 2.11 `src/cognitive_load.py`

**Responsabilité:** Calculer le CCI (Cognitive Capacity Index) et détecter le point de bascule.

```python
from dataclasses import dataclass
from typing import Optional, List
from collections import deque
import time

@dataclass
class CCISnapshot:
    """Snapshot of CCI calculation at a given time."""
    timestamp: float
    cci: float
    eda_index: float
    hrv_drop: float
    acc_index: float
    emg_tension: float

@dataclass
class TippingPoint:
    """Detected cognitive overload tipping point."""
    timestamp: float
    cci_value: float
    duration_above_threshold: float  # seconds

class CognitiveLoadAnalyzer:
    """Analyze cognitive load and detect overload tipping point."""
    
    def __init__(
        self,
        cci_weights: dict,
        overload_threshold: float,
        overload_duration: float
    ) -> None:
        """Initialize with CCI configuration."""
        self.cci_weights = cci_weights
        self.overload_threshold = overload_threshold
        self.overload_duration = overload_duration
        
        self._cci_history: deque = deque(maxlen=3600)  # 1 hour at 1Hz
        self._tipping_point: Optional[TippingPoint] = None
        self._overload_start: Optional[float] = None
    
    def compute_cci(
        self,
        eda_index: float,
        hrv_drop: float,
        acc_index: float,
        emg_tension: float
    ) -> float:
        """
        Compute Cognitive Capacity Index.
        Formula: CCI = (eda_index * 0.35) + (hrv_drop * 0.35) +
                       (acc_index * 0.15) + (emg_tension * 0.15)
        Returns normalized CCI (0-10 scale).
        """
    
    def update(
        self,
        timestamp: float,
        eda_index: float,
        hrv_drop: float,
        acc_index: float,
        emg_tension: float
    ) -> CCISnapshot:
        """
        Update CCI calculation with new data.
        Returns CCISnapshot with current CCI.
        """
    
    def detect_tipping_point(self, current_time: float) -> Optional[TippingPoint]:
        """
        Detect if cognitive overload tipping point has been reached.
        Criteria: CCI > threshold for > duration seconds.
        Returns TippingPoint if detected, None otherwise.
        """
    
    def get_tipping_point(self) -> Optional[TippingPoint]:
        """
        Get the detected tipping point (if any).
        Returns TippingPoint or None.
        """
    
    def get_cci_history(self) -> List[CCISnapshot]:
        """
        Get complete CCI history.
        Returns list of CCISnapshot.
        """
    
    def get_current_cci(self) -> Optional[float]:
        """
        Get most recent CCI value.
        Returns CCI or None if no data.
        """
```

**Méthodes privées:**

```python
def _normalize_cci(self, raw_cci: float) -> float:
    """
    Normalize CCI to 0-10 scale.
    Applies clamping to prevent values outside range.
    """
```

**Dépendances:**
- `config.py` (CCI_WEIGHTS, CCI_OVERLOAD_THRESHOLD, CCI_OVERLOAD_DURATION)

---

### 2.12 `src/report/reporter.py`

**Responsabilité:** Générer le rapport HTML final et sauvegarder les données de session.

```python
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from pathlib import Path
import json
import csv
from datetime import datetime
from jinja2 import Template
import matplotlib.pyplot as plt
import io
import base64

@dataclass
class SessionEvent:
    """Event annotation during session."""
    timestamp: float
    event_type: str  # "round_start", "round_end", "question", "response", "emg_challenge", "fsr_challenge"
    data: dict  # Event-specific data

@dataclass
class SessionMetadata:
    """Metadata for a session."""
    session_id: str  # YYYYMMDD_HHMMSS
    start_time: str  # ISO format
    end_time: str  # ISO format
    duration: float  # seconds
    mac_address: str
    sampling_rate: int

class SessionReporter:
    """Generate session report and save data."""
    
    def __init__(self, session_id: str, output_dir: str = "reports") -> None:
        """Initialize reporter with session ID."""
        self.session_id = session_id
        self.output_dir = Path(output_dir)
        self.data_dir = Path("data") / f"session_{session_id}"
        
        self._metadata: Optional[SessionMetadata] = None
        self._baseline_data: Optional[dict] = None
        self._sensor_data: Dict[str, List[tuple]] = {}  # sensor -> [(timestamp, value)]
        self._cci_data: List[tuple] = []  # [(timestamp, cci, eda_idx, hrv_drop, acc_idx, emg_tension)]
        self._events: List[SessionEvent] = []
        
    def set_metadata(self, metadata: SessionMetadata) -> None:
        """Set session metadata."""
    
    def set_baseline(self, baseline_data: dict) -> None:
        """Set baseline data for report."""
    
    def log_sensor_data(self, timestamp: float, sensor: str, value: float) -> None:
        """Log sensor data point."""
    
    def log_cci_data(
        self,
        timestamp: float,
        cci: float,
        eda_index: float,
        hrv_drop: float,
        acc_index: float,
        emg_tension: float
    ) -> None:
        """Log CCI calculation data."""
    
    def log_event(self, event: SessionEvent) -> None:
        """Log session event."""
    
    def save_raw_data(self) -> None:
        """
        Save all raw data to CSV files in data/session_XXX/.
        Creates one CSV per sensor and one for CCI data.
        """
    
    def save_events(self) -> None:
        """Save events to JSON file."""
    
    def generate_report(
        self,
        tipping_point: Optional[TippingPoint],
        template_path: str = "src/report/templates/report.html"
    ) -> str:
        """
        Generate HTML report.
        Returns path to generated report file.
        """
```

**Méthodes privées:**

```python
def _create_sensor_plot(self, sensor: str) -> str:
    """
    Create base64-encoded PNG plot for a sensor.
    Returns base64 string for embedding in HTML.
    """

def _create_cci_plot(self, tipping_point: Optional[TippingPoint]) -> str:
    """
    Create base64-encoded PNG plot for CCI with tipping point marker.
    Returns base64 string.
    """

def _analyze_most_reactive_sensor(self) -> str:
    """
    Determine which sensor deviated most from baseline.
    Returns sensor name.
    """

def _compute_eda_hrv_correlation(self) -> float:
    """
    Compute correlation between EDA rise and HRV drop.
    Returns Pearson correlation coefficient.
    """

def _generate_conclusion(self, tipping_point: Optional[TippingPoint]) -> str:
    """
    Generate automatic text conclusion.
    Returns HTML-formatted conclusion text.
    """

def _ensure_directories(self) -> None:
    """Create output directories if they don't exist."""
```

**Dépendances:**
- `jinja2` (template engine)
- `matplotlib` (pour génération graphiques)
- `pandas` (pour manipulation données)
- `numpy` (pour corrélations)
- `config.py`
- `cognitive_load.py` (TippingPoint)

---

### 2.13 `src/report/templates/report.html`

**Responsabilité:** Template Jinja2 pour le rapport HTML.

**Variables attendues du template:**
- `metadata: SessionMetadata`
- `baseline: dict` - Données baseline par capteur
- `sensor_plots: Dict[str, str]` - Base64 images par capteur
- `cci_plot: str` - Base64 image du graphique CCI
- `tipping_point: Optional[TippingPoint]`
- `most_reactive_sensor: str`
- `eda_hrv_correlation: float`
- `conclusion: str` - HTML formatté

**Structure HTML:**
```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>IQ Overload - Rapport de Session {{ metadata.session_id }}</title>
    <style>
        /* CSS inline pour autonomie du rapport */
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #2c3e50; }
        h2 { color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #3498db; color: white; }
        .plot { margin: 20px 0; text-align: center; }
        .plot img { max-width: 100%; height: auto; }
        .tipping-point { background-color: #e74c3c; color: white; padding: 10px; border-radius: 5px; }
        .conclusion { background-color: #ecf0f1; padding: 20px; border-left: 5px solid #3498db; }
    </style>
</head>
<body>
    <h1>IQ Overload - Rapport de Session</h1>
    
    <!-- Section 1: En-tête -->
    <section id="metadata">
        <h2>Informations de Session</h2>
        <table>
            <tr><th>ID Session</th><td>{{ metadata.session_id }}</td></tr>
            <tr><th>Début</th><td>{{ metadata.start_time }}</td></tr>
            <tr><th>Fin</th><td>{{ metadata.end_time }}</td></tr>
            <tr><th>Durée</th><td>{{ "%.1f"|format(metadata.duration) }} secondes</td></tr>
            <tr><th>MAC Address</th><td>{{ metadata.mac_address }}</td></tr>
            <tr><th>Fréquence</th><td>{{ metadata.sampling_rate }} Hz</td></tr>
        </table>
    </section>
    
    <!-- Section 2: Baseline -->
    <section id="baseline">
        <h2>Valeurs de Référence (Baseline)</h2>
        <!-- Tables pour chaque capteur avec valeurs baseline -->
        {% for sensor, data in baseline.items() %}
        <h3>{{ sensor }}</h3>
        <table>
            {% for key, value in data.items() %}
            <tr><th>{{ key }}</th><td>{{ "%.4f"|format(value) if value is number else value }}</td></tr>
            {% endfor %}
        </table>
        {% endfor %}
    </section>
    
    <!-- Section 3: Graphiques capteurs -->
    <section id="sensor-plots">
        <h2>Évolution des Capteurs</h2>
        {% for sensor, plot_b64 in sensor_plots.items() %}
        <div class="plot">
            <h3>{{ sensor }}</h3>
            <img src="data:image/png;base64,{{ plot_b64 }}" alt="Plot {{ sensor }}">
        </div>
        {% endfor %}
    </section>
    
    <!-- Section 4: CCI -->
    <section id="cci">
        <h2>Charge Cognitive Index (CCI)</h2>
        <div class="plot">
            <img src="data:image/png;base64,{{ cci_plot }}" alt="CCI Plot">
        </div>
        
        {% if tipping_point %}
        <div class="tipping-point">
            <h3>⚠️ Point de Bascule Détecté</h3>
            <p><strong>Timestamp:</strong> {{ "%.2f"|format(tipping_point.timestamp) }}s</p>
            <p><strong>CCI:</strong> {{ "%.2f"|format(tipping_point.cci_value) }}</p>
            <p><strong>Durée au-dessus seuil:</strong> {{ "%.2f"|format(tipping_point.duration_above_threshold) }}s</p>
        </div>
        {% else %}
        <p>Aucun point de bascule détecté durant la session.</p>
        {% endif %}
    </section>
    
    <!-- Section 5: Analyse automatique -->
    <section id="analysis">
        <h2>Analyse Automatique</h2>
        <table>
            <tr><th>Capteur le plus réactif</th><td>{{ most_reactive_sensor }}</td></tr>
            <tr><th>Corrélation EDA-HRV</th><td>{{ "%.3f"|format(eda_hrv_correlation) }}</td></tr>
        </table>
    </section>
    
    <!-- Section 6: Conclusion -->
    <section id="conclusion">
        <h2>Conclusion</h2>
        <div class="conclusion">
            {{ conclusion|safe }}
        </div>
    </section>
    
    <footer>
        <p style="text-align: center; color: #7f8c8d; margin-top: 40px;">
            Généré par IQ Overload - {{ metadata.end_time }}
        </p>
    </footer>
</body>
</html>
```

**Dépendances:**
- Aucune (HTML/CSS pur)

---

### 2.14 `src/app.py`

**Responsabilité:** Point d'entrée principal, orchestration de tous les modules.

```python
import sys
import signal
import threading
import queue
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

import config
from bitalino_reader import BITalinoReader, RawFrame
from visualizer import SensorVisualizer
from calibration import CalibrationManager, BaselineData
from cognitive_load import CognitiveLoadAnalyzer, CCISnapshot
from report.reporter import SessionReporter, SessionMetadata, SessionEvent
from sensors.eda_processor import EDAProcessor
from sensors.emg_processor import EMGProcessor
from sensors.acc_processor import ACCProcessor
from sensors.fsr_processor import FSRProcessor
from sensors.ppg_processor import PPGProcessor
from sensors.hrv_analyzer import HRVAnalyzer

class IQOverloadApp:
    """Main application orchestrator."""
    
    def __init__(self) -> None:
        """Initialize application."""
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.data_queue: queue.Queue[RawFrame] = queue.Queue()
        self.stop_event = threading.Event()
        
        # Components
        self.reader: Optional[BITalinoReader] = None
        self.visualizer: Optional[SensorVisualizer] = None
        self.calibration: Optional[CalibrationManager] = None
        self.cci_analyzer: Optional[CognitiveLoadAnalyzer] = None
        self.reporter: Optional[SessionReporter] = None
        
        # Processors (initialized after calibration)
        self.processors: dict = {}
        
        # State
        self.baseline: Optional[BaselineData] = None
        self.is_calibrated = False
        self.start_time: Optional[float] = None
    
    def setup(self) -> bool:
        """
        Setup all components and establish connection.
        Returns True if successful.
        """
    
    def run_calibration(self) -> bool:
        """
        Run 20-second calibration phase.
        Returns True if successful.
        """
    
    def start_session(self) -> None:
        """
        Start main session loop.
        Processes data from queue and updates visualizer/CCI.
        """
    
    def stop_session(self) -> None:
        """
        Stop session gracefully and generate report.
        """
    
    def run(self) -> None:
        """
        Main entry point.
        Runs complete flow: setup -> calibration -> session -> report.
        """
```

**Méthodes privées:**

```python
def _setup_signal_handlers(self) -> None:
    """Setup Ctrl+C handler for graceful shutdown."""

def _initialize_processors(self) -> None:
    """Initialize all sensor processors with baseline data."""

def _process_frame(self, frame: RawFrame) -> None:
    """
    Process a single frame from BITalino.
    Updates visualizer, processors, CCI, and reporter.
    """

def _data_processing_loop(self) -> None:
    """
    Main data processing loop running in main thread.
    Pulls from queue and processes frames.
    """

def _ensure_directories(self) -> None:
    """Create data/ and reports/ directories if needed."""
```

**Fonction principale:**

```python
def main() -> int:
    """
    Main entry point.
    Returns exit code.
    """
    app = IQOverloadApp()
    try:
        app.run()
        return 0
    except KeyboardInterrupt:
        print("\n⚠️  Interruption détectée, arrêt en cours...")
        app.stop_session()
        return 0
    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

**Dépendances:**
- Tous les autres modules du projet
- `config.py`
- `signal` (stdlib)
- `threading` (stdlib)
- `queue` (stdlib)

---

## 3. Structures de données partagées

### 3.1 Format JSON Baseline

**Fichier:** `data/baseline_YYYYMMDD_HHMMSS.json`

```json
{
  "timestamp": "2024-01-15T14:30:00",
  "duration": 20,
  "sampling_rate": 100,
  "eda": {
    "mean": 512.34,
    "std": 12.45,
    "min": 480.12,
    "max": 540.67,
    "samples_count": 2000,
    "threshold_moderate": 536.24,
    "threshold_high": 548.69
  },
  "emg": {
    "mean": 505.23,
    "std": 8.12,
    "min": 490.45,
    "max": 520.34,
    "samples_count": 2000,
    "rms_baseline": 6.78,
    "threshold_light": 20.34,
    "threshold_strong": 54.24,
    "threshold_target": 33.90
  },
  "acc": {
    "mean": 515.67,
    "std": 5.23,
    "min": 500.12,
    "max": 530.45,
    "samples_count": 2000,
    "threshold_agitation": 526.13,
    "threshold_movement": 536.59
  },
  "fsr": {
    "mean": 10.23,
    "std": 2.34,
    "min": 5.12,
    "max": 15.67,
    "samples_count": 2000,
    "threshold_press": 30.23
  },
  "ppg": {
    "mean": 520.45,
    "std": 15.67,
    "min": 480.12,
    "max": 560.34,
    "samples_count": 2000,
    "hrv_baseline": 45.67,
    "bpm_baseline": 72.34
  }
}
```

### 3.2 Format CSV Données Capteur

**Fichier:** `data/session_YYYYMMDD_HHMMSS/sensor_EDA.csv`

```csv
timestamp,value,processed_value
0.00,512.34,512.34
0.01,512.45,512.38
0.02,512.67,512.49
...
```

**Colonnes:**
- `timestamp`: float, temps relatif en secondes depuis début session
- `value`: float, valeur brute du capteur (ADC)
- `processed_value`: float, valeur après traitement (smoothing, etc.)

### 3.3 Format CSV Données CCI

**Fichier:** `data/session_YYYYMMDD_HHMMSS/cci_data.csv`

```csv
timestamp,cci,eda_index,hrv_drop,acc_index,emg_tension
0.00,2.34,0.45,5.67,0.89,1.23
1.00,2.56,0.56,6.12,0.91,1.34
2.00,3.12,0.78,7.89,1.23,1.67
...
```

**Colonnes:**
- `timestamp`: float, temps relatif en secondes
- `cci`: float, score CCI calculé (0-10)
- `eda_index`: float, indice EDA normalisé
- `hrv_drop`: float, pourcentage de chute HRV
- `acc_index`: float, indice d'agitation
- `emg_tension`: float, indice de tension musculaire

### 3.4 Format JSON Événements

**Fichier:** `data/session_YYYYMMDD_HHMMSS/events.json`

```json
{
  "events": [
    {
      "timestamp": 0.0,
      "event_type": "session_start",
      "data": {}
    },
    {
      "timestamp": 30.5,
      "event_type": "round_start",
      "data": {"round": 1}
    },
    {
      "timestamp": 35.2,
      "event_type": "question",
      "data": {"question_id": 1, "text": "2+2=?"}
    },
    {
      "timestamp": 38.7,
      "event_type": "response",
      "data": {"question_id": 1, "answer": "4", "correct": true, "reaction_time": 3.5}
    },
    {
      "timestamp": 90.0,
      "event_type": "round_end",
      "data": {"round": 1, "score": 5}
    },
    {
      "timestamp": 120.5,
      "event_type": "tipping_point",
      "data": {"cci": 7.23}
    }
  ]
}
```

### 3.5 Structure Queue Inter-threads

**Type:** `queue.Queue[RawFrame]`

**Objet transmis:** `RawFrame` (dataclass défini dans bitalino_reader.py)

```python
@dataclass
class RawFrame:
    timestamp: float  # Unix timestamp (time.time())
    sequence: int     # Numéro de séquence BITalino
    channels: List[int]  # Liste des valeurs ADC brutes [EMG, EDA, ACC, FSR, _, PPG]
                         # Index correspond aux ports: [1, 2, 3, 4, 5, 6]
```

---

## 4. Contrats d'interface entre modules

### 4.1 bitalino_reader → visualizer

**Ce que bitalino_reader expose:**
- `RawFrame` via `data_queue.get()`

**Ce que visualizer fait:**
- Extrait les valeurs brutes par port
- Appelle `visualizer.update_data(sensor, timestamp, value)` pour chaque capteur
- Appelle `visualizer.update_plots()` périodiquement (1Hz)

**Mapping ports → sensors:**
```python
channels[0] → EMG (port 1)
channels[1] → EDA (port 2)
channels[2] → ACC (port 3)
channels[3] → FSR (port 4)
channels[4] → (vide, port 5 non utilisé)
channels[5] → PPG (port 6)
```

### 4.2 bitalino_reader → calibration

**Ce que bitalino_reader expose:**
- `RawFrame` via `data_queue.get()`

**Ce que calibration fait:**
- Accumule les valeurs brutes pendant 20 secondes
- Appelle `calibration.add_sample(sensor, raw_value)` pour chaque frame
- Vérifie `calibration.is_complete()` à chaque frame
- Appelle `calibration.compute_baseline()` quand complet
- Sauvegarde avec `calibration.save_baseline(output_dir)`

**Contrainte:**
- Calibration s'exécute dans le même thread que le traitement principal
- Pas de traitement CCI pendant la calibration

### 4.3 calibration → sensors/*_processor

**Ce que calibration expose:**
- `BaselineData` complet après `compute_baseline()`

**Ce que les processors utilisent:**
```python
# Exemple pour EDAProcessor
eda_baseline = baseline.eda
processor = EDAProcessor(
    baseline_mean=eda_baseline.mean,
    baseline_std=eda_baseline.std
)

# Exemple pour EMGProcessor
emg_baseline = baseline.emg
processor = EMGProcessor(
    rms_baseline=emg_baseline.rms_baseline
)
```

### 4.4 sensors/*_processor → cognitive_load

**Ce que les processors exposent:**
```python
# EDAProcessor
eda_index = eda_processor.compute_eda_index(eda_value)

# EMGProcessor
emg_tension = emg_processor.compute_tension_index()

# ACCProcessor
acc_index = acc_processor.compute_acc_index(acc_value)

# HRVAnalyzer (via PPGProcessor)
hrv_drop = hrv_analyzer.compute_hrv_drop(current_rmssd, baseline_rmssd)
```

**Ce que cognitive_load fait:**
```python
snapshot = cci_analyzer.update(
    timestamp=current_time,
    eda_index=eda_index,
    hrv_drop=hrv_drop,
    acc_index=acc_index,
    emg_tension=emg_tension
)

tipping_point = cci_analyzer.detect_tipping_point(current_time)
```

### 4.5 cognitive_load → reporter

**Ce que cognitive_load expose:**
```python
# Liste complète des snapshots
cci_history: List[CCISnapshot] = cci_analyzer.get_cci_history()

# Point de bascule (si détecté)
tipping_point: Optional[TippingPoint] = cci_analyzer.get_tipping_point()
```

**Ce que reporter fait:**
```python
# Log chaque CCI snapshot
for snapshot in cci_history:
    reporter.log_cci_data(
        snapshot.timestamp,
        snapshot.cci,
        snapshot.eda_index,
        snapshot.hrv_drop,
        snapshot.acc_index,
        snapshot.emg_tension
    )

# Génère rapport avec tipping point
reporter.generate_report(tipping_point)
```

### 4.6 app.py → tous les modules

**app.py est le chef d'orchestre:**

```python
# 1. Initialise reader et démarre thread acquisition
reader = BITalinoReader(...)
reader.connect()
reader.start_acquisition()  # Lance thread

# 2. Initialise visualizer
visualizer = SensorVisualizer(...)
visualizer.setup_plots()

# 3. Lance calibration
calibration = CalibrationManager(...)
# Traite frames pendant 20s
baseline = calibration.compute_baseline()

# 4. Initialise processors avec baseline
eda_proc = EDAProcessor(baseline.eda.mean, baseline.eda.std)
# ... autres processors

# 5. Initialise CCI analyzer
cci = CognitiveLoadAnalyzer(...)

# 6. Initialise reporter
reporter = SessionReporter(session_id)

# 7. Boucle principale
while not stop_event.is_set():
    frame = data_queue.get(timeout=0.1)
    
    # Process frame
    processed_values = {
        'eda': eda_proc.process_raw(frame.channels[1]),
        'emg': emg_proc.process_raw(frame.channels[0]),
        # ...
    }
    
    # Update visualizer
    for sensor, value in processed_values.items():
        visualizer.update_data(sensor, frame.timestamp, value)
    
    # Compute CCI (every second)
    if should_compute_cci:
        cci_snapshot = cci.update(...)
        reporter.log_cci_data(...)
    
    # Check tipping point
    tipping_point = cci.detect_tipping_point(current_time)

# 8. Generate report
reporter.save_raw_data()
reporter.generate_report(tipping_point)
```

---

## 5. Formules et constantes

### 5.1 Formule CCI (Cognitive Capacity Index)

```python
CCI = (eda_index × 0.35) + (hrv_drop × 0.35) + (acc_index × 0.15) + (emg_tension × 0.15)
```

**Normalisation:**
- `cci_raw` peut théoriquement dépasser 10
- Clamping appliqué: `cci_final = min(max(cci_raw, 0), 10)`

### 5.2 Formule EDA Index

```python
eda_index = (valeur_actuelle - baseline_mean) / baseline_std
```
**Classification:**
- `< 1.0`: normal
- `1.0 - 2.0`: modéré
- `2.0 - 3.0`: élevé
- `> 3.0`: surcharge

### 5.3 Formule EMG Tension Index

```python
emg_tension = rms_actuel / rms_baseline
```

**Où:**
```python
rms_actuel = sqrt(mean(window^2))  # window = 50 derniers échantillons (0.5s à 100Hz)
```

**Classification des contractions:**
- `< 3.0`: repos
- `3.0 - 8.0`: contraction légère
- `> 8.0`: contraction forte

### 5.4 Formule ACC Index

```python
acc_index = magnitude_actuelle / magnitude_baseline
```

**Pour un seul axe (ACC simplifié):**
```python
magnitude_actuelle = smoothed_value  # Moyenne glissante sur 20 échantillons (0.2s)
magnitude_baseline = baseline_mean
```

**Classification:**
- `< 2.0`: repos
- `2.0 - 4.0`: agitation
- `> 4.0`: mouvement significatif

### 5.5 Formule HRV Drop

```python
hrv_drop = ((hrv_baseline - hrv_actuel) / hrv_baseline) × 100
```

**Où:**
```python
hrv_baseline = RMSSD calculé pendant calibration (ms)
hrv_actuel = RMSSD calculé sur fenêtre glissante de 60 secondes (ms)
```

**Classification:**
- `< 20%`: charge normale
- `20% - 40%`: charge significative
- `> 40%`: surcharge

### 5.6 Calcul RMSSD (Root Mean Square of Successive Differences)

```python
# ibi_values = liste des Inter-Beat Intervals en millisecondes
successive_diffs = [ibi_values[i+1] - ibi_values[i] for i in range(len(ibi_values)-1)]
rmssd = sqrt(mean([diff^2 for diff in successive_diffs]))
```

**Minimum requis:** 5 IBIs consécutifs pour calcul valide

### 5.7 Calcul RMS pour EMG

```python
# window = liste des 50 dernières valeurs EMG rectifiées
rms = sqrt(mean([value^2 for value in window]))
```

### 5.8 Seuils de calibration

**EDA:**
```python
threshold_moderate = baseline_mean + (2 × baseline_std)
threshold_high = baseline_mean + (3 × baseline_std)
```

**EMG:**
```python
threshold_light = rms_baseline × 3
threshold_strong = rms_baseline × 8
threshold_target = rms_baseline × 5
```

**ACC:**
```python
threshold_agitation = baseline_mean + (2 × baseline_std)
threshold_movement = baseline_mean + (4 × baseline_std)
```

**FSR:**
```python
threshold_press = baseline_value + 20  # Offset fixe de 20 unités ADC
```

### 5.9 Détection du Point de Bascule

**Méthode 1: Durée continue au-dessus du seuil**
```python
if cci > CCI_OVERLOAD_THRESHOLD (7.0):
    if duration_above_threshold > CCI_OVERLOAD_DURATION (3.0 secondes):
        tipping_point_detected = True
        tipping_point_timestamp = first_timestamp_above_threshold
```

**Méthode 2: Comparaison entre rounds (Phase 2)**
```python
if mean_cci_round_N > (mean_cci_round_1 × CCI_BASELINE_MULTIPLIER (2.0)):
    tipping_point_detected = True
    tipping_point_round = N
```

### 5.10 Constantes de lissage (smoothing)

**EDA:**
- Fenêtre: 10 échantillons (0.1 seconde à 100Hz)
- Méthode: Moyenne mobile simple

**EMG:**
- Fenêtre: 50 échantillons (0.5 seconde à 100Hz)
- Méthode: RMS glissant

**ACC:**
- Fenêtre: 20 échantillons (0.2 seconde à 100Hz)
- Méthode: Moyenne mobile simple

**PPG:**
- Filtre: Butterworth passe-bande 0.5-4 Hz (ordre 4)
- Fenêtre détection pics: 10 secondes (1000 échantillons)

### 5.11 Conversion ADC

**BITalino ADC résolution 16 bits:**
```python
# Valeurs brutes: 0 à 65535 (2^16 - 1)
# La plupart des capteurs sont centrés autour de 32768 (milieu de la plage)

# Pas de conversion voltage nécessaire en Phase 1
# On travaille directement avec les valeurs ADC normalisées
raw_value = channels[port_index]  # 0-65535
```

---

## 6. Stratégie de tests

### 6.1 Tests pour `bitalino_reader.py`

**Fichier:** `tests/test_bitalino_reader.py`

**Ce qu'on teste:**
- `test_rawframe_creation()`: Création d'un RawFrame
- `test_bitalino_reader_init()`: Initialisation correcte
- `test_onRawFrame_puts_data_in_queue()`: Callback met données dans queue
- `test_stop_event_stops_acquisition()`: Event stop fonctionne
- `test_reconnection_attempts()`: Tentatives de reconnexion (mock)

**Comment mocker la connexion BITalino:**
```python
import pytest
from unittest.mock import Mock, patch, MagicMock
import queue
from bitalino_reader import BITalinoReader, RawFrame

@pytest.fixture
def mock_plux_device():
    """Mock du device plux.SignalsDev."""
    with patch('bitalino_reader.plux.SignalsDev.__init__', return_value=None):
        yield

@pytest.fixture
def data_queue():
    return queue.Queue()

def test_onRawFrame_puts_data_in_queue(mock_plux_device, data_queue):
    reader = BITalinoReader(
        address="00:00:00:00:00:00",
        sampling_rate=100,
        active_ports=[1, 2, 3, 4, 6],
        resolution=16,
        data_queue=data_queue
    )
    
    # Simuler un appel au callback
    result = reader.onRawFrame(0, [100, 200, 300, 400, 500, 600])
    
    # Vérifier que les données sont dans la queue
    assert not data_queue.empty()
    frame = data_queue.get()
    assert isinstance(frame, RawFrame)
    assert len(frame.channels) == 6
    assert frame.channels[0] == 100
```

### 6.2 Tests pour `calibration.py`

**Fichier:** `tests/test_calibration.py`

**Ce qu'on teste:**
- `test_calibration_manager_init()`: Initialisation
- `test_add_sample()`: Ajout d'échantillons
- `test_is_complete()`: Détection de complétion
- `test_compute_eda_baseline()`: Calcul baseline EDA
- `test_compute_emg_baseline()`: Calcul baseline EMG avec RMS
- `test_compute_all_baselines()`: Calcul complet
- `test_save_and_load_baseline()`: Sauvegarde/chargement JSON

**Données de test synthétiques:**
```python
import numpy as np

@pytest.fixture
def synthetic_eda_data():
    """Données EDA synthétiques: signal stable avec peu de bruit."""
    np.random.seed(42)
    baseline = 512.0
    noise = np.random.normal(0, 5, 2000)
    return baseline + noise

@pytest.fixture
def synthetic_emg_data():
    """Données EMG synthétiques: bruit de base au repos."""
    np.random.seed(42)
    baseline = 510.0
    noise = np.random.normal(0, 3, 2000)
    return baseline + noise

def test_compute_eda_baseline(synthetic_eda_data):
    manager = CalibrationManager(duration=20, sampling_rate=100)
    
    for value in synthetic_eda_data:
        manager.add_sample("EDA", value)
    
    assert manager.is_complete()
    baseline = manager.compute_baseline()
    
    assert baseline.eda.mean == pytest.approx(512.0, abs=1.0)
    assert baseline.eda.std > 0
    assert baseline.eda.threshold_moderate > baseline.eda.mean
```

### 6.3 Tests pour `sensors/*_processor.py`

**Fichier:** `tests/test_sensors/test_eda_processor.py`

**Ce qu'on teste:**
- `test_eda_processor_init()`: Initialisation
- `test_process_raw_smoothing()`: Lissage correct
- `test_compute_eda_index()`: Calcul index correct
- `test_classify_level()`: Classification correcte

**Données de test:**
```python
def test_compute_eda_index():
    processor = EDAProcessor(baseline_mean=500.0, baseline_std=10.0)
    
    # Valeur = baseline → index = 0
    assert processor.compute_eda_index(500.0) == 0.0
    
    # Valeur = baseline + 1×std → index = 1
    assert processor.compute_eda_index(510.0) == pytest.approx(1.0)
    
    # Valeur = baseline + 2×std → index = 2
    assert processor.compute_eda_index(520.0) == pytest.approx(2.0)

def test_classify_level():
    processor = EDAProcessor(baseline_mean=500.0, baseline_std=10.0)
    
    assert processor.classify_level(0.5) == "normal"
    assert processor.classify_level(1.5) == "moderate"
    assert processor.classify_level(2.5) == "high"
    assert processor.classify_level(3.5) == "overload"
```

**Même structure pour:**
- `test_emg_processor.py`
- `test_acc_processor.py`
- `test_fsr_processor.py`
- `test_ppg_processor.py`

### 6.4 Tests pour `hrv_analyzer.py`

**Fichier:** `tests/test_sensors/test_hrv_analyzer.py`

**Ce qu'on teste:**
- `test_compute_rmssd()`: Calcul RMSSD correct
- `test_compute_sdnn()`: Calcul SDNN correct
- `test_compute_hrv_drop()`: Calcul chute HRV
- `test_insufficient_data()`: Gestion données insuffisantes

**Données de test:**
```python
def test_compute_rmssd():
    analyzer = HRVAnalyzer()
    
    # IBIs: [800, 820, 810, 830, 815] ms
    # Diffs: [20, -10, 20, -15]
    # Diffs^2: [400, 100, 400, 225]
    # Mean: 281.25
    # RMSSD: sqrt(281.25) ≈ 16.77
    ibi_values = [800.0, 820.0, 810.0, 830.0, 815.0]
    
    rmssd = analyzer.compute_rmssd(ibi_values)
    assert rmssd == pytest.approx(16.77, abs=0.1)

def test_compute_hrv_drop():
    analyzer = HRVAnalyzer()
    
    # Baseline: 50ms, Current: 30ms
    # Drop = (50-30)/50 × 100 = 40%
    drop = analyzer.compute_hrv_drop(current_rmssd=30.0, baseline_rmssd=50.0)
    assert drop == pytest.approx(40.0)
```

### 6.5 Tests pour `cognitive_load.py`

**Fichier:** `tests/test_cognitive_load.py`

**Ce qu'on teste:**
- `test_compute_cci()`: Formule CCI correcte
- `test_cci_normalization()`: Normalisation 0-10
- `test_detect_tipping_point_duration()`: Détection par durée
- `test_no_tipping_point_if_below_threshold()`: Pas de faux positifs
- `test_cci_history()`: Historique conservé

**Données de test:**
```python
def test_compute_cci():
    analyzer = CognitiveLoadAnalyzer(
        cci_weights={"eda": 0.35, "hrv": 0.35, "acc": 0.15, "emg": 0.15},
        overload_threshold=7.0,
        overload_duration=3.0
    )
    
    # Test avec valeurs connues
    # eda_index=2.0, hrv_drop=20.0, acc_index=1.0, emg_tension=1.5
    # CCI = (2.0×0.35) + (20.0×0.35) + (1.0×0.15) + (1.5×0.15)
    #     = 0.7 + 7.0 + 0.15 + 0.225 = 8.075
    cci = analyzer.compute_cci(
        eda_index=2.0,
        hrv_drop=20.0,
        acc_index=1.0,
        emg_tension=1.5
    )
    
    assert cci == pytest.approx(8.075, abs=0.01)

def test_detect_tipping_point_duration():
    analyzer = CognitiveLoadAnalyzer(
        cci_weights={"eda": 0.35, "hrv": 0.35, "acc": 0.15, "emg": 0.15},
        overload_threshold=7.0,
        overload_duration=3.0
    )
    
    # Simuler CCI > 7.0 pendant 4 secondes
    for t in range(5):
        snapshot = analyzer.update(
            timestamp=float(t),
            eda_index=3.0,
            hrv_drop=30.0,
            acc_index=2.0,
            emg_tension=2.0
        )
    
    tipping_point = analyzer.detect_tipping_point(4.0)
    
    assert tipping_point is not None
    assert tipping_point.timestamp == 0.0  # Premier moment au-dessus seuil
    assert tipping_point.duration_above_threshold >= 3.0
```

### 6.6 Tests pour `reporter.py`

**Fichier:** `tests/test_reporter.py`

**Ce qu'on teste:**
- `test_session_reporter_init()`: Initialisation
- `test_log_sensor_data()`: Logging données capteur
- `test_log_cci_data()`: Logging données CCI
- `test_save_raw_data_creates_csv()`: Création fichiers CSV
- `test_generate_report_creates_html()`: Génération rapport HTML
- `test_report_contains_all_sections()`: Toutes sections présentes

**Données de test:**
```python
import tempfile
from pathlib import Path

@pytest.fixture
def temp_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

def test_save_raw_data_creates_csv(temp_output_dir):
    reporter = SessionReporter(
        session_id="test_session",
        output_dir=temp_output_dir
    )
    
    # Log quelques données
    for t in range(10):
        reporter.log_sensor_data(float(t), "EDA", 512.0 + t)
        reporter.log_cci_data(float(t), 2.0 + t*0.1, 1.0, 10.0, 1.0, 1.0)
    
    reporter.save_raw_data()
    
    # Vérifier que les fichiers existent
    data_dir = Path("data") / "session_test_session"
    assert (data_dir / "sensor_EDA.csv").exists()
    assert (data_dir / "cci_data.csv").exists()
```

### 6.7 Tests pour `visualizer.py`

**Fichier:** `tests/test_visualizer.py`

**Ce qu'on teste:**
- `test_visualizer_init()`: Initialisation
- `test_update_data_adds_to_window()`: Ajout données
- `test_window_size_respected()`: Fenêtre glissante correcte
- `test_setup_plots_creates_subplots()`: Création subplots

**Note:** Tests visualizer difficiles car matplotlib. On teste surtout la logique de gestion des données.

```python
def test_update_data_adds_to_window():
    viz = SensorVisualizer(window_duration=10, sampling_rate=100)
    
    # Ajouter des données
    for t in range(15):
        viz.update_data("EDA", float(t), 512.0 + t)
    
    # Vérifier que seules les 10 dernières secondes sont conservées
    plot_data = viz.plot_data["EDA"]
    assert len(plot_data.timestamps) <= 10 * 100  # 10s × 100Hz
```

### 6.8 Tests pour `app.py`

**Fichier:** `tests/test_app.py`

**Ce qu'on teste:**
- `test_app_init()`: Initialisation
- `test_ensure_directories_creates_folders()`: Création répertoires
- `test_app_setup_with_mock_device()`: Setup complet (mocké)

**Note:** Tests app.py sont principalement d'intégration, difficiles à tester unitairement.

### 6.9 Commande pour exécuter tous les tests

```bash
# Tous les tests
pytest tests/ -v

# Tests spécifiques
pytest tests/test_calibration.py -v

# Tests avec couverture
pytest tests/ --cov=src --cov-report=html

# Tests rapides (skip integration)
pytest tests/ -v -m "not integration"
```

### 6.10 Fixtures partagées

**Fichier:** `tests/conftest.py`

```python
import pytest
import numpy as np
from pathlib import Path
import tempfile

@pytest.fixture
def temp_dir():
    """Temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def synthetic_baseline_data():
    """Complete synthetic baseline data for testing."""
    from calibration import BaselineData, EDABaseline, EMGBaseline, ACCBaseline, FSRBaseline, PPGBaseline
    
    return BaselineData(
        timestamp="2024-01-01T00:00:00",
        duration=20,
        sampling_rate=100,
        eda=EDABaseline(
            mean=512.0, std=10.0, min=480.0, max=540.0, samples_count=2000,
            threshold_moderate=532.0, threshold_high=542.0
        ),
        emg=EMGBaseline(
            mean=510.0, std=8.0, min=490.0, max=530.0, samples_count=2000,
            rms_baseline=5.0, threshold_light=15.0, threshold_strong=40.0, threshold_target=25.0
        ),
        acc=ACCBaseline(
            mean=515.0, std=5.0, min=500.0, max=530.0, samples_count=2000,
            threshold_agitation=525.0, threshold_movement=535.0
        ),
        fsr=FSRBaseline(
            mean=10.0, std=2.0, min=5.0, max=15.0, samples_count=2000,
            threshold_press=30.0
        ),
        ppg=PPGBaseline(
            mean=520.0, std=15.0, min=480.0, max=560.0, samples_count=2000,
            hrv_baseline=45.0, bpm_baseline=72.0
        )
    )

@pytest.fixture
def mock_raw_frame():
    """Mock RawFrame for testing."""
    from bitalino_reader import RawFrame
    import time
    
    return RawFrame(
        timestamp=time.time(),
        sequence=0,
        channels=[510, 512, 515, 10, 0, 520]  # EMG, EDA, ACC, FSR, _, PPG
    )
```

---

## 7. Récapitulatif des dépendances Python

**Fichier:** `requirements.txt`

```txt
# Core dependencies
numpy>=1.24.0
pandas>=2.0.0
matplotlib>=3.7.0
scipy>=1.10.0

# Template engine
jinja2>=3.1.0

# Testing
pytest>=7.3.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0

# Note: plux.pyd est un binaire local, pas dans PyPI
```

---

## 8. Points d'attention pour l'implémentation

### 8.1 Threading et synchronisation

- **JAMAIS** de `time.sleep()` dans le thread BITalino (perte de données)
- **TOUJOURS** utiliser `queue.get(timeout=0.1)` pour éviter blocage infini
- **TOUJOURS** vérifier `stop_event.is_set()` dans les boucles

### 8.2 Gestion mémoire

- Les `deque` ont une `maxlen` pour éviter croissance infinie
- Le reporter doit écrire les CSV progressivement pour sessions longues (Phase 2)
- En Phase 1, on peut tout garder en mémoire (sessions courtes)

### 8.3 Robustesse

- **TOUJOURS** gérer les exceptions dans les threads (sinon crash silencieux)
- **TOUJOURS** fermer proprement les ressources (BITalino, fichiers, plots)
- **TOUJOURS** logger les erreurs (print ou logging module)

### 8.4 Performance

- Calcul CCI: seulement 1 fois par seconde (pas 100 fois/sec)
- Visualizer: update plots max 10 Hz (matplotlib est lent)
- Processors: optimiser avec numpy (pas de boucles Python pures)

### 8.5 Validation des données

- Vérifier que `len(frame.channels) == 5` avant accès
- Vérifier que baseline est calculé avant d'initialiser processors
- Vérifier que calibration est complète avant de continuer

---

## 9. Ordre d'implémentation recommandé

### Phase 1 - Étape 1: Connexion continue

1. `src/config.py` ✓
2. Modifier `src/bitalino_reader.py` (RawFrame, BITalinoReader avec thread)
3. `tests/test_bitalino_reader.py`
4. Test manuel: connexion 10 minutes

### Phase 1 - Étape 2: Visualizer

5. `src/visualizer.py` (SensorVisualizer)
6. `tests/test_visualizer.py`
7. Intégration temporaire dans un script de test
8. Test manuel: observer courbes en temps réel

### Phase 1 - Étape 3: Calibration

9. `src/sensors/eda_processor.py`
10. `src/sensors/emg_processor.py`
11. `src/sensors/acc_processor.py`
12. `src/sensors/fsr_processor.py`
13. `src/sensors/ppg_processor.py`
14. `src/sensors/hrv_analyzer.py`
15. `src/calibration.py` (CalibrationManager)
16. Tests unitaires pour chaque processor
17. `tests/test_calibration.py`
18. Test manuel: vérifier baseline JSON cohérent

### Phase 1 - Étape 4: Cognitive Load

19. `src/cognitive_load.py` (CognitiveLoadAnalyzer)
20. `tests/test_cognitive_load.py`
21. Test manuel: observer CCI monter pendant calcul mental

### Phase 1 - Étape 5: Reporting

22. `src/report/reporter.py` (SessionReporter)
23. `src/report/templates/report.html`
24. `tests/test_reporter.py`
25. Test manuel: générer rapport après session test

### Phase 1 - Intégration finale

26. `src/app.py` (IQOverloadApp, orchestration complète)
27. `tests/test_app.py`
28. Test manuel: session complète de bout en bout
29. Validation globale Phase 1

---

## 10. Critères de validation finale Phase 1

### 10.1 Tests automatisés
- [ ] Tous les tests pytest passent (`pytest tests/ -v`)
- [ ] Couverture de code > 80% sur modules critiques
- [ ] Aucun warning pytest

### 10.2 Tests manuels
- [ ] Connexion stable 10 minutes sans crash
- [ ] 5 courbes affichées simultanément, fluides
- [ ] Calibration donne valeurs cohérentes (répétable sur 3 essais)
- [ ] CCI réagit quand on fait calcul mental (augmente visiblement)
- [ ] Point de bascule détecté quand stress prolongé
- [ ] Rapport HTML généré sans erreur
- [ ] Rapport contient tous les graphiques
- [ ] Données CSV lisibles et complètes

### 10.3 Qualité du code
- [ ] PEP8 respecté (`flake8 src/`)
- [ ] Type hints présents partout
- [ ] Docstrings sur toutes fonctions publiques
- [ ] Aucune fonction > 40 lignes
- [ ] Pas de code dupliqué

### 10.4 Documentation
- [ ] README.md avec instructions installation/lancement
- [ ] SPECS.md à jour
- [ ] Commentaires dans le code pour parties complexes

---

**FIN DE SPECS.MD - Phase 1**

Ce document constitue la spécification technique complète pour implémenter la Phase 1 du projet IQ Overload. Toute ambiguïté doit être clarifiée avant l'implémentation.