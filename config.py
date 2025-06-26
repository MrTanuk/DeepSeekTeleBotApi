import os
import sys
import logging
import telebot
from dotenv import load_dotenv
from supabase import Client

# Load environment variables from a .env file at the very beginning.
load_dotenv()

# --- Logging Setup ---
def setup_logging():
    is_production = os.environ.get('HOSTING') == "production"
    log_level = logging.INFO if is_production else logging.DEBUG

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout,
    )
    # Silence overly verbose libraries
    logging.getLogger('telebot').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('yt_dlp').setLevel(logging.ERROR)
    logging.getLogger('postgrest').setLevel(logging.WARNING) # For Supabase client

# --- Environment Variables and Configuration ---

# Bot Credentials
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN is not defined in the environment. The bot cannot start.")

# LLM Configuration
PROVIDER = os.getenv("PROVIDER")
API_TOKEN = os.getenv("API_TOKEN")
LLM_MODEL = os.getenv("LLM_MODEL")
SYSTEM_MESSAGE = os.getenv("SYSTEM_MESSAGE")
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", 700))

# API URL Construction
API_URL = os.getenv("API_URL")
if PROVIDER and PROVIDER.lower() == "google":
    API_URL = f"{API_URL}/{LLM_MODEL}:generateContent?key={API_TOKEN}"

# Webhook for production environment
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# --- Client and Global Object Initialization ---

# Initialize Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if SUPABASE_URL and SUPABASE_KEY:
    supabase = Client(SUPABASE_URL, SUPABASE_KEY)
    logging.info("Supabase client initialized.")
else:
    logging.warning("Supabase credentials not found. Cookie-related functions will be unavailable.")

# Initialize Telegram Bot (singleton instance)
bot = telebot.TeleBot(str(BOT_TOKEN))
BOT_USER_ID = bot.get_me().id
BOT_NAME = bot.get_me().username
logging.info(f"Bot '{BOT_NAME}' (ID: {BOT_USER_ID}) initialized.")
