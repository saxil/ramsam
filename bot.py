# bot.py
# Final version with email sending functionality.

import os
import logging
import threading
import smtplib
from email.message import EmailMessage
from flask import Flask

import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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

# Security Check for all necessary variables
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

        # Connect to Gmail's SMTP server using SSL
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            smtp.send_message(msg)
        logger.info(f"Email sent successfully to {RECIPIENT_EMAIL}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


# --- 3. TELEGRAM BOT LOGIC ---

# ... (start_command, code_command, generate_gemini_response functions are the same)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.from_user.first_name
    welcome_message = (
        f"Hello, {user_name}! I am your AI assistant.\n\n"
        "• `/code <python code>` - Executes Python code.\n"
        "• `/mail <Subject>\n<Body>` - Drafts an email to send."
    )
    await update.message.reply_text(welcome_message)

async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This function remains unchanged
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
    """Drafts an email and shows a 'Send' button."""
    full_command_text = update.message.text
    command_name = update.message.entities[0]
    content = full_command_text[command_name.offset + command_name.length:].strip()

    if not content:
        await update.message.reply_text("Usage: /mail <Subject Line>\n<Body of the email...>")
        return

    try:
        subject, body = content.split('\n', 1)
    except ValueError:
        subject = content
        body = "[No body provided]"

    # Store the draft in the user's context to be used by the button handler later
    context.user_data['email_draft'] = {'subject': subject, 'body': body}

    user_name = update.message.from_user.first_name
    email_template = f"*Subject:* {subject}\n\n*Dear Team,*\n\n{body}\n\n*Best regards,*\n{user_name}"
    
    # Create the inline button
    keyboard = [
        [InlineKeyboardButton("Send Email", callback_data='send_email_confirm')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Here is the email draft to be sent to `{RECIPIENT_EMAIL}`:\n---\n{email_template}", 
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles clicks on the inline buttons."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button press

    if query.data == 'send_email_confirm':
        # Retrieve the draft from user context
        draft = context.user_data.get('email_draft')
        if not draft:
            await query.edit_message_text(text="Sorry, I couldn't find the email draft to send.")
            return

        # Send the email
        success = send_email(draft['subject'], draft['body'])

        if success:
            await query.edit_message_text(text="✅ Email sent successfully!")
        else:
            await query.edit_message_text(text="❌ Failed to send email. Please check the server logs.")
        
        # Clear the draft
        del context.user_data['email_draft']

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This function remains unchanged
    message_text = update.message.text
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    ai_response = await generate_gemini_response(message_text)
    await update.message.reply_text(ai_response)


# --- 4. MAIN EXECUTION ---

def run_bot():
    """Initializes and runs the Telegram bot."""
    # We need to enable persistence to share data between handlers
    persistence = ExtBotPersistence(data_path='./bot_persistence')
    application = Application.builder().token(TELEGRAM_TOKEN).persistence(persistence).build()
    
    # Register all handlers, including the new button handler
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("mail", mail_command))
    application.add_handler(CallbackQueryHandler(button_handler)) # New handler for buttons
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Telegram bot is now polling for messages.")
    application.run_polling()


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    run_bot()
