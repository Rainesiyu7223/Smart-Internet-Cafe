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

DHT_PIN = 4          
DHT_TYPE = 0         
SOUND_PIN = 0        
BUZZER_PIN = 3       
PIR_PIN = 8          
ROTARY_PIN = 1       

NOISE_THRESHOLD = 400
# =======================================================================

def main():
    print("==================================================")
    print("Smart Cybercafe IoT Edge Node Core Starting...")
    print("Initializing hardware components & MQTT Client...")
    
    # 1. 初始化硬件
    setup_sound_pin(port=SOUND_PIN)
    setup_buzzer_pin(port=BUZZER_PIN)
    setup_pir_pin(port=PIR_PIN)
    
    # 2. 初始化 MQTT 客户端
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

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[SYS] KeyboardInterrupt captured. Exiting safely.")
