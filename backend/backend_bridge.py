import time
import json
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# ==================== Backend & Database Configuration ====================
# The Raspberry Pi's actual LAN IP address
#MQTT_BROKER = "192.168.0.165"  

MQTT_BROKER = "172.20.10.13"  
MQTT_PORT = 1883
MQTT_TOPIC = "cybercafe/seat_A1"

INFLUX_URL = "http://localhost:8086" 
#INFLUX_TOKEN = "my-super-secret-auth-token" 
INFLUX_TOKEN = "apiv3_kHXnnT92Gd5kGVoZSEUJ16UdgAPY80G6gnXTVneCtp8xaX2qpcAdQi6UBcPz-0HKi5swWffTjVIWXXlqPsyHuA" 
#new:token = "my-super-secret-token"
INFLUX_ORG = "cybercafe_org"
INFLUX_BUCKET = "cybercafe_data"
# =========================================================

# Initialize client
db_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = db_client.write_api(write_options=SYNCHRONOUS)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[Backend] Successfully connected to Pi MQTT Broker ({MQTT_BROKER})")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"[Backend] Connection failed with code {rc}")

def on_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode('utf-8')
        data = json.loads(payload_str)
        print(f"[📥 MQTT Received] Data fetched from {data['client_id']}")
        
<<<<<<< Updated upstream
        # Construct time-series data points
=======
        
>>>>>>> Stashed changes
        point = Point("cybercafe_telemetry") \
            .tag("client_id", data["client_id"]) \
            .field("temperature", float(data["environment"]["temperature"])) \
            .field("humidity", float(data["environment"]["humidity"])) \
            .field("noise_level", int(data["environment"]["noise_level"])) \
            .field("motion_detected", int(1 if data["seat_interact"]["motion_detected"] else 0)) \
            .time(data["timestamp"])
        
<<<<<<< Updated upstream
=======
        
>>>>>>> Stashed changes
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        print(f"[💾 DB Saved] Data committed successfully!")
        
    except Exception as e:
        print(f"[Error] Save failed: {e}")

def main():
    backend_client = mqtt.Client(client_id="mac_backend_server")
    backend_client.on_connect = on_connect
    backend_client.on_message = on_message
    backend_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    backend_client.loop_forever()

if __name__ == "__main__":
    main()