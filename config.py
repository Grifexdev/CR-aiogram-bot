import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Clash Royale API Token (официальный API)
CR_API_TOKEN = os.getenv("CR_API_TOKEN", "")

# Clash Royale API Base URL
CR_API_BASE_URL = "https://api.clashroyale.com/v1"

# RoyaleAPI Base URL
ROYALEAPI_BASE_URL = "https://royaleapi.com"

# Clan Tag (без #)
CLAN_TAG = os.getenv("CLAN_TAG", "")

# Время напоминаний об атаках (по умолчанию за 2 часа до окончания дня войны)
WAR_REMINDER_HOURS = int(os.getenv("WAR_REMINDER_HOURS", "22"))  # 22:00 по умолчанию

# ID супер-администратора (может добавлять других админов)
SUPER_ADMIN_ID = 1811574692

