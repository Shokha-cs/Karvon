# Karvon telegram bot
# /start, phone share, /me, location, any text = AI question
import os

import httpx
from dotenv import load_dotenv
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      KeyboardButton, MenuButtonWebApp, ReplyKeyboardMarkup,
                      Update, WebAppInfo)
from telegram.constants import ChatAction
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

load_dotenv()
import assistant  # noqa: E402  (after load_dotenv)

TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
# secret key, only in .env
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

HEADERS = {"apikey": SERVICE_KEY, "Content-Type": "application/json"}
if SERVICE_KEY.startswith("eyJ"):  # old jwt key
    HEADERS["Authorization"] = f"Bearer {SERVICE_KEY}"


# map is NOT a keyboard button: those don't get initData, so telegram login fails
MAP_BUTTON = InlineKeyboardMarkup([[InlineKeyboardButton("🗺 Open bus map", web_app=WebAppInfo(url=WEBAPP_URL))]])


def keyboard(has_phone: bool) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton("📍 Send my location", request_location=True)]]
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
    text = (
        "Salom! Avtobuslar qayerda, nechta odam bor va qachon kelishini xaritada ko'ring.\n\n"
        "🤖 Menga savol ham bering, masalan:\n"
        "• Qaysi avtobus Mindanobodga boradi?\n"
        "• Hozir 1-yo'nalish to'lami?\n"
        "📍 Joylashuvingizni yuborsangiz, eng yaqin bekatni aytaman."
    )
    await update.message.reply_text(text, reply_markup=MAP_BUTTON)
    tip = "📱 Share your phone number to log in." if not phone else "👇"
    await update.message.reply_text(tip, reply_markup=keyboard(bool(phone)))


async def got_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user = update.message, update.effective_user
    assert msg is not None and msg.contact is not None and user is not None
    # only accept their own number
    if msg.contact.user_id != user.id:
        await msg.reply_text("Please share YOUR number with the button below.", reply_markup=keyboard(False))
        return
    phone = msg.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    # save phone (upsert)
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
    # also update profile if it exists
    await db("PATCH", f"profiles?telegram_id=eq.{user.id}", json={"phone": phone})

    await msg.reply_text(f"✅ You're registered with {phone}.", reply_markup=keyboard(True))
    await msg.reply_text("Open the map, you'll be logged in automatically:", reply_markup=MAP_BUTTON)


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


# AI assistant
async def got_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    assert msg is not None and msg.location is not None and context.user_data is not None
    context.user_data["loc"] = (msg.location.latitude, msg.location.longitude, msg.date.timestamp())
    await ai_reply(update, context, "Which bus stops are nearest to me, and which buses stop there?")


async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert update.message is not None
    await ai_reply(update, context, update.message.text or "")


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    assert update.message is not None
    q = " ".join(context.args or [])
    if not q:
        await update.message.reply_text("Write your question after /ask, e.g. /ask Which bus goes to the bazaar?")
        return
    await ai_reply(update, context, q)


async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str):
    msg, user = update.message, update.effective_user
    assert msg is not None and user is not None and context.user_data is not None
    stop = assistant.allowed(user.id)
    if stop:
        await msg.reply_text(stop)
        return
    await context.bot.send_chat_action(msg.chat_id, ChatAction.TYPING)
    # ignore location older than 30 min
    loc = context.user_data.get("loc")
    where = loc[:2] if loc and msg.date.timestamp() - loc[2] < 30 * 60 else None
    try:
        data = await assistant.build_context(db, where)
        answer = await assistant.ask(question, data)
    except assistant.AssistantError as e:
        answer = f"⚠️ {e}"
    except Exception as e:  # keep bot running
        print("assistant error:", repr(e))
        answer = "⚠️ Something went wrong. Please try again in a moment."
    await msg.reply_text(answer)


async def post_init(app: Application):
    await app.bot.set_chat_menu_button(menu_button=MenuButtonWebApp("Map", WebAppInfo(url=WEBAPP_URL)))


app = Application.builder().token(TOKEN).post_init(post_init).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("me", me))
app.add_handler(CommandHandler("ask", ask_cmd))
app.add_handler(MessageHandler(filters.CONTACT, got_contact))
app.add_handler(MessageHandler(filters.LOCATION, got_location))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat))
app.run_polling()
