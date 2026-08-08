import logging
import os
import random
import sqlite3
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

# ================= CONFIGURATION VARIABLES =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8827005241:AAG-mAj8EkJmMrSi2KC8FobuucBwbFxJofY")
CHANNEL_LINK = "https://t.me/daily_price_alert"
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://price-alert-zs93.onrender.com")

app = Flask(__name__)
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ================= DATABASE SETUP =================
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            referral_count INTEGER DEFAULT 0,
            referred_by INTEGER
        )
    """)
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS approved_groups (
            group_id INTEGER PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

init_db()

SHORT_CAPTIONS = [
    "🔥 Phone price down! Jaldi check karo.",
    "💸 Aaj ka best laptop deal live hai.",
    "⚡ Flash sale start! Limited stock.",
    "📱 Best phone under 15k ab aur sasta.",
    "🛒 Deal miss mat karo, price kabhi bhi badh sakta hai.",
    "🚀 Dhamaka deal! Price drop ho gaya."
]

def get_random_caption():
    return random.choice(SHORT_CAPTIONS)

def fetch_product_details(url):
    platform = "Unknown"
    if "amazon" in url.lower():
        platform = "Amazon"
    elif "flipkart" in url.lower():
        platform = "Flipkart"
    elif "meesho" in url.lower():
        platform = "Meesho"

    dummy_price = round(random.uniform(999, 14999), 2)
    return {
        "success": True,
        "title": f"Sample {platform} Item",
        "price": dummy_price,
        "platform": platform
    }

# ================= TELEGRAM HANDLERS =================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
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
        f"👉 {CHANNEL_LINK}"
    )

    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("⚡ Track Product", callback_data="track_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        welcome_text, 
        parse_mode="Markdown", 
        reply_markup=reply_markup, 
        disable_web_page_preview=True
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if any(p in text.lower() for p in ["amazon", "flipkart", "meesho"]):
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
            await update.message.reply_text(
                response, 
                parse_mode="Markdown", 
                reply_markup=InlineKeyboardMarkup(keyboard), 
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_text("❌ Link fetch nahi ho paya. Dobara try karein.")
    else:
        await update.message.reply_text("⚠️ Direct Amazon, Flipkart, ya Meesho ka link bhejo.")

async def mydeals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT platform, last_price, updated_at FROM products WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Aapne abhi tak koi product track nahi kiya hai.")
        return

    msg = "📊 **Aapke Tracked Products:**\n\n"
    for idx, r in enumerate(rows, 1):
        msg += f"{idx}. **{r[0]}** - ₹{r[1]} (Updated: {r[2]})\n"

    msg += f"\n📢 Daily best deals:\n👉 {CHANNEL_LINK}"
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

# ================= TELEGRAM APP SETUP =================
ptb_app = Application.builder().token(BOT_TOKEN).build()
ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CommandHandler("mydeals", mydeals_command))
ptb_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Webhook Handler Fix using Asyncio Loop
import asyncio

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def respond():
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, ptb_app.bot)
    
    # Process update synchronously in event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ptb_app.process_update(update))
    loop.close()
    
    return "ok", 200

@app.route("/")
def index():
    return "PriceDrop Dost Bot is Active!", 200

# App initialization
loop = asyncio.get_event_loop()
loop.run_until_complete(ptb_app.initialize())
    
