# Fergana Bus bot: opens the map page inside Telegram as a Mini App.
# Setup: pip install -r requirements.txt
# Put BOT_TOKEN and WEBAPP_URL in a .env file (copy .env.example), then: python bot.py
import os
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, MenuButtonWebApp, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"]  # must be https


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("🗺 Open bus map", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        "Salom! Avtobuslar qayerda, nechta odam bor va qachon kelishini xaritada ko'ring.",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )


async def post_init(app: Application):
    # Also puts a "Map" button next to the chat input
    await app.bot.set_chat_menu_button(menu_button=MenuButtonWebApp("Map", WebAppInfo(url=WEBAPP_URL)))


app = Application.builder().token(TOKEN).post_init(post_init).build()
app.add_handler(CommandHandler("start", start))
app.run_polling()
