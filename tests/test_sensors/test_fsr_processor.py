# tests/test_sensors/test_fsr_processor.py
"""Unit tests for FSRProcessor."""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sensors.fsr_processor import FSRProcessor
import config


class TestFSRProcessorInit:
    """Test FSRProcessor initialization."""

    def test_fsr_processor_init(self) -> None:
        """Verify processor initializes with correct parameters."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        assert processor.baseline_value == 10.0
        assert processor.threshold_press == 30.0
        assert processor._last_state is False

    def test_fsr_processor_init_different_values(self) -> None:
        """Verify processor with different baseline/threshold."""
        processor = FSRProcessor(baseline_value=5.0, threshold_press=25.0)
        
        assert processor.baseline_value == 5.0
        assert processor.threshold_press == 25.0
        assert processor._last_state is False

    def test_fsr_processor_init_zero_baseline(self) -> None:
        """Verify processor handles zero baseline."""
        processor = FSRProcessor(baseline_value=0.0, threshold_press=20.0)
        
        assert processor.baseline_value == 0.0
        assert processor.threshold_press == 20.0


class TestProcessRaw:
    """Test raw FSR processing."""

    def test_process_raw_returns_float(self) -> None:
        """Raw value should be converted to float."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        value = processor.process_raw(100)
        
        assert isinstance(value, float)
        assert value == 100.0

    def test_process_raw_zero(self) -> None:
        """Zero pressure should return 0."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        value = processor.process_raw(0)
        
        assert value == 0.0

    def test_process_raw_high_pressure(self) -> None:
        """High pressure should return high value."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        value = processor.process_raw(65535)
        
        assert value == 65535.0

    def test_process_raw_baseline(self) -> None:
        """Baseline value should pass through unchanged."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        value = processor.process_raw(10)
        
        assert value == 10.0

    def test_process_raw_threshold(self) -> None:
        """Threshold value should pass through unchanged."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        value = processor.process_raw(30)
        
        assert value == 30.0

    def test_process_raw_multiple_calls(self) -> None:
        """Multiple calls should each return accurate value."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        value1 = processor.process_raw(15)
        value2 = processor.process_raw(25)
        value3 = processor.process_raw(35)
        
        assert value1 == 15.0
        assert value2 == 25.0
        assert value3 == 35.0


class TestIsPressed:
    """Test press state detection."""

    def test_is_pressed_below_threshold(self) -> None:
        """Value below threshold should return False."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        pressed = processor.is_pressed(20.0)
        
        assert pressed is False

    def test_is_pressed_at_threshold(self) -> None:
        """Value at threshold should return True."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        pressed = processor.is_pressed(30.0)
        
        assert pressed is True

    def test_is_pressed_above_threshold(self) -> None:
        """Value above threshold should return True."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        pressed = processor.is_pressed(40.0)
        
        assert pressed is True

    def test_is_pressed_zero(self) -> None:
        """Zero pressure should return False."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        pressed = processor.is_pressed(0.0)
        
        assert pressed is False

    def test_is_pressed_baseline(self) -> None:
        """Baseline value (no pressure) should return False."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        pressed = processor.is_pressed(10.0)
        
        assert pressed is False

    def test_is_pressed_does_not_modify_state(self) -> None:
        """is_pressed() should not update internal state."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        pressed1 = processor.is_pressed(35.0)
        pressed2 = processor.is_pressed(35.0)
        
        assert pressed1 is True
        assert pressed2 is True
        assert processor._last_state is False  # State unchanged


class TestDetectPressEvent:
    """Test rising edge (press event) detection."""

    def test_detect_press_event_rising_edge(self) -> None:
        """Transition from not-pressed to pressed should detect event."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        # Start: not pressed
        assert processor._last_state is False
        
        # Transition: not-pressed to pressed
        event = processor.detect_press_event(35.0)
        
        assert event is True
        assert processor._last_state is True

    def test_detect_press_event_no_transition(self) -> None:
        """Staying pressed should not detect event."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        # First press
        processor.detect_press_event(35.0)
        assert processor._last_state is True
        
        # Still pressed
        event = processor.detect_press_event(40.0)
        
        assert event is False
        assert processor._last_state is True

    def test_detect_press_event_release(self) -> None:
        """Transition from pressed to not-pressed should not detect event."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        # First press
        processor.detect_press_event(35.0)
        assert processor._last_state is True
        
        # Release (falling edge)
        event = processor.detect_press_event(20.0)
        
        assert event is False  # Only rising edge detected
        assert processor._last_state is False

    def test_detect_press_event_resting_no_press(self) -> None:
        """Staying not-pressed should not detect event."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        # Start: not pressed
        assert processor._last_state is False
        
        # Still not pressed
        event = processor.detect_press_event(15.0)
        
        assert event is False
        assert processor._last_state is False

    def test_detect_press_event_at_threshold(self) -> None:
        """Crossing threshold exactly should detect event."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        # Transition: at threshold value
        event = processor.detect_press_event(30.0)
        
        assert event is True
        assert processor._last_state is True

    def test_detect_press_event_just_below_threshold(self) -> None:
        """Value just below threshold should not detect event."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        event = processor.detect_press_event(29.9)
        
        assert event is False
        assert processor._last_state is False

    def test_detect_press_event_multiple_presses(self) -> None:
        """Multiple discrete presses should be detected correctly."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        # Press 1
        event1 = processor.detect_press_event(35.0)
        assert event1 is True
        
        # Release
        event_release = processor.detect_press_event(15.0)
        assert event_release is False
        
        # Press 2
        event2 = processor.detect_press_event(35.0)
        assert event2 is True
        
        # Another release
        event_release2 = processor.detect_press_event(15.0)
        assert event_release2 is False


