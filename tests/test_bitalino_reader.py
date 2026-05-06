"""Unit tests for bitalino_reader module."""

import pytest
import sys
from pathlib import Path
import queue
import time
import threading
import types
from unittest.mock import Mock, patch

# Add src directory to path so we can import bitalino_reader
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class FakeSignalsDev:
    """Fake plux.SignalsDev class for unit tests."""

    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def __init__(self, address=None):
        self.address = address

    def getBattery(self):
        return 75

    def start(self, *args, **kwargs):
        pass

    def stop(self):
        pass

    def close(self):
        pass

    def loop(self):
        pass


fake_plux = types.SimpleNamespace(SignalsDev=FakeSignalsDev)
sys.modules["plux"] = fake_plux

from bitalino_reader import BITalinoReader, RawFrame


def make_reader(address="98:D3:71:FE:4F:90", sampling_rate=100,
                active_ports=None, resolution=16, data_queue=None):
    """Helper to create a real BITalinoReader instance with mocked plux __new__."""
    if active_ports is None:
        active_ports = [1, 2, 3, 4, 6]
    if data_queue is None:
        data_queue = queue.Queue()

    # Bypass BITalinoReader.__new__ (which calls plux C extension)
    # and return a plain BITalinoReader instance instead
    with patch.object(BITalinoReader, '__new__',
                      lambda cls, *a, **kw: object.__new__(cls)):
        return BITalinoReader(
            address=address,
            sampling_rate=sampling_rate,
            active_ports=active_ports,
            resolution=resolution,
            data_queue=data_queue
        )


class TestRawFrame:
    """Tests for RawFrame dataclass."""

    def test_rawframe_creation(self):
        """Test RawFrame can be created with valid data."""
        frame = RawFrame(
            timestamp=1234567890.123,
            sequence=42,
            channels=[100, 200, 300, 400, 500, 600]
        )

        assert frame.timestamp == 1234567890.123
        assert frame.sequence == 42
        assert frame.channels == [100, 200, 300, 400, 500, 600]

    def test_rawframe_attributes_accessible(self):
        """Test RawFrame attributes are accessible."""
        frame = RawFrame(
            timestamp=time.time(),
            sequence=0,
            channels=[510, 512, 515, 10, 0, 520]
        )

        assert isinstance(frame.timestamp, float)
        assert isinstance(frame.sequence, int)
        assert isinstance(frame.channels, list)
        assert len(frame.channels) == 6

    def test_rawframe_with_different_channel_counts(self):
        """Test RawFrame works with different channel counts."""
        frame_5 = RawFrame(
            timestamp=time.time(),
            sequence=1,
            channels=[100, 200, 300, 400, 500]
        )
        assert len(frame_5.channels) == 5

        frame_6 = RawFrame(
            timestamp=time.time(),
            sequence=2,
            channels=[100, 200, 300, 400, 500, 600]
        )
        assert len(frame_6.channels) == 6


class TestBITalinoReaderInitialization:
    """Tests for BITalinoReader initialization."""

    @pytest.fixture
    def data_queue(self):
        return queue.Queue()

    def test_bitalino_reader_init(self, data_queue):
        """Test BITalinoReader initializes with correct attributes."""
        reader = make_reader(data_queue=data_queue)

        assert reader.address == "98:D3:71:FE:4F:90"
        assert reader.sampling_rate == 100
        assert reader.active_ports == [1, 2, 3, 4, 6]
        assert reader.resolution == 16
        assert reader.data_queue is data_queue
        assert isinstance(reader.stop_event, threading.Event)
        assert reader.is_connected is False
        assert reader.reconnection_attempts == 0
        assert reader._start_time == 0.0
        assert reader._acquisition_thread is None

    def test_bitalino_reader_different_configs(self, data_queue):
        """Test BITalinoReader with different configurations."""
        reader = make_reader(
            address="00:11:22:33:44:55",
            sampling_rate=1000,
            active_ports=[1, 2],
            resolution=10,
            data_queue=data_queue
        )

        assert reader.address == "00:11:22:33:44:55"
        assert reader.sampling_rate == 1000
        assert reader.active_ports == [1, 2]
        assert reader.resolution == 10


