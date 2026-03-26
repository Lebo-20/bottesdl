"""
handlers/vigloo.py — Vigloo Handlers
Refactored for robust data parsing, validation, and video downloading.
"""

import os
import logging
import math
import asyncio
from typing import List, Optional, Any, Dict

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, URLInputFile, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import time
from services.catbox import upload_to_catbox
from services.tele_client import send_file_via_telethon

from vigloo_api import (
    search_vigloo,
    fetch_vigloo_tabs,
    fetch_vigloo_tab_content,
    fetch_vigloo_drama_detail,
    fetch_vigloo_episodes,
)
from player import (
    get_vigloo_stream_and_subs, 
    format_vigloo_drama_markdown,
    download_vigloo_video,
)
from keyboards.inline import back_to_home_keyboard

router = Router(name="vigloo")
logger = logging.getLogger(__name__)

VIGLOO_PER_PAGE = 5
EPISODES_PER_GRID = 12


class ViglooState(StatesGroup):
    waiting_for_search = State()
    waiting_for_id = State()


# ── Menu & Keyboards ───────────────────────────────────────

def vigloo_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔍 Search Drama", callback_data="vmenu:search"))
    builder.row(
        InlineKeyboardButton(text="🔥 Popular", callback_data="vmenu:popular"),
        InlineKeyboardButton(text="📂 Browse Tags", callback_data="vmenu:browse"),
    )
    builder.row(InlineKeyboardButton(text="🏠 Menu Utama", callback_data="menu:home"))
    return builder.as_markup()


