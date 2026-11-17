// ai-chat: AI assistant for the website (same idea as assistant.py in the bot)
// secrets: GEMINI_API_KEY and/or ANTHROPIC_API_KEY (claude = backup), optional GEMINI_MODEL, CLAUDE_MODEL
// verify JWT = off (we check the user here)

import { createClient } from "npm:@supabase/supabase-js@2";

const admin = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  { auth: { persistSession: false } },
);
const GEMINI_KEY = Deno.env.get("GEMINI_API_KEY") ?? "";
const MODEL = Deno.env.get("GEMINI_MODEL") || "gemini-3.5-flash-lite";
const CLAUDE_KEY = Deno.env.get("ANTHROPIC_API_KEY") ?? "";
const CLAUDE_MODEL = Deno.env.get("CLAUDE_MODEL") || "claude-haiku-5-5";
const CAP = 60; // = 100% full
const OFFLINE_S = 120;

// same rules as assistant.py, keep both in sync
const PROMPT = `You are Karvon, the bus assistant for the city of Fergana, Uzbekistan.

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
- Reply in the passenger's language. Max 6 lines, plain text, no Markdown, no tables.`;

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

type Stop = [string, number, number]; // name, lat, lng
type Route = { name: string; title?: string; buses?: number; interval?: number; stops: Stop[] };

function dist(aLat: number, aLng: number, bLat: number, bLng: number) {
  const r = Math.PI / 180,
    dLat = (bLat - aLat) * r,
    dLng = (bLng - aLng) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(aLat * r) * Math.cos(bLat * r) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(h));
}

// rate limit per user (free key)
const usage = new Map<string, { last: number; day: string; n: number }>();
function limited(userId: string) {
  const now = Date.now(),
    day = new Date(now + 5 * 3600e3).toISOString().slice(0, 10);
  const u = usage.get(userId) ?? { last: 0, day, n: 0 };
  if (u.day !== day) Object.assign(u, { day, n: 0 });
  if (now - u.last < 4000) return "One question at a time, please 🙂";
  if (u.n >= 40) return "You've reached today's question limit. Try again tomorrow.";
  Object.assign(u, { last: now, n: u.n + 1 });
  usage.set(userId, u);
  return null;
}

async function buildContext(routes: Route[], loc: [number, number] | null) {
  const now = new Date(Date.now() + 5 * 3600e3); // fergana UTC+5
  const hour = now.getUTCHours();
  const day = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][now.getUTCDay()];
  const lines = [`Current time in Fergana: ${day} ${String(hour).padStart(2, "0")}:${String(now.getUTCMinutes()).padStart(2, "0")}.`, ""];

  // routes
  lines.push("ROUTES (stops in order, buses go both ways):");
  for (const r of routes) {
    const info = [`${r.buses ?? "?"} buses`];
    if (r.interval) info.push(`a bus every ~${r.interval} min`);
    lines.push(`Route ${r.name} (${r.title || "no title"}; ${info.join(", ")}):`);
    lines.push("  " + r.stops.map((s) => s[0]).join(" → "));
  }
  lines.push("");

  // live gps buses
  const byName = new Map(routes.map((r) => [String(r.name), r]));
  const { data: buses } = await admin.from("bus_positions").select("bus_id,route,lat,lng,passengers,updated_at");
  const live: string[] = [];
  for (const b of buses ?? []) {
    const age = (Date.now() - new Date(b.updated_at).getTime()) / 1000;
    const r = byName.get(String(b.route));
    if (age > OFFLINE_S || !r) continue;
    let best: [number, string] | null = null;
    for (const s of r.stops) {
      const d = dist(b.lat, b.lng, s[1], s[2]);
      if (!best || d < best[0]) best = [d, s[0]];
    }
    const f = b.passengers / CAP;
    const word = f > 0.8 ? "very full" : f > 0.5 ? "some seats" : "plenty of seats";
    live.push(`Bus ${b.bus_id} on route ${r.name}: near stop "${best?.[1]}" (~${Math.round(best?.[0] ?? 0)} m), ${b.passengers}/${CAP} passengers (${word}), reported ${Math.round(age)} s ago.`);
  }
  lines.push("LIVE BUSES WITH GPS (right now):");
  lines.push(...(live.length ? live : ["None online right now. Use the timetable data above."]));
  lines.push("");

  // forecast, now + 3h
  const { data: fc } = await admin.rpc("crowd_forecast");
  lines.push("USUAL CROWDING (average from the GPS boxes, last 4 weeks):");
  let added = 0;
  for (const r of routes) {
    const parts: string[] = [];
    for (let h = hour; h <= Math.min(23, hour + 3); h++) {
      const row = (fc ?? []).find((x: { route: string; hour: number }) => String(x.route) === String(r.name) && x.hour === h);
      if (row && row.samples >= 5) parts.push(`${String(h).padStart(2, "0")}:00 ~${Math.round(Math.min(1, row.avg_passengers / CAP) * 100)}% full`);
    }
    if (parts.length) {
      lines.push(`Route ${r.name}: ${parts.join(", ")}`);
      added++;
    }
  }
  if (!added) lines.push("Not enough data collected yet.");
  lines.push("");

  // user location if shared
  if (loc) {
    const near = routes
      .flatMap((r) => r.stops.map((s) => ({ d: dist(loc[0], loc[1], s[1], s[2]), route: r.name, name: s[0] })))
      .sort((a, b) => a.d - b.d)
      .slice(0, 4);
    lines.push("PASSENGER'S LOCATION: shared. Nearest stops:");
    near.forEach((x) => lines.push(`  "${x.name}" on route ${x.route}, ~${Math.round(x.d)} m away`));
  } else lines.push('PASSENGER\'S LOCATION: not shared (they can press "📍 Near me").');
  return lines.join("\n");
}

