import os
import json
import threading
import telebot
from telebot import types
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN"

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)

DATA_FILE = "data.json"
PHOTO_DIR = "photos"

if not os.path.exists(PHOTO_DIR):
    os.makedirs(PHOTO_DIR)

waiting_for_photo = {}
menu_state = {}

CHANNELS = {
    "channel1": {
        "name": "Channel 1",
        "chat_id": -1002674664027
    },
    "channel2": {
        "name": "Channel 2",
        "chat_id": -1002514181198
    },
    "channel3": {
        "name": "Channel 3",
        "chat_id": -1002427180742
    }
}

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

db = load_data()

def ensure_user(user_id):
    user_id = str(user_id)
    if user_id not in db:
        db[user_id] = {
            "photos": {},
            "active_photo": None,
            "selected_channels": []
        }
        save_data(db)
    return user_id

def get_selected_channel_names(user_id):
    names = []
    for ch in db[user_id].get("selected_channels", []):
        if ch in CHANNELS:
            names.append(CHANNELS[ch]["name"])
    return names

def main_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📸 Set Photo", "✅ Use Photo")
    m.row("📢 Auto Forward Channel")
    m.row("📋 Current Channels")
    return m

def photo_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("Photo 1", "Photo 2")
    m.row("Photo 3", "Photo 4")
    m.row("Photo 5")
    m.row("⬅️ Back")
    return m

def channel_menu():
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("Channel 1", "Channel 2")
    m.row("Channel 3")
    m.row("❌ Remove Channel 1", "❌ Remove Channel 2")
    m.row("❌ Remove Channel 3")
    m.row("🗑 Remove All Channels")
    m.row("⬅️ Back")
    return m

@app.route("/")
def home():
    return "Bot is running!"

@bot.message_handler(commands=["start"])
def start(message):
    user_id = ensure_user(message.from_user.id)
    active = db[user_id].get("active_photo") or "None"
    channels = get_selected_channel_names(user_id)
    channel_text = ", ".join(channels) if channels else "None"

    bot.send_message(
        message.chat.id,
        f"✅ Bot Ready\n\nActive Photo: {active}\nSelected Channels: {channel_text}",
        reply_markup=main_menu()
    )

@bot.channel_post_handler(content_types=['text', 'photo', 'video'])
def detect_channel(message):
    print("🔥 CHANNEL DETECTED 🔥")
    print("ID =", message.chat.id)
    print("TITLE =", message.chat.title)

