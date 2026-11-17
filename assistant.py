# AI assistant: routes + live buses + forecast -> gemini
# needs GEMINI_API_KEY in .env
import json
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
# can change model in .env
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

TZ = timezone(timedelta(hours=5))  # fergana UTC+5
CAP = 60  # = 100% full
OFFLINE_AFTER_S = 120
ROUTES_FILE = Path(__file__).with_name("routes.json")

SYSTEM_PROMPT = """You are Karvon, the bus assistant for the city of Fergana, Uzbekistan.
You help passengers with city buses: which route to take, where buses are now,
how full they are, and when it is less crowded.

Rules:
- Use ONLY the data given below. Never invent routes, stops, times or numbers.
  If the data doesn't answer the question, say so honestly.
- Stop names in the data are in Russian. Passengers may write them in Uzbek
  (Latin or Cyrillic), Russian or English; match them sensibly and write the
  stop name the way it appears in the data.
- To get from A to B: find routes that have both stops. If no single route has
  both, suggest a transfer at a stop shared by two routes. If you are not sure
  which stop the passenger means, ask a short question.
- Times are approximate. Say "about".
- Reply in the passenger's language (Uzbek, Russian or English).
- Keep it short: at most 6 lines. Plain text, no Markdown, no tables.
- Off-topic questions: politely say you only help with Fergana buses."""


# data helpers
_routes_cache = {"mtime": None, "routes": []}


def load_routes():
    # reload only if file changed
    mtime = ROUTES_FILE.stat().st_mtime
    if _routes_cache["mtime"] != mtime:
        _routes_cache["routes"] = json.loads(ROUTES_FILE.read_text(encoding="utf-8"))
        _routes_cache["mtime"] = mtime
    return _routes_cache["routes"]


def stops_of(route):
    # skip turn points
    out = []
    for s in route["stops"]:
        if len(s) > 2 and s[2] == 0:
            continue
        name = s[3] if len(s) > 3 and s[3] else f"Stop {len(out) + 1}"
        out.append((name, s[0], s[1]))
    return out


