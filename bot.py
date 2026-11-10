
import os
import sqlite3
from threading import Thread

import telebot
from telebot import types
from flask import Flask

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

db = sqlite3.connect("kinohub.db", check_same_thread=False)
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
db.execute("""
CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    title TEXT,
    link TEXT
)
""")
db.commit()


@app.route("/")
def home():
    return "KinoHub bot ishlayapti!"


def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))


def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🎬 Kino qo‘shish", "🗑 Kino o‘chirish")
    markup.row("📋 Kinolar ro‘yxati", "📊 Statistika")
    markup.row("➕ Kanal qo‘shish", "➖ Kanal o‘chirish")
    markup.row("📡 Kanallar ro‘yxati")
    return markup


def get_channels():
    return db.execute(
        "SELECT channel_id, title, link FROM channels"
    ).fetchall()


def check_subscriptions(user_id):
    channels = get_channels()

    for channel_id, title, link in channels:
        try:
            member = bot.get_chat_member(channel_id, user_id)
            if member.status in ["left", "kicked"]:
                return False
            if member.status == "restricted" and not member.is_member:
                return False
        except Exception:
            return False

    return True


def subscription_markup():
    markup = types.InlineKeyboardMarkup()
    for channel_id, title, link in get_channels():
        markup.add(types.InlineKeyboardButton(
            text="📢 " + title,
            url=link
        ))

    markup.add(types.InlineKeyboardButton(
        text="✅ Tekshirish",
        callback_data="check_sub"
    ))
    return markup


@bot.message_handler(commands=["start"])
def start(message):
    db.execute(
        "INSERT OR IGNORE INTO users VALUES (?)",
        (message.from_user.id,)
    )
    db.commit()

    if message.from_user.id == ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "👑 KinoHub Admin Panel",
            reply_markup=admin_menu()
        )
        return

    if not check_subscriptions(message.from_user.id):
        bot.send_message(
            message.chat.id,
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo‘ling:",
            reply_markup=subscription_markup()
        )
        return

    bot.send_message(
        message.chat.id,
        "🎬 KinoHub botiga xush kelibsiz!\nKino kodini yuboring."
    )


