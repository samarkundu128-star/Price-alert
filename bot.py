import os
import sqlite3
import requests
import logging
import random
import hashlib
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
DEDUP_HOURS = 30          # Same deal kitne hours tak nahi post hoga

app = Flask(__name__)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

deal_index = 0

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
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('promo_interval_mins', '30')")
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_group_limit', '20')")
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Database Init Error: {e}")

init_db()

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

def set_setting(key, value):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Setting Update Error: {e}")

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
    """Ye function check karega ki Amazon link live hai ya 'Looking for something' error de rahi hai"""
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
    ),
    (
        "💸 Deal miss mat karo!\n\n"
        "PriceDrop Dost automatically finds useful deals & price drops.\n\n"
        f"📢 Daily deals:\n👉 {CHANNEL_LINK}\n\n"
        f"🤖 Open Bot:\n👉 @{BOT_USERNAME}"
    ),
    (
        "⚡ Smart Shopping on Telegram\n\n"
        "🔥 Price drops\n📱 Best phones\n💻 Best laptops\n🛒 Amazon + Flipkart deals\n\n"
        f"👉 {CHANNEL_LINK}\n\n"
        f"🤖 @{BOT_USERNAME}"
    )
]

# ================= HOT DEALS CATALOG =================
HOT_DEALS = [
    {
        "id": "hp_15_ultra",
        "category": "laptop",
        "title": "💻 HP 15, Intel Core Ultra 5 125H (16GB RAM, 1TB SSD)",
        "orig_price": "₹86,451",
        "deal_price": "₹77,990",
        "discount": "10% OFF 🔥 (Freedom Sale Mega Deal)",
        "specs": "• Intel Arc Graphics\n• 15.6\" FHD IPS Display\n• Win 11 + MS Office 2024",
        "image": "https://m.media-amazon.com/images/I/71XvO-0bO5L._SL1500_.jpg",
        "url": f"https://www.amazon.in/dp/B0D131NS5K?tag={AMAZON_TAG}"
    },
    {
        "id": "asus_vivobook_16",
        "category": "laptop",
        "title": "💻 ASUS Vivobook 16, Intel Core Ultra 5",
        "orig_price": "₹93,990",
        "deal_price": "₹72,990",
        "discount": "22% OFF ⚡ (Limited Time Deal)",
        "specs": "• 16GB DDR5 / 512GB SSD\n• Thin & Light Design\n• ASUS AI Features",
        "image": "https://m.media-amazon.com/images/I/71S8U9VzLTL._SL1500_.jpg",
        "url": f"https://www.amazon.in/dp/B0CX58S11D?tag={AMAZON_TAG}"
    },
    {
        "id": "samsung_m35",
        "category": "mobile",
        "title": "📱 Samsung Galaxy M35 5G (8GB RAM, 128GB)",
        "orig_price": "₹24,999",
        "deal_price": "₹19,999",
        "discount": "20% OFF 🔥 (Official Price)",
        "specs": "• 6000mAh Battery\n• 120Hz Super AMOLED Display\n• 50MP OIS Camera",
        "image": "https://m.media-amazon.com/images/I/71d7rfSl0wL._SL1500_.jpg",
        "url": f"https://www.amazon.in/dp/B0D782C2LK?tag={AMAZON_TAG}"
    },
    {
        "id": "boat_141",
        "category": "audio",
        "title": "🎧 boAt Airdopes 141 TWS Earbuds",
        "orig_price": "₹4,490",
        "deal_price": "₹1,299",
        "discount": "71% OFF 💥 (Best Seller)",
        "specs": "• 42 Hours Playtime\n• Low Latency Gaming Mode\n• IPX4 Water Resistance",
        "image": "https://m.media-amazon.com/images/I/61KNJ34s9OL._SL1500_.jpg",
        "url": f"https://www.amazon.in/dp/B09N3Z3Y89?tag={AMAZON_TAG}"
    }
]

