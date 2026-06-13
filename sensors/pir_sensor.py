import time
from smbus2 import SMBus

GROVEPI_ADDRESS = 0x04
DIGITAL_READ_CMD = 1
PIN_MODE_CMD = 5
INPUT_MODE = 0

def setup_pir_pin(port):
    """Configure the GrovePi digital pin mode to INPUT for the PIR sensor."""
    try:
        with SMBus(1) as bus:
            cmd_data = [PIN_MODE_CMD, port, INPUT_MODE, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            time.sleep(0.1)
            print(f"Successfully configured Digital Port D{port} as INPUT for PIR.")
    except Exception as e:
        print(f"Failed to initialize PIR pin mode on Port D{port}: {e}")

def read_pir_motion(port):
    """
    Reads the PIR motion sensor state from a digital port.
    :param port: int, The digital port number (e.g., 8 for D8)
    :return: bool, True if motion is detected, False otherwise
    """
    try:
        with SMBus(1) as bus:
            cmd_data = [DIGITAL_READ_CMD, port, 0, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            time.sleep(0.05)
            
            # Read back 1 byte of response data
            bus.read_i2c_block_data(GROVEPI_ADDRESS, 1, 1)
            time.sleep(0.05)
            reply = bus.read_i2c_block_data(GROVEPI_ADDRESS, 1, 1)
            
            # 1 means motion detected, 0 means no motion
            return True if reply[0] == 1 else False
            
    except Exception as e:
        print(f"[Sensor Error] Failed to read PIR from Port D{port}: {e}")
        return False
