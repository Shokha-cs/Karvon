"""Pretends to be a GPS box: drives along a route from routes.json and
sends the position to Supabase every few seconds, exactly like the real box.

Use it to test the whole chain (box -> database -> map) without hardware:
    python tools/fake_box.py --bus 1-1 --key change-me-box-1 --route 1

Needs SUPABASE_URL and SUPABASE_ANON_KEY in .env (same as the bot) or
in your environment. Only Python's standard library is used.
"""
import argparse
import json
import math
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def dist(a, b):
    """metres between two [lat, lng] points"""
    R = 6371000
    dlat, dlng = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def send(url, key, payload):
    req = urllib.request.Request(
        f"{url}/rest/v1/rpc/report_position",
        data=json.dumps(payload).encode(),
        headers={"apikey": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--bus", default="1-1", help="bus_id from the devices table")
    ap.add_argument("--key", default="change-me-box-1", help="device_key from the devices table")
    ap.add_argument("--route", default="1", help="route number in routes.json")
    ap.add_argument("--speed", type=float, default=60, help="metres per second (60 = fast demo)")
    ap.add_argument("--every", type=float, default=3, help="seconds between reports")
    a = ap.parse_args()

    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_ANON_KEY"]
    routes = json.loads((ROOT / "routes.json").read_text(encoding="utf-8"))
    r = next(x for x in routes if x["name"] == a.route)
    line = [p[:2] for p in (r.get("path") or r["stops"])]

    pos, i, passengers = 0.0, 0, 10  # distance along current segment, segment index
    print(f"Driving bus {a.bus} on route {a.route} ({len(line)} points). Ctrl+C to stop.")
    while True:
        # move forward along the line
        step = a.speed * a.every
        while step > 0:
            seg = dist(line[i], line[i + 1])
            if pos + step < seg:
                pos += step
                step = 0
            else:
                step -= seg - pos
                pos, i = 0.0, i + 1
                if i >= len(line) - 1:  # end of route: turn around
                    line.reverse()
                    i = 0
        seg = dist(line[i], line[i + 1]) or 1
        t = pos / seg
        lat = line[i][0] + (line[i + 1][0] - line[i][0]) * t
        lng = line[i][1] + (line[i + 1][1] - line[i][1]) * t
        passengers = max(0, min(60, passengers + random.randint(-3, 4)))

        payload = {"bus_id": a.bus, "device_key": a.key, "lat": round(lat, 6), "lng": round(lng, 6), "passengers": passengers}
        status, body = send(url, key, payload)
        print(status, body, payload)
        time.sleep(a.every)


if __name__ == "__main__":
    main()
