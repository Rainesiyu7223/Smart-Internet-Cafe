import time
import json

# Import custom modular drivers
from sensors.tempHumid_sensor import read_temperature_humidity
from sensors.sound_sensor import setup_sound_pin, read_sound_level
from actuators.buzzer_actuator import setup_buzzer_pin, trigger_buzzer

# ==================== HARDWARE CONFIGURATION CENTER ====================
CLIENT_ID = "pi_node_seat_A1"
MQTT_TOPIC = "cybercafe/seats/A1"

DHT_PIN = 4          # DHT sensor connected to Digital Port D4
DHT_TYPE = 0         # 0 for Blue DHT11
SOUND_PIN = 0        # Sound sensor connected to Analog Port A0
BUZZER_PIN = 3       # Buzzer v1.2 connected to Digital Port D3
PIR_PIN = 8          # Motion sensor connected to Digital Port D8
ROTARY_PIN = 1       # Rotary sensor connected to Analog Port A1

# Edge Intelligence Thresholds
NOISE_THRESHOLD = 300  # Trigger alert if raw sound value exceeds this
# =======================================================================

def collect_all_sensor_data():
    """Invokes individual sensors and formats telemetry into a dictionary."""
    temp, hum = read_temperature_humidity(port=DHT_PIN, sensor_type=DHT_TYPE)
    sound_value = read_sound_level(port=SOUND_PIN)
    
    payload = {
        "client_id": CLIENT_ID,
        "timestamp": int(time.time()),
        "environment": {
            "temperature": temp if temp is not None else 0.0,
            "humidity": hum if hum is not None else 0.0,
            "noise_level": sound_value if sound_value is not None else 0
        },
        "seat_interact": {
            "motion_detected": False,
            "user_target_temp": 25.0
        },
        "local_actuators": {
            "fan_status": "OFF",
            "buzzer_active": False,   # Will be updated dynamically in main loop
            "lcd_alert": "Normal"
        }
    }
    return payload

def main():
    print("==================================================")
    print("Smart Cybercafe IoT Edge Node Core Starting...")
    print("Initializing hardware components...")
    
    # Initialize hardware registers
    setup_sound_pin(port=SOUND_PIN)
    setup_buzzer_pin(port=BUZZER_PIN)
    
    print("\nInitialization sequence complete. Entering tracking loop.")
    print("==================================================\n")
    
    while True:
        # Step 1: Gather integrated telemetry data
        telemetry_dict = collect_all_sensor_data()
        current_noise = telemetry_dict["environment"]["noise_level"]
        
        # Step 2: Edge Local Loop Decision Block (Close-loop control)
        if current_noise > NOISE_THRESHOLD:
            print(f"[ALERT] Noise level ({current_noise}) exceeded threshold ({NOISE_THRESHOLD})!")
            
            # Update the actuator status inside our telemetry package before serialization
            telemetry_dict["local_actuators"]["buzzer_active"] = True
            telemetry_dict["local_actuators"]["lcd_alert"] = "Noise Warning"
            
            # Execute hardware action (Beep for 0.3 seconds)
            trigger_buzzer(port=BUZZER_PIN, duration=0.3)
        else:
            telemetry_dict["local_actuators"]["buzzer_active"] = False
            telemetry_dict["local_actuators"]["lcd_alert"] = "Normal"
        
        # Step 3: Serialize Python dictionary to standard JSON String
        json_payload = json.dumps(telemetry_dict, indent=2)
        
        # Step 4: Local terminal output verification
        print("[LOCAL VERIFICATION] Serialized Payload:")
        print(json_payload)
        print("-" * 50)
        
        # Sampling rate throttle
        time.sleep(1.5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[SYS] KeyboardInterrupt captured. Exiting safely.")
