import os
import random
import sqlite3
import requests
import logging
from flask import Flask, request

# ================= CONFIGURATION =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8827005241:AAG-mAj8EkJmMrSi2KC8FobuucBwbFxJofY")
CHANNEL_ID = "@daily_price_alert"
CHANNEL_LINK = "https://t.me/daily_price_alert"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# ================= DATABASE SETUP =================
def init_db():
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
        cursor.execute("CREATE TABLE IF NOT EXISTS groups (group_id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Database Init Error: {e}")

init_db()

# ================= CATEGORIES & HOT DEALS =================
HOT_DEALS = [
    {
        "id": "samsung_m35",
        "category": "mobile",
        "title": "📱 Samsung Galaxy M35 5G (8GB RAM, 128GB)",
        "orig_price": "₹24,999",
        "deal_price": "₹13,999",
        "discount": "44% OFF 🔥 (Lowest Price Ever!)",
        "specs": "• 6000mAh Battery\n• 120Hz Super AMOLED Display\n• 50MP OIS Camera",
        "image": "https://i.postimg.cc/m2vS36L1/samsung-m35.jpg",
        "url": "https://www.amazon.in/dp/B0D782C2LK"
    },
    {
        "id": "asus_vivobook",
        "category": "laptop",
        "title": "💻 ASUS Vivobook 15 Intel Core i3 12th Gen",
        "orig_price": "₹49,990",
        "deal_price": "₹32,990",
        "discount": "34% OFF ⚡ (Heavy Drop)",
        "specs": "• 8GB RAM / 512GB SSD\n• Thin & Light Design\n• Windows 11 + MS Office",
        "image": "https://i.postimg.cc/3R9D16Nf/asus-laptop.jpg",
        "url": "https://www.amazon.in/dp/B0C3R82KWY"
    },
    {
        "id": "boat_141",
        "category": "audio",
        "title": "🎧 boAt Airdopes 141 TWS Earbuds",
        "orig_price": "₹4,490",
        "deal_price": "₹999",
        "discount": "78% OFF 💥 (Loot Deal)",
        "specs": "• 42 Hours Playtime\n• Low Latency Gaming Mode\n• IPX4 Water Resistance",
        "image": "https://i.postimg.cc/44M69Qd4/boat-airdopes.jpg",
        "url": "https://www.amazon.in/dp/B09N3Z3Y89"
    }
]

# ================= CORE UTILS =================
def send_deal(target_id, deal):
    caption = (
        f"🔥 *{deal['title']}*\n\n"
        f"❌ M.R.P.: ~{deal['orig_price']}~\n"
        f"💰 *Deal Price: {deal['deal_price']}*\n"
        f"⚡ *Discount:* {deal['discount']}\n\n"
        f"📌 *Key Features:*\n{deal['specs']}\n\n"
        f"📢 Join Channel: {CHANNEL_ID}"
    )

    reply_markup = {
        "inline_keyboard": [
            [{"text": "🛒 Direct Buy Product Here", "url": deal["url"]}]
        ]
    }

    requests.post(f"{TELEGRAM_API_URL}/sendPhoto", json={
        "chat_id": target_id,
        "photo": deal["image"],
        "caption": caption,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    })

def broadcast_deal():
    deal = random.choice(HOT_DEALS)
    send_deal(CHANNEL_ID, deal)

    # Users Broadcast
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        for user in users:
            send_deal(user[0], deal)
        conn.close()
    except Exception as e:
        logging.error(f"User Broadcast Error: {e}")

def promote_to_groups():
    promo_text = (
        "🔥 *Sabse Sasti Loot Deals & Price Drops!*\n\n"
        "Daily Amazon/Flipkart flash sales, 80% OFF tech deals aur loot offers paane ke liye abhi hamare channel aur bot ko join karein! 🚀\n\n"
        f"📢 *Main Channel:* {CHANNEL_LINK}\n"
        "🤖 *Bot:* @price_alert_zs93_bot"
    )
    reply_markup = {
        "inline_keyboard": [[{"text": "📢 Join Loot Channel Now", "url": CHANNEL_LINK}]]
    }

    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT group_id FROM groups")
        groups = cursor.fetchall()
        for group in groups:
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                "chat_id": group[0],
                "text": promo_text,
                "parse_mode": "Markdown",
                "reply_markup": reply_markup
            })
        conn.close()
    except Exception as e:
        logging.error(f"Group Promo Error: {e}")

# ================= FLASK WEBHOOK HANDLER =================
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json(force=True)

    # Inline Button Callbacks (Categories)
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb["data"]

        if data.startswith("cat_"):
            cat_type = data.split("_")[1]
            matching_deals = [d for d in HOT_DEALS if d["category"] == cat_type]
            if matching_deals:
                for deal in matching_deals:
                    send_deal(chat_id, deal)
            else:
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "❌ Iss category me abhi koi active deal nahi hai."
                })

    # Normal Messages
    elif "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        chat_type = msg["chat"]["type"]
        text = msg.get("text", "")

        # Store Groups where bot is added
        if chat_type in ["group", "supergroup"]:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO groups (group_id) VALUES (?)", (chat_id,))
            conn.commit()
            conn.close()

        # Commands
        if text.startswith("/start"):
            if chat_type == "private":
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (chat_id,))
                conn.commit()
                conn.close()

            welcome_text = (
                "🔥 *Welcome to Daily Price Alert!*\n\n"
                "Aapko saste se saste active plans aur deals bilkul free me milenge.\n\n"
                "📌 *Categories Select Karein:*👇"
            )
            cat_keyboard = {
                "inline_keyboard": [
                    [{"text": "📱 Mobiles", "callback_data": "cat_mobile"}, {"text": "💻 Laptops", "callback_data": "cat_laptop"}],
                    [{"text": "🎧 Audio & Accessories", "callback_data": "cat_audio"}],
                    [{"text": "📢 Join Channel", "url": CHANNEL_LINK}]
                ]
            }
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": welcome_text,
                "parse_mode": "Markdown",
                "reply_markup": cat_keyboard
            })

        # Product Search Command (Example: /search phone)
        elif text.startswith("/search"):
            query = text.replace("/search", "").strip().lower()
            if not query:
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "🔍 *Search Format:* `/search phone` ya `/search laptop`",
                    "parse_mode": "Markdown"
                })
            else:
                results = [d for d in HOT_DEALS if query in d["title"].lower() or query in d["specs"].lower()]
                if results:
                    for deal in results:
                        send_deal(chat_id, deal)
                else:
                    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": f"❌ '{query}' se match karti koi deal nahi mili."
                    })

        elif text.startswith("/postdeal"):
            broadcast_deal()

    return "ok", 200

# Cron Route for Posting Deals and Group Promo
@app.route("/cron-auto-post")
def auto_post_cron():
    broadcast_deal()
    promote_to_groups()
    return "Deal & Group Promo Triggered!", 200

@app.route("/")
def index():
    return "Bot Active!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
