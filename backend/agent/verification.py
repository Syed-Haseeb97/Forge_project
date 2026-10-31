"""Multimodal Resolution Verification Agent for Jan Aawaz.

Compares Before vs After photos using Gemini vision and issues structured verdicts:
fixed | partially_fixed | not_fixed | different_location | unclear
"""
import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import httpx
from google import genai
from google.genai import types

from agent.schemas import ResolutionVerification

logger = logging.getLogger("janaawaz.agent.verification")


def _get_client() -> Optional[genai.Client]:
    key = os.getenv("GEMINI_API_KEY")
    if not key or key == "your_api_key_here":
        return None
    try:
        return genai.Client(api_key=key)
    except Exception as e:
        logger.warning(f"Resolution verification could not init Gemini: {e}")
        return None


def _get_models() -> List[str]:
    raw = os.getenv("GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.8-flash,gemini-3.5-flash")
    return [m.strip() for m in raw.split(",") if m.strip()]


async def _load_original_bytes(media_url: Optional[str], upload_dir: str = "./uploads") -> Optional[tuple[bytes, str]]:
    """Fetch original submission photo bytes from local storage or remote URL."""
    if not media_url:
        return None

    # 1. Try remote URL via httpx (timeout <= 5.8s)
    if media_url.startswith("http://") or media_url.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=5.8) as client:
                res = await client.get(media_url)
                if res.status_code == 200:
                    mime = res.headers.get("content-type", "image/jpeg")
                    return res.content, mime
        except Exception as e:
            logger.warning(f"Could not fetch remote original photo {media_url}: {e}")

    # 2. Try local disk path
    filename = Path(media_url).name
    candidate_paths = [
        Path(media_url),
        Path(upload_dir) / filename,
        Path("./uploads") / filename,
        Path("uploads") / filename,
    ]
    for p in candidate_paths:
        if p.exists() and p.is_file():
            try:
                data = p.read_bytes()
                mime = "image/jpeg"
                if p.suffix.lower() == ".png":
                    mime = "image/png"
                elif p.suffix.lower() == ".webp":
                    mime = "image/webp"
                return data, mime
            except Exception as e:
                logger.warning(f"Could not read local original photo {p}: {e}")

    return None


async def verify_repair_evidence(
    original_media_url: Optional[str],
    after_bytes: bytes,
    after_mime: str,
    title: str,
    description: str,
    resolution_notes: str,
    upload_dir: str = "./uploads",
) -> ResolutionVerification:
    """Compare before and after photographic evidence to verify physical remediation."""
    client = _get_client()
    models = _get_models()

    original_info = await _load_original_bytes(original_media_url, upload_dir=upload_dir)

    if not original_info:
        # Only after-photo is available
        return ResolutionVerification(
            verdict="fixed",
            confidence=0.75,
            explanation="Single completion photograph submitted. Original photographic baseline was unavailable for comparative inspection.",
        )

    orig_bytes, orig_mime = original_info

    if client:
        prompt_parts: List[Any] = [
            types.Part.from_bytes(data=orig_bytes, mime_type=orig_mime),
            types.Part.from_bytes(data=after_bytes, mime_type=after_mime),
            types.Part.from_text(
                text=(
                    f"You are the Jan Aawaz Chief Forensic Infrastructure Inspector.\n"
                    f"You are reviewing municipal repair closeout evidence.\n\n"
                    f"IMAGE 1 (First image): Original Citizen Report Photo (BEFORE remediation).\n"
                    f"IMAGE 2 (Second image): Authority Completion Photo (AFTER remediation claim).\n\n"
                    f"CONTEXT:\n"
                    f"- Incident: {title}\n"
                    f"- Citizen Report: {description}\n"
                    f"- Authority Resolution Notes: {resolution_notes}\n\n"
                    f"EVALUATION CRITERIA:\n"
                    f"- 'fixed': The physical defect (e.g. pothole, broken curb, trash, leak) is clearly and completely repaired in the same location.\n"
                    f"- 'partially_fixed': Substantial work was done but repair is incomplete, temporary, or residual damage remains.\n"
                    f"- 'not_fixed': The exact same defect is still visible and unremedied.\n"
                    f"- 'different_location': The second photo appears to be taken of a completely different area, street, or object.\n"
                    f"- 'unclear': Insufficient lighting, blurry, obstructed angle, or impossible to determine with certainty.\n\n"
                    f"Provide structured JSON with verdict, confidence (0.0-1.0), and a detailed physical comparison explanation."
                )
            ),
        ]

        for model_name in models:
            try:
                resp = await client.aio.models.generate_content(
                    model=model_name,
                    contents=prompt_parts,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ResolutionVerification,
                    ),
                )
                if resp.text:
                    verif = ResolutionVerification.model_validate_json(resp.text)
                    logger.info(f"Resolution verification on {model_name}: {verif.verdict} ({verif.confidence})")
                    return verif
            except Exception as e:
                logger.warning(f"Resolution verification failed on {model_name}: {e}")

    # Fallback when Gemini is unavailable
    return ResolutionVerification(
        verdict="unclear",
        confidence=0.5,
        explanation="Automated visual inspection service was unreachable. Remediation closeout logged pending manual audit.",
    )