class TestBITalinoReaderConnection:
    """Tests for connection management."""

    @pytest.fixture
    def reader(self):
        return make_reader()

    def test_connect_success(self, reader):
        """Test successful connection."""
        reader.getBattery = Mock(return_value=75)

        with patch('bitalino_reader.plux.SignalsDev.__init__', return_value=None):
            result = reader.connect()

        assert result is True
        assert reader.is_connected is True
        assert reader.reconnection_attempts == 0
        reader.getBattery.assert_called_once()

    def test_connect_failure(self, reader):
        """Test connection failure handling."""
        reader.getBattery = Mock(side_effect=Exception("Connection error"))

        with patch('bitalino_reader.plux.SignalsDev.__init__', return_value=None):
            result = reader.connect()

        assert result is False
        assert reader.is_connected is False

    def test_get_battery_level_success(self, reader):
        """Test get_battery_level returns correct value."""
        reader.getBattery = Mock(return_value=85.7)

        level = reader.get_battery_level()

        assert level == 85
        assert isinstance(level, int)

    def test_get_battery_level_failure(self, reader):
        """Test get_battery_level handles errors."""
        reader.getBattery = Mock(side_effect=Exception("Battery read error"))

        level = reader.get_battery_level()

        assert level == 0


class TestBITalinoReaderAcquisition:
    """Tests for data acquisition."""

    @pytest.fixture
    def reader(self):
        reader = make_reader()
        reader.is_connected = True
        reader.start = Mock()
        reader.stop = Mock()
        reader.close = Mock()
        reader.loop = Mock()
        return reader

    def test_start_acquisition_not_connected(self):
        """Test start_acquisition raises error when not connected."""
        reader = make_reader()

        with pytest.raises(RuntimeError, match="device not connected"):
            reader.start_acquisition()

    def test_start_acquisition_spawns_thread(self, reader):
        """Test start_acquisition spawns acquisition thread."""
        def fake_loop():
            while not reader.stop_event.is_set():
                time.sleep(0.01)

        reader.loop = Mock(side_effect=fake_loop)

        reader.start_acquisition()

        assert reader._acquisition_thread is not None
        assert reader._acquisition_thread.is_alive()
        assert reader._acquisition_thread.daemon is True
        assert reader._acquisition_thread.name == "BITalinoAcquisition"
        assert reader.stop_event.is_set() is False

        reader.stop_event.set()
        reader._acquisition_thread.join(timeout=1.0)

    def test_stop_acquisition(self, reader):
        """Test stop_acquisition stops thread and device."""
        reader.start_acquisition()
        time.sleep(0.1)

        reader.stop_acquisition()

        assert reader.stop_event.is_set() is True
        assert reader.is_connected is False
        reader.stop.assert_called_once()
        reader.close.assert_called_once()


class TestOnRawFrameCallback:
    """Tests for onRawFrame callback."""

    @pytest.fixture
    def reader_and_queue(self):
        data_queue = queue.Queue(maxsize=10)
        reader = make_reader(data_queue=data_queue)
        return reader, data_queue

    def test_onRawFrame_puts_data_in_queue(self, reader_and_queue):
        """Test onRawFrame creates RawFrame and puts in queue."""
        reader, data_queue = reader_and_queue

        test_data = [100, 200, 300, 400, 500]
        result = reader.onRawFrame(42, test_data)

        assert result is False
        assert not data_queue.empty()
        frame = data_queue.get(timeout=1.0)

        assert isinstance(frame, RawFrame)
        assert frame.sequence == 42
        assert frame.channels == test_data
        assert isinstance(frame.timestamp, float)

    def test_onRawFrame_multiple_frames(self, reader_and_queue):
        """Test onRawFrame handles multiple frames."""
        reader, data_queue = reader_and_queue

        for seq in range(5):
            data = [seq * 10 + i for i in range(5)]
            result = reader.onRawFrame(seq, data)
            assert result is False

        assert data_queue.qsize() == 5

        frames = []
        while not data_queue.empty():
            frames.append(data_queue.get())

        assert len(frames) == 5
        for i, frame in enumerate(frames):
            assert frame.sequence == i

    def test_onRawFrame_queue_full_handling(self, reader_and_queue):
        """Test onRawFrame handles full queue gracefully."""
        reader, data_queue = reader_and_queue

        for i in range(10):
            data_queue.put(RawFrame(time.time(), i, [i] * 5))

        assert data_queue.full()

        result = reader.onRawFrame(999, [999] * 5)

        assert result is False