@bot.message_handler(func=lambda m: m.content_type == "text")
def handle_text(message):
    user_id = ensure_user(message.from_user.id)
    text = message.text.strip()

    if text == "📸 Set Photo":
        menu_state[user_id] = "set"
        bot.send_message(message.chat.id, "Select slot", reply_markup=photo_menu())
        return

    if text == "✅ Use Photo":
        menu_state[user_id] = "use"
        bot.send_message(message.chat.id, "Select photo", reply_markup=photo_menu())
        return

    if text == "📢 Auto Forward Channel":
        menu_state[user_id] = "channel"
        names = get_selected_channel_names(user_id)
        current = ", ".join(names) if names else "None"
        bot.send_message(
            message.chat.id,
            f"Select channel(s)\nCurrent: {current}",
            reply_markup=channel_menu()
        )
        return

    if text == "📋 Current Channels":
        names = get_selected_channel_names(user_id)
        if not names:
            bot.send_message(message.chat.id, "No channels selected", reply_markup=main_menu())
        else:
            bot.send_message(
                message.chat.id,
                "Selected Channels:\n\n" + "\n".join(f"✅ {name}" for name in names),
                reply_markup=main_menu()
            )
        return

    if text == "🗑 Remove All Channels":
        db[user_id]["selected_channels"] = []
        save_data(db)
        bot.send_message(message.chat.id, "All channels removed", reply_markup=channel_menu())
        return

    if text == "⬅️ Back":
        menu_state.pop(user_id, None)
        bot.send_message(message.chat.id, "Main Menu", reply_markup=main_menu())
        return

    if text.startswith("Photo"):
        num = text.split()[-1]
        slot = f"photo{num}"
        mode = menu_state.get(user_id)

        if mode == "set":
            waiting_for_photo[user_id] = slot
            bot.send_message(message.chat.id, "Send photo now")
            return

        if mode == "use":
            if slot in db[user_id]["photos"]:
                db[user_id]["active_photo"] = slot
                save_data(db)
                bot.send_message(message.chat.id, f"{text} selected", reply_markup=main_menu())
            else:
                bot.send_message(message.chat.id, f"{text} not saved", reply_markup=photo_menu())
            return

    if text in ["Channel 1", "Channel 2", "Channel 3"]:
        key = text.lower().replace(" ", "")

        if key not in db[user_id]["selected_channels"]:
            db[user_id]["selected_channels"].append(key)
            save_data(db)
            names = get_selected_channel_names(user_id)
            bot.send_message(
                message.chat.id,
                f"✅ {text} selected\n\nCurrent: {', '.join(names)}",
                reply_markup=channel_menu()
            )
        else:
            names = get_selected_channel_names(user_id)
            bot.send_message(
                message.chat.id,
                f"⚠️ {text} already selected\n\nCurrent: {', '.join(names)}",
                reply_markup=channel_menu()
            )
        return

    if text in ["❌ Remove Channel 1", "❌ Remove Channel 2", "❌ Remove Channel 3"]:
        key = text.replace("❌ Remove ", "").lower().replace(" ", "")
        if key in db[user_id]["selected_channels"]:
            db[user_id]["selected_channels"].remove(key)
            save_data(db)
            names = get_selected_channel_names(user_id)
            current = ", ".join(names) if names else "None"
            bot.send_message(
                message.chat.id,
                f"✅ {key.upper()} removed\n\nCurrent: {current}",
                reply_markup=channel_menu()
            )
        else:
            bot.send_message(message.chat.id, "Channel not selected", reply_markup=channel_menu())
        return

    if not text.startswith("/"):
        bot.send_message(message.chat.id, "Use buttons below", reply_markup=main_menu())

@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    user_id = ensure_user(message.from_user.id)

    if user_id in waiting_for_photo:
        slot = waiting_for_photo[user_id]

        try:
            file = bot.get_file(message.photo[-1].file_id)
            data = bot.download_file(file.file_path)

            path = f"{PHOTO_DIR}/{user_id}_{slot}.jpg"
            with open(path, "wb") as f:
                f.write(data)

            db[user_id]["photos"][slot] = path

            if not db[user_id]["active_photo"]:
                db[user_id]["active_photo"] = slot

            save_data(db)
            waiting_for_photo.pop(user_id)

            bot.send_message(message.chat.id, f"{slot.upper()} saved", reply_markup=main_menu())
            return

        except Exception as e:
            bot.send_message(message.chat.id, f"Save error: {e}", reply_markup=main_menu())
            return

    slot = db[user_id].get("active_photo")
    if not slot:
        bot.send_message(message.chat.id, "Select photo first", reply_markup=main_menu())
        return

    path = db[user_id]["photos"].get(slot)
    if not path or not os.path.exists(path):
        bot.send_message(message.chat.id, "Photo missing", reply_markup=main_menu())
        return

    caption = message.caption or ""

    try:
        with open(path, "rb") as img:
            bot.send_photo(message.chat.id, img, caption=caption)

        selected_channels = db[user_id].get("selected_channels", [])

        if not selected_channels:
            bot.send_message(message.chat.id, "No forward channel selected", reply_markup=main_menu())
            return

        success = []
        failed = []

        for ch in selected_channels:
            if ch in CHANNELS:
                try:
                    with open(path, "rb") as img:
                        bot.send_photo(CHANNELS[ch]["chat_id"], img, caption=caption)
                    success.append(CHANNELS[ch]["name"])
                except Exception as e:
                    failed.append(f"{CHANNELS[ch]['name']} - {e}")

        msg = ""
        if success:
            msg += "✅ Posted to:\n" + "\n".join(success)
        if failed:
            msg += "\n\n❌ Failed:\n" + "\n".join(failed)

        if msg:
            bot.send_message(message.chat.id, msg, reply_markup=main_menu())

    except Exception as e:
        bot.send_message(message.chat.id, f"Replace error: {e}", reply_markup=main_menu())

def run_bot():
    print("Bot running...")
    bot.infinity_polling(skip_pending=True)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