# ================= CORE FUNCTIONS =================
def send_deal(target_id, deal):
    # 1. Duplicate Check
    if is_already_posted(deal["id"]):
        logging.info(f"Skipped duplicate deal: {deal['id']}")
        return False

    # 2. Link Active Status Check (Agar link dead ya unavailable hai toh post nahi karega)
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
                {"text": "💻 Laptops", "callback_data": "cat_laptop"},
                {"text": "🎧 Audio", "callback_data": "cat_audio"}
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
    global deal_index
    deal = HOT_DEALS[deal_index % len(HOT_DEALS)]
    deal_index += 1

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

# ================= AUTOMATIC OPT-IN PROMOTION RUNNER =================
def run_scheduled_promotions():
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT group_id, group_name, promo_status, last_promo_time, daily_count, last_reset_date FROM optin_groups")
        groups = cursor.fetchall()
        conn.close()
    except Exception as e:
        return f"DB Error: {e}"

    sent_count, skipped_count, failed_count = 0, 0, 0
    report_lines = []
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    interval_mins = int(get_setting("promo_interval_mins") or 30)
    daily_limit = int(get_setting("daily_group_limit") or 20)

    for idx, (g_id, g_name, status, last_time, daily_cnt, last_reset) in enumerate(groups, start=1):
        if status != 'active':
            continue

        if last_reset != today_str:
            daily_cnt = 0
            last_reset = today_str

        if daily_cnt >= daily_limit:
            skipped_count += 1
            report_lines.append(f"⏭️ {g_name} — Daily limit reached")
            continue

        if last_time:
            last_dt = datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S")
            diff_mins = (now - last_dt).total_seconds() / 60
            if diff_mins < interval_mins:
                skipped_count += 1
                report_lines.append(f"⏭️ {g_name} — Rate limit")
                continue

        template_text = random.choice(PROMO_TEMPLATES)
        reply_markup = {
            "inline_keyboard": [
                [{"text": "📢 Join Channel", "url": CHANNEL_LINK}],
                [{"text": "🤖 Open Bot", "url": f"https://t.me/{BOT_USERNAME}"}],
                [{"text": "❌ Disable Promotions", "callback_data": f"optout_{g_id}"}]
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
                daily_cnt += 1
                report_lines.append(f"🟢 {g_name} — Sent")
                update_group_promo_state(g_id, now.strftime("%Y-%m-%d %H:%M:%S"), daily_cnt, last_reset)
            else:
                failed_count += 1
                report_lines.append(f"❌ {g_name} — Failed")
                if res.status_code in [403, 400]:
                    handle_bot_removed(g_id, g_name)
        except Exception as ex:
            failed_count += 1
            report_lines.append(f"❌ {g_name} — Error")

    if ADMIN_USER_ID != 0 and report_lines:
        report_text = (
            "📢 *Promotion Report*\n\n"
            f"✅ Sent: `{sent_count}`\n"
            f"⏭️ Skipped: `{skipped_count}`\n"
            f"❌ Failed: `{failed_count}`\n\n"
            "*Groups:*\n" + "\n".join(report_lines)
        )
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
            "chat_id": ADMIN_USER_ID,
            "text": report_text,
            "parse_mode": "Markdown"
        })

    return "Opt-in promotion cycle finished."

