"""Configuration management for TON Price Tracker."""

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Bot
    telegram_bot_token: str = Field(
        default="",
        description="Telegram bot token obtained from @BotFather",
    )

    # Crypto Provider
    crypto_api_provider: str = Field(
        default="binance",
        description="Crypto provider for TON/USDT data (binance, whitebit, coingecko)",
    )
    crypto_api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for crypto market data provider",
    )
    ton_symbol: str = Field(
        default="TON",
        description="Base TON symbol",
    )
    ton_usdt_symbol: str = Field(
        default="TONUSDT",
        description="Market pair symbol for TON/USDT",
    )

    # FX Provider
    fx_api_provider: str = Field(
        default="exchangerate-api",
        description="FX provider for USD/INR exchange rates (exchangerate-api, frankfurter, coingecko)",
    )
    fx_api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for FX provider",
    )
    fx_cache_ttl_seconds: int = Field(
        default=300,
        description="Cache TTL in seconds for FX rates (default: 5 minutes)",
    )

    # Telegram Stars
    stars_rate_source: str = Field(
        default="none",
        description="Source for TON -> Stars rate (none, fragment, custom)",
    )
    stars_rate_api_key: Optional[str] = Field(
        default=None,
        description="Optional API key for Stars rate provider",
    )
    stars_custom_api_url: Optional[str] = Field(
        default=None,
        description="Optional endpoint URL if custom Stars source is configured",
    )

    # Live Mode & Behavior
    live_mode_enabled: bool = Field(
        default=True,
        description="Whether Live Mode updates are enabled",
    )
    live_update_interval_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Interval in seconds between Telegram live message edits (default: 5)",
    )
    price_stale_after_seconds: int = Field(
        default=15,
        ge=1,
        description="Threshold in seconds after which data is considered delayed/stale (default: 15)",
    )
    api_timeout_seconds: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="HTTP request timeout in seconds (default: 5.0)",
    )
    user_refresh_cooldown_seconds: int = Field(
        default=3,
        ge=1,
        le=30,
        description="Cooldown between manual user refreshes (default: 3 seconds)",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    @field_validator("crypto_api_provider", mode="before")
    @classmethod
    def normalize_crypto_provider(cls, v: str) -> str:
        return (v or "binance").strip().lower()

    @field_validator("fx_api_provider", mode="before")
    @classmethod
    def normalize_fx_provider(cls, v: str) -> str:
        return (v or "exchangerate-api").strip().lower()

    @field_validator("stars_rate_source", mode="before")
    @classmethod
    def normalize_stars_source(cls, v: str) -> str:
        return (v or "none").strip().lower()

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        return (v or "INFO").strip().upper()


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
