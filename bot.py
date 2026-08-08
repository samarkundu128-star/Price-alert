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
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Database Init Error: {e}")

init_db()

# ================= HOT DEALS DATABASE =================
HOT_DEALS = [
    {
        "title": "📱 Samsung Galaxy M35 5G (8GB RAM, 128GB)",
        "orig_price": "₹24,999",
        "deal_price": "₹13,999",
        "discount": "44% OFF 🔥 (Lowest Price Ever!)",
        "specs": "• 6000mAh Battery\n• 120Hz Super AMOLED Display\n• 50MP OIS Camera",
        "image": "https://m.media-amazon.com/images/I/71d7rfSl0wL._SL1500_.jpg",
        "url": "https://www.amazon.in/dp/B0D782C2LK"
    },
    {
        "title": "💻 ASUS Vivobook 15 Intel Core i3 12th Gen",
        "orig_price": "₹49,990",
        "deal_price": "₹32,990",
        "discount": "34% OFF ⚡ (Heavy Drop)",
        "specs": "• 8GB RAM / 512GB SSD\n• Thin & Light Design\n• Windows 11 + MS Office",
        "image": "https://m.media-amazon.com/images/I/71S8U9VzLTL._SL1500_.jpg",
        "url": "https://www.amazon.in/dp/B0C3R82KWY"
    },
    {
        "title": "🎧 boAt Airdopes 141 TWS Earbuds",
        "orig_price": "₹4,490",
        "deal_price": "₹999",
        "discount": "78% OFF 💥 (Loot Deal)",
        "specs": "• 42 Hours Playtime\n• Low Latency Gaming Mode\n• IPX4 Water Resistance",
        "image": "https://m.media-amazon.com/images/I/61KNJ34s9OL._SL1500_.jpg",
        "url": "https://www.amazon.in/dp/B09N3Z3Y89"
    }
]

# ================= TELEGRAM API SENDER =================
def send_deal_to_target(target_id, deal):
    caption = (
        f"🔥 *{deal['title']}*\n\n"
        f"❌ M.R.P.: ~{deal['orig_price']}~\n"
        f"💰 *Deal Price: {deal['deal_price']}*\n"
        f"⚡ *Discount:* {deal['discount']}\n\n"
        f"📌 *Key Features:*\n{deal['specs']}\n\n"
        f"📢 Daily Price Updates: {CHANNEL_ID}"
    )

    reply_markup = {
        "inline_keyboard": [
            [{"text": "🛒 Direct Buy Product Here", "url": deal["url"]}]
        ]
    }

    # Send Photo with Caption and Buy Button directly
    try:
        res = requests.post(f"{TELEGRAM_API_URL}/sendPhoto", json={
            "chat_id": target_id,
            "photo": deal["image"],
            "caption": caption,
            "parse_mode": "Markdown",
            "reply_markup": reply_markup
        })
        logging.info(f"Photo Deal Sent ({target_id}): {res.status_code}")
    except Exception as e:
        logging.error(f"Send Photo Error: {e}")

def broadcast_deal():
    deal = random.choice(HOT_DEALS)
    
    # 1. Post to Channel
    send_deal_to_target(CHANNEL_ID, deal)

    # 2. Post to Personal Users
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()

        for user in users:
            send_deal_to_target(user[0], deal)
    except Exception as e:
        logging.error(f"DB Read Error: {e}")

# ================= FLASK ROUTES =================
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json(force=True)
    if "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

        if text.startswith("/start"):
            try:
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (chat_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                logging.error(f"DB Write Error: {e}")

            welcome_text = (
                "🔥 *Welcome to Daily Price Update!*\n\n"
                "Ab aapko sasti deals *Personal Chat + Channel* dono jagah milengi!\n\n"
                "📢 *Join Channel:*\n"
                f"👉 [Click Here to Join Channel]({CHANNEL_LINK})"
            )
            reply_markup = {
                "inline_keyboard": [[{"text": "📢 Join Channel", "url": CHANNEL_LINK}]]
            }
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": welcome_text,
                "parse_mode": "Markdown",
                "reply_markup": reply_markup,
                "disable_web_page_preview": True
            })

        elif text.startswith("/postdeal"):
            broadcast_deal()
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": "✅ Deal instant post kar di gayi hai!"
            })

    return "ok", 200

@app.route("/cron-auto-post")
def auto_post_cron():
    broadcast_deal()
    return "Deal Triggered Successfully!", 200

@app.route("/")
def index():
    return "Daily Deals Bot Active!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
        
