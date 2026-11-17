// crowding forecast: avg passengers per hour (crowd_forecast in db, last 28 days)
// no data yet -> example pattern, labeled on screen

const FC_CAP = 60; // = 100% full
const FC_MIN_SAMPLES = 30; // less = use example
const FC_FIRST = 6, // chart hours
  FC_LAST = 22;
const FC_REFRESH_MS = 5 * 60 * 1000;

let fcData = {}; // route name -> { hours[24], n, example }
let fcLoadedAt = 0,
  fcLoading = null,
  fcWasLoggedIn = false;

// hour in fergana
function fcHour() {
  const h = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Tashkent",
    hour: "numeric",
    hourCycle: "h23",
  }).format(new Date());
  return parseInt(h, 10) % 24;
}
const fcHH = (h) => String(h).padStart(2, "0") + ":00";

// example pattern (only when no real data)
function fcExample(name) {
  let seed = 0;
  for (const c of String(name)) seed = (seed * 31 + c.charCodeAt(0)) % 997;
  const shift = (seed % 3) - 1,
    scale = 0.85 + (seed % 5) * 0.05;
  const bump = (h, mid, width, height) =>
    height * Math.exp(-((h - mid) ** 2) / (2 * width * width));
  return Array.from({ length: 24 }, (_, h) => {
    if (h < FC_FIRST || h > FC_LAST) return null;
    const p =
      8 +
      bump(h, 8 + shift * 0.5, 1.2, 44) + // morning rush
      bump(h, 13, 2, 14) + // lunch
      bump(h, 18 + shift * 0.5, 1.5, 38); // evening rush
    return { avg: Math.round(Math.min(FC_CAP, p * scale)), n: 0 };
  });
}

async function loadForecast(force) {
  const loggedIn = !!(typeof sb !== "undefined" && sb && typeof me !== "undefined" && me);
  if (!force && loggedIn === fcWasLoggedIn && Date.now() - fcLoadedAt < FC_REFRESH_MS) return;
  if (fcLoading) return fcLoading;
  fcLoading = (async () => {
    await null; // so fcLoading is set first
    const real = {};
    if (loggedIn) {
      const { data, error } = await sb.rpc("crowd_forecast", { p_route: null });
      if (error) console.warn("forecast:", error.message);
      else
        data.forEach((row) => {
          const r = (real[row.route] ||= { hours: Array(24).fill(null), n: 0 });
          r.hours[row.hour] = { avg: +row.avg_passengers, n: +row.samples };
          r.n += +row.samples;
        });
    }
    fcData = {};
    routes.forEach((r) => {
      const x = real[r.name];
      fcData[r.name] =
        x && x.n >= FC_MIN_SAMPLES
          ? { ...x, example: false }
          : { hours: fcExample(r.name), n: x ? x.n : 0, example: true };
    });
    fcLoadedAt = Date.now();
    fcWasLoggedIn = loggedIn;
  })().finally(() => {
    fcLoading = null;
    renderCrowd();
    renderFcStats();
  });
  return fcLoading;
}

// bar per hour
function fcBars(f, now, compact) {
  const cols = [];
  for (let h = FC_FIRST; h <= FC_LAST; h++) {
    const v = f.hours[h],
      load = v ? Math.min(1, v.avg / FC_CAP) : 0;
    const title = v
      ? `${fcHH(h)} · ~${Math.round(load * 100)}% full`
      : `${fcHH(h)} · no data yet`;
    cols.push(
      `<div class="fcol${h === now ? " now" : ""}${v ? "" : " nodata"}" title="${title}">` +
        `<i style="height:${v ? Math.max(6, load * 100) : 6}%;background:${v ? loadColor(load) : "var(--line)"}"></i>` +
        (compact ? "" : `<span>${h % 3 === 0 ? h : ""}</span>`) +
        `</div>`,
    );
  }
  return `<div class="fcbars${compact ? " compact" : ""}">${cols.join("")}</div>`;
}

