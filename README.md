# 💎 TON Price Live Telegram Bot

A production-ready, highly accurate Telegram bot providing verified real-time market valuations and conversions for **The Open Network (TON)** in:
- 🇺🇸 **USDT** (US Dollar Tether)
- 🇮🇳 **INR** (Indian Rupee with live FX rates and Indian numbering formatting)
- 🪙 **GRAM** (On-chain GRAM jetton via TonAPI and DEX pool rates)
- ⭐ **Telegram Stars** (Documented Telegram official developer monetization rate and Fragment purchase rates)

Built with **Python 3.11+**, `python-telegram-bot`, `websockets`, `httpx`, and `pydantic-settings`.

---

## 1. Project Overview

**TON Price Live** provides a clean, simple, and responsive English-language Telegram interface inspired by professional price bots like *DurovKursBot*, while uniquely supporting **INR**, **GRAM**, and **Telegram Stars**.

### Core Guarantees:
- **Zero hardcoded crypto prices:** All rates are calculated dynamically from live market data.
- **Zero fabricated values:** If an external feed fails, the bot reports the rate as unavailable rather than inventing data.
- **Clean English interface:** All buttons, messages, alerts, and instructions are presented in clear, natural English.
- **Sub-second accuracy:** Leverages TonAPI (the official TON indexed data engine) alongside WebSocket streaming and multi-tiered REST fallbacks.

---

## 2. Features

- 💎 **Clean Price Dashboard:** One-tap view showing 1 TON in USDT, INR, GRAM, and Telegram Stars.
- 💱 **Instant Conversions (Two Ways):**
  - **Natural Chat Messages:** Simply type any amount directly in chat (e.g., `1 TON`, `10 TON`, `100 INR`, `₹500`, `$50 USDT`, `1000 GRAM`, `100 STARS`, `50 ⭐`, or just `10`).
  - **Interactive Button Flow:** Tap `💱 Convert` to choose a currency and pick from quick preset buttons or type custom amounts.
- 🔄 **Smart In-Place Refresh:** Pressing `🔄 Refresh` updates live market data and edits the existing message in-place without notification spam.
- 🚦 **Rate Limiting & Cooldown:** 3-second cooldown on manual refreshes to protect against API abuse.
- 🪙 **Live GRAM Jetton Pricing:** Retrieves live DEX rates for the official GRAM jetton (`EQC47093oX5Xhb0xuk2lCr2RhS8rj-vul61u4W2UH5ORmG_O`) via TonAPI, STON.fi, and CoinGecko.
- ⭐ **Documented Telegram Stars Valuation:**
  - `telegram_official`: Uses the official Telegram Bot Platform developer monetization rate ($0.013 USD / Star).
  - `fragment`: Uses the Fragment direct purchase rate (~$0.016 USD / Star).
  - `custom`: Supports custom endpoint integrations.
  - Transparently configurable via `.env`.
- 🇮🇳 **Live INR Forex Conversion:** TON → USD/USDT → INR calculated via live forex feeds (`ExchangeRate-API`, `Frankfurter`), formatted with Indian numbering notation (e.g., `₹1,492.50`).
- 📡 **Multi-User Live Mode:** Live ticker mode with periodic auto-updating edits (5s default).
- 🐳 **Docker Ready:** Includes `Dockerfile` and `docker-compose.yml` for non-root, isolated deployment.

---

## 3. Visual Interface & Preview

### Main Price Dashboard (`/price` or 💎 TON Price)
```
💎 TON Price

1 TON = $1.55 USDT
1 TON = ₹149.25 INR
1 TON = 2,082.75 GRAM
1 TON = 119.23 Stars

Last updated: 09:15:00 UTC
🟢 Live market data

📊 Source: TonAPI (REST) + ExchangeRate-API

[ 🔄 Refresh ]  [ 💱 Convert ]
[ 📡 Live Price ] [ ℹ️ Help ]
[ 🔙 Main Menu ]
```

