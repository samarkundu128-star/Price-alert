import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CUELINKS_PUBLISHER_ID = os.getenv("CUELINKS_PUBLISHER_ID")
AMAZON_TAG = os.getenv("AMAZON_TAG", "pricedropdost-21")
PUBLIC_GROUP_ID = os.getenv("PUBLIC_GROUP_ID")
WEBSITE_URL = os.getenv("WEBSITE_URL")
AUTOPILOT_MODE = os.getenv("AUTOPILOT_MODE", "False") == "True"
