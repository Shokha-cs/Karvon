"""Fergana Bus Telegram bot.

/start  -> buttons: "Share my phone number" and "Open bus map"
contact -> saves the phone number in Supabase (telegram_users + profiles)
/me     -> shows your phone and role

Login itself happens when the person opens the map (Mini App): the page sends
Telegram's signed data to the telegram-login function, which logs them in.
"""
import os

import httpx
from dotenv import load_dotenv
from telegram import (KeyboardButton, MenuButtonWebApp, ReplyKeyboardMarkup,
                      Update, WebAppInfo)
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

load_dotenv()
TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
# secret / service_role key: the bot is a server, it may write to protected tables.
# NEVER put this key in config.js or on GitHub.
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

HEADERS = {"apikey": SERVICE_KEY, "Content-Type": "application/json"}
if SERVICE_KEY.startswith("eyJ"):  # old-style JWT key also wants this header
    HEADERS["Authorization"] = f"Bearer {SERVICE_KEY}"


def keyboard(has_phone: bool) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton("🗺 Open bus map", web_app=WebAppInfo(url=WEBAPP_URL))]]
    if not has_phone:
        rows.insert(0, [KeyboardButton("📱 Share my phone number", request_contact=True)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


async def db(method: str, path: str, **kw) -> httpx.Response:
    async with httpx.AsyncClient(timeout=10) as c:
        return await c.request(method, f"{SUPABASE_URL}/rest/v1/{path}", headers={**HEADERS, **kw.pop("headers", {})}, **kw)


async def saved_phone(tg_id: int):
    r = await db("GET", f"telegram_users?tg_id=eq.{tg_id}&select=phone")
    rows = r.json() if r.is_success else []
    return rows[0]["phone"] if rows else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert update.message is not None and update.effective_user is not None
    phone = await saved_phone(update.effective_user.id)
    text = "Salom! Avtobuslar qayerda, nechta odam bor va qachon kelishini xaritada ko'ring."
    if not phone:
        text += "\n\n📱 Log in with your phone number: press the button below."
    await update.message.reply_text(text, reply_markup=keyboard(bool(phone)))


async def got_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user = update.message, update.effective_user
    assert msg is not None and msg.contact is not None and user is not None
    # people can send someone else's contact card; only accept their own number
    if msg.contact.user_id != user.id:
        await msg.reply_text("Please share YOUR number with the button below.", reply_markup=keyboard(False))
        return
    phone = msg.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    # 1. remember phone for this Telegram account (insert or update)
    r = await db(
        "POST",
        "telegram_users?on_conflict=tg_id",
        headers={"Prefer": "resolution=merge-duplicates"},
        json={"tg_id": user.id, "phone": phone, "first_name": user.first_name, "username": user.username},
    )
    if not r.is_success:
        await msg.reply_text(f"⚠️ Could not save your number ({r.status_code}). Try again later.")
        print("telegram_users error:", r.status_code, r.text)
        return
    # 2. if they already opened the map before, put the phone on their profile too
    await db("PATCH", f"profiles?telegram_id=eq.{user.id}", json={"phone": phone})

    await msg.reply_text(
        f"✅ You're registered with {phone}.\nOpen the map — you'll be logged in automatically.",
        reply_markup=keyboard(True),
    )


async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert update.message is not None and update.effective_user is not None
    r = await db("GET", f"profiles?telegram_id=eq.{update.effective_user.id}&select=role,phone,full_name")
    rows = r.json() if r.is_success else []
    if not rows:
        phone = await saved_phone(update.effective_user.id)
        await update.message.reply_text(f"Not logged in yet. Open the map once.\nPhone: {phone or 'not shared'}")
        return
    p = rows[0]
    await update.message.reply_text(f"👤 {p['full_name'] or ''}\nRole: {p['role']}\nPhone: {p['phone'] or 'not shared'}")


async def post_init(app: Application):
    await app.bot.set_chat_menu_button(menu_button=MenuButtonWebApp("Map", WebAppInfo(url=WEBAPP_URL)))


app = Application.builder().token(TOKEN).post_init(post_init).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("me", me))
app.add_handler(MessageHandler(filters.CONTACT, got_contact))
app.run_polling()
