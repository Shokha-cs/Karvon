// login + roles (supabase auth, session saved in browser)

const cfg = window.KARVON_CONFIG || {};
const sb =
  cfg.SUPABASE_URL && cfg.SUPABASE_ANON_KEY && window.supabase
    ? window.supabase.createClient(cfg.SUPABASE_URL, cfg.SUPABASE_ANON_KEY)
    : null; // no config = demo mode

let me = null; // { id, email, full_name, phone, role }
let signingUp = false;

// helpers
function authMsg(text, isError) {
  $("authMsg").textContent = text || "";
  $("authMsg").className = "small" + (isError ? " err" : "");
}
function showLogin(text, isError) {
  $("auth").hidden = false;
  $("authForm").hidden = false;
  $("userBtn").hidden = true;
  $("tgLogin").hidden = !inTelegram;
  $("googleLogin").hidden = inTelegram; // google blocked in telegram
  authMsg(text, isError);
}
function showLoading(text) {
  $("auth").hidden = false;
  $("authForm").hidden = true;
  authMsg(text);
}

// roles
function applyRole(role) {
  const allowed = {
    passenger: ["live"],
    hokimiyat: ["live", "stats"],
    developer: ["live", "stats", "edit"],
  }[role] || ["live"];
  document.querySelectorAll(".tabs button").forEach((b) => {
    b.hidden = !allowed.includes(b.dataset.tab);
  });
  // not allowed tab -> back to live
  if (!allowed.includes(tab)) document.querySelector('.tabs [data-tab="live"]').click();
  // requests come from db now
  $("resetStats").hidden = true;
}

// after login
async function afterLogin(session) {
  showLoading("Loading your account…");
  const { data: prof, error } = await sb
    .from("profiles")
    .select("id,email,full_name,phone,role")
    .eq("id", session.user.id)
    .maybeSingle();
  if (error) console.warn("profile", error.message);
  me = prof || { id: session.user.id, email: session.user.email, role: "passenger" };
  applyRole(me.role);
  $("auth").hidden = true;
  $("userBtn").hidden = false;
  if (window.startLive) window.startLive(me);
}

// email
$("aSwitch").onclick = () => {
  signingUp = !signingUp;
  $("aName").hidden = !signingUp;
  $("aSubmit").textContent = signingUp ? "Create account" : "Log in";
  $("aSwitch").textContent = signingUp ? "Have an account? Log in" : "No account? Sign up";
  $("aPass").autocomplete = signingUp ? "new-password" : "current-password";
  authMsg("");
};
$("aSubmit").onclick = async () => {
  const email = $("aEmail").value.trim(),
    password = $("aPass").value;
  if (!email || password.length < 6)
    return authMsg("Enter your email and a password of at least 6 characters.", true);
  authMsg(signingUp ? "Creating account…" : "Logging in…");
  if (signingUp) {
    const { data, error } = await sb.auth.signUp({
      email,
      password,
      options: { data: { full_name: $("aName").value.trim() } },
    });
    if (error) return authMsg(error.message, true);
    // no session if confirm email is on
    if (!data.session) authMsg("Account created. Check your email to confirm, then log in.");
  } else {
    const { error } = await sb.auth.signInWithPassword({ email, password });
    if (error) return authMsg(error.message, true);
  }
  // onAuthStateChange handles the rest
};

// google
$("googleLogin").onclick = async () => {
  const { error } = await sb.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: location.origin + location.pathname },
  });
  if (error) authMsg(error.message, true);
};

// telegram: server function checks initData, returns login token
async function telegramLogin() {
  showLoading("Logging in with Telegram…");
  const { data, error } = await sb.functions.invoke(cfg.TG_LOGIN_FUNCTION || "smart-api", {
    body: { initData: tg.initData },
  });
  if (error || !data || !data.token_hash)
    return showLogin("Telegram login failed: " + ((data && data.error) || (error && error.message) || "unknown error"), true);
  const res = await sb.auth.verifyOtp({ token_hash: data.token_hash, type: "magiclink" });
  if (res.error) showLogin(res.error.message, true);
}
$("tgLogin").onclick = telegramLogin;

// account / logout
$("userBtn").onclick = () => {
  if (!me) return;
  const who = me.full_name || me.email || me.phone || "you";
  const text = `${who}\nRole: ${me.role}${me.phone ? "\nPhone: " + me.phone : ""}\n\nLog out?`;
  const out = () => sb.auth.signOut();
  if (inTelegram && tg.showConfirm) tg.showConfirm(text, (ok) => ok && out());
  else if (confirm(text)) out();
};

// start
function startAuth() {
  if (!sb) return; // demo mode
  showLoading("Loading…");
  let triedTelegram = false;
  // page load, login, logout
  sb.auth.onAuthStateChange((event, session) => {
    // setTimeout: dont call supabase inside this callback
    setTimeout(() => {
      if (event === "TOKEN_REFRESHED" || event === "USER_UPDATED") return;
      if (session) {
        if (!me || me.id !== session.user.id) afterLogin(session);
        return;
      }
      me = null;
      if (window.stopLive) window.stopLive();
      if (inTelegram && !triedTelegram && event === "INITIAL_SESSION") {
        triedTelegram = true;
        telegramLogin(); // auto login in telegram
      } else showLogin(event === "SIGNED_OUT" ? "You logged out." : "");
    }, 0);
  });
}
document.addEventListener("DOMContentLoaded", startAuth);
