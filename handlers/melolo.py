"""
Handlers — Melolo API (Netflix-style Interactive Bot)
Navigasi penuh berbasis inline keyboard, pagination, editMessage.
"""

import logging
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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

router = Router(name="melolo")
logger = logging.getLogger(__name__)

DRAMAS_PER_PAGE = 5  # Jumlah drama per halaman


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


def _detail_kb(book_id: str, video_list: list, back_data: str) -> InlineKeyboardMarkup:
    """Keyboard detail drama dengan tombol tonton per episode."""
    builder = InlineKeyboardBuilder()

    for vid_item in video_list[:20]:
        v_id = vid_item.get("vid")
        v_idx = vid_item.get("vid_index")
        if v_id and v_idx is not None:
            builder.add(
                InlineKeyboardButton(
                    text=f"▶️ Ep {v_idx}",
                    callback_data=f"ml:stream:{v_id}:{book_id}:{back_data}",
                )
            )
    builder.adjust(3)

    builder.row(
        InlineKeyboardButton(
            text="🔙 Kembali",
            callback_data=f"ml:back:{back_data}",
        )
    )
    return builder.as_markup()


def _stream_kb(book_id: str, back_data: str) -> InlineKeyboardMarkup:
    """Keyboard setelah stream — kembali ke detail."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔙 Kembali ke Detail",
            callback_data=f"ml:detail:{book_id}:{back_data}",
        )
    )
    builder.row(
        InlineKeyboardButton(text="🏠 Menu Melolo", callback_data="ml:home")
    )
    return builder.as_markup()


# ╔══════════════════════════════════════════════════════════╗
# ║               HELPER: Ambil & Tampilkan List            ║
# ╚══════════════════════════════════════════════════════════╝

async def _show_list(
    target,  # Message atau CallbackQuery.message
    mode: str,
    offset: int,
    query: str = "",
    edit: bool = True,
) -> None:
    """Ambil data sesuai mode dan render list ke chat."""

    # Ambil data dari API
    dramas = []
    if mode == "foryou":
        dramas = await fetch_melolo_foryou(offset=offset)
        header = "🎯 <b>Drama Untuk Anda</b>"
    elif mode == "trending":
        dramas = await fetch_melolo_trending()
        header = "🔥 <b>Drama Trending</b>"
    elif mode == "latest":
        dramas = await fetch_melolo_latest()
        header = "🆕 <b>Drama Terbaru</b>"
    elif mode == "search":
        dramas = await fetch_melolo_search(query, limit=DRAMAS_PER_PAGE, offset=offset)
        header = f"🔍 <b>Hasil Pencarian:</b> {query}"
    else:
        dramas = []
        header = "🎬 <b>Drama</b>"

    # Pagination slice untuk trending/latest (sudah semua di-load)
    if mode in ("trending", "latest"):
        total = dramas
        dramas = total[offset: offset + DRAMAS_PER_PAGE]

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
        try:
            await target.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            try:
                await target.edit_caption(text, parse_mode="HTML", reply_markup=kb)
            except Exception:
                await target.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=kb)


# ╔══════════════════════════════════════════════════════════╗
# ║               MAIN COMMAND: /melolo                     ║
# ╚══════════════════════════════════════════════════════════╝

@router.message(Command("melolo"))
async def cmd_melolo(message: Message, state: FSMContext) -> None:
    """Entry point: /melolo — Tampilkan menu utama."""
    await state.clear()
    text = (
        "🎭 <b>Melolo Drama</b>\n\n"
        "Selamat datang! Pilih kategori drama favoritmu:\n\n"
        "🎯 <b>For You</b> — Rekomendasi spesial untukmu\n"
        "🔥 <b>Trending</b> — Drama yang lagi viral\n"
        "🆕 <b>Latest</b> — Rilis terbaru\n"
        "🔍 <b>Search</b> — Cari judul drama"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=_main_menu_kb())


# ╔══════════════════════════════════════════════════════════╗
# ║               CALLBACK: MENU HOME                       ║
# ╚══════════════════════════════════════════════════════════╝

@router.callback_query(F.data == "ml:home")
async def cb_home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    text = (
        "🎭 <b>Melolo Drama</b>\n\n"
        "Pilih kategori drama favoritmu:\n\n"
        "🎯 <b>For You</b> — Rekomendasi spesial untukmu\n"
        "🔥 <b>Trending</b> — Drama yang lagi viral\n"
        "🆕 <b>Latest</b> — Rilis terbaru\n"
        "🔍 <b>Search</b> — Cari judul drama"
    )
    try:
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=_main_menu_kb()
        )
    except Exception:
        await callback.message.answer(
            text, parse_mode="HTML", reply_markup=_main_menu_kb()
        )
    await callback.answer()


# ╔══════════════════════════════════════════════════════════╗
# ║               CALLBACK: LIST (foryou/trending/latest)   ║
# ╚══════════════════════════════════════════════════════════╝

@router.callback_query(F.data.regexp(r"^ml:(foryou|trending|latest):(\d+)$"))
async def cb_list(callback: CallbackQuery) -> None:
    """Tampilkan list drama berdasarkan mode & offset."""
    parts = callback.data.split(":")
    mode = parts[1]
    offset = int(parts[2])
    await callback.answer("⏳ Memuat...")
    await _show_list(callback.message, mode=mode, offset=offset, edit=True)


# ╔══════════════════════════════════════════════════════════╗
# ║               CALLBACK: SEARCH                          ║
# ╚══════════════════════════════════════════════════════════╝

@router.callback_query(F.data == "ml:search")
async def cb_search_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    """Minta user input keyword pencarian."""
    await callback.answer()
    await state.set_state(MeloloState.waiting_search)
    try:
        await callback.message.edit_text(
            "🔍 <b>Cari Drama</b>\n\nMasukkan kata kunci pencarian:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardBuilder()
            .row(InlineKeyboardButton(text="❌ Batal", callback_data="ml:home"))
            .as_markup(),
        )
    except Exception:
        await callback.message.answer(
            "🔍 <b>Cari Drama</b>\n\nMasukkan kata kunci pencarian:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardBuilder()
            .row(InlineKeyboardButton(text="❌ Batal", callback_data="ml:home"))
            .as_markup(),
        )


@router.message(MeloloState.waiting_search)
async def handle_search_query(message: Message, state: FSMContext) -> None:
    """Terima keyword dan tampilkan hasil pencarian."""
    query = (message.text or "").strip()
    await state.clear()

    if not query:
        await message.answer("❌ Kata kunci tidak boleh kosong.", reply_markup=_main_menu_kb())
        return

    await message.answer("🔍 Mencari drama...")
    await _show_list(message, mode="search", offset=0, query=query, edit=False)


@router.callback_query(F.data.regexp(r"^ml:search:(\d+):(.+)$"))
async def cb_search_paginate(callback: CallbackQuery) -> None:
    """Pagination hasil pencarian."""
    parts = callback.data.split(":", 3)
    offset = int(parts[2])
    query = parts[3] if len(parts) > 3 else ""
    await callback.answer("⏳ Memuat...")
    await _show_list(callback.message, mode="search", offset=offset, query=query, edit=True)


# ╔══════════════════════════════════════════════════════════╗
# ║               CALLBACK: BACK (list navigation)          ║
# ╚══════════════════════════════════════════════════════════╝

@router.callback_query(F.data.startswith("ml:back:"))
async def cb_back(callback: CallbackQuery) -> None:
    """Kembali ke list sebelumnya."""
    # back_data format: mode:offset:query
    back_data = callback.data[len("ml:back:"):]
    parts = back_data.split(":", 2)
    mode = parts[0] if len(parts) > 0 else "foryou"
    offset = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    query = parts[2] if len(parts) > 2 else ""
    await callback.answer("⏳ Kembali...")
    await _show_list(callback.message, mode=mode, offset=offset, query=query, edit=True)


# ╔══════════════════════════════════════════════════════════╗
# ║               CALLBACK: DETAIL                          ║
# ╚══════════════════════════════════════════════════════════╝

@router.callback_query(F.data.startswith("ml:detail:"))
async def cb_detail(callback: CallbackQuery) -> None:
    """Tampilkan detail drama beserta daftar episode."""
    # Format: ml:detail:{book_id}:{mode}:{offset}:{query}
    raw = callback.data[len("ml:detail:"):]
    parts = raw.split(":", 1)
    book_id = parts[0]
    back_data = parts[1] if len(parts) > 1 else "foryou:0:"

    await callback.answer("⏳ Memuat detail...")

    detail = await fetch_melolo_detail(book_id)
    if not detail:
        await callback.message.edit_text(
            "❌ Gagal mengambil data detail drama.",
            reply_markup=InlineKeyboardBuilder()
            .row(InlineKeyboardButton(text="🔙 Kembali", callback_data=f"ml:back:{back_data}"))
            .as_markup(),
        )
        return

    title = detail.get("series_title") or detail.get("book_name") or "No Title"
    desc = detail.get("series_intro") or detail.get("abstract") or "Tidak ada deskripsi."
    video_list = detail.get("video_list") or []

    # Truncate desc
    if len(desc) > 300:
        desc = desc[:300] + "..."

    ep_count = len(video_list)
    text = (
        f"📖 <b>{title}</b>\n\n"
        f"📄 {desc}\n\n"
        f"🎬 <b>Episode:</b> {ep_count} episode tersedia\n"
    )

    if not video_list:
        text += "\n❌ Tidak ada episode tersedia."

    kb = _detail_kb(book_id, video_list, back_data)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        try:
            await callback.message.edit_caption(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)


# ╔══════════════════════════════════════════════════════════╗
# ║               CALLBACK: STREAM                          ║
# ╚══════════════════════════════════════════════════════════╝

@router.callback_query(F.data.startswith("ml:stream:"))
async def cb_stream(callback: CallbackQuery) -> None:
    """Ambil link stream dan tampilkan ke user."""
    # Format: ml:stream:{video_id}:{book_id}:{back_data}
    raw = callback.data[len("ml:stream:"):]
    parts = raw.split(":", 2)
    video_id = parts[0]
    book_id = parts[1] if len(parts) > 1 else ""
    back_data = parts[2] if len(parts) > 2 else "foryou:0:"

    await callback.answer("⏳ Memuat stream...")

    stream_data = await fetch_melolo_stream(video_id)
    if not stream_data:
        await callback.message.edit_text(
            "❌ Gagal mengambil data stream.",
            reply_markup=_stream_kb(book_id, back_data),
        )
        return

    url = (
        stream_data.get("main_url")
        or stream_data.get("backup_url")
        or stream_data.get("url")
        or stream_data.get("video_url")
    )

    if not url:
        await callback.message.edit_text(
            "❌ Link stream tidak ditemukan.",
            reply_markup=_stream_kb(book_id, back_data),
        )
        return

    text = (
        f"🎬 <b>Streaming</b>\n\n"
        f"🍿 Selamat menonton!\n\n"
        f"<a href='{url}'>▶️ Tonton Sekarang</a>"
    )

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=_stream_kb(book_id, back_data),
            disable_web_page_preview=False,
        )
    except Exception:
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=_stream_kb(book_id, back_data),
            disable_web_page_preview=False,
        )
