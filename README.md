# 💎 TON Price Tracker Telegram Bot

A production-ready, highly resilient Telegram bot that provides verified, real-time market valuations for **Toncoin (TON)** in:
- 🇺🇸 **USDT** (US Dollar Tether)
- 🇮🇳 **INR** (Indian Rupee with Indian number formatting)
- ⭐ **Telegram Stars** (Honest rate tracking with zero fabrication)

Built with **Python 3.11+**, `python-telegram-bot`, `websockets`, `httpx`, and `pydantic-settings`.

---

## 1. Project Overview

The **TON Price Tracker** delivers streaming market data directly to Telegram users without hardcoded rates, stale mock data, or fabricated currency valuations. It uses a high-performance streaming architecture that prioritizes an in-memory WebSocket ticker stream, automatically switches to REST fallback endpoints if network interruptions occur, and throttles message updates to comply with Telegram API rate limits.

---

## 2. Features

- ⚡ **Real-Time WebSocket Feed:** Direct streaming trades from exchange WebSocket endpoints into memory.
- 🔄 **Automatic REST Fallback:** Immediate, seamless fallback to Binance and CoinGecko REST endpoints if WebSocket connectivity is lost.
- 🔁 **Exponential Backoff Reconnection:** Resilient background reconnects (1s, 2s, 4s, 8s, 16s... up to 32s).
- 🇮🇳 **Live TON → INR Calculation:** Live `TON/USDT × USD/INR` computation with proper Indian number formatting (e.g. `₹1,23,456.78`).
- ⭐ **Honest Telegram Stars Handling:** Dedicated `StarsRateService` that never invents or guesses a floating market rate for Stars, displaying `⭐ Stars: Rate unavailable` unless an authenticated live conversion feed is provided.
- 📡 **Multi-User Live Mode:** Users can turn on Live Price streaming that edits an existing message in-place every 5 seconds (configurable) without notification spam.
- 🛡 **Telegram Message Throttling:** Edits are throttled and only dispatched if the displayed text has actually changed, preventing Telegram API bans.
- 🚦 **Per-User Rate Limiting:** 3-second cooldown on manual `/refresh` commands to prevent user abuse.
- 🟢 **Data Freshness Indicators:** Real-time data classification:
  - 🟢 **Live market data** (< 15s)
  - 🟡 **Data delayed** (>= 15s)
  - 🔴 **Price unavailable** (Feed offline)
- 🕐 **Indian Standard Time (IST):** All timestamps are converted to `Asia/Kolkata` for clear readability.
- 🐳 **Docker Ready:** Secure containerization running as an unprivileged non-root user with automated healthcheck.

---

## 3. Visual Interface & Preview

### Current Price Screen (`/price` or 💰 Current Price)
```
💎 TON Current Price

━━━━━━━━━━━━━━━━━━

🇺🇸 1 TON = $1.7730 USDT

🇮🇳 1 TON ≈ ₹170.32

⭐ Stars: Rate unavailable

━━━━━━━━━━━━━━━━━━

🟢 Live market data
🕐 Updated: 30 Sep 2026, 03:50:50 PM IST

📊 Source: Whitebit (WS) + ExchangeRate-API (WebSocket)

[ 🔄 Refresh ]  [ 📡 Live Price ]
[ ℹ️ About ]    [ 🔙 Main Menu ]
```

### Live Mode Screen (📡 Live Price)
```
💎 TON Live Price

🇺🇸 USDT: $1.7730
🇮🇳 INR: ₹170.32
⭐ Stars: Rate unavailable

🟢 LIVE

Updated: 03:50:50 PM IST

[ ⏹ Stop Live Updates ]
```

---

## 4. Architecture

