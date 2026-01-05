import os
import time
import requests
import re
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

BUY_SELL = ["куплю", "продам"]
UA_BANKS = ["укр", "укра", "банк", "банки", "грн"]
USDT = ["usdt", "юсдт"]

STOP_SUBSTRINGS = [
    "скам","scam","фейк","fake","шутка","мем",
    "оффтоп","offtop","обсуждение","курс","новости"
]

STOP_WORDS_EXACT = ["ру","спб","сбер"]

headers = {
    "Authorization": DISCORD_TOKEN,
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

last_message_id = None
first_run = True

def normalize(text: str) -> str:
    return " ".join(text.lower().split())

def contains_stop_words(text: str) -> bool:
    t = normalize(text)

    for sw in STOP_SUBSTRINGS:
        if sw in t:
            return True

    words = re.findall(r"\b\w+\b", t)
    for sw in STOP_WORDS_EXACT:
        if sw in words:
            return True

    return False

def contains_keywords(text: str) -> bool:
    t = normalize(text)
    return (
        (any(w in t for w in BUY_SELL) and any(w in t for w in UA_BANKS)) or
        (any(w in t for w in BUY_SELL) and any(w in t for w in USDT))
    )

def escape_html(text: str) -> str:
    return text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def format_discord_time(iso_time: str) -> str:
    dt = datetime.fromisoformat(iso_time.replace("Z","+00:00"))
    return dt.astimezone().strftime("%d.%m.%Y %H:%M")

def get_latest_message():
    url = f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?limit=1"
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()[0]

def send_to_telegram(text: str):
    requests.post(
        f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TG_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        },
        timeout=20
    )

print("Bot started (FIXED STOP WORDS)")

while True:
    try:
        msg = get_latest_message()
        raw = msg.get("content","")

        if contains_stop_words(raw):
            time.sleep(CHECK_INTERVAL)
            continue

        if not contains_keywords(raw):
            time.sleep(CHECK_INTERVAL)
            continue

        content = escape_html(raw)
        author = escape_html(msg["author"]["username"])
        time_str = format_discord_time(msg["timestamp"])

        if first_run:
            first_run = False
            last_message_id = msg["id"]
            title = "🟦 Discord | Последнее сообщение"
        elif msg["id"] != last_message_id:
            last_message_id = msg["id"]
            title = "🟦 Discord"
        else:
            time.sleep(CHECK_INTERVAL)
            continue

        send_to_telegram(
            f"<b>{title}</b>\n\n"
            f"👤 <b>{author}</b>\n"
            f"🕒 <i>{time_str}</i>\n\n"
            f"💬 {content}"
        )

    except Exception as e:
        print("Error:", e)

    time.sleep(CHECK_INTERVAL)
