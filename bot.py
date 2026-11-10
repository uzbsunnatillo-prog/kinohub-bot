
import os
import sqlite3
import telebot
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

bot = telebot.TeleBot(TOKEN)
db = sqlite3.connect("kino.db", check_same_thread=False)
db.execute("""
CREATE TABLE IF NOT EXISTS movies (
    code TEXT PRIMARY KEY,
    file_id TEXT NOT NULL
)
""")
db.commit()

CHANNELS = []

def subscribed(user_id):
    for channel in CHANNELS:
        try:
            status = bot.get_chat_member(channel, user_id).status
            if status not in ("member", "administrator", "creator"):
                return False
        except Exception:
            return False
    return True

@bot.message_handler(commands=["start"])
def start(message):
    code = message.text.split(maxsplit=1)
    if len(code) > 1:
        send_movie(message.chat.id, code[1])
        return

    bot.send_message(
        message.chat.id,
        "🎬 KinoHub botiga xush kelibsiz!\n\n"
        "Kino kodini yuboring."
    )

def send_movie(chat_id, code):
    if not subscribed(chat_id):
        markup = types.InlineKeyboardMarkup()
        for channel in CHANNELS:
            markup.add(types.InlineKeyboardButton(
                "📢 Kanalga obuna bo‘lish",
                url="https://t.me/" + channel.lstrip("@")
            ))
        markup.add(types.InlineKeyboardButton(
            "✅ Obunani tekshirish",
            callback_data="check_" + code
        ))
        bot.send_message(
            chat_id, "Avval kanallarga obuna bo‘ling!",
            reply_markup=markup
        )
        return

    row = db.execute(
        "SELECT file_id FROM movies WHERE code=?", (code,)
    ).fetchone()

    if row:
        bot.send_video(chat_id, row[0], caption="🎬 KinoHub")
    else:
        bot.send_message(chat_id, "❌ Bunday kino kodi topilmadi.")

@bot.callback_query_handler(func=lambda c: c.data.startswith("check_"))
def check(call):
    code = call.data[6:]
    if subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "Obuna tasdiqlandi!")
        send_movie(call.message.chat.id, code)
    else:
        bot.answer_callback_query(
            call.id, "Avval barcha kanallarga obuna bo‘ling!",
            show_alert=True
        )

@bot.message_handler(commands=["add"])
def add_movie(message):
    if message.from_user.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "Kino kodini yuboring.")

    bot.register_next_step_handler(message, get_code)

def get_code(message):
    code = message.text.strip()
    bot.send_message(message.chat.id, "Endi kino videosini yuboring.")
    bot.register_next_step_handler(message, save_video, code)

def save_video(message, code):
    if message.video:
        db.execute(
            "INSERT OR REPLACE INTO movies VALUES (?, ?)",
            (code, message.video.file_id)
        )
        db.commit()
        bot.send_message(message.chat.id, "✅ Kino saqlandi!")
    else:
        bot.send_message(message.chat.id, "Video yuboring.")

from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "KinoHub ishlayapti!"

def run():
    app.run(host='0.0.0.0', port=10000)

Thread(target=run).start()

bot.infinity_polling(skip_pending=True)
