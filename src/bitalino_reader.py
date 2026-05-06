from dataclasses import dataclass
from typing import List, Optional
import threading
import queue
import time
import sys
import platform

osDic = {
    "Darwin": f"MacOS/Intel{''.join(platform.python_version().split('.')[:2])}",
    "Linux": "Linux64",
    "Windows": f"Win{platform.architecture()[0][:2]}_{''.join(platform.python_version().split('.')[:2])}",
}
if platform.mac_ver()[0] != "":
    import subprocess
    from os import linesep

    p = subprocess.Popen("sw_vers", stdout=subprocess.PIPE)
    result = p.communicate()[0].decode("utf-8").split(str("\t"))[2].split(linesep)[0]
    if result.startswith("12."):
        print("macOS version is Monterrey!")
        osDic["Darwin"] = "MacOS/Intel310"
        if (
            int(platform.python_version().split(".")[0]) <= 3
            and int(platform.python_version().split(".")[1]) < 10
        ):
            print(f"Python version required is ≥ 3.10. Installed is {platform.python_version()}")
            exit()


import plux
@dataclass
class RawFrame:
    """Raw data frame from BITalino sensor.
    
    Contains a single frame of ADC readings from all active BITalino ports,
    along with timing and sequence information.
    """
    timestamp: float  # Unix timestamp in seconds when frame was acquired
    sequence: int  # Frame sequence number from BITalino device
    channels: List[int]  # Raw ADC values indexed by port number (0-65535)