### Currency Conversion Example (`10 TON`)
```
💎 10 TON

≈ $15.50 USDT
≈ ₹1,492.50 INR
≈ 20,827.50 GRAM
≈ 1,192.30 Stars

[ 🔄 Refresh Rates ]  [ 💱 Convert Again ]
[ 💎 TON Price ]      [ 🔙 Main Menu ]
```

### Currency Conversion Example (`100 INR`)
```
🇮🇳 ₹100 INR

≈ 0.6700 TON
≈ $1.0385 USDT
≈ 1,395.44 GRAM
≈ 79.88 Stars

[ 🔄 Refresh Rates ]  [ 💱 Convert Again ]
[ 💎 TON Price ]      [ 🔙 Main Menu ]
```

---

## 4. Supported Commands

| Command | Description |
| :--- | :--- |
| `/start` | Open the welcome menu with navigation buttons |
| `/price` | Display the clean TON price dashboard |
| `/convert` | Open the interactive currency conversion menu |
| `/refresh` | Request an immediate live market refresh (rate-limited) |
| `/help` | Detailed guide on commands, conversions, and supported currencies |
| `/about` | Technical architecture, data providers, and rate transparency info |

Users can also type any amount directly in chat (e.g. `10 TON`, `100 INR`, `50 USDT`, `1000 GRAM`, `100 STARS`).

---

## 5. Architecture & Data Flow

```
                      ┌───────────────────────────────┐
                      │    TonAPI / WebSocket Feed    │
                      │  (Official TON Ecosystem API) │
                      └──────────────┬────────────────┘
                                     │ Live Crypto Ticker
                                     ▼
 ┌──────────────────────┐  ┌───────────────────────────┐      REST Fallbacks
 │  FX Exchange Rates   │  │     TONMarketService      │ ◄──────────────────────┐
 │ (ExchangeRate-API)   │  │   (In-Memory Streaming)   │   (CoinGecko / Binance)│
 └──────────┬───────────┘  └─────────────┬─────────────┘                        │
            │ USD/INR Rate               │ TON/USDT Rate                        │
            ▼                            ▼                                      │
 ┌─────────────────────────────────────────────────────┐                        │
 │                   PriceService                      │ ◄──────────────────────┤
 │  - Calculates TON/INR = TON/USDT * USD/INR          │                        │
 │  - Queries GramRateService (TonAPI / STON.fi DEX)   │                        │
 │  - Computes StarsRateService (Telegram Terms rate)  │                        │
 │  - Computes convert_currency() across all 5 assets  │                        │
 │  - Produces immutable, timestamped PriceSnapshot    │                        │
 └──────────────────────────┬──────────────────────────┘                        │
                            │                                                   │
                            ▼                                                   │
 ┌─────────────────────────────────────────────────────┐                        │
 │                 Telegram Handlers                   │                        │
 │  - Command Handlers (/start, /price, /convert, etc.)│                        │
 │  - MessageHandler (Direct text amount parsing)      │                        │
 │  - CallbackQueryHandler (Inline keyboards)          │                        │
 │  - UserRateLimiter (3-second cooldown)              │                        │
 └──────────────────────────┬──────────────────────────┘                        │
                            │                                                   │
                            ▼                                                   │
 ┌─────────────────────────────────────────────────────┐                        │
 │               End-User Telegram Client              │                        │
 └─────────────────────────────────────────────────────┘                        │
```

---

## 6. How Prices Are Calculated

1. **TON / USDT:**
   - **Primary:** `TonAPI` (`https://tonapi.io/v2/rates?tokens=ton&currencies=usd`). Aggregates DEX liquidity pools and major exchanges.
   - **Fallbacks:** `CoinGecko` and `Binance`.
2. **TON / INR:**
   - Sourced via `TON/USDT × USD/INR`.
   - `USD/INR` is fetched from `open.er-api.com` with hourly caching and fallbacks to `Frankfurter` (European Central Bank data) and `CoinGecko`.
