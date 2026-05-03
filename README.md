# 🤖 Crypto Price Telegram Bot

Bot Telegram theo dõi giá coin realtime từ **Binance API** (không cần API key).

## ✨ Tính năng

- 📊 Xem giá realtime BTC, ETH, BNB, SOL, XRP, DOGE, ADA, AVAX, DOT, MATIC
- ⏱ % thay đổi trong **1 giờ gần nhất** & 24h
- 🔔 Báo giá tự động: 1, 5, 10, 30, 60, 120 phút
- 🎯 Chọn từng coin hoặc theo dõi tất cả
- 🖱 Giao diện nút bấm inline keyboard tiện lợi

---

## 🚀 Cài đặt & Chạy

### Bước 1: Tạo bot Telegram

1. Mở Telegram, tìm **@BotFather**
2. Gửi `/newbot`
3. Đặt tên và username cho bot
4. Copy **Token** được cấp (dạng `123456:ABC-DEF...`)

### Bước 2: Cài thư viện

```bash
pip install -r requirements.txt
```

### Bước 3: Set token và chạy

**Linux / Mac:**
```bash
export TELEGRAM_BOT_TOKEN="your_token_here"
python bot.py
```

**Windows CMD:**
```cmd
set TELEGRAM_BOT_TOKEN=your_token_here
python bot.py
```

**Windows PowerShell:**
```powershell
$env:TELEGRAM_BOT_TOKEN="your_token_here"
python bot.py
```

---

## 🐳 Chạy bằng Docker

```bash
docker build -t crypto-bot .
docker run -d \
  --name crypto-bot \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN="your_token_here" \
  crypto-bot
```

---

## ☁️ Deploy lên VPS / Cloud (khuyên dùng)

Để bot chạy **24/7**, deploy lên:

### Railway (miễn phí, dễ nhất)
1. Tạo account tại https://railway.app
2. New Project → Deploy from GitHub
3. Thêm biến môi trường `TELEGRAM_BOT_TOKEN`
4. Done ✅

### Render.com
1. New → Web Service → Connect repo
2. Environment: `TELEGRAM_BOT_TOKEN = your_token`
3. Start command: `python bot.py`

### VPS (Ubuntu)
```bash
# Cài screen để chạy nền
sudo apt install screen -y
screen -S crypto-bot
export TELEGRAM_BOT_TOKEN="your_token"
python bot.py
# Ctrl+A D để thoát khỏi screen
```

---

## 📱 Lệnh bot

| Lệnh | Mô tả |
|------|-------|
| `/start` | Mở menu chính |
| `/price BTC` | Xem giá 1 coin |
| `/price ALL` | Xem tất cả coin |
| `/status` | Xem trạng thái báo giá |
| `/stop` | Dừng báo giá tự động |

---

## 📁 Cấu trúc file

```
crypto_bot/
├── bot.py          # Main bot logic, handlers
├── binance_api.py  # Binance REST API calls
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 🔧 Tùy chỉnh thêm coin

Mở `binance_api.py`, thêm vào danh sách:

```python
SUPPORTED_COINS = ["BTC", "ETH", "BNB", ..., "TEN_COIN_MỚI"]
```

Coin phải có cặp giao dịch `XXXUSDT` trên Binance.

---

## ⚠️ Lưu ý

- Bot dùng **Binance public API** → không cần tạo tài khoản hay API key
- Rate limit: ~1200 requests/phút (rất thoải mái cho cá nhân)
- Giá có thể chênh lệch vài giây so với realtime do latency mạng
