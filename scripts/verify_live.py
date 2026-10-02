"""Live verification script demonstrating real-time market data retrieval."""

import asyncio
import os
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.bot.messages import (
    format_conversion_message,
    format_current_price_message,
    format_live_price_message,
)
from src.logging_config import setup_logging
from src.services.price_service import PriceService


async def verify():
    setup_logging("INFO")
    print("=" * 60)
    print(" Verifying TON Price Live Market Data Feed & Conversions")
    print("=" * 60)

    service = PriceService()
    await service.start()
    print("Connecting to live feeds...")

    # Wait 2 seconds for initial ticks
    await asyncio.sleep(2.0)

    print("\n[1] Fetching live price snapshot...")
    snapshot = await service.get_snapshot(force_refresh=False)

    print("\n--- FORMATTED CURRENT PRICE SCREEN ---")
    print(format_current_price_message(snapshot))

    print("\n--- FORMATTED LIVE MODE SCREEN ---")
    print(format_live_price_message(snapshot))

    print("\n[2] Snapshot attributes:")
    print(f"  • TON/USDT: {snapshot.ton_usdt}")
    print(f"  • USD/INR:  {snapshot.usd_inr}")
    print(f"  • TON/INR:  {snapshot.ton_inr}")
    print(f"  • GRAM:     {snapshot.ton_gram}")
    print(f"  • Stars:    {snapshot.ton_stars}")
    print(f"  • Source:   {snapshot.source}")
    print(f"  • Feed:     {snapshot.feed_type}")
    print(f"  • Status:   {snapshot.get_overall_freshness().badge}")

    print("\n[3] Testing Conversions:")
    for test_amt, test_curr in [(1.0, "TON"), (10.0, "TON"), (100.0, "INR"), (10.0, "USDT"), (1000.0, "GRAM"), (100.0, "STARS")]:
        conv = service.convert_currency(test_amt, test_curr, snapshot)
        print(f"\n--- Conversion for {test_amt} {test_curr} ---")
        print(format_conversion_message(test_amt, test_curr, conv))

    print("\n[4] Shutting down services cleanly...")
    await service.stop()
    print("SUCCESS: Live verification completed cleanly.")


if __name__ == "__main__":
    asyncio.run(verify())