class BITalinoReader(plux.SignalsDev):
    """BITalino device reader with continuous acquisition support.
    
    Manages connection, acquisition, and reconnection logic for BITalino device.
    Data is acquired in a separate thread and put into a thread-safe queue.
    """
    def __new__(cls, address, sampling_rate, active_ports, resolution, data_queue):
        return plux.SignalsDev.__new__(cls, address)
    def __init__(
        self,
        address: str,
        sampling_rate: int,
        active_ports: List[int],
        resolution: int,
        data_queue: queue.Queue[RawFrame]
    ) -> None:
        """Initialize BITalino reader with configuration.
        
        Args:
            address: MAC address of BITalino device
            sampling_rate: Sampling frequency in Hz
            active_ports: List of active port numbers
            resolution: ADC resolution in bits
            data_queue: Thread-safe queue for output frames
        """
        self.address = address
        self.sampling_rate = sampling_rate
        self.active_ports = active_ports
        self.resolution = resolution
        self.data_queue = data_queue
        self.stop_event = threading.Event()
        self.is_connected = False
        self.reconnection_attempts = 0
        self._start_time: float = 0.0
        self._acquisition_thread: Optional[threading.Thread] = None
    
    def connect(self) -> bool:
        """Establish connection to BITalino device.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # plux.SignalsDev constructor already opens connection
            # Test connection by getting battery level
            plux.SignalsDev.__init__(self.address)
            battery = int(self.getBattery())
            self.is_connected = True
            self.reconnection_attempts = 0
            print(f"✓ Connected to BITalino at {self.address} (Battery: {battery}%)")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            self.is_connected = False
            return False
    
    def start_acquisition(self) -> None:
        """Start continuous data acquisition in a separate thread.
        
        Spawns a background thread that runs the acquisition loop.
        """
        if not self.is_connected:
            raise RuntimeError("Cannot start acquisition: device not connected")
        
        self.stop_event.clear()
        self._start_time = time.time()
        
        # Start BITalino acquisition
        try:
            self.start(self.sampling_rate, self.active_ports, self.resolution)
            print(f"✓ Started acquisition at {self.sampling_rate} Hz")
        except Exception as e:
            print(f"✗ Failed to start acquisition: {e}")
            raise
        
        # Spawn acquisition thread
        self._acquisition_thread = threading.Thread(
            target=self._acquisition_loop,
            name="BITalinoAcquisition",
            daemon=True
        )
        self._acquisition_thread.start()
        print("✓ Acquisition thread started")
    
    def stop_acquisition(self) -> None:
        """Stop acquisition gracefully and close connection.
        
        Sets stop event and waits for acquisition thread to finish.
        """
        print("⏹ Stopping acquisition...")
        self.stop_event.set()
        
        # Wait for thread to finish
        if self._acquisition_thread and self._acquisition_thread.is_alive():
            self._acquisition_thread.join(timeout=2.0)
        
        # Stop device
        try:
            self.stop()
            self.close()
            print("✓ Device stopped and closed")
        except Exception as e:
            print(f"⚠ Error stopping device: {e}")
        
        self.is_connected = False
    
    def get_battery_level(self) -> int:
        """Get current battery level percentage.
        
        Returns:
            Battery level (0-100)
        """
        try:
            level = self.getBattery()
            print(f" level: {level}")
            return int(level)
        except Exception as e:
            print(f"⚠ Failed to get battery level: {e}")
            return 0
    
    def onRawFrame(self, nSeq: int, data: List[int]) -> bool:
        """Callback invoked by plux at each frame.
        
        Creates RawFrame and puts it into the data queue.
        
        Args:
            nSeq: Frame sequence number from device
            data: List of raw ADC values from active ports
            
        Returns:
            True to stop acquisition, False to continue
        """
        try:
            frame = RawFrame(
                timestamp=time.time(),
                sequence=nSeq,
                channels=list(data)
            )
            self.data_queue.put(frame, block=False)
        except queue.Full:
            print(f"⚠ Queue full, dropping frame {nSeq}")
        except Exception as e:
            print(f"⚠ Error in onRawFrame: {e}")
        
        # Return True if stop_event is set
        return self.stop_event.is_set()
    
    def _acquisition_loop(self) -> None:
        """Main acquisition loop running in separate thread.
        
        Calls plux.loop() until stop_event is set or error occurs.
        Handles reconnection on communication errors.
        """
        try:
            # Call plux loop - it will repeatedly call onRawFrame
            # until onRawFrame returns True
            self.loop()
            print("✓ Acquisition loop completed normally")
        except Exception as e:
            print(f"✗ Error in acquisition loop: {e}")
            
            # Attempt reconnection if not intentionally stopped
            if not self.stop_event.is_set():
                print("⟳ Attempting reconnection...")
                if self._reconnect():
                    print("✓ Reconnected successfully, resuming acquisition")
                    # Restart acquisition
                    try:
                        self.start(
                            self.sampling_rate,
                            self.active_ports,
                            self.resolution
                        )
                        self._acquisition_loop()  # Recursive call to resume
                    except Exception as restart_error:
                        print(f"✗ Failed to restart after reconnection: {restart_error}")
                else:
                    print("✗ Reconnection failed, stopping acquisition")
                    self.stop_event.set()
    
    def _reconnect(self) -> bool:
        """Attempt to reconnect to BITalino device.
        
        Returns:
            True if reconnection successful, False after max attempts
        """
        max_attempts = 3  # Will be from config.MAX_RECONNECTION_ATTEMPTS
        reconnection_delay = 2.0  # Will be from config.RECONNECTION_DELAY
        
        while self.reconnection_attempts < max_attempts:
            self.reconnection_attempts += 1
            print(f"⟳ Reconnection attempt {self.reconnection_attempts}/{max_attempts}")
            
            try:
                # Close existing connection
                try:
                    self.close()
                except:
                    pass
                
                # Wait before retry
                time.sleep(reconnection_delay)
                
                
                try:
                    self.getBattery()
                    self.is_connected = True
                    return True
                except Exception as e:
                    print(f"✗ Reconnection attempt {self.reconnection_attempts} failed: {e}")
                    
            except Exception as e:
                print(f"✗ Reconnection attempt {self.reconnection_attempts} failed: {e}")
        
        print(f"✗ Max reconnection attempts ({max_attempts}) reached")
        return False


# Original example class preserved for compatibility
class NewDevice(plux.SignalsDev):
    def __init__(self, address):
        plux.SignalsDev.__init__( address)
        self.duration = 0
        self.frequency = 0

    def onRawFrame(self, nSeq, data):
        if nSeq % 2000 == 0:
            print(nSeq, *data)
        return nSeq > self.duration * self.frequency


def exampleAcquisition(
    address="98:D3:71:FE:4F:90",
    duration=20,
    frequency=1000,
    active_ports=[1, 2, 3, 4, 5, 6],
):
    """Example acquisition using original NewDevice class."""
    device = NewDevice(address)
    device.duration = int(duration)
    device.frequency = int(frequency)
    battery = device.getBattery()
    print(f"\nBattery charging level at {int(battery)}%")
    device.start(device.frequency, active_ports, 16)
    device.loop()
    device.stop()
    device.close()


if __name__ == "__main__":
    exampleAcquisition(*sys.argv[1:])
    