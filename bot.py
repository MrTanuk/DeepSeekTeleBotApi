import os
import logging
from datetime import datetime, timedelta, timezone
from flask import Flask, request
import telebot
import config
import api_llm
import api_video

# ========== Initial App Setup ==========
app = Flask(__name__)
logger = logging.getLogger(__name__)

# The conversation history is application state, so it stays here.
response_history = {}

# --- Helper Functions ---
def is_valid_command(message):
    """Differentiates commands intended for this bot from others in a group."""
    command = telebot.util.extract_command(message.text)
    if not command:
        return False
    
    user_command = message.text.partition(' ')[0].replace('/', '')
    complete_command = f'{command}@{config.BOT_NAME}'
    is_group = message.chat.type in ['group', 'supergroup']

    if is_group:
        return user_command == complete_command
    else:  # Private chat
        return user_command in (command, complete_command)

def extract_arguments(message):
    """Extracts arguments from a command or the full text if it's not a command."""
    if message.text.startswith('/'):
        return telebot.util.extract_arguments(message.text)
    else:
        return message.text.strip()

# --- Core Logic Functions ---
def use_get_api_llm(message, user_text, is_group=False):
    """Handles the logic of sending a prompt to the LLM and replying to the user."""
    try:
        # In groups, ignore messages that are not explicit commands or replies to the bot
        if is_group and message.reply_to_message is None:
            if not is_valid_command(message):
                return
        
        config.bot.send_chat_action(message.chat.id, "typing")
        user_key = (message.chat.id, message.from_user.id)
        current_time = datetime.now(timezone.utc)
        
        # Check if history exists and needs reset
        history_data = response_history.get(user_key)
        if history_data and (current_time - history_data['last_active'] > timedelta(hours=1)):
            response_history.pop(user_key, None)
            history_data = None # Force re-initialization
            config.bot.send_message(message.chat.id, "🕒 Chat history has been reset due to 1 hour of inactivity.")
        
        # Initialize new user history if needed
        if not history_data:
            response_history[user_key] = {
                'conversation': [{"role": "system", "content": config.SYSTEM_MESSAGE}],
                'last_active': current_time
            }

        # Update last activity timestamp and add new message
        response_history[user_key]['last_active'] = current_time
        response_history[user_key]['conversation'].append({"role": "user", "content": user_text})

        # Maintain conversation history limit
        MAX_HISTORY = 25
        response_history[user_key]['conversation'] = response_history[user_key]['conversation'][-MAX_HISTORY:]

        # Generate AI response using current conversation context
        ai_response = api_llm.get_api_llm(
            response_history[user_key]['conversation'],
            config.API_TOKEN,
            config.API_URL,
            config.LLM_MODEL,
            config.PROVIDER,
            config.MAX_OUTPUT_TOKENS
        )
        
        # Send response and update history
        config.bot.reply_to(message, ai_response, parse_mode="markdown")
        response_history[user_key]['conversation'].append({"role": "assistant", "content": ai_response})

    except (KeyError, ValueError, ConnectionError, RuntimeError) as e:
        config.bot.reply_to(message, str(e))
    except telebot.apihelper.ApiTelegramException as e:
        if "Can't find end of the entity starting" in str(e):
            return config.bot.reply_to(message, ai_response) # Send as plain text if markdown fails
        logger.error("Telegram API Error: %s", e)
    except Exception as e:
        logger.error("Unexpected error in use_get_api_llm: %s", e, exc_info=True)
        config.bot.reply_to(message, "🚨 An unexpected error occurred. Please try again.")

