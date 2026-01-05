
# main.py — NICK-BLOCK PARSER (FINAL)

import os
import time
import requests
import re
from datetime import datetime

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "10"))

required = {
    "DISCORD_TOKEN": DISCORD_TOKEN,
    "CHANNEL_ID": CHANNEL_ID,
    "TG_BOT_TOKEN": TG_BOT_TOKEN,
    "TG_CHAT_ID": TG_CHAT_ID,
}

missing = [k for k, v in required.items() if not v]
if missing:
    raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

BUY_WORDS = ["куплю", "продам"]
UA_WORDS = ["грн", "гривн", "укр", "укра"]
USDT_WORDS = ["usdt", "юсдт"]

STOP_SUBSTRINGS = [
    "скам","scam","фейк","fake","шутка","мем",
    "оффтоп","offtop","обсуждение","курс","новости"
]
STOP_WORDS_EXACT = ["спб", "сбер"]

headers = {
    "Authorization": DISCORD_TOKEN,
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

last_message_id = None

def normalize(text: str) -> str:
    return " ".join(text.lower().split())

def has_currency(text: str) -> bool:
    t = normalize(text)
    return any(w in t for w in UA_WORDS) or any(w in t for w in USDT_WORDS)

def contains_stop_words(text: str) -> bool:
    t = normalize(text)
    if has_currency(t):
        return False
    for sw in STOP_SUBSTRINGS:
        if sw in t:
            return True
    words = re.findall(r"\b\w+\b", t)
    for sw in STOP_WORDS_EXACT:
        if sw in words:
            return True
    return False

def split_by_nicks(text: str):
    pattern = re.compile(r"(\[[^\]]+\]:)")
    parts = pattern.split(text)
    blocks = []
    for i in range(1, len(parts), 2):
        nick = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        blocks.append(f"{nick} {body}".strip())
    return blocks

def classify_block(block: str):
    t = normalize(block)
    if not any(w in t for w in BUY_WORDS):
        return None
    if not has_currency(t):
        return None
    if contains_stop_words(t):
        return None
    if "продам" in t:
        return "SELL"
    if "куплю" in t:
        return "BUY"
    return None

def escape_html(text: str) -> str:
    return text.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def format_discord_time(iso_time: str) -> str:
    dt = datetime.fromisoformat(iso_time.replace("Z","+00:00"))
    return dt.astimezone().strftime("%d.%m.%Y %H:%M")

def fetch_messages():
    url = f"https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?limit={FETCH_LIMIT}"
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()

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

print("Bot started (NICK-BLOCK parsing enabled)")

while True:
    try:
        messages = fetch_messages()
        for msg in reversed(messages):
            msg_id = msg["id"]
            if last_message_id and msg_id <= last_message_id:
                continue
            raw = msg.get("content", "")
            blocks = split_by_nicks(raw)
            for block in blocks:
                trade = classify_block(block)
                if not trade:
                    continue
                badge = "🔴 BUY" if trade == "BUY" else "🟢 SELL"
                send_to_telegram(
                    f"<b>{badge}</b>\n\n"
                    f"👤 <b>{msg['author']['username']}</b>\n"
                    f"🕒 <i>{format_discord_time(msg['timestamp'])}</i>\n\n"
                    f"💬 {escape_html(block)}"
                )
                last_message_id = msg_id
                break
        time.sleep(CHECK_INTERVAL)
    except Exception as e:
        print("ERROR:", e)
        time.sleep(10)
