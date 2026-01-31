from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import schedule
import time
import threading
import datetime
import re
import sqlite3


import os
BOT_TOKEN = os.getenv("8513604691:AAGQGDRkFY7wGzShDGnhXeO8alZil_HE4h0")

# ---------------- DATABASE ----------------

conn = sqlite3.connect("reminders.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER,
    task TEXT,
    time TEXT,
    daily INTEGER
)
""")
conn.commit()

# ---------------- REMINDER ----------------

def send_reminder(chat_id, context, task, daily):
    text = "🔔 Daily Reminder: " if daily else "🔔 Reminder: "
    context.bot.send_message(chat_id=chat_id, text=text + task)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

def schedule_from_db(context):
    cursor.execute("SELECT chat_id, task, time, daily FROM reminders")
    rows = cursor.fetchall()

    for chat_id, task, reminder_time, daily in rows:
        if daily:
            schedule.every().day.at(reminder_time).do(
                send_reminder, chat_id, context, task, True
            )
        else:
            schedule.every().day.at(reminder_time).do(
                send_reminder, chat_id, context, task, False
            )

# ---------------- PARSING ----------------

def parse_time(text):
    text = text.lower()

    if "tonight" in text:
        return "21:00"

    match = re.search(r'(\d{1,2})(:\d{2})?\s?(am|pm)?', text)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2)[1:]) if match.group(2) else 0
    period = match.group(3)

    if period == "pm" and hour != 12:
        hour += 12
    if period == "am" and hour == 12:
        hour = 0

    return f"{hour:02d}:{minute:02d}"

def parse_task(text):
    text = re.sub(r"(remind me to|please|can you|every day|at.*)", "", text.lower())
    return text.strip()

# ---------------- HANDLER ----------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id

    if "remind" not in text.lower():
        await update.message.reply_text("🤖 I can save reminders for you!")
        return

    daily = "every day" in text.lower()
    reminder_time = parse_time(text)
    task = parse_task(text)

    if not reminder_time or not task:
        await update.message.reply_text(
            "❌ I couldn't understand.\nExample:\nRemind me to study every day at 9pm"
        )
        return

    # Save to DB
    cursor.execute(
        "INSERT INTO reminders (chat_id, task, time, daily) VALUES (?, ?, ?, ?)",
        (chat_id, task, reminder_time, int(daily))
    )
    conn.commit()

    # Schedule immediately
    if daily:
        schedule.every().day.at(reminder_time).do(
            send_reminder, chat_id, context, task, True
        )
    else:
        schedule.every().day.at(reminder_time).do(
            send_reminder, chat_id, context, task, False
        )

    await update.message.reply_text(
        f"✅ Saved!\n🕒 Time: {reminder_time}\n📝 Task: {task}\n🔁 Daily: {daily}"
    )

# ---------------- BOT ----------------

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

threading.Thread(target=run_scheduler, daemon=True).start()

print("🤖 Bot is running...")

# Load reminders from DB on startup
schedule_from_db(app.bot)

app.run_polling()

