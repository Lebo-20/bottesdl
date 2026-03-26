"""
Middleware untuk menghapus semua pesan user dan bot ketika ada perintah baru.
Memberikan kesan bot yang bersih dan terfokus.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, TelegramObject, CallbackQuery
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)

SESSION_KEY = "cleanup_ids"

async def add_to_cleanup(state: FSMContext, message_id: int):
    """Tambahkan ID pesan ke daftar cleanup."""
    data = await state.get_data()
    ids: List[int] = data.get(SESSION_KEY, [])
    if message_id not in ids:
        ids.append(message_id)
        await state.update_data({SESSION_KEY: ids})

async def perform_cleanup(bot: Bot, state: FSMContext, chat_id: int):
    """Hapus semua pesan yang terdaftar."""
    data = await state.get_data()
    ids: List[int] = data.get(SESSION_KEY, [])
    
    if not ids:
        return
        
    for mid in ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass # Lewati jika sudah terhapus atau kadaluarsa
            
    # Reset daftar
    await state.update_data({SESSION_KEY: []})


class CleanupMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Any],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        state: FSMContext = data.get("state")
        bot: Bot = data.get("bot")
        
        # 1. Jika ini PESAN (User mengirim sesuatu)
        if isinstance(event, Message):
            chat_id = event.chat.id
            text = event.text or ""
            
            # Ambil state saat ini (jika ada)
            current_state = ""
            if state:
                st = await state.get_state()
                current_state = str(st).lower() if st else ""
            
            # Jika ini PERINTAH BARU atau sedang dalam mode SEARCH
            if text.startswith("/") or "search" in current_state:
                if bot and state:
                    await perform_cleanup(bot, state, chat_id)
            
            # Tambahkan pesan USER saat ini ke daftar
            if state:
                await add_to_cleanup(state, event.message_id)
            
            # Jalankan handler
            result = await handler(event, data)
            
            # Jika bot membalas dengan pesan, tambahkan ke daftar
            if state and isinstance(result, Message):
                await add_to_cleanup(state, result.message_id)
            
            return result

        # 2. Jika ini CALLBACK (User menekan tombol)
        elif isinstance(event, CallbackQuery):
            # Di sini kita biasanya tidak menghapus pesan (hanya edit)
            # Namun kita pastikan pesan bot yang saat ini (tempat tombol berada) ada di daftar
            if event.message:
                await add_to_cleanup(state, event.message.message_id)
            
            return await handler(event, data)

        return await handler(event, data)
