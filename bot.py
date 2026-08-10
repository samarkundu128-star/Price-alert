import os
import logging
import sqlite3
import random
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# config.py se environment variables import ho rahe hain
from config import (
    TELEGRAM_BOT_TOKEN,
    CUELINKS_PUBLISHER_ID,
    AMAZON_TAG,
    PUBLIC_GROUP_ID,
    WEBSITE_URL,
    AUTOPILOT_MODE
)
from services.ai_service import AIService

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Validate configuration token
if not TELEGRAM_BOT_TOKEN:
    logger.critical("❌ TELEGRAM_BOT_TOKEN missing in environment variables!")
    exit(1)

# Initialize AI Service
ai_service = AIService()

# Global variable for Telegram application
telegram_app = None
DEDUP_HOURS = 30
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
CHANNEL_LINK = "https://t.me/daily_price_alert"

TEMPLATES = {
    "promotional_message": "Hello {name}, this is a promotional message from Pricedropdost Bot!"
}

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
        logger.error(f"Database Init Error: {e}")

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
        logger.error(f"Get deals error: {e}")
        return []

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
        return False
    except Exception as e:
        logger.error(f"Dedup check error: {e}")
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
        logger.error(f"Mark posted error: {e}")

def check_link_is_active(url: str) -> bool:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code == 200:
            page_text = response.text.lower()
            if "looking for something" in page_text or "currently unavailable" in page_text:
                return False
            return True
        return False
    except Exception as e:
        logger.error(f"Link check error: {e}")
        return False

# ================= LIFECYCLE & FASTAPI =================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_app
    try:
        telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Handlers
        telegram_app.add_handler(CommandHandler("start", start))
        telegram_app.add_handler(CommandHandler("postdeal", postdeal_command))
        telegram_app.add_handler(CommandHandler("promotional_message", promotional_message_command))
        telegram_app.add_handler(CommandHandler("public_group", public_group_integration))
        telegram_app.add_handler(CommandHandler("website", website_integration))
        telegram_app.add_handler(CallbackQueryHandler(button_handler))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Pricedropdost Bot polling started successfully via FastAPI lifespan.")
        yield
    finally:
        if telegram_app and telegram_app.updater:
            await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
            logger.info("Pricedropdost Bot stopped.")

app = FastAPI(title="Pricedropdost Bot Web Service", lifespan=lifespan)

@app.get("/")
async def health_check():
    return {"status": "online", "bot": "Pricedropdost Bot is running", "amazon_tag": AMAZON_TAG}

@app.get("/cron-auto-post")
def auto_post_cron():
    broadcast_deal()
    return {"status": "Triggered Successfully!"}

def get_start_menu():
    keyboard = [
        [InlineKeyboardButton("📱 Mobiles", callback_data="cat_mobile"), InlineKeyboardButton("💻 Laptops", callback_data="cat_laptop")],
        [InlineKeyboardButton("🌐 Visit Website", callback_data="proj_web")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_text = (
        "👋 **Welcome to Pricedropdost Bot!**\n\n"
        "Send me any product name (e.g., iPhone 15, Samsung S26, Watch) or choose a category below:"
    )
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=get_start_menu(), parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id

    if data.startswith("cat_"):
        cat_type = data.split("_")[1]
        matching_deals = [d for d in get_all_deals() if d["category"] == cat_type]
        if matching_deals:
            for deal in matching_deals:
                await send_deal_to_chat(chat_id, deal)
        else:
            await context.bot.send_message(chat_id=chat_id, text="❌ Iss category me abhi koi active deal nahi hai.")
    elif data == "proj_web":
        await context.bot.send_message(chat_id=chat_id, text=f"Visit our website: {WEBSITE_URL}")

async def send_deal_to_chat(target_id, deal):
    if is_already_posted(deal["id"]):
        return False
    if not check_link_is_active(deal["url"]):
        return False

    # Cuelinks tracking conversion formatting if publisher ID exists
    final_url = deal["url"]
    if CUELINKS_PUBLISHER_ID:
        encoded_url = requests.utils.quote(deal["url"], safe="")
        final_url = f"https://links.cuelinks.com/url?u={encoded_url}&i={CUELINKS_PUBLISHER_ID}"

    caption = (
        f"🔥 *{deal['title']}*\n\n"
        f"❌ M.R.P.: ~{deal['orig_price']}~\n"
        f"💰 *Deal Price: {deal['deal_price']}*\n"
        f"⚡ *Discount:* {deal['discount']}\n\n"
        f"📌 *Key Features:*\n{deal['specs']}\n\n"
        f"🔗 *Tag:* `{AMAZON_TAG}`"
    )

    reply_markup = {
        "inline_keyboard": [
            [{"text": "🛒 Buy Now (Open in App)", "url": final_url}],
            [{"text": "📱 Mobiles", "callback_data": "cat_mobile"}, {"text": "💻 Laptops", "callback_data": "cat_laptop"}]
        ]
    }

    try:
        requests.post(f"{TELEGRAM_API_URL}/sendPhoto", json={
            "chat_id": target_id,
            "photo": deal["image"],
            "caption": caption,
            "parse_mode": "Markdown",
            "reply_markup": reply_markup
        })
    except Exception:
        requests.post(f"{TELEGRAM_API_URL}/sendMessage", json={
            "chat_id": target_id,
            "text": caption,
            "parse_mode": "Markdown",
            "reply_markup": reply_markup
        })

    mark_as_posted(deal["id"])
    return True

def broadcast_deal():
    deals = get_all_deals()
    if not deals:
        return
    deal = random.choice(deals)
    if PUBLIC_GROUP_ID:
        send_deal_to_chat(PUBLIC_GROUP_ID, deal)

async def postdeal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    broadcast_deal()
    if update.message:
        await update.message.reply_text("✅ Deal broadcasted successfully!")

async def promotional_message_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if AUTOPILOT_MODE and PUBLIC_GROUP_ID:
        await context.bot.send_message(
            chat_id=PUBLIC_GROUP_ID, 
            text=TEMPLATES["promotional_message"].format(name="World", bot_name="Pricedropdost")
        )
    else:
        if update.message:
            await update.message.reply_text(
                TEMPLATES["promotional_message"].format(name=update.effective_user.first_name, bot_name="Pricedropdost")
            )

async def public_group_integration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if PUBLIC_GROUP_ID:
        await context.bot.send_message(
            chat_id=PUBLIC_GROUP_ID, 
            text=TEMPLATES["promotional_message"].format(name="World", bot_name="Pricedropdost")
        )

async def website_integration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = TEMPLATES["promotional_message"].format(name=update.effective_user.first_name, bot_name="Pricedropdost")
    full_message = f"{message} Visit our website: {WEBSITE_URL}"
    if update.message:
        await update.message.reply_text(full_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Fuzzy-style local search match through active deals or AI fallback
    deals = get_all_deals()
    matched = [d for d in deals if user_message.lower() in d['title'].lower() or user_message.lower() in d['category'].lower()]
    
    if matched:
        for deal in matched:
            await send_deal_to_chat(update.effective_chat.id, deal)
    else:
        ai_response = ai_service.generate_response(user_message)
        await update.message.reply_text(f"{ai_response}\n\n🔗 *Affiliate Tag:* `{AMAZON_TAG}`", parse_mode="Markdown")
        
