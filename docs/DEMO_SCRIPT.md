# ⏱️ Jan Aawaz (जनAawaz) – 3-Minute Live Judging Script

> **Hackathon Scoring Focus**:
> 1. **Technical Depth (20 pts)**
> 2. **AI Reasoning / Agentic Execution (25 pts)**
> 3. **Relevance / Real-World Impact (25 pts)**
> 4. **Live Demo Robustness (30 pts)**

---

### [0:00 - 0:35] Problem & Real-World Impact (25 pts)
**Speaker**:
"Distinguished judges, civic grievances in India usually disappear into a bureaucratic black hole. A citizen reports a severe water main burst or pothole cluster; weeks pass with zero visibility, no statutory timeline, and eventually contractors mark it 'resolved' without touching the site.

Welcome to **Jan Aawaz (जनAawaz)**—an autonomous civic triage, municipal dispatch, and public accountability engine. 

Notice our core rule: **Zero dummy data.** Every ticket, map cluster, and briefing you see right now is computed live from real citizen submissions, live microclimate weather, OpenStreetMap geospatial data, and Supabase PostgreSQL.

Notice how accessible it is: in our citizen portal, we don't just dump technical jargon. Any resident can click **जन संवाद (Plain-Language Explainer)** in 8 Indian languages—Hindi, Tamil, Telugu, Bengali, Marathi, and more—and press **Listen** to hear an audible briefing of what happened and what the municipal deadline is via browser speech synthesis."

*(Action: Click language dropdown to 'हिन्दी (Hindi)', click 'Listen' to let judges hear speech playback).*

---

### [0:35 - 1:25] AI Reasoning & Agentic Multi-Signal Pipeline (25 pts)
**Speaker**:
"Now let's look at the heart of Jan Aawaz: **Autonomous Agentic Triage**.

When a citizen uploads an incident photo—like this deep pothole cluster near an intersection—our backend doesn't just ask an LLM for an ad-hoc guess. It runs a **6-step correlated agent pipeline**:
1. **Understand Evidence**: Multimodal Gemini vision inspects depth, visible hazards (exposed pipes, live wires), and initial severity.
2. **Reverse Geocoding**: Nominatim resolves exact road and neighborhood boundaries.
3. **Microclimate Weather**: Open-Meteo forecasts precipitation and flood probability over the next 24 hours.
4. **Sensitive Sites**: OpenStreetMap Overpass queries schools, hospitals, and clinics within 250 meters.
5. **Recurrence**: Database proximity check detects if nearby repeat failures exist.
6. **Correlated Decision**: Gemini synthesizes these environmental signals.

Look right here at our **AI Reasoning Trace**: notice how the priority was automatically elevated from Medium to High because a primary school is 120 meters away and heavy rain is forecast tonight. The rationale is fully audited and visible to the public."

*(Action: Expand the 'AI Reasoning Trace' card in ReportDetail; point to the Nominatim, Weather, Overpass, and Rationale badges).*

---

### [1:25 - 2:05] Autonomous Dispatch & SLA Watchdog (20 pts - Technical Depth)
**Speaker**:
"Next: what happens after triage? Jan Aawaz doesn't wait for a human clerk.

1. **Autonomous Municipal Dispatch**: An asynchronous background agent drafts a formal government work order in English and regional language, complete with docket ID, severity, SLA deadline, and a clickable Google Maps link, dispatched immediately to the official municipal inbox.
2. **SLA Watchdog Worker**: In production, tickets have statutory SLAs—24 hours for critical, 72 hours for high. Our background watchdog worker monitors all active tickets.

For this live demo, we built in **Demo Time Acceleration** via `SLA_TIME_SCALE=3600`. Watch what happens: as deadline thresholds elapse, the watchdog autonomously escalates:
- **Level 1**: Urgent reminder dispatched to Department Head.
- **Level 2**: Formal escalation to Municipal Commissioner.
- **Level 3**: The ticket is branded with a public, immutable **OVERDUE** banner on the city dashboard.

And our test suite proves the watchdog is 100% idempotent—running it repeatedly never double-escalates or spams inboxes."

*(Action: Point to the 'Demo Time Compression Active' banner on Dashboard and the Level 1/2 Watchdog escalation ribbons on ReportDetail).*

---

### [2:05 - 2:40] AI Resolution Audit & Fraud Prevention (20 pts - Technical Depth & Robustness)
**Speaker**:
"Here is our biggest breakthrough for municipal integrity: **Multimodal Resolution Auditing**.

Historically, dishonest contractors close tickets by uploading a photo of a clean street taken 2 miles away, or an unresolved patch. 

In Jan Aawaz, when an authority submits closure proof, our AI Inspector loads the baseline photo and compares before-and-after evidence. If the verdict is `not_fixed` or `different_location`, the system **strictly rejects closure**, keeps the ticket In Progress, logs an audit strike on the timeline, and refuses to mark it resolved.

Even after closure, the citizen has the ultimate say: a resident can click **Dispute**, which instantly reopens the docket."

*(Action: Show the Before & After Resolution Proof card with the green 'Fixed' AI verification badge and the citizen Dispute button).*

---

### [2:40 - 3:00] Live Robustness, Open311 & Wrap Up (30 pts - Robustness)
**Speaker**:
"To conclude:
- **Production Architecture**: FastAPI + Async SQLAlchemy on Supabase PostgreSQL, PyJWT role guards, and Docker containerization.
- **Interoperability**: Native Open311 GeoReport v2 compliance (`/api/open311/v2/services.json`) compatible with international civic aggregators.
- **Resilience**: Every external API has a 6-second timeout with resilient heuristic fallbacks and an automated database migration engine (`ensure_schema()`).
- **Continuous Integration**: 7-test automated PyTest suite and Vite production builds running on GitHub Actions.

Jan Aawaz turns citizen grievances from a black hole into transparent, automated public accountability. Thank you!"
