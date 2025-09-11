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

# Request Status Constants
REQUEST_STATUS_PENDING = "pending"
REQUEST_STATUS_APPROVED = "approved"
REQUEST_STATUS_DECLINED = "declined"

# Callback Data Constants
CALLBACK_OPTION_PREFIX = "option_"
CALLBACK_BACK = "back"
CALLBACK_COMPLETE = "complete"
CALLBACK_APPROVE_PREFIX = "approve_"
CALLBACK_DECLINE_PREFIX = "decline_"

# HTTP Timeout Configuration
HTTP_CONNECT_TIMEOUT = 60.0
HTTP_READ_TIMEOUT = 120.0
HTTP_WRITE_TIMEOUT = 60.0
HTTP_POOL_TIMEOUT = 30.0

# Statistics Configuration
STATS_RECENT_DAYS = 7

# Validation
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is required")
if not ADMIN_CHAT_ID:
    raise ValueError("ADMIN_CHAT_ID is required")
if not TARGET_GROUP_ID:
    raise ValueError("TARGET_GROUP_ID is required")
