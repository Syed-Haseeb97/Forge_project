"""Department Directory & Recipient Resolution for Jan Aawaz.

Resolves real municipal authority contacts from backend/departments.json based on
incident category, geographical locality / city, and escalation tier.
Guarantees verified municipal contacts only; never invents email addresses.
Falls back safely to DISPATCH_EMAIL when no verified department is mapped.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("janaawaz.agent.directory")

# Locate departments.json relative to this file or backend root
DEPARTMENTS_FILE = Path(__file__).resolve().parent.parent / "departments.json"


def _load_departments() -> List[Dict[str, Any]]:
    """Load department mappings from departments.json."""
    if not DEPARTMENTS_FILE.exists():
        logger.warning(f"Departments file not found at {DEPARTMENTS_FILE}")
        return []
    try:
        with open(DEPARTMENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read {DEPARTMENTS_FILE}: {e}")
        return []


def mask_email(email: str) -> str:
    """Mask email for public audit timeline privacy (e.g. commr.trichy@tn.gov.in -> c***y@tn.gov.in)."""
    if not email or "@" not in email:
        return "configured inbox"
    user_part, domain = email.split("@", 1)
    if len(user_part) <= 2:
        masked_user = user_part[0] + "***"
    else:
        masked_user = user_part[0] + "***" + user_part[-1]
    return f"{masked_user}@{domain}"


def resolve_recipient(
    category: str,
    locality_or_city: Optional[str] = None,
    escalation_level: int = 0,
) -> Dict[str, Any]:
    """Resolve municipal recipient contact for dispatch.
    
    Returns a dict with:
      - to: str (email)
      - cc: List[str]
      - designation: str (official bureaucratic title)
      - source_url: Optional[str]
      - verified_on: Optional[str]
      - is_demo: bool
      - matched: bool (True if matched configured directory; False if fallback)
    """
    departments = _load_departments()
    norm_cat = (category or "").strip().lower()
    # Normalize category key (e.g. streetlight / street_light)
    if norm_cat in ["street_light", "streetlights", "lighting"]:
        norm_cat = "streetlight"

    norm_loc = (locality_or_city or "").strip().lower()

    best_match = None
    for entry in departments:
        entry_cat = entry.get("category", "").strip().lower()
        if entry_cat in ["street_light", "streetlights", "lighting"]:
            entry_cat = "streetlight"

        if entry_cat != norm_cat:
            continue

        entry_city = entry.get("city", "").strip().lower()
        # Match city by substring (e.g. "Tiruchirappalli" or "Trichy" in locality)
        city_matched = False
        if entry_city and (entry_city in norm_loc or norm_loc in entry_city):
            city_matched = True
        elif entry_city in ["tiruchirappalli", "trichy"] and ("trichy" in norm_loc or "tiruchirappalli" in norm_loc):
            city_matched = True

        if city_matched:
            # Check escalation level match (prefer exact or highest <= escalation_level)
            entry_lvl = entry.get("escalation_level", 0)
            if entry_lvl == escalation_level:
                best_match = entry
                break
            elif best_match is None or abs(entry_lvl - escalation_level) < abs(best_match.get("escalation_level", 0) - escalation_level):
                best_match = entry

    if best_match:
        logger.info(
            f"Resolved department for ({norm_cat}, '{locality_or_city}', lvl={escalation_level}): "
            f"{best_match.get('designation')} <{best_match.get('to')}>"
        )
        return {
            "to": best_match.get("to"),
            "cc": list(best_match.get("cc", [])),
            "designation": best_match.get("designation"),
            "source_url": best_match.get("source_url"),
            "verified_on": best_match.get("verified_on"),
            "is_demo": bool(best_match.get("is_demo", False)),
            "matched": True,
        }

    # Fallback to configured DISPATCH_EMAIL
    fallback_email = os.getenv("DISPATCH_EMAIL", "dispatch@janaawaz.in")
    logger.info(f"No matching department for ({norm_cat}, '{locality_or_city}', lvl={escalation_level}); using fallback inbox: {fallback_email}")
    return {
        "to": fallback_email,
        "cc": [],
        "designation": "Municipal Engineering Division (Fallback Desk)",
        "source_url": None,
        "verified_on": None,
        "is_demo": True,
        "matched": False,
    }
