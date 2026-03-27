"""
Keyboards — Inline keyboard builders
Semua keyboard yang digunakan oleh bot dikumpulkan di sini.
"""

import math
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import GROUP_LINK, ADMIN_USERNAME, EPISODES_PER_PAGE, DRAMAS_PER_PAGE


# ╔══════════════════════════════════════════════════════════╗
# ║                   MAIN MENU                             ║
# ╚══════════════════════════════════════════════════════════╝


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Keyboard utama yang muncul saat /start."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🚀 Buka Aplikasi",
            callback_data="menu:dramas:1",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔍 Cari Drama",
            callback_data="menu:search",
        ),
        InlineKeyboardButton(
            text="👑 Langganan VIP",
            callback_data="menu:vip",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="👤 Profil & Afiliasi",
            callback_data="menu:profile",
        ),
        InlineKeyboardButton(
            text="💬 Gabung Grup",
            url=GROUP_LINK,
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="📞 Hubungi Admin",
            url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}",
        )
    )

    return builder.as_markup()


# ╔══════════════════════════════════════════════════════════╗
# ║                  DRAMA LIST                             ║
# ╚══════════════════════════════════════════════════════════╝


def drama_list_keyboard(
    dramas: list[dict],
    page: int = 1,
    total_pages: int = 1,
    nav_prefix: str = "menu:dramas:",
) -> InlineKeyboardMarkup:
    """Keyboard daftar drama dengan pagination."""
    builder = InlineKeyboardBuilder()

    offset = (page - 1) * DRAMAS_PER_PAGE
    for i, drama in enumerate(dramas, offset + 1):
        title = drama["title"]
        eps = drama.get("total_episodes", "?")
        builder.row(
            InlineKeyboardButton(
                text=f"{i}. {title} • {eps} Ep",
                callback_data=f"drama:{drama['id']}",
            )
        )

    # ── Navigasi halaman ──
    nav_buttons: list[InlineKeyboardButton] = []

    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Sebelumnya",
                callback_data=f"{nav_prefix}{page - 1}",
            )
        )

    nav_buttons.append(
        InlineKeyboardButton(
            text=f"📄 {page}/{total_pages}",
            callback_data="noop",
        )
    )

    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text="➡️ Selanjutnya",
                callback_data=f"{nav_prefix}{page + 1}",
            )
        )

    if total_pages > 1:
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(text="🏠 Menu Utama", callback_data="menu:home")
    )

    return builder.as_markup()


def melolo_list_keyboard(
    dramas: list[dict],
    offset: int = 0,
    has_more: bool = True,
    nav_prefix: str = "melolo:foryou:",
) -> InlineKeyboardMarkup:
    """Keyboard daftar drama Melolo."""
    builder = InlineKeyboardBuilder()

    for drama in dramas:
        title = drama.get("name") or "No Title"
        book_id = drama.get("id") or ""
        builder.row(
            InlineKeyboardButton(
                text=f"🎬 {title}",
                callback_data=f"melolo_detail:{book_id}",
            )
        )

    nav_buttons = []
    if offset > 0:
        prev_offset = max(0, offset - 20)
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Sebelumnya", callback_data=f"{nav_prefix}{prev_offset}"))
    
    if has_more:
        next_offset = offset + 20
        nav_buttons.append(InlineKeyboardButton(text="Selanjutnya ➡️", callback_data=f"{nav_prefix}{next_offset}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Menu Melolo", callback_data="melolo:home"))
    builder.row(InlineKeyboardButton(text="🏠 Menu Utama", callback_data="menu:home"))

    return builder.as_markup()


# ╔══════════════════════════════════════════════════════════╗
# ║                 DRAMA DETAIL                            ║
# ╚══════════════════════════════════════════════════════════╝


