# 🏛️ Jan Aawaz (जनAawaz) – Technical Architecture & Agent Specification

Jan Aawaz is an autonomous civic grievance triage, dispatch, and public infrastructure monitoring system engineered for municipal governance, statutory accountability, and transparent citizen redressal.

---

## 1. System Architecture Overview

The system is organized into four core architectural planes:
1. **Civic Ingestion Plane**: Multimodal evidence capture (photos, voice notes, GPS coordinates, descriptions) with JWT-authenticated citizen credentials.
2. **Autonomous Multi-Signal Agent Triage Plane**: 6-step agentic pipeline integrating Gemini Multimodal reasoning, Nominatim geocoding, Open-Meteo microclimate weather, Overpass sensitive sites (250m), and live DB recurrence correlation.
3. **Municipal Dispatch & SLA Watchdog Plane**: Automated formal complaint work-order drafting via Gemini (English + regional language) and an asynchronous background watchdog worker managing tiered statutory escalations.
4. **Resolution Audit & Accountability Plane**: Computer-vision-based before/after verification rejecting false closures, citizen dispute reopening, and spatial 300m hotspot clustering.

```mermaid
flowchart TD
    subgraph Client["Frontend Layer (React 18 + Vite + Tailwind)"]
        A1[Citizen Reporting & Media Capture]
        A2[Interactive GIS Map & 300m Hotspots]
        A3[Public Docket & Multilingual Explainer]
        A4[Municipal Authority Dashboard]
    end

    subgraph API["FastAPI Gateway & Security"]
        B1[PyJWT Auth & RBAC Guard]
        B2[Open311 GeoReport v2 Endpoints]
        B3[Background Task Dispatcher]
        B4[Database Migrations Engine]
    end

    subgraph AgenticPipeline["Agentic Triage Pipeline"]
        C1[Step 1: Understand Evidence (Gemini Vision/Audio)]
        C2[Step 2: Reverse Geocode (Nominatim)]
        C3[Step 3: Microclimate Weather (Open-Meteo)]
        C4[Step 4: Sensitive Sites 250m (Overpass API)]
        C5[Step 5: Proximity Recurrence (Live DB)]
        C6[Step 6: Correlated Decision (Gemini Structured)]
        C7[Step 7: Heuristic Fallback Agent]
    end

    subgraph BackgroundWorkers["Autonomous Background Agents"]
        D1[Dispatch Agent: Formal Letter Generator]
        D2[SLA Watchdog Worker: Tiered Escalations]
        D3[Resolution Verification: Multimodal Image Audit]
        D4[Civic Intelligence: Spatial 300m Hotspot Clusters]
    end

    subgraph Storage["Persistence & External Services"]
        E1[(Supabase PostgreSQL / SQLite)]
        E2[Supabase Storage S3 / Local Media]
        E3[SMTP Email Gateway]
        E4[Web Speech API]
    end

    A1 -->|Multipart /api/reports| B1
    B1 --> C1
    C1 --> C2 --> C3 --> C4 --> C5 --> C6
    C6 -.->|Failure Fallback| C7
    C6 -->|Persist Ticket & Trace| E1
    B3 --> D1
    D1 -->|Work Order Letter| E3
    D2 -->|Periodic SLA Check| E1
    D2 -->|Escalation Notice| D1
    A4 -->|Resolve Proof| D3
    D3 -->|Approve/Reject| E1
    A3 -->|Explain Request| E4
    A2 -->|Fetch Hotspots| D4
    D4 -->|Grid Clustering| E1
```

---

## 2. Multi-Signal Agent Triage Pipeline

Every civic grievance submitted undergoes a deterministic, multi-signal correlated audit before departmental work-orders are assigned.

```mermaid
sequenceDiagram
    autonumber
    actor Citizen as Citizen / Commuter
    participant API as FastAPI Ingestion
    participant Gemini as Google Gemini API
    participant Nominatim as OpenStreetMap Nominatim
    participant Weather as Open-Meteo Weather
    participant Overpass as OSM Overpass API
    participant DB as Supabase PostgreSQL

    Citizen->>API: POST /api/reports (Photo/Audio + GPS + Title)
    API->>Gemini: 1. understand_evidence (Vision/Audio Multimodal)
    Gemini-->>API: {issue_type, hazards, dimensions, severity, language}
    
    API->>Nominatim: 2. reverse_geocode (Lat, Lon, User-Agent, Rate-limited)
    Nominatim-->>API: {locality, road, neighborhood, city}
    
    API->>Weather: 3. weather (Forecast API, 24h precipitation risk)
    Weather-->>API: {precipitation, max_prob_24h, heavy_rain_risk}
    
    API->>Overpass: 4. sensitive_sites (250m radius bounding box)
    Overpass-->>API: {schools, hospitals, clinics, transit_hubs}
    
    API->>DB: 5. recurrence (Open tickets within 300m)
    DB-->>API: {recurring_count, active_clusters}
    
    API->>Gemini: 6. decide (Correlate all 5 signals + context)
    Gemini-->>API: {final_severity, sla_hours, department, safety_advice, rationale}
    
    API->>DB: Persist Report + agent_trace + severity_rationale
    API-->>Citizen: 201 Created (Docket ID, SLA, Triage Summary)
    API-)DB: Queue Background Dispatch Letter & SMTP
```

