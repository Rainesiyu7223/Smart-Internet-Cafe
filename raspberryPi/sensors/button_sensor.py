import time
from smbus2 import SMBus

GROVEPI_ADDRESS = 0x04
DIGITAL_READ_CMD = 1
PIN_MODE_CMD = 5
INPUT_MODE = 0

def setup_button_pin(port):
    """Configure the GrovePi digital pin mode to INPUT for the button."""
    try:
        with SMBus(1) as bus:
            cmd_data = [PIN_MODE_CMD, port, INPUT_MODE, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            time.sleep(0.1)
            print(f"Successfully configured Digital Port D{port} as INPUT for Button.")
    except Exception as e:
        print(f"Failed to initialize button pin mode on Port D{port}: {e}")

def read_button_status(port):
    """
    Read button status from specified digital port (e.g., 2 for D2).
    :param port: int, digital port number
    :return: bool, True if pressed (High), False otherwise
    """
    try:
        with SMBus(1) as bus:
            cmd_data = [DIGITAL_READ_CMD, port, 0, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            
            
            
            reply = bus.read_i2c_block_data(GROVEPI_ADDRESS, 1, 2)
            # reply[1] usually returns 1 (pressed) or 0 (not pressed)
            
            return True if reply[1] == 1 else False
            
    except Exception as e:
        print(f"[Sensor Error] Failed to read Button from Port D{port}: {e}")
        return False