```
                    ┌────────────────────────┐
                    │ Crypto Market Data WS  │
                    │   (WhiteBIT / Binance) │
                    └───────────┬────────────┘
                                │ Live Ticker
                                ▼
                    ┌────────────────────────┐      REST Fallback
                    │   TONMarketService     │ ◄──────────────────────┐
                    │  (In-Memory Stream)    │   (Binance / CoinGecko)│
                    └───────────┬────────────┘                        │
                                │                                     │
┌──────────────────────┐        │                                     │
│  FX Exchange Rates   │        │                                     │
│ (ExchangeRate-API)   │        │                                     │
└──────────┬───────────┘        │                                     │
           │ USD/INR Rate       │                                     │
           ▼                    ▼                                     │
┌────────────────────────────────────────────┐                        │
│                PriceService                │                        │
│  - Calculates TON * USD/INR                │                        │
│  - Queries StarsRateService                │                        │
│  - Validates freshness (<15s)              │                        │
│  - Produces immutable PriceSnapshot        │                        │
└─────────────────────┬──────────────────────┘                        │
                      │                                               │
                      ▼                                               │
┌────────────────────────────────────────────┐                        │
│              Telegram Handlers             │                        │
│  - /start, /price, /refresh, /help, /about │                        │
│  - UserRateLimiter (3s cooldown)           │                        │
│  - LiveModeManager (Per-user live tasks)   │                        │
└─────────────────────┬──────────────────────┘                        │
                      │                                               │
                      ▼                                               │
┌────────────────────────────────────────────┐                        │
│            End-User Telegram Client        │                        │
└────────────────────────────────────────────┘                        │
```

---

## 5. Supported Commands

| Command | Description |
| :--- | :--- |
| `/start` | Open the main welcome menu with interactive navigation buttons |
| `/price` | Display the latest market snapshot in USDT, INR, and Stars |
| `/refresh` | Request an immediate live market refresh (rate-limited to 1 every 3s) |
| `/help` | Detailed guide on commands, live updates, and data freshness |
| `/about` | Technical details regarding architecture, data feeds, and Stars policy |

---

## 6. API Providers

| Category | Primary Provider | Fallback Provider | Authentication Required |
| :--- | :--- | :--- | :--- |
| **TON/USDT WebSocket** | WhiteBIT (`wss://api.whitebit.com/ws`) | Binance (`wss://stream.binance.com:9443/ws`) | ❌ No API key required |
| **TON/USDT REST** | Binance Public REST API | CoinGecko Public REST API | ❌ No API key required |
| **USD/INR FX** | ExchangeRate-API (Open endpoint) | Frankfurter (ECB rates) / CoinGecko | ❌ No API key required |
| **Telegram Stars** | Dedicated `StarsRateService` | Returns `Rate unavailable` unless configured | Configurable |

---

## 7. Creating a Telegram Bot with BotFather

1. Open Telegram and search for `@BotFather`.
2. Start the chat and send `/newbot`.
3. Choose a display name (e.g. `TON Price Tracker`).
4. Choose a username ending in `bot` (e.g. `ton_price_tracker_live_bot`).
5. Copy the generated API token (format: `123456789:ABCdefGHIjklMNOpqrSTUvwxYZ`).
6. Set this token as `TELEGRAM_BOT_TOKEN` in your `.env` file.

---

## 8. Obtaining API Keys

The default configuration is **100% plug-and-play** and uses open, high-liquidity market feeds without requiring paid accounts or API keys:
- **WhiteBIT & Binance:** Open public spot tickers for `TONUSDT`.
- **ExchangeRate-API:** Open daily/hourly USD/INR forex endpoint (`open.er-api.com`).
- **CoinGecko:** Public rate fallback.

If you wish to configure a private exchange account or custom Stars endpoint, enter the optional keys in `.env`.

---

## 9. Environment Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

