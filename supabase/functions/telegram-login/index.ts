// telegram-login: check initData signature, return login token
// secret: BOT_TOKEN. verify JWT = off

import { createClient } from "npm:@supabase/supabase-js@2";

const BOT_TOKEN = Deno.env.get("BOT_TOKEN")!;
const admin = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  { auth: { persistSession: false } },
);

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });

async function hmac(key: Uint8Array, data: string): Promise<Uint8Array> {
  const k = await crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", k, new TextEncoder().encode(data)));
}
const hex = (b: Uint8Array) => [...b].map((x) => x.toString(16).padStart(2, "0")).join("");

// telegram docs: hmac check of initData
export async function checkTelegram(initData: string, botToken: string) {
  const p = new URLSearchParams(initData);
  const hash = p.get("hash");
  if (!hash) return null;
  p.delete("hash");
  const check = [...p.entries()].map(([k, v]) => `${k}=${v}`).sort().join("\n");
  const secret = await hmac(new TextEncoder().encode("WebAppData"), botToken);
  if (hex(await hmac(secret, check)) !== hash) return null; // fake
  if (Date.now() / 1000 - Number(p.get("auth_date")) > 24 * 3600) return null; // too old
  return JSON.parse(p.get("user") || "null");
}

if (import.meta.main) Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  try {
    const { initData } = await req.json();
    const tg = await checkTelegram(initData || "", BOT_TOKEN);
    if (!tg) return json({ error: "Telegram data is invalid or expired" }, 401);

    // hidden email tg<id>@telegram.local
    const email = `tg${tg.id}@telegram.local`;
    const name = [tg.first_name, tg.last_name].filter(Boolean).join(" ");

    // create account (already exists = ok)
    const created = await admin.auth.admin.createUser({
      email,
      email_confirm: true,
      user_metadata: { full_name: name },
    });
    if (created.error && !/already|registered|exists/i.test(created.error.message)) throw created.error;

    // login token
    const { data: link, error } = await admin.auth.admin.generateLink({ type: "magiclink", email });
    if (error) throw error;
    const userId = link.user.id;

    // save tg id + phone
    const { data: tu } = await admin.from("telegram_users").select("phone").eq("tg_id", tg.id).maybeSingle();
    const update: Record<string, unknown> = { telegram_id: tg.id, full_name: name };
    if (tu?.phone) update.phone = tu.phone;
    await admin.from("profiles").update(update).eq("id", userId);
    const { data: prof } = await admin.from("profiles").select("role").eq("id", userId).single();

    // notify in bot
    await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_id: tg.id,
        text: `🔐 You logged in to Fergana Bus as ${prof?.role ?? "passenger"}.`,
      }),
    }).catch(() => {});

    return json({ token_hash: link.properties.hashed_token, role: prof?.role });
  } catch (e) {
    return json({ error: String((e as Error)?.message ?? e) }, 500);
  }
});