class TestStopEvent:
    """Tests for stop_event functionality."""

    @pytest.fixture
    def reader(self):
        return make_reader()

    def test_stop_event_stops_onRawFrame(self, reader):
        """Test onRawFrame returns True when stop_event is set."""
        result = reader.onRawFrame(0, [100] * 5)
        assert result is False

        reader.stop_event.set()

        result = reader.onRawFrame(1, [100] * 5)
        assert result is True

    def test_stop_event_initially_clear(self, reader):
        """Test stop_event is initially cleared."""
        assert reader.stop_event.is_set() is False

    def test_stop_event_set_by_stop_acquisition(self, reader):
        """Test stop_acquisition sets stop_event."""
        reader.is_connected = True
        reader.stop = Mock()
        reader.close = Mock()

        reader.stop_acquisition()

        assert reader.stop_event.is_set() is True


class TestReconnectionLogic:
    """Tests for reconnection logic."""

    @pytest.fixture
    def reader(self):
        reader = make_reader()
        reader.close = Mock()
        return reader

    @patch('bitalino_reader.time.sleep')
    @patch('bitalino_reader.plux.SignalsDev.__init__', return_value=None)
    def test_reconnect_success_on_first_attempt(self, mock_plux_init, mock_sleep, reader):
        """Test successful reconnection on first attempt."""
        reader.getBattery = Mock(return_value=50)

        result = reader._reconnect()

        assert result is True
        assert reader.reconnection_attempts == 1
        assert reader.is_connected is True
        mock_sleep.assert_called_once()

    @patch('bitalino_reader.time.sleep')
    @patch('bitalino_reader.plux.SignalsDev.__init__', return_value=None)
    def test_reconnect_fails_after_max_attempts(self, mock_plux_init, mock_sleep, reader):
        """Test reconnection fails after max attempts."""
        reader.getBattery = Mock(side_effect=Exception("Connection failed"))

        result = reader._reconnect()

        assert result is False
        assert reader.reconnection_attempts == 3
        assert mock_sleep.call_count == 3

    @patch('bitalino_reader.time.sleep')
    @patch('bitalino_reader.plux.SignalsDev.__init__', return_value=None)
    def test_reconnect_success_on_second_attempt(self, mock_plux_init, mock_sleep, reader):
        """Test successful reconnection on second attempt."""
        reader.getBattery = Mock(side_effect=[Exception("Failed"), 50])

        result = reader._reconnect()

        assert result is True
        assert reader.reconnection_attempts == 2
        assert mock_sleep.call_count == 2


class TestAcquisitionLoop:
    """Tests for acquisition loop behavior."""

    @pytest.fixture
    def reader(self):
        reader = make_reader()
        reader.loop = Mock()
        return reader

    def test_acquisition_loop_calls_plux_loop(self, reader):
        """Test _acquisition_loop calls plux loop."""
        reader._acquisition_loop()

        reader.loop.assert_called_once()

    def test_acquisition_loop_handles_exception(self, reader):
        """Test _acquisition_loop handles exceptions gracefully."""
        reader.loop = Mock(side_effect=Exception("Communication error"))
        reader.stop_event.set()

        reader._acquisition_loop()

        assert reader.loop.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])