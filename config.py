import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
REQUIRED_CHANNELS = [int(ch.strip()) for ch in os.getenv("REQUIRED_CHANNELS", "").split(",") if ch.strip()]
