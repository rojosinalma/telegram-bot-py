import os
import json
import logging
from datetime import datetime, UTC
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, ChatMemberHandler, filters

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
        chat_id = str(c.id)
        user_id = str(u.id)
        chat_title = c.title or c.username or "Private"
        now_iso = datetime.now(UTC).isoformat()

        if chat_id not in user_infos["chats"]:
            user_infos["chats"][chat_id] = {
                "chat_title": chat_title,
                "users": {}
            }
        chat_data = user_infos["chats"][chat_id]
        chat_data["chat_title"] = chat_title

        user_entry = chat_data["users"].get(user_id)
        if not user_entry:
            # New user: register, not subscribed by default!
            chat_data["users"][user_id] = {
                "username": u.username,
                "first_name": u.first_name or "",
                "joined_at": now_iso,
                "subscribed": False
            }
            logger.info(f"Registered new user {user_id} in chat {chat_id}: username={u.username}, first_name={u.first_name}")

            save_user_infos(user_infos)
            # Prompt in the group chat (can also DM, but group is clearer for privacy)
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"Hi {u.first_name or u.username or user_id}! "
                    "If you want to receive @everyone notifications in this group, send '@subscribe'.\n"
                    "You can always opt out later with '@unsubscribe'."
                ),
                # Optionally, reply to their message: reply_to_message_id=update.message.message_id
            )
        # Do NOT auto-subscribe on normal messages

async def keyword_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await collect_user(update, context)
        msg_text = update.message.text.lower()
        chat_id = str(update.effective_chat.id)
        user_id = str(update.effective_user.id)
        chat_data = user_infos["chats"].get(chat_id, {})
        users = chat_data.get("users", {})

        # --- Unsubscribe logic ---
        if "@unsubscribe" in msg_text:
            user_entry = users.get(user_id)
            if user_entry and user_entry.get("subscribed", True):
                user_entry["subscribed"] = False
                save_user_infos(user_infos)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="You have been unsubscribed from @everyone notifications."
                )
                logger.info(f"User {user_id} unsubscribed from chat {chat_id}")
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="You are already unsubscribed from @everyone notifications."
                )
            return

        # --- Subscribe logic ---
        if "@subscribe" in msg_text:
            user_entry = users.get(user_id)
            if not user_entry:
                # User wasn't in list, add as subscribed
                await collect_user(update, context)
                user_entry = users.get(user_id)
            if user_entry.get("subscribed") is not True:
                user_entry["subscribed"] = True
                save_user_infos(user_infos)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="You have been subscribed to @everyone notifications."
                )
                logger.info(f"User {user_id} re-subscribed to chat {chat_id}")
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="You are already subscribed to @everyone notifications."
                )
            return

        # --- @everyone notification ---
        if "@everyone" in msg_text:
            logger.info(f"@everyone detected in chat {chat_id} by user_id={user_id}")
            mentions = []
            for uid, info in users.items():
                if uid == user_id:
                    continue  # Don't mention the trigger user
                if not info.get("subscribed", True):
                    continue  # Only mention subscribed users
                if info.get("username"):
                    mention = f"@{info['username']}"
                elif info.get("first_name"):
                    mention = f"[{info['first_name']}](tg://user?id={uid})"
                else:
                    mention = f"[{uid}](tg://user?id={uid})"
                mentions.append(mention)
            if mentions:
                text = "Pinging everyone:\n" + " ".join(mentions)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    parse_mode="Markdown"
                )
                logger.info(f"Pinged {len(mentions)} users in chat {chat_id}")
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="No one to mention (maybe everyone has unsubscribed)!"
                )
    except Exception as e:
        logger.exception("Error in keyword_trigger handler")

# Remove people leaving the channel
async def handle_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not update.chat_member:
        return
    user = update.chat_member.user
    user_id = str(user.id)
    new_status = update.chat_member.new_chat_member.status

    if new_status in ("left", "kicked"):
        # Remove the user from the JSON if they exist
        chat_data = user_infos["chats"].get(chat_id, {})
        users = chat_data.get("users", {})
        if user_id in users:
            del users[user_id]
            save_user_infos(user_infos)
            logger.info(f"User {user_id} removed from chat {chat_id} due to leaving or being kicked.")

if __name__ == "__main__":
    if not BOT_TOKEN:
        logging.critical("TELEGRAM_BOT_TOKEN environment variable not set.")
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")

    logging.info("Starting Telegram bot...")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), keyword_trigger))
    app.add_handler(ChatMemberHandler(handle_member_update, chat_member_types="ALL"))
    app.run_polling()

