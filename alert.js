// arrival alert: "tell me when my bus is 2 min away"
const ALERT_SEC = 120;
let arrAlert = null; // { route, stop, dir }

function alertBtn(r, stop, dir) {
  const on = arrAlert && arrAlert.route === r.id && arrAlert.stop === stop && arrAlert.dir === dir;
  return `<button class="btn alertbtn${on ? " on" : ""}" data-dir="${dir}">${on ? "🔔 Alert on · tap to cancel" : "🔔 Alert me 2 min before"}</button>`;
}

document.getElementById("nextCard").addEventListener("click", (e) => {
  const btn = e.target.closest(".alertbtn");
  if (!btn) return;
  const dir = +btn.dataset.dir;
  const same = arrAlert && arrAlert.route === selRoute && arrAlert.stop === selStop && arrAlert.dir === dir;
  arrAlert = same ? null : { route: selRoute, stop: selStop, dir };
  // ask once for phone notifications (not in telegram)
  if (arrAlert && !inTelegram && "Notification" in window && Notification.permission === "default")
    Notification.requestPermission();
  renderNext();
});

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.25, 0.5].forEach((t) => {
      const o = ctx.createOscillator(),
        g = ctx.createGain();
      o.frequency.value = 880;
      g.gain.value = 0.15;
      o.connect(g).connect(ctx.destination);
      o.start(ctx.currentTime + t);
      o.stop(ctx.currentTime + t + 0.15);
    });
  } catch {}
}

function showBanner(text) {
  let el = document.getElementById("arrBanner");
  if (!el) {
    el = document.createElement("div");
    el.id = "arrBanner";
    el.onclick = () => (el.hidden = true);
    document.body.append(el);
  }
  el.textContent = text;
  el.hidden = false;
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.hidden = true), 15000);
}

function fireAlert(r, s, x) {
  const text = `🚌 Bus ${x.b.bus_id} (route ${r.name}) arrives at ${stopName(r, arrAlert.stop)} in about ${fmtMin(x.t)} min!`;
  arrAlert = null;
  showBanner(text);
  beep();
  if (navigator.vibrate) navigator.vibrate([300, 150, 300]);
  if (inTelegram && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
  if (!inTelegram && "Notification" in window && Notification.permission === "granted" && document.hidden)
    new Notification("Karvon", { body: text });
  renderNext();
}

// check every second
setInterval(() => {
  if (!arrAlert) return;
  const r = routeById(arrAlert.route);
  if (!r) return (arrAlert = null);
  const s = r._stopAt[arrAlert.stop];
  const next = visible()
    .filter((b) => b.route === r.id)
    .map((b) => ({ b, ...arrival(b, r, s) }))
    .filter((x) => x.dir === arrAlert.dir)
    .sort((a, c) => a.t - c.t)[0];
  if (next && next.t <= ALERT_SEC) fireAlert(r, s, next);
}, 1000);