def drama_detail_keyboard(
    drama_id: str,
    episodes: list[dict],
    page: int = 0,
) -> InlineKeyboardMarkup:
    """Keyboard detail drama — grid episode tiled (3 kolom)."""
    builder = InlineKeyboardBuilder()

    total_pages = max(1, math.ceil(len(episodes) / EPISODES_PER_PAGE))
    all_eps = list(episodes)
    start = page * EPISODES_PER_PAGE
    end = start + EPISODES_PER_PAGE
    page_episodes = all_eps[start:end]

    # ── Episode grid (Tiled Numbers) ──
    for ep in page_episodes:
        ep_num = ep["number"]
        builder.button(
            text=f"{ep_num}",
            callback_data=f"ep:{drama_id}:{ep_num}",
        )
    builder.adjust(3) # 3 Kolom sesuai gambar

    # ── Navigasi halaman ──
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Halaman", callback_data=f"ep_page:{drama_id}:{page - 1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Selanjutnya ➡️", callback_data=f"ep_page:{drama_id}:{page + 1}"))

    if total_pages > 1:
        builder.row(*nav_buttons)

    # ── Kembali & Search ──
    builder.row(InlineKeyboardButton(text="🔍 Cari Drama Lain", callback_data="menu:search"))
    builder.row(
        InlineKeyboardButton(text="🔙 Kembali", callback_data="menu:dramas:1"),
        InlineKeyboardButton(text="🏠 Menu Utama", callback_data="menu:home"),
    )

    return builder.as_markup()


# ╔══════════════════════════════════════════════════════════╗
# ║                 EPISODE PLAYER                          ║
# ╚══════════════════════════════════════════════════════════╝


def episode_player_keyboard(
    drama_id: str,
    episode_number: int,
    total_episodes: int,
    available_qualities: list[str] | None = None,
    episodes: list[dict] | None = None, # Mendukung Grid di Player
) -> InlineKeyboardMarkup:
    """Keyboard player dengan Grid Episode sesuai gambar user."""
    builder = InlineKeyboardBuilder()

    # 1. Episode Grid (Jika data episodes tersedia)
    if episodes:
        all_eps = list(episodes)
        # Tentukan halaman berdasarkan episode_number
        page = (episode_number - 1) // EPISODES_PER_PAGE
        start = page * EPISODES_PER_PAGE
        end = start + EPISODES_PER_PAGE
        page_items = all_eps[start:end]
        total_p = max(1, math.ceil(len(all_eps) / EPISODES_PER_PAGE))
        
        for ep in page_items:
            e_num = ep.get("number") or ep.get("ep") or 0
            # Highlight episode saat ini
            p_text = f"【 {e_num} 】" if e_num == episode_number else f"{e_num}"
            builder.button(text=p_text, callback_data=f"ep:{drama_id}:{e_num}")
        builder.adjust(3) # Grid 3 Kolom

        # Navigasi halaman grid
        nav_p = []
        if page > 0:
            nav_p.append(InlineKeyboardButton(text="⬅️ Halaman", callback_data=f"ep_page:{drama_id}:{page - 1}"))
        nav_p.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_p}", callback_data="noop"))
        if page < total_p - 1:
            nav_p.append(InlineKeyboardButton(text="Selanjutnya ➡️", callback_data=f"ep_page:{drama_id}:{page + 1}"))
        builder.row(*nav_p)

    # 2. Quality selection
    if available_qualities and len(available_qualities) > 1:
        quality_buttons = []
        for q in available_qualities:
            quality_buttons.append(InlineKeyboardButton(text=f"📺 {q}", callback_data=f"quality:{drama_id}:{episode_number}:{q}"))
        builder.row(*quality_buttons)

    # 3. Action Buttons
    builder.row(InlineKeyboardButton(text="🔍 Cari Drama Lain", callback_data="menu:search"))
    builder.row(
        InlineKeyboardButton(text="📋 Daftar Episode", callback_data=f"drama:{drama_id}"),
        InlineKeyboardButton(text="🏠 Menu Utama", callback_data="menu:home"),
    )

    return builder.as_markup()


# ╔══════════════════════════════════════════════════════════╗
# ║                   MISC                                  ║
# ╚══════════════════════════════════════════════════════════╝


def back_to_home_keyboard() -> InlineKeyboardMarkup:
    """Keyboard sederhana kembali ke menu utama."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏠 Menu Utama", callback_data="menu:home")
    )
    return builder.as_markup()
