"""External API tools for the Jan Aawaz agentic triage pipeline.

All external calls:
- Timeout <= 6s
- Try/except with graceful degradation
- Caching & rate limiting where required
"""
import math
import time
import asyncio
import logging
from typing import Optional, Dict, Any, List
import httpx
from sqlalchemy import select, and_

logger = logging.getLogger("janaawaz.agent.tools")

# In-memory cache for reverse geocoding: (rounded_lat, rounded_lon) -> result
_GEOCODE_CACHE: Dict[tuple, Dict[str, Any]] = {}
_GEOCODE_LOCK = asyncio.Lock()
_LAST_NOMINATIM_TIME = 0.0


async def reverse_geocode(lat: Optional[float], lon: Optional[float]) -> Dict[str, Any]:
    """Reverse geocode coordinates using Nominatim API.
    
    - User-Agent: JanAawaz-Hackathon/1.0
    - Cached by coordinates rounded to 3 decimal places (~110m)
    - Enforces max 1 request/second to respect OpenStreetMap usage policy
    """
    if lat is None or lon is None:
        return {"locality": None, "road": None, "city": None, "display_name": None}

    cache_key = (round(float(lat), 3), round(float(lon), 3))
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    global _LAST_NOMINATIM_TIME
    async with _GEOCODE_LOCK:
        elapsed = time.time() - _LAST_NOMINATIM_TIME
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        _LAST_NOMINATIM_TIME = time.time()

        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "format": "json",
            "lat": lat,
            "lon": lon,
            "zoom": 18,
            "addressdetails": 1,
        }
        headers = {"User-Agent": "JanAawaz-Hackathon/1.0"}

        try:
            async with httpx.AsyncClient(timeout=5.5) as client:
                res = await client.get(url, params=params, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    addr = data.get("address", {})
                    locality = (
                        addr.get("suburb")
                        or addr.get("neighbourhood")
                        or addr.get("residential")
                        or addr.get("subdistrict")
                        or addr.get("city_district")
                    )
                    road = addr.get("road") or addr.get("pedestrian") or addr.get("highway")
                    city = addr.get("city") or addr.get("town") or addr.get("county") or addr.get("state_district")

                    result = {
                        "locality": locality,
                        "road": road,
                        "city": city,
                        "display_name": data.get("display_name"),
                    }
                    _GEOCODE_CACHE[cache_key] = result
                    return result
        except Exception as e:
            logger.warning(f"Nominatim reverse geocode degraded gracefully: {e}")

    # Fallback default
    fallback_res = {"locality": None, "road": None, "city": None, "display_name": None}
    _GEOCODE_CACHE[cache_key] = fallback_res
    return fallback_res


async def get_weather(lat: Optional[float], lon: Optional[float]) -> Dict[str, Any]:
    """Fetch current precipitation and 24h forecast from Open-Meteo (no API key needed)."""
    if lat is None or lon is None:
        return {
            "current_precipitation_mm": 0.0,
            "max_precip_probability_24h": 0,
            "heavy_rain_risk": False,
            "summary": "Weather unavailable (no coordinates provided)",
        }

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "precipitation,rain,weather_code",
        "hourly": "precipitation_probability,precipitation",
        "forecast_days": 2,
    }

    try:
        async with httpx.AsyncClient(timeout=5.5) as client:
            res = await client.get(url, params=params)
            if res.status_code == 200:
                data = res.json()
                current_precip = float(data.get("current", {}).get("precipitation", 0.0))
                hourly_probs = data.get("hourly", {}).get("precipitation_probability", [])
                
                # Take the next 24 hours
                next_24h_probs = hourly_probs[:24] if hourly_probs else [0]
                max_prob = max(next_24h_probs) if next_24h_probs else 0

                heavy_rain = current_precip > 1.5 or max_prob >= 60

                if heavy_rain:
                    summary = f"High precipitation risk: {max_prob}% chance of rain in next 24h (current: {current_precip}mm)"
                elif max_prob >= 30:
                    summary = f"Moderate chance of rain: {max_prob}% in next 24h (current: {current_precip}mm)"
                else:
                    summary = f"Dry conditions: {max_prob}% precipitation probability, {current_precip}mm current"

                return {
                    "current_precipitation_mm": current_precip,
                    "max_precip_probability_24h": int(max_prob),
                    "heavy_rain_risk": heavy_rain,
                    "summary": summary,
                }
    except Exception as e:
        logger.warning(f"Open-Meteo weather check degraded gracefully: {e}")

    return {
        "current_precipitation_mm": 0.0,
        "max_precip_probability_24h": 0,
        "heavy_rain_risk": False,
        "summary": "Weather data temporarily unavailable",
    }


