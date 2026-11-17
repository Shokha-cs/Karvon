// AI chat window: sends the question + routes to the ai-chat edge function
const AI_FN = (window.KARVON_CONFIG || {}).AI_FUNCTION || "ai-chat";
const chatHistory = []; // { role: "user" | "model", text }
let chatBusy = false;

const SUGGESTIONS = [
  "Hozir 1-yo'nalish to'lami?",
  "Which bus is closest to me?",
  "Когда придёт автобус №2?",
  "When is route 3 least crowded?",
];

function addMsg(cls, text) {
  const el = document.createElement("div");
  el.className = "msg " + cls;
  el.textContent = text;
  $("chatLog").append(el);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
  return el;
}

function openChat() {
  $("chat").hidden = false;
  if (!$("chatLog").children.length)
    addMsg("ai", "Salom! 👋 Ask me anything about Fergana buses: which route to take, when the bus comes, how full it is.");
  setTimeout(() => $("chatInput").focus(), 50);
}
$("aiBtn").onclick = () => ($("chat").hidden ? openChat() : ($("chat").hidden = true));
$("chatClose").onclick = () => ($("chat").hidden = true);

$("chatSug").innerHTML = SUGGESTIONS.map((q) => `<button type="button">${esc(q)}</button>`).join("");
$("chatSug").onclick = (e) => {
  const b = e.target.closest("button");
  if (b) ask(b.textContent);
};
$("chatForm").onsubmit = (e) => {
  e.preventDefault();
  ask($("chatInput").value);
};

// what the AI needs to know about routes (names + stops with coords)
function routesForAI() {
  return routes.map((r) => ({
    name: r.name,
    title: r.title || "",
    buses: r.buses,
    interval: r.interval,
    stops: r._stops.map((s, i) => [stopName(r, i), +s[0].toFixed(5), +s[1].toFixed(5)]),
  }));
}

async function ask(q) {
  q = (q || "").trim();
  if (!q || chatBusy) return;
  $("chatInput").value = "";
  addMsg("user", q);
  if (!sb) return addMsg("ai err", "Demo mode: the AI works after login (Supabase not set up in config.js).");
  if (!me) return addMsg("ai err", "Please log in first to use the AI.");

  chatBusy = true;
  const typing = addMsg("ai typing", "Thinking…");
  const loc = meMarker ? meMarker.getLatLng() : null;
  const { data, error } = await sb.functions.invoke(AI_FN, {
    body: {
      question: q,
      routes: routesForAI(),
      location: loc ? [loc.lat, loc.lng] : null,
      history: chatHistory.slice(-6),
    },
  });
  typing.remove();
  chatBusy = false;

  let answer = data && data.answer;
  if (!answer) {
    let msg = (data && data.error) || (error && error.message) || "unknown error";
    // non-2xx: the real message is in the response body
    if (error && error.context && error.context.json)
      msg = await error.context.json().then((j) => j.error || msg).catch(() => msg);
    return addMsg("ai err", "⚠️ " + msg);
  }
  addMsg("ai", answer);
  chatHistory.push({ role: "user", text: q }, { role: "model", text: answer });
}
