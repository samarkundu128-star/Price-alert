import os
import sqlite3
import requests
import logging
from flask import Flask, request

# ================= CONFIGURATION =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8827005241:AAG-mAj8EkJmMrSi2KC8FobuucBwbFxJofY")
CHANNEL_ID = "@daily_price_alert"
CHANNEL_LINK = "https://t.me/daily_price_alert"
BOT_USERNAME = "price_alert_zs93_bot"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

deal_index = 0

# ================= DATABASE SETUP =================
def init_db():
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, referrals INTEGER DEFAULT 0)")
        cursor.execute("CREATE TABLE IF NOT EXISTS groups (group_id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Database Init Error: {e}")

init_db()

# ================= HOT DEALS DATABASE (WORKING AMAZON SEARCH LINKS) =================
HOT_DEALS = [
    {
        "id": "samsung_m35",
        "category": "mobile",
        "title": "📱 Samsung Galaxy M35 5G (8GB RAM, 128GB)",
        "orig_price": "₹24,999",
        "deal_price": "₹13,999",
        "discount": "44% OFF 🔥 (Lowest Price Ever!)",
        "specs": "• 6000mAh Battery\n• 120Hz Super AMOLED Display\n• 50MP OIS Camera",
        "image": "https://m.media-amazon.com/images/I/71d7rfSl0wL._SL1500_.jpg",
        "url": "https://www.amazon.in/s?k=Samsung+Galaxy+M35+5G+128GB"
    },
    {
        "id": "asus_vivobook",
        "category": "laptop",
        "title": "💻 ASUS Vivobook 15 Intel Core i3 12th Gen",
        "orig_price": "₹49,990",
        "deal_price": "₹32,990",
        "discount": "34% OFF ⚡ (Heavy Drop)",
        "specs": "• 8GB RAM / 512GB SSD\n• Thin & Light Design\n• Windows 11 + MS Office",
        "image": "https://m.media-amazon.com/images/I/71S8U9VzLTL._SL1500_.jpg",
        "url": "https://www.amazon.in/s?k=ASUS+Vivobook+15+i3+12th+Gen"
    },
    {
        "id": "boat_141",
        "category": "audio",
        "title": "🎧 boAt Airdopes 141 TWS Earbuds",
        "orig_price": "₹4,490",
        "deal_price": "₹999",
        "discount": "78% OFF 💥 (Loot Deal)",
        "specs": "• 42 Hours Playtime\n• Low Latency Gaming Mode\n• IPX4 Water Resistance",
        "image": "https://m.media-amazon.com/images/I/61KNJ34s9OL._SL1500_.jpg",
        "url": "https://www.amazon.in/s?k=boAt+Airdopes+141"
    }
]

# ================= TELEGRAM FUNCTIONS =================
def send_deal(target_id, deal):
    caption = (
        f"🔥 *{deal['title']}*\n\n"
        f"❌ M.R.P.: ~{deal['orig_price']}~\n"
        f"💰 *Deal Price: {deal['deal_price']}*\n"
        f"⚡ *Discount:* {deal['discount']}\n\n"
        f"📌 *Key Features:*\n{deal['specs']}\n\n"
        f"📢 Join Channel: {CHANNEL_ID}"
    )

    share_text = f"🔥 Checkout this deal: {deal['title']} at {deal['deal_price']}!\nJoin: {CHANNEL_LINK}"
    share_url = f"https://t.me/share/url?url={CHANNEL_LINK}&text={requests.utils.quote(share_text)}"

    reply_markup = {
        "inline_keyboard": [
            [{"text": "🛒 Direct Buy Product Here", "url": deal["url"]}],
            [{"text": "⏩ Share Deal with Friends", "url": share_url}]
        ]
    }

    res = requests.post(f"{TELEGRAM_API_URL}/sendPhoto", json={
        "chat_id": target_id,
        "photo": deal["image"],
        "caption": caption,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    })

    if res.status_code != 200:
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
            "chat_id": target_id,
            "text": caption,
            "parse_mode": "Markdown",
            "reply_markup": reply_markup,
            "disable_web_page_preview": False
        })

def broadcast_deal():
    global deal_index
    deal = HOT_DEALS[deal_index % len(HOT_DEALS)]
    deal_index += 1

    send_deal(CHANNEL_ID, deal)

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
        "Daily Amazon/Flipkart flash sales, 80% OFF tech deals aur loot offers paane ke liye abhi hamare channel ko join karein! 🚀\n\n"
        f"📢 *Main Channel:* {CHANNEL_LINK}"
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

# ================= FLASK WEBHOOK =================
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json(force=True)

    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb["id"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")

        requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": cb_id})

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

    elif "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        chat_type = msg["chat"]["type"]
        text = msg.get("text", "")

        if chat_type in ["group", "supergroup"]:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO groups (group_id) VALUES (?)", (chat_id,))
            conn.commit()
            conn.close()

        if text.startswith("/start"):
            ref_id = None
            parts = text.split(" ")
            if len(parts) > 1 and parts[1].isdigit():
                ref_id = int(parts[1])

            if chat_type == "private":
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (chat_id,))
                
                if ref_id and ref_id != chat_id:
                    cursor.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (ref_id,))
                
                conn.commit()
                conn.close()

            ref_link = f"https://t.me/{BOT_USERNAME}?start={chat_id}"
            
            welcome_text = (
                "🔥 *Welcome to Daily Price Alert!*\n\n"
                "Aapko saste se saste active plans aur deals bilkul free me milengi.\n\n"
                "🔍 *Product Search Kaise Karein?*\n"
                "Kisi bhi item ko khojne ke liye chat me likhein:\n"
                "👉 `/search phone` ya `/search laptop` ya `/search audio`\n\n"
                f"🎁 *Aapka Referral Link:* `{ref_link}`\n\n"
                "📌 *Categories Se Deals Dekhein:*👇"
            )
            cat_keyboard = {
                "inline_keyboard": [
                    [{"text": "📱 Mobiles Deals", "callback_data": "cat_mobile"}, {"text": "💻 Laptop Deals", "callback_data": "cat_laptop"}],
                    [{"text": "🎧 Audio & Earbuds", "callback_data": "cat_audio"}],
                    [{"text": "📢 Join Official Channel", "url": CHANNEL_LINK}]
                ]
            }
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": welcome_text,
                "parse_mode": "Markdown",
                "reply_markup": cat_keyboard
            })

        elif text.startswith("/search"):
            query = text.replace("/search", "").strip().lower()
            if not query:
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "🔍 *Search Format:* `/search phone` ya `/search laptop`",
                    "parse_mode": "Markdown"
                })
            else:
                results = [d for d in HOT_DEALS if query in d["title"].lower() or query in d["specs"].lower() or query in d["category"].lower()]
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

@app.route("/cron-auto-post")
def auto_post_cron():
    broadcast_deal()
    promote_to_groups()
    return "Deal & Group Promo Triggered!", 200

@app.route("/")
def index():
    return "Daily Deals Bot Active!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
    
