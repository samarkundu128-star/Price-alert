import os
import json
import hashlib
import logging
import asyncio
from datetime import datetime, timedelta
from flask import Flask, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

# ====================== CONFIG ======================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PROMO_GROUPS = [g.strip() for g in os.getenv("PROMO_GROUPS", "").split(",") if g.strip()]

AMAZON_TAG = "pricedropdost-21"
CHANNEL_USERNAME = "daily_price_alert"
CHANNEL_LINK = f"https://t.me/{CHANNEL_USERNAME}"

DEDUP_HOURS = 36
MIN_DISCOUNT = 20
CACHE_FILE = "posted_cache.json"
# ====================================================

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------- Cache (Duplicate Prevention) ----------
def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

def already_posted(pid: str) -> bool:
    cache = load_cache()
    if pid in cache:
        t = datetime.fromisoformat(cache[pid])
        if datetime.now() - t < timedelta(hours=DEDUP_HOURS):
            return True
        del cache[pid]
        save_cache(cache)
    return False

def mark_posted(pid: str):
    cache = load_cache()
    cache[pid] = datetime.now().isoformat()
    if len(cache) > 500:
        items = sorted(cache.items(), key=lambda x: x[1])[:150]
        for k, _ in items:
            del cache[k]
    save_cache(cache)

# ---------- Link Makers ----------
def make_amazon_link(asin: str) -> str:
    return f"https://www.amazon.in/dp/{asin}/?tag={AMAZON_TAG}"

# ---------- Caption Maker ----------
def make_caption(p: dict) -> str:
    title = p.get("title", "Great Deal")[:90]
    price = p.get("price", "N/A")
    mrp = p.get("mrp")
    discount = p.get("discount")
    platform = p.get("platform", "Amazon")

    text = f"🔥 *Daily Price Updates*\n\n"
    text += f"*{title}*\n\n"
    text += f"💰 *Price:* ₹{price}"
    if mrp:
        text += f"  ~~₹{mrp}~~"
    if discount:
        text += f"\n📉 *{discount}% OFF*"
    text += f"\n🛒 {platform}\n"
    text += f"\n⚡ Limited time deal!"
    return text

# ---------- Post Deal (with Image support) ----------
async def post_deal(bot: Bot, product: dict):
    pid = product.get("id") or hashlib.md5(
        f"{product.get('title','')}{product.get('price','')}".encode()
    ).hexdigest()

    if already_posted(pid):
        logger.info(f"Skipped duplicate: {product.get('title')}")
        return False

    discount = product.get("discount")
    if discount and str(discount).isdigit() and int(discount) < MIN_DISCOUNT:
        return False

    caption = make_caption(product)
    link = product.get("link", "")
    if product.get("asin"):
        link = make_amazon_link(product["asin"])

    buttons = [
        [InlineKeyboardButton("🛒 Buy Now (Open in App)", url=link)],
        [
            InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK),
            InlineKeyboardButton("📤 Share", switch_inline_query=product.get("title", "Deal"))
        ]
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    try:
        image = product.get("image")
        if image:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption,
                parse_mode="Markdown",
                reply_markup=keyboard,
                disable_web_page_preview=False
            )
        mark_posted(pid)
        logger.info(f"Posted → {product.get('title')}")
        return True
    except Exception as e:
        logger.error(f"Post error: {e}")
        if ADMIN_ID:
            try:
                await bot.send_message(ADMIN_ID, f"❌ Error:\n{e}")
            except:
                pass
        return False

# ---------- Promo ----------
async def send_promos(bot: Bot):
    if not PROMO_GROUPS:
        return
    text = (
        f"🔥 *Daily Price Updates*\n\n"
        f"Roz ke best Amazon & Flipkart price drops yahan milte hain.\n"
        f"Real deals • Fast alerts • Direct app links\n\n"
        f"👉 Join now: {CHANNEL_LINK}"
    )
    for g in PROMO_GROUPS:
        try:
            await bot.send_message(g, text, parse_mode="Markdown")
            await asyncio.sleep(1.5)
        except Exception as e:
            logger.error(f"Promo fail {g}: {e}")
    if ADMIN_ID:
        await bot.send_message(ADMIN_ID, "✅ Promos sent")

# ---------- Deal Source (Amazon + Flipkart structure) ----------
def get_current_deals() -> list:
    """
    Yahan real deals aayenge.
    Abhi example structure diya hai.
    Aap isme real data daal sakte ho ya baad mein scraper/API laga sakte ho.
    """
    deals = [
        # Example Amazon deal (is format mein data daalo)
        # {
        #     "id": "B0XXXXXXX",
        #     "title": "Product Name",
        #     "price": "999",
        #     "mrp": "1999",
        #     "discount": "50",
        #     "platform": "Amazon",
        #     "asin": "B0XXXXXXX",
        #     "link": "https://www.amazon.in/dp/B0XXXXXXX",
        #     "image": "https://m.media-amazon.com/images/I/xxxxx.jpg"
        # },
        # Example Flipkart deal
        # {
        #     "id": "FLIP123",
        #     "title": "Product Name",
        #     "price": "799",
        #     "mrp": "1599",
        #     "discount": "50",
        #     "platform": "Flipkart",
        #     "link": "https://www.flipkart.com/....",
        #     "image": "https://rukminim2.flixcart.com/image/...."
        # },
    ]
    return deals

# ---------- Bot Commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    text = (
        f"👋 Hello {name}!\n\n"
        f"Welcome to *Daily Price Updates*\n\n"
        f"Main aapko Amazon aur Flipkart ke best price drops deta hoon.\n\n"
        f"🔹 /track <link> - Kisi bhi product ko track karo\n"
        f"🔹 /help - Help menu"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("🔥 See Latest Deals", url=CHANNEL_LINK)]
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*Commands:*\n\n"
        "/start - Start bot\n"
        "/track <product link> - Product track karo\n"
        "/help - Help",
        parse_mode="Markdown"
    )

async def track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage:\n`/track https://amazon.in/...`", parse_mode="Markdown")
        return
    link = context.args[0]
    await update.message.reply_text(
        f"✅ Product tracking mein add ho gaya!\n\n`{link}`\n\n"
        f"Price drop hone par aapko alert mil jayega.",
        parse_mode="Markdown"
    )

# ---------- Flask Routes ----------
@app.route("/")
def home():
    return "Daily Price Updates Bot is Live 🚀", 200

@app.route("/cron-auto-post")
def cron_auto_post():
    async def job():
        app_bot = Application.builder().token(BOT_TOKEN).build()
        bot = app_bot.bot
        deals = get_current_deals()
        count = 0
        for d in deals:
            if await post_deal(bot, d):
                count += 1
            await asyncio.sleep(1.2)
        return count
    posted = asyncio.run(job())
    return jsonify({"status": "ok", "posted": posted})

@app.route("/promo")
def promo_route():
    async def job():
        app_bot = Application.builder().token(BOT_TOKEN).build()
        await send_promos(app_bot.bot)
    asyncio.run(job())
    return jsonify({"status": "promo sent"})

# ---------- For local run ----------
if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("track", track))
    application.run_polling()
