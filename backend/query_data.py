import urllib.parse
import urllib.request
from io import StringIO
from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd

app = Flask(__name__)
# 🔒 极其关键：允许跨域请求（CORS）。如果没有这一行，她的前端在调用你的IP时会被浏览器拦截报错
CORS(app)  

URL = "http://127.0.0.1:8086"  # 保持和你本地数据库通信的端口一致
TOKEN = "apiv3_kHXnnT92Gd5kGVoZSEUJ16UdgAPY80G6gnXTVneCtp8xaX2qpcAdQi6UBcPz-0HKi5swWffTjVIWXXlqPsyHuA"  # 👈 你的真钥匙
DATABASE = "cybercafe_data"

@app.route('/api/seat_data', methods=['GET'])
def get_seat_data():
    """这是给前端专门准备的接口，访问 http://你的IP:5000/api/seat_data 就能拿数"""
    # 编写标准 SQL 语句，获取最新的 15 条实时数据
    SQL_QUERY = "SELECT * FROM cybercafe_telemetry ORDER BY time DESC LIMIT 15;"
    
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
            
            # 利用 Pandas 把 InfluxDB 吐出来的 CSV 变成 DataFrame
            df = pd.read_csv(StringIO(html))
            
            # 🌟 降维打击转换：把 DataFrame 格式直接转化为标准的前端最喜欢的 JSON 数组
            result_json = df.to_dict(orient="records")
            
            return jsonify({
                "status": "success", 
                "count": len(result_json),
                "data": result_json
            })
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # 🌟 极其重要：host='0.0.0.0' 意味着这个 Web 服务不只是给你自己看
    # 它是对整个局域网公开的，允许你组员的电脑顺着网络过来要数据！
    app.run(host='0.0.0.0', port=5001, debug=True)