def setup_bot_handlers():
    """Sets up all the message handlers for the bot."""
    # Decorators now use the `config.bot` instance
    config.bot.set_my_commands([
        telebot.types.BotCommand("/start", "Greet the bot"),
        telebot.types.BotCommand("/help", "Show all commands"),
        telebot.types.BotCommand("/ask", "Ask a question"),
        telebot.types.BotCommand("/clear", "Clear conversation history"),
        telebot.types.BotCommand("/dl", "Download a video")
    ])

    @config.bot.message_handler(commands=["start"])
    def send_start(message):
        if not is_valid_command(message): return
        config.bot.reply_to(message, "Welcome to Mario Kart")

    @config.bot.message_handler(commands=["help"])
    def send_help(message):
        if not is_valid_command(message): return
        help_text = (
            "🤖 **Available Commands:**\n\n"
            "/start - Greet the bot\n"
            "/help - Show this help message\n"
            "/ask `[question]` - Start or continue a conversation\n"
            "/clear - Clear the conversation history\n"
            "/dl `[url]` - Download a video from:\n"
            "**Youtube**\n"
            "**Instagram**\n"
            "**Facebook**\n"
            "**TikTok**\n\n"
            f"In groups, commands must be addressed to me (e.g., `/ask@{config.BOT_NAME}`)."
        )
        config.bot.reply_to(message, help_text, parse_mode="markdown")

    @config.bot.message_handler(commands=["dl"])
    def send_video(message):
        if not is_valid_command(message): return
        try:
            args = extract_arguments(message)
            if not args:
                raise IndexError
            url = args.split()[0].strip()
            
            config.bot.send_chat_action(message.chat.id, 'upload_video')
            video = api_video.download_video(url)
            
            config.bot.send_video(
                chat_id=message.chat.id,
                video=video,
                reply_to_message_id=message.message_id,
                supports_streaming=True,
                timeout=120
            )
        except IndexError:
            config.bot.reply_to(message, "Please provide a URL after the command.\nExample: `/dl https://...`")
        except (ValueError, RuntimeError, Exception) as e:
            logger.error(f"Failed to process /dl command: {e}", exc_info=True)
            config.bot.reply_to(message, str(e))

    @config.bot.message_handler(commands=["clear"])
    def clear_history(message):
        if not is_valid_command(message): return
        key = (message.chat.id, message.from_user.id)
        if key in response_history:
            del response_history[key]
        config.bot.reply_to(message, "♻️ Conversation history has been cleared.")

    # Handler for /ask command (works in all chat types)
    @config.bot.message_handler(commands=["ask"])
    def handle_ask(message):
        if not is_valid_command(message): return
        question = extract_arguments(message)
        if not question:
            config.bot.reply_to(message, "Please ask a question after the `/ask` command.")
            return
        is_group = message.chat.type in ["group", "supergroup"]
        use_get_api_llm(message, question, is_group=is_group)

    # Handler for direct messages in private chat (no command needed)
    @config.bot.message_handler(chat_types=["private"], content_types=["text"], func=lambda msg: not msg.text.startswith('/'))
    def handle_private_text(message):
        use_get_api_llm(message, message.text, is_group=False)

    @config.bot.message_handler(content_types=['new_chat_members'])
    def handle_new_users(message):
        for new_user in message.new_chat_members:
            config.bot.send_message(message.chat.id, f'Welcome, {new_user.first_name}! I hope you enjoy this group 🎉.')

# ========== Flask Routes for Webhook ==========
@app.route('/')
def health_check():
    return "🤖 Bot is active.", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        config.bot.process_new_updates([update])
        return '', 200
    return 'Invalid content type', 403

# ========== Application Entry Point ==========
if __name__ == '__main__':
    # Setup logging first
    config.setup_logging()
    
    # Then setup bot handlers
    setup_bot_handlers()
    
    if os.environ.get('HOSTING') == "production":
        from waitress import serve
        logger.info(f"Starting in production mode, setting webhook to {config.WEBHOOK_URL}")
        config.bot.remove_webhook()
        config.bot.set_webhook(url=config.WEBHOOK_URL + '/webhook')
        serve(app, host='0.0.0.0', port=8080)
    else:
        logger.info("Starting in development mode with polling...")
        config.bot.delete_webhook()
        config.bot.infinity_polling()