| Variable | Default | Description |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | *(Required)* | Telegram bot token from @BotFather |
| `CRYPTO_API_PROVIDER` | `whitebit` | Primary crypto provider (`whitebit`, `binance`, `coingecko`) |
| `CRYPTO_API_KEY` | `None` | Optional API key for crypto provider |
| `TON_SYMBOL` | `TON` | Base asset symbol |
| `TON_USDT_SYMBOL` | `TONUSDT` | Spot market pair symbol |
| `FX_API_PROVIDER` | `exchangerate-api` | FX provider (`exchangerate-api`, `frankfurter`, `coingecko`) |
| `FX_API_KEY` | `None` | Optional FX provider API key |
| `FX_CACHE_TTL_SECONDS` | `300` | In-memory cache duration for forex rates |
| `STARS_RATE_SOURCE` | `none` | Stars rate provider (`none`, `fragment`, `custom`) |
| `STARS_RATE_API_KEY` | `None` | Optional API key for Stars provider |
| `STARS_CUSTOM_API_URL` | `None` | Custom endpoint for Stars conversion |
| `LIVE_MODE_ENABLED` | `true` | Enable or disable live streaming updates |
| `LIVE_UPDATE_INTERVAL_SECONDS` | `5` | Message edit frequency during Live Mode (seconds) |
| `PRICE_STALE_AFTER_SECONDS` | `15` | Freshness threshold for market data (seconds) |
| `API_TIMEOUT_SECONDS` | `5.0` | Global HTTP timeout for external REST calls |
| `USER_REFRESH_COOLDOWN_SECONDS` | `3` | Cooldown period between manual user refreshes |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## 10. Local Installation

### Prerequisites
- Python 3.11 or higher
- Git

### Steps
1. Clone the repository:
   ```bash
   git clone <repository_url>
   cd ton-price-tracker
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## 11. Running the Bot

1. Ensure your `.env` file exists with your `TELEGRAM_BOT_TOKEN`.
2. Start the bot:
   ```bash
   python -m src.main
   ```
3. Open Telegram and message your bot (`/start`).

---

## 12. Testing

The repository contains an automated test suite with **100% mocked external APIs** that executes in under 3 seconds:

Run all tests:
```bash
pytest -v
```

Verify live market data retrieval (standalone integration verification):
```bash
python scripts/verify_live.py
```

---

## 13. Docker Deployment

### Using Docker Compose (Recommended)
```bash
# Build and run in background
docker compose up -d --build

# View real-time logs
docker compose logs -f

# Stop container
docker compose down
```

### Using Plain Docker
```bash
# Build image
docker build -t ton-price-tracker:latest .

# Run container
docker run -d --name ton_price_tracker --env-file .env ton-price-tracker:latest
```

---

## 14. Production Deployment

### Option A: Railway
1. Fork or push this repository to GitHub.
2. Log into [Railway.app](https://railway.app) and select **New Project** → **Deploy from GitHub repo**.
3. In **Variables**, add `TELEGRAM_BOT_TOKEN` and any optional configuration.
4. Deploy. The Dockerfile is automatically recognized and started.

### Option B: Render (Background Worker)
1. In [Render Dashboard](https://render.com), click **New +** → **Background Worker**.
2. Select your repository.
3. Select Environment: **Docker**.
4. Under **Environment Variables**, add `TELEGRAM_BOT_TOKEN`.
5. Click **Create Background Worker**.

### Option C: Fly.io
1. Install flyctl: `curl -L https://fly.io/install.sh | sh`
2. Run `fly launch` and select existing Dockerfile.
3. Set your secret: `fly secrets set TELEGRAM_BOT_TOKEN="your_token"`
4. Deploy: `fly deploy`

