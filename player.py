"""
player.py — Video Player & Downloader
Handles conversion, streaming links, and yt-dlp integration.
"""

import os
import logging
import asyncio
import asyncio.subprocess
from typing import List, Optional, Any, Dict, Tuple
from aiogram.types import Message

from vigloo_api import fetch_vigloo_play_url

logger = logging.getLogger(__name__)

# Temporary directory for bot downloads
TEMP_DIR = "temp_vigloo"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)


async def get_vigloo_stream_and_subs(
    season_id: int, 
    ep: int
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
    """Mendapatkan link stream, cookie, dan subtitle Vigloo."""
    play_data = await fetch_vigloo_play_url(season_id, ep)
    if not play_data:
        return None, None, None
    
    url = play_data.get("url")
    cookies = play_data.get("cookies")
    subtitles = play_data.get("subtitles")
    
    return url, cookies, subtitles


def build_vigloo_cookie_header(cookies: Dict[str, Any]) -> str:
    """Membangun string header Cookie dari dictionary cookies CloudFront."""
    if not cookies:
        return ""
    # CloudFront cookies are typically: CloudFront-Policy, CloudFront-Signature, CloudFront-Key-Pair-Id
    parts = []
    for k, v in cookies.items():
        parts.append(f"{k}={v}")
    return "; ".join(parts)


def format_vigloo_drama_markdown(detail: Dict[str, Any]) -> str:
    """Format detail drama ke Markdown."""
    title = detail.get("title") or "Unknown Title"
    synopsis = detail.get("synopsis", "Tidak ada sinopsis.")
    genres_list = detail.get("genres", [])
    genres = ", ".join([g.get("title", "") for g in genres_list]) if genres_list else "N/A"
    
    status = "Tamat" if detail.get("finished") else "Berjalan"
    
    text = (
        f"🎬 *{title}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 *Genre:* {genres}\n"
        f"📊 *Status:* {status}\n\n"
        f"📖 *Sinopsis:*\n{synopsis[:300]}...\n\n"
        f"👇 *Pilih Episode:* "
    )
    return text


async def download_vigloo_video(
    stream_url: str, 
    output_name: str, 
    cookies: Optional[Dict[str, Any]] = None,
    subtitle_url: Optional[str] = None
) -> Optional[str]:
    """Download video m3u8 menggunakan yt-dlp + aria2c + optional subtitle merge."""
    output_path = os.path.join(TEMP_DIR, f"{output_name}.mp4")
    
    # Siapkan headers
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    referer = "https://vigloo.com/"
    
    cmd = [
        "yt-dlp",
        "-o", output_path,
        "--downloader", "aria2c",
        "--downloader-args", "aria2c:-x 16 -s 16 -k 1M",
        "--user-agent", ua,
        "--add-header", f"Referer:{referer}",
        "--add-header", "Origin:https://vigloo.com",
        "--no-check-certificate",
        "--merge-output-format", "mp4"
    ]
    
    if cookies:
        cookie_str = build_vigloo_cookie_header(cookies)
        if cookie_str:
            cmd.extend(["--add-header", f"Cookie:{cookie_str}"])
    
    cmd.append(stream_url)
    
    logger.info("Starting yt-dlp download: %s", output_name)
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        if process.returncode == 0 and os.path.exists(output_path):
            logger.info("Download success: %s", output_path)
            
            # ── Softsub Merge ──
            if subtitle_url:
                with_sub_path = os.path.join(TEMP_DIR, f"{output_name}_sub.mp4")
                merged = await merge_subtitles(output_path, subtitle_url, with_sub_path)
                if merged:
                    return merged
            
            return output_path
    except Exception:
        logger.exception("Error downloading video %s:", stream_url)
    
    return None


async def merge_subtitles(video_path: str, sub_url: str, output_path: str) -> Optional[str]:
    """Download subtitle VTT dan gabungkan ke MP4 sebagai softsub."""
    import aiohttp
    sub_path = video_path.replace(".mp4", ".vtt")
    
    try:
        # 1. Download Subtitle
        async with aiohttp.ClientSession() as session:
            async with session.get(sub_url) as resp:
                if resp.status == 200:
                    with open(sub_path, "wb") as f:
                        f.write(await resp.read())
                else:
                    return None
                    
        # 2. Merge via FFmpeg (Softsub)
        # -c copy: Menyalin stream video/audio tanpa re-encode
        # -c:s mov_text: Codec untuk subtitle di MP4
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", sub_path,
            "-c", "copy",
            "-c:s", "mov_text",
            "-metadata:s:s:0", "language=ind",
            "-metadata:s:s:0", "title=Indonesia",
            output_path
        ]
        
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        
        if proc.returncode == 0 and os.path.exists(output_path):
            # Hapus file mentah
            if os.path.exists(video_path): os.remove(video_path)
            if os.path.exists(sub_path): os.remove(sub_path)
            return output_path
            
    except Exception as e:
        logger.error("Softsub merge failed: %s", e)
    
    return None


async def download_generic_video(
    url: str, 
    output_name: str
) -> Optional[str]:
    """Download video dari URL menggunakan yt-dlp + aria2c (Power Combo)."""
    output_path = os.path.join(TEMP_DIR, f"{output_name}.mp4")
    
    # User-Agent & Referer untuk bypass protection
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    cmd = [
        "yt-dlp",
        "-o", output_path,
        "--downloader", "aria2c",
        "--downloader-args", "aria2c:-x 16 -s 16 -k 1M --no-conf",
        "--user-agent", ua,
        "--no-check-certificate",
        "--format", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        url
    ]
    
    logger.info("Starting power download with yt-dlp: %s", url)
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
        
        if process.returncode == 0 and os.path.exists(output_path):
            logger.info("Power download success: %s", output_path)
            return output_path
        else:
            logger.error("yt-dlp generic download failed with code %s", process.returncode)
    except Exception:
        logger.exception("Error in power download %s:", url)
    
    return None
