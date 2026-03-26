"""
Konfigurasi bot Dramaku.
Membaca variabel environment dari file .env
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ── Telegram API ──────────────────────────────────────────
API_ID: int = int(os.getenv("API_ID", "0"))
API_HASH: str = os.getenv("API_HASH", "")

# ── DotDrama API ──────────────────────────────────────────
API_BASE_URL: str = os.getenv(
    "API_BASE_URL",
    "https://captain.sapimu.au/dotdrama/api/v1",
)
API_TOKEN: str = os.getenv(
    "API_TOKEN",
    "5cf419a4c7fb1c8585314b9f797bf77e7b10a705f32c91aac65b901559780e12",
)

# ── Vigloo API ────────────────────────────────────────────
VIGLOO_BASE_URL: str = os.getenv(
    "VIGLOO_BASE_URL",
    "https://captain.sapimu.au/vigloo/api/v1",
)
VIGLOO_TOKEN: str = os.getenv(
    "VIGLOO_TOKEN",
    API_TOKEN,  # Default to API_TOKEN as it's from the same provider
)

# ── Pagination ────────────────────────────────────────────
DRAMAS_PER_PAGE: int = 5      # Drama per halaman di list
EPISODES_PER_PAGE: int = 12   # Episode per halaman di detail

# ── Links ─────────────────────────────────────────────────
GROUP_LINK: str = "https://t.me/dramaku_group"
ADMIN_USERNAME: str = "@dramaku_admin"

# ── Banner ────────────────────────────────────────────────
BANNER_URL: str = (
    "https://images.unsplash.com/photo-1616530940355-351fabd9524b"
    "?w=800&q=80"
)
