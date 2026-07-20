import time
import json
import paho.mqtt.client as mqtt  

# Import custom modular drivers
from sensors.dht_sensor import read_temperature_humidity
from sensors.noise_sensor import setup_sound_pin, read_sound_level
from sensors.pir_sensor import setup_pir_pin, read_pir_motion
from sensors.rotary_sensor import read_rotary_raw
from actuators.buzzer_actuator import setup_buzzer_pin, trigger_buzzer

# ==================== HARDWARE & NETWORK CONFIGURATION ====================
CLIENT_ID = "pi_node_seat_A1"

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "cybercafe/seat_A1"


# Physical pin
SOUND_PIN = 0         # A0
LIGHT_PIN = 1         # A1 
BUTTON_PIN = 2        # D2 
LED_PIN = 3           # D3 
DHT_PIN = 4           # D4
DHT_TYPE = 0          

# thredshold
LIGHT_THRESHOLD = 200  
NOISE_THRESHOLD = 220  

# =======================================================================

def main():
    print("==================================================")
    print("Smart Cybercafe IoT Edge Node Core Starting...")
    print("Initializing hardware components & MQTT Client...")
    

    # 1. Initialize hardware pins and patterns

    setup_sound_pin(port=SOUND_PIN)
    setup_buzzer_pin(port=BUZZER_PIN)
    setup_pir_pin(port=PIR_PIN)
    
    # 2. Initialize the MQTT client
    mqtt_client = mqtt.Client(client_id=CLIENT_ID)
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()  
        print("Successfully connected to local MQTT Broker.")
    except Exception as e:
        print(f"MQTT Connection Failed: {e}")
        return
    
    print("\nInitialization sequence complete. Entering tracking loop.")
    print("==================================================\n")
    

    
    last_lcd_status = ""      

    
    cached_temp, cached_hum = 0.0, 0.0
    cached_light = 500
    cached_noise = 0
    
    # Timestamp anchor
    last_fast_env_time = 0.0      
    last_slow_env_time = 0.0      
    last_mqtt_publish_time = 0.0   

    # Core variable: Used to latch the short-press state during the one-second MQTT reporting period
    period_button_latched = False

    #
    while True:
        current_time = time.time()

        # ---------------- 1. Extreme reading keystrokes & in-cycle state latching ----------------
        # As soon as any key is detected in that second, the variable is locked to True and won't be flushed by any subsequent False
        period_button_latched |= read_button_status(port=BUTTON_PIN)

        # ---------------- 2. Refresh light sensitivity and noise faster (every 2.0 seconds) ----------------
        if current_time - last_fast_env_time >= 2.0:
            light_value = read_light_level(port=LIGHT_PIN)
            sound_value = read_sound_level(port=SOUND_PIN)
            cached_light = light_value if light_value is not None else cached_light
            cached_noise = sound_value if sound_value is not None else cached_noise
            last_fast_env_time = current_time

        # ---------------- 3. Temperature and humidity reading (every 3.0 seconds) ----------------
        if current_time - last_slow_env_time >= 3.0 or last_slow_env_time == 0.0:
            temp, hum = read_temperature_humidity(port=DHT_PIN, sensor_type=DHT_TYPE)
            cached_temp = temp if temp is not None else cached_temp
            cached_hum = hum if hum is not None else cached_hum
            last_slow_env_time = current_time

    
        if cached_light < LIGHT_THRESHOLD:
            set_led_status(port=LED_PIN, turn_on=True)
            led_status_str = "ON"
        else:
            set_led_status(port=LED_PIN, turn_on=False)
            led_status_str = "OFF"
            
        if cached_noise > NOISE_THRESHOLD:
            # Excessive sound: Warning red + Please keep quiet
            lcd_alert_str = "Noise Alert"
            if last_lcd_status != "Noise Alert":
                display_text("Please Be Quiet")
                set_lcd_backlight(255, 0, 0) 
                last_lcd_status = "Noise Alert"
        else:
            # Quiet environment: Healthy green + system normal
            lcd_alert_str = "Normal"
            if last_lcd_status != "Normal":
                display_text("System Normal")
                set_lcd_backlight(0, 255, 0) 
                last_lcd_status = "Normal"
        
        # ---------------- 4. Reporting to the MQTT broker is strictly maintained every 1.0 seconds ----------------
        if current_time - last_mqtt_publish_time >= 1.0:
            telemetry_payload = {
                "client_id": CLIENT_ID,
                "timestamp": int(current_time),
                "environment": {
                    "temperature": cached_temp,
                    "humidity": cached_hum,
                    "noise_level": cached_noise,
                    "light_level": cached_light    
                },
                "seat_interact": {
                    "button_pressed": period_button_latched 
                },
                "local_actuators": {
                    "led_status": led_status_str,   
                    "lcd_alert": lcd_alert_str       
                }
            }
                
            json_output = json.dumps(telemetry_payload, indent=2)
            try:
                mqtt_client.publish(MQTT_TOPIC, json_output, qos=0)
                print(f"[MQTT] Published. Noise: {cached_noise}, Button: {period_button_latched}, LED: {led_status_str}, Display: {lcd_alert_str}")
            except Exception as e:
                print(f"[MQTT Error] Failed to publish: {e}")
            
            print("-" * 50)
            last_mqtt_publish_time = current_time
            
            # Periodic reset: The key latch state is cleared immediately after the data is successfully reported to the MQTT broker
            period_button_latched = False
        
        # ---------------- 5. The system beats out (50ms) ----------------
        time.sleep(0.05)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:

        
        try:
            set_led_status(3, turn_on=False)
            display_text("")
        except Exception:
            pass

        print("\n[SYS] KeyboardInterrupt captured. Exiting safely.")
