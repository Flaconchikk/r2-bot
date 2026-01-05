import os
import time
import requests
from datetime import datetime

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "90"))

required = {
    "DISCORD_TOKEN": DISCORD_TOKEN,
    "CHANNEL_ID": CHANNEL_ID,
    "TG_BOT_TOKEN": TG_BOT_TOKEN,
    "TG_CHAT_ID": TG_CHAT_ID,
}

missing = [k for k, v in required.items() if not v]
if missing:
    raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

KEYWORDS = [
    "продам укр банки",
    "продам грн",
    "куплю укр банки",
    "куплю грн",
    "продам usdt",
    "продам юсдт",
    "куплю usdt",
    "куплю юсдт",
]

headers = {
    "Authorization": DISCORD_TOKEN,
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

last_message_id = None
first_run = True

def normalize(text: str) -> str:
    return " ".join(text.lower().split())

def contains_keywords(text: str) -> bool:
    text = normalize(text)
    return any(kw in text for kw in KEYWORDS)

def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )

def format_discord_time(iso_time: str) -> str:
    dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
    return dt.astimezone().strftime("%d.%m.%Y %H:%M")

def get_latest_message():
    url = f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?limit=1"
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data[0] if data else None

def send_to_telegram(text: str):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=20)

print("Discord → Telegram bot started")

while True:
    try:
        msg = get_latest_message()
        if not msg:
            time.sleep(CHECK_INTERVAL)
            continue

        msg_id = msg["id"]
        raw_content = msg["content"] or ""

        if not contains_keywords(raw_content):
            time.sleep(CHECK_INTERVAL)
            continue

        content = escape_html(raw_content)
        author = escape_html(msg["author"]["username"])
        time_str = format_discord_time(msg["timestamp"])

        if first_run:
            first_run = False
            last_message_id = msg_id
            title = "🟦 Discord | Последнее сообщение"
        elif msg_id != last_message_id:
            last_message_id = msg_id
            title = "🟦 Discord"
        else:
            time.sleep(CHECK_INTERVAL)
            continue

        text = (
            f"<b>{title}</b>\n\n"
            f"👤 <b>{author}</b>\n"
            f"🕒 <i>{time_str}</i>\n\n"
            f"💬 {content}"
        )

        send_to_telegram(text)
        print(f"Sent message {msg_id}")

    except Exception as e:
        print("Error:", e)

    time.sleep(CHECK_INTERVAL)
