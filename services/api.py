"""
Services — API Client
Mengambil data dari DotDrama API.

Field mapping (obfuscated → semantic):
────────────────────────────────────────
DRAMA LIST  /dramas
  squa        → status (1=ok)
  mcase       → message
  dgiv.lint   → drama items
  dgiv.torga  → total_items
  dgiv.tpen   → total_pages
  dgiv.pdirec → current_page

DRAMA ITEM
  dcup   → id
  svari  → series_code
  nseri  → title
  ewood  → total_episodes
  dwill  → description
  pday   → cover_url
  lweek  → language
  funi   → preview_files (first ep videos)

DRAMA DETAIL  /dramas/:id
  dgiv.bswitc  → drama info
  dgiv.ebeer   → episodes[]

EPISODE
  ewheel → number
  eholi  → episode_id
  pphys  → video_files[]

VIDEO FILE
  Dbag   → quality (360P/480P/540P/720P)
  Mopp   → video_url
  Dissue → duration_seconds
  Wroll  → width
  Hdet   → height

COLLECTIONS  /collections
  dgiv[]        → collection groups
  mluck         → collection_type
  csalar[]      → items
  rbirt         → series_code
  rdinn         → description
  puser         → cover_url
"""

import logging
from typing import Optional

import aiohttp

from config import API_BASE_URL, API_TOKEN

logger = logging.getLogger(__name__)


def _headers() -> dict:
    """Default headers untuk API request."""
    return {"Authorization": f"Bearer {API_TOKEN}"}


def _format_duration(seconds: float) -> str:
    """Format durasi dari detik ke mm:ss."""
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _best_video(files: list[dict], preferred: str = "720P") -> Optional[dict]:
    """Pilih kualitas video terbaik yang tersedia."""
    quality_order = ["720P", "540P", "480P", "360P"]
    # Cari preferred dulu
    for f in files:
        if f.get("Dbag") == preferred:
            return f
    # Fallback ke urutan kualitas
    for q in quality_order:
        for f in files:
            if f.get("Dbag") == q:
                return f
    return files[0] if files else None


# ╔══════════════════════════════════════════════════════════╗
# ║                  NORMALIZED TYPES                        ║
# ╚══════════════════════════════════════════════════════════╝


def _normalize_drama(raw: dict) -> dict:
    """Normalize drama dari API response ke format internal."""
    return {
        "id": raw.get("dcup", ""),
        "series_code": raw.get("svari", ""),
        "title": raw.get("nseri", "No Title"),
        "total_episodes": raw.get("ewood", 0),
        "description": raw.get("dwill", "Tidak ada deskripsi."),
        "cover_url": raw.get("pday", ""),
        "language": raw.get("lweek", "id"),
    }


def _normalize_episode(raw: dict, drama_title: str = "") -> dict:
    """Normalize episode dari API response ke format internal."""
    files = raw.get("pphys", [])
    best = _best_video(files)
    duration = best.get("Dissue", 0) if best else 0

    return {
        "episode_id": raw.get("eholi", ""),
        "drama_id": raw.get("dcup", ""),
        "number": raw.get("ewheel", 0),
        "drama_title": drama_title,
        "duration": _format_duration(duration),
        "duration_seconds": duration,
        "video_files": files,
        "best_video": best,
    }


def _normalize_collection_item(raw: dict) -> dict:
    """Normalize collection item ke format internal."""
    return {
        "series_code": raw.get("rbirt", ""),
        "description": raw.get("rdinn", ""),
        "cover_url": raw.get("puser", ""),
        "sort_order": raw.get("sremo", 0),
        "language": raw.get("lweek", "id"),
    }


# ╔══════════════════════════════════════════════════════════╗
# ║                    API FUNCTIONS                         ║
# ╚══════════════════════════════════════════════════════════╝


