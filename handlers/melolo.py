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
from aiogram.filters import Command, CommandObject

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

    # Melolo detail structure: data.video_data
    title = detail.get("series_title", "No Title")
    desc = detail.get("series_intro", "Tidak ada deskripsi.")
    cover = detail.get("series_cover")
    video_list = detail.get("video_list", [])
    
    text = (
        f"🎬 <b>{title}</b>\n\n"
        f"📝 {desc}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📺 <b>Daftar Episode:</b>\n"
    )

    builder = InlineKeyboardBuilder()
    for vid_item in video_list[:10]: # Limit to 10 for inline buttons
        v_id = vid_item.get("vid")
        v_idx = vid_item.get("vid_index")
        if v_id and v_idx:
            builder.add(InlineKeyboardButton(text=f"Eps {v_idx}", callback_data=f"melolo_stream:{v_id}"))
    
    builder.adjust(5)
    builder.row(InlineKeyboardButton(text="🔙 Kembali", callback_data="melolo:home"))
    
    # Add full episode list in text for slash command reference
    if len(video_list) > 10:
        text += "<i>(Gunakan perintah /melolo detail untuk list lengkap)</i>"
    elif not video_list:
        text += "Tidak ada episode tersedia."

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

    # Melolo stream structure: data.main_url or data.backup_url
    url = stream_data.get("main_url") or stream_data.get("backup_url")
    if not url:
        await callback.message.answer("😔 Link stream tidak ditemukan.")
        return

    await callback.message.answer(f"🍿 <b>Link Nonton:</b>\n<a href='{url}'>Klik di sini untuk menonton</a>", parse_mode="HTML")


# ╔══════════════════════════════════════════════════════════╗
# ║                   SLASH COMMANDS                        ║
# ╚══════════════════════════════════════════════════════════╝

@router.message(Command("melolo"))
async def cmd_melolo_base(message: Message, command: CommandObject) -> None:
    """Handler utama untuk perintah /melolo."""
    sub = command.command
    args = command.args or ""
    
    # Karena Command() menangkap /melolo, sub akan selalu 'melolo'
    # Kita perlu parse argumen pertama sebagai sub-command
    parts = args.split()
    if not parts:
        # Jika cuma /melolo tanpa argumen, tampilkan help atau menu
        text = (
            "🚀 <b>Melolo Bot — Panduan Penggunaan</b>\n\n"
            "• <code>/melolo foryou [offset]</code> — Rekomendasi drama\n"
            "• <code>/melolo latest</code> — Drama terbaru\n"
            "• <code>/melolo trending</code> — Drama trending\n"
            "• <code>/melolo search [query]</code> — Cari drama\n"
            "• <code>/melolo detail [bookId]</code> — Detail drama\n"
            "• <code>/melolo stream [videoId]</code> — Nonton drama\n\n"
            "Gunakan perintah di atas untuk mulai menonton! 🍿"
        )
        await message.answer(text, parse_mode="HTML")
        return

    sub_cmd = parts[0].lower()
    sub_args = parts[1:]

    if sub_cmd == "foryou":
        await cmd_melolo_foryou(message, sub_args)
    elif sub_cmd == "latest":
        await cmd_melolo_latest(message)
    elif sub_cmd == "trending":
        await cmd_melolo_trending(message)
    elif sub_cmd == "search":
        await cmd_melolo_search(message, sub_args)
    elif sub_cmd == "detail":
        await cmd_melolo_detail(message, sub_args)
    elif sub_cmd == "stream":
        await cmd_melolo_stream(message, sub_args)
    else:
        await message.answer("❌ Perintah tidak dikenal. Ketik <code>/melolo</code> untuk bantuan.")


async def cmd_melolo_foryou(message: Message, args: list[str]) -> None:
    offset = int(args[0]) if args and args[0].isdigit() else 20
    dramas = await fetch_melolo_foryou(offset=offset)
    
    if not dramas:
        await message.answer("😔 Tidak ada drama tersedia.")
        return

    text = f"🎬 <b>Drama Untuk Anda (Offset: {offset})</b>\n\n"
    for i, d in enumerate(dramas, 1):
        text += f"{i}. <b>{d['name']}</b>\n   ID: <code>{d['id']}</code>\n\n"
    
    text += "💡 Gunakan: <code>/melolo detail <bookId></code> untuk melihat detail."
    await message.answer(text, parse_mode="HTML")


