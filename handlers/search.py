"""
Handlers — Pencarian drama
Menggunakan FSM untuk menangkap input teks dari user.
Mendukung pagination hasil pencarian (5 drama per halaman).
"""

import logging
import math
from typing import List

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import DRAMAS_PER_PAGE
from keyboards.inline import drama_list_keyboard, back_to_home_keyboard
from services.api import fetch_dramas

router = Router(name="search")
logger = logging.getLogger(__name__)


class SearchState(StatesGroup):
    """FSM states untuk pencarian."""
    waiting_for_query = State()


async def _get_search_results(query: str) -> List[dict]:
    """Helper untuk mencari drama di beberapa halaman API."""
    query_lower = query.lower()
    matched = []

    # Ambil hingga 5 halaman API (250 drama) untuk difilter
    for p in range(1, 6):
        result = await fetch_dramas(page=p, limit=50)
        dramas = result.get("dramas", [])
        if not dramas:
            break

        for d in dramas:
            if (
                query_lower in d["title"].lower()
                or query_lower in d.get("description", "").lower()
            ):
                # Hindari duplikat
                if not any(m["id"] == d["id"] for m in matched):
                    matched.append(d)

        if result.get("page", 1) >= result.get("total_pages", 1):
            break

    return matched


def _format_search_message(query: str, matched: List[dict], page: int) -> str:
    """Helper untuk format pesan hasil pencarian."""
    total = len(matched)
    total_pages = max(1, math.ceil(total / DRAMAS_PER_PAGE))
    start_idx = (page - 1) * DRAMAS_PER_PAGE
    end_idx = start_idx + DRAMAS_PER_PAGE
    page_items = matched[start_idx:end_idx]

    text = (
        f"🔍 <b>Hasil Pencarian:</b> <code>{query}</code>\n"
        f"📊 Ditemukan <b>{total}</b> drama\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    for i, d in enumerate(page_items, start_idx + 1):
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
    return text


@router.callback_query(F.data == "menu:search")
async def cb_start_search(callback: CallbackQuery, state: FSMContext) -> None:
    """Memulai mode pencarian — minta user ketik judul."""
    logger.info("User %s → Cari Drama", callback.from_user.id)
    await callback.answer()

    text = (
        "🔍 <b>Cari Drama</b>\n\n"
        "Ketik judul drama yang ingin kamu cari.\n"
        "Contoh: <code>Cinta</code> atau <code>CEO</code>\n\n"
        "💡 <i>Ketik minimal 2 huruf untuk mencari.</i>"
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

    await state.set_state(SearchState.waiting_for_query)


@router.message(SearchState.waiting_for_query)
async def handle_search_query(message: Message, state: FSMContext) -> None:
    """Menangkap teks pencarian dari user dan cari di API."""
    query = message.text.strip() if message.text else ""

    if len(query) < 2:
        await message.answer(
            "⚠️ Ketik minimal <b>2 huruf</b> untuk mencari drama.",
            parse_mode="HTML",
        )
        return

    logger.info("User %s mencari: '%s'", message.from_user.id, query)
    await state.clear()

    loading = await message.answer("🔍 <b>Mencari drama...</b>", parse_mode="HTML")

    matched = await _get_search_results(query)

    try:
        await loading.delete()
    except Exception:
        pass

    if not matched:
        await message.answer(
            f"😔 <b>Tidak ditemukan drama dengan kata kunci:</b>\n"
            f"<code>{query}</code>\n\n"
            f"💡 Coba kata kunci lain.",
            parse_mode="HTML",
            reply_markup=back_to_home_keyboard(),
        )
        return

    text = _format_search_message(query, matched, page=1)
    total_pages = math.ceil(len(matched) / DRAMAS_PER_PAGE)

    # Kirim keyboard dengan prefix khusus untuk search pagination
    # Format: sp:{query}:{page} -> sp = search page (pendek agar tidak melebihi limit callback_data)
    keyboard = drama_list_keyboard(
        dramas=matched[0:DRAMAS_PER_PAGE],
        page=1,
        total_pages=total_pages,
        nav_prefix=f"sp:{query}:",
    )

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("sp:"))
async def cb_search_pagination(callback: CallbackQuery) -> None:
    """Handler untuk pagination hasil pencarian."""
    parts = callback.data.split(":")
    query = parts[1]
    page = int(parts[2])

    logger.info("User %s → Search '%s' page %d", callback.from_user.id, query, page)
    await callback.answer(f"📄 Halaman {page}")

    matched = await _get_search_results(query)

    if not matched:
        await callback.message.edit_text(
            "❌ Hasil pencarian sudah tidak tersedia. Silakan cari ulang.",
            reply_markup=back_to_home_keyboard(),
        )
        return

    text = _format_search_message(query, matched, page)
    total_pages = math.ceil(len(matched) / DRAMAS_PER_PAGE)

    start_idx = (page - 1) * DRAMAS_PER_PAGE
    end_idx = start_idx + DRAMAS_PER_PAGE

    keyboard = drama_list_keyboard(
        dramas=matched[start_idx:end_idx],
        page=page,
        total_pages=total_pages,
        nav_prefix=f"sp:{query}:",
    )

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except Exception:
        # Jika gagal edit (misal: pesan sama), abaikan
        pass
