import os
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, MenuButtonWebApp, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("🗺 Open bus map", web_app=WebAppInfo(url=WEBAPP_URL))]]
    assert update.message is not None
    await update.message.reply_text(
        "Salom! Avtobuslar qayerda, nechta odam bor va qachon kelishini xaritada ko'ring.",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )


async def post_init(app: Application):
    await app.bot.set_chat_menu_button(menu_button=MenuButtonWebApp("Map", WebAppInfo(url=WEBAPP_URL)))


app = Application.builder().token(TOKEN).post_init(post_init).build()
app.add_handler(CommandHandler("start", start))
app.run_polling()