def dist(a_lat, a_lng, b_lat, b_lng):
    R = 6371000
    dlat, dlng = math.radians(b_lat - a_lat), math.radians(b_lng - a_lng)
    h = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(dlng / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def nearest_stop(route, lat, lng):
    return min(((dist(lat, lng, s[1], s[2]), s[0]) for s in stops_of(route)), default=(None, None))


def parse_time(text):
    # fix fraction digits so fromisoformat works
    t = text.replace("Z", "+00:00")
    if "." in t:
        head, rest = t.split(".", 1)
        digits = rest[: len(rest) - len(rest.lstrip("0123456789"))]
        t = f"{head}.{(digits + '000000')[:6]}{rest[len(digits):]}"
    return datetime.fromisoformat(t).timestamp()


def load_word(passengers):
    f = passengers / CAP
    return "very full" if f > 0.8 else "some seats" if f > 0.5 else "plenty of seats"


# context for the AI
async def build_context(db, user_location=None):
    routes = load_routes()
    now = datetime.now(TZ)
    lines = [f"Current time in Fergana: {now:%A %H:%M}.", ""]

    # routes
    lines.append("ROUTES (stops in order, buses go both ways):")
    for r in routes:
        info = [f"{r.get('buses') or '?'} buses"]
        if r.get("interval"):
            info.append(f"a bus every ~{r['interval']} min")
        lines.append(f"Route {r['name']} ({r.get('title') or 'no title'}; {', '.join(info)}):")
        lines.append("  " + " → ".join(s[0] for s in stops_of(r)))
    lines.append("")

    # live gps buses
    by_name = {str(r["name"]): r for r in routes}
    resp = await db("GET", "bus_positions?select=bus_id,route,lat,lng,passengers,updated_at")
    rows = resp.json() if resp.is_success else []
    live = []
    for b in rows:
        age = time.time() - parse_time(b["updated_at"])
        r = by_name.get(str(b["route"]))
        if age > OFFLINE_AFTER_S or not r:
            continue
        d, stop = nearest_stop(r, b["lat"], b["lng"])
        live.append(f"Bus {b['bus_id']} on route {r['name']}: near stop \"{stop}\" (~{round(d)} m), "
                    f"{b['passengers']}/{CAP} passengers ({load_word(b['passengers'])}), "
                    f"reported {round(age)} s ago.")
    lines.append("LIVE BUSES WITH GPS (right now):")
    lines += live or ["None online right now. Only the timetable data above is available."]
    lines.append("")

    # forecast, now + 3h
    resp = await db("POST", "rpc/crowd_forecast", json={})
    fc = resp.json() if resp.is_success else []
    hours = range(now.hour, min(24, now.hour + 4))
    lines.append("USUAL CROWDING (average from the GPS boxes, last 4 weeks):")
    added = 0
    for r in routes:
        parts = []
        for h in hours:
            row = next((x for x in fc if str(x["route"]) == str(r["name"]) and x["hour"] == h), None)
            if row and row["samples"] >= 5:
                pct = round(min(1, float(row["avg_passengers"]) / CAP) * 100)
                parts.append(f"{h:02d}:00 ~{pct}% full")
        if parts:
            lines.append(f"Route {r['name']}: " + ", ".join(parts))
            added += 1
    if not added:
        lines.append("Not enough data collected yet.")
    lines.append("")

    # user location if shared
    if user_location:
        lat, lng = user_location
        near = sorted(
            (d, r["name"], name)
            for r in routes
            for (name, s_lat, s_lng) in stops_of(r)
            for d in [dist(lat, lng, s_lat, s_lng)]
        )[:4]
        lines.append("PASSENGER'S LOCATION: shared. Nearest stops:")
        lines += [f"  \"{name}\" on route {rn}, ~{round(d)} m away" for d, rn, name in near]
    else:
        lines.append("PASSENGER'S LOCATION: not shared (they can press \"📍 Send my location\").")
    return "\n".join(lines)


# gemini
class AssistantError(Exception):
    pass


async def ask(question: str, context_text: str) -> str:
    if not GEMINI_KEY:
        raise AssistantError("The AI assistant is not set up yet (no GEMINI_API_KEY).")
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT + "\n\nDATA:\n" + context_text}]},
        "contents": [{"role": "user", "parts": [{"text": question[:1000]}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
    }
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=15)) as c:
            r = await c.post(GEMINI_URL.format(model=GEMINI_MODEL),
                             headers={"x-goog-api-key": GEMINI_KEY}, json=body)
    except httpx.TimeoutException:
        print(f"gemini timeout after {time.time() - t0:.0f}s")
        raise AssistantError("The AI took too long to answer. Please try again.")
    print(f"gemini {r.status_code} in {time.time() - t0:.1f}s")
    if r.status_code == 429:
        raise AssistantError("The AI is busy right now. Please try again in a minute.")
    if not r.is_success:
        print("gemini error:", r.status_code, r.text[:500])
        raise AssistantError("The AI assistant had a problem. Please try again later.")
    data = r.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    except (KeyError, IndexError):
        text = ""
    if not text:
        print("gemini empty answer:", json.dumps(data)[:500])
        raise AssistantError("Sorry, I couldn't answer that. Try asking in another way.")
    return text[:3500]  # telegram limit 4096


# rate limit per user (free key)
MIN_GAP_S = 4
PER_DAY = 40
_last, _count = {}, {}


def allowed(user_id: int):
    # None = ok
    now, today = time.time(), datetime.now(TZ).date()
    if now - _last.get(user_id, 0) < MIN_GAP_S:
        return "One question at a time, please 🙂"
    day, n = _count.get(user_id, (today, 0))
    if day != today:
        n = 0
    if n >= PER_DAY:
        return "You've reached today's question limit. Try again tomorrow."
    _last[user_id] = now
    _count[user_id] = (today, n + 1)
    return None