async def cmd_melolo_latest(message: Message) -> None:
    dramas = await fetch_melolo_latest()
    if not dramas:
        await message.answer("😔 Tidak ada drama terbaru.")
        return

    text = "✨ <b>Drama Terbaru</b>\n\n"
    for i, d in enumerate(dramas, 1):
        text += f"{i}. <b>{d['name']}</b>\n   ID: <code>{d['id']}</code>\n\n"
    
    text += "💡 Gunakan: <code>/melolo detail <bookId></code> untuk melihat detail."
    await message.answer(text, parse_mode="HTML")


async def cmd_melolo_trending(message: Message) -> None:
    dramas = await fetch_melolo_trending()
    if not dramas:
        await message.answer("😔 Tidak ada drama trending.")
        return

    text = "🔥 <b>Drama Trending</b>\n\n"
    for i, d in enumerate(dramas, 1):
        text += f"{i}. <b>{d['name']}</b>\n   ID: <code>{d['id']}</code>\n\n"
    
    text += "💡 Gunakan: <code>/melolo detail <bookId></code> untuk melihat detail."
    await message.answer(text, parse_mode="HTML")


async def cmd_melolo_search(message: Message, args: list[str]) -> None:
    if not args:
        await message.answer("⚠️ Harap masukkan kata kunci! Contoh: <code>/melolo search cinta</code>")
        return
    
    query = " ".join(args)
    dramas = await fetch_melolo_search(query)
    
    if not dramas:
        await message.answer(f"😔 Drama tidak ditemukan untuk kata kunci: <b>{query}</b>")
        return

    text = f"🔍 <b>Hasil pencarian \"{query}\":</b>\n\n"
    for i, d in enumerate(dramas, 1):
        text += f"{i}. <b>{d['name']}</b>\n   ID: <code>{d['id']}</code>\n\n"
    
    text += "💡 Gunakan: <code>/melolo detail <bookId></code> untuk melihat detail."
    await message.answer(text, parse_mode="HTML")


async def cmd_melolo_detail(message: Message, args: list[str]) -> None:
    if not args:
        await message.answer("⚠️ Harap masukkan ID Drama! Contoh: <code>/melolo detail 123456</code>")
        return
    
    book_id = args[0]
    detail = await fetch_melolo_detail(book_id)
    
    if not detail:
        await message.answer("😔 Drama tidak ditemukan atau ID salah.")
        return

    title = detail.get("series_title", "No Title")
    desc = detail.get("series_intro", "Tidak ada deskripsi.")
    video_list = detail.get("video_list", [])
    
    text = (
        f"🎬 <b>{title}</b>\n\n"
        f"📝 <b>Deskripsi:</b>\n{desc}\n\n"
        f"📺 <b>Daftar Episode:</b>\n"
    )

    for v in video_list:
        text += f"• Episode {v.get('vid_index')}: <code>{v.get('vid')}</code>\n"
    
    if not video_list:
        text += "Tidak ada episode."

    text += f"\n💡 Gunakan: <code>/melolo stream &lt;videoId&gt;</code> untuk menonton."
    
    # Handle long text (max 4096 chars)
    if len(text) > 4000:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            await message.answer(chunk, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")


async def cmd_melolo_stream(message: Message, args: list[str]) -> None:
    if not args:
        await message.answer("⚠️ Harap masukkan Video ID! Contoh: <code>/melolo stream 789101</code>")
        return
    
    video_id = args[0]
    stream_data = await fetch_melolo_stream(video_id)
    
    if not stream_data:
        await message.answer("😔 Stream tidak tersedia.")
        return

    url = stream_data.get("main_url") or stream_data.get("backup_url")
    if not url:
        await message.answer("😔 Link stream tidak ditemukan.")
        return

    text = (
        f"🍿 <b>Link Streaming:</b>\n"
        f"<a href='{url}'>Klik di sini untuk menonton</a>\n\n"
        f"Selamat menonton! ✨"
    )
    await message.answer(text, parse_mode="HTML")