### Option D: Ubuntu / Debian VPS
1. Install Docker:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
   ```
2. Clone repo and create `.env`.
3. Start service:
   ```bash
   sudo docker compose up -d
   ```

---

## 15. WebSocket Architecture

The bot connects to an exchange WebSocket feed using an asynchronous persistent loop.
- **Single Connection Multiplexing:** One centralized WebSocket connection feeds price data into the shared `PriceService`. Whether 1 user or 10,000 users are using the bot, only **one single market connection** is maintained, preventing IP rate limits.
- **Ping / Pong Heartbeat:** Pings are exchanged every 20 seconds to prevent silent socket dropouts.
- **Immediate In-Memory Snapshot:** Every trade or ticker frame updates the memory store instantly.

---

## 16. REST Fallback

If the WebSocket stream encounters any network latency or connection drops:
1. `TONMarketService` detects that the WebSocket connection is down or the cached tick is older than `PRICE_STALE_AFTER_SECONDS` (15s).
2. The service immediately triggers the REST fallback:
   - Primary: Binance REST endpoint (`https://api.binance.com/api/v3/ticker/price?symbol=TONUSDT`).
   - Secondary: CoinGecko REST endpoint (`https://api.coingecko.com/api/v3/simple/price`).
3. Parallel user requests are deduplicated using a 2-second cache lock to avoid firing redundant requests during network reconnection.
4. Meanwhile, the WebSocket client executes exponential backoff to restore the live stream. Once re-established, the bot automatically switches back to WebSocket streaming.

---

## 17. TON → INR Calculation

Calculated dynamically on every snapshot:
$$\text{TON/INR} = \text{TON/USDT} \times \text{USD/INR}$$

- Sourced from live forex providers (ExchangeRate-API / Frankfurter / CoinGecko).
- Freshness tracking: If either the TON price or the FX rate is delayed, the INR price is flagged with `_(delayed FX)_` or `🟡 Data delayed`.
- Formatted with Indian numeral grouping (e.g. `₹1,23,456.78`).

---

## 18. Telegram Stars Limitations & Honest Handling

**Why are Telegram Stars treated separately?**
- Telegram Stars are an in-app digital product sold by Telegram for microtransactions and bot interactions.
- Unlike cryptocurrencies (TON, BTC) or fiat currencies (USD, INR), Telegram Stars do not trade on open, free-floating cryptocurrency order books.
- **Data Integrity Guarantee:** In strict adherence to honest data reporting, this bot **never fabricates, guesses, or hardcodes** a conversion rate.
- If no live authenticated provider is configured, the bot displays:
  ```
  ⭐ Stars: Rate unavailable
  ```
- The `StarsRateService` is fully modular: if Telegram or Fragment publishes an open live rate API, it can be plugged in via `.env` without modifying core pricing logic.

---

## 19. Data Freshness Policy

Every data snapshot records the UTC timestamp when the quote was minted:
- 🟢 **Live market data:** Ticker timestamp is within `PRICE_STALE_AFTER_SECONDS` (15 seconds).
- 🟡 **Data delayed:** Network blip or exchange latency exceeded 15 seconds.
- 🔴 **Price unavailable:** Both WebSocket and REST fallback endpoints are unreachable.

---

## 20. Security & Privacy

- **Zero Secret Leakage:** Sensitive tokens and keys are automatically masked from all logs via `SensitiveDataFilter`.
- **No User Tracking:** User state is kept purely in volatile memory for live task management; no personal chat history is stored.
- **Non-Root Container:** Docker container runs under UID `10001` (`appuser`).
- **Telegram Formatting Protection:** All user strings and Markdown templates are escaped.

---

## 21. Troubleshooting

### Problem: Bot does not respond to `/start`
- **Solution:** Verify `TELEGRAM_BOT_TOKEN` in `.env`. Ensure no trailing spaces or quotes around the token. Check logs with `docker compose logs -f` or console output.

### Problem: Telegram message doesn't update every second in Live Mode
- **Solution:** Telegram restricts bots from sending rapid bursts of edits to avoid UI lag and server bans. Live Mode throttles updates to 5-second intervals and skips edits if the price has not changed.

### Problem: `Too Many Requests` error from Telegram
- **Solution:** Ensure you are not running multiple instances of the bot with the same token. `LiveModeManager` enforces a single background task per chat ID.

---

## 📄 License
MIT License. Open-source and free for commercial and non-commercial use.
