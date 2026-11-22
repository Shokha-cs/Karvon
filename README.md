# Karvon · Fergana Bus

Live bus map for Fergana: where each bus is, how many passengers, and when it arrives.
Works as a website and as a Telegram Mini App. UzHack — Smart Transport & Mobility track.

For Housing Box concept 3D model photos check hardware/esp32_box 

- **Passengers:** live buses, minutes until arrival, how full
- **Hokimiyat:** buses running, passengers now, demand per route
- **Developer:** everything + route editor
- **Crowding forecast:** how full each route usually is, hour by hour (from the GPS history)
- **AI assistant (Telegram):** ask "which bus goes to …?" in Uzbek, Russian or English; answers from live data

Login: email/password or Google on the website; Telegram account + shared phone number in Telegram.
Backend: Supabase (database, auth, security rules). GPS boxes POST to one database function.

**Setup, hardware connection and how every part works: see [GUIDE.md](GUIDE.md).**

Hardware data format: `{bus_id, device_key, lat, lng, passengers}` → `POST /rest/v1/rpc/report_position`.
Without `config.js` filled in, the site runs in demo mode with simulated buses.
