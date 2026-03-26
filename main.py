"""
Dramaku Bot — Main Entry Point
Telegram bot streaming drama menggunakan aiogram v3.
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import start, menu, drama
from handlers import search, vigloo, owner

# ╔══════════════════════════════════════════════════════════╗
# ║                     LOGGING                             ║
# ╚══════════════════════════════════════════════════════════╝

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("dramaku.log", encoding="utf-8"),
    ],
)

# Kurangi noise dari library
logging.getLogger("aiogram").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════╗
# ║                      MAIN                               ║
# ╚══════════════════════════════════════════════════════════╝


async def main() -> None:
    """Menjalankan bot."""

    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN tidak ditemukan! Pastikan file .env sudah benar.")
        sys.exit(1)

    # ── Inisialisasi Bot & Dispatcher ──
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # ── Register Routers ──
    dp.include_routers(
        start.router,
        search.router,
        menu.router,
        drama.router,
        vigloo.router,
        owner.router,
    )

    # ── Startup ──
    logger.info("🎬 Dramaku Bot dimulai!")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    try:
        # Hapus webhook lama jika ada, lalu mulai polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logger.info("🛑 Dramaku Bot berhenti.")
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot dihentikan oleh user.")
