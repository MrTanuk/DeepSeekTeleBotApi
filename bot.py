import os
import sys
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import Flask, request
import telebot
import api_llm
import api_video

# ========== Initial configuration ==========
app = Flask(__name__)

# ========== Bot config ==========
load_dotenv()
# In a futere, with DB to respond all the answer made by the bot
response_history = {}

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_NAME = os.getenv("BOT_NAME")

PROVIDER = os.getenv("PROVIDER")
API_TOKEN = os.getenv("API_TOKEN")
LLM_MODEL = os.getenv("LLM_MODEL")

MAX_OUTPUT_TOKENS = os.getenv("MAX_OUTPUT_TOKENS")
SYSTEM_MESSAGE = os.getenv("SYSTEM_MESSAGE")

if PROVIDER == "google":
    API_URL = f"{os.getenv('API_URL')}/{str(LLM_MODEL)}:generateContent?key={str(API_TOKEN)}"
else:
    API_URL = os.getenv("API_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(str(BOT_TOKEN))
bot_user_id = bot.get_me().id

def is_valid_command(message):
    """This is for differentiate the commands that has the same names of others bots in the same group, so in group is used complete command, and private can be both"""
    command = telebot.util.extract_command(message.text)
    user_command = message.text.partition(' ')[0].replace('/', '')
    complete_command = f'{command}@{BOT_NAME}'

    # Use complete command only in groups
    if user_command == complete_command and message.chat.type in ['groups', 'supergroup']:
        return True
    # Use either complete command or command in private
    elif user_command in (command, complete_command) and message.chat.type == 'private':
        return True
    else:
        return False

def extract_question(message):
    """Separate the command of the bot and the message made by the user neither private or group"""
    #Parse message from private or group
    if message.startswith('/'):
        question = telebot.util.extract_arguments(message)
    #Only in private
    else:
        question = message.strip()
    
    return question

def use_get_api_llm(message, user_text, is_group=False, is_reply=False):
    try:
        # Handle group replies without proper command
        if is_group and is_reply and (not message.text.startswith('/ask') and (f'/ask@{BOT_NAME}' in message.text or not f'@{BOT_NAME}' in message.text)):
            return None
        
        bot.send_chat_action(message.chat.id, "typing")

        user_key = (message.chat.id, message.from_user.id)
        current_time = datetime.now(timezone.utc)
        # Check if history exists and needs reset
        if user_key in response_history:
            history_data = response_history[user_key]
            
            # Reset history if last interaction was over 1 hour ago
            if current_time - history_data['last_active'] > timedelta(hours=1):
                response_history[user_key] = {
                    'conversation': [{"role": "system", "content": SYSTEM_MESSAGE}],
                    'last_active': current_time
                }
                bot.send_message(message.chat.id, "🕒 Chat history reset due to 1 hour of inactivity")

        # Initialize new user history if needed
        if user_key not in response_history:
            response_history[user_key] = {
                'conversation': [{"role": "system", "content": SYSTEM_MESSAGE}],
                'last_active': current_time
            }

        # Update last activity timestamp
        response_history[user_key]['last_active'] = current_time

        # Add new user message to history
        response_history[user_key]['conversation'].append({"role": "user", "content": user_text})

        # Maintain conversation history limit
        MAX_HISTORY = 25
        response_history[user_key]['conversation'] = response_history[user_key]['conversation'][-MAX_HISTORY:]

        # Generate AI response using current conversation context
        ai_response = api_llm.get_api_llm(
            response_history[user_key]['conversation'],
            API_TOKEN,
            API_URL,
            LLM_MODEL,
            PROVIDER,
            MAX_OUTPUT_TOKENS
        )

        # Send response and update history
        bot.reply_to(message, ai_response, parse_mode="markdown")
        response_history[user_key]['conversation'].append({"role": "assistant", "content": ai_response})

    except KeyError as e:
        bot.reply_to(message, "Configuration error, try again.")
    except ConnectionError as e:
        bot.reply_to(message, str(e))
    except telebot.apihelper.ApiTelegramException as e:
        if "Can't find end of the entity starting" in str(e):
            return bot.reply_to(message, ai_response)
        raise
    except Exception as e:
        bot.reply_to(message, f"Unexpected error, Try again.")

def setup_bot_handlers():
    # Config commands
    bot.set_my_commands([
        telebot.types.BotCommand("/start", "Enjoy the bot"),
        telebot.types.BotCommand("/help", "Show all commands"),
        telebot.types.BotCommand("/ask", "Ask something"),
        telebot.types.BotCommand("/new", "Clear the historial"),
        telebot.types.BotCommand("/dl", "Download videos from Facebook, Instagram and TikTok")
    ])

    # Handler to /start
    @bot.message_handler(commands=["start", f"start@{BOT_NAME}"], chat_types=["private", "group", "supergroup"])
    def send_start(message):
        if not is_valid_command(message):
            return None

        bot.reply_to(message, "Welcome to Mario Kart... ♪♪")

    # Handler to /help
    @bot.message_handler(commands=["help", f"help@{BOT_NAME}"], chat_types=["private", "group", "supergroup"])
    def send_help(message):
        if not is_valid_command(message):
            return None

        help_text = (
            "🤖 Commands available: \n\n"
            "/start\n"
            "/help - Show help\n"
            "/ask [questions] - init the conversation. Optional in private\n"
            "/dl [url] - Download videos from Facebook, Instagram and TikTok\n\n"
            "In groups, the commands must have the name bot. For example:\n"
            f'/ask@{BOT_NAME}'
        )
        bot.reply_to(message, help_text)
    
    # Handler to /dl (Download video and send to the user)
    @bot.message_handler(commands=["dl", f"dl@{BOT_NAME}"], chat_types=["private", "group", "supergroup"], content_types=["text"])
    def send_video(message):
        if not is_valid_command(message):
            return None

        try:
            # We get a a list of each word written by the user.
            text = extract_question(message.text)
            # The first word should be the url
            url = text.split()[0].strip()

            bot.send_chat_action(message.chat.id, 'upload_video')

            video = api_video.download_video(url)
            bot.send_video(
                chat_id=message.chat.id,
                video=video,
                reply_to_message_id=message.message_id,
                supports_streaming=True,
                timeout=120
            )

        except IndexError as e:
            if "Parameter not found" in str(e):
                return bot.reply_to(message, str(e))
            elif "list index out" in str(e):
                return bot.reply_to(message, "You must send a command followed by a URL:\n\n/dl https://www.facebook.com/..")
            bot.reply_to(message, str(e))

        except (ValueError, Exception) as ve:
            bot.reply_to(message, str(ve))

    # Handler to /new (clear history)
    @bot.message_handler(commands=["new", f"new@{BOT_NAME}"], chat_types=["private", "group", "supergroup"])
    def clear_history(message):
        if not is_valid_command(message):
            return None

        key = (message.chat.id, message.from_user.id)

        if key in response_history:
            del response_history[key]
        bot.reply_to(message, "♻️ Conversation reloaded")

    # Handler to /ask in private, group
    @bot.message_handler(commands=["ask", f"ask@{BOT_NAME}"], chat_types=["group", "supergroup"], content_types=["text"])
    @bot.message_handler(chat_types=["private"], content_types=["text"])
    def handle_all_question(message):
        question = extract_question(message.text)
        if not question:
            return bot.reply_to(message, "Use: /ask [your question]")

        if message.chat.type in ["group", "supergroup"]:
            if not is_valid_command(message):
                return None
            use_get_api_llm(message, question, is_group=True)
        else:
            use_get_api_llm(message, question)

    # Handler to reply in private, group
    @bot.message_handler(func=lambda m: m.reply_to_message and m.reply_to_message.from_user.id == bot_user_id, chat_types=["private","group", "supergroup"], content_types=["text"])
    def handle_reply(message):
        is_group = message.chat.type in ["group", "supergroup"]
        use_get_api_llm(message, message.text, is_group=is_group, is_reply=True)

    @bot.message_handler(content_types=['new_chat_members'])
    def handle_new_users(message):
            new_user = message.new_chat_members[-1].first_name
            bot.reply_to(message, f'Welcome, {new_user}! I hope you enjoy this group 🎉.')

def setup_logging():
    formatting = logging.Formatter('%(asctime)s | %(levelname)-8s | %(name)s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    stream_logging = logging.StreamHandler(sys.stdout)
    stream_logging.setFormatter(formatting)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(stream_logging)

    # Show only errors
    logging.getLogger('telebot').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('yt_dlp').setLevel(logging.ERROR)

    if os.environ.get('HOSTING'):
        stream_logging.setLevel(logging.INFO)
    else:
        stream_logging.setLevel(logging.DEBUG)


# handlers config
setup_bot_handlers()
setup_logging()

logger = logging.getLogger(__name__)

# ========== Flask routes ==========
@app.route('/')
def health_check():
    return "🤖 Bot active", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Invalid content type', 403

# ========== Entry point =========

if __name__ == '__main__':
    if os.environ.get('HOSTING') == "production":
        from waitress import serve
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL + '/webhook')

        serve(app, host='0.0.0.0', port=8080)
    else:
        bot.delete_webhook()
        bot.infinity_polling()
        app.run(host='0.0.0.0', port=8080, debug=True)
