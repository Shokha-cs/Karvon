# Fergana Bus: how it works and how to set it up

## 1. Big picture

```
 GPS BOX (ESP32)                SUPABASE (cloud database)             WEBSITE / TELEGRAM MINI APP
 ──────────────                 ─────────────────────────             ───────────────────────────
 reads GPS + counts   POST →    report_position()  checks the key     every 3 s: read bus_positions
 passengers, every    every     → saves to bus_positions (latest)  ←  → show real bus on the map
 5 seconds            5 s       → saves to bus_history (all)          → calculate "arrives in X min"

                                Auth (logins) + profiles (roles)  ←   email / Google / Telegram login
 TELEGRAM BOT (bot.py) ──────→  telegram_users (phone numbers)
                                telegram-login function  ←──────────  Mini App sends Telegram's signed data
```

There is **no server of our own**. Supabase is the backend: it stores the data, handles the logins and
checks permissions. The website is static files on GitHub Pages. Only the bot runs on a computer.

## 2. Files

| File | What it does |
|---|---|
| `index.html` | The map: Live / Hokimiyat / Edit tabs, the bus simulation, ETA maths, the route editor |
| `auth.js` | Login screen, the 3 ways to log in, and which tabs each role sees |
| `live.js` | Reads real bus positions from the database and puts them on the map; saves stop requests |
| `config.js` | Supabase address + public key. Empty means demo mode (no login, only simulated buses) |
| `routes.json` | The 3 routes (stops + road shape) |
| `supabase/schema.sql` | All database tables, the security rules and the hardware endpoint. Run it once |
| `supabase/functions/telegram-login/index.ts` | Checks that Telegram login data is real, then logs the person in |
| `bot.py` | Telegram bot: share phone number, open map, `/me` |
| `tools/fake_box.py` | Pretends to be a GPS box. Use it to test without hardware |
| `hardware/esp32_box/esp32_box.ino` | Example code for the real box (ESP32 + GPS over Wi-Fi) |

---

## 3. BEFORE THE HARDWARE MEETING (about 15 minutes)

1. **Create a Supabase project** at supabase.com (free). Choose a region near you (Singapore is fine).
2. **SQL Editor → New query →** paste all of `supabase/schema.sql` → **Run**. You should see "Success".
3. **Table Editor → devices:** change `change-me-box-1` / `change-me-box-2` to your own secret words.
   Each row is one box: `bus_id` is the box's name, `route` is the route **number** on the map (`1`, `2`, `3`).
4. **Project Settings → API:** copy the **Project URL** and the **anon / publishable key** into `config.js`.
   Copy the **service_role / secret key** into `.env` only, and never put it on GitHub.
5. Copy `.env.example` to `.env` and fill in `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_KEY`.
6. **Test without hardware:**
   ```
   python tools/fake_box.py --bus 1-1 --key YOUR-BOX-1-KEY --route 1
   ```
   Each line should start with `200 "ok"`. Open the site, log in, and the route 1 bus has a green outline
   with "🛰 Live 1" at the top. If you see that, the software side is done.

### What to give your hardware teammate

| | |
|---|---|
| URL | `https://YOUR-PROJECT.supabase.co/rest/v1/rpc/report_position` |
| Method | `POST` |
| Headers | `apikey: <anon/publishable key>`, `Content-Type: application/json` |
| Body | `{"bus_id":"1-1","device_key":"...","lat":40.4115,"lng":71.8424,"passengers":12}` |
| How often | Every 3–10 seconds |
| Success | HTTP 200, body `"ok"` |
| Wrong key | HTTP 400, `wrong bus_id or device_key` |
| Bad GPS | HTTP 400, `position outside Fergana region` (e.g. 0,0 before the GPS gets a fix) |

Test from any laptop (Mac, Linux, or Git Bash on Windows):
```
curl -X POST "https://YOUR-PROJECT.supabase.co/rest/v1/rpc/report_position" \
  -H "apikey: YOUR-ANON-KEY" -H "Content-Type: application/json" \
  -d '{"bus_id":"1-1","device_key":"YOUR-BOX-1-KEY","lat":40.4115,"lng":71.8424,"passengers":12}'
```

