import time
from smbus2 import SMBus

GROVEPI_ADDRESS = 0x04
DIGITAL_WRITE_CMD = 2
PIN_MODE_CMD = 5
OUTPUT_MODE = 1

def setup_led_pin(port):
    """Configure the GrovePi digital pin mode to OUTPUT for the LED."""
    try:
        with SMBus(1) as bus:
            cmd_data = [PIN_MODE_CMD, port, OUTPUT_MODE, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            time.sleep(0.1)
            print(f"Successfully configured Digital Port D{port} as OUTPUT for LED.")
    except Exception as e:
        print(f"Failed to initialize led pin mode on Port D{port}: {e}")

def set_led_status(port, turn_on=False):
    """
    Control LED status, explicitly enforcing OUTPUT mode to ensure hardware execution.
    """
    try:
        with SMBus(1) as bus:
            
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, [PIN_MODE_CMD, port, OUTPUT_MODE, 0])
            time.sleep(0.02) 
            
            val = 1 if turn_on else 0
            cmd_data = [DIGITAL_WRITE_CMD, port, val, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
    except Exception as e:
        print(f"[Actuator Error] Failed to control LED on Port D{port}: {e}")
