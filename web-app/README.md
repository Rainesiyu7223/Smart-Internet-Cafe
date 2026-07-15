# Smart Internet Cafe Web App

FastAPI + SQLite web app for online reservation, arrival check-in, seat recommendation, and Raspberry Pi seat telemetry dashboard.

## Run

```bash
cd /Users/Rain/Desktop/Project/Smart-Internet-Cafe/web-app
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

## Dashboard

Open <http://127.0.0.1:8000/dashboard> to view the latest A01 seat temperature and humidity.

By default, the dashboard reads live data from Computer A:

```bash
TELEMETRY_API_URL=http://192.168.0.114:5001/api/seat_data
```

Computer A should return JSON with a `data` list, for example:

```json
{
  "status": "ok",
  "data": [
    {
      "seat_code": "A01",
      "temperature": 24.6,
      "humidity": 52.3,
      "noise_level": 218,
      "motion_detected": true,
      "received_at": "2026-06-22T13:30:00Z"
    }
  ]
}
```

The app can also subscribe to MQTT topic `cybercafe/#` and stores incoming Raspberry Pi telemetry in SQLite. The existing Raspberry Pi script publishes payloads like:

```json
{
  "client_id": "pi_node_seat_A1",
  "timestamp": 1782140000,
  "environment": {
    "temperature": 24.6,
    "humidity": 52.3,
    "noise_level": 218
  },
  "seat_interact": {
    "motion_detected": true,
    "rotary_raw_value": 687
  }
}
```

Environment variables:

```bash
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_TOPIC=cybercafe/#
ENABLE_MQTT_SUBSCRIBER=1
```

You can also test without Raspberry Pi hardware:

```bash
curl -X POST http://127.0.0.1:8000/api/telemetry \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi_node_seat_A1","environment":{"temperature":24.6,"humidity":52.3,"noise_level":218},"seat_interact":{"motion_detected":true}}'
```

## Flow

1. User creates an online reservation with their name.
2. The name is stored in SQLite at `web-app/cafe.db`.
3. User arrives and enters the same name on `/checkin`.
4. The app compares the name with pending reservations.
5. A successful check-in redirects to `/seats` with an available seat recommendation.
