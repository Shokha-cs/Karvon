# Karvon telegram bot
# /start, menu (location, settings, help), phone share, any other text = AI question
import os

import httpx
from dotenv import load_dotenv
from telegram import (BotCommand, InlineKeyboardButton, InlineKeyboardMarkup,
                      KeyboardButton, MenuButtonWebApp, ReplyKeyboardMarkup,
                      Update, WebAppInfo)
from telegram.constants import ChatAction
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, MessageHandler, filters)

load_dotenv()
import assistant  # noqa: E402  (after load_dotenv)
from texts import LANGS, labels, t  # noqa: E402

TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
# secret key, only in .env
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

HEADERS = {"apikey": SERVICE_KEY, "Content-Type": "application/json"}
if SERVICE_KEY.startswith("eyJ"):  # old jwt key
    HEADERS["Authorization"] = f"Bearer {SERVICE_KEY}"


async def db(method: str, path: str, **kw) -> httpx.Response:
    async with httpx.AsyncClient(timeout=10) as c:
        return await c.request(method, f"{SUPABASE_URL}/rest/v1/{path}", headers={**HEADERS, **kw.pop("headers", {})}, **kw)


async def save_user(tg_id: int, **fields) -> httpx.Response:
    # upsert into telegram_users (only the given columns change)
    r = await db("POST", "telegram_users?on_conflict=tg_id",
                 headers={"Prefer": "resolution=merge-duplicates"}, json={"tg_id": tg_id, **fields})
    if not r.is_success:
        print("telegram_users error:", r.status_code, r.text, "(re-run supabase/schema.sql?)")
    return r


async def get_user(tg_id: int) -> dict:
    r = await db("GET", f"telegram_users?tg_id=eq.{tg_id}&select=phone,lang,full_name")
    if not r.is_success:  # old table without lang/full_name
        r = await db("GET", f"telegram_users?tg_id=eq.{tg_id}&select=phone")
    rows = r.json() if r.is_success else []
    return rows[0] if rows else {}


async def get_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    ud = context.user_data
    if "lang" not in ud:
        ud["lang"] = (await get_user(update.effective_user.id)).get("lang")
    return ud["lang"]


async def lang_of(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    # saved language, else telegram's app language, else uzbek
    lang = await get_lang(update, context)
    if lang:
        return lang
    code = (update.effective_user.language_code or "")[:2]
    return code if code in LANGS else "uz"


# buttons
def map_button(lang: str) -> InlineKeyboardMarkup:
    # inline button, not keyboard: keyboard buttons don't send initData, so telegram login fails
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("open_map", lang), web_app=WebAppInfo(url=WEBAPP_URL))]])


def keyboard(lang: str, has_phone: bool) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(t("btn_loc", lang), request_location=True)],
        [KeyboardButton(t("btn_settings", lang)), KeyboardButton(t("btn_help", lang))],
    ]
    if not has_phone:
        rows.insert(0, [KeyboardButton(t("btn_phone", lang), request_contact=True)])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def lang_picker(after: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(name, callback_data=f"lang:{code}:{after}")]
                                 for code, name in LANGS.items()])


async def send_welcome(chat, update: Update, lang: str):
    phone = (await get_user(update.effective_user.id)).get("phone")
    await chat.send_message(t("welcome", lang), reply_markup=map_button(lang))
    await chat.send_message(t("menu_below" if phone else "share_phone", lang), reply_markup=keyboard(lang, bool(phone)))


# commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await get_lang(update, context)
    if not lang:  # first time: pick a language
        await update.message.reply_text("🌐 Tilni tanlang / Выберите язык / Choose language:",
                                        reply_markup=lang_picker("start"))
        return
    await send_welcome(update.effective_chat, update, lang)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await lang_of(update, context)
    await update.message.reply_text(t("help", lang), reply_markup=map_button(lang))


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    lang = await lang_of(update, context)
    user = update.effective_user
    tu = await get_user(user.id)
    r = await db("GET", f"profiles?telegram_id=eq.{user.id}&select=role,full_name,phone")
    prof = (r.json() or [{}])[0] if r.is_success and r.json() else {}
    text = t("settings", lang,
             name=tu.get("full_name") or prof.get("full_name") or user.full_name or t("not_set", lang),
             phone=tu.get("phone") or prof.get("phone") or t("not_set", lang),
             role=prof.get("role") or t("no_role", lang),
             language=LANGS[lang])
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(t("s_lang", lang), callback_data="set:lang")],
        [InlineKeyboardButton(t("s_name", lang), callback_data="set:name"),
         InlineKeyboardButton(t("s_phone", lang), callback_data="set:phone")],
        [InlineKeyboardButton(t("s_close", lang), callback_data="set:close")],
    ])
    if edit:
        await update.callback_query.edit_message_text(text, reply_markup=buttons)
    else:
        await update.message.reply_text(text, reply_markup=buttons)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = await lang_of(update, context)
    context.user_data.pop("await", None)
    phone = (await get_user(update.effective_user.id)).get("phone")
    await update.message.reply_text(t("cancelled", lang), reply_markup=keyboard(lang, bool(phone)))


async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await settings(update, context)


