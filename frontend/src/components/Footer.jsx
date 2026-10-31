import CivicIcon from './CivicIcon'

export default function Footer() {
  return (
    <footer className="mt-auto">
      {/* Connected Civic Services Strip */}
      <section className="border-t border-[#173e42]/10 bg-[#ece9df] dark:bg-[#071f23] transition-colors">
        <div className="mx-auto flex max-w-[1240px] flex-col items-center gap-4 px-5 py-6 text-center lg:flex-row lg:justify-between lg:px-8 lg:text-left">
          <p className="text-[11px] font-bold tracking-[0.16em] uppercase text-[#687975] dark:text-[#8ea5a2]">
            CONNECTED TO CIVIC SERVICES
          </p>
          <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-xs font-bold text-[#34514f] dark:text-[#bcd3ce]">
            <span>Public Works</span>
            <span className="text-[#b7b3a6] dark:text-white/20">•</span>
            <span>Water & Sewage Board</span>
            <span className="text-[#b7b3a6] dark:text-white/20">•</span>
            <span>Municipal Sanitation</span>
            <span className="text-[#b7b3a6] dark:text-white/20">•</span>
            <span>Transport Authority</span>
            <span className="text-[#b7b3a6] dark:text-white/20">•</span>
            <span>Environmental Protection</span>
            <span className="text-[#b7b3a6] dark:text-white/20">•</span>
            <span>Public Safety</span>
          </div>
        </div>
      </section>

      {/* Main Official Footer */}
      <div className="bg-[#08272b] px-5 py-10 text-white/60 lg:px-8">
        <div className="mx-auto flex max-w-[1240px] flex-col items-center justify-between gap-6 text-center text-xs sm:flex-row sm:text-left">
          <div className="flex flex-col sm:flex-row items-center gap-4 text-white">
            <img
              src="/logo-dark.jpg"
              alt="जनAawaz"
              className="h-9 w-auto object-contain rounded-md"
            />
            <div className="h-6 w-px bg-white/15 hidden sm:block" />
            <div className="flex items-center gap-3">
              <img src="/emblem-india.svg" alt="State Emblem of India" className="h-8 w-auto object-contain" />
              <img src="/digital-india.svg" alt="Digital India" className="h-6 w-auto object-contain" />
            </div>
          </div>

          <p className="max-w-md text-[11px] leading-5 text-white/50">
            Emergency? For immediate life-safety hazards, please contact 112 or your local emergency dispatch service directly.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-5 text-xs font-semibold text-white/70">
            <a href="#accessibility" className="transition hover:text-[#e8b855]">Accessibility</a>
            <a href="#privacy" className="transition hover:text-[#e8b855]">Privacy Policy</a>
            <a href="#terms" className="transition hover:text-[#e8b855]">SLA Charter</a>
            <a href="#contact" className="transition hover:text-[#e8b855]">Ombudsman</a>
          </div>
        </div>
        <div className="mx-auto mt-8 max-w-[1240px] border-t border-white/10 pt-5 text-center text-[10px] text-white/35 sm:flex sm:justify-between sm:text-left">
          <p>© 2026 Jan Aawaz (जनAawaz) Public Service Infrastructure. All citizen submissions protected under digital public record charters.</p>
          <p className="mt-1 sm:mt-0">Powered by Gemini AI Multimodal Triage & Open GIS</p>
        </div>
      </div>
    </footer>
  )
}
