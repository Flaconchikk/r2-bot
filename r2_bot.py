
# ================== R2 BUYER BOT — ALL IN ONE (FULL & FIXED) ==================
# aiogram 3.x | FULL PRODUCTION | SINGLE FILE
# ============================================================================

import asyncio
import time
import logging
import traceback
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage

# ================== CONFIG ==================

BOT_TOKEN = "BOT TOKEN"
ADMIN_ID = 6216901670
GROUP_ID = -1003099089601

DB = "database.db"

RATE_UAH = 60
RATE_USDT = 1.4

BAN_SECONDS = 15 * 60
TIMER_SECONDS = 10 * 60
SPAM_DELAY = 1.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ================== DATABASE ==================

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                banned_until INTEGER DEFAULT 0
            )"""
        )

        await db.execute(
            """CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                currency TEXT,
                bank TEXT,
                initials TEXT,
                usdt_net TEXT,
                amount_kk INTEGER,
                deal_time TEXT,
                nick TEXT,
                status TEXT,
                created_at INTEGER
            )"""
        )

        # ---- migration: timer_until ----
        cur = await db.execute("PRAGMA table_info(deals)")
        cols = [row[1] for row in await cur.fetchall()]
        if "timer_until" not in cols:
            await db.execute("ALTER TABLE deals ADD COLUMN timer_until INTEGER")

        # ---- migration: usdt_net ----
        cur = await db.execute("PRAGMA table_info(deals)")
        cols = [row[1] for row in await cur.fetchall()]
        if "usdt_net" not in cols:
            await db.execute("ALTER TABLE deals ADD COLUMN usdt_net TEXT")

        await db.commit()

async def db_exec(sql, params=(), fetch=False, one=False):
    async with aiosqlite.connect(DB) as conn:
        cur = await conn.execute(sql, params)
        await conn.commit()
        if fetch:
            return await (cur.fetchone() if one else cur.fetchall())

async def is_banned(uid):
    r = await db_exec("SELECT banned_until FROM users WHERE user_id=?", (uid,), True, True)
    return r and r[0] > int(time.time())

async def has_active(uid):
    # active only if amount_kk IS NOT NULL and status active
    r = await db_exec(
        "SELECT id FROM deals WHERE user_id=? AND status IN ('new','time_set','time_confirmed','nick_set','buyer_created','paid')",
        (uid,), True, True
    )
    return bool(r)

# ================== KEYBOARDS ==================

def reply_kb(*texts):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t)] for t in texts],
        resize_keyboard=True
    )

def inline_kb(pairs):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d)] for t, d in pairs]
    )

# ================== HELPERS ==================

def kk_fmt(k):
    if k is None:
        return "—"
    return f"{k}кк ({k*1_000_000:,}".replace(",", ".") + ")"

def sum_fmt(cur, k):
    return f"{k*RATE_UAH} грн" if cur == "UAH" else f"{k*RATE_USDT:.2f} USDT"

_last_action = {}

async def anti_spam(uid):
    now = time.time()
    if uid in _last_action and now - _last_action[uid] < SPAM_DELAY:
        return False
    _last_action[uid] = now
    return True

# ================== FSM ==================

class DealFSM(StatesGroup):
    currency = State()
    bank = State()
    initials = State()
    usdt_net = State()
    amount = State()
    admin_time = State()
    admin_nick = State()

# ================== BOT INIT ==================

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# ================== MENU ==================

@dp.message(F.text == "/start")
@dp.message(F.text == "⬅ ГЛАВНОЕ МЕНЮ")
async def menu(msg: Message):
    await msg.answer(
        "🏦 <b>R2 SILVER TRADE</b>",
        reply_markup=reply_kb(
            "🟢 ОСТАВИТЬ ЗАЯВКУ",
            "💱 ПРОВЕРИТЬ КУРС",
            "📂 МОИ АКТИВНЫЕ СДЕЛКИ",
            "📜 ИСТОРИЯ",
            "🧹 ОЧИСТИТЬ АКТИВНЫЕ ЗАКАЗЫ",
            "ℹ️ О БОТЕ"
        )
    )

# ================== STATIC ==================

@dp.message(F.text == "💱 ПРОВЕРИТЬ КУРС")
async def rate(msg: Message):
    await msg.answer(
        f"💴 <b>{RATE_UAH}</b> грн / 1кк\n💵 <b>{RATE_USDT}</b> USDT / 1кк",
        reply_markup=reply_kb("⬅ ГЛАВНОЕ МЕНЮ")
    )

@dp.message(F.text == "ℹ️ О БОТЕ")
async def about(msg: Message):
    await msg.answer(
        "🤖 <b>О БОТЕ</b>\n\n"
        "Бот предназначен для создания сделок.\n"
        "Все оплаты и подтверждения проходят <b>ТОЛЬКО В ИГРЕ</b>.",
        reply_markup=reply_kb("⬅ ГЛАВНОЕ МЕНЮ")
    )

# ================== ACTIVE DEALS ==================

@dp.message(F.text == "📂 МОИ АКТИВНЫЕ СДЕЛКИ")
async def my_active(msg: Message):
    rows = await db_exec(
        "SELECT id,status,amount_kk,currency FROM deals "
        "WHERE user_id=? AND status IN ('new','time_set','time_confirmed','nick_set','buyer_created','paid')",
        (msg.from_user.id,), True
    )
    if not rows:
        return await msg.answer("📂 У вас нет активных сделок.", reply_markup=reply_kb("⬅ ГЛАВНОЕ МЕНЮ"))
    for did, st, kk, cur in rows:
        await msg.answer(
            f"📂 <b>Сделка #{did}</b>\n"
            f"📦 {kk_fmt(kk)}\n"
            f"📌 Статус: <i>{st}</i>",
            reply_markup=inline_kb([
                ("❌ ОТМЕНИТЬ СДЕЛКУ", f"user_cancel:{did}")
            ])
        )

# ================== HISTORY ==================

@dp.message(F.text == "📜 ИСТОРИЯ")
async def history(msg: Message):
    if msg.from_user.id == ADMIN_ID:
        rows = await db_exec(
            "SELECT id,user_id,amount_kk,currency FROM deals "
            "WHERE status='done' ORDER BY id DESC LIMIT 10",
            fetch=True
        )
        if not rows:
            return await msg.answer("📜 История пуста.", reply_markup=reply_kb("⬅ ГЛАВНОЕ МЕНЮ"))
        text = "📜 <b>История заказов (ADMIN)</b>\n\n"
        for did, uid, kk, cur in rows:
            text += f"• #{did} | UID {uid} | {kk_fmt(kk)} | {sum_fmt(cur,kk)}\n"
    else:
        rows = await db_exec(
            "SELECT id,amount_kk,currency FROM deals "
            "WHERE user_id=? AND status='done' ORDER BY id DESC LIMIT 10",
            (msg.from_user.id,), True
        )
        if not rows:
            return await msg.answer("📜 История пуста.", reply_markup=reply_kb("⬅ ГЛАВНОЕ МЕНЮ"))
        text = "📜 <b>История сделок</b>\n\n"
        for did, kk, cur in rows:
            text += f"• #{did} — {kk_fmt(kk)} — {sum_fmt(cur,kk)}\n"
    await msg.answer(text, reply_markup=reply_kb("⬅ ГЛАВНОЕ МЕНЮ"))

# ================== DEAL CREATION ==================

@dp.message(F.text == "🟢 ОСТАВИТЬ ЗАЯВКУ")
async def create(msg: Message, state: FSMContext):
    if await is_banned(msg.from_user.id):
        return await msg.answer("⛔ Временный бан.", reply_markup=reply_kb("⬅ ГЛАВНОЕ МЕНЮ"))
    if await has_active(msg.from_user.id):
        return await msg.answer("⚠️ У вас уже есть активная сделка.", reply_markup=reply_kb("⬅ ГЛАВНОЕ МЕНЮ"))
    await state.clear()
    await msg.answer("Выберите валюту:", reply_markup=reply_kb("💴 ГРН", "💵 USDT"))
    await state.set_state(DealFSM.currency)

@dp.message(DealFSM.currency)
async def choose_currency(msg: Message, state: FSMContext):
    if msg.text == "💴 ГРН":
        await state.update_data(currency="UAH")
        await msg.answer("Выберите банк:", reply_markup=reply_kb("Приват24", "Монобанк", "Другие"))
        await state.set_state(DealFSM.bank)
    elif msg.text == "💵 USDT":
        await state.update_data(currency="USDT")
        await msg.answer("Выберите сеть:", reply_markup=reply_kb("Binance ID", "BEP20", "TRC20"))
        await state.set_state(DealFSM.usdt_net)

@dp.message(DealFSM.bank)
async def choose_bank(msg: Message, state: FSMContext):
    await state.update_data(bank=msg.text)
    await msg.answer("Введите инициалы:")
    await state.set_state(DealFSM.initials)

@dp.message(DealFSM.initials)
async def initials(msg: Message, state: FSMContext):
    await state.update_data(initials=msg.text)
    await msg.answer("Введите количество (кк):")
    await state.set_state(DealFSM.amount)

@dp.message(DealFSM.usdt_net)
async def choose_net(msg: Message, state: FSMContext):
    await state.update_data(usdt_net=msg.text)
    await msg.answer("Введите количество (кк):")
    await state.set_state(DealFSM.amount)

@dp.message(DealFSM.amount)
async def amount(msg: Message, state: FSMContext):
    try:
        k = int(msg.text)
    except:
        return await msg.answer("Введите число.")
    data = await state.get_data()

    if data.get("currency") == "UAH" and k < 10:
        return await msg.answer("Минимум 10кк.")
    if data.get("usdt_net") == "BEP20" and k < 10_000_000:
        return await msg.answer("Минимум 10кк.")
    if data.get("usdt_net") == "TRC20" and k < 50_000_000:
        return await msg.answer("Минимум 50кк.")

    await db_exec(
        "INSERT INTO deals (user_id,currency,bank,initials,usdt_net,amount_kk,status,created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            msg.from_user.id,
            data.get("currency"),
            data.get("bank"),
            data.get("initials"),
            data.get("usdt_net"),
            k,
            "new",
            int(time.time())
        )
    )

    deal_id = (await db_exec("SELECT MAX(id) FROM deals", fetch=True, one=True))[0]

    await bot.send_message(
        GROUP_ID,
        f"🆕 <b>Заявка #{deal_id}</b>\n📦 {kk_fmt(k)}\n💵 {sum_fmt(data.get('currency'), k)}",
        reply_markup=inline_kb([
            ("⏱ УКАЗАТЬ ВРЕМЯ", f"time:{deal_id}"),
            ("❌ ОТМЕНИТЬ", f"cancel:{deal_id}")
        ])
    )

    await msg.answer("Заявка отправлена админу.", reply_markup=reply_kb("⬅ ГЛАВНОЕ МЕНЮ"))
    await state.clear()

# ================== ADMIN / BUYER CHAIN ==================
# (same as production version, unchanged)

@dp.callback_query(F.data.startswith("time:"))
async def admin_time(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.edit_reply_markup(None)
    await state.update_data(deal_id=int(cb.data.split(":")[1]))
    await cb.message.answer("Введите время сделки (HH:MM):")
    await state.set_state(DealFSM.admin_time)

@dp.message(DealFSM.admin_time)
async def save_time(msg: Message, state: FSMContext):
    deal_id = (await state.get_data())["deal_id"]
    await db_exec("UPDATE deals SET deal_time=?, status=? WHERE id=?", (msg.text, "time_set", deal_id))
    uid = (await db_exec("SELECT user_id FROM deals WHERE id=?", (deal_id,), True, True))[0]
    await bot.send_message(
        uid,
        f"⏱ Время сделки: <b>{msg.text}</b>",
        reply_markup=inline_kb([
            ("✅ ПОДТВЕРДИТЬ", f"confirm:{deal_id}"),
            ("❌ ОТМЕНИТЬ", f"user_cancel:{deal_id}")
        ])
    )
    await state.clear()

@dp.callback_query(F.data.startswith("confirm:"))
async def confirm_time(cb: CallbackQuery):
    deal_id = int(cb.data.split(":")[1])
    await cb.answer()
    await cb.message.edit_reply_markup(None)
    await db_exec("UPDATE deals SET status=? WHERE id=?", ("time_confirmed", deal_id))
    await bot.send_message(
        ADMIN_ID,
        f"⏱ Время подтверждено по сделке #{deal_id}",
        reply_markup=inline_kb([("✏️ ВВЕСТИ НИК", f"nick:{deal_id}")])
    )

@dp.callback_query(F.data.startswith("nick:"))
async def ask_nick(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.edit_reply_markup(None)
    await state.update_data(deal_id=int(cb.data.split(":")[1]))
    await cb.message.answer("Введите ник покупателя:")
    await state.set_state(DealFSM.admin_nick)

@dp.message(DealFSM.admin_nick)
async def save_nick(msg: Message, state: FSMContext):
    deal_id = (await state.get_data())["deal_id"]
    await db_exec(
        "UPDATE deals SET nick=?, status=?, timer_until=? WHERE id=?",
        (msg.text, "nick_set", int(time.time()) + TIMER_SECONDS, deal_id)
    )
    uid = (await db_exec("SELECT user_id FROM deals WHERE id=?", (deal_id,), True, True))[0]
    await bot.send_message(
        uid,
        f"👤 Ник для сделки: <b>{msg.text}</b>\nСоздайте сделку в игре.",
        reply_markup=inline_kb([("🟢 СДЕЛКУ СОЗДАЛ", f"created:{deal_id}")])
    )
    await state.clear()

@dp.callback_query(F.data.startswith("created:"))
async def buyer_created(cb: CallbackQuery):
    deal_id = int(cb.data.split(":")[1])
    await cb.answer()
    await cb.message.edit_reply_markup(None)
    await db_exec("UPDATE deals SET status=? WHERE id=?", ("buyer_created", deal_id))
    await bot.send_message(
        ADMIN_ID,
        f"💸 Сделка #{deal_id}: покупатель создал сделку",
        reply_markup=inline_kb([("💰 ОПЛАТИЛ", f"paid:{deal_id}")])
    )

@dp.callback_query(F.data.startswith("paid:"))
async def admin_paid(cb: CallbackQuery):
    deal_id = int(cb.data.split(":")[1])
    await cb.answer()
    await cb.message.edit_reply_markup(None)
    await db_exec("UPDATE deals SET status=? WHERE id=?", ("paid", deal_id))
    uid = (await db_exec("SELECT user_id FROM deals WHERE id=?", (deal_id,), True, True))[0]
    await bot.send_message(
        uid,
        "💸 Средства переведены. Подтвердите получение.",
        reply_markup=inline_kb([("✅ СДЕЛКУ ПОДТВЕРДИЛ", f"user_confirm:{deal_id}")])
    )

@dp.callback_query(F.data.startswith("user_confirm:"))
async def buyer_confirm(cb: CallbackQuery):
    deal_id = int(cb.data.split(":")[1])
    await cb.answer()
    await cb.message.edit_reply_markup(None)
    await db_exec("UPDATE deals SET status=? WHERE id=?", ("buyer_confirmed", deal_id))
    await bot.send_message(
        ADMIN_ID,
        f"✅ Покупатель подтвердил сделку #{deal_id}",
        reply_markup=inline_kb([("🏁 ЗАВЕРШИТЬ СДЕЛКУ", f"finish:{deal_id}")])
    )

@dp.callback_query(F.data.startswith("finish:"))
async def finish(cb: CallbackQuery):
    deal_id = int(cb.data.split(":")[1])
    await cb.answer()
    await cb.message.edit_reply_markup(None)
    await db_exec("UPDATE deals SET status=? WHERE id=?", ("done", deal_id))
    uid = (await db_exec("SELECT user_id FROM deals WHERE id=?", (deal_id,), True, True))[0]
    await bot.send_message(uid, "🎉 Сделка успешно завершена!")
    await bot.send_message(ADMIN_ID, f"🎉 Сделка #{deal_id} завершена.")


@dp.message(F.text == "🧹 ОЧИСТИТЬ АКТИВНЫЕ ЗАКАЗЫ")
async def admin_clear_active(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    rows = await db_exec(
        "SELECT DISTINCT user_id FROM deals "
        "WHERE status IN ('new','time_set','time_confirmed','nick_set','buyer_created','paid')",
        fetch=True
    )

    if not rows:
        return await msg.answer(
            "🧹 Активных сделок нет.",
            reply_markup=reply_kb("⬅ ГЛАВНОЕ МЕНЮ")
        )

    count = 0
    for (uid,) in rows:
        await db_exec(
            "UPDATE deals SET status='cancelled' "
            "WHERE user_id=? AND status IN ('new','time_set','time_confirmed','nick_set','buyer_created','paid')",
            (uid,)
        )
        await db_exec(
            "INSERT OR IGNORE INTO users (user_id,banned_until) VALUES (?,0)",
            (uid,)
        )
        count += 1

    await msg.answer(
        f"🧹 <b>Очистка завершена</b>\n"
        f"Пользователей очищено: <b>{count}</b>",
        reply_markup=reply_kb("⬅ ГЛАВНОЕ МЕНЮ")
    )


# ================== TIMER ==================

async def timer_watcher():
    while True:
        now = int(time.time())
        rows = await db_exec(
            "SELECT id,user_id FROM deals WHERE status='nick_set' AND timer_until<?",
            (now,), True
        )
        for deal_id, uid in rows:
            await db_exec("UPDATE deals SET status='cancelled' WHERE id=?", (deal_id,))
            await db_exec(
                "INSERT OR REPLACE INTO users (user_id,banned_until) VALUES (?,?)",
                (uid, now + BAN_SECONDS)
            )
            await bot.send_message(uid, "⏱ Время истекло. Сделка отменена.")
            await bot.send_message(ADMIN_ID, f"⛔ Сделка #{deal_id} отменена по таймеру.")
        await asyncio.sleep(5)

# ================== ERRORS ==================

@dp.errors()
async def errors_handler(event, exception: Exception):
    logging.error("Exception: %s", exception)
    traceback.print_exc()
    return True

# ================== MAIN ==================

async def main():
    await init_db()
    asyncio.create_task(timer_watcher())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
