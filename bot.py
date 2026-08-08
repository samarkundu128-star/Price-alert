import logging
import os
import random
import sqlite3
import requests
from datetime import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Configuration Variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/YOUR_CHANNEL_LINK")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # Replace with your Telegram ID
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-app-name.onrender.com")

# Initialize Flask for Render Webhook & Keeping Bot Alive
app = Flask(__name__)

# Logging Setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ================= DATABASE SETUP =================
def init_db():
    """SQLite Database setup for Users, Products, Whitelisted Groups, and Admin Config"""
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER
        )
    """)
    
    # Tracked Products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            platform TEXT,
            url TEXT,
            target_price REAL,
            last_price REAL,
            updated_at TEXT
        )
    """)
    
    # Whitelisted Groups table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approved_groups (
            group_id INTEGER PRIMARY KEY
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ================= CAPTION & ROTATION SYSTEM =================
SHORT_CAPTIONS = [
    "🔥 Phone price down! Jaldi check karo.",
    "💸 Aaj ka best laptop deal live hai.",
    "⚡ Flash sale start! Limited stock.",
    "📱 Best phone under 15k ab aur sasta.",
    "🛒 Deal miss mat karo, price kabhi bhi badh sakta hai.",
    "🚀 Dhamaka deal! Price drop ho gaya.",
    "🤩 Itna sasta dobara nahi milega!"
]

def get_random_caption():
    """Smart Rotation: Pick random short caption"""
    return random.choice(SHORT_CAPTIONS)

# ================= PRICE CHECKER (FAIL-SAFE RETRY) =================
def fetch_product_details(url):
    """
    Mock scraper with Fail-Safe Retry logic.
    Supports Amazon, Flipkart, and Meesho.
    """
    platform = "Unknown"
    if "amazon" in url:
        platform = "Amazon"
    elif "flipkart" in url:
        platform = "Flipkart"
    elif "meesho" in url:
        platform = "Meesho"

    # Retry 3 times system
    for attempt in range(3):
        try:
            # Simulated extracted data (In real setup, scrape or use API)
            dummy_price = round(random.uniform(999, 14999), 2)
            return {
                "success": True,
                "title": f"Sample {platform} Item",
                "price": dummy_price,
                "platform": platform
            }
        except Exception:
            continue

    # Fallback response if fetch fails completely
    return {"success": False, "price": 0, "platform": platform}

# ================= TELEGRAM HANDLERS =================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with buttons and referral check"""
    user_id = update.effective_user.id
    
    # Save user to DB if not exists
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    welcome_text = (
        "🔥 **Welcome to PriceDrop Dost!**\n\n"
        "Best phone, laptop, PC and daily deals in easy English.\n\n"
        "📢 **Join our deals channel first:**\n"
        f"👉 [Click Here to Join]({CHANNEL_LINK})\n\n"
        "👇 Send any Amazon, Flipkart or Meesho product link to start tracking price.\n\n"
        "📢 Daily best deals:\n"
        f"👉 [Join Deals Channel]({CHANNEL_LINK})"
    )

    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("⚡ Track Product", callback_data="track_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup, disable_web_page_preview=True)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process incoming URLs from Amazon, Flipkart, or Meesho"""
    text = update.message.text
    user_id = update.effective_user.id

    if any(p in text for p in ["amazon", "flipkart", "meesho"]):
        await update.message.reply_text("⏳ Price check kar rahe hain, wait karo...")

        data = fetch_product_details(text)
        if data["success"]:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO products (user_id, platform, url, last_price, updated_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, data["platform"], text, data["price"], datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            conn.commit()
            conn.close()

            caption = get_random_caption()
            
            response = (
                f"✅ **Tracking Start Ho Gaya!**\n\n"
                f"📦 **Platform:** {data['platform']}\n"
                f"💰 **Current Price:** ₹{data['price']}\n\n"
                f"⚡ {caption}\n\n"
                f"📢 Daily best deals:\n👉 {CHANNEL_LINK}"
            )
            
            keyboard = [[InlineKeyboardButton("🛒 Buy Now", url=text)]]
            await update.message.reply_text(response, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
        else:
            await update.message.reply_text("❌ Link fetch nahi ho paya. Dobara try karein.")
    else:
        await update.message.reply_text("⚠️ Direct Amazon, Flipkart, ya Meesho ka link bhejo.")


async def mydeals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User Tracking Dashboard"""
    user_id = update.effective_user.id
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT platform, last_price, updated_at FROM products WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Aapne koi product track nahi kiya hai.")
        return

    msg = "📊 **Aapke Tracked Products:**\n\n"
    for idx, r in enumerate(rows, 1):
        msg += f"{idx}. **{r[0]}** - ₹{r[1]} (Updated: {r[2]})\n"

    msg += f"\n📢 Daily best deals:\n👉 {CHANNEL_LINK}"
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)


# ================= ADMIN & GROUP CONTROL =================

async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Whitelist group command"""
    if update.effective_user.id != ADMIN_ID:
        return
    
    chat_id = update.effective_chat.id
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO approved_groups VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ Ye group auto-posting ke liye approve ho gaya!")

# ================= TELEGRAM APP SETUP =================

ptb_app = Application.builder().token(BOT_TOKEN).build()

ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CommandHandler("mydeals", mydeals_command))
ptb_app.add_handler(CommandHandler("add_group", add_group))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook Routes for Render
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def respond():
    """Receive Telegram Webhook Updates"""
    update = Update.de_json(request.get_json(force=True), ptb_app.bot)
    ptb_app.update_queue.put_nowait(update)
    return "ok", 200

@app.route("/")
def index():
    return "PriceDrop Dost Bot is Active!", 200

# ================= STARTUP SCRIPT =================
if __name__ == "__main__":
    import asyncio
    
    # Initialize webhook on startup
    async def setup_webhook():
        await ptb_app.initialize()
        await ptb_app.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
        await ptb_app.start()

    asyncio.run(setup_webhook())
