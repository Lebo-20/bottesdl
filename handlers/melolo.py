"""
Handlers — Melolo API
Menangani navigasi untuk Melolo API.
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, URLInputFile, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.melolo import (
    fetch_melolo_foryou,
    fetch_melolo_latest,
    fetch_melolo_trending,
    fetch_melolo_search,
    fetch_melolo_detail,
    fetch_melolo_stream,
)
from keyboards.inline import (
    melolo_menu_keyboard,
    melolo_list_keyboard,
    back_to_home_keyboard,
)
from config import BANNER_URL

router = Router(name="melolo")
logger = logging.getLogger(__name__)

class MeloloSearchState(StatesGroup):
    waiting_for_query = State()

@router.callback_query(F.data == "melolo:home")
async def cb_melolo_home(callback: CallbackQuery) -> None:
    """Kembali ke menu Melolo."""
    logger.info("User %s → Menu Melolo", callback.from_user.id)
    
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
        await callback.message.edit_caption(
            caption=welcome_text,
            parse_mode="HTML",
            reply_markup=melolo_menu_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=melolo_menu_keyboard(),
        )
    await callback.answer()

@router.callback_query(F.data.startswith("melolo:foryou:"))
async def cb_melolo_foryou(callback: CallbackQuery) -> None:
    """Menampilkan drama For You Melolo."""
    offset = int(callback.data.split(":")[2])
    logger.info("User %s → Melolo For You offset %d", callback.from_user.id, offset)
    await callback.answer("⏳ Memuat drama untukmu...")

    dramas = await fetch_melolo_foryou(offset=offset)
    if not dramas:
        await callback.message.answer("😔 Tidak ada drama tersedia.")
        return

    text = "🎬 <b>Drama Untuk Anda (Melolo)</b>\n\n👇 Pilih drama:"
    keyboard = melolo_list_keyboard(dramas, offset=offset, nav_prefix="melolo:foryou:")
    
    await callback.message.edit_caption(
        caption=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )

@router.callback_query(F.data == "melolo:latest")
async def cb_melolo_latest(callback: CallbackQuery) -> None:
    """Menampilkan drama terbaru Melolo."""
    logger.info("User %s → Melolo Terbaru", callback.from_user.id)
    await callback.answer("⏳ Memuat drama terbaru...")

    dramas = await fetch_melolo_latest()
    if not dramas:
        await callback.message.answer("😔 Tidak ada drama terbaru.")
        return

    text = "✨ <b>Drama Terbaru (Melolo)</b>\n\n👇 Pilih drama:"
    keyboard = melolo_list_keyboard(dramas, has_more=False)
    
    await callback.message.edit_caption(
        caption=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )

@router.callback_query(F.data == "melolo:trending")
async def cb_melolo_trending(callback: CallbackQuery) -> None:
    """Menampilkan drama trending Melolo."""
    logger.info("User %s → Melolo Trending", callback.from_user.id)
    await callback.answer("⏳ Memuat drama trending...")

    dramas = await fetch_melolo_trending()
    if not dramas:
        await callback.message.answer("😔 Tidak ada drama trending.")
        return

    text = "🔥 <b>Drama Trending (Melolo)</b>\n\n👇 Pilih drama:"
    keyboard = melolo_list_keyboard(dramas, has_more=False)
    
    await callback.message.edit_caption(
        caption=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )

@router.callback_query(F.data == "melolo:search")
async def cb_melolo_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Memulai pencarian Melolo."""
    await callback.answer()
    await callback.message.answer("🔍 <b>Ketik judul drama Melolo yang dicari:</b>", parse_mode="HTML")
    await state.set_state(MeloloSearchState.waiting_for_query)

@router.message(MeloloSearchState.waiting_for_query)
async def handle_melolo_search(message: Message, state: FSMContext) -> None:
    """Menangani query pencarian Melolo."""
    query = message.text
    logger.info("User %s mencari Melolo: %s", message.from_user.id, query)
    await state.clear()
    
    dramas = await fetch_melolo_search(query)
    if not dramas:
        await message.answer(f"😔 Tidak ditemukan drama Melolo dengan kata kunci: {query}")
        return

    text = f"🔍 <b>Hasil Pencarian Melolo:</b> {query}\n\n👇 Pilih drama:"
    keyboard = melolo_list_keyboard(dramas, has_more=False)
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@router.callback_query(F.data.startswith("melolo_detail:"))
async def cb_melolo_detail(callback: CallbackQuery) -> None:
    """Menampilkan detail drama Melolo."""
    book_id = callback.data.split(":")[1]
    logger.info("User %s → Detail Melolo %s", callback.from_user.id, book_id)
    await callback.answer("⏳ Memuat detail...")

    detail = await fetch_melolo_detail(book_id)
    if not detail:
        await callback.message.answer("😔 Gagal memuat detail drama.")
        return

    # Melolo detail structure inference
    title = detail.get("bookName") or detail.get("name") or "No Title"
    desc = detail.get("intro") or detail.get("description") or "Tidak ada deskripsi."
    vid = detail.get("vid") or detail.get("videoId")
    cover = detail.get("cover") or detail.get("horizontalCover")
    
    text = (
        f"🎬 <b>{title}</b>\n\n"
        f"📝 {desc}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    builder = InlineKeyboardBuilder()
    if vid:
        builder.row(InlineKeyboardButton(text="▶️ Tonton Sekarang", callback_data=f"melolo_stream:{vid}"))
    
    builder.row(InlineKeyboardButton(text="🔙 Kembali", callback_data="melolo:home"))
    
    if cover:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=cover,
                caption=text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
        except Exception:
            await callback.message.edit_caption(
                caption=text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
    else:
        await callback.message.edit_caption(
            caption=text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

@router.callback_query(F.data.startswith("melolo_stream:"))
async def cb_melolo_stream(callback: CallbackQuery) -> None:
    """Menangani stream Melolo."""
    video_id = callback.data.split(":")[1]
    logger.info("User %s → Stream Melolo %s", callback.from_user.id, video_id)
    await callback.answer("⏳ Memuat link stream...")

    stream_data = await fetch_melolo_stream(video_id)
    if not stream_data:
        await callback.message.answer("😔 Gagal memuat link stream.")
        return

    # Stream data structure inference
    url = stream_data.get("url") or stream_data.get("videoUrl") or stream_data.get("playUrl")
    if not url:
        await callback.message.answer("😔 Link stream tidak ditemukan.")
        return

    await callback.message.answer(f"🍿 <b>Link Nonton:</b>\n<a href='{url}'>Klik di sini untuk menonton</a>", parse_mode="HTML")
