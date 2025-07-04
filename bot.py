import os
import json
import logging
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

if os.path.exists(USER_FILE):
    try:
        with open(USER_FILE, "r") as f:
            user_infos = json.load(f)
        logging.info(f"Loaded {len(user_infos)} users from {USER_FILE}")
    except (json.JSONDecodeError, ValueError):
        logging.warning(f"{USER_FILE} is empty or corrupt. Starting with an empty user list.")
else:
    logging.info("No existing user info file found. Starting fresh.")

def save_user_infos():
    with open(USER_FILE, "w") as f:
        json.dump(user_infos, f)
    logging.info(f"Saved {len(user_infos)} users to {USER_FILE}")

async def collect_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if u:
        uid = str(u.id)
        old = user_infos.get(uid)
        user_infos[uid] = {
            "username": u.username,
            "first_name": u.first_name or ""
        }
        if not old:
            logging.info(
                f"Registered new user: id={u.id}, username={u.username}, first_name={u.first_name}"
            )
            save_user_infos()

async def keyword_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await collect_user(update, context)
        msg_text = update.message.text.lower()
        if "@everyone" in msg_text:
            logging.info(f"@everyone detected in message by user_id={update.effective_user.id}")
            if not user_infos:
                await update.message.reply_text("No users to mention yet!")
                logging.info("Tried to mention but user list is empty.")
                return
            mentions = []
            for user_id, info in user_infos.items():
                if info.get("username"):
                    mention = f"@{info['username']}"
                elif info.get("first_name"):
                    mention = f"[{info['first_name']}](tg://user?id={user_id})"
                else:
                    mention = f"[{user_id}](tg://user?id={user_id})"
                mentions.append(mention)
            text = "Pinging everyone:\n" + " ".join(mentions)
            await update.message.reply_text(
                text,
                parse_mode="Markdown"
            )
            logging.info(
                f"Pinged {len(mentions)} users in response to @everyone by user_id={update.effective_user.id}"
            )
    except Exception as e:
        logging.exception("Error in keyword_trigger handler")

if __name__ == "__main__":
    if not BOT_TOKEN:
        logging.critical("TELEGRAM_BOT_TOKEN environment variable not set.")
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")
    logging.info("Starting Telegram bot...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), keyword_trigger))
    app.run_polling()

