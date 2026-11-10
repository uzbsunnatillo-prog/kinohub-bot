
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
db.execute("CREATE TABLE IF NOT EXISTS movies (code TEXT PRIMARY KEY, file_id TEXT NOT NULL)")
db.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
db.execute("""CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    title TEXT,
    link TEXT,
    username TEXT
)""")
db.commit()

app = Flask(__name__)

@app.route("/")
def home():
    return "KinoHub ishlayapti!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

Thread(target=run_web, daemon=True).start()

def is_admin(message):
    return message.from_user.id == ADMIN_ID

def admin_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("🎬 Kino qo‘shish", "🗑 Kino o‘chirish")
    m.row("📋 Kinolar", "📢 Kanallar")
    m.row("👥 Foydalanuvchilar", "📊 Statistika")
    m.row("🔄 Panel")
    return m

def channel_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("➕ Kanal qo‘shish", "➖ Kanal o‘chirish")
    m.row("📋 Kanallar ro‘yxati", "⬅️ Asosiy panel")
    return m

def subscribed(user_id):
    rows = db.execute("SELECT channel_id FROM channels").fetchall()
    for row in rows:
        try:
            status = bot.get_chat_member(row[0], user_id).status
            if status not in ("member", "administrator", "creator"):
                return False
        except Exception:
            return False
    return True

def ask_subscription(chat_id, code):
    rows = db.execute(
        "SELECT title, link FROM channels"
    ).fetchall()

    m = types.InlineKeyboardMarkup()
    for title, link in rows:
        m.add(types.InlineKeyboardButton(
            "📢 " + title, url=link
        ))
    m.add(types.InlineKeyboardButton(
        "✅ Obunani tekshirish",
        callback_data="check_" + code
    ))
    bot.send_message(
        chat_id,
        "🎬 Kinoni olish uchun quyidagi kanallarga obuna bo‘ling.\n"
        "Yopiq kanal bo‘lsa, obuna uchun zayavka yuboring.",
        reply_markup=m
    )

def send_movie(chat_id, code, user_id):
    if not subscribed(user_id):
        ask_subscription(chat_id, code)
        return

    row = db.execute(
        "SELECT file_id FROM movies WHERE code=?", (code,)
    ).fetchone()

    if row:
        bot.send_video(chat_id, row[0], caption="🎬 KinoHub")
    else:
        bot.send_message(chat_id, "❌ Bunday kino kodi topilmadi.")

@bot.message_handler(commands=["start", "panel"])
def start(message):
    db.execute(
        "INSERT OR IGNORE INTO users VALUES (?)",
        (message.from_user.id,)
    )
    db.commit()

    if is_admin(message):
        bot.send_message(
            message.chat.id,
            "👑 KinoHub boshqaruv paneli",
            reply_markup=admin_menu()
        )
    else:
        bot.send_message(
            message.chat.id,
            "🎬 KinoHub botiga xush kelibsiz!\n\nKino kodini yuboring."
        )

@bot.message_handler(func=lambda m: m.text == "🔄 Panel")
def panel(message):
    if is_admin(message):
        bot.send_message(message.chat.id, "Admin panel:", reply_markup=admin_menu())

@bot.message_handler(func=lambda m: m.text == "⬅️ Asosiy panel")
def back_panel(message):
    if is_admin(message):
        bot.send_message(message.chat.id, "Asosiy panel:", reply_markup=admin_menu())

# KINO QO‘SHISH
@bot.message_handler(func=lambda m: m.text == "🎬 Kino qo‘shish")
def add_movie_start(message):
    if not is_admin(message):
        return
    msg = bot.send_message(message.chat.id, "Kino kodini yuboring:")
    bot.register_next_step_handler(msg, get_movie_code)

def get_movie_code(message):
    if not is_admin(message):
        return
    code = message.text.strip()
    msg = bot.send_message(message.chat.id, "Endi kino videosini yuboring:")
    bot.register_next_step_handler(msg, save_movie, code)

def save_movie(message, code):
    if not is_admin(message):
        return
    if not message.video:
        bot.send_message(message.chat.id, "❌ Video yuboring.", reply_markup=admin_menu())
        return
    db.execute(
        "INSERT OR REPLACE INTO movies VALUES (?, ?)",
        (code, message.video.file_id)
    )
    db.commit()
    bot.send_message(
        message.chat.id, "✅ Kino saqlandi!",
        reply_markup=admin_menu()
    )

# KINO O‘CHIRISH
@bot.message_handler(func=lambda m: m.text == "🗑 Kino o‘chirish")
def delete_start(message):
    if not is_admin(message):
        return
    msg = bot.send_message(message.chat.id, "O‘chiriladigan kino kodini yuboring:")
    bot.register_next_step_handler(msg, delete_movie)

def delete_movie(message):
    if not is_admin(message):
        return
    cur = db.execute("DELETE FROM movies WHERE code=?", (message.text.strip(),))
    db.commit()
    answer = "✅ Kino o‘chirildi!" if cur.rowcount else "❌ Kino topilmadi."
    bot.send_message(message.chat.id, answer, reply_markup=admin_menu())

# KINOLAR RO‘YXATI
@bot.message_handler(func=lambda m: m.text == "📋 Kinolar")
def movie_list(message):
    if not is_admin(message):
        return
    rows = db.execute("SELECT code FROM movies ORDER BY code").fetchall()
    if not rows:
        bot.send_message(message.chat.id, "Hozircha kino yo‘q.")
        return
    result = "\n".join("🎬 " + r[0] for r in rows)
    bot.send_message(message.chat.id, "Kinolar ro‘yxati:\n\n" + result[:4000])

# KANAL MENYUSI
@bot.message_handler(func=lambda m: m.text == "📢 Kanallar")
def channels_menu(message):
    if is_admin(message):
        bot.send_message(message.chat.id, "📢 Kanal boshqaruvi:", reply_markup=channel_menu())

