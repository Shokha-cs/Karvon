// Fill these from Supabase → Project Settings → API (or "API Keys").
// The anon / publishable key is SAFE to be public: the database rules
// (Row Level Security in supabase/schema.sql) decide what it can do.
// NEVER put the service_role / secret key here.
// Leave empty → the site runs in demo mode (no login, simulated buses).
window.KARVON_CONFIG = {
  SUPABASE_URL: "",
  SUPABASE_ANON_KEY: "",
};
