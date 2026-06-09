import time
import struct
import math
from smbus2 import SMBus

GROVEPI_ADDRESS = 0x04
DHT_CMD = 40

def read_temperature_humidity(port, sensor_type=0):
    """
    Read DHT sensor data from specified digital port via I2C.
    
    :param port: int, digital port number (e.g., 4 for D4)
    :param sensor_type: int, 0 for DHT11, 1 for DHT22/AM2302
    :return: tuple (temperature, humidity), returns (None, None) if read fails
    """
    try:
        with SMBus(1) as bus:
            cmd_data = [DHT_CMD, port, sensor_type, 0]
            bus.write_i2c_block_data(GROVEPI_ADDRESS, 1, cmd_data)
            
            time.sleep(0.6)
            
            bus.read_i2c_block_data(GROVEPI_ADDRESS, 1, 1)
            time.sleep(0.1)
            reply = bus.read_i2c_block_data(GROVEPI_ADDRESS, 1, 9)
            
            temp_bytes = bytes(reply[1:5])
            hum_bytes = bytes(reply[5:9])
            
            temperature = struct.unpack('f', temp_bytes)[0]
            humidity = struct.unpack('f', hum_bytes)[0]
            
            if math.isnan(temperature) or math.isnan(humidity) or (temperature == 0 and humidity == 0):
                return None, None
            
            if temperature > 100 and humidity < 50:
                temperature, humidity = humidity, temperature
                
            return round(temperature, 1), round(humidity, 1)

    except Exception as e:
        print(f"[Sensor Error] Failed to read DHT from Port D{port}: {e}")
        return None, None
