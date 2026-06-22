import json
import urllib.request
import pandas as pd
from io import StringIO

# 1. 对齐 v3 核心参数 (注意：v3单机版原生查询网关默认在 8082 端口！)
URL = "http://127.0.0.1:8086"  
TOKEN = "apiv3_kHXnnT92Gd5kGVoZSEUJ16UdgAPY80G6gnXTVneCtp8xaX2qpcAdQi6UBcPz-0HKi5swWffTjVIWXXlqPsyHuA"    # 👈 粘贴你在 config.toml 里找到的真钥匙
DATABASE = "cybercafe_data"       # 👈 确定是你的网咖数据库

# 2. 编写无比纯净的标准 SQL
# 临时改写这行，让数据库列出它名下所有的表
#SQL_QUERY = "SHOW TABLES;"
SQL_QUERY = "SELECT * FROM cybercafe_telemetry ORDER BY time DESC LIMIT 15;"

print(f"🚀 正在通过 v3 原生 gRPC/HTTP 桥梁执行标准 SQL 查询...")

# 3. 构造 v3 原生兼容的 V1 查询网关请求 (这是v3单机版最通用的轻量读数方式)
req_url = f"{URL}/query"
params = {
    "db": DATABASE,
    "q": SQL_QUERY
}
full_url = f"{req_url}?{urllib.parse.urlencode(params)}"

req = urllib.request.Request(full_url)
req.add_header("Authorization", f"Bearer {TOKEN}")
req.add_header("Accept", "application/csv") # 让它直接吐出清爽的 CSV 格式

try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        
        print("\n" + "="*60)
        print(f"🎉 成功获取 cybercafe_data 中最新的 15 条实时数据:")
        print("="*60)
        
        # 4. 用 Pandas 优雅平铺出来
        if not html.strip():
            print("⚠️ 数据库目前是一张白纸，还没有收到任何树莓派写入的数据数据。")
        else:
            df = pd.read_csv(StringIO(html))
            print(df.to_string(index=False))
            
        print("="*60)

except urllib.error.HTTPError as e:
    error_body = e.read().decode('utf-8')
    print(f"\n❌ 查询请求失败 (状态码 {e.code})")
    print(f"错误详情: {error_body}")
    print("💡 提示：如果报 table not found，说明树莓派的数据还没写进去，请让 Backend_bridge.py 多跑几秒钟。")
except Exception as e:
    print(f"\n❌ 发生意外错误: {e}")