**Questions to ask him first:**
- **Which board?** The example is for an ESP32.
- **How does it reach the internet?** Wi-Fi or a phone hotspot is easy. A **SIM800L cannot do modern HTTPS**,
  so it won't work with Supabase directly. SIM7600 or A7670 modules can.
- **How does he count passengers?** He only needs to put the number in the `passengers` variable.

**For the demo:** GPS needs open sky. Indoors it may never get a fix. If a judge asks, you can show
`fake_box.py` as the backup.

---

## 4. Login setup (about 30–40 minutes)

### Email + password (website)
- **Authentication → Sign In / Providers → Email:** turn **OFF "Confirm email"** for the hackathon.
  If it stays on, Supabase's free email sender only allows a few emails per hour and sign-ups will get stuck.
- **Authentication → URL Configuration:** set **Site URL** to your GitHub Pages address (e.g.
  `https://shokha-cs.github.io/Karvon/`) and add it to **Redirect URLs**.

### Google (website)
1. In Google Cloud Console → APIs & Services → Credentials, create an **OAuth client ID** of type **Web application**.
2. Under **Authorized redirect URIs**, paste the callback URL that Supabase shows on its Google provider page
   (`https://YOUR-PROJECT.supabase.co/auth/v1/callback`).
3. In Supabase → Sign In / Providers → **Google**, enable it and paste the Client ID and Secret.
4. Google login is hidden inside Telegram because Google blocks logins from in-app browsers.

### Telegram (Mini App)
1. **Edge Functions → Deploy a new function → via Editor**. Name it **`telegram-login`**, paste
   `supabase/functions/telegram-login/index.ts`, and deploy.
2. **Edge Functions → Secrets:** add `BOT_TOKEN` = your bot token.
3. In the function's settings, turn **OFF "Verify JWT"**. The function checks Telegram's signature itself.
4. Fill `.env` with `BOT_TOKEN` and `WEBAPP_URL`, then run:
   ```
   pip install -r requirements.txt
   python bot.py
   ```
5. In Telegram: `/start` → **📱 Share my phone number** → **🗺 Open bus map**. You're logged in automatically
   and the bot sends "🔐 You logged in…".

### Roles
Everyone starts as `passenger`. To promote someone, open **Table Editor → profiles**, find the person,
and set `role` to `hokimiyat` or `developer`. Users cannot change their own role because there is no rule that allows it.

