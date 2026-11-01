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

  const [mode, setMode] = useState('login') // 'login' | 'signup'
  const [step, setStep] = useState('form') // 'form' | 'otp'

  // Login form state
  const [loginEmail, setLoginEmail] = useState('')
  const [unregisteredPrompt, setUnregisteredPrompt] = useState(null)

  // Signup form state
  const [signupForm, setSignupForm] = useState({
    firstName: '',
    lastName: '',
    email: '',
    dob: '',
    phone: '',
    address: '',
  })

  // OTP Verification state
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

  const setSignupField = (field) => (e) => {
    setSignupForm(prev => ({ ...prev, [field]: e.target.value }))
  }

  // Handle Login: Send OTP to existing registered citizen
  const handleLoginSendCode = async (e) => {
    e?.preventDefault()
    const cleanEmail = loginEmail.trim().toLowerCase()
    if (!cleanEmail || !cleanEmail.includes('@')) {
      toast.error('Please enter a valid registered email address')
      return
    }

    setSending(true)
    setUnregisteredPrompt(null)
    try {
      const { data } = await axios.post('/api/auth/login-send-code', { email: cleanEmail })
      const devNotice = data.dev_code ? ` (Dev code: ${data.dev_code})` : ''
      const msg = data.message || 'Verification code sent to your email inbox! (Please check your Spam/Junk folder if not in Inbox)'
      toast.success(
        `${msg}${devNotice}`,
        { duration: 8000, icon: '✉️' }
      )
      if (data.dev_code) {
        setOtp(data.dev_code)
      }
      setStep('otp')
      setCooldown(60)
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail
      if (status === 404) {
        setUnregisteredPrompt(cleanEmail)
        toast.error('This email is not registered. Want to create an account?', { duration: 5000 })
      } else {
        toast.error(detail || 'Failed to dispatch verification code')
      }
    } finally {
      setSending(false)
    }
  }

  // Handle Sign Up: Send OTP with citizen registration data
  const handleSignupSendCode = async (e) => {
    e?.preventDefault()
    const cleanEmail = signupForm.email.trim().toLowerCase()
    if (!cleanEmail || !cleanEmail.includes('@')) {
      toast.error('Please enter a valid email address')
      return
    }

    if (!signupForm.firstName.trim() || !signupForm.lastName.trim()) {
      toast.error('First and last name are required')
      return
    }

    if (!signupForm.dob) {
      toast.error('Date of birth is required')
      return
    }

    if (!signupForm.address.trim()) {
      toast.error('Primary residence address is required')
      return
    }

    const phoneClean = signupForm.phone.replace(/\D/g, '')
    if (phoneClean && phoneClean.length !== 10) {
      toast.error('Indian mobile number must be exactly 10 digits')
      return
    }
    const formattedPhone = phoneClean ? `+91 ${phoneClean}` : null

    setSending(true)
    try {
      const { data } = await axios.post('/api/auth/register-send-code', {
        first_name: signupForm.firstName.trim(),
        last_name: signupForm.lastName.trim(),
        email: cleanEmail,
        dob: signupForm.dob,
        phone: formattedPhone,
        address: signupForm.address.trim(),
      })
      const devNotice = data.dev_code ? ` (Dev code: ${data.dev_code})` : ''
      const msg = data.message || 'Verification code sent to your email inbox! (Please check your Spam/Junk folder if not in Inbox)'
      toast.success(
        `${msg}${devNotice}`,
        { duration: 8000, icon: '✉️' }
      )
      if (data.dev_code) {
        setOtp(data.dev_code)
      }
      setStep('otp')
      setCooldown(60)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (detail && detail.includes('already registered')) {
        toast.error('This email is already registered. Please sign in instead.')
        setLoginEmail(cleanEmail)
        setMode('login')
      } else {
        toast.error(detail || 'Failed to send registration code')
      }
    } finally {
      setSending(false)
    }
  }

  // Handle Verify Code (works for both Login & Signup)
  const handleVerifyCode = async (e, directCode = null) => {
    e?.preventDefault()
    const cleanCode = (directCode !== null && directCode !== undefined ? directCode : otp).trim()
    if (cleanCode.length !== 6) {
      toast.error('Please enter the full 6-digit verification code')
      return
    }

    const activeEmail = mode === 'signup' ? signupForm.email.trim().toLowerCase() : loginEmail.trim().toLowerCase()
    const phoneClean = signupForm.phone.replace(/\D/g, '')
    const formattedPhone = phoneClean ? `+91 ${phoneClean}` : null

    setVerifying(true)
    try {
      if (mode === 'signup') {
        const { data } = await axios.post('/api/auth/register-verify-code', {
          email: activeEmail,
          code: cleanCode,
          registration_data: {
            first_name: signupForm.firstName.trim(),
            last_name: signupForm.lastName.trim(),
            email: activeEmail,
            dob: signupForm.dob,
            phone: formattedPhone,
            address: signupForm.address.trim(),
          },
        })
        toast.success(`Citizen profile created! Welcome, ${data.user.first_name}.`)
        login(data.user, data.token)
      } else {
        const { data } = await axios.post('/api/auth/verify-code', {
          email: activeEmail,
          code: cleanCode,
        })
        toast.success(`Welcome back, ${data.user.first_name || 'Citizen'}!`)
        login(data.user, data.token)
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Invalid or expired code. Please try again.')
    } finally {
      setVerifying(false)
    }
  }

  const activeEmail = mode === 'signup' ? signupForm.email : loginEmail

  return (
    <main className="grid min-h-screen bg-[#f6f4ee] dark:bg-[#06181b] text-[#102a2f] dark:text-[#f6f4ee] lg:grid-cols-[1fr_1fr] transition-colors">
      {/* Left Form Column */}
      <section className="flex min-h-screen flex-col px-6 py-8 sm:px-12 lg:px-16 overflow-y-auto">
        <div className="flex items-center justify-between">
          <Brand />
          <div
            className="inline-flex items-center rounded-full border border-[#173e42]/15 dark:border-white/15 bg-black/5 dark:bg-white/5 p-0.5"
            role="group"
            aria-label="Color scheme theme"
          >
            <button
              type="button"
              onClick={() => isDark && toggleTheme()}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold transition-all ${
                !isDark
                  ? 'bg-white text-[#ba7c29] shadow-xs'
                  : 'text-[#829794] hover:text-[#f6f4ee]'
              }`}
              title="Light mode"
            >
              <Sun size={13} className={!isDark ? 'text-[#ba7c29]' : 'text-current'} />
              <span>Light</span>
            </button>
            <button
              type="button"
              onClick={() => !isDark && toggleTheme()}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold transition-all ${
                isDark
                  ? 'bg-[#12383e] text-[#e8b855] shadow-xs border border-[#e8b855]/25'
                  : 'text-[#617370] hover:text-[#0d3035]'
              }`}
              title="Dark mode"
            >
              <Moon size={13} className={isDark ? 'text-[#e8b855]' : 'text-current'} />
              <span>Dark</span>
            </button>
          </div>
        </div>

        <div className="mx-auto flex w-full max-w-lg flex-1 flex-col justify-center py-8">
          {/* Top Status & Mode Toggle */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-[#bd7f23]/25 bg-[#fffaf0] dark:bg-[#0d3035] px-3.5 py-1.5 text-[10px] font-bold tracking-[.16em] uppercase text-[#ba7c29] dark:text-[#e8b855] w-fit shadow-xs">
              <span className="size-1.5 rounded-full bg-[#347161]" />
              CITIZEN AUTHENTICATION
            </div>

            {step === 'form' && (
              <div className="flex rounded-full border border-[#173e42]/15 bg-white/70 dark:bg-[#0b2529] p-1 w-fit">
                <button
                  type="button"
                  onClick={() => {
                    setMode('login')
                    setStep('form')
                    setUnregisteredPrompt(null)
                  }}
                  className={`rounded-full px-4 py-1.5 text-xs font-bold transition ${
                    mode === 'login'
                      ? 'bg-[#0d3035] text-white shadow-sm'
                      : 'text-[#617471] dark:text-[#8ea5a2] hover:text-[#0d3035] dark:hover:text-white'
                  }`}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setMode('signup')
                    setStep('form')
                    setUnregisteredPrompt(null)
                  }}
                  className={`rounded-full px-4 py-1.5 text-xs font-bold transition ${
                    mode === 'signup'
                      ? 'bg-[#0d3035] text-white shadow-sm'
                      : 'text-[#617471] dark:text-[#8ea5a2] hover:text-[#0d3035] dark:hover:text-white'
                  }`}
                >
                  Sign Up
                </button>
              </div>
            )}
          </div>

          <h1 className="font-serif text-3xl sm:text-4xl font-bold tracking-tight text-[#0d3035] dark:text-[#f6f4ee]">
            {step === 'otp' ? (
              'Enter Verification Code'
            ) : mode === 'login' ? (
              <span>
                Sign in to <span className="text-[#ba7c29] dark:text-[#e8b855]">जन</span>Aawaz
              </span>
            ) : (
              'Create Citizen Profile'
            )}
          </h1>

          <p className="mt-2 text-xs sm:text-sm leading-relaxed text-[#687976] dark:text-[#95a9a6]">
            {step === 'otp'
              ? `We sent a 6-digit verification code to ${activeEmail}. Please check your Inbox and Spam/Junk folder. Enter it below to complete authentication.`
              : mode === 'login'
              ? 'Enter your registered email address to access your complaints, monitor engineering resolution dockets, and track responses.'
              : 'Register your citizen profile in the public municipal database to file complaints, attach verified evidence, and receive transparent updates.'}
          </p>

          {/* Form Step: Sign In */}
          {step === 'form' && mode === 'login' && (
            <form onSubmit={handleLoginSendCode} className="mt-8 space-y-4">
              <div>
                <label className="mb-2 block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                  Registered Citizen Email <span className="text-[#b04b37]">*</span>
                </label>
                <div className="relative">
                  <CivicIcon name="mail" size={18} className="absolute left-4 top-4 text-[#70817e]" />
                  <input
                    required
                    type="email"
                    autoFocus
                    value={loginEmail}
                    onChange={(e) => {
                      setLoginEmail(e.target.value)
                      if (unregisteredPrompt) setUnregisteredPrompt(null)
                    }}
                    placeholder="citizen@example.com"
                    className="w-full rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#0b2529] py-3.5 pl-11 pr-4 text-sm text-[#0d3035] dark:text-[#f6f4ee] outline-none placeholder:text-[#95a5a3] focus:border-[#ba7c29] focus:ring-2 focus:ring-[#ba7c29]/15 transition"
                  />
                </div>
              </div>

              {/* Unregistered Email Warning Card */}
              {unregisteredPrompt && (
                <div className="rounded-xl border border-[#bd7f23]/40 bg-[#fffaf0] dark:bg-[#1f1708] p-4 text-xs text-[#0d3035] dark:text-[#f6f4ee] shadow-sm animate-fadeIn">
                  <div className="flex items-start gap-3">
                    <CivicIcon name="alert" size={18} className="text-[#ba7c29] shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-bold text-sm text-[#0d3035] dark:text-[#f6f4ee]">
                        This email is not registered.
                      </p>
                      <p className="mt-1 text-[#6e7d7a] dark:text-[#95a9a6] text-xs leading-relaxed">
                        No citizen profile was found for <strong className="text-[#0d3035] dark:text-[#f6f4ee]">{unregisteredPrompt}</strong>. Want to create an account?
                      </p>
                      <div className="mt-3 flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setSignupForm(prev => ({ ...prev, email: unregisteredPrompt }))
                            setUnregisteredPrompt(null)
                            setMode('signup')
                          }}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-[#0d3035] dark:bg-[#e8b855] text-white dark:text-[#0d3035] px-3.5 py-2 text-xs font-bold hover:bg-[#16444a] dark:hover:bg-[#efc56b] transition shadow-sm"
                        >
                          <span>Yes, create account</span>
                          <CivicIcon name="arrow" size={13} />
                        </button>
                        <button
                          type="button"
                          onClick={() => setUnregisteredPrompt(null)}
                          className="rounded-lg border border-[#173e42]/20 dark:border-white/10 px-3 py-2 text-xs font-medium text-[#687976] dark:text-[#95a9a6] hover:bg-black/5 dark:hover:bg-white/5 transition"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={sending}
                className="flex w-full items-center justify-center gap-3 rounded-xl bg-[#0d3035] px-6 py-4 text-xs font-bold uppercase tracking-wider text-white transition hover:bg-[#16444a] disabled:opacity-60 shadow-md"
              >
                {sending ? 'Sending Verification Code...' : 'SIGN IN WITH EMAIL'}
                <CivicIcon name="arrow" size={16} />
              </button>

              <div className="text-center pt-2">
                <span className="text-xs text-[#70817e]">New here? </span>
                <button
                  type="button"
                  onClick={() => setMode('signup')}
                  className="text-xs font-bold text-[#ba7c29] hover:underline"
                >
                  Create citizen profile (Sign up)
                </button>
              </div>
            </form>
          )}

          {/* Form Step: Sign Up (Registration) */}
          {step === 'form' && mode === 'signup' && (
            <form onSubmit={handleSignupSendCode} className="mt-6 space-y-4">
              {/* First & Last Name */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div>
                  <label className="mb-1.5 block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    First Name <span className="text-[#b04b37]">*</span>
                  </label>
                  <input
                    required
                    type="text"
                    value={signupForm.firstName}
                    onChange={setSignupField('firstName')}
                    placeholder="e.g. Aarav"
                    className="w-full rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#0b2529] px-3.5 py-3 text-xs sm:text-sm text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    Last Name <span className="text-[#b04b37]">*</span>
                  </label>
                  <input
                    required
                    type="text"
                    value={signupForm.lastName}
                    onChange={setSignupField('lastName')}
                    placeholder="e.g. Sharma"
                    className="w-full rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#0b2529] px-3.5 py-3 text-xs sm:text-sm text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
                  />
                </div>
              </div>

              {/* Email Address */}
              <div>
                <label className="mb-1.5 block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                  Citizen Email Address <span className="text-[#b04b37]">*</span>
                </label>
                <div className="relative">
                  <CivicIcon name="mail" size={17} className="absolute left-3.5 top-3.5 text-[#70817e]" />
                  <input
                    required
                    type="email"
                    value={signupForm.email}
                    onChange={setSignupField('email')}
                    placeholder="aarav.sharma@example.com"
                    className="w-full rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#0b2529] py-3 pl-10 pr-3.5 text-xs sm:text-sm text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
                  />
                </div>
              </div>

              {/* DOB & Phone (Optional) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div>
                  <label className="mb-1.5 block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    Date of Birth (DOB) <span className="text-[#b04b37]">*</span>
                  </label>
                  <input
                    required
                    type="date"
                    value={signupForm.dob}
                    onChange={setSignupField('dob')}
                    max={new Date().toISOString().split('T')[0]}
                    className="w-full rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#0b2529] px-3.5 py-3 text-xs sm:text-sm text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
                  />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                      Mobile Number
                    </label>
                    <span className="text-[10px] text-[#70817e]">Optional</span>
                  </div>
                  <div className="relative flex items-center">
                    {/* Locked +91 Calling Code for India */}
                    <div className="absolute left-0 inset-y-0 flex items-center pl-3 pr-2.5 rounded-l-xl border-r border-[#173e42]/15 dark:border-white/10 bg-[#e7ebe8]/70 dark:bg-[#071c1e] select-none text-xs font-mono font-bold text-[#0d3035] dark:text-[#e8b855] pointer-events-none">
                      <span className="mr-1.5 text-xs">🇮🇳</span>
                      <span>+91</span>
                    </div>
                    <input
                      type="tel"
                      maxLength={10}
                      pattern="[0-9]{10}"
                      value={signupForm.phone}
                      onChange={(e) => {
                        const digits = e.target.value.replace(/\D/g, '').slice(0, 10)
                        setSignupForm(prev => ({ ...prev, phone: digits }))
                      }}
                      placeholder="98765 43210"
                      className="w-full rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#0b2529] py-3 pl-[76px] pr-3.5 text-xs sm:text-sm font-mono text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29] transition placeholder:text-[#95a5a3]"
                    />
                  </div>
                </div>
              </div>

              {/* Primary Address of Residence */}
              <div>
                <label className="mb-1.5 block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                  Primary Address of Residence <span className="text-[#b04b37]">*</span>
                </label>
                <textarea
                  required
                  rows={2}
                  value={signupForm.address}
                  onChange={setSignupField('address')}
                  placeholder="House/Flat number, Street name, Ward/Sector, City, Pin Code"
                  className="w-full resize-none rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#0b2529] p-3 text-xs sm:text-sm text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
                />
              </div>

              {/* Submit Sign Up */}
              <button
                type="submit"
                disabled={sending}
                className="flex w-full items-center justify-center gap-3 rounded-xl bg-[#0d3035] px-6 py-4 text-xs font-bold uppercase tracking-wider text-white transition hover:bg-[#16444a] disabled:opacity-60 shadow-md"
              >
                {sending ? 'Sending Verification Code...' : 'VERIFY EMAIL & CREATE PROFILE'}
                <CivicIcon name="arrow" size={16} />
              </button>

              <div className="text-center pt-2">
                <span className="text-xs text-[#70817e]">Already registered? </span>
                <button
                  type="button"
                  onClick={() => setMode('login')}
                  className="text-xs font-bold text-[#ba7c29] hover:underline"
                >
                  Sign in to account
                </button>
              </div>
            </form>
          )}

          {/* OTP Step (Both Modes) */}
          {step === 'otp' && (
            <form onSubmit={handleVerifyCode} className="mt-8 space-y-5">
              {/* Spam/Junk Folder Notice Banner */}
              <div className="rounded-xl border border-[#ba7c29]/35 bg-[#fffaf0] dark:bg-[#132a2f] p-3.5 text-xs text-[#8a5b17] dark:text-[#e8b855] flex items-start gap-2.5 shadow-xs">
                <CivicIcon name="mail" size={17} className="shrink-0 mt-0.5 text-[#ba7c29]" />
                <div className="space-y-1 text-left">
                  <p className="font-bold">Check your Inbox &amp; Spam / Junk folder</p>
                  <p className="text-[11px] text-[#6b7b79] dark:text-[#95a9a6] leading-relaxed">
                    A 6-digit verification code was dispatched to <strong className="text-[#0d3035] dark:text-[#f6f4ee]">{activeEmail}</strong>. If you do not see it in your primary inbox, please check your <strong>Spam or Junk folder</strong>.
                  </p>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    6-Digit Verification Code <span className="text-[#b04b37]">*</span>
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setStep('form')
                      setOtp('')
                    }}
                    className="text-[11px] font-bold text-[#ba7c29] hover:underline"
                  >
                    Edit information
                  </button>
                </div>

                <div className="relative">
                  <input
                    required
                    type="text"
                    maxLength={6}
                    autoFocus
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="[0-9]{6}"
                    value={otp}
                    onChange={(e) => {
                      const val = e.target.value.replace(/\D/g, '').slice(0, 6)
                      setOtp(val)
                      if (val.length === 6) {
                        handleVerifyCode(undefined, val)
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
                  onClick={mode === 'signup' ? handleSignupSendCode : handleLoginSendCode}
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
                {verifying
                  ? 'Verifying Code...'
                  : mode === 'signup'
                  ? 'VERIFY & SAVE CITIZEN PROFILE'
                  : 'VERIFY & ENTER PORTAL'}
                <CivicIcon name="check" size={17} />
              </button>
            </form>
          )}

          {/* Privacy Guarantee Note */}
          <div className="mt-8 flex items-start gap-3 rounded-xl border border-[#347161]/20 bg-[#e9efea] dark:bg-[#122824] p-4 text-xs leading-relaxed text-[#405654] dark:text-[#9eb5b1]">
            <CivicIcon name="shield" size={18} className="text-[#347161] shrink-0 mt-0.5" />
            <span>
              Your personal information, contact number, and address are securely stored and never exposed on public dashboards.
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
              CITIZEN REGISTRY
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
          <img
            src="/jan-icon-dark.png"
            alt="जनAawaz"
            className="size-14 rounded-2xl object-cover shadow-2xl border border-white/20 mb-3"
          />
          <blockquote className="mt-5 font-serif text-3xl leading-snug xl:text-4xl text-white">
            “Public problems deserve visible progress, not silent paperwork.”
          </blockquote>
          <p className="mt-4 max-w-lg text-xs sm:text-sm leading-relaxed text-white/60">
            Authenticated citizen records ensure municipal accountability, prevent duplicate work orders, and connect residents directly to engineering teams.
          </p>
        </div>
      </section>
    </main>
  )
}
