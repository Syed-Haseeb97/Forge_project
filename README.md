# 🏛️ Jan Aawaz (जनAawaz) – Civic Grievance & Infrastructure Redressal System

> **Note**: Hackathon prototype, not an official government service.

AI-powered civic issue reporting, automated multimodal severity triage, geospatial infrastructure mapping, and transparent public municipal accountability.

Inspired by premier open-source civic platforms (**FixMyStreet**, **Mark-a-Spot**, and the **Open311 GeoReport v2** international specification).

---

## ⚡ Tech Stack
- **Backend**: FastAPI + async SQLAlchemy (SQLite locally, Supabase PostgreSQL via `DATABASE_URL`) + PyJWT + `google-genai`
- **Frontend**: React 18 + Vite + Tailwind CSS + Leaflet GIS (`react-leaflet`) + Axios + React Hot Toast
- **AI Multimodal Engine**: Google Gemini API (`gemini-2.5-flash`, `gemini-1.5-flash`) with structured schema output and resilient heuristic fallbacks
- **Standard Protocol**: Native Open311 GeoReport v2 compliance

---

## 🌟 Key Features

### 1. 🤖 Multimodal AI Severity Triage & Routing
- Upload photographic or audio evidence of civic infrastructure failures.
- Gemini assesses structural damage, classifies severity (`critical`, `high`, `medium`, `low`), formulates engineering action plans, and establishes target SLA resolution hours (24h, 72h, 168h, 336h).
- Automatic routing to the responsible municipal department (Road & Highway, Water & Sewage, Sanitation, Power, Public Safety, etc.).

### 2. 🗺️ Interactive Civic GIS Map & Pin Placement
- **Reports GIS**: Seamless switch between Grid View and interactive Map View with color-coded severity pins.
- **Location Picker**: Tap or drag the pin anywhere on the map when reporting an issue to set exact GPS coordinates.

### 3. 🛡️ Proximity-Based Duplicate Detection
- Avoid duplicate city tickets: when a citizen selects a location, Jan Aawaz scans for open reports within 500 meters and invites the citizen to upvote the existing ticket instead.

### 4. 📜 Civic Lifecycle Audit Trail & Transparency
- Complete chronological activity timeline tracking each ticket from submission through AI triage, department routing, official comments, and resolution.

### 5. ✅ Verified Resolution Proof (Before & After Verification)
- Authorities close tickets by submitting verified completion notes and photographic proof ("After Photo").
- Detail view renders side-by-side Before & After photographic evidence to the public.

### 6. 🔐 Authenticated Access & Role-Based Authorization
- OTP-based citizen authentication powered by signed PyJWT tokens (12h expiration).
- Role segregation: Citizen (reporting, endorsements, inquiries) vs. Municipal Authority (official status updates, resolution verification, authoritative notices).

### 7. 🌐 Open311 GeoReport v2 Interoperability
- Bidirectional standard endpoints (`/api/open311/v2/services.json` and `/api/open311/v2/requests.json`) compatible with municipal 311 systems and civic data aggregators.

### 8. 📊 Open Data Export
- One-click public data export to CSV or JSON for citizen researchers, journalists, and city audits.

---

## 🚀 Running on Localhost

### 1. Backend (FastAPI on http://localhost:8000)
```bash
cd backend
# Create and activate virtual environment:
python -m venv venv
venv\Scripts\activate  # On Windows
pip install -r requirements.txt

# Copy environment variables and configure keys:
cp .env.example .env

# Run server:
uvicorn main:app --reload --port 8000
```

### 2. Frontend (Vite on http://localhost:5173)
```bash
cd frontend
npm install
npm run dev
```

- **Frontend App**: http://localhost:5173
- **Interactive Swagger Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health
- **Open311 Service Catalog**: http://localhost:8000/api/open311/v2/services.json

---

## ☁️ Deployment Guide

