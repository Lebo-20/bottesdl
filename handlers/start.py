"""
Handlers — Command /start
"""

import logging

from aiogram import Router, F
from aiogram.types import Message, URLInputFile
from aiogram.filters import CommandStart, Command

from config import BANNER_URL
from keyboards.inline import main_menu_keyboard, melolo_menu_keyboard

router = Router(name="start")
logger = logging.getLogger(__name__)


@router.message(Command("start", "melolo"))
async def cmd_start(message: Message) -> None:
    """Handler untuk command /start."""
    logger.info("User %s memulai bot", message.from_user.id)

    welcome_text = (
        "🎬 <b>Selamat datang kembali!</b>\n\n"
        "Yuk, lanjut nonton drama favoritmu sekarang! 🍿\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎭 <b>Dramaku</b> — Streaming Drama #1\n"
        "✨ Ribuan drama terbaru & terlengkap\n"
        "📱 Nonton kapan saja, di mana saja\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    is_melolo = message.text.startswith("/melolo")
    keyboard = melolo_menu_keyboard() if is_melolo else main_menu_keyboard()

    if is_melolo:
        welcome_text = (
            "🎭 <b>Melolo Drama</b>\n\n"
            "Temukan drama terbaik khusus untukmu! ✨\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔥 Trending & Terbaru setiap hari\n"
            "🎬 Koleksi lengkap & update cepat\n"
            "🍿 Nonton nyaman tanpa ribet\n"
            "━━━━━━━━━━━━━━━━━━━━"
        )

    try:
        banner = URLInputFile(BANNER_URL, filename="dramaku_banner.jpg")
        await message.answer_photo(
            photo=banner,
            caption=welcome_text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception as e:
        logger.warning("Gagal kirim banner: %s — fallback ke teks", e)
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