@bot.message_handler(commands=["admin"])
def admin_command(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(
            message.chat.id,
            "👑 Admin Panel",
            reply_markup=admin_menu()
        )


@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def check_sub_callback(call):
    if check_subscriptions(call.from_user.id):
        bot.answer_callback_query(call.id, "Obuna tasdiqlandi!")
        bot.send_message(
            call.message.chat.id,
            "✅ Obuna tasdiqlandi!\nKino kodini yuboring."
        )
    else:
        bot.answer_callback_query(
            call.id,
            "Avval barcha kanallarga obuna bo‘ling!",
            show_alert=True
        )


# KINO QO‘SHISH

@bot.message_handler(func=lambda m: m.text == "🎬 Kino qo‘shish")
def add_start(message):
    if message.from_user.id != ADMIN_ID:
        return

    msg = bot.send_message(
        message.chat.id,
        "Kino kodini yuboring:"
    )
    bot.register_next_step_handler(msg, get_code)


def get_code(message):
    if message.from_user.id != ADMIN_ID:
        return

    code = message.text.strip()
    msg = bot.send_message(
        message.chat.id,
        "Endi kino videosini yuboring:"
    )
    bot.register_next_step_handler(msg, save_video, code)


def save_video(message, code):
    if message.from_user.id != ADMIN_ID:
        return

    if message.content_type == "video":
        db.execute(
            "INSERT OR REPLACE INTO movies VALUES (?, ?)",
            (code, message.video.file_id)
        )
        db.commit()

        bot.send_message(
            message.chat.id,
            "✅ Kino saqlandi!",
            reply_markup=admin_menu()
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ Video yuboring. Qaytadan boshlash uchun Kino qo‘shish tugmasini bosing."
        )


# KINOLAR RO‘YXATI

@bot.message_handler(func=lambda m: m.text == "📋 Kinolar ro‘yxati")
def movie_list(message):
    if message.from_user.id != ADMIN_ID:
        return

    rows = db.execute(
        "SELECT code FROM movies ORDER BY code"
    ).fetchall()

    if not rows:
        bot.send_message(message.chat.id, "Hozircha kinolar yo‘q.")
        return

    result = "\n".join("🎬 " + row[0] for row in rows)
    bot.send_message(message.chat.id, "Kinolar:\n" + result)


# KINO O‘CHIRISH

@bot.message_handler(func=lambda m: m.text == "🗑 Kino o‘chirish")
def delete_start(message):
    if message.from_user.id != ADMIN_ID:
        return

    msg = bot.send_message(
        message.chat.id,
        "O‘chiriladigan kino kodini yuboring:"
    )
    bot.register_next_step_handler(msg, delete_movie)


def delete_movie(message):
    if message.from_user.id != ADMIN_ID:
        return

    code = message.text.strip()
    cur = db.execute(
        "DELETE FROM movies WHERE code=?",
        (code,)
    )
    db.commit()

    if cur.rowcount:
        bot.send_message(message.chat.id, "✅ Kino o‘chirildi!")
    else:
        bot.send_message(message.chat.id, "❌ Bunday kod topilmadi!")


# STATISTIKA

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def statistics(message):
    if message.from_user.id != ADMIN_ID:
        return

    users = db.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    movies = db.execute(
        "SELECT COUNT(*) FROM movies"
    ).fetchone()[0]

    channels = db.execute(
        "SELECT COUNT(*) FROM channels"
    ).fetchone()[0]

    bot.send_message(
        message.chat.id,
        f"📊 Statistika\n\n"
        f"👥 Foydalanuvchilar: {users}\n"
        f"🎬 Kinolar: {movies}\n"
        f"📢 Kanallar: {channels}"
    )


# KANAL QO‘SHISH

@bot.message_handler(func=lambda m: m.text == "➕ Kanal qo‘shish")
def channel_add_start(message):
    if message.from_user.id != ADMIN_ID:
        return

    msg = bot.send_message(
        message.chat.id,
        "Kanal username yoki ID sini yuboring.\n"
        "Masalan: @kanal_nomi yoki -1001234567890"
    )
    bot.register_next_step_handler(msg, channel_add)


def channel_add(message):
    if message.from_user.id != ADMIN_ID:
        return

    value = message.text.strip()

    try:
        chat = bot.get_chat(value)

        if chat.username:
            link = "https://t.me/" + chat.username
        else:
            invite = bot.create_chat_invite_link(
                chat.id,
                creates_join_request=True
            )
            link = invite.invite_link

        title = chat.title or value

        db.execute(
            "INSERT OR REPLACE INTO channels VALUES (?, ?, ?)",
            (str(chat.id), title, link)
        )
        db.commit()

        bot.send_message(
            message.chat.id,
            "✅ Kanal qo‘shildi!\n"
            f"📢 {title}\n"
            f"🔗 {link}",
            reply_markup=admin_menu()
        )

    except Exception as e:
        bot.send_message(
            message.chat.id,
            "❌ Kanal qo‘shilmadi.\n"
            "Botni kanalga administrator qiling va qayta urinib ko‘ring.\n\n"
            f"Xato: {e}"
        )


# KANAL O‘CHIRISH

@bot.message_handler(func=lambda m: m.text == "➖ Kanal o‘chirish")
def channel_delete_start(message):
    if message.from_user.id != ADMIN_ID:
        return

    msg = bot.send_message(
        message.chat.id,
        "O‘chiriladigan kanal ID sini yuboring:"
    )
    bot.register_next_step_handler(msg, channel_delete)


def channel_delete(message):
    if message.from_user.id != ADMIN_ID:
        return

    value = message.text.strip()

    cur = db.execute(
        "DELETE FROM channels WHERE channel_id=?",
        (value,)
    )
    db.commit()

    if cur.rowcount:
        bot.send_message(message.chat.id, "✅ Kanal o‘chirildi!")
    else:
        bot.send_message(message.chat.id, "❌ Bunday kanal topilmadi!")


# KANALLAR RO‘YXATI

@bot.message_handler(func=lambda m: m.text == "📡 Kanallar ro‘yxati")
def channel_list(message):
    if message.from_user.id != ADMIN_ID:
        return

    rows = get_channels()

    if not rows:
        bot.send_message(message.chat.id, "Hozircha kanallar yo‘q.")
        return

    result = "\n".join(
        f"📢 {title}\n🆔 {channel_id}\n"
        for channel_id, title, link in rows
    )
    bot.send_message(message.chat.id, result)


# YOPIQ KANAL ZAYAVKASI

@bot.chat_join_request_handler(func=lambda request: True)
def join_request_handler(request):
    user_id = request.from_user.id
    chat_id = request.chat.id

    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(
            "✅ Tasdiqlash",
            callback_data=f"approve:{chat_id}:{user_id}"
        ),
        types.InlineKeyboardButton(
            "❌ Rad etish",
            callback_data=f"decline:{chat_id}:{user_id}"
        )
    )

    try:
        bot.send_message(
            ADMIN_ID,
            f"📩 Yangi zayavka!\n"
            f"👤 {request.from_user.first_name}\n"
            f"🆔 {user_id}",
            reply_markup=markup
        )
        bot.send_message(
            user_id,
            "📩 Zayavkangiz yuborildi. Admin tasdiqlashini kuting."
        )
    except Exception:
        pass


@bot.callback_query_handler(
    func=lambda c: c.data.startswith(("approve:", "decline:"))
)
def join_request_decision(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Ruxsat yo‘q!")
        return

    action, chat_id, user_id = call.data.split(":")
    chat_id = int(chat_id)
    user_id = int(user_id)

    try:
        if action == "approve":
            bot.approve_chat_join_request(chat_id, user_id)
            bot.answer_callback_query(call.id, "Zayavka tasdiqlandi!")
            bot.send_message(user_id, "✅ Zayavkangiz tasdiqlandi!")
            bot.edit_message_text(
                "✅ Zayavka tasdiqlandi.",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.decline_chat_join_request(chat_id, user_id)
            bot.answer_callback_query(call.id, "Zayavka rad etildi!")
            bot.send_message(user_id, "❌ Zayavkangiz rad etildi.")
            bot.edit_message_text(
                "❌ Zayavka rad etildi.",
                call.message.chat.id,
                call.message.message_id
            )
    except Exception as e:
        bot.answer_callback_query(call.id, "Xatolik yuz berdi!")
        bot.send_message(ADMIN_ID, f"Xato: {e}")


# FOYDALANUVCHI KINO KODI YUBORGANDA

@bot.message_handler(content_types=["text"])
def get_movie(message):
    if message.from_user.id == ADMIN_ID:
        return

    if not check_subscriptions(message.from_user.id):
        bot.send_message(
            message.chat.id,
            "Avval kanallarga obuna bo‘ling:",
            reply_markup=subscription_markup()
        )
        return

    code = message.text.strip()

    row = db.execute(
        "SELECT file_id FROM movies WHERE code=?",
        (code,)
    ).fetchone()

    if row:
        bot.send_video(
            message.chat.id,
            row[0],
            caption="🎬 KinoHub"
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ Bunday kino kodi topilmadi."
        )


if __name__ == "__main__":
    Thread(target=run_web, daemon=True).start()
    bot.infinity_polling(
        skip_pending=True,
        allowed_updates=["message", "callback_query", "chat_join_request"]
    )