def update_group_promo_state(g_id, time_str, count, reset_date):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE optin_groups 
            SET last_promo_time = ?, daily_count = ?, last_reset_date = ? 
            WHERE group_id = ?
        """, (time_str, count, reset_date, g_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"State Update Error: {e}")

def handle_bot_removed(g_id, g_name):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE optin_groups SET promo_status = 'removed' WHERE group_id = ?", (g_id,))
        conn.commit()
        conn.close()
        if ADMIN_USER_ID != 0:
            alert = f"⚠️ *Alert Notification*\nBot was removed or lost permissions in group: *{g_name}* (ID: `{g_id}`)"
            requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                "chat_id": ADMIN_USER_ID,
                "text": alert,
                "parse_mode": "Markdown"
            })
    except Exception as e:
        logging.error(f"Removal Handler Error: {e}")

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
            matching_deals = [d for d in HOT_DEALS if d["category"] == cat_type]
            if matching_deals:
                for deal in matching_deals:
                    send_deal(chat_id, deal)
            else:
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "❌ Iss category me abhi koi active deal nahi hai."
                })

        elif data.startswith("optin_"):
            g_id = int(data.split("_")[1])
            try:
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE optin_groups SET promo_status = 'active' WHERE group_id = ?", (g_id,))
                conn.commit()
                conn.close()
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "✅ *Promotions Enabled Successfully!* PriceDrop Dost deals will now be shared here.",
                    "parse_mode": "Markdown"
                })
            except Exception as e:
                logging.error(f"Optin Error: {e}")

        elif data.startswith("optout_"):
            g_id = int(data.split("_")[1])
            try:
                conn = sqlite3.connect("database.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE optin_groups SET promo_status = 'disabled' WHERE group_id = ?", (g_id,))
                conn.commit()
                conn.close()
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": "❌ *Promotions Disabled* by group interaction.",
                    "parse_mode": "Markdown"
                })
                if ADMIN_USER_ID != 0:
                    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                        "chat_id": ADMIN_USER_ID,
                        "text": f"⚠️ Group ID `{g_id}` has disabled promotions.",
                        "parse_mode": "Markdown"
                    })
            except Exception as e:
                logging.error(f"Optout Error: {e}")

    elif "my_chat_member" in update:
        mcm = update["my_chat_member"]
        chat = mcm["chat"]
        new_status = mcm["new_chat_member"]["status"]
        if chat["type"] in ["group", "supergroup"]:
            g_id = chat["id"]
            g_name = chat.get("title", "Unknown Group")
            g_username = chat.get("username", "")
            date_added = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if new_status in ["member", "administrator"]:
                try:
                    conn = sqlite3.connect("database.db")
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR IGNORE INTO optin_groups (group_id, group_name, username, date_added, promo_status)
                        VALUES (?, ?, ?, ?, 'disabled')
                    """, (g_id, g_name, g_username, date_added))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logging.error(f"Auto-save group error: {e}")

                setup_text = (
                    "🔥 *PriceDrop Dost Promotion*\n\n"
                    "Want to receive useful deal updates in this group?\n\n"
                    "📱 Best phone deals\n"
                    "💻 Laptop & PC deals\n"
                    "💸 Price drops\n"
                    "🛒 Shopping deals"
                )
                setup_markup = {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Enable Deals", "callback_data": f"optin_{g_id}"},
                            {"text": "❌ Don't Enable", "callback_data": f"optout_{g_id}"}
                        ]
                    ]
                }
                requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                    "chat_id": g_id,
                    "text": setup_text,
                    "parse_mode": "Markdown",
                    "reply_markup": setup_markup
                })
            elif new_status in ["left", "kicked"]:
                handle_bot_removed(g_id, g_name)

    elif "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        chat_type = msg["chat"]["type"]
        text = msg.get("text", "").strip()

        if text.startswith("/promo_on"):
            if chat_type in ["group", "supergroup"]:
                try:
                    conn = sqlite3.connect("database.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE optin_groups SET promo_status = 'active' WHERE group_id = ?", (chat_id,))
                    conn.commit()
                    conn.close()
                    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": "🟢 Group promotions enabled via `/promo_on` command."
                    })
                except Exception as e:
                    logging.error(f"Promo On Error: {e}")
        elif text.startswith("/promo_off"):
            if chat_type in ["group", "supergroup"]:
                try:
                    conn = sqlite3.connect("database.db")
                    cursor = conn.cursor()
                    cursor.execute("UPDATE optin_groups SET promo_status = 'disabled' WHERE group_id = ?", (chat_id,))
                    conn.commit()
                    conn.close()
                    requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
                        "chat_id": chat_id,
                        "text": "🔴 Group promotions disabled via `/promo_off` command."
                    })
                except Exception as e:
                    logging.error(f"Promo Off Error: {e}")
                    