### 1. Backend Deployment (Render or Fly.io)
The backend includes a production [Dockerfile](file:///D:/projects/fordge5/fordge/backend/Dockerfile) with a built-in health check on `/api/health`.

- **On Render**:
  1. Create a new **Web Service** connected to the repository.
  2. Set Root Directory to `backend` (or build using the Docker runtime pointing to `backend/Dockerfile`).
  3. Set Environment Variables:
     - `DATABASE_URL`: Your Supabase PostgreSQL connection string (`postgresql+asyncpg://...`).
     - `JWT_SECRET`: Secure random string for signing JWT tokens.
     - `AUTHORITY_EMAILS`: Comma-separated list of authority emails (e.g. `admin@municipal.gov,inspector@civic.org`).
     - `CORS_ORIGINS`: Your Vercel frontend URL (e.g. `https://jan-aawaz.vercel.app`).
     - `GEMINI_API_KEY`: Google Gemini API key.
     - `DEV_MODE`: `false` in production.
     - `SUPABASE_URL` & `SUPABASE_KEY` / `SUPABASE_STORAGE_BUCKET`: For uploaded media storage.
     - `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`: For live OTP delivery (if unset, auth operates gracefully).

- **On Fly.io**:
  ```bash
  cd backend
  fly launch --dockerfile Dockerfile
  fly secrets set JWT_SECRET="your-secret" DATABASE_URL="postgresql+asyncpg://..." GEMINI_API_KEY="..." CORS_ORIGINS="https://jan-aawaz.vercel.app"
  fly deploy
  ```

### 2. Database & Storage (Supabase)
- **Database**:
  - Provision a Supabase PostgreSQL project.
  - Set `DATABASE_URL` using the `postgresql+asyncpg://` dialect.
  - Jan Aawaz runs automatic startup migrations via `migrations.py` (`ensure_schema()`), inspecting and provisioning tables and missing columns dynamically.
- **Storage**:
  - Create a public Supabase Storage bucket named `civicline-media` (or configure `SUPABASE_STORAGE_BUCKET`).
  - Provide `SUPABASE_URL` and `SUPABASE_KEY` in environment variables.

### 3. Frontend Deployment (Vercel)
The frontend includes [vercel.json](file:///D:/projects/fordge5/fordge/frontend/vercel.json) to handle Single Page Application (SPA) routing without swallowing API paths.

- **On Vercel**:
  1. Import the repository and set Root Directory to `frontend`.
  2. Framework Preset: **Vite**.
  3. Environment Variables:
     - `VITE_API_BASE`: The deployed backend URL (e.g. `https://jan-aawaz-api.onrender.com` or empty string if behind a reverse proxy).
  4. Deploy.

---

## 📁 Project Structure
```
fordge/
├── backend/
│   ├── main.py           # FastAPI routes, Open311 & export endpoints
│   ├── auth.py           # PyJWT verification, RBAC & dependencies
│   ├── migrations.py     # ensure_schema() auto-migration for SQLite/Postgres
│   ├── models.py         # SQLAlchemy ORM (Reports, Timeline, Comments, Citizens)
│   ├── database.py       # Async SQLAlchemy session and connection pool
│   ├── gemini_service.py # Gemini multimodal triage & heuristic fallback
│   ├── email_service.py  # OTP mailing & 30s rate limiting
│   ├── storage_service.py# Local & Supabase object storage
│   ├── Dockerfile        # Production container definition
│   ├── .env.example      # Sample configuration
│   └── requirements.txt  # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AuthContext.jsx # JWT session, role management & 401 interceptor
│   │   │   ├── CivicMap.jsx    # Interactive Leaflet GIS map
│   │   │   ├── Navbar.jsx      # Header, authentication status & navigation
│   │   │   ├── Footer.jsx      # Footer with prototype notice & links
│   │   │   ├── ReportCard.jsx  # Card with SLA & watchlist
│   │   │   └── constants.js    # Badges, categories & watchlist helpers
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx   # Metrics, charts, incident filing & tracking
│   │   │   ├── ReportsList.jsx # Grid/Map view, filters & CSV export
│   │   │   ├── SubmitReport.jsx# Map picker & duplicate detection
│   │   │   ├── ReportDetail.jsx# Before/After proof, audit trail, gated authority tools
│   │   │   └── AuthPage.jsx    # Citizen OTP registration & login
│   │   ├── App.jsx
│   │   └── index.css
│   ├── vercel.json       # Production SPA rewrites
│   └── package.json
└── README.md
```

---

## 🔌 API Endpoints
| Method | Path | Description | Access |
|--------|------|-------------|--------|
| GET | `/api/health` | Service health status & DB connectivity | Public |
| POST | `/api/auth/register-send-code` | Send OTP for citizen registration | Public (rate limited 30s) |
| POST | `/api/auth/register-verify-code` | Verify OTP & issue signed JWT | Public |
| POST | `/api/auth/login-send-code` | Send OTP for citizen sign-in | Public (rate limited 30s) |
| POST | `/api/auth/verify-code` | Verify OTP & issue signed JWT | Public |
| GET | `/api/reports` | List reports with search & multi-field filters | Public |
| POST | `/api/reports` | Submit new report with photo/audio evidence | Citizen Auth |
| GET | `/api/reports/nearby` | Proximity duplicate detection within radius | Public |
| GET | `/api/reports/export` | Download public dataset as CSV or JSON | Public |
| GET | `/api/reports/{id}` | Get full report details | Public |
| GET | `/api/reports/{id}/timeline` | Retrieve chronological audit trail | Public |
| PATCH| `/api/reports/{id}/status` | Update status (open, in_progress, closed) | Authority Auth |
| POST | `/api/reports/{id}/resolve` | Resolve issue with official notes & After Photo | Authority Auth |
| POST | `/api/reports/{id}/upvote` | Citizen endorsement | Citizen Auth |
| GET | `/api/reports/{id}/comments` | Public discussion thread | Public |
| POST | `/api/reports/{id}/comments` | Post inquiry or official update | Citizen / Authority |
| GET | `/api/stats` | Comprehensive stats, SLA rate & department loads | Public |
| GET | `/api/open311/v2/services.json` | Open311 GeoReport v2 service list | Public |
| GET | `/api/open311/v2/requests.json` | Open311 GeoReport v2 request queries | Public |
