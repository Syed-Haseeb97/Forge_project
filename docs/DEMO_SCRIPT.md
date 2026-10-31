# ⏱️ Jan Aawaz (जनAawaz) – 3-Minute Live Judging Script

> **Hackathon Scoring Rubric (100 Points Total)**:
> 1. **Relevance / Real-World Impact / USP (25 pts)**
> 2. **AI Reasoning / Agentic Execution (25 pts)**
> 3. **Technical Depth (20 pts)**
> 4. **Live Demo Robustness (30 pts)**

---

### Segment 1: [0:00 - 0:45] Relevance, Real-World Impact & USP (25 pts)
**Speaker**:
"Distinguished judges, civic grievances in India typically disappear into a bureaucratic black hole. A citizen reports a severe water main burst or pothole cluster; weeks pass with zero transparency, no enforced timeline, and eventually contractors mark it 'resolved' without touching the site.

Welcome to **Jan Aawaz (जनAawaz)**—an autonomous civic triage, municipal dispatch, and public accountability engine designed for the Digital Governance & Civic Pulse theme.

Notice our core rule: **Zero dummy data.** Every ticket, map cluster, and briefing you see right now is computed live from real citizen submissions, live microclimate weather, OpenStreetMap geospatial data, and Supabase PostgreSQL.

Our unique selling proposition is radical citizen accessibility: in our portal, residents aren't trapped by bureaucratic jargon. Any resident can click **जन संवाद (Plain-Language Explainer)** in 8 Indian languages—Hindi, Tamil, Telugu, Kannada, Bengali, Marathi, Malayalam, and English—and press **Listen** to hear an audible briefing of what happened and what the target municipal deadline is via browser speech synthesis."

*(Action: Click language selector to 'हिन्दी (Hindi)', click 'Listen' to let judges hear speech playback).*

---

### Segment 2: [0:45 - 1:35] AI Reasoning & Agentic Execution (25 pts)
**Speaker**:
"Now let's examine the heart of Jan Aawaz: **Autonomous Agentic Triage**.

When a citizen uploads an incident photo—like this deep pothole cluster near an intersection—our backend does not ask an LLM for an ad-hoc hallucinated guess. Instead, it runs an autonomous **6-step correlated agent pipeline**:
1. **Understand Evidence**: Multimodal Gemini vision inspects depth, visible hazards (exposed pipes, live wires), and initial severity.
2. **Reverse Geocoding**: Nominatim resolves exact road and neighborhood boundaries.
3. **Microclimate Weather**: Open-Meteo forecasts precipitation and flood probability over the next 24 hours.
4. **Sensitive Sites**: OpenStreetMap Overpass queries schools, hospitals, and clinics within 250 meters.
5. **Recurrence**: Database proximity check detects if nearby repeat failures exist.
6. **Correlated Decision**: Gemini synthesizes these environmental signals with full chain-of-thought rationale.

Look right here at our **AI Reasoning Trace**: notice how the priority was automatically elevated from Medium to High because a primary school is 120 meters away and heavy rain is forecast tonight. The rationale is fully audited and visible to the public."

*(Action: Expand the 'AI Reasoning Trace' card in ReportDetail; point to the Nominatim, Weather, Overpass, and Rationale badges).*

---

### Segment 3: [1:35 - 2:15] Technical Depth (20 pts)
**Speaker**:
"Next is technical depth across autonomous backend agents and asynchronous systems:

1. **Autonomous Municipal Dispatch**: Immediately following triage, an asynchronous background agent drafts a formal work order in English and regional language, complete with docket ID, severity, SLA deadline, and a clickable Google Maps link, dispatched immediately to the configured demo dispatch inbox.
2. **Idempotent SLA Watchdog**: In production, tickets have target SLAs—24 hours for critical, 72 hours for high. Our background watchdog worker monitors all active tickets in an asyncio loop.
3. **Demo Time Acceleration**: For this live evaluation, we built in demo time compression via `SLA_TIME_SCALE=3600`. As deadline thresholds elapse, the watchdog autonomously escalates:
   - **Level 1**: Urgent reminder dispatched to Department Head.
   - **Level 2**: Formal escalation to Municipal Commissioner.
   - **Level 3**: The ticket is branded with a public, immutable **OVERDUE** banner on the city dashboard.

And our test suite proves the watchdog is 100% idempotent—running it repeatedly never double-escalates or spams inboxes."

*(Action: Point to the 'Demo Time Compression Active' banner on Dashboard and the Level 1/2 Watchdog escalation ribbons on ReportDetail).*

---

### Segment 4: [2:15 - 3:00] Live Demo Robustness (30 pts)
**Speaker**:
"Finally, live demo robustness and integrity verification:

1. **Multimodal Resolution Auditing**: When an authority submits closure proof, our AI Inspector loads the baseline photo and compares before-and-after evidence. If the verdict is `not_fixed` or `different_location`, the system **strictly rejects closure**, keeps the ticket In Progress, logs an audit strike on the timeline, and refuses to mark it resolved.
2. **Citizen Dispute Power**: Even after closure, a resident can click **Dispute**, which instantly returns the ticket to In Progress.
3. **Enterprise Hardening**:
   - FastAPI + Async SQLAlchemy on Supabase PostgreSQL with runtime migration (`ensure_schema()`).
   - PyJWT authentication with citizen and authority role guards.
   - Dual email provider support: SMTP and Resend REST API, completely non-blocking via `asyncio.to_thread`.
   - Comprehensive `/api/health` monitoring showing Gemini, email, watchdog, and database status in real-time.
   - Native Open311 GeoReport v2 standard compliance (`/api/open311/v2/services.json`).
   - Automated PyTest test suite and Vite build passing cleanly on GitHub Actions CI.

Jan Aawaz turns citizen grievances from a black hole into transparent, automated public accountability. Thank you!"