| Role | Sees |
|---|---|
| passenger | Live tab: buses, location, minutes until arrival, how full |
| hokimiyat | Live + Hokimiyat (buses running, passengers now, today's requests per route) |
| developer | Everything + Edit (route editor) |

---

## 5. How the logic works (for explaining and for the video)

### A. One GPS report, start to finish
1. The box reads GPS (lat, lng) and its passenger count.
2. It POSTs `{bus_id, device_key, lat, lng, passengers}` to `report_position`.
3. `report_position` (in `schema.sql`) runs **inside the database**:
   - It looks up `devices` for that `bus_id` + `device_key`. If there's no match, it rejects the report,
     so a stranger can't send fake buses.
   - It rejects positions outside the Fergana region (bad GPS).
   - It **upserts** `bus_positions`: the first report inserts a row and later reports update the same row,
     so there is always one row per bus with its latest position.
   - It adds a row to `bus_history` so every report is kept for analytics.
4. The box can't read or change anything else. It can only call this one function.

### B. How the map shows a real bus (`live.js`)
1. Every 3 seconds, `pollLive()` reads `bus_positions`.
2. A row older than 2 minutes means the box is **offline**, so that bus is skipped.
3. The box only knows the route **number** ("1"). We find the route on the map with the same `name`.
4. **Projection:** `projectOnRoute()` finds the closest point on the route line to the GPS point and returns
   how many metres along the route that is (`d`). The simulated buses use the same `d`, which is why
   the same ETA code works for real buses.
5. **Direction:** if `d` grew since the last report, the bus is going forward (towards the last stop).
   If it shrank, the bus is going back.
6. **ETA:** `arrival()` in `index.html` takes (distance to the stop along the route) ÷ (route speed).
   The speed comes from the route's interval, so it's an estimate, not live traffic.
7. **Fullness:** `passengers / 60`. Above 80% shows "Very full", above 50% "Some seats", otherwise "Plenty of seats".
8. **Mixing real and demo data:** if a route has a real box, its simulated buses are hidden (`hide = true`).
   Routes without a box keep the simulation. A real bus has a **green outline** and "· GPS" in its name.

### C. Logins (`auth.js`)
- **Supabase Auth** stores accounts in its own hidden `auth.users` table. When a user is created, a
  **trigger** (`handle_new_user`) automatically creates their row in `profiles` with role `passenger`.
- **Staying logged in:** Supabase saves the session in the browser. On the next visit, `onAuthStateChange`
  fires with that session, so there's no login screen.
- **Email:** `signUp()` creates the account (name saved as `full_name`) and `signInWithPassword()` logs in.
  Passwords are never stored by us; Supabase hashes them.
- **Google:** `signInWithOAuth()` sends the person to Google, Google sends them back, and Supabase logs them in.
- **Telegram:**
  1. Telegram gives the Mini App `initData`: the user's id and name plus a **signature** made with our bot token.
  2. The page sends it to the `telegram-login` function.
  3. The function recalculates the signature with the bot token. If it matches, the data really came from
     Telegram (`checkTelegram()`).
  4. It creates the account the first time (hidden email `tg<id>@telegram.local`), creates a **one-time
     login token**, copies the phone number from the bot onto the profile, and sends the bot notification.
  5. The page exchanges the token for a session (`verifyOtp`).
  - The bot token never goes to the browser. That's why this step needs a server function.
- **Phone number (bot):** Telegram's "share contact" button gives the bot a phone number that Telegram
  has already verified, so no SMS is needed. The bot only accepts the person's own number and saves it to
  `telegram_users`.

### D. Security: who can see what (Row Level Security)
Every table has RLS on. With no matching rule, the answer is "no".

| Table | Rule |
|---|---|
| `profiles` | You can read **only your own** row. Nobody can change roles through the app |
| `bus_positions` | Any **logged-in** user can read |
| `bus_history`, `stop_requests` (read) | Only `hokimiyat` and `developer` (`my_role()` checks this) |
| `stop_requests` (write) | A logged-in user can add **their own** request |
| `devices`, `telegram_users` | Nobody through the app. Only the database function, bot and edge function |

That's why the **anon key can be public** in `config.js`: the rules decide what it's allowed to do.
The **service key** skips all rules, so it lives only in `.env` and in Supabase's secrets.

### E. Demand for hokimiyat
When a passenger taps a stop (or presses "Near me"), `countRequest` → `onStopRequest` saves a row in
`stop_requests`. The Hokimiyat tab counts today's rows per route every 15 seconds. A route is flagged
**"⚠ Add buses"** when its buses are more than 70% full on average, or when it has more than half of all requests.

---

## 6. What is still NOT done (be honest if judges ask)
- Route edits by a developer are still saved in the browser and published with Export JSON → `routes.json` → commit.
  They are not stored in the database yet.
- ETA uses the scheduled route speed, not real traffic.
- The bot runs on your laptop (polling mode). To keep it on 24/7, move it to PythonAnywhere in webhook mode.
- An email account and a Telegram account for the same person are two separate accounts.
- Not tested against a real Supabase project or real hardware yet. Test steps are in section 3.

## 7. Video outline (3–4 min)
1. **Problem (20 s):** in Fergana you don't know where the bus is or whether it's full.
2. **Architecture (40 s):** show the diagram in section 1.
3. **Hardware → database (60 s):** box (or `fake_box.py`) sends a report → `bus_positions` row changes in
   Supabase → the bus moves on the map with a green outline.
4. **Passenger (40 s):** log in with Telegram → tap a stop → "arrives in 4 min, some seats".
5. **Hokimiyat (30 s):** log in as hokimiyat → requests and how full each route is → "⚠ Add buses".
6. **Developer (20 s):** Edit tab, route editor.
7. **Security (20 s):** device keys, RLS, Telegram signature check.
