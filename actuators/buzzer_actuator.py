import time
from smbus2 import SMBus

GROVEPI_ADDRESS = 0x04
DIGITAL_WRITE_CMD = 2
PIN_MODE_CMD = 5
OUTPUT_MODE = 1

def setup_buzzer_pin(port):
    """Configure the GrovePi digital pin mode to OUTPUT for the buzzer."""
    try:
        with SMBus(1) as bus:
            cmd_data = [PIN_MODE_CMD, port, OUTPUT_MODE, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            time.sleep(0.1)
            print(f"Successfully configured Digital Port D{port} as OUTPUT for Buzzer.")
    except Exception as e:
        print(f"Failed to initialize buzzer pin mode on Port D{port}: {e}")

def trigger_buzzer(port, duration=0.5):
    """
    Triggers the buzzer to beep for a specific duration.
    :param port: int, The digital port number (e.g., 3 for D3)
    :param duration: float, Time in seconds for the buzzer to stay active
    """
    try:
        with SMBus(1) as bus:
            # Phase 1: Turn Buzzer ON (High level = 1)
            cmd_data = [DIGITAL_WRITE_CMD, port, 1, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            
            # Keep it beeping
            time.sleep(duration)
            
            # Phase 2: Turn Buzzer OFF (Low level = 0)
            cmd_data = [DIGITAL_WRITE_CMD, port, 0, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            
    except Exception as e:
        print(f"[Actuator Error] Failed to control Buzzer on Port D{port}: {e}")
