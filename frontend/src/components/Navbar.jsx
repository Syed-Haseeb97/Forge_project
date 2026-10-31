import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Sun, Moon } from 'lucide-react'
import Brand from './Brand'
import CivicIcon from './CivicIcon'
import { useTheme } from './ThemeContext'
import { useAuth } from './AuthContext'
import toast from 'react-hot-toast'

export default function Navbar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { isDark, toggleTheme } = useTheme()
  const { user, isVerified, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  const handleSignOut = () => {
    logout()
    toast.success('Signed out of citizen account')
    setMenuOpen(false)
  }

  return (
    <>
      {/* Civic Redressal Top Strip */}
      <div className="bg-[#092225] border-b border-white/10 px-5 py-1.5 text-white/90 transition-colors">
        <div className="mx-auto flex max-w-[1240px] items-center justify-between text-[10px] sm:text-[11px] font-semibold tracking-wider">
          <div className="flex items-center gap-2">
            <span className="font-bold text-[#e8b855]">जनAawaz</span>
            <span className="text-white/40">|</span>
            <span className="text-white/80">Civic Grievance & Infrastructure Redressal</span>
          </div>
          <div className="flex items-center gap-3 text-white/60">
            <span className="text-[10px]">Hackathon prototype, not an official government service</span>
          </div>
        </div>
      </div>

      {/* Main Navigation Bar */}
      <header className="sticky top-0 z-40 border-b border-[#173e42]/10 bg-[#f6f4ee]/95 dark:bg-[#06181b]/95 backdrop-blur-md transition-colors">
        <div className="mx-auto flex max-w-[1240px] items-center justify-between px-5 py-3.5 lg:px-8">
          <Link to="/" onClick={() => setMenuOpen(false)}>
            <Brand />
          </Link>

          {/* Desktop Navigation Links */}
          <nav className="hidden items-center gap-8 text-sm font-semibold lg:flex">
            <Link
              to="/"
              className={`transition hover:text-[#bd7f23] ${
                pathname === '/' ? 'text-[#0d3035] dark:text-[#e8b855] font-bold' : 'text-[#536866] dark:text-[#95a9a6]'
              }`}
            >
              Overview
            </Link>
            <Link
              to="/reports"
              className={`transition hover:text-[#bd7f23] ${
                pathname === '/reports' ? 'text-[#0d3035] dark:text-[#e8b855] font-bold' : 'text-[#536866] dark:text-[#95a9a6]'
              }`}
            >
              Incident Registry
            </Link>
            <a
              href="/#accountability"
              className="text-[#536866] dark:text-[#95a9a6] transition hover:text-[#bd7f23]"
            >
              Public Dashboard
            </a>
            <a
              href="/#how-it-works"
              className="text-[#536866] dark:text-[#95a9a6] transition hover:text-[#bd7f23]"
            >
              How it works
            </a>
          </nav>

          {/* Right Action Items */}
          <div className="hidden items-center gap-3 sm:flex">
            {/* Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              type="button"
              aria-label="Toggle visual theme"
              title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
              className="flex items-center gap-1.5 rounded-full border border-[#173e42]/15 bg-white/60 dark:bg-white/10 px-3.5 py-2 text-xs font-bold text-[#102a2f] dark:text-[#f6f4ee] transition hover:bg-white dark:hover:bg-white/20"
            >
              {isDark ? (
                <>
                  <Sun size={15} className="text-[#e8b855]" />
                  <span>Light</span>
                </>
              ) : (
                <>
                  <Moon size={15} className="text-[#0d3035]" />
                  <span>Dark</span>
                </>
              )}
            </button>

            {/* Authentication Status / Sign In / Sign Out */}
            {isVerified ? (
              <div className="flex items-center gap-2.5">
                <div className="flex items-center gap-2 rounded-full bg-[#e3f0ea] dark:bg-[#123830] px-3.5 py-1.5 text-xs font-bold text-[#2f7661] dark:text-[#70b99e] border border-[#347161]/20">
                  <span className="size-2 rounded-full bg-[#347161] dark:bg-[#70b99e]" />
                  <span className="truncate max-w-[150px]">
                    {user.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : user.email}
                  </span>
                  {user.role === 'authority' && (
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#ba7c29] text-white uppercase">
                      Authority
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={handleSignOut}
                  className="rounded-full border border-[#173e42]/20 bg-white/60 dark:bg-white/10 px-3.5 py-2 text-xs font-bold text-[#6a7c79] dark:text-[#95a9a6] hover:text-[#b04b37] hover:border-[#b04b37]/30 transition"
                >
                  SIGN OUT
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => navigate('/auth')}
                className="rounded-full border border-[#173e42]/20 bg-white/60 dark:bg-white/10 px-4 py-2 text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee] hover:bg-white dark:hover:bg-white/20 transition"
              >
                SIGN IN
              </button>
            )}

            {/* File a Complaint Button */}
            <button
              onClick={() => {
                if (!isVerified) {
                  toast('Please verify your email before filing a complaint', { icon: '🛡️' })
                  navigate('/auth?redirect=/submit')
                } else {
                  navigate('/submit')
                }
              }}
              className="btn-gold text-xs shadow-[0_5px_16px_rgba(196,141,36,.18)]"
            >
              FILE A COMPLAINT
            </button>
          </div>

          {/* Mobile Right Bar: Theme Toggle + Menu */}
          <div className="flex sm:hidden items-center gap-2">
            <button
              onClick={toggleTheme}
              type="button"
              aria-label="Toggle theme"
              className="flex items-center justify-center size-9 rounded-full border border-[#173e42]/15 bg-white/60 dark:bg-white/10 text-[#0d3035] dark:text-[#e8b855]"
            >
              {isDark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="rounded-lg border border-[#173e42]/15 p-2 text-[#0d3035] dark:text-[#f6f4ee]"
              aria-label="Open navigation"
            >
              <CivicIcon name={menuOpen ? 'x' : 'menu'} size={20} />
            </button>
          </div>
        </div>

        {/* Mobile Slide-out Menu */}
        {menuOpen && (
          <div className="border-t border-[#173e42]/10 bg-[#f6f4ee] dark:bg-[#06181b] p-5 lg:hidden animate-fadeIn space-y-4">
            {isVerified ? (
              <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#e3f0ea] dark:bg-[#123830] text-xs font-bold text-[#2f7661] dark:text-[#70b99e] border border-[#347161]/20">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <CivicIcon name="shield" size={14} />
                    <span className="truncate">{user.first_name ? `${user.first_name} ${user.last_name || ''}`.trim() : user.email}</span>
                  </div>
                  {user.role === 'authority' && (
                    <p className="mt-0.5 text-[10px] font-bold text-[#ba7c29] uppercase">
                      Municipal Authority
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={handleSignOut}
                  className="text-[#b04b37] hover:underline shrink-0 text-xs font-bold pl-2"
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false)
                  navigate('/auth')
                }}
                className="w-full py-3 rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#0b2529] text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee] text-center"
              >
                Sign In to Citizen Account
              </button>
            )}

            <nav className="flex flex-col gap-3 text-sm font-semibold">
              <Link
                to="/"
                onClick={() => setMenuOpen(false)}
                className="p-2 rounded-lg hover:bg-black/5 dark:hover:bg-white/5"
              >
                Overview
              </Link>
              <Link
                to="/reports"
                onClick={() => setMenuOpen(false)}
                className="p-2 rounded-lg hover:bg-black/5 dark:hover:bg-white/5"
              >
                Incident Registry
              </Link>
              <a
                href="/#accountability"
                onClick={() => setMenuOpen(false)}
                className="p-2 rounded-lg hover:bg-black/5 dark:hover:bg-white/5"
              >
                Public Dashboard
              </a>
              <a
                href="/#how-it-works"
                onClick={() => setMenuOpen(false)}
                className="p-2 rounded-lg hover:bg-black/5 dark:hover:bg-white/5"
              >
                How it works
              </a>
            </nav>

            <button
              onClick={() => {
                setMenuOpen(false)
                if (!isVerified) {
                  navigate('/auth?redirect=/submit')
                } else {
                  navigate('/submit')
                }
              }}
              className="w-full btn-gold py-3 text-xs"
            >
              FILE A COMPLAINT
            </button>
          </div>
        )}
      </header>
    </>
  )
}
