import { Link } from 'react-router-dom'
import CivicIcon from '../components/CivicIcon'

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-[960px] px-5 py-12 lg:px-8 space-y-8 animate-fadeIn">
      {/* Disclaimer Banner */}
      <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5 text-xs text-amber-900 dark:text-amber-200 space-y-2">
        <div className="flex items-center gap-2 font-bold uppercase tracking-wider text-[#956018] dark:text-[#e8b855]">
          <CivicIcon name="shield" size={16} />
          <span>Prototype Privacy Notice</span>
        </div>
        <p className="leading-relaxed">
          This portal is an evaluation prototype. Submissions made here are intended for hackathon testing and technical demonstration.
          Do not submit sensitive personal identifiers, passwords, or confidential medical or financial records.
        </p>
      </div>

      {/* Main Header */}
      <div className="space-y-3">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-bold tracking-[0.16em] uppercase text-[#ba7c29]">
          DATA GOVERNANCE &amp; HANDLING
        </span>
        <h1 className="font-serif text-3xl sm:text-4xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
          Privacy Policy
        </h1>
        <p className="text-sm sm:text-base leading-relaxed text-[#5f716e] dark:text-[#95a9a6]">
          Jan Aawaz is designed with citizen privacy and data minimization principles. Below is how data is collected, processed, and displayed in this demonstration environment.
        </p>
      </div>

      <div className="card space-y-6 text-sm text-[#334e4c] dark:text-[#cbd5e1] leading-relaxed">
        <section className="space-y-2">
          <h2 className="font-serif text-lg font-bold text-[#0d3035] dark:text-[#f6f4ee]">
            1. What We Collect
          </h2>
          <ul className="list-disc pl-5 space-y-1.5 text-xs sm:text-sm text-[#5f716e] dark:text-[#95a9a6]">
            <li><strong>Email Address:</strong> Used solely to issue a time-limited 6-digit one-time password (OTP) for authentication and dispatch tracking.</li>
            <li><strong>Incident Evidence:</strong> Photographs, voice recordings, and text descriptions provided during report submission.</li>
            <li><strong>Geographic Location:</strong> Coordinates selected by dropping a map pin or granted via browser geolocation to localize the incident.</li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="font-serif text-lg font-bold text-[#0d3035] dark:text-[#f6f4ee]">
            2. How Information Is Processed
          </h2>
          <p className="text-xs sm:text-sm text-[#5f716e] dark:text-[#95a9a6]">
            Submitted media is processed through Google Gemini AI APIs to extract hazard severity, generate public plain-language briefs, and draft simulated departmental work orders. Coordinates are reverse-geocoded using OpenStreetMap Nominatim.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="font-serif text-lg font-bold text-[#0d3035] dark:text-[#f6f4ee]">
            3. Public Docket Transparency
          </h2>
          <p className="text-xs sm:text-sm text-[#5f716e] dark:text-[#95a9a6]">
            Jan Aawaz operates an open civic incident registry to facilitate community awareness and accountability. Incident descriptions, photographs, locations, and audit timelines are visible in the public registry. Citizen email addresses are never displayed publicly.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="font-serif text-lg font-bold text-[#0d3035] dark:text-[#f6f4ee]">
            4. Third-Party Sharing &amp; Commercialization
          </h2>
          <p className="text-xs sm:text-sm text-[#5f716e] dark:text-[#95a9a6]">
            Data submitted to this prototype is not sold, monetized, or shared with commercial advertising brokers.
          </p>
        </section>
      </div>

      {/* Navigation CTA */}
      <div className="pt-4 flex flex-wrap gap-4">
        <Link to="/" className="btn-primary text-xs">
          Return to Overview
        </Link>
        <Link to="/about" className="btn-secondary text-xs">
          About the Project
        </Link>
      </div>
    </div>
  )
}
