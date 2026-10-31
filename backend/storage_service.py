"""
Storage service supporting both local disk and Supabase Cloud Storage.
"""
import os
from pathlib import Path
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "reports")


async def save_media(filename: str, content: bytes, content_type: Optional[str] = None) -> str:
    """
    Saves media file to Supabase Storage if credentials exist;
    otherwise saves to local UPLOAD_DIR.
    Returns the public URL string.
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
            async with httpx.AsyncClient() as client:
                res = await client.post(target_url, content=content, headers=headers)
                if res.status_code in [200, 201]:
                    return f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{SUPABASE_BUCKET}/{filename}"
                print(f"Supabase storage upload note: status {res.status_code}. Using local upload.")
        except Exception as e:
            print(f"Supabase storage upload exception: {e}. Falling back to local.")

    # Fallback to local storage
    dest = UPLOAD_DIR / filename
    dest.write_bytes(content)
    return f"/uploads/{filename}"