3. **TON ↔ GRAM:**
   - Sourced from the official GRAM jetton contract (`EQC47093oX5Xhb0xuk2lCr2RhS8rj-vul61u4W2UH5ORmG_O`) on TON blockchain.
   - `TonAPI` indexes the live on-chain DEX pool pairs directly; fallback to `STON.fi` and `CoinGecko`.
4. **TON ↔ Telegram Stars:**
   - Grounded in Telegram's official Bot Monetization terms: 1 Star = $0.013 USD developer payout rate.
   - 1 TON = `TON/USDT / $0.013` Stars.
   - Can also be set to `fragment` (~$0.016 USD purchase rate) or a custom API endpoint in `.env`.

---

## 7. Environment Configuration

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

| Variable | Default | Description |
| :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | *(Required)* | Telegram bot token from @BotFather |
| `CRYPTO_API_PROVIDER` | `tonapi` | Crypto provider (`tonapi`, `binance`, `coingecko`, `whitebit`) |
| `CRYPTO_API_KEY` | `None` | Optional API key for crypto provider |
| `TON_SYMBOL` | `TON` | Base asset symbol |
| `TON_USDT_SYMBOL` | `TONUSDT` | Spot market pair symbol |
| `FX_API_PROVIDER` | `exchangerate-api` | FX provider (`exchangerate-api`, `frankfurter`, `coingecko`) |
| `FX_API_KEY` | `None` | Optional FX provider API key |
| `FX_CACHE_TTL_SECONDS` | `300` | In-memory cache duration for forex rates |
| `GRAM_CONTRACT_ADDRESS` | `EQC4...` | On-chain contract address for GRAM jetton |
| `GRAM_CACHE_TTL_SECONDS` | `60` | Cache duration for GRAM rates |
| `STARS_RATE_SOURCE` | `telegram_official`| Source for Stars rate (`telegram_official`, `fragment`, `custom`, `none`) |
| `STARS_USD_RATE` | `0.013` | Documented USD valuation per Telegram Star ($0.013) |
| `STARS_PER_TON` | `None` | Optional static override for Stars/TON |
| `STARS_CUSTOM_API_URL` | `None` | Optional custom endpoint URL for Stars |
| `LIVE_MODE_ENABLED` | `true` | Enable or disable live streaming mode |
| `LIVE_UPDATE_INTERVAL_SECONDS` | `5` | Message edit frequency during Live Mode (seconds) |
| `PRICE_STALE_AFTER_SECONDS` | `15` | Freshness threshold for market data (seconds) |
| `API_TIMEOUT_SECONDS` | `5.0` | Global HTTP timeout for external REST calls |
| `USER_REFRESH_COOLDOWN_SECONDS` | `3` | Cooldown period between manual user refreshes |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## 8. Local Setup & Installation

### Prerequisites
- Python 3.11 or higher
- Git

### Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/vanshDongrii/ton-price-tracker.git
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
4. Configure your `.env` file with your `TELEGRAM_BOT_TOKEN`.

---

## 9. Running the Bot

Run the application:
```bash
python -m src.main
```

Open Telegram and send `/start` or `/price` to your bot.

---

## 10. Automated Testing & Verification

### Run Full Test Suite:
```bash
pytest -v
```

### Run All 16 Requirement Verification Tests:
```bash
python scripts/test_all_requirements.py
```
This script tests:
1. `/start` command & welcome menu
2. `/help` command & user guide
3. `/price` dashboard output
4. TON live price retrieval
5. TON → USDT conversion
6. TON → INR conversion
7. TON → GRAM conversion
8. TON → Telegram Stars conversion
9. INR → TON conversion
10. USDT → TON conversion
11. Invalid amount handling & regex normalization
12. External API failure resilience
13. Refresh button in-place message edit
14. Rapid refresh cooldown / rate limiting
15. Clean startup and shutdown lifecycle
16. Resilience with missing API keys

### Verify Live Feeds & Conversions Interactively:
```bash
python scripts/verify_live.py
```

---

## 11. Deployment

### Using Docker Compose
```bash
docker compose up -d --build
```

### Viewing Logs
```bash
docker compose logs -f
```