type Msg = { role: string; parts: { text: string }[] };

async function post(name: string, url: string, headers: Record<string, string>, body: unknown) {
  const t0 = Date.now();
  let r: Response;
  try {
    r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(60000),
    });
  } catch (e) {
    console.log(name, "network/timeout", e);
    throw new Error("The AI took too long to answer. Try again.");
  }
  console.log(`${name} ${r.status} in ${(Date.now() - t0) / 1000}s`);
  if (r.status === 429 || r.status === 529) throw new Error("The AI is busy right now. Try again in a minute.");
  if (!r.ok) {
    console.log(name, "error", await r.text());
    throw new Error("The AI had a problem. Try again later.");
  }
  return await r.json();
}

async function askGemini(system: string, history: Msg[], question: string) {
  const out = await post("gemini", `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`, { "x-goog-api-key": GEMINI_KEY }, {
    system_instruction: { parts: [{ text: system }] },
    contents: [...history, { role: "user", parts: [{ text: question }] }],
    generationConfig: { temperature: 0.3, maxOutputTokens: 2048 },
  });
  const text = (out?.candidates?.[0]?.content?.parts ?? [])
    .filter((p: { thought?: boolean }) => !p.thought)
    .map((p: { text?: string }) => p.text ?? "")
    .join("")
    .trim();
  if (!text) throw new Error("Sorry, I couldn't answer that. Try asking another way.");
  return text;
}

async function askClaude(system: string, history: Msg[], question: string) {
  const out = await post("claude", "https://api.anthropic.com/v1/messages", { "x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01" }, {
    model: CLAUDE_MODEL,
    max_tokens: 1024,
    temperature: 0.3,
    system,
    messages: [
      ...history.map((m) => ({ role: m.role === "model" ? "assistant" : "user", content: m.parts[0].text })),
      { role: "user", content: question },
    ],
  });
  const text = (out?.content ?? [])
    .filter((b: { type: string }) => b.type === "text")
    .map((b: { text: string }) => b.text)
    .join("")
    .trim();
  if (!text) throw new Error("Sorry, I couldn't answer that. Try asking another way.");
  return text;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    // must be logged in
    const token = (req.headers.get("Authorization") ?? "").replace("Bearer ", "");
    const { data: auth } = await admin.auth.getUser(token);
    if (!auth?.user) return json({ error: "Please log in to use the AI." }, 401);
    const stop = limited(auth.user.id);
    if (stop) return json({ error: stop }, 429);
    if (!GEMINI_KEY && !CLAUDE_KEY) return json({ error: "AI is not set up yet (no GEMINI_API_KEY or ANTHROPIC_API_KEY secret)." }, 500);

    const body = await req.json();
    const question = String(body.question ?? "").slice(0, 500).trim();
    if (!question) return json({ error: "Empty question" }, 400);
    const routes: Route[] = (Array.isArray(body.routes) ? body.routes : []).slice(0, 20).map((r: Route) => ({
      ...r,
      stops: (r.stops ?? []).slice(0, 400),
    }));
    const loc = Array.isArray(body.location) && body.location.length === 2 ? (body.location as [number, number]) : null;

    // earlier messages so follow-up questions work
    const history = (Array.isArray(body.history) ? body.history : [])
      .slice(-6)
      .map((m: { role: string; text: string }) => ({
        role: m.role === "model" ? "model" : "user",
        parts: [{ text: String(m.text).slice(0, 1000) }],
      }));
    while (history.length && history[0].role !== "user") history.shift();

    const system = PROMPT + "\n\nDATA:\n" + (await buildContext(routes, loc));
    let answer = "";
    let fail = "The AI had a problem. Try again later.";
    if (GEMINI_KEY) {
      try {
        answer = await askGemini(system, history, question);
      } catch (e) {
        fail = String((e as Error).message);
        console.log("gemini failed:", fail);
      }
    }
    if (!answer && CLAUDE_KEY) {
      try {
        answer = await askClaude(system, history, question);
      } catch (e) {
        fail = String((e as Error).message);
        console.log("claude failed:", fail);
      }
    }
    if (!answer) return json({ error: fail }, 502);
    return json({ answer: answer.slice(0, 3500) });
  } catch (e) {
    console.log("ai-chat error", e);
    return json({ error: String((e as Error)?.message ?? e) }, 500);
  }
});
