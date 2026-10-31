import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="mt-auto border-t border-[#173e42]/10 dark:border-white/10 bg-[#08272b] text-white">
      {/* Department Routing Categories Ticker */}
      <div className="border-b border-white/10 bg-[#051c1f]/80 px-5 py-3.5">
        <div className="mx-auto flex max-w-[1240px] flex-col items-center gap-3 text-center lg:flex-row lg:justify-between lg:px-8 lg:text-left">
          <div className="flex items-center gap-2 shrink-0">
            <span className="size-2 rounded-full bg-[#e8b855] animate-pulse" />
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#e8b855]">
              Department categories used for routing
            </span>
          </div>
          <div className="flex flex-wrap justify-center gap-x-5 gap-y-1.5 text-xs font-semibold text-white/75">
            <span>Public Works Department (PWD)</span>
            <span className="text-white/20">•</span>
            <span>Water Supply &amp; Sewage Board</span>
            <span className="text-white/20">•</span>
            <span>Municipal Sanitation &amp; Solid Waste</span>
            <span className="text-white/20">•</span>
            <span>Traffic &amp; Highway Authority</span>
            <span className="text-white/20">•</span>
            <span>Environmental Protection</span>
            <span className="text-white/20">•</span>
            <span>Public Safety &amp; Hazards</span>
          </div>
        </div>
        <div className="mx-auto max-w-[1240px] px-5 lg:px-8 pt-2 text-center lg:text-left">
          <p className="text-[11px] text-white/50 italic">
            Dispatches in this prototype go to a demo inbox; no municipal system is connected.
          </p>
        </div>
      </div>

      {/* Main Footer */}
      <div className="mx-auto max-w-[1240px] px-5 py-10 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
          {/* Brand & Prototype Disclaimer */}
          <div className="md:col-span-5 space-y-4">
            <div className="flex items-center gap-3">
              <img
                src="/logo-dark.jpg"
                alt="जनAawaz"
                className="h-9 w-auto object-contain rounded-md shadow-sm"
              />
            </div>
            <div>
              <p className="text-sm font-bold text-white tracking-tight">
                <span className="text-[#e8b855]">जन</span>Aawaz
                <span className="ml-2 text-[10px] font-mono uppercase tracking-widest text-[#e8b855] border border-[#e8b855]/30 rounded px-1.5 py-0.5">
                  CIVIC 2.0
                </span>
              </p>
              <p className="text-xs text-white/60 mt-1 leading-relaxed max-w-sm">
                AI-Powered Multimodal Citizen Grievance Redressal &amp; Open Infrastructure Accountability Platform.
              </p>
              {/* Visible Prototype Disclaimer Line */}
              <div className="mt-3.5 inline-flex items-center gap-2 rounded-lg bg-amber-500/15 border border-amber-500/30 px-3 py-1.5 text-xs text-amber-200">
                <span className="font-bold text-[#e8b855]">⚠️ Notice:</span>
                <span>Hackathon prototype, not an official government service.</span>
              </div>
            </div>
          </div>

          {/* Emergency Alert Box */}
          <div className="md:col-span-4 rounded-2xl border border-amber-500/30 bg-amber-950/20 p-4 text-xs text-amber-200/90 leading-relaxed">
            <div className="flex items-center gap-2 text-[#e8b855] font-bold text-[11px] uppercase tracking-wider mb-1.5">
              <span>🚨</span>
              <span>EMERGENCY LIFE-SAFETY DISPATCH</span>
            </div>
            <p className="text-[11px] text-white/70">
              For immediate life-safety hazards, collapsed structures, or active electrical fires, please dial{' '}
              <strong className="text-white font-bold bg-[#e8b855]/20 text-[#e8b855] px-1.5 py-0.5 rounded">112</strong>{' '}
              or reach out to local emergency services directly.
            </p>
          </div>

          {/* Portal Navigation Links */}
          <div className="md:col-span-3 flex flex-col sm:flex-row md:flex-col gap-4 text-xs">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[#e8b855] mb-2">
                Public Registry
              </p>
              <ul className="space-y-1.5 text-white/70 font-medium">
                <li><Link to="/reports" className="hover:text-[#e8b855] transition">Incident Registry</Link></li>
                <li><Link to="/submit" className="hover:text-[#e8b855] transition">Lodge New Grievance</Link></li>
                <li><a href="/#accountability" className="hover:text-[#e8b855] transition">Public Accountability</a></li>
              </ul>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[#e8b855] mb-2">
                Prototype Information
              </p>
              <ul className="space-y-1.5 text-white/70 font-medium">
                <li><Link to="/about" className="hover:text-[#e8b855] transition">About This Prototype</Link></li>
                <li><Link to="/privacy" className="hover:text-[#e8b855] transition">Privacy &amp; Data Handling</Link></li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Copyright Bar */}
      <div className="border-t border-white/10 bg-[#05181a] px-5 py-4 lg:px-8">
        <div className="mx-auto flex max-w-[1240px] flex-col sm:flex-row items-center justify-between gap-2 text-[10px] text-white/40">
          <div>
            <span>© 2026 Jan Aawaz (जनAawaz). Hackathon demonstration prototype.</span>
          </div>
          <span className="shrink-0 text-[#e8b855]/70 font-mono">
            Powered by Gemini AI Multimodal Triage &amp; Open GIS
          </span>
        </div>
      </div>
    </footer>
  )
}
