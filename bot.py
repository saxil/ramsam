
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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    logger.critical("FATAL ERROR: TELEGRAM_TOKEN or GEMINI_API_KEY is not set.")
    exit()

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
        "• `/code <python code>` - Executes Python code and shows the output.\n"
        "• `/mail <Subject>\n<Body>` - Formats your text as an email.\n\n"
        "You can also chat with me normally, or mention me in a group!"
    )
    # The .reply_text() function automatically replies to the user's command.
    await update.message.reply_text(welcome_message)


async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simulates Python code execution by sending it to the Gemini AI."""
    if not context.args:
        await update.message.reply_text("Usage: /code <python code snippet to execute>")
        return
    
    user_code = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    execution_prompt = (
        "You are a Python code execution engine. "
        "Execute the following Python code and return ONLY the standard output (stdout). "
        "If the code produces an error, return ONLY the error message. "
        "Do not provide any explanation, commentary, or formatting. "
        "Just the raw output.\n\n"
        f"Code:\n```python\n{user_code}\n```"
    )
    
    output = await generate_gemini_response(execution_prompt)
    
    # This also replies directly to the user's /code message.
    await update.message.reply_text(
        f"Output:\n```\n{output}\n```",
        parse_mode=ParseMode.MARKDOWN_V2
    )


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
    
    # This also replies directly to the user's /mail message.
    await update.message.reply_text(
        f"Here is your email draft:\n---\n{email_template}",
        parse_mode=ParseMode.MARKDOWN_V2
    )


# --- 4. GENERAL MESSAGE HANDLER ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles all non-command text messages and gets a response from Gemini."""
    message_text = update.message.text
    chat_id = update.effective_chat.id
    
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    
    ai_response = await generate_gemini_response(message_text)
    
    # This line sends the ai_response AS A REPLY to the user's original message.
    await update.message.reply_text(ai_response)


# --- 5. MAIN BOT EXECUTION ---

def main() -> None:
    """Initializes and runs the Telegram bot."""
    logger.info("Bot is starting...")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("mail", mail_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is now polling for messages.")
    application.run_polling()


if __name__ == "__main__":
    main()
