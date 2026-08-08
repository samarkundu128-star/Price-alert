import asyncio
import logging
import os
import random
import sqlite3
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, ContextTypes

# ================= CONFIGURATION =================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8827005241:AAG-mAj8EkJmMrSi2KC8FobuucBwbFxJofY")
CHANNEL_ID = "@daily_price_alert"
CHANNEL_LINK = "https://t.me/daily_price_alert"

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
        "images": [
            "https://m.media-amazon.com/images/I/71d7rfSl0wL._SL1500_.jpg",
            "https://m.media-amazon.com/images/I/71K8iX2BAnL._SL1500_.jpg",
            "https://m.media-amazon.com/images/I/81P8y-d3kYL._SL1500_.jpg"
        ],
        "url": "https://www.amazon.in/dp/B0D782C2LK"
    },
    {
        "title": "💻 ASUS Vivobook 15 Intel Core i3 12th Gen",
        "orig_price": "₹49,990",
        "deal_price": "₹32,990",
        "discount": "34% OFF ⚡ (Heavy Drop)",
        "specs": "• 8GB RAM / 512GB SSD\n• Thin & Light Design\n• Windows 11 + MS Office",
        "images": [
            "https://m.media-amazon.com/images/I/71S8U9VzLTL._SL1500_.jpg",
            "https://m.media-amazon.com/images/I/71x317mKzmL._SL1500_.jpg",
            "https://m.media-amazon.com/images/I/71L-fPzN1YL._SL1500_.jpg"
        ],
        "url": "https://www.amazon.in/dp/B0C3R82KWY"
    },
    {
        "title": "🎧 boAt Airdopes 141 TWS Earbuds",
        "orig_price": "₹4,490",
        "deal_price": "₹999",
        "discount": "78% OFF 💥 (Loot Deal)",
        "specs": "• 42 Hours Playtime\n• Low Latency Gaming Mode\n• IPX4 Water Resistance",
        "images": [
            "https://m.media-amazon.com/images/I/61KNJ34s9OL._SL1500_.jpg",
            "https://m.media-amazon.com/images/I/61i2+b6P-XL._SL1500_.jpg",
            "https://m.media-amazon.com/images/I/61M-f13qf0L._SL1500_.jpg"
        ],
        "url": "https://www.amazon.in/dp/B09N3Z3Y89"
    }
]

ptb_app = Application.builder().token(BOT_TOKEN).build()

# ================= MULTI-PHOTO DEAL BROADCASTER =================
async def send_multi_image_deal():
    deal = random.choice(HOT_DEALS)
    
    caption = (
        f"🔥 **{deal['title']}**\n\n"
        f"❌ M.R.P.: ~~{deal['orig_price']}~~\n"
        f"💰 **Deal Price: {deal['deal_price']}**\n"
        f"⚡ **Discount:** {deal['discount']}\n\n"
        f"📌 **Key Features:**\n{deal['specs']}\n\n"
        f"📢 Daily Price Updates: {CHANNEL_ID}"
    )

    media_group = []
    for idx, img_url in enumerate(deal["images"]):
        if idx == 0:
            media_group.append(InputMediaPhoto(media=img_url, caption=caption, parse_mode="Markdown"))
        else:
            media_group.append(InputMediaPhoto(media=img_url))

    keyboard = [[InlineKeyboardButton("🛒 Direct Buy Product Here", url=deal["url"])]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 1. CHANNEL BROADCAST
    try:
        await ptb_app.bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)
        await ptb_app.bot.send_message(
            chat_id=CHANNEL_ID, 
            text=f"👉 **Click below to buy {deal['title']}:**", 
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        logging.info("SUCCESS: Posted to Channel!")
    except Exception as e:
        logging.error(f"Channel Error: {e}")

    # 2. USER BROADCAST
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()

        for user in users:
            try:
                await ptb_app.bot.send_media_group(chat_id=user[0], media=media_group)
                await ptb_app.bot.send_message(
                    chat_id=user[0], 
                    text=f"👉 **Click below to buy {deal['title']}:**", 
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                await asyncio.sleep(0.1)
            except Exception as user_err:
                logging.error(f"User {user[0]} Send Error: {user_err}")
    except Exception as db_err:
        logging.error(f"User DB Error: {db_err}")

# ================= TELEGRAM HANDLERS =================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Start DB Error: {e}")

    welcome_text = (
        "🔥 **Welcome to Daily Price Update!**\n\n"
        "Ab aapko sabse sasti aur dhamaka deals **Personal Chat + Channel** dono jagah milengi!\n\n"
        "📢 **Humara Main Deals Channel zaroor join karein:**\n"
        f"👉 [Click Here to Join Channel]({CHANNEL_LINK})\n\n"
        "⚡ *Naye offers automatic update hote rahenge!*"
    )

    keyboard = [[InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)]]
    await update.message.reply_text(
        welcome_text, 
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

async def post_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_multi_image_deal()
    await update.message.reply_text("✅ Instant Deal Post kar di gayi hai!")

ptb_app.add_handler(CommandHandler("start", start_command))
ptb_app.add_handler(CommandHandler("postdeal", post_now_command))

# ================= FLASK ROUTES =================
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def respond():
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, ptb_app.bot)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ptb_app.process_update(update))
    loop.close()
    return "ok", 200

# Continuous Auto-Posting Trigger Route (CRON-JOB ROUTE)
@app.route("/cron-auto-post")
def auto_post_cron():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(send_multi_image_deal())
    loop.close()
    return "Deal Triggered Successfully!", 200

@app.route("/")
def index():
    return "Daily Deals Bot Active!", 200

loop = asyncio.get_event_loop()
loop.run_until_complete(ptb_app.initialize())
