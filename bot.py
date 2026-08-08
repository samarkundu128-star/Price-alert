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
CHANNEL_ID = "@daily_price_alert"  # Aapka Channel Username

app = Flask(__name__)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

init_db()

# ================= HIGH DISCOUNT MULTI-IMAGE DEALS DATABASE =================
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
            "https://m.media-amazon.com/images/I/81P8y-d3kYL._SL1500_.jpg",
            "https://m.media-amazon.com/images/I/710e2jI5b2L._SL1500_.jpg"
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
        f"🛒 **Buy Link:** {deal['url']}\n\n"
        f"📢 Daily Price Updates: {CHANNEL_ID}"
    )

    # 3-4 Images Album Prep
    media_group = []
    for idx, img_url in enumerate(deal["images"]):
        if idx == 0:
            # Pehli photo ke sath Caption lagana padta hai
            media_group.append(InputMediaPhoto(media=img_url, caption=caption, parse_mode="Markdown"))
        else:
            media_group.append(InputMediaPhoto(media=img_url))

    # 1. Channel me Post Karein (3-4 Photos Gallery)
    try:
        await ptb_app.bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)
        logging.info("Multi-image deal posted to channel!")
    except Exception as e:
        logging.error(f"Channel Broadcast Error: {e}")

    # 2. Personal Users ko Post Karein
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()

    for user in users:
        try:
            await ptb_app.bot.send_media_group(chat_id=user[0], media=media_group)
            await asyncio.sleep(0.1) # Flood prevention
        except Exception as e:
            logging.error(f"User Broadcast Error: {e}")

# ================= TELEGRAM HANDLERS =================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🔥 **Daily Price Update Bot Active!**\n\n"
        f"Aapko sabse sasti loot deals multiple photos aur full details ke sath yahan milengi.\n\n"
        f"📢 **Channel Join Karein:** {CHANNEL_ID}",
        parse_mode="Markdown"
    )

async def post_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_multi_image_deal()
    await update.message.reply_text("✅ Multi-photo deal Post kar di gayi hai!")

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

# Fast Auto Post Cron Trigger Route
@app.route("/cron-auto-post")
def auto_post_cron():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(send_multi_image_deal())
    loop.close()
    return "Deal Posted with 3-4 Images!", 200

@app.route("/")
def index():
    return "Daily Multi-Image Deals Bot Active!", 200

loop = asyncio.get_event_loop()
loop.run_until_complete(ptb_app.initialize())
    
