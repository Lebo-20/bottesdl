import logging
import asyncio
from telethon import TelegramClient
from config import API_ID, API_HASH, BOT_TOKEN

logger = logging.getLogger(__name__)

_client = None

async def get_tele_client():
    global _client
    if _client is None:
        _client = TelegramClient('bot_session', API_ID, API_HASH)
        await _client.start(bot_token=BOT_TOKEN)
    return _client

async def send_file_via_telethon(chat_id: int, file_path: str, caption: str):
    """Mengirim file besar menggunakan Telethon."""
    try:
        client = await get_tele_client()
        await client.send_file(
            chat_id,
            file_path,
            caption=caption,
            supports_streaming=True,
            parse_mode='html'
        )
        return True
    except Exception as e:
        logger.error("Telethon send_file error: %s", e)
        return False
