# bot.py
# Secure version with TEMPORARY debugging lines

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

# --- Configuration ---
# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# --- TEMPORARY DEBUGGING ---
# We will check the environment variables right at the start.
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

logger.info("--- STARTING DEBUG CHECK ---")
logger.info(f"Is TELEGRAM_TOKEN found? {TELEGRAM_TOKEN is not None}")
logger.info(f"Is GEMINI_API_KEY found? {GEMINI_API_KEY is not None}")

# Let's check the first 5 characters to confirm they are loaded.
if TELEGRAM_TOKEN:
    logger.info(f"Telegram Token starts with: {TELEGRAM_TOKEN[:5]}")
else:
    logger.warning("Telegram Token is MISSING.")
    
if GEMINI_API_KEY:
    logger.info(f"Gemini Key starts with: {GEMINI_API_KEY[:5]}")
else:
    logger.warning("Gemini API Key is MISSING.")
logger.info("--- FINISHED DEBUG CHECK ---")
# --- END OF DEBUGGING ---


# --- Security Check ---
if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    logger.critical("CRITICAL ERROR: API keys not set. Exiting.")
    exit()

# Configure the Gemini API
genai.configure(api_key=GEMINI_API_KEY)


# --- All your command and message handlers remain the same ---
# (The rest of your code for start_command, code_command, etc. goes here)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if not context.args:
        await update.message.reply_text("Please provide some code after the /code command.")
        return
    user_code = " ".join(context.args)
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
    
async def generate_response_gemini(prompt: str) -> str:
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error generating response from Gemini: {e}")
        return "Sorry, I'm having trouble thinking right now. Please try again later."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action='typing'
    )
    ai_response = await generate_response_gemini(message_text)
    await update.message.reply_text(ai_response)

# --- Main Bot Execution ---
def main() -> None:
    logger.info("Starting bot...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler
