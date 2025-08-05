# bot.py
# Final version with fixes for /mail command and persistence.

import os
import logging
import threading
import smtplib
from email.message import EmailMessage
from flask import Flask

import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, DictPersistence
from telegram.constants import ParseMode

# --- 1. CONFIGURATION & SETUP ---

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Load all environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PORT = int(os.environ.get('PORT', 8443))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.getenv("SENDER_APP_PASSWORD")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

if not all([TELEGRAM_TOKEN, GEMINI_API_KEY, SENDER_EMAIL, SENDER_APP_PASSWORD, RECIPIENT_EMAIL]):
    logger.critical("FATAL ERROR: One or more environment variables are not set.")
    exit()

try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    logger.critical(f"FATAL ERROR: Failed to configure Gemini API: {e}")
    exit()


# --- 2. FLASK WEB SERVER & EMAIL SENDER ---

app = Flask(__name__)

@app.route('/')
def health_check():
    return "OK", 200

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

def send_email(subject, body):
    """Connects to Gmail and sends the email."""
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENT_EMAIL

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            smtp.send_message(msg)
        logger.info(f"Email sent successfully to {RECIPIENT_EMAIL}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


# --- 3. TELEGRAM BOT LOGIC ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    welcome_message = (
        f"Hello, {user_name}! I am your AI assistant.\n\n"
        "• `/code <python code>` - Executes Python code.\n"
        "• `/mail <Subject>\n<Body>` - Drafts an email to send."
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
    """(FIXED) Drafts an email and shows a 'Send' button."""
    
    # This is a much more robust way to get the text after the command
    if not context.args:
        await update.message.reply_text("Usage: /mail <Subject Line>\n<Body of the email...>")
        return
        
    # Re-join the arguments to get the full content string, preserving newlines
    content = " ".join(context.args)

    try:
        subject, body = content.split('\n', 1)
    except ValueError:
        subject = content
        body = "[No body provided]"

    context.user_data['email_draft'] = {'subject': subject, 'body': body}

    user_name = update.message.from_user.first_name
    email_template = f"*Subject:* {subject}\n\n*Dear Team,*\n\n{body}\n\n*Best regards,*\n{user_name}"
    
    keyboard = [[InlineKeyboardButton("Send Email", callback_data='send_email_confirm')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Here is the email draft to be sent to `{RECIPIENT_EMAIL}`:\n---\n{email_template}", 
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=reply_markup
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles clicks on the inline buttons."""
    query = update.callback_query
    await query.answer()

    if query.data == 'send_email_confirm':
        draft = context.user_data.get('email_draft')
        if not draft:
            await query.edit_message_text(text="Sorry, I couldn't find the email draft. Please try again.")
            return

        success = send_email(draft['subject'], draft['body'])

        if success:
            await query.edit_message_text(text="✅ Email sent successfully!")
        else:
            await query.edit_message_text(text="❌ Failed to send email. Please check the server logs.")
        
        if 'email_draft' in context.user_data:
            del context.user_data['email_draft']


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    ai_response = await generate_gemini_response(message_text)
    await update.message.reply_text(ai_response)


# --- 4. MAIN EXECUTION ---

def run_bot():
    """Initializes and runs the Telegram bot."""
    # Use DictPersistence for simple, in-memory storage of user_data
    persistence = DictPersistence()
    application = Application.builder().token(TELEGRAM_TOKEN).persistence(persistence).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("mail", mail_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Telegram bot is now polling for messages.")
    application.run_polling()


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    run_bot()

