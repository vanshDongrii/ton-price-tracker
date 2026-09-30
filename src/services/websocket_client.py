"""Asynchronous WebSocket client with exponential backoff and automatic reconnection."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional
import websockets

logger = logging.getLogger(__name__)

PriceCallback = Callable[[float, datetime, str], Awaitable[None]]


class CryptoWebSocketClient:
    """Manages WebSocket connection to crypto market ticker streams."""

    def __init__(
        self,
        provider: str = "whitebit",
        symbol_pair: str = "TONUSDT",
        on_price_update: Optional[PriceCallback] = None,
        initial_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 32.0,
        ping_interval: float = 20.0,
        open_timeout: float = 5.0,
    ):
        self.provider = provider.lower()
        self.symbol_pair = symbol_pair.upper()
        self.on_price_update = on_price_update
        self.initial_backoff = initial_backoff_seconds
        self.max_backoff = max_backoff_seconds
        self.ping_interval = ping_interval
        self.open_timeout = open_timeout

        self._running = False
        self._connected = False
        self._task: Optional[asyncio.Task] = None
        self._current_ws = None
        self._last_tick_time: Optional[datetime] = None

    @property
    def is_connected(self) -> bool:
        """Return True if WebSocket connection is currently active."""
        return self._connected

    @property
    def last_tick_time(self) -> Optional[datetime]:
        """Return the timestamp of the last received price tick."""
        return self._last_tick_time

    def start(self) -> None:
        """Start the background WebSocket listening loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="ws-market-feed")
        logger.info("WebSocket feed started for provider: %s", self.provider)

    async def stop(self) -> None:
        """Gracefully stop WebSocket connection and background loop."""
        logger.info("Stopping WebSocket feed for provider: %s", self.provider)
        self._running = False
        self._connected = False

        if self._current_ws is not None:
            try:
                await self._current_ws.close()
            except Exception as e:
                logger.debug("Error closing WebSocket connection: %s", e)
            self._current_ws = None

        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def _get_connection_config(self) -> tuple[str, Optional[dict]]:
        """Return (ws_url, subscribe_payload) for the configured provider."""
        if self.provider == "whitebit":
            url = "wss://api.whitebit.com/ws"
            sub = {
                "id": 1,
                "method": "lastprice_subscribe",
                "params": ["TON_USDT"],
            }
            return url, sub

        if self.provider == "binance":
            # Direct trade stream for TONUSDT
            url = "wss://stream.binance.com:9443/ws/tonusdt@trade"
            return url, None

        # Default fallback
        url = "wss://api.whitebit.com/ws"
        sub = {
            "id": 1,
            "method": "lastprice_subscribe",
            "params": ["TON_USDT"],
        }
        return url, sub

    def _parse_message(self, message: str) -> Optional[tuple[float, datetime]]:
        """Parse raw incoming WebSocket frame into (price, timestamp_utc)."""
        try:
            data = json.loads(message)
        except Exception:
            return None

        now_utc = datetime.now(timezone.utc)

        # WhiteBIT format: {"method": "lastprice_update", "params": ["TON_USDT", "1.773"]}
        if self.provider == "whitebit" or "params" in data:
            if data.get("method") == "lastprice_update" and isinstance(data.get("params"), list):
                params = data["params"]
                if len(params) >= 2:
                    try:
                        price = float(params[1])
                        return price, now_utc
                    except (ValueError, TypeError):
                        pass

        # Binance format: {"e": "trade", "s": "TONUSDT", "p": "1.773", "T": 1727690000000}
        if "p" in data and ("s" in data or "e" in data):
            try:
                price = float(data["p"])
                # Use exchange timestamp if available
                if "T" in data and isinstance(data["T"], (int, float)):
                    ts = datetime.fromtimestamp(data["T"] / 1000.0, tz=timezone.utc)
                elif "E" in data and isinstance(data["E"], (int, float)):
                    ts = datetime.fromtimestamp(data["E"] / 1000.0, tz=timezone.utc)
                else:
                    ts = now_utc
                return price, ts
            except (ValueError, TypeError):
                pass

        # Binance ticker format: {"c": "1.773"}
        if "c" in data:
            try:
                price = float(data["c"])
                return price, now_utc
            except (ValueError, TypeError):
                pass

        return None

    async def _run_loop(self) -> None:
        """Main execution loop with exponential backoff reconnection."""
        backoff = self.initial_backoff

        while self._running:
            url, sub_payload = self._get_connection_config()
            logger.info("Connecting to WebSocket: %s", url)

            try:
                async with websockets.connect(
                    url,
                    open_timeout=self.open_timeout,
                    ping_interval=self.ping_interval,
                ) as ws:
                    self._current_ws = ws
                    self._connected = True
                    logger.info("WebSocket connected successfully to %s", self.provider)

                    if sub_payload is not None:
                        await ws.send(json.dumps(sub_payload))
                        logger.debug("Sent subscription payload: %s", sub_payload)

                    # Successful connection: reset backoff
                    backoff = self.initial_backoff

                    # Message loop
                    while self._running:
                        try:
                            # 30 second receive timeout to detect zombie connections
                            raw_msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                        except asyncio.TimeoutError:
                            logger.warning("WebSocket receive timeout on %s, pinging...", self.provider)
                            # Send ping to verify connection liveness
                            pong_waiter = await ws.ping()
                            await asyncio.wait_for(pong_waiter, timeout=5.0)
                            continue

                        parsed = self._parse_message(raw_msg)
                        if parsed is not None:
                            price, ts = parsed
                            self._last_tick_time = ts
                            if self.on_price_update:
                                try:
                                    await self.on_price_update(price, ts, f"{self.provider.title()} (WS)")
                                except Exception as e:
                                    logger.error("Error in on_price_update callback: %s", e)

            except asyncio.CancelledError:
                logger.info("WebSocket loop cancelled")
                break
            except Exception as e:
                self._connected = False
                logger.warning(
                    "WebSocket disconnected/failed (%s: %s). Reconnecting in %.1fs...",
                    type(e).__name__,
                    e,
                    backoff,
                )

            self._connected = False
            self._current_ws = None

            if not self._running:
                break

            # Exponential backoff sleep before reconnecting
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, self.max_backoff)
