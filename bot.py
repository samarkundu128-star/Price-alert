import asyncio
import logging
import os
import random
import requests
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "8827005241:AAG-mAj8EkJmMrSi2KC8FobuucBwbFxJofY")
CHANNEL_ID = "@daily_price_alert"  # Aapka channel handle

app = Flask(__name__)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# Sample Deals Database (Auto-Poster Demo Deals)
SAMPLE_DEALS = [
    {
        "title": "🔥 M35 5G (8GB RAM, 128GB) - Monster Battery Phone!",
        "orig_price": "₹24,999",
        "deal_price": "₹13,999",
        "discount": "44% OFF",
        "image": "https://m.media-amazon.com/images/I/71d7rfSl0wL._SL1500_.jpg",
        "url": "https://www.amazon.in/dp/B0D782C2LK"
    },
    {
        "title": "💻 ASUS Vivobook 15 Intel Core i3 12th Gen Laptop",
        "orig_price": "₹49,990",
        "deal_price": "₹32,990",
        "discount": "34% OFF",
        "image": "https://m.media-amazon.com/images/I/71S8U9VzLTL._SL1500_.jpg",
        "url": "https://www.amazon.in/dp/B0C3R82KWY"
    },
    {
        "title": "🎧 Boat Airdopes 141 Bluetooth TWS Earbuds",
        "orig_price": "₹4,490",
        "deal_price": "₹999",
        "discount": "78% OFF",
        "image": "https://m.media-amazon.com/images/I/61KNJ34s9OL._SL1500_.jpg",
        "url": "https://www.amazon.in/dp/B09N3Z3Y89"
    }
]

ptb_app = Application.builder().token(BOT_TOKEN).build()

# Channel me Deal Post karne ka main function
async def post_deal_to_channel():
    deal = random.choice(SAMPLE_DEALS)
    caption = (
        f"🔥 **{deal['title']}**\n\n"
        f"❌ Original Price: ~~{deal['orig_price']}~~\n"
        f"✅ **Offer Price: {deal['deal_price']}** ({deal['discount']})\n\n"
        f"⚡ *Limited time deal! Jaldi check karo.*\n\n"
        f"📢 Daily Price Updates: {CHANNEL_ID}"
    )
    
    keyboard = [[InlineKeyboardButton("🛒 Buy Now / Check Deal", url=deal["url"])]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await ptb_app.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=deal["image"],
            caption=caption,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        logging.info("Deal posted successfully!")
    except Exception as e:
        logging.error(f"Failed to post deal: {e}")

# Admin test command (/postdeal)
async def post_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await post_deal_to_channel()
    await update.message.reply_text("✅ Deal channel me post kar di gayi hai!")

ptb_app.add_handler(CommandHandler("postdeal", post_now_command))

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def respond():
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, ptb_app.bot)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ptb_app.process_update(update))
    loop.close()
    return "ok", 200

@app.route("/cron-auto-post")
def auto_post_cron():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(post_deal_to_channel())
    loop.close()
    return "Deal Posted!", 200

@app.route("/")
def index():
    return "Daily Auto Deals Bot Active!", 200

loop = asyncio.get_event_loop()
loop.run_until_complete(ptb_app.initialize())