class TestIntegration:
    """Integration tests for FSRProcessor."""

    def test_no_pressure_scenario(self) -> None:
        """Test scenario with no pressure applied."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        # Simulate idle: maintain baseline
        for _ in range(5):
            value = processor.process_raw(10)
            pressed = processor.is_pressed(value)
            event = processor.detect_press_event(value)
            
            assert pressed is False
            assert event is False
        
        assert processor._last_state is False

    def test_sustained_pressure_scenario(self) -> None:
        """Test sustained button press."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        # Press button
        value1 = processor.process_raw(35)
        event1 = processor.detect_press_event(value1)
        assert event1 is True  # First detection
        
        # Hold button
        for _ in range(3):
            value = processor.process_raw(38)
            event = processor.detect_press_event(value)
            assert event is False  # Already pressed, no new event

    def test_button_press_release_cycle(self) -> None:
        """Test realistic button press-release cycle."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        # Idle
        assert processor.detect_press_event(12.0) is False
        
        # Press down (increasing pressure)
        assert processor.detect_press_event(25.0) is False  # Still below threshold
        assert processor.detect_press_event(31.0) is True   # Crosses threshold - EVENT!
        
        # Hold
        assert processor.detect_press_event(32.0) is False
        assert processor.detect_press_event(30.5) is False
        
        # Release (decreasing pressure)
        assert processor.detect_press_event(28.0) is False
        
        # Back to idle
        assert processor.detect_press_event(12.0) is False
        assert processor._last_state is False

    def test_rapid_press_bouncing(self) -> None:
        """Test rapid bouncing around threshold."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        # Rapid crossing of threshold
        events = []
        values = [15, 32, 28, 33, 27, 35, 10]  # Bouncy sequence
        
        for val in values:
            event = processor.detect_press_event(float(val))
            events.append(event)
        
        # Trace through state transitions:
        # 15: not pressed, start not-pressed → no event
        # 32: pressed, was not-pressed → PRESS EVENT
        # 28: not pressed, was pressed → no event (falling edge)
        # 33: pressed, was not-pressed → PRESS EVENT (new rising edge!)
        # 27: not pressed, was pressed → no event (falling edge)
        # 35: pressed, was not-pressed → PRESS EVENT (new rising edge!)
        # 10: not pressed, was pressed → no event (falling edge)
        
        assert events[0] is False  # 15: no transition, stays not-pressed
        assert events[1] is True   # 32: rising edge (PRESS)
        assert events[2] is False  # 28: falling edge (release)
        assert events[3] is True   # 33: rising edge again (NEW PRESS)
        assert events[4] is False  # 27: falling edge (release)
        assert events[5] is True   # 35: rising edge again (NEW PRESS)
        assert events[6] is False  # 10: falling edge (release)
    def test_stress_induced_grip(self) -> None:
        """Simulate stress-induced increase in grip pressure."""
        processor = FSRProcessor(baseline_value=10.0, threshold_press=30.0)
        
        # Normal grip pressure (below threshold)
        event1 = processor.detect_press_event(20.0)
        assert event1 is False
        assert processor._last_state is False
        
        # Stress increases grip crossing threshold
        event2 = processor.detect_press_event(32.0)
        assert event2 is True
        assert processor._last_state is True
        
        # Sustained stressed grip
        event3 = processor.detect_press_event(35.0)
        assert event3 is False
        assert processor._last_state is True
        
        # Relaxation when stress resolves
        event4 = processor.detect_press_event(18.0)
        assert event4 is False
        assert processor._last_state is False