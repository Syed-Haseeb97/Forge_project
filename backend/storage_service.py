"""
Storage service supporting both local disk and Supabase Cloud Storage.
Returns absolute URLs for all uploaded media.
"""
import os
import logging
from pathlib import Path
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("janaawaz.storage")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "reports")
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL")


def get_storage_mode() -> str:
    """Return active storage mode ('supabase' or 'local')."""
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"):
        return "supabase"
    return "local"


def check_storage_startup_warning():
    """Logs warning if using local storage without a defined PUBLIC_API_URL in production."""
    if get_storage_mode() == "local" and not os.getenv("PUBLIC_API_URL"):
        is_dev = os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes")
        if not is_dev:
            logger.warning(
                "STARTUP WARNING: PUBLIC_API_URL is unset while using local file storage. "
                "Set PUBLIC_API_URL in production so media paths are globally accessible."
            )


check_storage_startup_warning()


async def save_media(filename: str, content: bytes, content_type: Optional[str] = None) -> str:
    """
    Saves media file to Supabase Storage if credentials exist;
    otherwise saves to local UPLOAD_DIR.
    Returns an absolute public URL string.
    """
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            target_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/{SUPABASE_BUCKET}/{filename}"
            headers = {
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "apikey": SUPABASE_KEY,
                "Content-Type": content_type or "application/octet-stream",
                "x-upsert": "true",
            }
            async with httpx.AsyncClient(timeout=6.0) as client:
                res = await client.post(target_url, content=content, headers=headers)
                if res.status_code in [200, 201]:
                    return f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}"
                logger.warning(f"Supabase storage upload returned status {res.status_code}. Using local upload.")
        except Exception as e:
            logger.warning(f"Supabase storage upload exception: {e}. Falling back to local.")

    # Fallback to local storage with absolute URL
    dest = UPLOAD_DIR / filename
    dest.write_bytes(content)

    base_url = (os.getenv("PUBLIC_API_URL") or "http://localhost:8000").rstrip("/")
    return f"{base_url}/uploads/{filename}"