---

## 3. SLA Watchdog & Autonomous Escalation Cycle

Municipal accountability is enforced by an autonomous background worker running every `WATCHDOG_INTERVAL_SEC` (default: 60s) with support for demo time compression (`SLA_TIME_SCALE`).

```mermaid
stateDiagram-v2
    [*] --> Open: Ticket Filed & Triaged
    
    Open --> InProgress: Assigned to Department
    
    InProgress --> EscalationLevel1: SLA Threshold Breached (overdue_ratio >= 1.0)
    note right of EscalationLevel1
        Autonomous Dispatch:
        Urgent Reminder to Department Head
    end note
    
    EscalationLevel1 --> EscalationLevel2: Sustained Breach (overdue_ratio >= 1.4)
    note right of EscalationLevel2
        Autonomous Dispatch:
        Escalation to Municipal Commissioner
    end note
    
    EscalationLevel2 --> EscalationLevel3: Critical Breach (overdue_ratio >= 1.8)
    note right of EscalationLevel3
        Public Flag: is_overdue = True
        Public Transparency Alert
    end note

    InProgress --> ResolutionAudit: Authority Submits After-Photo
    ResolutionAudit --> Resolved: Gemini Vision Verdict == fixed / partially_fixed
    ResolutionAudit --> InProgress: Gemini Vision Verdict == not_fixed / different_location
    
    Resolved --> InProgress: Citizen Disputes Resolution
    Resolved --> [*]: Citizen Confirms Resolution
```

---

## 4. Multimodal Resolution Audit Loop

To prevent fraudulent municipal closures where contractors mark tickets resolved without performing on-site repairs, the resolution endpoint executes an autonomous computer-vision comparison.

```mermaid
sequenceDiagram
    autonumber
    actor Official as Municipal Authority
    participant API as POST /api/reports/{id}/resolve
    participant Vision as Gemini Vision AI Inspector
    participant DB as Database & Timeline
    actor Resident as Resident Citizen

    Official->>API: Submit Resolution Proof (After-Photo + Notes)
    API->>DB: Fetch Baseline Evidence Photo
    API->>Vision: Compare Before vs. After (Spatial, Hazard, Completion)
    Vision-->>API: {verdict, confidence, explanation}
    
    alt Verdict is not_fixed OR different_location
        API->>DB: Reject Closure: Keep Status IN_PROGRESS
        API->>DB: Log "AI verification rejected closure: <explanation>"
        API-->>Official: 200 OK (Status: in_progress, Verdict: rejected)
    else Verdict is fixed OR partially_fixed
        API->>DB: Approve Closure: Set Status RESOLVED
        API->>DB: Log "Issue resolved: <notes> · AI Verdict: Fixed"
        API-->>Official: 200 OK (Status: resolved)
        
        opt Resident Verification
            Resident->>API: POST /api/reports/{id}/feedback
            alt Feedback == disputed
                API->>DB: Reopen Ticket (Status: IN_PROGRESS)
                API->>DB: Log "Citizen disputed resolution on ground"
            else Feedback == confirmed
                API->>DB: Log "Citizen confirmed resolution"
            end
        end
    end
```

---

## 5. Spatial Hotspot Clustering Math (~300m)

Hotspot clusters are computed purely from live database records without precomputed dummy coordinates:
- 1° Latitude $\approx 111,139\text{ m} \implies 300\text{ m} \approx 0.0027^\circ$.
- 1° Longitude at latitude $28^\circ\text{ N} \approx 98,000\text{ m} \implies 300\text{ m} \approx 0.0030^\circ$.
- Reports are mapped into spatial grid cells:
  $$\text{Cell} = \left(\left\lfloor \frac{\text{lat}}{0.0027} + 0.5 \right\rfloor, \left\lfloor \frac{\text{lon}}{0.0030} + 0.5 \right\rfloor\right)$$
- Centroids are calculated as the arithmetic mean of all reports in the grid cell.
- Clusters with $\ge 2$ grievances are designated as active municipal hotspots.

---

## 6. Database Entity Relationship Model

```mermaid
erDiagram
    CITIZEN ||--o{ REPORT : files
    REPORT ||--o{ REPORT_TIMELINE : audits
    REPORT ||--o{ COMMENT : discusses
    REPORT ||--o{ DISPATCH : notifies
    REPORT ||--o{ EXPLANATION : translates

    CITIZEN {
        string id PK
        string email UK
        string full_name
        string role
        datetime created_at
    }

    REPORT {
        string id PK
        string citizen_id FK
        string title
        string description
        string category
        string severity
        string status
        float latitude
        float longitude
        string location
        string locality
        string media_url
        string routed_to
        int sla_hours
        int escalation_level
        boolean is_overdue
        string resolution_verdict
        float resolution_confidence
        text resolution_explanation
        string citizen_feedback
        text agent_trace
        datetime created_at
        datetime resolved_at
    }

    DISPATCH {
        string id PK
        string report_id FK
        string kind
        string to_email
        string subject
        text body
        boolean sent
        datetime created_at
    }

    EXPLANATION {
        string id PK
        string report_id FK
        string lang
        text text
        datetime created_at
    }

    REPORT_TIMELINE {
        string id PK
        string report_id FK
        string status
        string actor
        string action_type
        text notes
        string media_url
        datetime created_at
    }
```
