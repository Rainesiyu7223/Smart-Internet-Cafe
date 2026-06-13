import time
from smbus2 import SMBus

GROVEPI_ADDRESS = 0x04
ANALOG_READ_CMD = 3
PIN_MODE_CMD = 5
INPUT_MODE = 0 

def setup_sound_pin(port):
    """Configure the GrovePi analog pin mode to INPUT."""
    try:
        with SMBus(1) as bus:
            cmd_data = [PIN_MODE_CMD, port, INPUT_MODE, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            time.sleep(0.1)
            print(f"Successfully configured Analog Port A{port} as INPUT.")
    except Exception as e:
        print(f"Failed to initialize pin mode on Port A{port}: {e}")

def read_sound_level(port):
    """Read the current analog voltage level (0-1023) from the sound sensor."""
    try:
        with SMBus(1) as bus:
            cmd_data = [ANALOG_READ_CMD, port, 0, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            
            time.sleep(0.02)
            
            reply = bus.read_i2c_block_data(GROVEPI_ADDRESS, 1, 3)
            
            val = (reply[1] << 8) + reply[2]
            return val
    except Exception as e:
        print(f"I2C Communication Error on Port A{port}: {e}")
        return None
