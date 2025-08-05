
import os
import logging
import asyncio
from dotenv import load_dotenv

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

# --- Configuration ---
# Load environment variables from .env file
load_dotenv()

# Get your API keys from the environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Set up logging to see errors and bot activity
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Configure the Gemini API
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Failed to configure Gemini API: {e}")
    # Consider exiting if Gemini is essential for your bot's function
    # exit() 

# --- Gemini AI Model Interaction ---
async def generate_response_gemini(prompt: str) -> str:
    """
    Sends a prompt to the Gemini API and returns the generated response.
    This is used for general chat.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating response from Gemini: {e}")
        return "Sorry, I'm having trouble thinking right now. Please try again later."


# --- Telegram Bot Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command. Sends a welcome message."""
    user_name = update.message.from_user.first_name
    welcome_message = (
        f"Hello, {user_name}! I am an AI assistant.\n\n"
        "Here's what I can do:\n"
        "- Chat with me normally.\n"
        "- Use `/code your code here` to format code.\n"
        "- Use `/mail Your Subject\nYour body...` to format an email.\n"
    )
    await update.message.reply_text(welcome_message)


async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /code. Formats the user's text as a code block.
    """
    if not context.args:
        await update.message.reply_text("Please provide some code after the /code command.")
        return
    
    user_code = " ".join(context.args)
    
    # We use MarkdownV2 for formatting. Note: Telegram requires escaping for some characters.
    # For many simple code blocks, this will work fine.
    # A more advanced version would manually escape characters like '.', '-', '(', ')', etc.
    formatted_code = f"```\n{user_code}\n```"
    
    try:
        await update.message.reply_text(
            f"Here is your formatted code:\n{formatted_code}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        logger.error(f"Error sending formatted code: {e}")
        await update.message.reply_text(f"Here is your code:\n\n{user_code}")


async def mail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for /mail. Formats text into a simple email template.
    """
    if not context.args:
        await update.message.reply_text("Usage: /mail Subject Line\nBody of the email...")
        return

    full_text = " ".join(context.args)
    
    parts = full_text.split('\n', 1)
    subject = parts[0]
    body = parts[1] if len(parts) > 1 else "[No body provided]"
    user_name = update.message.from_user.first_name
    
    email_template = (
        f"*Subject:* {subject}\n\n"
        f"*Dear Team,*\n\n"
        f"{body}\n\n"
        f"*Best regards,*\n{user_name}"
    )
    
    await update.message.reply_text(
        f"Here is the email draft:\n\n---\n\n{email_template}",
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler for all regular text messages. It gets a response from Gemini.
    """
    message_text = update.message.text

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action='typing'
    )
    
    ai_response = await generate_response_gemini(message_text)
    
    await update.message.reply_text(ai_response)


# --- Main Bot Execution ---
def main() -> None:
    """Starts the bot and keeps it running."""
    logger.info("Starting bot...")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # --- Add all command handlers here ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("mail", mail_command))
    
    # This handler must be added last. It handles non-command messages.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is polling for updates...")
    application.run_polling()


if __name__ == "__main__":
    main()
