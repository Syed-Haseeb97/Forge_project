"""Gemini-powered report analysis service for Fordge Civic Triage"""
import os
import json
import re
from typing import Optional, Tuple, Dict, Any
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

DEFAULT_SLA_MAP = {
    "critical": 24,   # 24 hours (immediate hazard)
    "high": 72,       # 3 days
    "medium": 168,    # 7 days
    "low": 336,       # 14 days
}

ROUTING_MAP = {
    "road_damage": "Public Works Department",
    "bridge_damage": "Civil Engineering Division",
    "water_leak": "Water & Sewage Authority",
    "pollution": "Environmental Protection Agency",
    "streetlight": "Electricity Board",
    "garbage": "Municipal Sanitation Department",
    "drainage": "Storm Water Management",
    "other": "General Civic Administration",
}

SEVERITY_PROMPT = """You are an advanced municipal civic infrastructure triage and safety assessment AI.
Analyze this civic issue report and provide structured JSON assessment.

Your response MUST be a valid JSON object matching this schema:
{{
  "severity": "low" | "medium" | "high" | "critical",
  "analysis": "2-3 sentences analyzing the infrastructure problem, root cause risks, and public impact.",
  "recommended_action": "Specific engineering action item or repair protocol for the municipal department.",
  "safety_precautions": "Safety advice for citizens, pedestrians, or drivers in the vicinity.",
  "sla_hours": 24 | 72 | 168 | 336,
  "suggested_department": "Name of responsible city department or authority"
}}

Severity Guidelines:
- critical: Immediate risk to life or severe structural collapse (bridge cracks, uncontained toxic spills, deep sinkholes, downed live power lines). SLA: 24h.
- high: Serious safety hazard or severe infrastructure disruption (major pothole on highway, broken traffic light at busy junction, raw sewage leak). SLA: 72h.
- medium: Moderate inconvenience or degrading asset (cracked pavement, overflowing public bins, blocked storm drain before rain). SLA: 168h.
- low: Cosmetic or minor non-urgent civic maintenance (faded street signs, minor curb paint chip, small non-blocking debris). SLA: 336h.

Report Title: {title}
Category: {category}
Location: {location}
Description: {description}

Respond ONLY with valid JSON. Do not include markdown ticks if possible, or wrap in ```json```."""


def _get_client() -> Optional[genai.Client]:
    key = os.getenv("GEMINI_API_KEY")
    if not key or key == "your_api_key_here":
        return None
    try:
        return genai.Client(api_key=key)
    except Exception as e:
        print(f"Failed to initialize Gemini client: {e}")
        return None


def _fallback_triage(title: str, description: str, category: str) -> Dict[str, Any]:
    text = f"{title} {description}".lower()
    dept = ROUTING_MAP.get(category, ROUTING_MAP["other"])

    if any(w in text for w in ["collapse", "toxic", "fire", "explosion", "flood", "electrocution", "live wire", "sinkhole", "bridge crack"]):
        severity = "critical"
        analysis = "Critical infrastructure danger identified with immediate threat to life, property, or public safety."
        action = "Deploy emergency rapid response crew immediately. Secure perimeter and reroute traffic."
        safety = "Keep well clear of the affected perimeter. Do not approach and report any rapid changes to authorities."
    elif any(w in text for w in ["broken", "leak", "damage", "pothole", "sewage", "hazard", "burst", "traffic light"]):
        severity = "high"
        analysis = "High-priority infrastructure fault detected causing significant disruption or potential safety hazard."
        action = "Schedule priority maintenance crew within 72 hours. Install temporary warning signage."
        safety = "Exercise heightened caution around this area. Slow down if driving and watch for hazards."
    elif any(w in text for w in ["crack", "blockage", "accumulation", "trash", "garbage", "streetlight", "drain"]):
        severity = "medium"
        analysis = "Moderate municipal issue noted requiring standard scheduled repair to avoid escalation."
        action = "Queue for routine departmental work order."
        safety = "General public caution advised until regular repairs are completed."
    else:
        severity = "low"
        analysis = "Minor cosmetic or non-hazardous civic matter logged for routine city maintenance."
        action = "Include in upcoming neighborhood maintenance cycle."
        safety = "No immediate danger identified."

    return {
        "severity": severity,
        "analysis": analysis,
        "recommended_action": action,
        "safety_precautions": safety,
        "sla_hours": DEFAULT_SLA_MAP[severity],
        "suggested_department": dept,
    }


async def analyze_report(
    title: str,
    description: str,
    category: str,
    location: str = "Unspecified",
    media_path: Optional[str] = None,
    media_bytes: Optional[bytes] = None,
    media_mime: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns a dictionary with:
    {
        "ai_analysis": str,
        "severity": str,
        "action_plan": str,
        "safety_precautions": str,
        "sla_hours": int,
        "routed_to": str
    }
    """
    client = _get_client()

    if client:
        candidate_models = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash"]
        prompt_text = SEVERITY_PROMPT.format(
            title=title, category=category, location=location, description=description
        )

        contents = []
        if media_bytes and media_mime:
            if media_mime.startswith("image/"):
                contents.append(
                    types.Part.from_bytes(data=media_bytes, mime_type=media_mime)
                )
                prompt_text += "\n\nAn image of the issue has been attached. Carefully examine visible structural damage, cracks, water levels, or hazards to refine severity."
            elif media_mime.startswith("audio/"):
                contents.append(
                    types.Part.from_bytes(data=media_bytes, mime_type=media_mime)
                )
                prompt_text += "\n\nAn audio recording from the reporting citizen is attached. Transcribe and consider auditory cues."

        contents.append(types.Part.from_text(text=prompt_text))

        for model_name in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )
                raw = response.text or ""
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                    sev = str(data.get("severity", "medium")).lower()
                    if sev not in ["low", "medium", "high", "critical"]:
                        sev = "medium"

                    analysis = data.get("analysis", "")
                    action = data.get("recommended_action", "")
                    safety = data.get("safety_precautions", "Follow standard municipal safety guidelines.")
                    sla = int(data.get("sla_hours", DEFAULT_SLA_MAP.get(sev, 72)))
                    suggested_dept = data.get("suggested_department") or ROUTING_MAP.get(category, ROUTING_MAP["other"])

                    full_analysis = f"{analysis}\n\n**Recommended Action:** {action}"
                    return {
                        "ai_analysis": full_analysis,
                        "severity": sev,
                        "action_plan": action,
                        "safety_precautions": safety,
                        "sla_hours": sla,
                        "routed_to": suggested_dept,
                    }
            except Exception as e:
                print(f"Gemini model {model_name} attempt error: {e}")
                continue

    # Fallback to local heuristic
    fallback = _fallback_triage(title, description, category)
    full_analysis = f"{fallback['analysis']}\n\n**Recommended Action:** {fallback['recommended_action']}"
    return {
        "ai_analysis": full_analysis,
        "severity": fallback["severity"],
        "action_plan": fallback["recommended_action"],
        "safety_precautions": fallback["safety_precautions"],
        "sla_hours": fallback["sla_hours"],
        "routed_to": fallback["suggested_department"],
    }
