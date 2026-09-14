"""Telepost Bot Configuration — loaded from environment variables."""
import os
from dataclasses import dataclass, field
from typing import List

def _env(name, default=""):
    v = os.getenv(name)
    if v is None:
        v = default
    v = v.strip()
    if v.lower() in ("not_configured", "none", "null"): return ""
    # Empty env value (e.g. an unset GitHub Actions secret arrives as "")
    # must not wipe the default — fall back to it.
    if not v and default:
        return default
    return v

@dataclass
class BotConfig:
    # Telegram
    BOT_TOKEN: str = field(default_factory=lambda: _env("BOT_TOKEN"))
    BOT_USERNAME: str = field(default_factory=lambda: _env("BOT_USERNAME", "telepostspace_bot"))
    OWNER_ID: int = field(default_factory=lambda: int(_env("OWNER_ID", "0") or 0))
    ADMIN_IDS: List[int] = field(default_factory=lambda: [int(x) for x in _env("ADMIN_IDS").replace(","," ").split() if x.isdigit()])

    # Channel
    CHANNEL_ID: str = field(default_factory=lambda: _env("CHANNEL_ID"))
    CHANNEL_USERNAME: str = field(default_factory=lambda: _env("CHANNEL_USERNAME", "telepost_space"))

    # Database
    DB_PATH: str = field(default_factory=lambda: _env("DB_PATH", "data/telepost.db"))

    # Cloudflare Workers AI
    CF_ACCOUNT_ID: str = field(default_factory=lambda: _env("CF_ACCOUNT_ID"))
    CF_API_TOKEN: str = field(default_factory=lambda: _env("CF_API_TOKEN"))
    CF_MODEL: str = field(default_factory=lambda: _env("CF_MODEL", "@cf/meta/llama-4-scout-17b-16e-instruct"))

    # Site URL (for links in posts)
    SITE_URL: str = field(default_factory=lambda: _env("SITE_URL", "https://telepost.space"))

    # Limits
    MAX_PHOTOS_PER_AD: int = field(default_factory=lambda: int(_env("MAX_PHOTOS_PER_AD", "8")))
    AD_EXPIRE_DAYS: int = field(default_factory=lambda: int(_env("AD_EXPIRE_DAYS", "30")))
    LOG_LEVEL: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))

    @property
    def BOT_HANDLE(self): return self.BOT_USERNAME.lstrip("@")

    def has_cf(self) -> bool:
        return bool(self.CF_ACCOUNT_ID and self.CF_API_TOKEN)

config = BotConfig()
