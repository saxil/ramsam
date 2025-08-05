# bot.py
# Final, clean version of the Gemini-powered Telegram Bot

import os
import logging
import asyncio
import google.generativeai as genai

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# --- 1. CONFIGURATION & SETUP ---

# Set up detailed logging to see what the bot is doing
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Get API keys directly from the hosting environment (e.g., Render)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Security Check: Ensure keys are present before starting
if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    logger.critical("FATAL ERROR: TELEGRAM_TOKEN or GEMINI_API_KEY is not set.")
    exit()

# Configure the Google Gemini API
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.critical(f"FATAL ERROR: Failed to configure Gemini API: {e}")
    exit()


# --- 2. CORE AI FUNCTION ---

async def generate_gemini_response(prompt: str) -> str:
    """Sends a prompt to the Gemini API and returns the text response."""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error communicating with Gemini API: {e}")
        return "Sorry, I'm having trouble connecting to my brain right now. Please try again later."


# --- 3. TELEGRAM COMMAND HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the /start command is issued."""
    user_name = update.message.from_user.first_name
    welcome_message = (
        f"Hello, {user_name}! I am your AI assistant.\n\n"
        "Here are the commands you can use:\n"
        "• `/code <your code>` - Formats your text as a code block.\n"
        "• `/mail <Subject>\n<Body>` - Formats your text as an email.\n\n"
        "You can also chat with me normally, or mention me in a group!"
    )
    await update.message.reply_text(welcome_message)


async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Formats the user's provided text into a Markdown code block."""
    if not context.args:
        await update.message.reply_text("Usage: /code <your code snippet>")
        return
    
    user_code = " ".join(context.args)
    # Using MarkdownV2 for formatting.
    formatted_code = f"```\n{user_code}\n```"
    
    try:
        await update.message.reply_text(
            f"Here is your formatted code:\n{formatted_code}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception:
        # Fallback for cases where Markdown parsing fails due to special characters
        await update.message.reply_text(f"Here is your code:\n\n{user_code}")


async def mail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Formats user text into a simple email template."""
    if not context.args:
        await update.message.reply_text("Usage: /mail <Subject Line>\n<Body of the email...>")
        return

    full_text = " ".join(context.args)
    try:
        subject, body = full_text.split('\n', 1)
    except ValueError:
        subject = full_text
        body = "[No body provided]"

    user_name = update.message.from_user.first_name
    email_template = (
        f"*Subject:* {subject}\n\n"
        f"*Dear Team,*\n\n"
        f"{body}\n\n"
        f"*Best regards,*\n{user_name}"
    )
    
    await update.message.reply_text(
        f"Here is your email draft:\n---\n{email_template}",
        parse_mode=ParseMode.MARKDOWN_V2
    )


# --- 4. GENERAL MESSAGE HANDLER ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all non-command text messages and gets a response from Gemini."""
    message_text = update.message.text
    chat_id = update.effective_chat.id

    # Show a "typing..." status to the user
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    
    # Get the AI's response
    ai_response = await generate_gemini_response(message_text)
    
    # Reply to the user's message, keeping the conversation threaded
    await update.message.reply_text(ai_response)


# --- 5. MAIN BOT EXECUTION ---

def main() -> None:
    """Initializes and runs the Telegram bot."""
    logger.info("Bot is starting...")

    # Create the bot application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Register all the command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("mail", mail_command))
    
    # Register the general message handler (must be last)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot
    logger.info("Bot is now polling for messages.")
    application.run_polling()


if __name__ == "__main__":
    main()
