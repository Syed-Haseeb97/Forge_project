import { useState, useEffect } from 'react'
import axios from 'axios'
import toast from 'react-hot-toast'
import Brand from '../components/Brand'
import CivicIcon from '../components/CivicIcon'
import { useAuth } from '../components/AuthContext'
import { useTheme } from '../components/ThemeContext'
import { Sun, Moon } from 'lucide-react'

export default function AuthPage() {
  const { login } = useAuth()
  const { isDark, toggleTheme } = useTheme()

  const [step, setStep] = useState('email') // 'email' | 'otp'
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [sending, setSending] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  // Countdown timer for resend cooldown
  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setInterval(() => {
      setCooldown(prev => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [cooldown])

  // Handle sending verification email
  const handleSendCode = async (e) => {
    e?.preventDefault()
    const cleanEmail = email.trim().toLowerCase()
    if (!cleanEmail || !cleanEmail.includes('@')) {
      toast.error('Please enter a valid citizen email address')
      return
    }

    setSending(true)
    try {
      const { data } = await axios.post('/api/auth/send-code', { email: cleanEmail })
      toast.success(data.message || 'Verification code sent to your inbox!')
      setStep('otp')
      setCooldown(60)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to dispatch verification code')
    } finally {
      setSending(false)
    }
  }

  // Handle verifying OTP code
  const handleVerifyCode = async (e) => {
    e?.preventDefault()
    const cleanCode = otp.trim()
    if (cleanCode.length !== 6) {
      toast.error('Please enter the full 6-digit verification code')
      return
    }

    setVerifying(true)
    try {
      const { data } = await axios.post('/api/auth/verify-code', {
        email: email.trim().toLowerCase(),
        code: cleanCode,
      })
      toast.success('Citizen identity verified! Welcome to CivicLine.')
      login(data.user)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Invalid or expired code. Please try again.')
    } finally {
      setVerifying(false)
    }
  }

  return (
    <main className="grid min-h-screen bg-[#f6f4ee] dark:bg-[#06181b] text-[#102a2f] dark:text-[#f6f4ee] lg:grid-cols-[.92fr_1.08fr] transition-colors">
      {/* Left Form Column */}
      <section className="flex min-h-screen flex-col px-6 py-8 sm:px-12 lg:px-16">
        <div className="flex items-center justify-between">
          <Brand />
          <button
            onClick={toggleTheme}
            type="button"
            aria-label="Toggle visual theme"
            className="flex items-center justify-center size-9 rounded-full border border-[#173e42]/15 bg-white/60 dark:bg-white/10 text-[#0d3035] dark:text-[#e8b855] transition hover:bg-white"
          >
            {isDark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>

        <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
          <div className="inline-flex items-center gap-2 w-fit rounded-full border border-[#bd7f23]/25 bg-[#fffaf0] dark:bg-[#0d3035] px-3.5 py-1.5 text-[10px] font-bold tracking-[.16em] uppercase text-[#ba7c29] dark:text-[#e8b855]">
            <CivicIcon name="shield" size={13} className="text-[#347161]" />
            SECURE CITIZEN ACCESS
          </div>

          <h1 className="mt-4 font-serif text-3xl sm:text-5xl font-bold tracking-tight text-[#0d3035] dark:text-[#f6f4ee]">
            {step === 'email' ? 'Welcome to CivicLine' : 'Enter Verification Code'}
          </h1>

          <p className="mt-3 text-xs sm:text-sm leading-relaxed text-[#687976] dark:text-[#95a9a6]">
            {step === 'email'
              ? 'Verify your email to access the municipal grievance portal, file complaints with direct camera proof, and monitor resolution timelines.'
              : `We sent a 6-digit verification code to ${email}. Please enter it below to authenticate and enter the portal.`}
          </p>

          {step === 'email' ? (
            <form onSubmit={handleSendCode} className="mt-8 space-y-4">
              <div>
                <label className="mb-2 block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                  Citizen Email Address <span className="text-[#b04b37]">*</span>
                </label>
                <div className="relative">
                  <CivicIcon name="mail" size={18} className="absolute left-4 top-4 text-[#70817e]" />
                  <input
                    required
                    type="email"
                    autoFocus
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="citizen@example.com"
                    className="w-full rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#0b2529] py-3.5 pl-11 pr-4 text-sm text-[#0d3035] dark:text-[#f6f4ee] outline-none placeholder:text-[#95a5a3] focus:border-[#ba7c29] focus:ring-2 focus:ring-[#ba7c29]/15 transition"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={sending}
                className="flex w-full items-center justify-center gap-3 rounded-xl bg-[#0d3035] px-6 py-4 text-xs font-bold uppercase tracking-wider text-white transition hover:bg-[#16444a] disabled:opacity-60 shadow-md"
              >
                {sending ? 'Sending Verification Code...' : 'CONTINUE WITH EMAIL'}
                <CivicIcon name="arrow" size={16} />
              </button>
            </form>
          ) : (
            <form onSubmit={handleVerifyCode} className="mt-8 space-y-5">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    6-Digit Verification Code <span className="text-[#b04b37]">*</span>
                  </label>
                  <button
                    type="button"
                    onClick={() => setStep('email')}
                    className="text-[11px] font-bold text-[#ba7c29] hover:underline"
                  >
                    Change email
                  </button>
                </div>

                <div className="relative">
                  <input
                    required
                    type="text"
                    maxLength={6}
                    autoFocus
                    pattern="[0-9]{6}"
                    value={otp}
                    onChange={(e) => {
                      const val = e.target.value.replace(/\D/g, '')
                      setOtp(val)
                      if (val.length === 6) {
                        setTimeout(() => handleVerifyCode(), 100)
                      }
                    }}
                    placeholder="• • • • • •"
                    className="w-full text-center tracking-[0.4em] font-mono font-bold text-2xl rounded-xl border border-[#173e42]/20 bg-white dark:bg-[#0b2529] py-3.5 text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29] focus:ring-2 focus:ring-[#ba7c29]/15 transition"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between text-xs text-[#6e7d7a] dark:text-[#95a9a6]">
                <span>Didn't receive code?</span>
                <button
                  type="button"
                  disabled={cooldown > 0 || sending}
                  onClick={handleSendCode}
                  className="font-bold text-[#ba7c29] hover:underline disabled:opacity-50 disabled:no-underline"
                >
                  {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend Code'}
                </button>
              </div>

              <button
                type="submit"
                disabled={verifying || otp.length !== 6}
                className="flex w-full items-center justify-center gap-3 rounded-xl bg-[#e8b855] px-6 py-4 text-xs font-extrabold uppercase tracking-wider text-[#0d3035] transition hover:bg-[#efc56b] disabled:opacity-60 shadow-md"
              >
                {verifying ? 'Verifying Code...' : 'VERIFY & ENTER PORTAL'}
                <CivicIcon name="check" size={17} />
              </button>
            </form>
          )}

          {/* Privacy Guarantee Note */}
          <div className="mt-8 flex items-start gap-3 rounded-xl border border-[#347161]/20 bg-[#e9efea] dark:bg-[#122824] p-4 text-xs leading-relaxed text-[#405654] dark:text-[#9eb5b1]">
            <CivicIcon name="shield" size={18} className="mt-0.5 shrink-0 text-[#3f776b]" />
            <span>
              Your contact information is strictly confidential. Citizen emails and personal coordinates are never published on the public municipal dashboard.
            </span>
          </div>
        </div>
      </section>

      {/* Right Visual Column (Desktop) */}
      <section className="relative hidden overflow-hidden bg-[#0d3035] p-12 text-white lg:flex lg:flex-col lg:justify-end">
        <div className="civic-grid absolute inset-0 opacity-15 pointer-events-none" />

        {/* Image Montage */}
        <div className="absolute inset-x-12 top-10 h-[56%]">
          <div className="absolute inset-y-0 left-0 w-[70%] overflow-hidden rounded-[26px] shadow-2xl border border-white/10">
            <img
              src="https://images.unsplash.com/photo-1580060092295-dbe639fffda3?crop=entropy&cs=tinysrgb&fit=crop&fm=jpg&q=85&w=1200"
              alt="Citizens walking in city"
              className="size-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[#0d3035]/65 via-transparent to-transparent" />
            <div className="absolute bottom-5 left-5 rounded-full bg-white/90 px-3.5 py-1.5 text-[9px] font-bold tracking-[.14em] text-[#0d3035] uppercase">
              COMMUNITY IN ACTION
            </div>
          </div>

          <div className="absolute right-0 top-6 h-[44%] w-[35%] overflow-hidden rounded-2xl border-4 border-[#0d3035] shadow-2xl">
            <img
              src="https://images.unsplash.com/photo-1695834195972-9fd5877b8ad0?crop=entropy&cs=tinysrgb&fit=crop&fm=jpg&q=85&w=600"
              alt="City transport"
              className="size-full object-cover"
            />
          </div>

          <div className="absolute bottom-4 right-4 h-[38%] w-[30%] overflow-hidden rounded-2xl border-4 border-[#0d3035] shadow-2xl">
            <img
              src="https://images.unsplash.com/photo-1504244648668-89000185ea9b?crop=entropy&cs=tinysrgb&fit=crop&fm=jpg&q=85&w=600"
              alt="Community street"
              className="size-full object-cover"
            />
          </div>

          <div className="absolute -bottom-3 left-[56%] flex size-12 items-center justify-center rounded-full border-4 border-[#0d3035] bg-[#e8b855] text-[#0d3035] shadow-xl">
            <CivicIcon name="camera" size={20} />
          </div>
        </div>

        {/* Quote Block */}
        <div className="relative max-w-xl border-t border-white/15 pt-8">
          <span className="flex size-14 items-center justify-center rounded-full bg-[#e8b855] text-[#0d3035] shadow-lg">
            <CivicIcon name="shield" size={26} />
          </span>
          <blockquote className="mt-5 font-serif text-3xl leading-snug xl:text-4xl text-white">
            “Public problems deserve visible progress, not silent paperwork.”
          </blockquote>
          <p className="mt-4 max-w-lg text-xs sm:text-sm leading-relaxed text-white/60">
            One secure citizen account keeps all your submitted infrastructure reports, photo evidence, and engineering responses in one transparent place.
          </p>
        </div>
      </section>
    </main>
  )
}
