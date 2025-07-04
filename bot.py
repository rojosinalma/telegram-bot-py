import os
import json
import logging
from datetime import datetime, UTC
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# Set up noisy logger
NOISY_LOGGER_NAME = "bot"
NOISY_LOG_LEVEL   = logging.WARNING

logger = logging.getLogger(NOISY_LOGGER_NAME)

# Regular logger
logging.basicConfig(
    level=logging.INFO,  # This sets the default for root, we'll set others below
    format='[%(asctime)s] %(levelname)s - %(message)s'
)

# Set noisy/external libraries to LOG_LEVEL
noisy_loggers = [
    "httpx",
    "urllib3",
    "telegram.ext._application",
    "telegram.vendor.ptb_urllib3.urllib3.connectionpool",
    "telegram.bot",
    "apscheduler.executors.default",
    "telegram.ext.dispatcher",
    "telegram.ext.updater",
    "telegram.ext.jobqueue",
    "telegram.request",
    "telegram"
]
for logger_name in noisy_loggers:
    logging.getLogger(logger_name).setLevel(NOISY_LOG_LEVEL)

# Load user_infos from file at startup
USER_FILE = "data/user_infos.json"

os.makedirs("data", exist_ok=True)
user_infos = {}

# Load JSON with structure
def load_user_infos():
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, "r") as f:
                data = json.load(f)
            logger.info(f"Loaded user info from {USER_FILE}")
            if "chats" not in data:
                data = {"chats": {}}  # migrate old files if needed
            return data
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"{USER_FILE} is empty or corrupt. Starting fresh.")

    else:
        logger.info("No existing user info file found. Starting fresh.")
    return {"chats": {}}

user_infos = load_user_infos()

def save_user_infos(data):
    with open(USER_FILE, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("User info saved.")

async def collect_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    c = update.effective_chat

    if u and c:
        chat_id    = str(c.id)
        user_id    = str(u.id)
        chat_title = c.title or c.username or "Private"
        now_iso    = datetime.now(UTC).isoformat()

        if chat_id not in user_infos["chats"]:
            user_infos["chats"][chat_id] = {
                "chat_title": chat_title,
                "users": {}
            }
        chat_data = user_infos["chats"][chat_id]
        already = user_id in chat_data["users"]

        if not already:
            logger.info(f"Registered user {user_id} in chat {chat_id}: username={u.username}, first_name={u.first_name}")
        chat_data["chat_title"] = chat_title  # update if group title changed
        chat_data["users"][user_id] = {
            "username": u.username,
            "first_name": u.first_name or "",
            "joined_at": chat_data["users"].get(user_id, {}).get("joined_at", now_iso)
        }
        if not already:
            save_user_infos(user_infos)

async def keyword_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await collect_user(update, context)
        msg_text = update.message.text.lower()
        chat_id  = str(update.effective_chat.id)

        if "@everyone" in msg_text:
            logger.info(f"@everyone detected in chat {chat_id} by user_id={update.effective_user.id}")
            chat_data = user_infos["chats"].get(chat_id, {})
            chat_users = chat_data.get("users", {})

            if not chat_users:
                await update.message.send_message("No users to mention yet!")
                logger.info(f"No users to ping in chat {chat_id}.")
                return
            mentions = []

            caller_id = str(update.effective_user.id)
            mentions = []
            for user_id, info in chat_users.items():
                if user_id == caller_id:
                    continue  # Skip the person who triggered the keyword
                if info.get("username"):
                    mention = f"@{info['username']}"
                elif info.get("first_name"):
                    mention = f"[{info['first_name']}](tg://user?id={user_id})"
                else:
                    mention = f"[{user_id}](tg://user?id={user_id})"
                mentions.append(mention)

            text = "Pinging everyone:\n" + " ".join(mentions)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                parse_mode="Markdown"
            )

            logger.info(f"Pinged {len(mentions)} users in chat {chat_id}")
    except Exception as e:
        logger.exception("Error in keyword_trigger handler")

if __name__ == "__main__":
    if not BOT_TOKEN:
        logging.critical("TELEGRAM_BOT_TOKEN environment variable not set.")
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")

    logging.info("Starting Telegram bot...")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), keyword_trigger))
    app.run_polling()

