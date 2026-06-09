import time
import json

# Import custom modular sensor drivers
from sensors.tempHumid_sensor import read_temperature_humidity
from sensors.sound_sensor import setup_sound_pin, read_sound_level

# ==================== HARDWARE CONFIGURATION CENTER ====================
CLIENT_ID = "pi_node_seat_A1"
MQTT_TOPIC = "cybercafe/seats/A1"

DHT_PIN = 4          # DHT sensor connected to Digital Port D4
DHT_TYPE = 0         # 0 for Blue DHT11, 1 for White DHT22
SOUND_PIN = 0        # Sound sensor connected to Analog Port A0
PIR_PIN = 8          # Motion sensor connected to Digital Port D8 (Future use)
ROTARY_PIN = 1       # Rotary sensor connected to Analog Port A1 (Future use)
# =======================================================================

def collect_all_sensor_data():
    """
    Invokes individual sensor modules, handles hardware exception guardrails,
    and structures the multi-modal telemetry into a standardized dictionary.
    """
    # 1. Fetch DHT Telemetry
    temp, hum = read_temperature_humidity(port=DHT_PIN, sensor_type=DHT_TYPE)
    
    # 2. Fetch Sound Telemetry
    sound_value = read_sound_level(port=SOUND_PIN)
    
    # 3. Construct Structured Payload Schema
    payload = {
        "client_id": CLIENT_ID,
        "timestamp": int(time.time()),
        "environment": {
            "temperature": temp if temp is not None else 0.0,
            "humidity": hum if hum is not None else 0.0,
            "noise_level": sound_value if sound_value is not None else 0
        },
        "seat_interact": {
            "motion_detected": False,   # Placeholder for Day 2 integration
            "user_target_temp": 25.0    # Placeholder for Day 2 integration
        },
        "local_actuators": {
            "fan_status": "OFF",        # Placeholder for Day 3 actuators loop
            "lcd_alert": "Normal"       # Placeholder for Day 3 actuators loop
        }
    }
    return payload

def main():
    print("==================================================")
    print("Smart Cybercafe IoT Edge Node Core Starting...")
    print("Initializing hardware components...")
    
    # Initialize necessary hardware registers
    setup_sound_pin(port=SOUND_PIN)
    
    print("\nInitialization sequence complete. Entering tracking loop.")
    print("Press Ctrl+C to terminate application safely.")
    print("==================================================\n")
    
    while True:
        # Step 1: Gather integrated dictionary structure
        telemetry_dict = collect_all_sensor_data()
        
        # Step 2: Serialize Python dictionary to standard JSON String format
        json_payload = json.dumps(telemetry_dict, indent=2)
        
        # Step 3: Local terminal output verification
        print(f"[LOCAL VERIFICATION] Serialized JSON Payload:")
        print(json_payload)
        print("-" * 50)
        
        # Step 4: MQTT Transmission Bridge (Uncomment this section tomorrow when Broker is active)
        # if mqtt_client and mqtt_client.is_connected():
        #     mqtt_client.publish(MQTT_TOPIC, json_payload, qos=1)
        #     print(f"[MQTT] Packet transmitted successfully to topic: {MQTT_TOPIC}")
        
        # Local loop sampling throttle interval
        time.sleep(2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[SYS] KeyboardInterrupt captured. Cleaning up registers and exiting safely.")