@bot.message_handler(func=lambda m: m.text == "➕ Kanal qo‘shish")
def add_channel_start(message):
    if not is_admin(message):
        return
    msg = bot.send_message(
        message.chat.id,
        "Kanal username yoki ID sini yuboring.\n\n"
        "Ochiq kanal: @kanal_nomi\n"
        "Yopiq kanal: -100 bilan boshlanadigan ID"
    )
    bot.register_next_step_handler(msg, add_channel)

def add_channel(message):
    if not is_admin(message):
        return
    ref = message.text.strip()
    try:
        chat = bot.get_chat(ref)
        channel_id = str(chat.id)
        title = chat.title or ref
        username = chat.username or ""
        if username:
            link = "https://t.me/" + username
        else:
            invite = bot.create_chat_invite_link(
                chat.id, creates_join_request=True
            )
            link = invite.invite_link

        db.execute(
            "INSERT OR REPLACE INTO channels VALUES (?, ?, ?, ?)",
            (channel_id, title, link, username)
        )
        db.commit()
        bot.send_message(
            message.chat.id,
            "✅ Kanal qo‘shildi!\n"
            "Nomi: " + title + "\n"
            "Havola: " + link,
            reply_markup=channel_menu()
        )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            "❌ Kanal qo‘shilmadi.\n"
            "Botni kanalga administrator qiling va ID yoki username ni tekshiring.\n"
            "Xato: " + str(e)[:500],
            reply_markup=channel_menu()
        )

# KANAL O‘CHIRISH
@bot.message_handler(func=lambda m: m.text == "➖ Kanal o‘chirish")
def remove_channel_start(message):
    if not is_admin(message):
        return
    msg = bot.send_message(message.chat.id, "O‘chiriladigan kanal ID sini yuboring:")
    bot.register_next_step_handler(msg, remove_channel)

def remove_channel(message):
    if not is_admin(message):
        return
    cur = db.execute(
        "DELETE FROM channels WHERE channel_id=?",
        (message.text.strip(),)
    )
    db.commit()
    answer = "✅ Kanal o‘chirildi!" if cur.rowcount else "❌ Kanal topilmadi."
    bot.send_message(message.chat.id, answer, reply_markup=channel_menu())

# KANALLAR RO‘YXATI
@bot.message_handler(func=lambda m: m.text == "📋 Kanallar ro‘yxati")
def channel_list(message):
    if not is_admin(message):
        return
    rows = db.execute(
        "SELECT channel_id, title, link FROM channels"
    ).fetchall()
    if not rows:
        bot.send_message(message.chat.id, "Hozircha kanal qo‘shilmagan.")
        return
    for cid, title, link in rows:
        bot.send_message(
            message.chat.id,
            f"📢 {title}\nID: {cid}\nHavola: {link}"
        )

# ZAYAVKALARNI ADMIN TASDIQLAYDI
@bot.chat_join_request_handler(func=lambda request: True)
def join_request(request):
    user = request.from_user
    chat = request.chat
    m = types.InlineKeyboardMarkup()
    m.row(
        types.InlineKeyboardButton(
            "✅ Tasdiqlash",
            callback_data=f"approve:{chat.id}:{user.id}"
        ),
        types.InlineKeyboardButton(
            "❌ Rad etish",
            callback_data=f"decline:{chat.id}:{user.id}"
        )
    )
    bot.send_message(
        ADMIN_ID,
        f"📩 Yangi zayavka!\n"
        f"Foydalanuvchi: {user.first_name}\n"
        f"ID: {user.id}\n"
        f"Kanal: {chat.title}",
        reply_markup=m
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith(("approve:", "decline:")))
def manage_request(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Bu amal faqat admin uchun.")
        return
    action, channel_id, user_id = call.data.split(":")
    try:
        if action == "approve":
            bot.approve_chat_join_request(int(channel_id), int(user_id))
            answer = "✅ Zayavka tasdiqlandi."
        else:
            bot.decline_chat_join_request(int(channel_id), int(user_id))
            answer = "❌ Zayavka rad etildi."
        bot.answer_callback_query(call.id, answer)
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None
        )
    except Exception as e:
        bot.answer_callback_query(call.id, "Xato: " + str(e)[:150], show_alert=True)

# OBUNANI TEKSHIRISH
@bot.callback_query_handler(func=lambda c: c.data.startswith("check_"))
def check_subscription(call):
    code = call.data[6:]
    if subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Obuna tasdiqlandi!")
        send_movie(call.message.chat.id, code, call.from_user.id)
    else:
        bot.answer_callback_query(
            call.id,
            "Avval barcha kanallarga obuna bo‘ling yoki zayavka yuboring.",
            show_alert=True
        )

# STATISTIKA
@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar")
def users_count(message):
    if not is_admin(message):
        return
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    bot.send_message(message.chat.id, f"👥 Foydalanuvchilar: {count}")

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def stats(message):
    if not is_admin(message):
        return
    users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    movies = db.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
    channels = db.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    bot.send_message(
        message.chat.id,
        f"📊 KinoHub statistikasi\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"🎬 Kinolar: {movies}\n"
        f"📢 Kanallar: {channels}",
        reply_markup=admin_menu()
    )

# FOYDALANUVCHI KINO KODI YUBORADI
@bot.message_handler(content_types=["text"])
def user_movie(message):
    if is_admin(message):
        return
    db.execute(
        "INSERT OR IGNORE INTO users VALUES (?)",
        (message.from_user.id,)
    )
    db.commit()
    send_movie(
        message.chat.id,
        message.text.strip(),
        message.from_user.id
    )

bot.infinity_polling(skip_pending=True)
