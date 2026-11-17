// real gps buses from bus_positions, every 3s
// route with a real box -> hide fake buses

const LIVE_EVERY_MS = 3000;
const OFFLINE_AFTER_MS = 2 * 60 * 1000; // 2 min no report = offline
let liveTimer = null,
  statsTimer = null;

// gps point -> metres along route (for eta)
function projectOnRoute(r, lat, lng) {
  const kx = Math.cos(rad(lat)) * 111320, // m per degree lng
    ky = 110540; // m per degree lat
  const px = lng * kx,
    py = lat * ky;
  let best = { d: 0, off: Infinity };
  for (let i = 1; i < r._line.length; i++) {
    const ax = r._line[i - 1][1] * kx,
      ay = r._line[i - 1][0] * ky;
    const dx = r._line[i][1] * kx - ax,
      dy = r._line[i][0] * ky - ay;
    const len2 = dx * dx + dy * dy || 1;
    // closest point on this segment
    const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2));
    const off = Math.hypot(ax + dx * t - px, ay + dy * t - py);
    if (off < best.off)
      best = { d: r._cum[i - 1] + (r._cum[i] - r._cum[i - 1]) * t, off };
  }
  return best; // d = along route, off = distance from line
}

async function pollLive() {
  const { data, error } = await sb
    .from("bus_positions")
    .select("bus_id,route,lat,lng,passengers,updated_at");
  if (error) return console.warn("live buses:", error.message);

  const now = Date.now(),
    online = new Set(),
    liveRoutes = new Set();
  data.forEach((row) => {
    if (now - new Date(row.updated_at).getTime() > OFFLINE_AFTER_MS) return;
    // box sends route number, match by name
    const r = routes.find((x) => x.name === String(row.route) || x.id === row.route);
    if (!r) return;
    if (!r._line) prep(r);
    const { d } = projectOnRoute(r, row.lat, row.lng);

    let b = buses.find((x) => x.live && x.box === row.bus_id);
    if (!b) {
      b = { live: true, box: row.bus_id, bus_id: `${row.bus_id} · GPS`, dir: 1, d, cap: 60 };
      buses.push(b);
    } else if (Math.abs(d - b.d) > 15) {
      b.dir = d > b.d ? 1 : -1;
    }
    Object.assign(b, {
      route: r.id,
      d,
      lat: row.lat,
      lng: row.lng,
      passengers: row.passengers,
      time: row.updated_at,
    });
    online.add(row.bus_id);
    liveRoutes.add(r.id);
  });

  buses = buses.filter((b) => !b.live || online.has(b.box)); // drop offline
  buses.forEach((b) => {
    if (!b.live) b.hide = liveRoutes.has(b.route);
  });

  const badge = $("liveBadge");
  if (liveRoutes.size) {
    const names = routes.filter((r) => liveRoutes.has(r.id)).map((r) => r.name);
    badge.textContent = `🛰 Live ${names.join(", ")}`;
    badge.style.color = "var(--ok)";
  } else {
    badge.textContent = "Demo data";
    badge.style.color = "";
  }
  drawBuses();
  renderNext();
  renderBuses();
}

// staff: today's requests from db
async function pollStats() {
  const since = new Date();
  since.setHours(0, 0, 0, 0);
  const { data, error } = await sb
    .from("stop_requests")
    .select("route_id")
    .gte("time", since.toISOString())
    .limit(10000);
  if (error) return console.warn("stats:", error.message);
  demand = {};
  data.forEach((x) => (demand[x.route_id] = (demand[x.route_id] || 0) + 1));
  renderStats();
}

// save stop request
window.onStopRequest = (routeId, stopIndex) => {
  if (!sb || !me) return;
  sb.from("stop_requests")
    .insert({ route_id: routeId, stop_index: stopIndex })
    .then(({ error }) => error && console.warn("request:", error.message));
};

// called from auth.js
window.startLive = (user) => {
  window.stopLive();
  if (window.loadForecast) loadForecast(true);
  pollLive();
  liveTimer = setInterval(pollLive, LIVE_EVERY_MS);
  if (["hokimiyat", "developer"].includes(user.role)) {
    pollStats();
    statsTimer = setInterval(pollStats, 15000);
  }
};
window.stopLive = () => {
  clearInterval(liveTimer);
  clearInterval(statsTimer);
  buses = buses.filter((b) => !b.live);
  buses.forEach((b) => (b.hide = false));
  if (window.loadForecast) loadForecast(true);
};
