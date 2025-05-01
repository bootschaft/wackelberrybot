# Wackelberry Bot

Wackelberry Bot is a Telegram bot that provides user registration, approval, and live location sharing functionalities. It is designed to manage user access and share live GPS locations with approved users.

## Features

### 1. User Registration
- **Command:** `/register`
- Allows users to request registration.
- Responses:
  - ✅ If the user is already registered.
  - 🕒 If the user's registration is pending approval.
  - ⛔ If the user is blocked.
  - 📨 Sends a registration request to admins if the user is unknown.

### 2. User Approval
- **Command:** `/approve <user_id>`
- Admins can approve pending users.
- Sends a notification to the approved user and other admins.
- Validates user status before approval:
  - Blocks approval for users who are already blocked.
  - Approves users who are pending or already admins.

### 3. Live Location Sharing
- **Command:** `/live`
- Approved users can request live GPS location updates.
- Sends a live location message that updates every 15 seconds for up to 1 hour.
- Blocks access for unapproved users.

## How It Works

1. **User Management:**
   - User data is stored in `users.json`.
   - Users are categorized as:
     - `admin`: Admin users with special privileges.
     - `approved`: Approved users with access to bot features.
     - `pending`: Users awaiting admin approval.
     - `blocked`: Users restricted from using the bot.
     - `unknown`: Users not yet registered.

2. **Admin Notifications:**
   - Admins are notified of new registration requests and approvals.

3. **Live Location Updates:**
   - Uses a mock GPS function to simulate location updates.
   - Updates the live location message periodically.

## Setup

1. Clone the repository.
2. Install dependencies using [Poetry](https://python-poetry.org/):
   ```bash
   poetry install
   ```
3. Create a .env file and set the TELEGRAM_BOT_TOKEN environment variable:
   ```
   TELEGRAM_BOT_TOKEN="..."
   ```
4. Run the bot:
    ```bash
    poetry run python main.py
    ```
