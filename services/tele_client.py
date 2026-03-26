import logging
import asyncio
from telethon import TelegramClient, Button
from config import API_ID, API_HASH, BOT_TOKEN
from aiogram.types import InlineKeyboardMarkup

logger = logging.getLogger(__name__)

def convert_to_telethon_buttons(markup: InlineKeyboardMarkup):
    """Konversi InlineKeyboardMarkup aiogram ke format Telethon."""
    if not markup or not markup.inline_keyboard:
        return None
        
    tele_rows = []
    for row in markup.inline_keyboard:
        tele_row = []
        for btn in row:
            if btn.url:
                tele_row.append(Button.url(btn.text, btn.url))
            elif btn.callback_data:
                tele_row.append(Button.inline(btn.text, btn.callback_data.encode('utf-8')))
        if tele_row:
            tele_rows.append(tele_row)
    return tele_rows if tele_rows else None


_client = None

async def get_tele_client():
    global _client
    if _client is None:
        _client = TelegramClient('bot_session', API_ID, API_HASH)
        await _client.start(bot_token=BOT_TOKEN)
    return _client

async def send_file_via_telethon(chat_id: int, file_path: str, caption: str, reply_markup=None):
    """Mengirim file besar menggunakan Telethon dengan tombol (markup aiogram)."""
    try:
        client = await get_tele_client()
        buttons = convert_to_telethon_buttons(reply_markup)
        
        await client.send_file(
            chat_id,
            file_path,
            caption=caption,
            supports_streaming=True,
            buttons=buttons,
            parse_mode='html'
        )
        return True
    except Exception as e:
        logger.error("Telethon send_file error: %s", e)
        return False
