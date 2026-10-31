# 🏙️ Fordge – Transparent Civic Grievance & Infrastructure Triage System

AI-powered civic issue reporting, automated multimodal severity triage, geospatial infrastructure mapping, and public municipal accountability.

Inspired by premier open-source civic platforms (**FixMyStreet**, **Mark-a-Spot**, and the **Open311 GeoReport v2** international specification).

---

## ⚡ Tech Stack
- **Backend**: FastAPI + SQLite (async via `aiosqlite`) + SQLAlchemy 2.0
- **Frontend**: React 18 + Vite + Tailwind CSS + Leaflet GIS (`react-leaflet`) + Recharts
- **AI Intelligence**: Google Gemini multimodal API (`gemini-3.5-flash-lite`, `gemini-3.8-flash`) with resilient heuristic fallback
- **Standard Protocol**: Native Open311 GeoReport v2 compliance

---

## 🌟 Key Features

### 1. 🤖 Multimodal AI Severity Triage & Routing
- Upload photographic or audio evidence of civic infrastructure failures.
- Gemini assesses structural damage, classifies severity (`critical`, `high`, `medium`, `low`), formulates engineering action plans, and establishes target SLA resolution hours (24h, 72h, 168h, 336h).
- Automatic routing to the responsible municipal department (Public Works, Civil Engineering, Water Authority, EPA, Sanitation, etc.).

### 2. 🗺️ Interactive Civic GIS Map & Pin Placement
- **Reports GIS**: Seamless switch between Grid View and interactive Map View with color-coded severity pins.
- **Location Picker**: Tap or drag the pin anywhere on the map when reporting an issue to set exact GPS coordinates.

### 3. 🛡️ Proximity-Based Duplicate Detection
- Avoid duplicate city tickets: when a citizen selects a location, Fordge scans for open reports within 500 meters and invites the citizen to upvote the existing ticket instead.

### 4. 📜 Civic Lifecycle Audit Trail & Transparency
- Complete chronological activity timeline tracking each ticket from submission through AI triage, department routing, official comments, and resolution.

### 5. ✅ Verified Resolution Proof (Before & After Verification)
- Authorities close tickets by submitting verified completion notes and photographic proof ("After Photo").
- Detail view renders side-by-side Before & After photographic evidence to the public.

### 6. ⭐ Citizen Watchlist
- Citizens can bookmark and follow key issues in their neighborhood with one-click watchlist filtering.

### 7. 🚨 Crisis / Urgent Hazard Banner
- Immediate municipal alert banner triggered on the Dashboard whenever critical life-safety hazards are active.

### 8. 🌐 Open311 GeoReport v2 Interoperability
- Bidirectional standard endpoints (`/api/open311/v2/services.json` and `/api/open311/v2/requests.json`) compatible with municipal 311 systems and civic data aggregators.

### 9. 📊 Open Data Export
- One-click public data export to CSV or JSON for citizen researchers, journalists, and city audits.

---

## 🚀 Running on Localhost

### 1. Backend (FastAPI on http://localhost:8000)
```bash
cd backend
# With virtual environment:
# ..\..\venv\Scripts\uvicorn.exe main:app --reload --port 8000
uvicorn main:app --reload --port 8000
```

### 2. Frontend (Vite on http://localhost:5173)
```bash
cd frontend
npm run dev
```

- **Frontend App**: http://localhost:5173
- **Interactive Swagger Docs**: http://localhost:8000/docs
- **Open311 Service Catalog**: http://localhost:8000/api/open311/v2/services.json

---

## 📁 Project Structure
```
fordge/
├── backend/
│   ├── main.py           # FastAPI routes, Open311 & export endpoints
│   ├── models.py         # SQLAlchemy ORM (Reports, Timeline, Comments)
│   ├── database.py       # Async DB connection
│   ├── gemini_service.py # Gemini multimodal triage & heuristic fallback
│   ├── .env              # Configuration & API keys
│   └── requirements.txt  # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── CivicMap.jsx    # Interactive Leaflet GIS map
│   │   │   ├── Navbar.jsx      # Navigation bar
│   │   │   ├── ReportCard.jsx  # Card with SLA & watchlist
│   │   │   └── constants.js    # Badges, categories & watchlist helpers
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx   # Metrics, charts, crisis alerts
│   │   │   ├── ReportsList.jsx # Grid/Map view, filters & CSV export
│   │   │   ├── SubmitReport.jsx# Map picker & duplicate detection
│   │   │   └── ReportDetail.jsx# Before/After proof, audit trail, comments
│   │   ├── App.jsx
│   │   └── index.css
│   └── package.json
└── README.md
```

---

## 🔌 API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/reports` | Submit new report with photo/audio evidence |
| GET | `/api/reports` | List reports with search & multi-field filters |
| GET | `/api/reports/nearby` | Proximity duplicate detection within radius |
| GET | `/api/reports/export` | Download public dataset as CSV or JSON |
| GET | `/api/reports/{id}` | Get full report details |
| GET | `/api/reports/{id}/timeline` | Retrieve chronological audit trail |
| PATCH| `/api/reports/{id}/status` | Update status (open, in_progress, closed) |
| POST | `/api/reports/{id}/resolve` | Resolve issue with official notes & After Photo |
| POST | `/api/reports/{id}/upvote` | Citizen upvote |
| GET | `/api/reports/{id}/comments` | Public discussion thread |
| POST | `/api/reports/{id}/comments` | Post comment (citizen or authority) |
| GET | `/api/stats` | Comprehensive stats, SLA rate & department loads |
| GET | `/api/open311/v2/services.json` | Open311 GeoReport v2 service list |
| GET | `/api/open311/v2/requests.json` | Open311 GeoReport v2 request queries |
