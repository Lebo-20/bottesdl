"""
Handlers — Drama detail & episode player
Menangani callback untuk melihat detail drama dan memutar episode.
"""

import logging
import os
import time
import asyncio

from aiogram import Router, F
from aiogram.types import CallbackQuery, URLInputFile, FSInputFile

from keyboards.inline import (
    drama_detail_keyboard,
    episode_player_keyboard,
    back_to_home_keyboard,
)
from services.api import fetch_drama_detail, get_video_url, get_available_qualities
from services.catbox import upload_to_catbox
from services.tele_client import send_file_via_telethon

router = Router(name="drama")
logger = logging.getLogger(__name__)


# ╔══════════════════════════════════════════════════════════╗
# ║                  DRAMA DETAIL                           ║
# ╚══════════════════════════════════════════════════════════╝


@router.callback_query(F.data.startswith("drama:"))
async def cb_drama_detail(callback: CallbackQuery) -> None:
    """Menampilkan detail drama + daftar episode halaman pertama."""
    drama_id = callback.data.split(":")[1]
    logger.info("User %s → Detail Drama %s", callback.from_user.id, drama_id)
    await callback.answer("⏳ Memuat detail drama...")

    drama = await fetch_drama_detail(drama_id)

    if drama is None:
        try:
            await callback.message.edit_text(
                "❌ <b>Drama tidak ditemukan.</b>\n\n"
                "Drama mungkin sudah dihapus atau tidak tersedia.",
                parse_mode="HTML",
                reply_markup=back_to_home_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                "❌ <b>Drama tidak ditemukan.</b>",
                parse_mode="HTML",
                reply_markup=back_to_home_keyboard(),
            )
        return

    episodes = drama.get("episodes", [])

    # Potong deskripsi jika terlalu panjang
    desc = drama["description"]
    if len(desc) > 300:
        desc = desc[:300] + "..."

    text = (
        f"🎬 <b>{drama['title']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎞 Total: <b>{drama['total_episodes']} Episode</b>\n"
        f"🌐 Bahasa: <b>{drama.get('language', 'id').upper()}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📝 <b>Sinopsis:</b>\n"
        f"<i>{desc}</i>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📺 <b>Pilih episode untuk ditonton:</b>"
    )

    keyboard = drama_detail_keyboard(drama_id, episodes, page=0)

    try:
        await callback.message.delete()
    except Exception:
        pass

    # Kirim poster + detail
    cover = drama.get("cover_url", "")
    if cover:
        try:
            photo = URLInputFile(cover, filename="drama_cover.jpg")
            await callback.message.answer_photo(
                photo=photo,
                caption=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return
        except Exception as e:
            logger.warning("Gagal kirim cover drama: %s", e)

    # Fallback ke teks
    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ╔══════════════════════════════════════════════════════════╗
# ║              EPISODE PAGE NAVIGATION                    ║
# ╚══════════════════════════════════════════════════════════╝


@router.callback_query(F.data.startswith("ep_page:"))
async def cb_episode_page(callback: CallbackQuery) -> None:
    """Navigasi halaman episode."""
    parts = callback.data.split(":")
    drama_id = parts[1]
    page = int(parts[2])

    logger.info(
        "User %s → Drama %s episode halaman %d",
        callback.from_user.id,
        drama_id,
        page + 1,
    )
    await callback.answer(f"📄 Halaman {page + 1}")

    drama = await fetch_drama_detail(drama_id)

    if drama is None:
        await callback.message.edit_text(
            "❌ <b>Drama tidak ditemukan.</b>",
            parse_mode="HTML",
            reply_markup=back_to_home_keyboard(),
        )
        return

    episodes = drama.get("episodes", [])
    keyboard = drama_detail_keyboard(drama_id, episodes, page=page)

    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        logger.warning("Gagal edit keyboard: %s", e)


# ╔══════════════════════════════════════════════════════════╗
# ║                 EPISODE PLAYER                          ║
# ╚══════════════════════════════════════════════════════════╝


@router.callback_query(F.data.startswith("ep:"))
async def cb_episode_play(callback: CallbackQuery) -> None:
    """Memutar episode — ambil video URL dari API."""
    parts = callback.data.split(":")
    drama_id = parts[1]
    ep_number = int(parts[2])

    logger.info("User %s → Episode %d drama %s", callback.from_user.id, ep_number, drama_id)
    await callback.answer("⏳ Memuat video episode...")

    drama = await fetch_drama_detail(drama_id)

    if drama is None:
        try:
            await callback.message.edit_text(
                "❌ <b>Drama tidak ditemukan.</b>",
                parse_mode="HTML",
                reply_markup=back_to_home_keyboard(),
            )
        except Exception:
            await callback.message.answer(
                "❌ <b>Drama tidak ditemukan.</b>",
                parse_mode="HTML",
                reply_markup=back_to_home_keyboard(),
            )
        return

    episodes = drama.get("episodes", [])
    episode = next((ep for ep in episodes if ep["number"] == ep_number), None)

    if episode is None:
        await callback.message.answer(
            f"❌ <b>Episode {ep_number} tidak ditemukan.</b>",
            parse_mode="HTML",
            reply_markup=back_to_home_keyboard(),
        )
        return

    total_episodes = drama["total_episodes"]
    video_url = get_video_url(episode, quality="720P")
    qualities = get_available_qualities(episode)

    # ── Format pesan episode ──
    text = (
        f"📺 <b>{drama['title']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"▶️ <b>Episode {ep_number}</b>\n"
        f"⏱ Durasi: {episode['duration']}\n"
        f"📺 Kualitas: {', '.join(qualities)}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    keyboard = episode_player_keyboard(
        drama_id=drama_id,
        episode_number=ep_number,
        total_episodes=total_episodes,
        available_qualities=qualities,
    )

    try:
        await callback.message.delete()
    except Exception:
        pass

    if video_url:
        target_quality = "720P" # Default quality
        status_msg = await callback.message.answer(f"⏳ Sedang mendownload *Episode {ep_number}* ({target_quality})...\n(Mungkin perlu 1-2 menit, mohon tunggu)", parse_mode="Markdown")
        
        from player import download_generic_video
        file_path = await download_generic_video(video_url, f"drama_{drama_id}_{ep_number}_{target_quality}")
        
        if file_path:
            file_size = os.path.getsize(file_path) / (1024 * 1024)
            await status_msg.edit_text(f"🚀 Sedang mengirim file Episode {ep_number} ({file_size:.2f} MB)...")
            
            # Method 1: Telethon (Mandatory Video)
            caption = f"🎬 <b>{drama.get('title', 'Unknown')}</b>\n▶️ Episode {ep_number} ({target_quality})"
            upload_success = await send_file_via_telethon(
                chat_id=callback.from_user.id,
                file_path=file_path,
                caption=caption
            )
            
            if upload_success:
                await status_msg.edit_text("✅ Video berhasil terkirim!")
            else:
                # Gagal total (Bot wajib kirim video, tapi Telegram/Telethon gagal)
                await status_msg.edit_text("❌ Gagal mengirim video secara langsung ke Telegram. Server sedang sibuk, silakan coba lagi nanti.")
            
            # Cleanup
            if os.path.exists(file_path): os.remove(str(file_path))
        else:
            await status_msg.edit_text("❌ Gagal mendownload video. Stream sedang tidak tersedia atau dilindungi.")
    else:
        await callback.message.answer(
            text + "\n\n⚠️ <b>Video tidak tersedia saat ini.</b>",
            parse_mode="HTML",
            reply_markup=keyboard,
        )


# ╔══════════════════════════════════════════════════════════╗
# ║              QUALITY SELECTION                          ║
# ╚══════════════════════════════════════════════════════════╝


@router.callback_query(F.data.startswith("quality:"))
async def cb_quality_select(callback: CallbackQuery) -> None:
    """Pilih kualitas video yang berbeda."""
    parts = callback.data.split(":")
    drama_id = parts[1]
    ep_number = int(parts[2])
    quality = parts[3]

    logger.info(
        "User %s → Quality %s for Ep %d drama %s",
        callback.from_user.id, quality, ep_number, drama_id,
    )
    await callback.answer(f"📺 Mengambil link {quality}...")

    drama = await fetch_drama_detail(drama_id)
    if drama is None:
        await callback.answer("❌ Drama tidak ditemukan", show_alert=True)
        return

    episodes = drama.get("episodes", [])
    episode = next((ep for ep in episodes if ep["number"] == ep_number), None)

    if episode is None:
        await callback.answer("❌ Episode tidak ditemukan", show_alert=True)
        return

    video_url = get_video_url(episode, quality=quality)
    qualities = get_available_qualities(episode)

    text = (
        f"📺 <b>{drama['title']}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"▶️ <b>Episode {ep_number}</b>\n"
        f"⏱ Durasi: {episode['duration']}\n"
        f"📺 Kualitas: <b>{quality}</b> ✅\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    keyboard = episode_player_keyboard(
        drama_id=drama_id,
        episode_number=ep_number,
        total_episodes=drama["total_episodes"],
        available_qualities=qualities,
    )

    if video_url:
        status_msg = await callback.message.answer(f"⏳ Sedang mendownload *Episode {ep_number}* ({quality})...\n(Mungkin perlu 1-2 menit)", parse_mode="Markdown")
        
        from player import download_generic_video
        file_path = await download_generic_video(video_url, f"drama_{drama_id}_{ep_number}_{quality}")
        
        if file_path:
            file_size = os.path.getsize(file_path) / (1024 * 1024)
            await status_msg.edit_text(f"🚀 Sedang mengirim file Episode {ep_number} ({file_size:.2f} MB)...")
            
            # Telethon (Wajib Video)
            caption = f"🎬 <b>{drama.get('title', 'Unknown')}</b>\n▶️ Episode {ep_number} ({quality})"
            upload_success = await send_file_via_telethon(
                chat_id=callback.from_user.id,
                file_path=file_path,
                caption=caption
            )
            
            if upload_success:
                try: await callback.message.delete()
                except: pass
                await status_msg.edit_text("✅ Video berhasil terkirim!")
            else:
                await status_msg.edit_text("❌ Gagal mengirim video secara langsung. Silakan coba lagi nanti.")
            
            if os.path.exists(file_path): os.remove(str(file_path))
        else:
            await status_msg.edit_text("❌ Gagal mendownload video kualitas ini.")
    else:
        await callback.answer("⚠️ Kualitas tidak tersedia", show_alert=True)