async def get_sensitive_sites(lat: Optional[float], lon: Optional[float], radius_m: int = 250) -> Dict[str, Any]:
    """Query Overpass API for schools, hospitals, clinics, colleges, bus stations within radius_m."""
    if lat is None or lon is None:
        return {"count": 0, "sites": [], "summary": "No coordinates provided for sensitive site analysis"}

    query = f"""[out:json][timeout:5];
(
  node["amenity"~"school|hospital|clinic|college|bus_station"](around:{radius_m},{lat},{lon});
  way["amenity"~"school|hospital|clinic|college|bus_station"](around:{radius_m},{lat},{lon});
);
out center tags;"""

    url = "https://overpass-api.de/api/interpreter"

    try:
        async with httpx.AsyncClient(timeout=5.8) as client:
            res = await client.post(url, data={"data": query})
            if res.status_code == 200:
                data = res.json()
                elements = data.get("elements", [])
                sites: List[Dict[str, Any]] = []

                for el in elements:
                    tags = el.get("tags", {})
                    amenity = tags.get("amenity", "sensitive_site")
                    name = tags.get("name") or tags.get("name:en") or f"Unnamed {amenity.replace('_', ' ').capitalize()}"
                    
                    # Calculate approximate distance if center/coordinates exist
                    el_lat = el.get("lat") or el.get("center", {}).get("lat")
                    el_lon = el.get("lon") or el.get("center", {}).get("lon")
                    dist_m = None
                    if el_lat and el_lon:
                        dist_m = round(_haversine_distance(lat, lon, el_lat, el_lon))

                    sites.append({
                        "type": amenity,
                        "name": name,
                        "distance_m": dist_m,
                    })

                count = len(sites)
                if count > 0:
                    names_str = ", ".join([f"{s['name']} ({s['type']})" for s in sites[:3]])
                    if count > 3:
                        names_str += f", and {count - 3} more"
                    summary = f"{count} sensitive site(s) within {radius_m}m: {names_str}"
                else:
                    summary = f"No schools, hospitals, or transit hubs within {radius_m}m"

                return {
                    "count": count,
                    "sites": sites,
                    "summary": summary,
                }
    except Exception as e:
        logger.warning(f"Overpass sensitive sites query degraded gracefully: {e}")

    return {
        "count": 0,
        "sites": [],
        "summary": "Sensitive sites lookup timed out or returned no records",
    }


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters between two lat/lon coordinates."""
    r = 6371000  # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


async def get_recurrence(
    lat: Optional[float],
    lon: Optional[float],
    category: str,
    session=None,
    radius_m: int = 300,
) -> Dict[str, Any]:
    """Check database for existing open or in-progress reports in the same category within radius_m."""
    if lat is None or lon is None or session is None:
        return {"count": 0, "radius_m": radius_m, "category": category, "summary": "No recurrence check possible"}

    try:
        from models import Report, StatusEnum
        # Fetch active reports of same category with coordinates
        stmt = select(Report.latitude, Report.longitude).where(
            and_(
                Report.category == category,
                Report.status.in_([StatusEnum.open, StatusEnum.in_progress]),
                Report.latitude.isnot(None),
                Report.longitude.isnot(None),
            )
        )
        res = await session.execute(stmt)
        rows = res.all()

        nearby_count = 0
        for r_lat, r_lon in rows:
            if r_lat is not None and r_lon is not None:
                d = _haversine_distance(lat, lon, r_lat, r_lon)
                if d <= radius_m:
                    nearby_count += 1

        if nearby_count > 0:
            summary = f"{nearby_count} recurring open '{category}' incident(s) detected within {radius_m}m"
        else:
            summary = f"No open recurring incidents of category '{category}' within {radius_m}m"

        return {
            "count": nearby_count,
            "radius_m": radius_m,
            "category": category,
            "summary": summary,
        }
    except Exception as e:
        logger.warning(f"Recurrence check degraded gracefully: {e}")
        return {"count": 0, "radius_m": radius_m, "category": category, "summary": "Recurrence check unavailable"}
