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

# -------------------- DATA SAVE / LOAD --------------------

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
            "active_photo": None
        }
        save_data(db)
    return user_id

# -------------------- MENUS --------------------

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📸 Set Photo")
    markup.row("✅ Use Photo")
    return markup

def photo_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Photo 1", "Photo 2")
    markup.row("Photo 3", "Photo 4")
    markup.row("Photo 5")
    markup.row("⬅️ Back")
    return markup

# -------------------- FLASK --------------------

@app.route("/")
def home():
    return "Bot is running!"

# -------------------- BOT COMMANDS --------------------

@bot.message_handler(commands=["start"])
def start(message):
    user_id = ensure_user(message.from_user.id)
    active = db[user_id].get("active_photo")

    if active:
        active_text = f"\nCurrent active: {active.upper()}"
    else:
        active_text = "\nCurrent active: None"

    bot.send_message(
        message.chat.id,
        "✅ Bot Ready\n\n"
        "1. 📸 Set Photo അമർത്തൂ\n"
        "2. Photo 1 മുതൽ 5 വരെ ഒരു slot select ചെയ്യൂ\n"
        "3. ശേഷം photo അയച്ചാൽ save ചെയ്യും\n"
        "4. ✅ Use Photo ഉപയോഗിച്ച് active photo select ചെയ്യൂ\n"
        "5. ഇനി photo + text + link അയച്ചാൽ photo replace ചെയ്യും"
        + active_text,
        reply_markup=main_menu()
    )

# -------------------- TEXT BUTTON HANDLER --------------------

@bot.message_handler(func=lambda m: m.content_type == "text")
def handle_text(message):
    user_id = ensure_user(message.from_user.id)
    text = message.text.strip()

    if text == "📸 Set Photo":
        menu_state[user_id] = "set"
        bot.send_message(
            message.chat.id,
            "📸 ഏത് slot-il photo save ചെയ്യണം?",
            reply_markup=photo_menu()
        )
        return

    if text == "✅ Use Photo":
        menu_state[user_id] = "use"
        bot.send_message(
            message.chat.id,
            "✅ ഏത് photo active ആക്കണം?",
            reply_markup=photo_menu()
        )
        return

    if text == "⬅️ Back":
        menu_state.pop(user_id, None)
        bot.send_message(
            message.chat.id,
            "🏠 Main menu",
            reply_markup=main_menu()
        )
        return

    if text in ["Photo 1", "Photo 2", "Photo 3", "Photo 4", "Photo 5"]:
        num = text.split()[-1]
        slot = f"photo{num}"
        current_mode = menu_state.get(user_id)

        if current_mode == "set":
            waiting_for_photo[user_id] = slot
            bot.send_message(
                message.chat.id,
                f"📸 ഇനി {text} ആയി save ചെയ്യാനുള്ള photo അയക്കൂ",
                reply_markup=photo_menu()
            )
            return

        if current_mode == "use":
            if slot in db[user_id]["photos"]:
                db[user_id]["active_photo"] = slot
                save_data(db)
                bot.send_message(
                    message.chat.id,
                    f"✅ {text} active ആയി set ചെയ്തു",
                    reply_markup=main_menu()
                )
            else:
                bot.send_message(
                    message.chat.id,
                    f"❌ {text} save ചെയ്തിട്ടില്ല.\nആദ്യം Set Photo ഉപയോഗിക്കൂ.",
                    reply_markup=photo_menu()
                )
            return

        bot.send_message(
            message.chat.id,
            "❌ ആദ്യം 📸 Set Photo അല്ലെങ്കിൽ ✅ Use Photo അമർത്തൂ",
            reply_markup=main_menu()
        )
        return

    if not text.startswith("/"):
        bot.send_message(
            message.chat.id,
            "📌 താഴെയുള്ള buttons use ചെയ്യൂ",
            reply_markup=main_menu()
        )

# -------------------- PHOTO HANDLER --------------------

@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    user_id = ensure_user(message.from_user.id)

    # Save mode
    if user_id in waiting_for_photo:
        slot = waiting_for_photo[user_id]

        try:
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            filename = os.path.join(PHOTO_DIR, f"{user_id}_{slot}.jpg")
            with open(filename, "wb") as f:
                f.write(downloaded_file)

            db[user_id]["photos"][slot] = filename

            if not db[user_id]["active_photo"]:
                db[user_id]["active_photo"] = slot

            save_data(db)
            waiting_for_photo.pop(user_id, None)

            bot.send_message(
                message.chat.id,
                f"✅ {slot.upper()} saved ചെയ്തു",
                reply_markup=main_menu()
            )
            return

        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"❌ Save error: {e}",
                reply_markup=main_menu()
            )
            return

    # Replace mode
    active_slot = db[user_id].get("active_photo")

    if not active_slot:
        bot.send_message(
            message.chat.id,
            "❌ ആദ്യം ✅ Use Photo ഉപയോഗിച്ച് photo select ചെയ്യൂ",
            reply_markup=main_menu()
        )
        return

    photo_path = db[user_id]["photos"].get(active_slot)

    if not photo_path or not os.path.exists(photo_path):
        bot.send_message(
            message.chat.id,
            "❌ Active photo കിട്ടിയില്ല. വീണ്ടും set ചെയ്യൂ",
            reply_markup=main_menu()
        )
        return

    caption = message.caption or ""

    try:
        with open(photo_path, "rb") as img:
            bot.send_photo(
                chat_id=message.chat.id,
                photo=img,
                caption=caption,
                reply_markup=main_menu()
            )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Replace error: {e}",
            reply_markup=main_menu()
        )

# -------------------- BOT RUN --------------------

def run_bot():
    print("Bot running...")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=20)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
