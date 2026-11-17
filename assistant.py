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
GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash-lite"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

TZ = timezone(timedelta(hours=5))  # fergana UTC+5
CAP = 60  # = 100% full
OFFLINE_AFTER_S = 120
ROUTES_FILE = Path(__file__).with_name("routes.json")

# same rules as supabase/functions/ai-chat/index.ts, keep both in sync
SYSTEM_PROMPT = """You are Karvon, the bus assistant for the city of Fergana, Uzbekistan.

How to answer:
- Bus questions come first. ALWAYS give a direct, useful answer in the first line:
  which route, which stop, roughly how long to wait, how full it is.
  Never answer only "there is not enough data".
- If live GPS data exists, use it. If not, answer from the timetable data
  (routes, stops, buses per route, interval) and say it is an estimate.
  Example: a bus every ~15 min means you wait about 8 min on average, 15 at most.
- Then, if useful, add one short note (e.g. "live GPS is not on for this route yet").
- Only ask a question back if you really can't tell which stop or route they mean,
  and still give your best guess first.
- Stop names in the data are in Russian. Passengers may write in Uzbek (Latin or
  Cyrillic), Russian or English: match names sensibly, write the stop name as in the data.
- From A to B: find a route with both stops. If none, suggest a transfer at a stop
  shared by two routes.
- Never invent routes, stops or numbers that are not in the data.
- Other questions (not about buses): answer briefly and politely, then offer bus help.
- Reply in the passenger's language. Max 6 lines, plain text, no Markdown, no tables."""


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
        if d is None:  # route has no stops
            continue
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


LANG_NAME = {"uz": "Uzbek (Latin script)", "ru": "Russian", "en": "English"}


# errors carry a key, bot.py turns it into the user's language
async def ask(question: str, context_text: str, lang: str | None = None) -> str:
    if not GEMINI_KEY:
        raise AssistantError("no_key")
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT
                                         + (f"\n- ALWAYS reply in {LANG_NAME[lang]}, whatever language the question is in." if lang in LANG_NAME else "")
                                         + "\n\nDATA:\n" + context_text}]},
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
        raise AssistantError("timeout")
    print(f"gemini {r.status_code} in {time.time() - t0:.1f}s")
    if r.status_code == 429:
        raise AssistantError("busy")
    if not r.is_success:
        print("gemini error:", r.status_code, r.text[:500])
        raise AssistantError("problem")
    data = r.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    except (KeyError, IndexError):
        text = ""
    if not text:
        print("gemini empty answer:", json.dumps(data)[:500])
        raise AssistantError("empty")
    return text[:3500]  # telegram limit 4096


# rate limit per user (free key)
MIN_GAP_S = 4
PER_DAY = 40
_last, _count = {}, {}


def allowed(user_id: int):
    # None = ok
    now, today = time.time(), datetime.now(TZ).date()
    if now - _last.get(user_id, 0) < MIN_GAP_S:
        return "slow"
    day, n = _count.get(user_id, (today, 0))
    if day != today:
        n = 0
    if n >= PER_DAY:
        return "limit"
    _last[user_id] = now
    _count[user_id] = (today, n + 1)
    return None
