"""
Handlers — Menu navigasi & callback utama
Menangani semua callback_data yang dimulai dengan 'menu:'
"""

import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, URLInputFile

from config import BANNER_URL, DRAMAS_PER_PAGE
from keyboards.inline import (
    main_menu_keyboard,
    drama_list_keyboard,
    back_to_home_keyboard,
)
from services.api import fetch_dramas

router = Router(name="menu")
logger = logging.getLogger(__name__)


# ── Menu Home ──────────────────────────────────────────────


@router.callback_query(F.data == "menu:home")
async def cb_menu_home(callback: CallbackQuery) -> None:
    """Kembali ke menu utama."""
    logger.info("User %s → Menu Utama", callback.from_user.id)

    welcome_text = (
        "🎬 <b>Selamat datang kembali!</b>\n\n"
        "Yuk, lanjut nonton drama favoritmu sekarang! 🍿\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎭 <b>Dramaku</b> — Streaming Drama #1\n"
        "✨ Ribuan drama terbaru & terlengkap\n"
        "📱 Nonton kapan saja, di mana saja\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        banner = URLInputFile(BANNER_URL, filename="dramaku_banner.jpg")
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=banner,
            caption=welcome_text,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
    except Exception:
        try:
            await callback.message.edit_text(
                welcome_text,
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                welcome_text,
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(),
            )

    await callback.answer()


# ── Menu Drama List (paginated) ────────────────────────────


@router.callback_query(F.data.startswith("menu:dramas:"))
async def cb_menu_dramas(callback: CallbackQuery) -> None:
    """Menampilkan daftar drama — paginated dari API."""
    page = int(callback.data.split(":")[2])
    logger.info("User %s → Daftar Drama halaman %d", callback.from_user.id, page)
    await callback.answer("⏳ Memuat daftar drama...")

    result = await fetch_dramas(page=page, limit=DRAMAS_PER_PAGE)
    dramas = result["dramas"]
    total_pages = result["total_pages"]
    total = result["total"]

    if not dramas:
        try:
            await callback.message.edit_text(
                "😔 <b>Tidak ada drama tersedia saat ini.</b>\n\n"
                "Silakan coba lagi nanti.",
                parse_mode="HTML",
                reply_markup=back_to_home_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                "😔 <b>Tidak ada drama tersedia.</b>",
                parse_mode="HTML",
                reply_markup=back_to_home_keyboard(),
            )
        return

    text = (
        f"🎭 <b>Daftar Drama Populer</b>\n"
        f"📊 Total: <b>{total}</b> drama tersedia\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    for i, d in enumerate(dramas, (page - 1) * DRAMAS_PER_PAGE + 1):
        desc = d["description"]
        if len(desc) > 80:
            desc = desc[:80] + "..."
        text += (
            f"<b>{i}.</b> {d['title']}\n"
            f"    🎞 {d['total_episodes']} Episode\n"
            f"    📝 <i>{desc}</i>\n\n"
        )
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += "👇 <b>Pilih drama untuk melihat detail:</b>"

    keyboard = drama_list_keyboard(dramas, page=page, total_pages=total_pages)

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ── Menu VIP (Placeholder) ────────────────────────────────


@router.callback_query(F.data == "menu:vip")
async def cb_menu_vip(callback: CallbackQuery) -> None:
    """Placeholder untuk fitur VIP."""
    logger.info("User %s → Langganan VIP", callback.from_user.id)
    await callback.answer()

    text = (
        "👑 <b>Langganan VIP</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🥉 <b>Basic</b> — Rp 29.000/bulan\n"
        "   ✅ Akses 100+ drama\n"
        "   ✅ Kualitas 720p\n\n"
        "🥈 <b>Premium</b> — Rp 49.000/bulan\n"
        "   ✅ Akses semua drama\n"
        "   ✅ Kualitas 1080p\n"
        "   ✅ Tanpa iklan\n\n"
        "🥇 <b>Ultimate</b> — Rp 79.000/bulan\n"
        "   ✅ Semua fitur Premium\n"
        "   ✅ Download offline\n"
        "   ✅ Early access\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💳 <i>Pembayaran akan segera tersedia.</i>"
    )

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=back_to_home_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=back_to_home_keyboard(),
        )


# ── Menu Profil (Placeholder) ─────────────────────────────


@router.callback_query(F.data == "menu:profile")
async def cb_menu_profile(callback: CallbackQuery) -> None:
    """Placeholder untuk profil & afiliasi."""
    logger.info("User %s → Profil", callback.from_user.id)
    await callback.answer()

    user = callback.from_user
    text = (
        "👤 <b>Profil Kamu</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📛 Nama: <b>{user.full_name}</b>\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📱 Username: @{user.username or 'tidak ada'}\n"
        "📊 Status: <b>Free Member</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🤝 <b>Program Afiliasi</b>\n"
        f"🔗 Link referral:\n<code>https://t.me/dramaku_bot?start=ref_{user.id}</code>\n\n"
        "💰 Ajak teman, dapatkan bonus VIP gratis!"
    )

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=back_to_home_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=back_to_home_keyboard(),
        )


# ── NOOP (untuk tombol informasi) ─────────────────────────


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    """Tombol yang tidak melakukan apa-apa (misal: halaman info)."""
    await callback.answer()
