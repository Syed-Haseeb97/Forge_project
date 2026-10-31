import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="mt-auto">
      {/* Connected Municipal Departments Strip */}
      <section className="border-t border-[#173e42]/10 bg-[#ece9df] dark:bg-[#071f23] transition-colors">
        <div className="mx-auto flex max-w-[1240px] flex-col items-center gap-4 px-5 py-6 text-center lg:flex-row lg:justify-between lg:px-8 lg:text-left">
          <p className="text-[11px] font-bold tracking-[0.16em] uppercase text-[#687975] dark:text-[#8ea5a2] shrink-0">
            Connected Municipal Departments
          </p>
          <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-xs font-bold text-[#34514f] dark:text-[#e8b855]">
            <span>Public Works Department</span>
            <span className="text-[#b7b3a6] dark:text-white/20">•</span>
            <span>Water &amp; Sewage Board</span>
            <span className="text-[#b7b3a6] dark:text-white/20">•</span>
            <span>Municipal Sanitation</span>
            <span className="text-[#b7b3a6] dark:text-white/20">•</span>
            <span>Traffic &amp; Highway Authority</span>
            <span className="text-[#b7b3a6] dark:text-white/20">•</span>
            <span>Environmental Protection</span>
            <span className="text-[#b7b3a6] dark:text-white/20">•</span>
            <span>Public Safety &amp; Hazards</span>
          </div>
        </div>
      </section>

      {/* Main Official Footer */}
      <div className="bg-[#08272b] text-white/60 overflow-hidden">
        {/* Three-column footer row */}
        <div className="mx-auto flex max-w-[1240px] flex-col items-center justify-between gap-8 px-8 py-10 text-center sm:flex-row sm:text-left">
          {/* Brand column */}
          <div className="flex flex-col sm:flex-row items-center gap-3 text-white shrink-0">
            <img
              src="/logo-dark.jpg"
              alt="जनAawaz"
              className="h-9 w-auto object-contain rounded-md"
            />
            <div className="hidden sm:block h-6 w-px bg-white/15" />
            <div className="text-left">
              <p className="text-[13px] font-bold text-white leading-tight">
                <span className="text-[#e8b855]">जन</span>Aawaz
              </p>
              <p className="text-[10px] text-white/40 tracking-wider uppercase">Public Grievance Portal</p>
            </div>
          </div>

          {/* Emergency notice */}
          <p className="text-xs text-white/55 max-w-xs leading-relaxed">
            Emergency? For immediate life-safety hazards, call{' '}
            <span className="text-white font-bold">112</span> or your local emergency dispatch directly.
          </p>

          {/* Nav links */}
          <nav className="flex flex-wrap justify-center sm:justify-end gap-x-5 gap-y-2 text-xs font-semibold text-white/70">
            <Link to="/reports" className="transition hover:text-[#e8b855]">Incident Registry</Link>
            <Link to="/submit" className="transition hover:text-[#e8b855]">File Complaint</Link>
            <a href="#" className="transition hover:text-[#e8b855]">Accessibility</a>
            <a href="#" className="transition hover:text-[#e8b855]">Privacy Policy</a>
            <a href="#" className="transition hover:text-[#e8b855]">SLA Charter</a>
            <a href="#" className="transition hover:text-[#e8b855]">Ombudsman</a>
          </nav>
        </div>

        {/* Copyright bar */}
        <div className="border-t border-white/10 px-8 py-4">
          <div className="mx-auto flex max-w-[1240px] flex-col sm:flex-row items-center justify-between gap-2 text-[10px] text-white/35">
            <div>
              <span>© 2026 Jan Aawaz (जनAawaz). All citizen submissions protected under digital public record charters.</span>
              <span className="block sm:inline sm:ml-3 text-white/50 font-medium">
                Hackathon prototype, not an official government service.
              </span>
            </div>
            <span className="shrink-0">Powered by Gemini AI Multimodal Triage &amp; Open GIS</span>
          </div>
        </div>
      </div>
    </footer>
  )
}
