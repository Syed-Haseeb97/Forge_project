import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="mt-auto border-t border-[#173e42]/10 dark:border-white/10 bg-[#06181b] text-white">
      {/* Connected Municipal Departments Ticker */}
      <div className="border-b border-white/10 bg-[#041012]/80 px-5 py-3">
        <div className="mx-auto flex max-w-[1240px] flex-col items-center gap-2.5 text-center lg:flex-row lg:justify-between lg:px-8 lg:text-left">
          <div className="flex items-center gap-2 shrink-0">
            <span className="size-2 rounded-full bg-[#e8b855] animate-pulse" />
            <span className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#e8b855]">
              CONNECTED CIVIC DEPARTMENTS &amp; INFRASTRUCTURE
            </span>
          </div>
          <div className="flex flex-wrap justify-center gap-x-5 gap-y-1.5 text-xs font-semibold text-white/70">
            <span className="hover:text-white transition">Public Works (PWD)</span>
            <span className="text-white/20">•</span>
            <span className="hover:text-white transition">Water Supply &amp; Sewage</span>
            <span className="text-white/20">•</span>
            <span className="hover:text-white transition">Municipal Sanitation</span>
            <span className="text-white/20">•</span>
            <span className="hover:text-white transition">Traffic &amp; Highway Authority</span>
            <span className="text-white/20">•</span>
            <span className="hover:text-white transition">Environmental Protection</span>
            <span className="text-white/20">•</span>
            <span className="hover:text-white transition">Public Safety &amp; Hazards</span>
          </div>
        </div>
      </div>

      {/* Main Official Footer */}
      <div className="mx-auto max-w-[1240px] px-5 py-10 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-start">
          {/* Brand & Statutory seals */}
          <div className="md:col-span-5 space-y-4">
            <div className="flex items-center gap-3">
              <img
                src="/logo-dark.jpg"
                alt="जनAawaz"
                className="h-9 w-auto object-contain rounded-md shadow-sm"
              />
              <div className="h-6 w-px bg-white/20" />
              <img
                src="/emblem-india.svg"
                alt="Emblem of India"
                className="h-8 w-auto object-contain opacity-85 invert brightness-200"
              />
              <img
                src="/digital-india.svg"
                alt="Digital India"
                className="h-6 w-auto object-contain opacity-85"
              />
            </div>
            <div>
              <p className="font-serif text-lg font-bold text-white tracking-tight">
                <span className="text-[#e8b855]">जन</span>Aawaz
                <span className="ml-2 font-mono text-[10px] uppercase tracking-widest text-[#e8b855] border border-[#e8b855]/30 rounded px-1.5 py-0.5">
                  CIVIC 2.0
                </span>
              </p>
              <p className="text-xs text-white/60 mt-1.5 leading-relaxed max-w-sm">
                AI-Powered Multimodal Citizen Grievance Redressal &amp; Open Municipal Infrastructure Accountability Platform.
              </p>
              <div className="mt-3 flex items-center gap-2 text-[10px] text-white/45">
                <span className="size-1.5 rounded-full bg-[#347161]" />
                <span>Protected citizen records with transparent public dispatch dockets.</span>
              </div>
            </div>
          </div>

          {/* Emergency Alert Box */}
          <div className="md:col-span-4 rounded-2xl border border-amber-500/30 bg-amber-950/20 p-4 text-xs text-amber-200/90 leading-relaxed space-y-2">
            <div className="flex items-center gap-2 text-[#e8b855] font-bold text-[11px] uppercase tracking-wider">
              <span>🚨</span>
              <span>EMERGENCY LIFE-SAFETY DISPATCH</span>
            </div>
            <p className="text-[11px] text-white/70 leading-relaxed">
              For immediate life-safety hazards, collapsed structures, or active electrical wire falls, dial emergency services immediately.
            </p>
            <div className="pt-1 flex items-center gap-2">
              <a
                href="tel:112"
                className="inline-flex items-center gap-1.5 rounded-full bg-[#e8b855] px-3.5 py-1 text-[11px] font-extrabold text-[#0d3035] shadow-xs hover:bg-[#efc56b] transition"
              >
                <span>CALL 112 DIRECTLY</span>
              </a>
              <span className="text-[10px] text-white/40">Toll-free national emergency</span>
            </div>
          </div>

          {/* Portal Navigation Links */}
          <div className="md:col-span-3 grid grid-cols-2 gap-4 text-xs">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[#e8b855] mb-2.5">
                Public Registry
              </p>
              <ul className="space-y-2 text-white/70 font-medium">
                <li><Link to="/reports" className="hover:text-[#e8b855] transition">Incident Registry</Link></li>
                <li><Link to="/submit" className="hover:text-[#e8b855] transition">Lodge Grievance</Link></li>
                <li><a href="/#accountability" className="hover:text-[#e8b855] transition">Public Dashboard</a></li>
                <li><a href="/#how-it-works" className="hover:text-[#e8b855] transition">How It Works</a></li>
              </ul>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[#e8b855] mb-2.5">
                Governance
              </p>
              <ul className="space-y-2 text-white/70 font-medium">
                <li><a href="#accountability" className="hover:text-[#e8b855] transition">SLA Charter</a></li>
                <li><span className="text-white/50 cursor-default">Privacy Policy</span></li>
                <li><span className="text-white/50 cursor-default">Ombudsman</span></li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      {/* Copyright Bar */}
      <div className="border-t border-white/10 bg-[#041012] px-5 py-4 lg:px-8">
        <div className="mx-auto flex max-w-[1240px] flex-col sm:flex-row items-center justify-between gap-2 text-[10px] text-white/45">
          <div>
            <span>© 2026 Jan Aawaz (जनAawaz). All citizen submissions protected under digital public record charters.</span>
            <span className="block sm:inline sm:ml-2 text-white/60 font-medium">
              Hackathon prototype, not an official government service.
            </span>
          </div>
          <span className="shrink-0 text-[#e8b855]/80 font-mono">
            Powered by Gemini AI Multimodal Triage &amp; Open GIS
          </span>
        </div>
      </div>
    </footer>
  )
}

