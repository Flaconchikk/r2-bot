import os
import time
import requests

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

headers = {
    "Authorization": DISCORD_TOKEN,
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

last_message_id = None

def get_latest_message():
    url = f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?limit=1"
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()[0]

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload, timeout=20)

print("Discord → Telegram bot started")

while True:
    try:
        msg = get_latest_message()
        if msg["id"] != last_message_id:
            last_message_id = msg["id"]
            author = msg["author"]["username"]
            content = msg["content"] or "[no text]"
            text = f"🟦 Discord\n👤 {author}\n\n{content}"
            send_to_telegram(text)
    except Exception as e:
        print("Error:", e)

    time.sleep(CHECK_INTERVAL)
