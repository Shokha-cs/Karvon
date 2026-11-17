// supabase url + publishable key (public is ok, RLS protects data)
// never put the secret key here. empty = demo mode
window.KARVON_CONFIG = {
  SUPABASE_URL: "https://loyycxhifrdecdbvizbn.supabase.co",
  // edge function names = the end of their URL in supabase
  AI_FUNCTION: "ai-chat",
  TG_LOGIN_FUNCTION: "smart-api",
  SUPABASE_ANON_KEY: "sb_publishable_d1uigsXa4xDIQeDS2zcTkA_ZlrQepHA",
};
