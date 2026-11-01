"""Citizen Tracking Token Generator for Jan Aawaz.

Generates unambiguous, human-friendly tracking tokens formatted as JA-TRK-XXXX-XXXX
excluding easily confused characters (0, O, 1, I).
"""
import secrets
import re

UNAMBIGUOUS_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
TRACKING_TOKEN_REGEX = re.compile(r"^JA-TRK-[2-9A-HJ-NP-Z]{4}-[2-9A-HJ-NP-Z]{4}$")


def generate_tracking_token() -> str:
    """Generate unambiguous tracking token (e.g. JA-TRK-A7X9-K2M4)."""
    p1 = "".join(secrets.choice(UNAMBIGUOUS_ALPHABET) for _ in range(4))
    p2 = "".join(secrets.choice(UNAMBIGUOUS_ALPHABET) for _ in range(4))
    return f"JA-TRK-{p1}-{p2}"


def is_valid_tracking_token(token: str) -> bool:
    """Validate token format strictly."""
    if not token or not isinstance(token, str):
        return False
    return bool(TRACKING_TOKEN_REGEX.match(token.strip().upper()))
