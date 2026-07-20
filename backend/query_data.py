import json
import urllib.request
import pandas as pd
import random
import json

app = Flask(__name__)
CORS(app)  

URL = "http://127.0.0.1:8086"  
TOKEN = "apiv3_kHXnnT92Gd5kGVoZSEUJ16UdgAPY80G6gnXTVneCtp8xaX2qpcAdQi6UBcPz-0HKi5swWffTjVIWXXlqPsyHuA"  
DATABASE = "cybercafe_data"

# ==================== PDDL  ====================
def generate_problem_pddl(seats_list):
    
    pddl = "(define (problem cybercafe-recommend)\n"
    pddl += "  (:domain cybercafe)\n"
    pddl += "  (:objects seat_A1 seat_A2 seat_A3 seat_A4)\n"
    pddl += "  (:init\n"
    
    for seat in seats_list:
        sid = seat["seat_id"]
        pddl += f"    (seat {sid})\n"
        
        
        pddl += f"    (is-available {sid})\n"
            
        if seat["noise"] < 60:     
            pddl += f"    (is-quiet {sid})\n"
        if seat["light"] > 100:    
            pddl += f"    (is-bright {sid})\n"
        if seat["temperature"] < 28: 
            pddl += f"    (is-comfortable {sid})\n" # 顺便将谓词语义微调得更严谨
            
    pddl += "  )\n"
    pddl += "  (:goal (or (recommended seat_A1) (recommended seat_A2) (recommended seat_A3) (recommended seat_A4)))\n"
    pddl += ")"
    return pddl

def solve_pddl(problem_pddl):
    """local PDDL planer"""
    try:
        import re
        init_section = re.search(r'\(:init\s+(.*?)\s*\)', problem_pddl, re.DOTALL)
        if not init_section:
            return "seat_A1"
        predicates = re.findall(r'\(([\w-]+)\s+([\w-]+)\)', init_section.group(1))
        
        world_state = {}
        for pred, obj in predicates:
            if obj not in world_state:
                world_state[obj] = set()
            world_state[obj].add(pred)
            
        
        required_conditions = {"is-available", "is-quiet", "is-bright", "is-comfortable"}
        for seat_id, status_set in world_state.items():
            if required_conditions.issubset(status_set):
                return seat_id
    except Exception as e:
        print(f"[Local PDDL Planner Error] {e}")
    return "seat_A3"

# =========================================================

@app.route('/api/seat_data', methods=['GET'])
def get_seat_data():
    SQL_QUERY = "SELECT * FROM cybercafe_telemetry ORDER BY time DESC LIMIT 1;"
    params = {"db": DATABASE, "q": SQL_QUERY}
    full_url = f"{URL}/query?{urllib.parse.urlencode(params)}"
    
    req = urllib.request.Request(full_url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/csv")
    
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            if not html.strip():
                return jsonify({"status": "empty", "data": []})
            
            df = pd.read_csv(StringIO(html))
            if df.empty:
                return jsonify({"status": "empty", "data": []})
                
            latest_real = df.iloc[0]
            
            # 1. parameters of A1
            is_button_pressed = int(latest_real.get("button_pressed", 0)) == 1
            real_temp = round(float(latest_real.get("temperature", 24.0)), 1)
            real_hum = round(float(latest_real.get("humidity", 50.0)), 1)
            real_noise = int(latest_real.get("noise_level", 40))
            real_light = int(latest_real.get("light_level", 300))
            
            seat_A1 = {
                "seat_id": "seat_A1",
                "temperature": real_temp,
                "humidity": real_hum,
                "noise": real_noise,
                "light": real_light,
                "button_pressed": is_button_pressed,
                "led_status": str(latest_real.get("led_status", "OFF")),
                "lcd_alert": str(latest_real.get("lcd_alert", "Normal"))
            }
            
            # 
            
            change_chance = random.random() < 0.15  # 每2秒只有15%的几率触发数据微变
            
            # parameters of A2
            a2_noise_bounce = random.randint(-1, 1) if change_chance else 0
            a2_hum_bounce = random.uniform(-0.1, 0.1) if change_chance else 0
            
            seat_A2 = {
                "seat_id": "seat_A2",
                "temperature": round(real_temp + 1.2, 1), # 温度直接锚定，不频繁刷新
                "humidity": round(real_hum + 2.0 + a2_hum_bounce, 1),
                "noise": int(80 + a2_noise_bounce),      # 大部分时间死死保持在 80
                "light": int(real_light - 20),
                "button_pressed": False,
                "led_status": "OFF",
                "lcd_alert": "Normal"
            }
            
            # parameters of A3
            a3_noise_bounce = random.randint(-1, 1) if (change_chance and random.random() < 0.5) else 0 # 让它更不容易变
            a3_hum_bounce = random.uniform(-0.05, 0.05) if change_chance else 0
            
            seat_A3 = {
                "seat_id": "seat_A3",
                "temperature": round(real_temp - 1.5, 1),
                "humidity": round(real_hum - 2.0 + a3_hum_bounce, 1),
                "noise": int(30 + a3_noise_bounce),      # 大部分时间死死保持在 30
                "light": int(real_light + 50),
                "button_pressed": False,
                "led_status": "OFF",
                "lcd_alert": "Welcome"
            }
            
            # parameters of A4
            a4_noise_bounce = random.randint(-1, 1) if change_chance else 0
            a4_hum_bounce = random.uniform(-0.1, 0.1) if change_chance else 0
            
            a4_button = random.random() < 0.1 if not hasattr(get_seat_data, "a4_state") else get_seat_data.a4_state
            get_seat_data.a4_state = a4_button 
            
            seat_A4 = {
                "seat_id": "seat_A4",
                "temperature": round(real_temp + 6.5, 1),
                "humidity": round(real_hum + 12.0 + a4_hum_bounce, 1),
                "noise": int(35 + a4_noise_bounce),
                "light": int(100),
                "button_pressed": a4_button,
                "led_status": "ON" if a4_button else "OFF",
                "lcd_alert": "Calling..." if a4_button else "Normal"
            }
            
            all_seats = [seat_A1, seat_A2, seat_A3, seat_A4]
            
            # 3. run PDDL 
            problem_pddl_str = generate_problem_pddl(all_seats)
            recommended_id = solve_pddl(problem_pddl_str)
            
            return jsonify({
                "status": "success",
                "recommended_seat": recommended_id,
                "data": all_seats
            })
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

