# bot.py
# Final version with a Flask web server to keep the Render service alive.

import os
import logging
import threading
from flask import Flask

import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# --- 1. CONFIGURATION & SETUP ---

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Render provides the port to listen on in this env var
PORT = int(os.environ.get('PORT', 8443))

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    logger.critical("FATAL ERROR: TELEGRAM_TOKEN or GEMINI_API_KEY is not set.")
    exit()

try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.critical(f"FATAL ERROR: Failed to configure Gemini API: {e}")
    exit()

# --- 2. FLASK WEB SERVER (for Render Health Checks) ---

# Create a Flask app
app = Flask(__name__)

@app.route('/')
def health_check():
    """This route will be checked by Render to confirm the service is live."""
    return "OK", 200

def run_flask():
    """Runs the Flask app in a separate thread."""
    # Listens on 0.0.0.0 to be accessible by Render
    # Uses the PORT environment variable provided by Render
    app.run(host='0.0.0.0', port=PORT)


# --- 3. TELEGRAM BOT LOGIC ---
# All your bot functions (generate_gemini_response, start_command, etc.) remain the same.

async def generate_gemini_response(prompt: str) -> str:
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Error communicating with Gemini API: {e}")
        return "Sorry, I'm having trouble connecting to my brain right now."

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    welcome_message = (
        f"Hello, {user_name}! I am your AI assistant.\n\n"
        "• `/code <python code>` - Executes Python code.\n"
        "• `/mail <Subject>\n<Body>` - Formats text as an email."
    )
    await update.message.reply_text(welcome_message)

async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /code <python code snippet to execute>")
        return
    user_code = " ".join(context.args)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    execution_prompt = (
        "You are a Python code execution engine. "
        "Execute the following Python code and return ONLY the standard output (stdout). "
        "If there's an error, return ONLY the error message. Provide no explanation."
        f"\n\nCode:\n```python\n{user_code}\n```"
    )
    output = await generate_gemini_response(execution_prompt)
    await update.message.reply_text(f"Output:\n```\n{output}\n```", parse_mode=ParseMode.MARKDOWN_V2)

async def mail_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /mail <Subject Line>\n<Body...>")
        return
    full_text = " ".join(context.args)
    try:
        subject, body = full_text.split('\n', 1)
    except ValueError:
        subject = full_text
        body = "[No body provided]"
    user_name = update.message.from_user.first_name
    email_template = f"*Subject:* {subject}\n\n*Dear Team,*\n\n{body}\n\n*Best regards,*\n{user_name}"
    await update.message.reply_text(f"Here is the email draft:\n---\n{email_template}", parse_mode=ParseMode.MARKDOWN_V2)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    ai_response = await generate_gemini_response(message_text)
    await update.message.reply_text(ai_response)


# --- 4. MAIN EXECUTION ---

def run_bot():
    """Initializes and runs the Telegram bot."""
    logger.info("Starting Telegram bot...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("mail", mail_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Telegram bot is now polling for messages.")
    application.run_polling()


if __name__ == "__main__":
    # Start the Flask web server in a background thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    # Start the Telegram bot in the main thread
    run_bot()

