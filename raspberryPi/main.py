import time
import json
import paho.mqtt.client as mqtt  # 导入刚刚安装的库

# Import custom modular drivers
from sensors.dht_sensor import read_temperature_humidity
from sensors.noise_sensor import setup_sound_pin, read_sound_level
from sensors.pir_sensor import setup_pir_pin, read_pir_motion
from sensors.rotary_sensor import read_rotary_raw
from actuators.buzzer_actuator import setup_buzzer_pin, trigger_buzzer

# ==================== HARDWARE & NETWORK CONFIGURATION ====================
CLIENT_ID = "pi_node_seat_A1"
# ⚡ MQTT 配置：localhost 代表连接树莓派本地刚刚建好的 Mosquitto 邮局
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "cybercafe/seat_A1"

<<<<<<< Updated upstream
DHT_PIN = 4          
DHT_TYPE = 0         
SOUND_PIN = 0        
BUZZER_PIN = 3       
PIR_PIN = 8          
ROTARY_PIN = 1       

NOISE_THRESHOLD = 400
=======
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
>>>>>>> Stashed changes
# =======================================================================

def main():
    print("==================================================")
    print("Smart Cybercafe IoT Edge Node Core Starting...")
    print("Initializing hardware components & MQTT Client...")
    
<<<<<<< Updated upstream
    # 1. 初始化硬件
=======
    # 1. Initialize hardware pins and patterns
>>>>>>> Stashed changes
    setup_sound_pin(port=SOUND_PIN)
    setup_buzzer_pin(port=BUZZER_PIN)
    setup_pir_pin(port=PIR_PIN)
    
    # 2. Initialize the MQTT client
    mqtt_client = mqtt.Client(client_id=CLIENT_ID)
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()  # 启动后台线程处理网络通信
        print("Successfully connected to local MQTT Broker.")
    except Exception as e:
        print(f"MQTT Connection Failed: {e}")
        return
    
    print("\nInitialization sequence complete. Entering tracking loop.")
    print("==================================================\n")
    
<<<<<<< Updated upstream
    while True:
        # 🛡️ 强行每轮重置蜂鸣器防止死锁
        try:
            from smbus2 import SMBus
            with SMBus(1) as bus:
                bus.write_i2c_block_data(0x04, 1, [2, BUZZER_PIN, 0, 0])
        except Exception:
            pass

        # Step 1: Telemetry gathering
        is_occupied = read_pir_motion(port=PIR_PIN)
        rotary_raw = read_rotary_raw(port=ROTARY_PIN)
        sound_value = read_sound_level(port=SOUND_PIN)
        temp, hum = read_temperature_humidity(port=DHT_PIN, sensor_type=DHT_TYPE)
        
        if sound_value is None:
            current_noise = 0
        else:
            current_noise = sound_value
        
        # Step 2: Construct full-dimensional JSON telemetry payload
        telemetry_payload = {
            "client_id": CLIENT_ID,
            "timestamp": int(time.time()),
            "environment": {
                "temperature": temp if temp is not None else 0.0,
                "humidity": hum if hum is not None else 0.0,
                "noise_level": current_noise
            },
            "seat_interact": {
                "motion_detected": is_occupied,
                "rotary_raw_value": rotary_raw
            },
            "local_actuators": {
                "fan_status": "OFF",
                "buzzer_active": False,
                "lcd_alert": "Normal"
            }
        }
        
        # Step 3: Context-Aware Decision Block
        if is_occupied and current_noise > NOISE_THRESHOLD:
            print(f"[ALERT] Noise level ({current_noise}) exceeded threshold!")
            telemetry_payload["local_actuators"]["buzzer_active"] = True
            telemetry_payload["local_actuators"]["lcd_alert"] = "Noise Warning"
            trigger_buzzer(port=BUZZER_PIN, duration=0.1)
            time.sleep(0.5)
        elif not is_occupied:
            telemetry_payload["local_actuators"]["lcd_alert"] = "Seat Vacant"
        else:
            telemetry_payload["local_actuators"]["lcd_alert"] = "Normal"
            
        # Step 4: Serialize to standard JSON String
        json_output = json.dumps(telemetry_payload, indent=2)
        
        # 🚀 Step 5: 把 JSON 实时发布到 MQTT 话题中！
        try:
            mqtt_client.publish(MQTT_TOPIC, json_output, qos=0)
            print(f"[MQTT] Successfully published data frame to {MQTT_TOPIC}")
        except Exception as e:
            print(f"[MQTT Error] Failed to publish: {e}")
        
        print("-" * 50)
        time.sleep(1.0)
=======
    
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
                    "button_pressed": period_button_latched  # 📊 上报这 1 秒周期内最终的锁存结果
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
>>>>>>> Stashed changes

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
<<<<<<< Updated upstream
=======
        
        try:
            set_led_status(3, turn_on=False)
            display_text("")
        except Exception:
            pass
>>>>>>> Stashed changes
        print("\n[SYS] KeyboardInterrupt captured. Exiting safely.")
