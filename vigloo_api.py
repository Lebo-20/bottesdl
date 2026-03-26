"""
vigloo_api.py — Vigloo Core API Client
Modular component for Vigloo API interactions.
"""

import logging
import json
from typing import Optional, List, Dict, Any

import aiohttp

from config import VIGLOO_BASE_URL, VIGLOO_TOKEN

logger = logging.getLogger(__name__)


def _headers() -> dict:
    """Authentication headers for Vigloo API."""
    return {"Authorization": f"Bearer {VIGLOO_TOKEN}"}


async def vigloo_request(endpoint: str, params: Optional[dict] = None) -> Any:
    """Base request helper for Vigloo API."""
    try:
        url = f"{VIGLOO_BASE_URL}/{endpoint.lstrip('/')}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 401 or resp.status == 403:
                    logger.error("Vigloo API Token Expired or Invalid (401/403)")
                    return None
                    
                resp.raise_for_status()
                data = await resp.json()
                
                # Debug Logging
                logger.info("Vigloo API [%s] RAW: %s", endpoint, json.dumps(data)[:1000])

                # Common wrapper check
                if isinstance(data, dict):
                    if "payloads" in data:
                        return data["payloads"]
                    if "dgiv" in data:
                        return data["dgiv"]
                return data
    except Exception as e:
        logger.error("Vigloo API Request Error [%s]: %s", endpoint, e)
    return None


async def search_vigloo(query: str, limit: int = 20, lang: str = "id") -> List[Dict[str, Any]]:
    """Search for dramas by query."""
    params = {"q": query, "limit": limit, "lang": lang}
    data = await vigloo_request("search", params)
    
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "lint" in data:
        return data["lint"]
    return []


async def fetch_vigloo_tabs(lang: str = "id") -> List[Dict[str, Any]]:
    """Fetch home tabs/categories."""
    params = {"lang": lang}
    dgiv = await vigloo_request("tabs", params)
    
    if isinstance(dgiv, list):
        return dgiv
    if isinstance(dgiv, dict) and "lint" in dgiv:
        return dgiv["lint"]
    return []


async def fetch_vigloo_tab_content(tab_id: int, offset: int = 0, limit: int = 20, lang: str = "id") -> List[Dict[str, Any]]:
    """Fetch content of a specific tab."""
    params = {"offset": offset, "limit": limit, "lang": lang}
    dgiv = await vigloo_request(f"tabs/{tab_id}", params)
    
    if isinstance(dgiv, list):
        return dgiv
    if isinstance(dgiv, dict) and "lint" in dgiv:
        return dgiv["lint"]
    return []


async def get_vigloo_season_id(program_id: int, lang: str = "id") -> Optional[int]:
    """Explicitly extract seasonId from drama detail."""
    detail = await fetch_vigloo_drama_detail(program_id, lang)
    if not detail:
        return None
    
    # Priority 1: seasons[0].id
    seasons = detail.get("seasons", [])
    if isinstance(seasons, list) and len(seasons) > 0:
        s_id = seasons[0].get("id")
        if s_id: return int(s_id)
        
    # Priority 2: root keys
    s_id = detail.get("seasonId") or detail.get("defaultSeasonId")
    if s_id: return int(s_id)
    
    return None


async def fetch_vigloo_drama_detail(program_id: int, lang: str = "id") -> Optional[Dict[str, Any]]:
    """Fetch drama details."""
    params = {"lang": lang}
    data = await vigloo_request(f"drama/{program_id}", params)
    
    if isinstance(data, dict):
        # Normalization: look into 'bswitc', 'drama', or root
        drama_data = data.get("bswitc") or data.get("drama") or data
        return drama_data
    return None


async def fetch_vigloo_episodes(program_id: int, season_id: int, lang: str = "id") -> List[Dict[str, Any]]:
    """Fetch episode list for a drama/season."""
    params = {"lang": lang}
    data = await vigloo_request(f"drama/{program_id}/season/{season_id}/episodes", params)
    
    # Structure could be wrapped in 'episodes', 'ebeer' or just a list
    if isinstance(data, dict):
        ep_list = data.get("episodes") or data.get("ebeer") or data.get("lint")
        if isinstance(ep_list, list):
            return ep_list
            
    if isinstance(data, list):
        return data
        
    return []


async def fetch_vigloo_play_url(season_id: int, ep: int) -> Optional[Dict[str, Any]]:
    """Mendapatkan link streaming, cookies CloudFront, dan subtitle dari Vigloo."""
    params = {"seasonId": season_id, "ep": ep}
    data = await vigloo_request("play", params)
    
    if not isinstance(data, dict):
        return None
        
    # Vigloo structure check
    payload = data.get("payload") or data.get("play") or data
    if not isinstance(payload, dict):
        return None
        
    stream_url = payload.get("url") or payload.get("stream_url")
    cookies = payload.get("cookies") # Expecting a dict of CloudFront-*
    subtitles = payload.get("subtitles")
    
    if not stream_url:
        return None
        
    return {
        "url": stream_url,
        "cookies": cookies,
        "subtitles": subtitles
    }


async def get_vigloo_stream_url(season_id: int, ep: int) -> Optional[str]:
    """Get HLS stream URL directly."""
    params = {"seasonId": season_id, "ep": ep}
    try:
        url = f"{VIGLOO_BASE_URL}/stream"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers=_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        data = await resp.json()
                        if isinstance(data, dict):
                            # Follow wrapper normalization
                            if "payloads" in data: data = data["payloads"]
                            elif "dgiv" in data: data = data["dgiv"]
                            return data.get("stream_url") or data.get("url")
                    else:
                        text = await resp.text()
                        # If it's an M3U8 playlist, try to find the actual stream URL inside
                        import re
                        match = re.search(r'https?://[^\s\"\'\>]+', text)
                        if match:
                            return match.group(0)
                        return None
    except Exception as e:
        logger.error("Vigloo Stream Request Error: %s", e)
    return None
