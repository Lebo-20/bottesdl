"""
Handlers — Melolo API (Video Player & Cleanup System)
Support for playing video directly from bot and cleanup old messages.
"""

import os
import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    FSInputFile,
    InputMediaVideo,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command

from services.melolo import (
    fetch_melolo_foryou,
    fetch_melolo_latest,
    fetch_melolo_trending,
    fetch_melolo_search,
    fetch_melolo_detail,
    fetch_melolo_stream,
)
from player import download_generic_video
from middlewares.cleanup import perform_cleanup, add_to_cleanup
from config import DRAMAS_PER_PAGE, EPISODES_PER_PAGE

router = Router(name="melolo")
logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════╗
# ║                   FSM STATES                            ║
# ╚══════════════════════════════════════════════════════════╝

class MeloloState(StatesGroup):
    waiting_search = State()  # Menunggu input keyword pencarian


# ╔══════════════════════════════════════════════════════════╗
# ║               KEYBOARD BUILDERS                         ║
# ╚══════════════════════════════════════════════════════════╝

def _main_menu_kb() -> InlineKeyboardMarkup:
    """Menu utama Melolo."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎯 For You", callback_data="ml:foryou:0"),
        InlineKeyboardButton(text="🔥 Trending", callback_data="ml:trending:0"),
    )
    builder.row(
        InlineKeyboardButton(text="🆕 Latest", callback_data="ml:latest:0"),
        InlineKeyboardButton(text="🔍 Search", callback_data="ml:search"),
    )
    return builder.as_markup()


def _drama_list_kb(
    dramas: list,
    mode: str,
    offset: int,
    query: str = "",
) -> InlineKeyboardMarkup:
    """Keyboard list drama dengan tombol detail & navigasi."""
    builder = InlineKeyboardBuilder()

    # Tombol detail per drama (satu baris per drama)
    for i, d in enumerate(dramas, offset + 1):
        title = (d.get("name") or "No Title")[:40]
        book_id = d.get("id", "")
        back_data = f"{mode}:{offset}:{query}"
        builder.row(
            InlineKeyboardButton(
                text=f"{i}. {title}",
                callback_data=f"ml:detail:{book_id}:{back_data}",
            )
        )

    # Navigasi Prev / Next
    nav = []
    if offset > 0:
        prev_offset = max(0, offset - DRAMAS_PER_PAGE)
        nav.append(
            InlineKeyboardButton(
                text="⬅️ Prev",
                callback_data=f"ml:{mode}:{prev_offset}:{query}",
            )
        )
    if len(dramas) >= DRAMAS_PER_PAGE:
        next_offset = offset + DRAMAS_PER_PAGE
        nav.append(
            InlineKeyboardButton(
                text="➡️ Next",
                callback_data=f"ml:{mode}:{next_offset}:{query}",
            )
        )

    if nav:
        builder.row(*nav)

    builder.row(
        InlineKeyboardButton(text="🏠 Menu Melolo", callback_data="ml:home")
    )
    return builder.as_markup()


def _player_kb(
    book_id: str, 
    video_list: list, 
    current_vid: str, 
    back_data: str,
    ep_page: int = 0
) -> InlineKeyboardMarkup:
    """Keyboard player dengan grid episode (3 kolom)."""
    builder = InlineKeyboardBuilder()

    # Pagination episode grid (sama seperti di Vigloo)
    total_eps = len(video_list)
    total_pages = (total_eps + EPISODES_PER_PAGE - 1) // EPISODES_PER_PAGE
    start = ep_page * EPISODES_PER_PAGE
    end = start + EPISODES_PER_PAGE
    cur_eps = video_list[start:end]

    for v in cur_eps:
        v_id = v.get("vid")
        v_idx = v.get("vid_index")
        # Highlight episode aktif
        btn_text = f"【 {v_idx} 】" if v_id == current_vid else f"{v_idx}"
        builder.button(
            text=btn_text, 
            callback_data=f"ml:stream:{v_id}:{book_id}:{back_data}:{ep_page}"
        )
    builder.adjust(3)

    # Navigasi grid
    nav = []
    if ep_page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Halaman", callback_data=f"ml:ep_page:{book_id}:{current_vid}:{back_data}:{ep_page - 1}"))
    
    nav.append(InlineKeyboardButton(text=f"📄 {ep_page + 1}/{total_pages}", callback_data="noop"))
    
    if ep_page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Selanjutnya ➡️", callback_data=f"ml:ep_page:{book_id}:{current_vid}:{back_data}:{ep_page + 1}"))
    
    if nav:
        builder.row(*nav)

    # Action buttons
    builder.row(
        InlineKeyboardButton(text="📋 Daftar Episode", callback_data=f"ml:detail:{book_id}:{back_data}"),
        InlineKeyboardButton(text="🏠 Menu Utama", callback_data="ml:home")
    )

    return builder.as_markup()


# ╔══════════════════════════════════════════════════════════╗
# ║               HELPER: Ambil & Tampilkan List            ║
# ╚══════════════════════════════════════════════════════════╝

async def _edit_safe(message: Message, text: str, kb: InlineKeyboardMarkup) -> None:
    """Safe edit that handles text and caption."""
    try:
        # Hapus web preview biar rapi tapi biarkan jika di stream video
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        try:
            await message.edit_caption(caption=text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            # Jika semua gagal (misal sudah terhapus), kirim pesan baru
            await message.answer(text, parse_mode="HTML", reply_markup=kb)


async def _show_list(
    target,  # Message atau CallbackQuery.message
    mode: str,
    offset: int,
    query: str = "",
    edit: bool = True,
) -> None:
    # ... (header logic sama)
    # Ambil data dari API
    dramas = []
    if mode == "foryou":
        dramas = await fetch_melolo_foryou(offset=offset)
        header = "🎯 <b>Drama Untuk Anda</b>"
    elif mode == "trending":
        dramas = await fetch_melolo_trending(offset=offset)
        header = "🔥 <b>Drama Trending</b>"
    elif mode == "latest":
        dramas = await fetch_melolo_latest(offset=offset)
        header = "🆕 <b>Drama Terbaru</b>"
    elif mode == "search":
        dramas = await fetch_melolo_search(query, limit=DRAMAS_PER_PAGE, offset=offset)
        header = f"🔍 <b>Hasil Pencarian:</b> {query}"
    else:
        dramas = []
        header = "🎬 <b>Drama</b>"

    if not dramas:
        text = "❌ Tidak ada hasil."
        kb = _main_menu_kb()
    else:
        numbered = "\n".join(
            f"{offset + i + 1}. {d.get('name', 'No Title')}"
            for i, d in enumerate(dramas)
        )
        text = f"{header}\n\n🎬 Daftar Drama:\n\n{numbered}\n\n📖 Klik judul untuk melihat detail."
        kb = _drama_list_kb(dramas, mode=mode, offset=offset, query=query)

    if edit:
        await _edit_safe(target, text, kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


# ╔══════════════════════════════════════════════════════════╗
# ║               MAIN COMMANDS & CALLBACKS                 ║
# ╚══════════════════════════════════════════════════════════╝

@router.message(Command("melolo"))
async def cmd_melolo(message: Message, state: FSMContext, bot: Bot) -> None:
    """Cleanup chat dan tampilkan menu."""
    await perform_cleanup(bot, state, message.chat.id)
    text = (
        "🎭 <b>Melolo Drama</b>\n\n"
        "Selamat datang! Pilih kategori drama favoritmu:\n\n"
        "🎯 <b>For You</b> — Rekomendasi spesial untukmu\n"
        "🔥 <b>Trending</b> — Drama yang lagi viral\n"
        "🆕 <b>Latest</b> — Rilis terbaru\n"
        "🔍 <b>Search</b> — Cari judul drama"
    )
    res = await message.answer(text, parse_mode="HTML", reply_markup=_main_menu_kb())
    await add_to_cleanup(state, res.message_id)


@router.callback_query(F.data == "ml:home")
async def cb_home(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await perform_cleanup(bot, state, callback.message.chat.id)
    text = (
        "🎭 <b>Melolo Drama</b>\n\n"
        "Pilih kategori drama favoritmu:\n\n"
        "🎯 <b>For You</b> — Rekomendasi spesial untukmu\n"
        "🔥 <b>Trending</b> — Drama yang lagi viral\n"
        "🆕 <b>Latest</b> — Rilis terbaru\n"
        "🔍 <b>Search</b> — Cari judul drama"
    )
    await callback.answer()
    res = await callback.message.answer(text, parse_mode="HTML", reply_markup=_main_menu_kb())
    await add_to_cleanup(state, res.message_id)


@router.callback_query(F.data.regexp(r"^ml:(foryou|trending|latest):(\d+)$"))
async def cb_list(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    mode = parts[1]
    offset = int(parts[2])
    await callback.answer("⏳ Memuat...")
    await _show_list(callback.message, mode=mode, offset=offset, edit=True)


@router.callback_query(F.data == "ml:search")
async def cb_search_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(MeloloState.waiting_search)
    await callback.message.edit_text(
        "🔍 <b>Cari Drama</b>\n\nMasukkan kata kunci pencarian:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder()
        .row(InlineKeyboardButton(text="❌ Batal", callback_data="ml:home"))
        .as_markup(),
    )


@router.message(MeloloState.waiting_search)
async def handle_search_query(message: Message, state: FSMContext, bot: Bot) -> None:
    query = (message.text or "").strip()
    await state.clear()
    
    # Cleanup call
    await perform_cleanup(bot, state, message.chat.id)

    if not query:
        res = await message.answer("❌ Kata kunci tidak boleh kosong.", reply_markup=_main_menu_kb())
        await add_to_cleanup(state, res.message_id)
        return

    res = await message.answer(f"🔍 Mencari drama: {query}...")
    await add_to_cleanup(state, res.message_id)
    await _show_list(res, mode="search", offset=0, query=query, edit=True)


@router.callback_query(F.data.regexp(r"^ml:search:(\d+):(.+)$"))
async def cb_search_paginate(callback: CallbackQuery) -> None:
    parts = callback.data.split(":", 3)
    offset = int(parts[2])
    query = parts[3]
    await callback.answer("⏳ Memuat...")
    await _show_list(callback.message, mode="search", offset=offset, query=query, edit=True)


@router.callback_query(F.data.startswith("ml:detail:"))
async def cb_detail(callback: CallbackQuery) -> None:
    raw = callback.data[len("ml:detail:"):]
    parts = raw.split(":", 1)
    book_id = parts[0]
    back_data = parts[1] if len(parts) > 1 else "foryou:0:"

    await callback.answer("⏳ Memuat detail...")
    detail = await fetch_melolo_detail(book_id)
    if not detail:
        await callback.message.edit_text("❌ Gagal.")
        return

    title = detail.get("series_title") or detail.get("book_name") or "No Title"
    desc = detail.get("series_intro") or detail.get("abstract") or "Tidak ada deskripsi."
    video_list = detail.get("video_list") or []

    text = f"📖 <b>{title}</b>\n\n📄 {desc[:300]}...\n\n🎬 <b>Daftar Episode:</b>"
    kb = _player_kb(book_id, video_list, "", back_data, 0)
    
    await _edit_safe(callback.message, text, kb)


@router.callback_query(F.data.startswith("ml:ep_page:"))
async def cb_ep_page(callback: CallbackQuery) -> None:
    # Format: ml:ep_page:{book_id}:{current_vid}:{back_data}:{ep_page}
    parts = callback.data.split(":", 5)
    book_id = parts[2]
    current_vid = parts[3]
    back_data = parts[4]
    ep_page = int(parts[5])

    detail = await fetch_melolo_detail(book_id)
    video_list = detail.get("video_list", []) if detail else []
    
    kb = _player_kb(book_id, video_list, current_vid, back_data, ep_page)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("ml:stream:"))
async def cb_stream(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Download video dari Melolo dan kirim file langsung."""
    # Format: ml:stream:{video_id}:{book_id}:{back_data}:{ep_page}
    parts = callback.data.split(":")
    video_id = parts[2]
    book_id = parts[3]
    back_data = parts[4]
    ep_page = int(parts[5]) if len(parts) > 5 else 0

    await callback.answer("⏳ Menyiapkan video...")
    
    # 1. Ambil detail & link stream
    detail = await fetch_melolo_detail(book_id)
    stream_data = await fetch_melolo_stream(video_id)
    
    if not detail or not stream_data:
        await callback.message.edit_text("❌ Gagal.")
        return

    title = detail.get("series_title", "Drama")
    video_list = detail.get("video_list", [])
    current_ep_idx = "0"
    for v in video_list:
        if v.get("vid") == video_id:
            current_ep_idx = v.get("vid_index")
            break

    url = stream_data.get("main_url") or stream_data.get("url")
    if not url:
        await callback.message.edit_text("❌ Link stream tidak ditemukan.")
        return

    # 2. UI Cleaning: Beritahu user sedang download
    wait_msg = await callback.message.answer(f"📥 <b>Downloading Episode {current_ep_idx}...</b>\n\n<i>Mohon tunggu, video sedang diproses oleh bot.</i>", parse_mode="HTML")
    await perform_cleanup(bot, state, callback.message.chat.id)
    await add_to_cleanup(state, wait_msg.message_id)

    # 3. Download
    filename = f"melolo_{video_id}"
    video_path = await download_generic_video(url, filename)
    
    if not video_path:
        await wait_msg.edit_text("❌ Gagal mendownload video. Silakan coba link cadangan atau episode lain.")
        return

    # 4. Create Keyboard & Send
    kb = _player_kb(book_id, video_list, video_id, back_data, ep_page)
    caption = (
        f"🎬 <b>{title}</b>\n"
        f"▶️ Episode {current_ep_idx}\n\n"
        f"🍿 Selamat menonton langsung dari bot!"
    )

    try:
        res = await bot.send_video(
            chat_id=callback.message.chat.id,
            video=FSInputFile(video_path),
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb
        )
        await add_to_cleanup(state, res.message_id)
        # Hapus sisa file & pesan "Downloading"
        await bot.delete_message(callback.message.chat.id, wait_msg.message_id)
        if os.path.exists(video_path): os.remove(video_path)
    except Exception as e:
        logger.error("Gagal kirim video: %s", e)
        await wait_msg.edit_text(f"❌ Terjadi kesalahan saat mengirim video.\n<code>{str(e)[:100]}</code>")

