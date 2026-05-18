# src/sensors/fsr_processor.py
"""FSR (Force Sensitive Resistor) signal processor.

Processes force/pressure sensor data to detect button presses and sustained grip.
FSR indicates stress through hand clenching and button pressing behavior.
"""

import config


class FSRProcessor:
    """Process FSR (Force Sensitive Resistor) signal from port 4.
    
    Detects button press events and sustained pressure indicative of stress.
    FSR values increase with applied force. Rising edge detection captures
    discrete press events for user interaction challenges.
    """

    def __init__(self, baseline_value: float, threshold_press: float) -> None:
        """Initialize FSR processor with baseline and press threshold.
        
        Args:
            baseline_value: Baseline FSR value with no pressure applied.
                           Typically in range 5-20 ADC units.
            threshold_press: ADC value above which FSR is considered pressed.
                            Usually baseline + 20 ADC units.
        """
        self.baseline_value = baseline_value
        self.threshold_press = threshold_press
        self._last_state: bool = False  # False = not pressed, True = pressed

    def process_raw(self, raw_value: int) -> float:
        """Convert raw ADC value to pressure value.
        
        No filtering applied - FSR response is already low-frequency.
        Directly returns the raw value as pressure magnitude.
        
        Args:
            raw_value: Raw 16-bit ADC value (0-65535).
        
        Returns:
            Pressure value (same as raw input, in ADC units).
        """
        return float(raw_value)

    def is_pressed(self, fsr_value: float) -> bool:
        """Detect if FSR is currently pressed.
        
        Compares current value against threshold. Does not track state
        transitions - purely checks instantaneous pressure level.
        
        Args:
            fsr_value: Current FSR value (from process_raw).
        
        Returns:
            True if fsr_value >= threshold_press, False otherwise.
        """
        return fsr_value >= self.threshold_press

    def detect_press_event(self, fsr_value: float) -> bool:
        """Detect rising edge (new press event).
        
        Identifies transition from not-pressed to pressed state.
        Updates internal state tracker and returns True only on
        transition. Used to detect discrete button presses for
        challenge scoring.
        
        Args:
            fsr_value: Current FSR value (from process_raw).
        
        Returns:
            True on transition from not_pressed to pressed,
            False otherwise (including if already pressed).
        """
        current_state = self.is_pressed(fsr_value)
        press_detected = (not self._last_state) and current_state
        self._last_state = current_state
        
        return press_detected