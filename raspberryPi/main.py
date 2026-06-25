import time
import json
import paho.mqtt.client as mqtt

# Import custom modular drivers
from sensors.dht_sensor import read_temperature_humidity
from sensors.noise_sensor import setup_sound_pin, read_sound_level
from sensors.light_sensor import read_light_level          
from sensors.button_sensor import setup_button_pin, read_button_status 
from actuators.led_actuator import setup_led_pin, set_led_status       
from actuators.lcd_actuator import init_lcd, display_text, set_lcd_backlight 

# ==================== HARDWARE & NETWORK CONFIGURATION ====================
CLIENT_ID = "pi_node_seat_A1"
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "cybercafe/seat_A1"

# 🔄 物理引脚映射
SOUND_PIN = 0         # A0
LIGHT_PIN = 1         # A1 
BUTTON_PIN = 2        # D2 
LED_PIN = 3           # D3 
DHT_PIN = 4           # D4
DHT_TYPE = 0          

# 📊 业务阈值与时间配置
LIGHT_THRESHOLD = 200  
CALL_DURATION = 2.0    # 呼叫信息在 LCD 上的持续时间（秒）
# =======================================================================

def main():
    print("==================================================")
    print("Smart Cybercafe IoT Edge Node Core Starting...")
    print("Initializing hardware components & MQTT Client...")
    
    # 1. 初始化硬件引脚与模式
    setup_sound_pin(port=SOUND_PIN)
    setup_button_pin(port=BUTTON_PIN)  
    setup_led_pin(port=LED_PIN)        
    init_lcd()                         
    
    # 2. 初始化 MQTT 客户端
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
    
    # ⏳ 状态机与降频控制变量（严格的4空格缩进）
    call_active = False       
    call_start_time = 0.0     
    last_lcd_status = ""      

    # 💾 硬件数据缓存变量
    cached_temp, cached_hum = 0.0, 0.0
    cached_light = 500
    cached_noise = 0
    
    # ⏰ 时间戳锚点
    last_fast_env_time = 0.0      # 用于光敏/噪音（2秒一读）
    last_slow_env_time = 0.0      # 用于温湿度（3秒一读）
    last_mqtt_publish_time = 0.0   # MQTT上报（1秒一报）

    def trigger_call():
        """闭包函数：统一处理呼叫状态触发"""
        nonlocal call_active, call_start_time
        if not call_active:
            print("[CALL] Button pressed! Activating 2s Admin Alert.")
        call_active = True
        call_start_time = time.time()

    # 🚀 极速主循环 (以 20Hz/50ms 速度高频运转)
    while True:
        current_time = time.time()

        # ---------------- 1. 极速读取按键 (优先级别最高，每次循环都读) ----------------
        button_pressed = read_button_status(port=BUTTON_PIN)
        if button_pressed:
            trigger_call()

        # ---------------- 2. 较快地刷新光敏和噪音 (每 2.0 秒) ----------------
        if current_time - last_fast_env_time >= 2.0:
            light_value = read_light_level(port=LIGHT_PIN)
            sound_value = read_sound_level(port=SOUND_PIN)
            cached_light = light_value if light_value is not None else cached_light
            cached_noise = sound_value if sound_value is not None else cached_noise
            last_fast_env_time = current_time

        # ---------------- 3. 提速后的温湿度读取 (从 10秒 优化至 3.0 秒) ----------------
        if current_time - last_slow_env_time >= 3.0 or last_slow_env_time == 0.0:
            # 此时会卡顿固件要求的0.7秒，但因为每3秒才发生一次，按键体验大幅提升
            temp, hum = read_temperature_humidity(port=DHT_PIN, sensor_type=DHT_TYPE)
            cached_temp = temp if temp is not None else cached_temp
            cached_hum = hum if hum is not None else cached_hum
            last_slow_env_time = current_time

        # 🛠️ 自动联动决策 A: 光敏联动补光灯
        if cached_light < LIGHT_THRESHOLD:
            set_led_status(port=LED_PIN, turn_on=True)
            led_status_str = "ON"
        else:
            set_led_status(port=LED_PIN, turn_on=False)
            led_status_str = "OFF"
            
        # 🛠️ 自动联动决策 B: 带时间锁的按键呼叫管理员
        if call_active:
            if current_time - call_start_time < CALL_DURATION:
                lcd_alert_str = "Calling Admin"
                if last_lcd_status != "Calling Admin":
                    display_text("Calling Admin...")
                    set_lcd_backlight(255, 0, 0) # 警示红
                    last_lcd_status = "Calling Admin"
            else:
                # 满 2 秒了，自动退出呼叫状态
                call_active = False
                lcd_alert_str = "Normal"
                display_text("System Normal")
                set_lcd_backlight(255, 255, 255) # 恢复白
                last_lcd_status = "Normal"
        else:
            # 常态情况
            lcd_alert_str = "Normal"
            if last_lcd_status != "Normal":
                display_text("System Normal")
                set_lcd_backlight(255, 255, 255)
                last_lcd_status = "Normal"
        
        # ---------------- 4. 严格维持每 1.0 秒向 MQTT 代理上报一次 ----------------
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
                    "button_pressed": button_pressed  
                },
                "local_actuators": {
                    "led_status": led_status_str,   
                    "lcd_alert": lcd_alert_str       
                }
            }
                
            json_output = json.dumps(telemetry_payload, indent=2)
            try:
                mqtt_client.publish(MQTT_TOPIC, json_output, qos=0)
                print(f"[MQTT] Published. Temp: {cached_temp}°C, Light: {cached_light}, LED: {led_status_str}, Display: {lcd_alert_str}")
            except Exception as e:
                print(f"[MQTT Error] Failed to publish: {e}")
            
            print("-" * 50)
            last_mqtt_publish_time = current_time
        
        # ---------------- 5. 极短的系统节拍放空 ----------------
        # 每次循环睡 50ms (20Hz)，既保证极速捕捉按键，又防止CPU占用率飙满 100%
        time.sleep(0.05)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # 安全退出保护机制
        try:
            set_led_status(3, turn_on=False)
            display_text("")
        except Exception:
            pass
        print("\n[SYS] KeyboardInterrupt captured. Exiting safely.")
