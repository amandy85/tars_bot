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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
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

# Initialize client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message on /start command"""
    welcome_message = (
        "👋 Hello! I'm your Deepseek powered AI assistant.\n\n"
        "📝 Reasoning model takes time to think!\n"
        "🚀 I provide responses in plain text format only.\n"
        "⏱️ Rate limit: 3 requests per minute\n"

    )
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_time = time.time()

    # Rate limiting check
    if current_time - LAST_REQUEST_TIME[user_id] < 60:
        if USER_REQUEST_COUNT[user_id] >= REQUEST_LIMIT:
            await update.message.reply_text("⚠️ Rate limit exceeded. Please wait 1 minute.")
            return
    else:
        USER_REQUEST_COUNT[user_id] = 0
        LAST_REQUEST_TIME[user_id] = current_time

    USER_REQUEST_COUNT[user_id] += 1

    try:
        await update.message.reply_text("Deep thinking in progress..\n" "🤔 → 🧠 → 🚀 ")
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://github.com/my-ai-project",
                "X-Title": "Telegram DeepSeek Bot"
            },
            extra_body={},
            model="deepseek/deepseek-chat-v3-0324:free",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Always respond in clear plain text without any special formatting, boxes, or markdown."
                },
                {
                    "role": "user",
                    "content": update.message.text
                }
            ]
        )

        bot_response = response.choices[0].message.content

        # Clean special formatting
        clean_response = bot_response.replace("\\boxed{", "").replace("}", "")

        # Split long responses
        max_length = 4096
        for i in range(0, len(clean_response), max_length):
            chunk = clean_response[i:i+max_length]
            await update.message.reply_text(chunk)
            time.sleep(1)

    except Exception as e:
        logger.error(f"Error: {e}")
        error_message = (
            "🚨 Oops! Something went wrong.\n\n"
            "Possible reasons:\n"
            "1. Service temporarily unavailable\n"
            "2. Network connection issue\n"
            "3. API rate limit reached\n\n"
            "Please try again in a minute."
        )
        await update.message.reply_text(error_message)

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
