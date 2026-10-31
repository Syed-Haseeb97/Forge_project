import { Link } from 'react-router-dom'
import CivicIcon from '../components/CivicIcon'

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-[960px] px-5 py-12 lg:px-8 space-y-8 animate-fadeIn">
      {/* Disclaimer Banner */}
      <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5 text-xs text-amber-900 dark:text-amber-200 space-y-2">
        <div className="flex items-center gap-2 font-bold uppercase tracking-wider text-[#956018] dark:text-[#e8b855]">
          <CivicIcon name="alert" size={16} />
          <span>Hackathon Prototype Notice</span>
        </div>
        <p className="leading-relaxed">
          <strong>Jan Aawaz (जनAawaz)</strong> is an experimental digital governance and civic pulse prototype submitted for hackathon evaluation.
          It is <strong>not</strong> an official government portal, municipal agency, or statutory public service of any government entity.
          Dispatches in this prototype are directed to a demo inbox for demonstration and testing purposes; no municipal system is connected.
        </p>
      </div>

      {/* Main Header */}
      <div className="space-y-3">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-bold tracking-[0.16em] uppercase text-[#ba7c29]">
          PROJECT OVERVIEW
        </span>
        <h1 className="font-serif text-3xl sm:text-4xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
          About Jan Aawaz (जनAawaz)
        </h1>
        <p className="text-sm sm:text-base leading-relaxed text-[#5f716e] dark:text-[#95a9a6]">
          Jan Aawaz is an autonomous multimodal civic redressal platform engineered to demonstrate how modern AI
          can eliminate bureaucratic delays, triage physical infrastructure hazards, and provide transparent public accountability.
        </p>
      </div>

      {/* Core Prototype Capabilities */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card space-y-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-[#0d3035] text-[#e8b855]">
            <CivicIcon name="brain" size={20} />
          </div>
          <h2 className="font-serif text-lg font-bold text-[#0d3035] dark:text-[#f6f4ee]">
            Multimodal Hazard Triage
          </h2>
          <p className="text-xs sm:text-sm text-[#5f716e] dark:text-[#95a9a6] leading-relaxed">
            Citizens can submit photos, audio recordings, or text descriptions. Gemini multimodal models extract incident categories, evaluate severity, check sensitive landmark proximity, and assign target response turnaround times.
          </p>
        </div>

        <div className="card space-y-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-[#0d3035] text-[#e8b855]">
            <CivicIcon name="route" size={20} />
          </div>
          <h2 className="font-serif text-lg font-bold text-[#0d3035] dark:text-[#f6f4ee]">
            Automated Dispatch Work Orders
          </h2>
          <p className="text-xs sm:text-sm text-[#5f716e] dark:text-[#95a9a6] leading-relaxed">
            The platform automatically composes structured work orders with precise coordinates, SLA deadlines, and multimodal evidence links. In this prototype, work orders are dispatched to configured demo inboxes.
          </p>
        </div>

        <div className="card space-y-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-[#0d3035] text-[#e8b855]">
            <CivicIcon name="clock" size={20} />
          </div>
          <h2 className="font-serif text-lg font-bold text-[#0d3035] dark:text-[#f6f4ee]">
            Autonomous SLA Watchdog
          </h2>
          <p className="text-xs sm:text-sm text-[#5f716e] dark:text-[#95a9a6] leading-relaxed">
            A background worker monitors open tickets against their target SLA deadlines. Overdue tickets receive tiered escalations and are flagged visibly in the public registry.
          </p>
        </div>

        <div className="card space-y-3">
          <div className="flex size-10 items-center justify-center rounded-xl bg-[#0d3035] text-[#e8b855]">
            <CivicIcon name="check" size={20} />
          </div>
          <h2 className="font-serif text-lg font-bold text-[#0d3035] dark:text-[#f6f4ee]">
            Verified Resolution Audit
          </h2>
          <p className="text-xs sm:text-sm text-[#5f716e] dark:text-[#95a9a6] leading-relaxed">
            Tickets cannot simply be marked resolved with a click. Field closeout requires an after-photo and notes, which the AI compares against baseline evidence before confirming remediation.
          </p>
        </div>
      </div>

      {/* Navigation CTA */}
      <div className="pt-4 flex flex-wrap gap-4">
        <Link to="/" className="btn-primary text-xs">
          Return to Overview
        </Link>
        <Link to="/reports" className="btn-secondary text-xs">
          Explore Incident Registry
        </Link>
      </div>
    </div>
  )
}
