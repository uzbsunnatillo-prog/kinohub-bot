
import os
import sqlite3
import telebot
from telebot import types
from flask import Flask
from threading import Thread

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "481978731"))

bot = telebot.TeleBot(TOKEN)
db = sqlite3.connect("kino.db", check_same_thread=False)
db.execute("""
CREATE TABLE IF NOT EXISTS movies (
    code TEXT PRIMARY KEY,
    file_id TEXT NOT NULL
)
""")
db.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
)
""")
db.commit()

app = Flask(__name__)

@app.route("/")
def home():
    return "KinoHub ishlayapti!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

Thread(target=run_web, daemon=True).start()

def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🎬 Kino qo‘shish", "🗑 Kino o‘chirish")
    markup.row("📋 Kinolar ro‘yxati", "📊 Statistika")
    return markup

@bot.message_handler(commands=["start"])
def start(message):
    db.execute("INSERT OR IGNORE INTO users VALUES (?)",
               (message.from_user.id,))
    db.commit()

    if message.from_user.id == ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "👑 KinoHub Admin Panel",
            reply_markup=admin_menu()
        )
    else:
        bot.send_message(
            message.chat.id,
            "🎬 KinoHub botiga xush kelibsiz!\n\nKino kodini yuboring."
        )

@bot.message_handler(func=lambda m: m.text == "🎬 Kino qo‘shish")
def add_start(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "Kino kodini yuboring:")
    bot.register_next_step_handler(msg, get_code)

def get_code(message):
    if message.from_user.id != ADMIN_ID:
        return
    code = message.text.strip()
    msg = bot.send_message(message.chat.id, "Endi kino videosini yuboring:")
    bot.register_next_step_handler(msg, save_video, code)

def save_video(message, code):
    if message.from_user.id != ADMIN_ID:
        return
    if message.video:
        db.execute(
            "INSERT OR REPLACE INTO movies VALUES (?, ?)",
            (code, message.video.file_id)
        )
        db.commit()
        bot.send_message(
            message.chat.id, "✅ Kino saqlandi!",
            reply_markup=admin_menu()
        )
    else:
        bot.send_message(message.chat.id, "Video yuboring.")

@bot.message_handler(func=lambda m: m.text == "📋 Kinolar ro‘yxati")
def movie_list(message):
    if message.from_user.id != ADMIN_ID:
        return
    rows = db.execute("SELECT code FROM movies ORDER BY code").fetchall()
    if not rows:
        bot.send_message(message.chat.id, "Hozircha kinolar yo‘q.")
        return
    result = "\n".join("🎬 " + row[0] for row in rows)
    bot.send_message(message.chat.id, "Kinolar:\n" + result)

@bot.message_handler(func=lambda m: m.text == "🗑 Kino o‘chirish")
def delete_start(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "O‘chiriladigan kino kodini yuboring:")
    bot.register_next_step_handler(msg, delete_movie)

def delete_movie(message):
    if message.from_user.id != ADMIN_ID:
        return
    code = message.text.strip()
    cur = db.execute("DELETE FROM movies WHERE code=?", (code,))
    db.commit()
    if cur.rowcount:
        bot.send_message(message.chat.id, "✅ Kino o‘chirildi!")
    else:
        bot.send_message(message.chat.id, "❌ Bunday kod topilmadi.")

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def stats(message):
    if message.from_user.id != ADMIN_ID:
        return
    movies = db.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    bot.send_message(
        message.chat.id,
        f"📊 Statistika\n\n👥 Foydalanuvchilar: {users}\n🎬 Kinolar: {movies}"
    )

@bot.message_handler(func=lambda m: True, content_types=["text"])
def get_movie(message):
    if message.from_user.id == ADMIN_ID:
        return
    code = message.text.strip()
    row = db.execute(
        "SELECT file_id FROM movies WHERE code=?", (code,)
    ).fetchone()
    if row:
        bot.send_video(message.chat.id, row[0], caption="🎬 KinoHub")
    else:
        bot.send_message(message.chat.id, "❌ Bunday kino kodi topilmadi.")

bot.infinity_polling(skip_pending=True)