async def fetch_dramas(page: int = 1, limit: int = 50) -> dict:
    """
    GET /dramas — Mengambil daftar drama.
    Returns dict with keys: dramas, total, total_pages, page
    """
    try:
        async with aiohttp.ClientSession() as session:
            params = {"page": page, "limit": limit, "lang": "id"}
            async with session.get(
                f"{API_BASE_URL}/dramas",
                params=params,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        if data.get("squa") != 1:
            logger.warning("API dramas error: %s", data.get("mcase"))
            return {"dramas": [], "total": 0, "total_pages": 0, "page": 1}

        dgiv = data.get("dgiv", {})
        raw_list = dgiv.get("lint", [])
        dramas = [_normalize_drama(d) for d in raw_list]

        return {
            "dramas": dramas,
            "total": dgiv.get("torga", 0),
            "total_pages": dgiv.get("tpen", 0),
            "page": dgiv.get("pdirec", 1),
        }

    except aiohttp.ClientError as e:
        logger.error("API Error fetch dramas: %s", e)
        return {"dramas": [], "total": 0, "total_pages": 0, "page": 1}
    except Exception as e:
        logger.error("Unexpected error fetch dramas: %s", e)
        return {"dramas": [], "total": 0, "total_pages": 0, "page": 1}


async def fetch_drama_detail(drama_id: str) -> Optional[dict]:
    """
    GET /dramas/:id — Mengambil detail drama + daftar episode.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE_URL}/dramas/{drama_id}",
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                data = await resp.json()

        if data.get("squa") != 1:
            logger.warning("API drama detail error: %s", data.get("mcase"))
            return None

        dgiv = data.get("dgiv", {})
        raw_drama = dgiv.get("bswitc", {})
        raw_episodes = dgiv.get("ebeer", [])

        drama = _normalize_drama(raw_drama)
        drama_title = drama["title"]

        episodes = [
            _normalize_episode(ep, drama_title)
            for ep in raw_episodes
        ]
        # Sort by episode number
        episodes.sort(key=lambda e: e["number"])

        drama["episodes"] = episodes

        return drama

    except aiohttp.ClientError as e:
        logger.error("API Error fetch drama %s: %s", drama_id, e)
        return None
    except Exception as e:
        logger.error("Unexpected error fetch drama %s: %s", drama_id, e)
        return None


async def fetch_collections() -> list[dict]:
    """
    GET /collections — Mengambil koleksi (hot, for you, etc).
    Returns list of collection groups.
    """
    try:
        async with aiohttp.ClientSession() as session:
            params = {"lang": "id"}
            async with session.get(
                f"{API_BASE_URL}/collections",
                params=params,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        if data.get("squa") != 1:
            logger.warning("API collections error: %s", data.get("mcase"))
            return []

        raw_collections = data.get("dgiv", [])
        result = []
        for coll in raw_collections:
            collection_type = coll.get("mluck", "unknown")
            items = [
                _normalize_collection_item(item)
                for item in coll.get("csalar", [])
            ]
            result.append({
                "type": collection_type,
                "sort": coll.get("sforce", ""),
                "items": items,
            })
        return result

    except aiohttp.ClientError as e:
        logger.error("API Error fetch collections: %s", e)
        return []
    except Exception as e:
        logger.error("Unexpected error fetch collections: %s", e)
        return []


async def fetch_categories(page: int = 1, limit: int = 100) -> list[dict]:
    """
    GET /categories — Mengambil daftar kategori.
    """
    try:
        async with aiohttp.ClientSession() as session:
            params = {"page": page, "limit": limit}
            async with session.get(
                f"{API_BASE_URL}/categories",
                params=params,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        if data.get("squa") != 1:
            return []

        dgiv = data.get("dgiv", {})
        raw_list = dgiv.get("lint", [])
        return [
            {
                "code": c.get("cseas", ""),
                "grade": c.get("rbatt", ""),
            }
            for c in raw_list
        ]

    except Exception as e:
        logger.error("Error fetch categories: %s", e)
        return []


def get_video_url(episode: dict, quality: str = "720P") -> Optional[str]:
    """
    Ambil URL video dari episode berdasarkan kualitas yang diinginkan.
    """
    files = episode.get("video_files", [])
    if not files:
        return None

    video = _best_video(files, preferred=quality)
    return video.get("Mopp") if video else None


def get_available_qualities(episode: dict) -> list[str]:
    """List kualitas video yang tersedia untuk episode."""
    files = episode.get("video_files", [])
    return sorted(
        [f.get("Dbag", "") for f in files if f.get("Dbag")],
        key=lambda q: int(q.replace("P", "")),
        reverse=True,
    )
