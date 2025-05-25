# 🤖 Telegram AI & Video Downloader Bot  

A multifunctional Telegram bot integrating conversational AI and social media video downloading capabilities.

## 🌟 Features  

- **AI Assistant**:  
  - Supported providers: OpenAI, Google Gemini, DeepSeek  
  - Context-aware conversation history (last 15 messages)  
  - Auto-reset after 1 hour of inactivity  
- **Video Downloader**:  
  - Supported platforms: Facebook, Instagram, TikTok  
  - Size limit: 45MB  
  - Platform-specific format optimization  
- **Additional Functionality**:  
  - Custom commands system  
  - Group and private chat support  
  - Detailed logging system  
  - New member detection in groups  

## 📋 Requirements  

- Python 3.9+  
- LLM service accounts (OpenAI/Google/DeepSeek)  
- Publicly accessible server for webhooks (optional)  

## 🛠️ Setup  

### 1. Clone Repository  
```bash  
git clone https://github.com/yourusername/telegram-ai-video-bot.git  
cd telegram-ai-video-bot
```

## Dependencies

```bash
pip install -r requirements.txt

```

## Configuration

Create .env file:

```
# Bot Configuration  
BOT_TOKEN="your_telegram_bot_token"  
BOT_NAME="your_bot_username"  

# LLM Configuration  
PROVIDER="google"  # openai|google|deepseek  
API_TOKEN="your_llm_provider_token"  
LLM_MODEL="gemini-pro"  # Model matching your provider  
API_URL="your_provider_api_endpoint"  

# Hosting Configuration  
WEBHOOK_URL="https://yourdomain.com"  # For production only  
HOSTING="production"  # Enable for server deployment  

# Advanced Settings  
MAX_OUTPUT_TOKENS=500
SYSTEM_MESSAGE="You are a helpful AI assistant"  
```

## 🚀 Usage

Available commands

| Command | Description | Example |
|---------|-------------|---------|
|*/start*|Initialize bot|*/start*|
|*/help*|Show help menu|*help*|
|*/ask [question]*|Query the AI|*/ask How to setup SSH keys*|
|*/dl [url]*|Download video|*/dl https://facebook.com/reel/...*|
|*/new*|Reset conversation|*/new*|

### Usage Guidelines

- Private Chats: Use commands directly
- Group Chats: Append @bot_username to commands

Example: `/ask@your_bot What's the weather foecast?`

### Key Limits

  - Max video size: 45MB
  - Conversation history: 20 most recent messages
  - Inactivity reset: 1 hour

## 🔧 Advanced Configuration

### Environment Variables

|Variable|Purpose|
|--------|-------|
|*BOT_TOKEN*| Telegram bot token from @BotFather|
|*PROVIDER*| LLM service provider|
|*LLM_MODEL*|	Model version (e.g., "gpt-4", "gemini-pro")|
|*MAX_OUTPUT_TOKENS*|	Response length control (50-4096)|
|*SYSTEM_MESSAGE*|	Defines AI personality/behavior|

### Deployment

#### Local Development:

```bash
python bot.py  
```

#### Production Server:

```bash
export HOSTING=production && python bot.py
```

## Dependencies

```
Flask==3.0.0
pyTelegramBotAPI==4.26.0
python-dotenv==1.0.0
requests==2.32.3
waitress==3.0.0
yt-dlp==2025.3.31
```