function fcSource(f) {
  return f.example
    ? `<div class="fcnote warn">Example pattern, not real data yet. The real forecast appears after the GPS boxes have sent ${FC_MIN_SAMPLES}+ readings${f.n ? ` (${f.n} so far)` : ""}.</div>`
    : `<div class="fcnote">Based on ${f.n.toLocaleString()} readings from the GPS boxes, last 4 weeks.</div>`;
}

// live tab card
function renderCrowd() {
  const el = document.getElementById("crowdCard");
  if (!el) return;
  const r = routeById(selRoute);
  if (!r) return (el.hidden = true);
  el.hidden = false;
  const f = fcData[r.name];
  if (!f) {
    el.innerHTML = `<div class="cardhead"><h2>Crowding forecast</h2></div><div class="empty small">Loading…</div>`;
    if (!fcLoading) loadForecast(true); // routes changed
    return;
  }
  const now = fcHour(),
    cur = f.hours[now];
  const pct = (v) => Math.round(Math.min(1, v.avg / FC_CAP) * 100);

  // best hour in next 3h
  let best = null;
  for (let h = now; h <= Math.min(23, now + 3); h++) {
    const v = f.hours[h];
    if (v && (!best || v.avg < best.v.avg)) best = { h, v };
  }
  const known = f.hours
    .map((v, h) => ({ v, h }))
    .filter((x) => x.v && x.h >= FC_FIRST && x.h <= FC_LAST);
  const busiest = known.reduce((a, x) => (!a || x.v.avg > a.v.avg ? x : a), null);

  let line;
  if (cur) {
    const load = Math.min(1, cur.avg / FC_CAP);
    line = `At ${fcHH(now)} route ${esc(r.name)} is usually <b class="${loadClass(load)}">${pct(cur)}% full</b> (${loadText(load).toLowerCase()}).`;
  } else line = `No readings for ${fcHH(now)} yet.`;
  const tips = [];
  if (best && best.h !== now)
    tips.push(`Less crowded at <b>${fcHH(best.h)}</b> (~${pct(best.v)}%)`);
  if (busiest) tips.push(`Busiest at <b>${fcHH(busiest.h)}</b> (~${pct(busiest.v)}%)`);

  el.innerHTML =
    `<div class="cardhead"><h2>Crowding forecast</h2><span class="tag">${f.example ? "Example" : "From GPS data"}</span></div>` +
    `<div class="small">${line}</div>` +
    fcBars(f, now) +
    (tips.length ? `<div class="small muted">${tips.join(" · ")}</div>` : "") +
    fcSource(f);
}

// hokimiyat: when to add buses
function renderFcStats() {
  const el = document.getElementById("fcList");
  if (!el) return;
  if (!routes.length) return (el.innerHTML = "");
  const now = fcHour();
  el.innerHTML = routes
    .map((r) => {
      const f = fcData[r.name];
      if (!f) return "";
      // 75%+ hours -> ranges
      const ranges = [];
      for (let h = 0; h < 24; h++) {
        const v = f.hours[h];
        if (v && v.avg / FC_CAP >= 0.75) {
          const last = ranges[ranges.length - 1];
          if (last && last[1] === h - 1) last[1] = h;
          else ranges.push([h, h]);
        }
      }
      const advice = ranges.length
        ? `<span class="flag">⚠ Add buses ${ranges.map(([a, b]) => `${fcHH(a)}–${fcHH(b + 1)}`).join(", ")}</span>`
        : `<span class="small ok">✓ Enough buses all day</span>`;
      return `<div class="rstat">
        <div class="top"><b><span class="dot" style="--c:${r.color};margin-right:6px"></span>Route ${esc(r.name)}</b>${f.example ? `<span class="tag">Example</span>` : ""}</div>
        ${fcBars(f, now, true)}
        <div>${advice}</div>
      </div>`;
    })
    .join("");
  const anyExample = routes.some((r) => fcData[r.name] && fcData[r.name].example);
  if (anyExample)
    el.innerHTML += `<div class="fcnote warn">Routes marked “Example” have no real GPS data yet. Their pattern is only an illustration.</div>`;
}

// refresh every minute
setInterval(() => {
  loadForecast();
  renderCrowd();
  renderFcStats();
}, 60 * 1000);
document.addEventListener("DOMContentLoaded", () => loadForecast(true));
