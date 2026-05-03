"""
Binance public REST API — no API key required for market data.

Spot    base: https://api.binance.com
  • GET /api/v3/ticker/24hr   → 24h stats
  • GET /api/v3/klines        → candlesticks (1h change)

Futures base: https://fapi.binance.com
  • GET /fapi/v1/ticker/24hr  → 24h stats
  • GET /fapi/v1/klines       → candlesticks (1h change)
  • GET /fapi/v1/premiumIndex → mark price + funding rate
"""

from __future__ import annotations

import aiohttp
import asyncio
from datetime import datetime, timezone

SPOT_BASE    = "https://api3.binance.com"
FUTURES_BASE = "https://fapi.binance.com"

SUPPORTED_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "DOT", "MATIC"]

MARKET_SPOT    = "spot"
MARKET_FUTURES = "futures"


async def _get(session: aiohttp.ClientSession, base: str, path: str, params: dict = None):
    url = base + path
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            print(f"[Binance API {resp.status}] {url}: {text[:200]}")
            return None
    except Exception as e:
        print(f"[Binance API error] {url}: {e}")
        return None


async def get_price_change(symbol: str, market: str = MARKET_SPOT) -> dict | None:
    """
    Returns a dict with price info. `market` is either 'spot' or 'futures'.
    Futures adds: funding_rate, mark_price.
    """
    ticker = f"{symbol}USDT"
    is_futures = (market == MARKET_FUTURES)
    base        = FUTURES_BASE if is_futures else SPOT_BASE
    stats_path  = "/fapi/v1/ticker/24hr" if is_futures else "/api/v3/ticker/24hr"
    klines_path = "/fapi/v1/klines"      if is_futures else "/api/v3/klines"

    async with aiohttp.ClientSession() as session:
        # 1. 24h stats
        stats = await _get(session, base, stats_path, {"symbol": ticker})
        if not stats:
            return None

        # 2. 1h kline for % change in last hour
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        one_hour_ago_ms = now_ms - 3_600_000
        klines = await _get(session, base, klines_path, {
            "symbol":    ticker,
            "interval":  "1h",
            "startTime": one_hour_ago_ms - 60_000,
            "limit":     2,
        })

        price_1h_ago = None
        if klines and len(klines) >= 1:
            price_1h_ago = float(klines[0][1])

        current_price = float(stats["lastPrice"])
        change_1h_pct = None
        if price_1h_ago and price_1h_ago > 0:
            change_1h_pct = ((current_price - price_1h_ago) / price_1h_ago) * 100

        result = {
            "symbol":         symbol,
            "market":         market,
            "price":          current_price,
            "change_1h_pct":  change_1h_pct,
            "price_1h_ago":   price_1h_ago,
            "high_24h":       float(stats["highPrice"]),
            "low_24h":        float(stats["lowPrice"]),
            "volume_24h":     float(stats["volume"]),
            "change_24h_pct": float(stats["priceChangePercent"]),
        }

        # 3. Futures-only extras: funding rate + mark price
        if is_futures:
            premium = await _get(session, base, "/fapi/v1/premiumIndex", {"symbol": ticker})
            if premium:
                result["funding_rate"] = float(premium.get("lastFundingRate", 0)) * 100
                result["mark_price"]   = float(premium.get("markPrice", current_price))
            else:
                result["funding_rate"] = None
                result["mark_price"]   = current_price

        return result


def format_price_message(data: dict) -> str:
    sym     = data["symbol"]
    market  = data.get("market", MARKET_SPOT)
    price   = data["price"]
    h24_pct = data["change_24h_pct"]
    h1_pct  = data["change_1h_pct"]
    high    = data["high_24h"]
    low     = data["low_24h"]
    vol     = data["volume_24h"]

    is_futures   = (market == MARKET_FUTURES)
    market_label = "🔵 <b>FUTURES</b>" if is_futures else "🟡 <b>SPOT</b>"

    def arrow(pct):
        if pct is None: return "❔"
        return "🟢📈" if pct >= 0 else "🔴📉"

    def fmt_pct(pct):
        if pct is None: return "N/A"
        return f"{'+' if pct >= 0 else ''}{pct:.2f}%"

    def fmt_price(p):
        if p >= 1000:  return f"${p:,.2f}"
        elif p >= 1:   return f"${p:.4f}"
        else:          return f"${p:.6f}"

    def fmt_vol(v):
        if v >= 1_000_000: return f"{v/1_000_000:.2f}M"
        elif v >= 1_000:   return f"{v/1_000:.2f}K"
        return f"{v:.2f}"

    lines = [
        f"<b>{'─'*28}</b>",
        f"💎 <b>{sym}/USDT</b>  {market_label}",
        f"💵 Giá: <b>{fmt_price(price)}</b>",
        f"⏱ 1 giờ:   {arrow(h1_pct)} <b>{fmt_pct(h1_pct)}</b>",
        f"📅 24h:     {arrow(h24_pct)} <b>{fmt_pct(h24_pct)}</b>",
        f"⬆️ Cao 24h: {fmt_price(high)}",
        f"⬇️ Thấp 24h: {fmt_price(low)}",
        f"📦 Vol 24h: {fmt_vol(vol)} {sym}",
    ]

    if is_futures:
        mark = data.get("mark_price")
        fr   = data.get("funding_rate")
        if mark:
            lines.append(f"🏷 Mark Price: {fmt_price(mark)}")
        if fr is not None:
            lines.append(f"💸 Funding Rate: {'🟢' if fr >= 0 else '🔴'} {fr:+.4f}%")

    return "\n".join(lines)


if __name__ == "__main__":
    async def test():
        print("=== SPOT ===")
        d = await get_price_change("BTC", MARKET_SPOT)
        if d: print(format_price_message(d))
        print("\n=== FUTURES ===")
        d = await get_price_change("BTC", MARKET_FUTURES)
        if d: print(format_price_message(d))
    asyncio.run(test())
