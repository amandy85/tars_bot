import os
import logging
import time
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Rate limiting: 3 requests per minute per user
USER_REQUEST_COUNT = defaultdict(int)
LAST_REQUEST_TIME = defaultdict(float)
REQUEST_LIMIT = 3

# Per-user conversation history + last activity time
CONVERSATIONS = defaultdict(list)
LAST_ACTIVITY = defaultdict(float)

# Inactivity timeout (30 minutes = 1800 sec)
INACTIVITY_TIMEOUT = 1800

# Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message on /start command"""
    welcome_message = (
        "👋 Hello! I'm your Deepseek powered AI assistant.\n\n"
        "📝 I remember context within our chat.\n"
        "🚀 Responses are plain text only.\n"
        "⏱️ Rate limit: 3 requests per minute\n"
        "🧹 Use /reset anytime to clear chat history.\n"
        "⏳ Auto-reset happens if you're inactive for 30 minutes.\n"
    )
    await update.message.reply_text(welcome_message)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear user conversation history manually"""
    user_id = update.effective_user.id
    if user_id in CONVERSATIONS:
        CONVERSATIONS[user_id] = []
        LAST_ACTIVITY[user_id] = time.time()
        await update.message.reply_text("✅ Your conversation history has been reset. Starting fresh!")
    else:
        await update.message.reply_text("ℹ️ No conversation history found to reset.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    current_time = time.time()

    # Auto reset if inactive > 30 minutes
    if current_time - LAST_ACTIVITY[user_id] > INACTIVITY_TIMEOUT and CONVERSATIONS[user_id]:
        CONVERSATIONS[user_id] = []
        await update.message.reply_text("⏳ Your conversation history was automatically reset due to inactivity.")

    # Update last activity time
    LAST_ACTIVITY[user_id] = current_time

    # Rate limiting
    if current_time - LAST_REQUEST_TIME[user_id] < 60:
        if USER_REQUEST_COUNT[user_id] >= REQUEST_LIMIT:
            await update.message.reply_text("⚠️ Rate limit exceeded. Please wait 1 minute.")
            return
    else:
        USER_REQUEST_COUNT[user_id] = 0
        LAST_REQUEST_TIME[user_id] = current_time

    USER_REQUEST_COUNT[user_id] += 1

    # Save user message into conversation history
    CONVERSATIONS[user_id].append({"role": "user", "content": user_message})

    try:
        await update.message.reply_text("Deep thinking in progress..\n🤔 → 🧠 → 🚀")

        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/my-ai-project",
                "X-Title": "Telegram DeepSeek Bot"
            },
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Always reply in plain text."},
                *CONVERSATIONS[user_id]
            ]
        )

        bot_response = response.choices[0].message.content

        # Save assistant response in history
        CONVERSATIONS[user_id].append({"role": "assistant", "content": bot_response})

        # Clean formatting
        clean_response = bot_response.replace("\\boxed{", "").replace("}", "")

        # Split long responses if needed
        max_length = 4096
        for i in range(0, len(clean_response), max_length):
            chunk = clean_response[i:i+max_length]
            await update.message.reply_text(chunk)
            time.sleep(1)

        # Trim history to last 20 exchanges
        if len(CONVERSATIONS[user_id]) > 20:
            CONVERSATIONS[user_id] = CONVERSATIONS[user_id][-20:]

    except Exception as e:
        logger.error(f"Error: {e}")
        error_message = (
            "🚨 Oops! Something went wrong.\n\n"
            "Possible reasons:\n"
            "1. Service temporarily unavailable\n"
            "2. Network issue\n"
            "3. API rate limit reached\n\n"
            "Please try again in a minute."
        )
        await update.message.reply_text(error_message)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