# inline button clicks
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")

    if parts[0] == "lang":  # lang:<code>:<start|set>
        code, after = parts[1], parts[2]
        context.user_data["lang"] = code
        await save_user(update.effective_user.id, lang=code)
        if after == "start":
            await q.edit_message_text(t("lang_set", code))
            await send_welcome(update.effective_chat, update, code)
        else:
            await settings(update, context, edit=True)
            phone = (await get_user(update.effective_user.id)).get("phone")
            # new keyboard in the new language
            await update.effective_chat.send_message(t("lang_set", code), reply_markup=keyboard(code, bool(phone)))
        return

    lang = await lang_of(update, context)
    action = parts[1]
    if action == "lang":
        await q.edit_message_text(t("choose_lang", lang), reply_markup=lang_picker("set"))
    elif action == "name":
        context.user_data["await"] = "name"
        await update.effective_chat.send_message(t("ask_name", lang))
    elif action == "phone":
        kb = ReplyKeyboardMarkup([[KeyboardButton(t("btn_phone", lang), request_contact=True)]],
                                 resize_keyboard=True, one_time_keyboard=True)
        await update.effective_chat.send_message(t("ask_phone", lang), reply_markup=kb)
    elif action == "close":
        await q.delete_message()


# phone shared
async def got_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, user = update.message, update.effective_user
    lang = await lang_of(update, context)
    if msg.contact.user_id != user.id:  # only their own number
        await msg.reply_text(t("phone_not_yours", lang), reply_markup=keyboard(lang, False))
        return
    phone = msg.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    r = await save_user(user.id, phone=phone, first_name=user.first_name, username=user.username)
    if not r.is_success:
        await msg.reply_text(t("save_error", lang, code=r.status_code))
        return
    # also update profile if it exists
    await db("PATCH", f"profiles?telegram_id=eq.{user.id}", json={"phone": phone})
    await msg.reply_text(t("phone_saved", lang, phone=phone), reply_markup=keyboard(lang, True))
    await msg.reply_text(t("map_hint", lang), reply_markup=map_button(lang))


# location shared
async def got_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    context.user_data["loc"] = (msg.location.latitude, msg.location.longitude, msg.date.timestamp())
    lang = await lang_of(update, context)
    await ai_reply(update, context, t("near_me_q", lang))


# any text: name being changed, a menu button, or a question for the AI
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    lang = await lang_of(update, context)

    if context.user_data.get("await") == "name":
        if not 2 <= len(text) <= 60:
            await update.message.reply_text(t("name_bad", lang))
            return
        context.user_data.pop("await")
        r = await save_user(update.effective_user.id, full_name=text)
        if not r.is_success:
            await update.message.reply_text(t("save_error", lang, code=r.status_code))
            return
        await db("PATCH", f"profiles?telegram_id=eq.{update.effective_user.id}", json={"full_name": text})
        await update.message.reply_text(t("name_saved", lang, name=text))
        return

    if text in labels("btn_settings"):
        await settings(update, context)
    elif text in labels("btn_help"):
        await help_cmd(update, context)
    else:
        await ai_reply(update, context, text)


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = " ".join(context.args or [])
    if not q:
        await update.message.reply_text(t("ask_usage", await lang_of(update, context)))
        return
    await ai_reply(update, context, q)


async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str):
    msg, user = update.message, update.effective_user
    lang = await lang_of(update, context)
    stop = assistant.allowed(user.id)
    if stop:
        await msg.reply_text(t(stop, lang))
        return
    await context.bot.send_chat_action(msg.chat_id, ChatAction.TYPING)
    # ignore location older than 30 min
    loc = context.user_data.get("loc")
    where = loc[:2] if loc and msg.date.timestamp() - loc[2] < 30 * 60 else None
    step = "supabase"
    try:
        data = await assistant.build_context(db, where)
        step = "gemini"
        answer = await assistant.ask(question, data, lang)
    except assistant.AssistantError as e:
        answer = t(str(e), lang)
    except Exception as e:  # keep bot running
        print(f"assistant error ({step}):", repr(e))
        answer = t("error", lang)
    await msg.reply_text(answer)


async def post_init(app: Application):
    await app.bot.set_chat_menu_button(menu_button=MenuButtonWebApp("Map", WebAppInfo(url=WEBAPP_URL)))
    # "/" command list, per app language
    cmds = {
        "en": [("start", "Start / open the map"), ("settings", "Language, name, phone"), ("help", "What I can do"), ("ask", "Ask the AI")],
        "ru": [("start", "Старт / открыть карту"), ("settings", "Язык, имя, телефон"), ("help", "Что я умею"), ("ask", "Спросить AI")],
        "uz": [("start", "Boshlash / xaritani ochish"), ("settings", "Til, ism, telefon"), ("help", "Nima qila olaman"), ("ask", "AI ga savol")],
    }
    await app.bot.set_my_commands([BotCommand(c, d) for c, d in cmds["en"]])
    for code in ("ru", "uz"):
        await app.bot.set_my_commands([BotCommand(c, d) for c, d in cmds[code]], language_code=code)


app = Application.builder().token(TOKEN).post_init(post_init).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("settings", settings))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("me", me))
app.add_handler(CommandHandler("ask", ask_cmd))
app.add_handler(CommandHandler("cancel", cancel))
app.add_handler(CallbackQueryHandler(on_button))
app.add_handler(MessageHandler(filters.CONTACT, got_contact))
app.add_handler(MessageHandler(filters.LOCATION, got_location))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
app.run_polling()
