# Smart Internet Cafe Web App

FastAPI + SQLite web app for online reservation, arrival check-in, and seat recommendation.

## Run

```bash
cd /Users/Rain/Desktop/Project/Smart-Internet-Cafe/web-app
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>.

## Flow

1. User creates an online reservation with their name.
2. The name is stored in SQLite at `web-app/cafe.db`.
3. User arrives and enters the same name on `/checkin`.
4. The app compares the name with pending reservations.
5. A successful check-in redirects to `/seats` with an available seat recommendation.
