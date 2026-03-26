import os
import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CATBOX_URL = "https://catbox.moe/user/api.php"

async def upload_to_catbox(file_path: str) -> Optional[str]:
    """Upload file ke Catbox.moe dan return URL."""
    if not os.path.exists(file_path):
        return None
    
    try:
        data = aiohttp.FormData()
        data.add_field('reqtype', 'fileupload')
        data.add_field('fileToUpload', open(file_path, 'rb'))
        
        async with aiohttp.ClientSession() as session:
            async with session.post(CATBOX_URL, data=data) as resp:
                if resp.status == 200:
                    url = await resp.text()
                    return url.strip()
                else:
                    logger.error("Catbox upload failed: %s", await resp.text())
    except Exception as e:
        logger.error("Catbox upload exception: %s", e)
    
    return None
