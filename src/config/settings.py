import os

from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", 0))
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID", 0))

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///bot_database.db")

# Timezone
TIMEZONE = os.getenv("TIMEZONE", "Asia/Almaty")

# Validation
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is required")
if not ADMIN_CHAT_ID:
    raise ValueError("ADMIN_CHAT_ID is required")
if not TARGET_GROUP_ID:
    raise ValueError("TARGET_GROUP_ID is required")
