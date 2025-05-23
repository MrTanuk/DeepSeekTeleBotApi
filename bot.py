import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from flask import Flask, request
import telebot
import api_llm
import api_video

# ========== Initial configuration ==========
app = Flask(__name__)
SYSTEM_MESSAGE = "You are a professional telegram bot to help people. Answer briefly"

# ========== Bot config ==========
load_dotenv()
# In a futere, with DB to respond all the answer made by the bot
response_history = {}

PROVIDER = os.getenv("PROVIDER")
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_NAME = os.getenv("BOT_NAME")
API_TOKEN = os.getenv("API_TOKEN")
LLM_MODEL = os.getenv("LLM_MODEL")
if PROVIDER == "google":
    API_URL = f"{os.getenv('API_URL')}/{str(LLM_MODEL)}:generateContent?key={str(API_TOKEN)}"
else:
    API_URL = os.getenv("API_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(str(BOT_TOKEN))
bot_user_id = bot.get_me().id

def is_type_chat_command(message, command_well, type_chat=False):
    """This is for differentiate the commands that has the same names of others bots in the same group, so in group is used complete command, and private can be both"""
    command = message.partition(' ')[0]
    complete_command = f'{command_well}@{BOT_NAME}'
    # Use complete command only in groups
    if command == complete_command and type_chat:
        return True
    # Use either complete command or command in private
    elif command in (command_well, complete_command) and not type_chat:
        return True
    else:
        return False

def extract_question(message, complete_message=True):
    """Separate the command of the bot and the message made by the user neither private or group"""
    #Parse message from private or group
    if message.startswith('/'):
        # Extract command
        command = message.split()[0].strip()
        # Extract question to get all complete message
        if complete_message:
            question = message.replace(command, "", 1).strip()
        # Extract all the text written by the user
        else:
            question = message.split()
    else:
        #Only in private
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
        MAX_HISTORY = 8
        response_history[user_key]['conversation'] = response_history[user_key]['conversation'][-MAX_HISTORY:]

        MAX_OUTPUT_TOKENS = 500

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
        print(e)
        bot.reply_to(message, str(e))
    except telebot.apihelper.ApiTelegramException as e:
        if "Can't find end of the entity starting" in str(e):
            return bot.reply_to(message, ai_response)
        raise
    except Exception as e:
        print("Error on bot.py APi:", e)
        bot.reply_to(message, f"Unexpected error, Try later.")

def setup_bot_handlers():
    # Config commands
    bot.set_my_commands([
        telebot.types.BotCommand("/start", "Enjoy the bot"),
        telebot.types.BotCommand("/help", "Show all commands"),
        telebot.types.BotCommand("/ask", "Ask something"),
        telebot.types.BotCommand("/new", "Clear the historial"),
        telebot.types.BotCommand("/dl", "Download videos from Youtube, Facebook and Instagram")
    ])

    # Handler to /start
    @bot.message_handler(commands=["start", f"start@{BOT_NAME}"], chat_types=["private", "group", "supergroup"])
    def send_start(message):
        if not is_type_chat_command(message.text, "/start"):
            return None

        bot.reply_to(message, "Welcome to Mario Kart... ♪♪")

    # Handler to /help
    @bot.message_handler(commands=["help", f"help@{BOT_NAME}"], chat_types=["private", "group", "supergroup"])
    def send_help(message):
        if not is_type_chat_command(message.text, "/help"):
            return None

        help_text = (
            "🤖 *Commands available:* \n"
            "/start\n"
            "/help - Show help\n"
            "/ask [questions] - init the conversation. Optional in private\n"
            "/dl [url] - Download video from Youtube, Facebook and Instagram"
        )
        bot.reply_to(message, help_text, parse_mode="markdown", reply_markup=markup)
    
    # Handler to /dl (Download video and send to the user)
    @bot.message_handler(commands=["dl", f"dl@{BOT_NAME}"], chat_types=["private", "group", "supergroup"], content_types=["text"])
    def send_video(message):
        if not is_type_chat_command(message.text, "/dl"):
            return None

        try:
            # We get a a list of each word written by the user.
            text = extract_question(message.text, complete_message=False)
            # The first word should be the url
            url = text[1].strip()

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
                return bot.reply_to(message, "You must send a command followed by a URL:\n\n/dl https://www.youtube.com/watch?v=...")
            bot.reply_to(message, str(e))

        except (ValueError, Exception) as ve:
            bot.reply_to(message, str(ve))

    # Handler to /new (clear history)
    @bot.message_handler(commands=["new", f"new@{BOT_NAME}"], chat_types=["private", "group", "supergroup"])
    def clear_history(message):
        if not is_type_chat_command(message.text, "/new"):
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
            if not is_type_chat_command(message.text, "/ask"):
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


# handlers config
setup_bot_handlers()

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
    if os.environ.get('HOSTING'):
        from waitress import serve
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL + '/webhook')

        serve(app, host='0.0.0.0', port=8080)
    else:
        bot.delete_webhook()
        bot.infinity_polling()
        app.run(host='0.0.0.0', port=8080, debug=True)
