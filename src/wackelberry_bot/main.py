
import os
import json
from telegram import Update, User
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
import asyncio

UPDATE_INTERVAL = 15  # seconds
# Load the bot token from environment variable
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Please set the TELEGRAM_BOT_TOKEN environment variable.")


# Mock GPS function
def get_position():
    from random import uniform
    return (37.7749 + uniform(-0.001, 0.001), -122.4194 + uniform(-0.001, 0.001))


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
    print("Registration requested by:", user)

    if is_approved(user):
        await update.message.reply_text("✅ You're already registered.")
    elif is_pending(user):
        await update.message.reply_text("🕒 Your registration is pending.")
    elif is_blocked(user):
        await update.message.reply_text("⛔ You're blocked from using this bot.")
    else:
        add_pending_user(user)
        await update.message.reply_text("📨 Registration request sent. Please wait for approval.")
        
        await send_message_to_admins(context, f"👤 New registration request from {user.full_name} (ID: {user.id})")


# Command: /approve <user_id>
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    print("Approval requested by:", user)
    
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
    print("Live location requested by:", user)

    if not is_approved(user):
        await update.message.reply_text("❌ You're not approved to access the location. Use /register.")
        return

    latitude, longitude = get_position()

    msg = await update.message.reply_location(
        latitude=latitude,
        longitude=longitude,
        live_period=3600
    )

    message_id = msg.message_id
    chat_id = update.effective_chat.id

    for _ in range(int(3600 / UPDATE_INTERVAL)):
        await asyncio.sleep(UPDATE_INTERVAL)

        latitude, longitude = get_position()
        try:
            await context.bot.edit_message_live_location(
                chat_id=chat_id,
                message_id=message_id,
                latitude=latitude,
                longitude=longitude
            )
        except Exception as e:
            print(f"Error updating location: {e}")
            # TODO: Cancel sharing
            break


# Main app
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("register", register))
app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("live", send_live_location))

app.run_polling()
