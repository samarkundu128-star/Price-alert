import os
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
import asyncio
import requests
from urllib.parse import quote

# ====================== CONFIG ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")                    # Your Telegram Bot Token
CHANNEL_ID = os.getenv("CHANNEL_ID")                  # Main channel/group ID (e.g. -100xxxxxxxxxx)
ADMIN_ID = os.getenv("ADMIN_ID")                      # Your Telegram user ID (to receive notifications)
PROMO_GROUPS = os.getenv("PROMO_GROUPS", "").split(",")  # Comma separated group IDs for promo

# Affiliate tags (replace with your real ones)
AMAZON_TAG = os.getenv("AMAZON_TAG", "yourtag-21")
FLIPKART_AFFILIATE_ID = os.getenv("FLIPKART_AFFILIATE_ID", "")

# How long to remember a product so it is not posted again (in hours)
DEDUP_HOURS = 48

CACHE_FILE = "posted_products.json"
# ====================================================

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None

# ---------- Deduplication ----------
def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

def is_already_posted(product_id: str) -> bool:
    cache = load_cache()
    if product_id in cache:
        posted_time = datetime.fromisoformat(cache[product_id])
        if datetime.now() - posted_time < timedelta(hours=DEDUP_HOURS):
            return True
        else:
            del cache[product_id]
            save_cache(cache)
    return False

def mark_as_posted(product_id: str):
    cache = load_cache()
    cache[product_id] = datetime.now().isoformat()
    # Keep only last 500 entries
    if len(cache) > 500:
        oldest = sorted(cache.items(), key=lambda x: x[1])[:100]
        for k, _ in oldest:
            del cache[k]
    save_cache(cache)

# ---------- Link Builders (Deep links that open product inside app) ----------
def make_amazon_link(asin: str, title: str = "") -> str:
    """Creates a proper Amazon deep link that opens product page in app"""
    # This format works very well on both Android & iOS Amazon app
    return f"https://www.amazon.in/dp/{asin}/?tag={AMAZON_TAG}"

def make_flipkart_link(product_url: str) -> str:
    """Clean Flipkart link"""
    if "flipkart.com" in product_url:
        if FLIPKART_AFFILIATE_ID:
            # Basic affiliate style (you can improve with official API later)
            return product_url
        return product_url
    return product_url

# ---------- Message Templates ----------
def create_deal_message(product: dict) -> str:
    title = product.get("title", "Great Deal")
    price = product.get("price", "N/A")
    mrp = product.get("mrp", "")
    discount = product.get("discount", "")
    platform = product.get("platform", "Amazon")

    msg = f"🔥 *PriceDrop Dost — Deal Alert!*\n\n"
    msg += f"*{title}*\n\n"
    msg += f"💰 *Price:* ₹{price}"
    if mrp:
        msg += f"  ~~₹{mrp}~~"
    if discount:
        msg += f"\n📉 *{discount}% OFF*"
    msg += f"\n🛒 *Platform:* {platform}\n"
    msg += f"\n⚡ Limited time deal — Grab fast!"
    return msg

def create_promo_message() -> str:
    return (
        "🔥 *PriceDrop Dost* is live!\n\n"
        "Get the best Amazon & Flipkart price drops every day.\n"
        "Real deals • Real prices • Instant alerts\n\n"
        "👉 Join now and never miss a drop!"
    )

# ---------- Core Posting Function ----------
async def post_deal(product: dict):
    product_id = product.get("id") or hashlib.md5(product.get("title", "").encode()).hexdigest()

    if is_already_posted(product_id):
        logger.info(f"Skipping duplicate: {product.get('title')}")
        return False

    message = create_deal_message(product)

    # Create deep link button
    link = product.get("link", "")
    if product.get("platform") == "Amazon" and product.get("asin"):
        link = make_amazon_link(product["asin"])
    elif "flipkart" in link.lower():
        link = make_flipkart_link(link)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Buy Now (Open in App)", url=link)]
    ])

    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            parse_mode="Markdown",
            reply_markup=keyboard,
            disable_web_page_preview=False
        )
        mark_as_posted(product_id)
        logger.info(f"Posted: {product.get('title')}")
        return True
    except TelegramError as e:
        logger.error(f"Failed to post: {e}")
        return False

# ---------- Promo to other groups ----------
async def send_promo_to_groups():
    if not PROMO_GROUPS or PROMO_GROUPS == [""]:
        return

    promo = create_promo_message()
    for group_id in PROMO_GROUPS:
        group_id = group_id.strip()
        if not group_id:
            continue
        try:
            await bot.send_message(
                chat_id=group_id,
                text=promo,
                parse_mode="Markdown"
            )
            logger.info(f"Promo sent to {group_id}")
            await asyncio.sleep(1.5)  # avoid flood
        except Exception as e:
            logger.error(f"Promo failed for {group_id}: {e}")

    # Notify admin
    if ADMIN_ID:
        try:
            await bot.send_message(chat_id=ADMIN_ID, text="✅ Promo messages sent to groups.")
        except:
            pass

# ---------- Example Deal Finder (Replace with your real source) ----------
def get_current_deals() -> list:
    """
    This is a placeholder.
    Replace this function with your real deal source
    (Keepa, affiliate API, scraping, etc.)
    """
    # Example structure - put your real deals here
    deals = [
        # {
        #     "id": "B0XXXXXXX",
        #     "title": "Product Name",
        #     "price": "999",
        #     "mrp": "1999",
        #     "discount": "50",
        #     "platform": "Amazon",
        #     "asin": "B0XXXXXXX",
        #     "link": "https://www.amazon.in/dp/B0XXXXXXX"
        # },
    ]
    return deals

# ---------- Flask Routes ----------
@app.route("/")
def home():
    return "PriceDrop Dost is running 🚀", 200

@app.route("/cron-auto-post")
def cron_auto_post():
    """Called by cron-job.org"""
    async def run():
        deals = get_current_deals()
        posted = 0
        for deal in deals:
            success = await post_deal(deal)
            if success:
                posted += 1
            await asyncio.sleep(1)

        # Optional: send promo once a day (you can control frequency)
        # await send_promo_to_groups()

        return posted

    posted_count = asyncio.run(run())
    return jsonify({"status": "ok", "posted": posted_count}), 200

@app.route("/promo")
def trigger_promo():
    """Manual promo trigger"""
    asyncio.run(send_promo_to_groups())
    return jsonify({"status": "promo sent"}), 200

# ---------- Start ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
