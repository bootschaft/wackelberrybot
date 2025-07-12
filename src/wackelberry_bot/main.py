
import os
import json
from telegram import Update, User
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
import asyncio
import logging
import random

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING,  # Set to DEBUG for more detailed logs
)
logger = logging.getLogger(__name__)

UPDATE_INTERVAL = 15  # seconds
# Load the bot token from environment variable
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Please set the TELEGRAM_BOT_TOKEN environment variable.")

TELEGRAF_OUTPUT = "/home/marc/boat-pi/metrics.json"


def read_telegraf_output() -> dict:
    try:
        with open(TELEGRAF_OUTPUT, "r") as file:
            data = json.load(file)
    except FileNotFoundError:
        logger.error(f"File {TELEGRAF_OUTPUT} not found.")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {TELEGRAF_OUTPUT}.")
        return {}
    
    metrics = {}
    metrics["timestamp"] = data["metrics"][0]["timestamp"]
    gps_data = [m for m in data["metrics"] if m["name"] == "gps"]
    metrics["gps"] = gps_data[0]["fields"] if gps_data else None
    victron = [m for m in data["metrics"] if m["name"] == "victron"]
    metrics["victron"] = victron[0]["fields"] if victron else None
    return metrics


def get_position():
    metrics = read_telegraf_output()
    if not metrics:
        logger.error("No metrics data available.")
        return 52.245126076131164, 8.905499525447263, 0
    
    lat, lon, heading = metrics["gps"]["lat"], metrics["gps"]["lon"], int(metrics["gps"]["track"])
    noise_lat = random.uniform(-0.000001, 0.000001)
    noise_lon = random.uniform(-0.000001, 0.000001)
    lat += noise_lat
    lon += noise_lon
    return lat, lon, heading



def load_users() -> dict:
    try:
        with open("users.json", "r") as fp:
            users = json.load(fp)
    except FileNotFoundError:
        users = {}
    return users


def get_user(user_id: str) -> dict:
    users = load_users()
    return users.get(user_id, None)


def save_users(users: dict):
    with open("users.json", "w") as fp:
        json.dump(users, fp, indent=4)


def get_admins() -> list[dict]:
    users = load_users()
    return [u for u in users.values() if u["admin"]]


def check_user(user: User = None, user_id: str = None) -> str:
    if not user and not user_id:
        raise ValueError("Either user or user_id must be provided.")
    
    users = load_users()
    
    approved_users = [u["id"] for u in users.values() if u["approved"]]
    pending_users = [u["id"] for u in users.values() if u["pending"]]
    blocked_users = [u["id"] for u in users.values() if u["blocked"]]
    admin_users = [u["id"] for u in users.values() if u["admin"]]
    
    if not user_id:
        user_id = user.id

    if user_id in admin_users:
        return "admin"
    elif user_id in approved_users:
        return "approved"
    elif user_id in pending_users:
        return "pending"
    elif user_id in blocked_users:
        return "blocked"
    else:
        return "unknown"


def is_admin(user: User = None, user_id: str = None) -> bool:
    return check_user(user, user_id) == "admin"


def is_approved(user: User = None, user_id: str = None) -> bool:
    return check_user(user, user_id) in ["approved", "admin"]


def is_pending(user: User = None, user_id: str = None) -> bool:
    return check_user(user, user_id) == "pending"


def is_blocked(user: User = None, user_id: str = None) -> bool:
    return check_user(user, user_id) == "blocked"


def is_unknown(user: User = None, user_id: str = None) -> bool:
    return check_user(user, user_id) == "unknown"


def add_pending_user(user: User):
    users = load_users()
    users[user.id] = {
        "id": user.id,
        "name": user.full_name,
        "approved": False,
        "pending": True,
        "admin": False,
        "blocked": False
    }
    save_users(users)


def approve_user(user_id: str):
    users = load_users()
    
    user_id = str(user_id)
    
    if is_blocked(user_id=user_id):
        raise ValueError("User is blocked and cannot be approved.")
    
    users[user_id]["approved"] = True
    users[user_id]["pending"] = False
    save_users(users)

async def send_message_to_admins(context: ContextTypes.DEFAULT_TYPE, message: str):
    admins = get_admins()
    for admin in admins:
        await context.bot.send_message(
            chat_id=admin["id"],
            text=message
        )

# Command: /register
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Registration requested by:" + str(user))

    if is_approved(user):
        logger.info(f"User {user.id} is already registered.")
        await update.message.reply_text("✅ You're already registered.")
    elif is_pending(user):
        logger.info(f"User {user.id} has a pending registration.")
        await update.message.reply_text("🕒 Your registration is pending.")
    elif is_blocked(user):
        logger.warning(f"User {user.id} is blocked.")
        await update.message.reply_text("⛔ You're blocked from using this bot.")
    else:
        add_pending_user(user)
        logger.info(f"User {user.id} added to pending registrations.")
        await update.message.reply_text("📨 Registration request sent. Please wait for approval.")
        
        await send_message_to_admins(context, f"👤 New registration request from {user.full_name} (ID: {user.id})")


# Command: /approve <user_id>
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Approval requested by:" + str(user))
    
    if not is_admin(update.effective_user):
        await update.message.reply_text("⛔ You're not allowed to approve users.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /approve <user_id>")
        return

    try:
        user_id = int(context.args[0])
        user = get_user(user_id=str(user_id))
    except ValueError:
        logger.error("Invalid user ID provided.")
        await update.message.reply_text("❌ Invalid user ID.")
        return

    if is_pending(user_id=user_id) or is_admin(user_id=user_id):
        approve_user(user_id=user_id)

        await send_message_to_admins(context, f"✅ Approved {user['name']} (ID: {user_id})")
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Your registration has been approved! You can now use /live."
            )
        except:
            pass
    else:
        await update.message.reply_text("ℹ️ No such user in pending list.")


# Command: /live (send live location)
async def send_live_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info("Live location requested by:" + str(user))

    if not is_approved(user):
        await update.message.reply_text("❌ You're not approved to access the location. Use /register.")
        return

    latitude, longitude, heading = get_position()
    logger.info(f"Sending live location: {latitude}, {longitude}, heading {heading}")
    
    update_period = 15*60

    msg = await update.message.reply_location(
        latitude=latitude,
        longitude=longitude,
        heading=heading,
        live_period=update_period
    )

    message_id = msg.message_id
    chat_id = update.effective_chat.id

    for _ in range(int(update_period / UPDATE_INTERVAL)):
        await asyncio.sleep(UPDATE_INTERVAL)

        new_latitude, new_longitude, new_heading = get_position()
        
        if new_latitude == latitude and new_longitude == longitude and new_heading == heading:
            logger.info("Position has not changed, skipping update.")
            continue
        latitude, longitude, heading = new_latitude, new_longitude, new_heading
        logger.info(f"Updating location to: {latitude}, {longitude}, heading {heading}")
        try:
            await context.bot.edit_message_live_location(
                chat_id=chat_id,
                message_id=message_id,
                latitude=latitude,
                heading=heading,
                longitude=longitude
            )
        except Exception as e:
            logger.error(f"Error updating location: {e}")
            if str(e).startswith("Message is not modified"):
                continue
            # stop location sharing
            await context.bot.stop_message_live_location(
                chat_id=chat_id,
                message_id=message_id
            )
            break


# Main app
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("register", register))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("live", send_live_location))

app.run_polling()
