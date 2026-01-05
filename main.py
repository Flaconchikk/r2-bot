
import os
import time
import requests
import re
from datetime import datetime

# ================= ENV =================
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

# ================= FILTERS =================
BUY_WORDS = ["куплю", "продам"]

UA_WORDS = ["грн", "гривн", "укр", "укра", "банк", "банки"]
USDT_WORDS = ["usdt", "юсдт"]

# nкк (optional now)
KK_PATTERN = re.compile(r"\b\d+\s*кк\b")

# Goods to IGNORE (do not require, do not block)
IGNORED_GOODS = ["серебро", "золото", "gold", "silver"]

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

# ================= HELPERS =================
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

    has_trade = any(w in t for w in BUY_WORDS)
    has_ua = any(w in t for w in UA_WORDS)
    has_usdt = any(w in t for w in USDT_WORDS)
    has_kk = bool(KK_PATTERN.search(t))

    # Условия:
    # 1) куплю/продам
    # 2) (UA или USDT)
    # 3) кк НЕ обязательно
    return has_trade and (has_ua or has_usdt)

def get_trade_type(text: str) -> str:
    t = normalize(text)
    if "куплю" in t:
        return "BUY"
    if "продам" in t:
        return "SELL"
    return "TRADE"

def escape_html(text: str) -> str:
    return (
        text.replace("&","&amp;")
            .replace("<","&lt;")
            .replace(">","&gt;")
    )

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

# ================= START =================
print("Bot started (KK optional, goods ignored)")

while True:
    try:
        messages = fetch_messages()

        for msg in reversed(messages):
            msg_id = msg["id"]

            if last_message_id and msg_id <= last_message_id:
                continue

            raw = msg.get("content", "")
            print(f"[CHECK] {msg_id}: {raw}")

            if contains_stop_words(raw):
                print("  ⛔ stop-word")
                continue

            if not contains_keywords(raw):
                print("  ⛔ no trade keywords")
                continue

            trade = get_trade_type(raw)
            badge = "🔴 BUY" if trade == "BUY" else "🟢 SELL"

            content = escape_html(raw)
            author = escape_html(msg["author"]["username"])
            time_str = format_discord_time(msg["timestamp"])

            send_to_telegram(
                f"<b>{badge}</b>\n\n"
                f"👤 <b>{author}</b>\n"
                f"🕒 <i>{time_str}</i>\n\n"
                f"💬 {content}"
            )

            print(f"  ✅ SENT {msg_id}")
            last_message_id = msg_id

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("ERROR:", e)
        time.sleep(10)