def vigloo_list_keyboard(
    items: List[Dict[str, Any]],
    page: int = 1,
    total_pages: int = 1,
    nav_prefix: str = "vlist:",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for i, item in enumerate(items, (page - 1) * VIGLOO_PER_PAGE + 1):
        title = item.get("title") or item.get("name") or "No Title"
        program_id = item.get("id") or item.get("programId")
        builder.row(
            InlineKeyboardButton(
                text=f"{i}. {title}",
                callback_data=f"vdrama:{program_id}",
            )
        )

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"{nav_prefix}{page - 1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"{nav_prefix}{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Kembali", callback_data="vigloo:home"))
    return builder.as_markup()


def vigloo_detail_keyboard(
    program_id: int,
    season_id: int,
    episodes: List[Dict[str, Any]],
    page: int = 0,
) -> InlineKeyboardMarkup:
    """Keyboard detail drama Vigloo — grid tiled (3 kolom)."""
    builder = InlineKeyboardBuilder()

    ep_list = list(episodes)
    total_pages = max(1, math.ceil(len(ep_list) / EPISODES_PER_GRID))
    start = page * EPISODES_PER_GRID
    end = start + EPISODES_PER_GRID
    page_episodes = ep_list[start:end]

    # ── Episode grid (Tiled Numbers) ──
    for ep in page_episodes:
        ep_val = ep.get("number") or ep.get("ep") or ep.get("episode")
        ep_num = str(ep_val) if ep_val is not None else "?"
        
        builder.button(
            text=f"{ep_num}",
            callback_data=f"vep:{season_id}:{ep_num}",
        )
    builder.adjust(3) # 3 Kolom sesuai gambar

    # ── Navigasi halaman ──
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Halaman", callback_data=f"vpep:{program_id}:{season_id}:{page - 1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Selanjutnya ➡️", callback_data=f"vpep:{program_id}:{season_id}:{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    # ── Action Buttons ──
    builder.row(InlineKeyboardButton(text="🔍 Cari Drama Lain", callback_data="vmenu:search"))
    builder.row(
        InlineKeyboardButton(text="🔙 Kembali", callback_data="vigloo:home"),
        InlineKeyboardButton(text="🏠 Menu Utama", callback_data="menu:home"),
    )
    return builder.as_markup()


# ── Commands ───────────────────────────────────────────────

async def show_vigloo_main_menu(message: Message) -> None:
    """Menampilkan menu utama Vigloo."""
    text = (
        "✨ *Vigloo Streaming* ✨\n\n"
        "Cari dan tonton drama Vigloo favoritmu!\n\n"
        "📖 *Commands:* \n"
        "• `/vigloo` - Tampilkan menu utama\n"
        "• `/vigloo search <judul>` - Cari drama\n"
        "• `/vigloo play <seasonId> <ep>` - Putar langsung\n"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=vigloo_main_menu())


@router.message(Command("vigloo"))
async def cmd_vigloo(message: Message, command: CommandObject, state: FSMContext) -> None:
    """Entry point /vigloo dengan menu dan sub-perintah."""
    logger.info("Command /vigloo received")
    await state.clear()
    
    if not command or not command.args:
        await show_vigloo_main_menu(message)
        return

    # Handle sub-commands manually based on first arg
    args = command.args.split()
    sub_cmd = args[0].lower()

    if sub_cmd == "play":
        if len(args) >= 3:
            try:
                season_id = int(args[1])
                ep = int(args[2])
                await perform_vigloo_play(message, season_id, ep)
            except ValueError:
                await message.answer("⚠️ Season ID dan Episode harus berupa angka.")
        else:
            await message.answer("🎬 Gunakan format: `/vigloo play <seasonId> <ep>`", parse_mode="Markdown")
    else:
        # Search for the whole string if no special command found
        query = command.args.strip()
        if query.lower().startswith("search "):
            query = query[7:].strip()
        await perform_vigloo_search(message, state, query)


# ── Search & Detail Functions ──────────────────────────────

@router.callback_query(F.data == "vmenu:search")
async def cb_vigloo_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    logger.info("VMenu Search clicked")
    await callback.answer()
    await callback.message.answer("🔍 Silakan ketik judul drama Vigloo yang ingin dicari atau masukkan *ID Drama*:", parse_mode="Markdown")
    await state.set_state(ViglooState.waiting_for_search)


@router.message(ViglooState.waiting_for_search)
async def handle_vigloo_search_msg(message: Message, state: FSMContext) -> None:
    logger.info("Search query received: %s", message.text)
    query = message.text.strip()
    await state.clear()
    await perform_vigloo_search(message, state, query)


async def perform_vigloo_search(message: Message, state: FSMContext, query: str, page: int = 1) -> None:
    loading = await message.answer(f"🔍 Mencari *{query}* di Vigloo...", parse_mode="Markdown")
    results = await search_vigloo(query, limit=50)
    
    try: await loading.delete()
    except: pass

    if results is None:
        await message.answer("⚠️ Token expired atau masalah koneksi. Coba lagi nanti.", reply_markup=back_to_home_keyboard())
        return

    if not results:
        if query.isdigit():
            await show_vigloo_drama_detail(message, int(query))
            return
            
        await message.answer(
            f"😔 Tidak ditemukan drama dengan judul `{query}`.\n\n"
            "Silakan masukkan *Program ID* jika Anda mengetahuinya:",
            parse_mode="Markdown",
            reply_markup=back_to_home_keyboard()
        )
        await state.set_state(ViglooState.waiting_for_id)
        return

    matched = list(results)
    total = len(matched)
    total_pages = math.ceil(total / VIGLOO_PER_PAGE)
    start_idx = (page - 1) * VIGLOO_PER_PAGE
    end_idx = start_idx + VIGLOO_PER_PAGE
    page_items = matched[start_idx:end_idx]

    text = f"🔍 *Hasil Vigloo untuk:* `{query}`\n📊 Ditemukan *{total}* drama\n\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, item in enumerate(page_items, start_idx + 1):
        title = item.get("title") or item.get("name") or "No Title"
        text += f"*{i}. {title}*\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += "👇 Pilih drama di bawah:"

    nav_prefix = f"vsp:{query}:"
    keyboard = vigloo_list_keyboard(page_items, page, total_pages, nav_prefix)
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(F.data.startswith("vsp:"))
async def cb_vigloo_search_pagination(callback: CallbackQuery, state: FSMContext) -> None:
    logger.info("VSearch Pagination clicked: %s", callback.data)
    parts = callback.data.split(":")
    query = parts[1]
    page = int(parts[2])
    
    await callback.answer()
    results = await search_vigloo(query, limit=50)
    if not results:
        await callback.message.edit_text("❌ Hasil tidak ditemukan.")
        return

    matched = list(results)
    total_pages = math.ceil(len(matched) / VIGLOO_PER_PAGE)
    start_idx = (page - 1) * VIGLOO_PER_PAGE
    end_idx = start_idx + VIGLOO_PER_PAGE
    page_items = matched[start_idx:end_idx]

    text = f"🔍 *Hasil Vigloo untuk:* `{query}`\n📊 Ditemukan *{len(matched)}* drama\n\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, item in enumerate(page_items, start_idx + 1):
        title = item.get("title") or item.get("name") or "No Title"
        text += f"*{i}. {title}*\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += "👇 Pilih drama di bawah:"

    nav_prefix = f"vsp:{query}:"
    keyboard = vigloo_list_keyboard(page_items, page, total_pages, nav_prefix)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)


@router.message(ViglooState.waiting_for_id)
async def handle_vigloo_id_input(message: Message, state: FSMContext) -> None:
    logger.info("ID input received: %s", message.text)
    query = message.text.strip()
    if not query.isdigit():
        await message.answer("⚠️ Harap masukkan *Program ID* dalam bentuk angka.", parse_mode="Markdown")
        return
    await state.clear()
    await show_vigloo_drama_detail(message, int(query))


async def show_vigloo_drama_detail(target: Message | CallbackQuery, program_id: int) -> None:
    """Helper untuk menampilkan detail drama Vigloo."""
    logger.info("Showing detail for program: %s", program_id)
    is_callback = isinstance(target, CallbackQuery)
    message = target.message if is_callback else target

    loading = await message.answer("⏳ Memuat detail drama...")
    detail = await fetch_vigloo_drama_detail(program_id)
    
    try: await loading.delete()
    except: pass

    if detail is None:
        await message.answer("⚠️ Token expired atau data gagal dimuat.", reply_markup=back_to_home_keyboard())
        return

    seasons = detail.get("seasons", [])
    season_id = seasons[0].get("id") if seasons and isinstance(seasons, list) else (detail.get("seasonId") or detail.get("defaultSeasonId"))
    
    if season_id is None:
        await message.answer("❌ *Season tidak ditemukan* untuk drama ini.", parse_mode="Markdown", reply_markup=back_to_home_keyboard())
        return

    episodes = await fetch_vigloo_episodes(program_id, season_id)
    if not episodes:
        await message.answer("😔 *Episode tidak tersedia* untuk drama ini.", parse_mode="Markdown", reply_markup=back_to_home_keyboard())
        return
    
    text = format_vigloo_drama_markdown(detail)
    cover = detail.get("cover") or detail.get("thumbnail")
    keyboard = vigloo_detail_keyboard(program_id, season_id, episodes)
    
    if cover:
        try:
            if is_callback: await target.message.delete()
            await message.answer_photo(photo=URLInputFile(cover), caption=text, 
                                       parse_mode="Markdown", reply_markup=keyboard)
            return
        except: pass

    if is_callback:
        await target.message.edit_text(text, parse_mode="Markdown", reply_markup=keyboard)
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)


@router.callback_query(F.data.startswith("vdrama:"))
async def cb_vigloo_detail_callback(callback: CallbackQuery) -> None:
    logger.info("VDrama detail clicked: %s", callback.data)
    program_id = int(callback.data.split(":")[1])
    await callback.answer()
    await show_vigloo_drama_detail(callback, program_id)


# ── Play Logic ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("vep:"))
async def cb_vigloo_preplay(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    season_id = parts[1]
    ep = parts[2]
    
    await callback.answer(f"🚀 Memproses Episode {ep}...")
    
    text = (
        f"📺 *Vigloo Episode {ep}*\n"
        f"🔹 Season ID: `{season_id}`\n\n"
        "👇 *Pilih Cara Tonton:*"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎞️ Streaming Link", callback_data=f"vplay:{season_id}:{ep}"))
    builder.row(InlineKeyboardButton(text="📥 File MP4 (Direct)", callback_data=f"vdl:{season_id}:{ep}"))
    builder.row(InlineKeyboardButton(text="🔙 Kembali", callback_data="vigloo:home"))
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("vplay:"))
async def cb_vigloo_play_callback(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    season_id = int(parts[1])
    ep_str = parts[2]
    await callback.answer("🚀 Menyiapkan link streaming...")
    
    try: ep_num = int(ep_str)
    except: ep_num = 1
    
    await perform_vigloo_play(callback.message, season_id, ep_num)


async def perform_vigloo_play(message: Message, season_id: int, ep: int) -> None:
    stream_url, cookies, subtitles = await get_vigloo_stream_and_subs(season_id, ep)
    
    if not stream_url:
        await message.answer("❌ Gagal mendapatkan link streaming.")
        return

    text = (
        f"📺 *Vigloo Play*\n🔹 Season ID: `{season_id}`\n🔹 Episode: *{ep}*\n\n"
        "💡 *Tips:* Klik tombol di bawah untuk membuka link di pemutar video."
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔗 Buka Link Stream", url=stream_url))
    
    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    
    # Subtitles
    if subtitles:
        for sub in subtitles:
            lang = sub.get("lang", "Unknown")
            sub_url = sub.get("url")
            if sub_url:
                try:
                    await message.answer_document(
                        document=URLInputFile(sub_url, filename=f"sub_{lang}_{ep}.vtt"),
                        caption=f"📄 Subtitle: *{lang}*"
                    )
                except: pass


@router.callback_query(F.data.startswith("vdl:"))
async def cb_vigloo_download(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    season_id = int(parts[1])
    ep_str = parts[2]
    
    # Safe parsing for ep
    try:
        ep = int(ep_str)
    except:
        ep = 1

    await callback.answer("⏳ Memulai proses download...")
    status_msg = await callback.message.answer(f"⏳ Sedang mendownload *Episode {ep}* dari Vigloo...\n(Ini perlu beberapa saat, mohon tunggu)", parse_mode="Markdown")
    
    # Download with retry
    file_path = None
    retries = 1
    
    # Cari subtitle Indonesia (ID) untuk softsub
    id_sub_url = None
    
    for attempt in range(retries + 1):
        stream_url, cookies, subtitles = await get_vigloo_stream_and_subs(season_id, ep)
        
        if not stream_url:
            await status_msg.edit_text("❌ Gagal mendapatkan link download.")
            return
            
        if not cookies:
            await status_msg.edit_text("⚠️ Token streaming tidak ditemukan. Gagal memproses download.")
            return

        if subtitles:
            for s in subtitles:
                if s.get("lang", "").lower() in ["id", "ind", "indonesia"]:
                    id_sub_url = s.get("url")
                    break

        file_path = await download_vigloo_video(
            stream_url, 
            f"vigloo_{season_id}_{ep}", 
            cookies=cookies,
            subtitle_url=id_sub_url
        )
        if file_path:
            break
        
        if attempt < retries:
            await status_msg.edit_text(f"⏳ Download gagal (percobaan {attempt+1}). Mencoba ambil token baru...")
            await asyncio.sleep(2)
    
    if not file_path:
        await status_msg.edit_text("❌ Download gagal setelah beberapa kali percobaan.\n\n🔄 *Fallback ke Streaming Link...*", parse_mode="Markdown")
        await asyncio.sleep(1)
        await perform_vigloo_play(callback.message, season_id, ep)
        return
    
    # Validasi & Log Ukuran File
    if not os.path.exists(file_path):
        await status_msg.edit_text("❌ File video tidak ditemukan.")
        return
        
    file_size = os.path.getsize(file_path) / (1024 * 1024)
    logger.info("Video ready to upload: %s (Size: %.2f MB)", file_path, file_size)
    await status_msg.edit_text(f"✅ Download selesai! ({file_size:.2f} MB)\n🚀 Sedang mengirim file...")
    
    # ── Upload Phase ──
    start_time = time.time()
    
    # Method 1: Telethon (Bypass Bot API limits & more stable)
    caption = f"🎬 <b>Vigloo Episode {ep}</b>\n📂 Ukuran: <code>{file_size:.2f} MB</code>"
    
    await status_msg.edit_text(f"🚀 Sedang mengirim file Episode {ep} via Stable Stream...")
    
    upload_success = await send_file_via_telethon(
        chat_id=callback.from_user.id,
        file_path=file_path,
        caption=caption
    )
    
    if upload_success:
        duration = time.time() - start_time
        logger.info("Upload success (Telethon) in %.2f seconds", duration)
        await status_msg.edit_text(f"✅ Video Episode {ep} berhasil dikirim!")
        
        # Hapus pesan pilihan cara tonton (yang ada di gambar user)
        try: await callback.message.delete()
        except: pass

        # Tombol Episode Selanjutnya
        try:
            drama = await fetch_vigloo_drama_detail(season_id)
            total = drama.get("total_episodes", 0)
            if ep < total:
                next_kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text=f"⏭️ Next Episode {ep+1}", callback_data=f"vigloo_play:{season_id}:{ep+1}")
                ]])
                await callback.message.answer(f"✅ Selesai menonton Episode {ep}. Lanjut?", reply_markup=next_kb)
        except: pass
    else:
        # Method 2: Fallback to Catbox (Direct Download Link)
        logger.warning("Telethon upload failed for ep %s, trying Catbox...", ep)
        await status_msg.edit_text("⚠️ Gagal mengirim file langsung. Mengupload ke Hosting...")
        
        catbox_url = await upload_to_catbox(file_path)
        if catbox_url:
            await callback.message.answer(
                f"✅ <b>Download Selesai!</b>\n\n🎬 Episode {ep}\n📂 Size: {file_size:.2f} MB\n\n🔗 <b>Link Download:</b>\n{catbox_url}",
                parse_mode="HTML"
            )
            upload_success = True
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Gagal mengirim video. Silakan gunakan link streaming.")

    # Send Subtitles
    if upload_success and subtitles:
        for sub in subtitles:
            lang = sub.get("lang", "Unknown")
            sub_url = sub.get("url")
            if sub_url:
                try:
                    await callback.message.answer_document(
                        document=URLInputFile(sub_url, filename=f"sub_{lang}_{ep}.vtt"),
                        caption=f"📄 Subtitle: *{lang}*",
                        request_timeout=60
                    )
                except: pass
                
    # Cleanup
    if file_path and os.path.exists(file_path):
        try: os.remove(file_path)
        except: pass
    if not upload_success:
        try: await status_msg.delete()
        except: pass


@router.callback_query(F.data == "vigloo:home")
async def cb_vigloo_home(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await show_vigloo_main_menu(callback.message)
