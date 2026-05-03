import os
import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from binance_api import (
    get_price_change, format_price_message,
    SUPPORTED_COINS, MARKET_SPOT, MARKET_FUTURES
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# alert_jobs[chat_id] = {"job", "interval", "coins", "market", "started"}
alert_jobs: dict = {}

# Per-chat market preference (default: spot)
chat_market: dict = {}  # chat_id -> MARKET_SPOT | MARKET_FUTURES


# ══════════════════════════════════════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════════════════════════════════════

def main_keyboard(chat_id: int = None):
    market = chat_market.get(chat_id, MARKET_SPOT)
    spot_check    = "✅" if market == MARKET_SPOT    else "◻️"
    futures_check = "✅" if market == MARKET_FUTURES else "◻️"

    keyboard = [
        [
            InlineKeyboardButton(f"{spot_check} Spot",    callback_data="switch_spot"),
            InlineKeyboardButton(f"{futures_check} Futures", callback_data="switch_futures"),
        ],
        [
            InlineKeyboardButton("📊 BTC", callback_data="price_BTC"),
            InlineKeyboardButton("📊 ETH", callback_data="price_ETH"),
            InlineKeyboardButton("📊 BNB", callback_data="price_BNB"),
        ],
        [
            InlineKeyboardButton("📊 SOL", callback_data="price_SOL"),
            InlineKeyboardButton("📊 XRP", callback_data="price_XRP"),
            InlineKeyboardButton("📊 DOGE", callback_data="price_DOGE"),
        ],
        [
            InlineKeyboardButton("📊 Tất cả coin", callback_data="price_ALL"),
        ],
        [
            InlineKeyboardButton("⏱ Báo giá tự động", callback_data="menu_alert"),
            InlineKeyboardButton("🛑 Dừng báo giá",   callback_data="stop_alert"),
        ],
        [
            InlineKeyboardButton("ℹ️ Hướng dẫn", callback_data="help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def alert_interval_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("⚡ 1 phút",  callback_data="alert_1"),
            InlineKeyboardButton("🕐 5 phút",  callback_data="alert_5"),
            InlineKeyboardButton("🕑 10 phút", callback_data="alert_10"),
        ],
        [
            InlineKeyboardButton("🕕 30 phút", callback_data="alert_30"),
            InlineKeyboardButton("🕐 1 giờ",   callback_data="alert_60"),
            InlineKeyboardButton("🕑 2 giờ",   callback_data="alert_120"),
        ],
        [InlineKeyboardButton("⬅️ Quay lại", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def coin_select_keyboard(interval: int):
    keyboard = [
        [
            InlineKeyboardButton("₿ BTC",  callback_data=f"set_BTC_{interval}"),
            InlineKeyboardButton("Ξ ETH",  callback_data=f"set_ETH_{interval}"),
            InlineKeyboardButton("◎ SOL",  callback_data=f"set_SOL_{interval}"),
        ],
        [
            InlineKeyboardButton("⬡ BNB",  callback_data=f"set_BNB_{interval}"),
            InlineKeyboardButton("◈ XRP",  callback_data=f"set_XRP_{interval}"),
            InlineKeyboardButton("✦ DOGE", callback_data=f"set_DOGE_{interval}"),
        ],
        [
            InlineKeyboardButton("🌐 Tất cả coin", callback_data=f"set_ALL_{interval}"),
        ],
        [InlineKeyboardButton("⬅️ Quay lại", callback_data="menu_alert")],
    ]
    return InlineKeyboardMarkup(keyboard)


def market_label(market: str) -> str:
    return "🔵 Futures" if market == MARKET_FUTURES else "🟡 Spot"


# ══════════════════════════════════════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    market  = chat_market.get(chat_id, MARKET_SPOT)
    status  = ""
    if chat_id in alert_jobs:
        info = alert_jobs[chat_id]
        coins_str = ", ".join(info["coins"])
        status = (
            f"\n\n🔔 <b>Đang báo giá:</b> {coins_str}\n"
            f"• Thị trường: {market_label(info['market'])}\n"
            f"• Mỗi <b>{info['interval']} phút</b>"
        )

    await update.message.reply_text(
        f"👋 <b>Chào mừng đến với Crypto Price Bot!</b>\n\n"
        f"🤖 Kết nối trực tiếp <b>Binance API</b> — realtime.\n"
        f"📈 Giá & % thay đổi <b>1 giờ</b> + 24h.\n"
        f"🔵🟡 Chọn <b>Spot</b> hoặc <b>Futures</b> tuỳ ý.\n"
        f"⏰ Báo giá tự động theo lịch của bạn."
        f"{status}",
        parse_mode="HTML",
        reply_markup=main_keyboard(chat_id)
    )


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args    = context.args
    symbol  = args[0].upper() if args else "BTC"
    market  = chat_market.get(chat_id, MARKET_SPOT)
    await send_price(update.message.reply_text, symbol, market)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in alert_jobs:
        info      = alert_jobs[chat_id]
        coins_str = ", ".join(info["coins"])
        text = (
            f"🔔 <b>Trạng thái báo giá</b>\n\n"
            f"• Coin: <b>{coins_str}</b>\n"
            f"• Thị trường: <b>{market_label(info['market'])}</b>\n"
            f"• Mỗi: <b>{info['interval']} phút</b>\n"
            f"• Chạy từ: <b>{info['started']}</b>\n\n"
            f"Dùng /stop để dừng."
        )
    else:
        text = "⭕ Chưa có báo giá nào đang chạy.\nDùng /start để thiết lập."
    await update.message.reply_text(text, parse_mode="HTML")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await do_stop_alert(chat_id, context, update.message.reply_text)


# ══════════════════════════════════════════════════════════════════════════════
#  PRICE FETCHING
# ══════════════════════════════════════════════════════════════════════════════

async def send_price(reply_fn, symbol: str, market: str):
    coins = SUPPORTED_COINS if symbol == "ALL" else (
        [symbol] if symbol in SUPPORTED_COINS else None
    )
    if coins is None:
        await reply_fn(
            f"❌ Coin <b>{symbol}</b> không được hỗ trợ.\nHỗ trợ: {', '.join(SUPPORTED_COINS)}",
            parse_mode="HTML"
        )
        return

    await reply_fn("⏳ Đang lấy dữ liệu từ Binance...", parse_mode="HTML")

    results = []
    for coin in coins:
        data = await get_price_change(coin, market)
        results.append(format_price_message(data) if data else f"❌ Không lấy được giá <b>{coin}</b>")

    now    = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    mlabel = market_label(market)
    header = f"📡 <b>Binance Realtime</b>  {mlabel}\n🕐 {now}\n{'─'*30}\n"
    await reply_fn(header + "\n".join(results), parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════════════
#  ALERT JOB
# ══════════════════════════════════════════════════════════════════════════════

async def alert_job_callback(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    if chat_id not in alert_jobs:
        return

    info    = alert_jobs[chat_id]
    coins   = info["coins"]
    market  = info["market"]
    results = []
    for coin in coins:
        data = await get_price_change(coin, market)
        results.append(format_price_message(data) if data else f"❌ Không lấy được giá <b>{coin}</b>")

    interval = info["interval"]
    mlabel   = market_label(market)
    now      = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    header   = (
        f"🔔 <b>Báo giá tự động</b>  {mlabel}  (mỗi {interval} phút)\n"
        f"🕐 {now}\n{'─'*30}\n"
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=header + "\n".join(results),
        parse_mode="HTML"
    )


async def do_start_alert(chat_id: int, interval: int, coins: list, market: str,
                          context: ContextTypes.DEFAULT_TYPE, reply_fn):
    if chat_id in alert_jobs:
        alert_jobs[chat_id]["job"].schedule_removal()

    job = context.job_queue.run_repeating(
        alert_job_callback,
        interval=interval * 60,
        first=5,
        chat_id=chat_id,
        name=f"alert_{chat_id}"
    )
    alert_jobs[chat_id] = {
        "job":     job,
        "interval": interval,
        "coins":   coins,
        "market":  market,
        "started": datetime.now().strftime("%H:%M %d/%m/%Y"),
    }

    coins_str = ", ".join(coins)
    await reply_fn(
        f"✅ <b>Đã bật báo giá tự động!</b>\n\n"
        f"• Coin: <b>{coins_str}</b>\n"
        f"• Thị trường: <b>{market_label(market)}</b>\n"
        f"• Tần suất: mỗi <b>{interval} phút</b>\n\n"
        f"Tin nhắn đầu tiên gửi sau ~5 giây.\nDùng /stop hoặc 🛑 để tắt.",
        parse_mode="HTML",
        reply_markup=main_keyboard(chat_id)
    )


async def do_stop_alert(chat_id: int, context: ContextTypes.DEFAULT_TYPE, reply_fn):
    if chat_id in alert_jobs:
        alert_jobs[chat_id]["job"].schedule_removal()
        del alert_jobs[chat_id]
        await reply_fn("🛑 <b>Đã dừng báo giá tự động.</b>", parse_mode="HTML",
                       reply_markup=main_keyboard(chat_id))
    else:
        await reply_fn("⭕ <b>Không có báo giá nào đang chạy.</b>", parse_mode="HTML",
                       reply_markup=main_keyboard(chat_id))


# ══════════════════════════════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════════════════════

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    data    = query.data
    chat_id = query.message.chat_id
    market  = chat_market.get(chat_id, MARKET_SPOT)

    async def edit(text, keyboard=None):
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)

    # ── Switch market ──────────────────────────────────────────────────────────
    if data == "switch_spot":
        chat_market[chat_id] = MARKET_SPOT
        await edit(
            f"🟡 <b>Đã chuyển sang SPOT</b>\n\nTất cả giá sẽ lấy từ thị trường Spot.",
            main_keyboard(chat_id)
        )

    elif data == "switch_futures":
        chat_market[chat_id] = MARKET_FUTURES
        await edit(
            f"🔵 <b>Đã chuyển sang FUTURES (Perpetual)</b>\n\n"
            f"Giá Futures + Funding Rate sẽ được hiển thị thêm.",
            main_keyboard(chat_id)
        )

    # ── Price views ────────────────────────────────────────────────────────────
    elif data.startswith("price_"):
        symbol = data.split("_")[1]
        coins  = SUPPORTED_COINS if symbol == "ALL" else [symbol]
        await edit(f"⏳ Đang lấy dữ liệu {market_label(market)}...")

        results = []
        for coin in coins:
            d = await get_price_change(coin, market)
            results.append(format_price_message(d) if d else f"❌ Không lấy được giá <b>{coin}</b>")

        now    = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        header = f"📡 <b>Binance Realtime</b>  {market_label(market)}\n🕐 {now}\n{'─'*30}\n"
        await edit(header + "\n".join(results), main_keyboard(chat_id))

    # ── Alert menu ─────────────────────────────────────────────────────────────
    elif data == "menu_alert":
        await edit(
            f"⏱ <b>Chọn tần suất báo giá</b>\n\n"
            f"Thị trường hiện tại: {market_label(market)}\n"
            f"(Đổi thị trường ở menu chính trước khi đặt lịch)",
            alert_interval_keyboard()
        )

    elif data.startswith("alert_"):
        interval = int(data.split("_")[1])
        await edit(
            f"🎯 <b>Tần suất: {interval} phút</b>  |  {market_label(market)}\n\nChọn coin:",
            coin_select_keyboard(interval)
        )

    elif data.startswith("set_"):
        parts    = data.split("_")
        coin     = parts[1]
        interval = int(parts[2])
        coins    = SUPPORTED_COINS if coin == "ALL" else [coin]

        if chat_id in alert_jobs:
            alert_jobs[chat_id]["job"].schedule_removal()

        job = context.job_queue.run_repeating(
            alert_job_callback,
            interval=interval * 60,
            first=5,
            chat_id=chat_id,
            name=f"alert_{chat_id}"
        )
        alert_jobs[chat_id] = {
            "job":      job,
            "interval": interval,
            "coins":    coins,
            "market":   market,
            "started":  datetime.now().strftime("%H:%M %d/%m/%Y"),
        }

        coins_str = ", ".join(coins)
        await edit(
            f"✅ <b>Đã bật báo giá tự động!</b>\n\n"
            f"• Coin: <b>{coins_str}</b>\n"
            f"• Thị trường: <b>{market_label(market)}</b>\n"
            f"• Tần suất: mỗi <b>{interval} phút</b>\n\n"
            f"Tin nhắn đầu tiên gửi sau ~5 giây.",
            main_keyboard(chat_id)
        )

    # ── Stop alert ─────────────────────────────────────────────────────────────
    elif data == "stop_alert":
        if chat_id in alert_jobs:
            alert_jobs[chat_id]["job"].schedule_removal()
            del alert_jobs[chat_id]
            await edit("🛑 <b>Đã dừng báo giá tự động.</b>", main_keyboard(chat_id))
        else:
            await edit("⭕ <b>Không có báo giá nào đang chạy.</b>", main_keyboard(chat_id))

    # ── Help ───────────────────────────────────────────────────────────────────
    elif data == "help":
        await edit(
            "📖 <b>Hướng dẫn sử dụng</b>\n\n"
            "<b>Lệnh:</b>\n"
            "• /start – Mở menu chính\n"
            "• /price BTC – Xem giá 1 coin\n"
            "• /price ALL – Xem tất cả coin\n"
            "• /status – Trạng thái báo giá\n"
            "• /stop – Dừng báo giá tự động\n\n"
            "<b>Thị trường:</b>\n"
            "• 🟡 <b>Spot</b> — giá giao ngay\n"
            "• 🔵 <b>Futures</b> — hợp đồng vĩnh viễn, có thêm Mark Price & Funding Rate\n\n"
            "<b>Coin hỗ trợ:</b>\n"
            f"{', '.join(SUPPORTED_COINS)}\n\n"
            "<b>Dữ liệu hiển thị:</b>\n"
            "• Giá hiện tại (USDT)\n"
            "• % thay đổi 1 giờ & 24h\n"
            "• Cao/thấp nhất 24h, Volume\n"
            "• (Futures) Mark Price, Funding Rate",
            main_keyboard(chat_id)
        )

    elif data == "back_main":
        status = ""
        if chat_id in alert_jobs:
            info = alert_jobs[chat_id]
            status = (
                f"\n\n🔔 Đang báo: <b>{', '.join(info['coins'])}</b>  "
                f"{market_label(info['market'])}  mỗi <b>{info['interval']} phút</b>"
            )
        await edit(f"🏠 <b>Menu chính</b>{status}", main_keyboard(chat_id))


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    token = os.environ.get("8287497174:AAF2nNaaYiWdSVe0IbKdL2dYFd54q35AGHw")
    if not token:
        raise ValueError("❌ Vui lòng set biến môi trường TELEGRAM_BOT_TOKEN")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("price",  price_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stop",   stop_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("🤖 Bot đang chạy...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
