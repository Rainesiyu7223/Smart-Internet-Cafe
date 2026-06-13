import time
from smbus2 import SMBus

GROVEPI_ADDRESS = 0x04
ANALOG_READ_CMD = 3

def read_rotary_raw(port):
    """
    Reads the raw analog integer value from the rotary angle sensor.
    :param port: int, The analog port number (e.g., 1 for A1)
    :return: int, Raw analog value between 0 and 1023
    """
    try:
        with SMBus(1) as bus:
            cmd_data = [ANALOG_READ_CMD, port, 0, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            time.sleep(0.05)
            
            # Read back the 3-byte block from GrovePi ADC
            bus.read_i2c_block_data(GROVEPI_ADDRESS, 1, 1)
            time.sleep(0.05)
            reply = bus.read_i2c_block_data(GROVEPI_ADDRESS, 1, 3)
            
            # Reconstruct the 10-bit analog integer (0 - 1023)
            raw_value = (reply[1] * 256) + reply[2]
            return raw_value
            
    except Exception as e:
        print(f"[Sensor Error] Failed to read Rotary Raw from Port A{port}: {e}")
        return 0
