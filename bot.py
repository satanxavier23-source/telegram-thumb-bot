import os
import json
import telebot
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8747520627:AAGtWhETPQJZdNTBkoEJNf1wh4BkpOwM0os"
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

DATA_FILE = "data.json"
PHOTO_DIR = "photos"

if not os.path.exists(PHOTO_DIR):
    os.makedirs(PHOTO_DIR)

# Runtime state
waiting_for_photo = {}   # {user_id: "photo1"}
menu_state = {}          # {user_id: "set" or "use"}

# Persistent state
# {
#   "12345": {
#       "photos": {"photo1": "photos/12345_photo1.jpg", ...},
#       "active_photo": "photo1"
#   }
# }
user_data = {}


def load_data():
    global user_data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
        except Exception:
            user_data = {}
    else:
        user_data = {}


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_data, f, indent=2, ensure_ascii=False)


def get_user(user_id):
    uid = str(user_id)
    if uid not in user_data:
        user_data[uid] = {
            "photos": {},
            "active_photo": None
        }
        save_data()
    return user_data[uid]


def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📸 Set Photo")
    markup.row("✅ Use Photo")
    markup.row("📂 My Active Photo")
    return markup


def photo_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Photo 1", "Photo 2")
    markup.row("Photo 3", "Photo 4")
    markup.row("Photo 5")
    markup.row("⬅️ Back")
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "✅ Bot Ready\n\n"
        "1. 📸 Set Photo അമർത്തൂ\n"
        "2. Photo 1 മുതൽ 5 വരെ slot select ചെയ്യൂ\n"
        "3. ശേഷം photo അയച്ചാൽ save ചെയ്യും\n"
        "4. ✅ Use Photo ഉപയോഗിച്ച് active photo select ചെയ്യൂ\n"
        "5. ഇനി photo + text + link അയച്ചാൽ photo replace ചെയ്യും\n\n"
        "🔁 Restart ആയാലും saved photos പോകില്ല",
        reply_markup=main_menu()
    )


@bot.message_handler(func=lambda m: m.content_type == "text")
def handle_text(message):
    user_id = message.from_user.id
    text = message.text.strip()
    user = get_user(user_id)

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

    if text == "📂 My Active Photo":
        active = user.get("active_photo")
        if not active:
            bot.send_message(
                message.chat.id,
                "❌ Active photo set ചെയ്തിട്ടില്ല",
                reply_markup=main_menu()
            )
            return

        photo_path = user["photos"].get(active)
        if not photo_path or not os.path.exists(photo_path):
            bot.send_message(
                message.chat.id,
                "❌ Active photo file കിട്ടിയില്ല",
                reply_markup=main_menu()
            )
            return

        with open(photo_path, "rb") as img:
            bot.send_photo(
                message.chat.id,
                img,
                caption=f"✅ Current active: {active.upper()}",
                reply_markup=main_menu()
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
            if slot in user["photos"] and os.path.exists(user["photos"][slot]):
                user["active_photo"] = slot
                save_data()
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

    bot.send_message(
        message.chat.id,
        "📌 താഴെയുള്ള buttons use ചെയ്യൂ",
        reply_markup=main_menu()
    )


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    user = get_user(user_id)

    # Save mode
    if user_id in waiting_for_photo:
        slot = waiting_for_photo[user_id]

        try:
            file_info = bot.get_file(message.photo[-1].file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            filename = os.path.join(PHOTO_DIR, f"{user_id}_{slot}.jpg")
            with open(filename, "wb") as f:
                f.write(downloaded_file)

            user["photos"][slot] = filename

            if not user.get("active_photo"):
                user["active_photo"] = slot

            save_data()
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
    active_slot = user.get("active_photo")
    if not active_slot:
        bot.send_message(
            message.chat.id,
            "❌ ആദ്യം ✅ Use Photo ഉപയോഗിച്ച് active photo select ചെയ്യൂ",
            reply_markup=main_menu()
        )
        return

    photo_path = user["photos"].get(active_slot)
    if not photo_path or not os.path.exists(photo_path):
        bot.send_message(
            message.chat.id,
            "❌ Active photo കിട്ടിയില്ല",
            reply_markup=main_menu()
        )
        return

    caption = message.caption or ""

    try:
        with open(photo_path, "rb") as img:
            bot.send_photo(
                message.chat.id,
                img,
                caption=caption,
                reply_markup=main_menu()
            )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Replace error: {e}",
            reply_markup=main_menu()
        )


load_data()
print("Bot running...")
bot.infinity_polling(skip_pending=True)