import os
import sqlite3
import requests
import logging
import random
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from flask import Flask, request

# ================= CONFIGURATION =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8827005241:AAG-mAj8EkJmMrSi2KC8FobuucBwbFxJofY")
CHANNEL_ID = "@daily_price_alert"
CHANNEL_LINK = "https://t.me/daily_price_alert"
BOT_USERNAME = "price_alert_zs93_bot"
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

AMAZON_TAG = "pricedropdost-21"
DEDUP_HOURS = 30

app = Flask(__name__)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# ================= DATABASE SETUP =================
def init_db():
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, referrals INTEGER DEFAULT 0)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS optin_groups (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                username TEXT,
                date_added TEXT,
                promo_status TEXT DEFAULT 'disabled',
                last_promo_time TEXT,
                daily_count INTEGER DEFAULT 0,
                last_reset_date TEXT
            )
        """)
        cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS posted_deals (deal_id TEXT PRIMARY KEY, posted_at TEXT)")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id TEXT PRIMARY KEY,
                category TEXT,
                title TEXT,
                orig_price TEXT,
                deal_price TEXT,
                discount TEXT,
                specs TEXT,
                image TEXT,
                url TEXT
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('promo_interval_mins', '30')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_group_limit', '20')")
        
        cursor.execute("SELECT COUNT(*) FROM deals")
        if cursor.fetchone()[0] == 0:
            default_deals = [
                ("hp_15_ultra", "laptop", "💻 HP 15, Intel Core Ultra 5 125H (16GB RAM, 1TB SSD)", "₹86,451", "₹77,990", "10% OFF 🔥", "• Intel Arc Graphics\n• 15.6\" FHD IPS Display", "https://m.media-amazon.com/images/I/71XvO-0bO5L._SL1500_.jpg", f"https://www.amazon.in/dp/B0D131NS5K?tag={AMAZON_TAG}"),
                ("samsung_m35", "mobile", "📱 Samsung Galaxy M35 5G (8GB RAM, 128GB)", "₹24,999", "₹19,999", "20% OFF 🔥", "• 6000mAh Battery\n• 120Hz Super AMOLED", "https://m.media-amazon.com/images/I/71d7rfSl0wL._SL1500_.jpg", f"https://www.amazon.in/dp/B0D782C2LK?tag={AMAZON_TAG}")
            ]
            cursor.executemany("INSERT OR IGNORE INTO deals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", default_deals)

        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Database Init Error: {e}")

init_db()

def get_all_deals():
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, category, title, orig_price, deal_price, discount, specs, image, url FROM deals")
        rows = cursor.fetchall()
        conn.close()
        deals = []
        for r in rows:
            deals.append({
                "id": r[0], "category": r[1], "title": r[2], "orig_price": r[3],
                "deal_price": r[4], "discount": r[5], "specs": r[6], "image": r[7], "url": r[8]
            })
        return deals
    except Exception as e:
        logging.error(f"Get deals error: {e}")
        return []

def get_setting(key):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None

# ================= DUPLICATE & LINK VALIDATION =================
def is_already_posted(deal_id: str) -> bool:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT posted_at FROM posted_deals WHERE deal_id = ?", (deal_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            posted_at = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - posted_at < timedelta(hours=DEDUP_HOURS):
                return True
            else:
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("DELETE FROM posted_deals WHERE deal_id = ?", (deal_id,))
                conn.commit()
                conn.close()
        return False
    except Exception as e:
        logging.error(f"Dedup check error: {e}")
        return False

def mark_as_posted(deal_id: str):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO posted_deals (deal_id, posted_at) VALUES (?, ?)",
                       (deal_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Mark posted error: {e}")

def check_link_is_active(url: str) -> bool:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code == 200:
            page_text = response.text.lower()
            if "looking for something" in page_text or "currently unavailable" in page_text:
                return False
            return True
        return False
    except Exception as e:
        logging.error(f"Link check error for {url}: {e}")
        return False

# ================= PROMO TEMPLATES =================
PROMO_TEMPLATES = [
    (
        "🔥 Aaj ka best deal miss mat karo!\n\n"
        "📱 Phones • 💻 Laptops • 🖥️ PCs\n"
        "💸 Price-drop alerts • 🛒 Smart deals\n\n"
        f"📢 Daily Deals:\n👉 {CHANNEL_LINK}\n\n"
        f"🤖 Try PriceDrop Dost:\n👉 @{BOT_USERNAME}"
    )
]

# ================= CORE FUNCTIONS =================
def send_deal(target_id, deal):
    if is_already_posted(deal["id"]):
        logging.info(f"Skipped duplicate deal: {deal['id']}")
        return False

    if not check_link_is_active(deal["url"]):
        logging.warning(f"Skipped dead or unavailable link: {deal['title']} ({deal['url']})")
        return False

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
            [{"text": "🛒 Buy Now (Open in App)", "url": deal["url"]}],
            [
                {"text": "📱 Mobiles", "callback_data": "cat_mobile"},
                {"text": "💻 Laptops", "callback_data": "cat_laptop"}
            ],
            [{"text": "📢 Join Main Channel", "url": CHANNEL_LINK}]
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

    mark_as_posted(deal["id"])
    return True

def broadcast_deal():
    deals = get_all_deals()
    if not deals:
        return
    deal = random.choice(deals)

    send_deal(CHANNEL_ID, deal)

    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()
        for user in users:
            send_deal(user[0], deal)
    except Exception as e:
        logging.error(f"User Broadcast Error: {e}")

def run_scheduled_promotions():
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT group_id, group_name, promo_status, last_promo_time, daily_count, last_reset_date FROM optin_groups")
        groups = cursor.fetchall()
        conn.close()
    except Exception as e:
        return f"DB Error: {e}"

    sent_count = 0
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    interval_mins = int(get_setting("promo_interval_mins") or 30)
    daily_limit = int(get_setting("daily_group_limit") or 20)

    for g_id, g_name, status, last_time, daily_cnt, last_reset in groups:
        if status != 'active':
            continue
        if last_reset != today_str:
            daily_cnt = 0
        if daily_cnt >= daily_limit:
            continue

        template_text = random.choice(PROMO_TEMPLATES)
        reply_markup = {
            "inline_keyboard": [
                [{"text": "📢 Join Channel", "url": CHANNEL_LINK}],
                [{"text": "🤖 Open Bot", "url": f"https://t.me/{BOT_USERNAME}"}]
            ]
        }

        try:
            res = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                "chat_id": g_id,
                "text": template_text,
                "parse_mode": "Markdown",
                "reply_markup": reply_markup
            })
            if res.status_code == 200:
                sent_count += 1
        except Exception:
            pass

    return "Opt-in promotion cycle finished."

# ================= FLASK WEBHOOK HANDLER =================
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
            matching_deals = [d for d in get_all_deals() if d["category"] == cat_type]
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
        text = msg.get("text", "").strip()

        if text.startswith("/start"):
            welcome_text = "🔥 *Welcome to Daily Price Alert!*\n\nSelect a category below to check live deals:"
            cat_keyboard = {
                "inline_keyboard": [
                    [{"text": "📱 Mobiles", "callback_data": "cat_mobile"}, {"text": "💻 Laptops", "callback_data": "cat_laptop"}],
                    [{"text": "📢 Join Official Channel", "url": CHANNEL_LINK}]
                ]
            }
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                "chat_id": chat_id,
                "text": welcome_text,
                "parse_mode": "Markdown",
                "reply_markup": cat_keyboard
            })
        elif text.startswith("/postdeal"):
            broadcast_deal()

    return "ok", 200

@app.route("/cron-auto-post")
def auto_post_cron():
    broadcast_deal()
    run_scheduled_promotions()
    return "Triggered Successfully!", 200

@app.route("/")
def index():
    return "Bot is Active!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
            
