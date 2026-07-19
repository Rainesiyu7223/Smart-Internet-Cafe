import time
from smbus2 import SMBus

GROVEPI_ADDRESS = 0x04
ANALOG_READ_CMD = 3

def read_light_level(port):
    """
    Read light sensor level from specified analog port (e.g., 1 for A1).
    :param port: int, analog port number
    :return: int, raw light intensity value (0 - 1023), returns None if read fails
    """
    try:
        with SMBus(1) as bus:
            # Send simulated read instructions
            cmd_data = [ANALOG_READ_CMD, port, 0, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            
            time.sleep(0.05)  
            
            # Read the returned data from GrovePi (the first byte is the flag, the second and third bytes are the high and low bits of the 10-bit ADC)
            
            reply = bus.read_i2c_block_data(GROVEPI_ADDRESS, 1, 4)
            
            # Concatenate integer data according to GrovePi's native protocol
            raw_value = (reply[1] << 8) + reply[2]
            return raw_value
            
    except Exception as e:
        print(f"[Sensor Error] Failed to read Light Sensor from Port A{port}: {e}")
        return None
