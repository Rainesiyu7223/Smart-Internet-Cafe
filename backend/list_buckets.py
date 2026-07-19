import urllib.request
import json

TOKEN = "apiv3_kHXnnT92Gd5kGVoZSEUJ16UdgAPY80G6gnXTVneCtp8xaX2qpcAdQi6UBcPz-0HKi5swWffTjVIWXXlqPsyHuA"
URL = "http://127.0.0.1:8086"

# list all buckets
req = urllib.request.Request(f"{URL}/api/v2/buckets")
req.add_header("Authorization", f"Token {TOKEN}")

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        print("Existing buckets:")
        for bucket in data.get('buckets', []):
            print(f"  - {bucket['name']}")
except Exception as e:
    print(f"Error: {e}")