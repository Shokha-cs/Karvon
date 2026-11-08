# Fergana Bus

Live bus map for Fergana: where each bus is, how many passengers, and when it arrives.
Works as a website and as a Telegram Mini App. UzHack — Smart Transport & Mobility track.

## Files
- `index.html` — the map (Live / Add route / Hokimiyat demand view)
- `routes.json` — bus routes, loaded by the map when online (export from "Add route")
- `bot.py` — Telegram bot that opens the map

## Run the bot
1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env`, fill in BOT_TOKEN and WEBAPP_URL
3. `python bot.py`

## Bus data format (shared with the hardware box)
`{bus_id, route, lat, lng, passengers, time}` — currently simulated in `index.html`.
