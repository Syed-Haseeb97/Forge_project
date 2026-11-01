"""Single source of truth configuration for Jan Aawaz.

Defines standard department routing and default SLA turnaround hours.
"""
from typing import Dict

# Default SLA turnaround window in hours by severity level
DEFAULT_SLA_MAP: Dict[str, int] = {
    "critical": 24,   # 24 hours
    "high": 72,       # 3 days
    "medium": 168,    # 7 days
    "low": 336,       # 14 days
}

# Standard department routing by civic fault category
ROUTING_MAP: Dict[str, str] = {
    "road_damage": "Public Works Department",
    "bridge_damage": "Civil Engineering Division",
    "water_leak": "Water & Sewage Authority",
    "pollution": "Environmental Protection Agency",
    "streetlight": "Electricity Board",
    "garbage": "Municipal Sanitation Department",
    "drainage": "Storm Water Management",
    "other": "General Civic Administration",
}
