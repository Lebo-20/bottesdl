"""
handlers/owner.py — Owner-only commands
Menangani update (git pull) dan restart bot.
"""

import os
import sys
import logging
import asyncio
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

router = Router(name="owner")
logger = logging.getLogger(__name__)

# Owner ID only
OWNER_ID = 5888747846

async def run_cmd_async(command: str) -> tuple:
    """Helper to run shell command and return result."""
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()

@router.message(Command("update"), F.from_user.id == OWNER_ID)
async def cmd_update(message: Message):
    """Update bot dari GitHub (Tarik Paksa)."""
    await message.answer("♻️ **Memulai Update (System Sync)...**", parse_mode="Markdown")
    
    try:
        # Detect branch
        rc, branch, _ = await run_cmd_async("git branch --show-current")
        if not branch: branch = "main" # Fallback if empty repo

        # 1. Fetch
        await run_cmd_async("git fetch origin")
        
        # 2. Reset Hard (Tarik Paksa)
        rc, stdout, stderr = await run_cmd_async(f"git reset --hard origin/{branch}")
        
        if rc == 0:
            await message.answer(f"✅ **Update Berhasil!**\n\n`{stdout[:500]}`\n\n🔄 **Bot akan dimulai ulang...**", parse_mode="Markdown")
            # Restart Bot
            os.execv(sys.executable, ['python'] + sys.argv)
        else:
            # Fallback jika origin/branch belum ada (mungkin repository masih kosong atau branch master)
            await message.answer(f"⚠️ **Reset gagal ke {branch}. Mencoba git login/pull...**", parse_mode="Markdown")
            rc, stdout, stderr = await run_cmd_async(f"git pull origin {branch}")
            if rc == 0:
                await message.answer("✅ **Pull berhasil! Restarting...**", parse_mode="Markdown")
                os.execv(sys.executable, ['python'] + sys.argv)
            else:
                await message.answer(f"❌ **Update Gagal!**\n\n`{stderr[:500]}`", parse_mode="Markdown")
            
    except Exception as e:
        await message.answer(f"❌ **Error saat update:**\n`{str(e)}`", parse_mode="Markdown")


@router.message(Command("restart"), F.from_user.id == OWNER_ID)
async def cmd_restart(message: Message):
    """Restart bot paksa."""
    await message.answer("🔄 **Memulai ulang Bot...**", parse_mode="Markdown")
    os.execv(sys.executable, ['python'] + sys.argv)
