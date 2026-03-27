"""
Services — Melolo API Client
Mengambil data dari Melolo API.
"""

import logging
from typing import Optional, List, Dict, Any

import aiohttp

from config import MELOLO_BASE_URL

logger = logging.getLogger(__name__)


def _headers() -> dict:
    """Default headers untuk API request."""
    return {"accept": "*/*"}


def _normalize_book(raw: dict) -> dict:
    """Normalize data buku/drama dari API Melolo."""
    return {
        "id": raw.get("book_id", ""),
        "name": raw.get("book_name", "No Title"),
        "description": raw.get("abstract", "Tidak ada deskripsi."),
        "cover": raw.get("thumb_url", ""),
    }


async def fetch_melolo_foryou(offset: int = 20) -> List[Dict[str, Any]]:
    """GET /foryou — Mengambil daftar drama untuk Anda."""
    try:
        async with aiohttp.ClientSession() as session:
            params = {"offset": offset}
            async with session.get(
                f"{MELOLO_BASE_URL}/foryou",
                params=params,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                books = data.get("books", [])
                return [_normalize_book(b) for b in books]
    except Exception as e:
        logger.error("Error fetch melolo foryou: %s", e)
        return []


async def fetch_melolo_latest() -> List[Dict[str, Any]]:
    """GET /latest — Mengambil daftar drama terbaru."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{MELOLO_BASE_URL}/latest",
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                books = data.get("books", [])
                return [_normalize_book(b) for b in books]
    except Exception as e:
        logger.error("Error fetch melolo latest: %s", e)
        return []


async def fetch_melolo_trending() -> List[Dict[str, Any]]:
    """GET /trending — Mengambil daftar drama trending."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{MELOLO_BASE_URL}/trending",
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                books = data.get("books", [])
                return [_normalize_book(b) for b in books]
    except Exception as e:
        logger.error("Error fetch melolo trending: %s", e)
        return []


async def fetch_melolo_search(query: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    """GET /search — Mengambil daftar drama yang cocok dengan query pencarian."""
    try:
        async with aiohttp.ClientSession() as session:
            params = {"query": query, "limit": limit, "offset": offset}
            async with session.get(
                f"{MELOLO_BASE_URL}/search",
                params=params,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                books = data.get("books", [])
                return [_normalize_book(b) for b in books]
    except Exception as e:
        logger.error("Error fetch melolo search: %s", e)
        return []


async def fetch_melolo_detail(book_id: str) -> Optional[Dict[str, Any]]:
    """GET /detail — Mengambil detail drama."""
    try:
        async with aiohttp.ClientSession() as session:
            params = {"bookId": book_id}
            async with session.get(
                f"{MELOLO_BASE_URL}/detail",
                params=params,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
    except Exception as e:
        logger.error("Error fetch melolo detail: %s", e)
        return None


async def fetch_melolo_stream(video_id: str) -> Optional[Dict[str, Any]]:
    """GET /stream — Mengambil stream drama."""
    try:
        async with aiohttp.ClientSession() as session:
            params = {"videoId": video_id}
            async with session.get(
                f"{MELOLO_BASE_URL}/stream",
                params=params,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()
    except Exception as e:
        logger.error("Error fetch melolo stream: %s", e)
        return None
