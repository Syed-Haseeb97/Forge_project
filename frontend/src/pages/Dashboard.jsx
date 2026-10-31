import { useEffect, useState } from 'react'
import axios from 'axios'
import { Link, useNavigate } from 'react-router-dom'
import CivicIcon from '../components/CivicIcon'
import { CATEGORIES } from '../components/constants'
import { useAuth } from '../components/AuthContext'
import toast from 'react-hot-toast'

export default function Dashboard() {
  const navigate = useNavigate()
  const { user, isVerified, isAuthority } = useAuth()
  const [stats, setStats] = useState(null)
  const [insights, setInsights] = useState(null)
  const [healthInfo, setHealthInfo] = useState(null)
  const [recent, setRecent] = useState([])
  const [criticalReports, setCriticalReports] = useState([])
  const [activeTab, setActiveTab] = useState('report') // 'report' | 'track'
  const [trackingId, setTrackingId] = useState('')
  const [trackingResult, setTrackingResult] = useState(null)
  const [searchingTicket, setSearchingTicket] = useState(false)

  // Quick report form state inside hero
  const [quickForm, setQuickForm] = useState({
    title: '',
    category: 'road_damage',
    description: '',
    location: '',
    latitude: '',
    longitude: '',
  })
  const [quickLocating, setQuickLocating] = useState(false)
  const [quickFile, setQuickFile] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [submittedReport, setSubmittedReport] = useState(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, reportsRes, insightsRes, healthRes] = await Promise.all([
          axios.get('/api/stats'),
          axios.get('/api/reports', { params: { limit: 8 } }),
          axios.get('/api/insights').catch(() => ({ data: null })),
          axios.get('/api/health').catch(() => ({ data: null })),
        ])
        setStats(statsRes.data)
        setRecent(reportsRes.data)
        setCriticalReports(reportsRes.data.filter(r => r.severity === 'critical' || r.severity === 'high'))
        if (insightsRes?.data) setInsights(insightsRes.data)
        if (healthRes?.data) setHealthInfo(healthRes.data)
      } catch (err) {
        console.error('Failed to load dashboard metrics', err)
      }
    }
    fetchData()
  }, [])

  const acquireQuickLocation = () => {
    if (!navigator.geolocation) {
      toast.error('Geolocation not supported by browser')
      return
    }
    setQuickLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(6))
        const lng = Number(pos.coords.longitude.toFixed(6))
        setQuickForm(f => ({ ...f, latitude: String(lat), longitude: String(lng) }))
        setQuickLocating(false)
        toast.success(`GPS coordinates captured (${lat}, ${lng})`)
      },
      () => {
        setQuickLocating(false)
        toast.error('Location permission denied or unavailable')
      },
      { timeout: 8000, enableHighAccuracy: true }
    )
  }

  const handleQuickSubmit = async (e) => {
    e.preventDefault()
    if (!isVerified) {
      toast('Please verify your email before filing a complaint', { icon: '🛡️' })
      navigate('/auth?redirect=/submit')
      return
    }

    if (!quickForm.title.trim() || !quickForm.description.trim()) {
      toast.error('Please enter issue title and description')
      return
    }

    // Must have coordinates or redirect to full submission page to place map pin
    if (!quickForm.latitude || !quickForm.longitude) {
      toast('Please specify incident location on the map to complete your report', { icon: '📍' })
      navigate('/submit', { state: { ...quickForm } })
      return
    }

    setProcessing(true)
    try {
      const fd = new FormData()
      Object.entries(quickForm).forEach(([k, v]) => v && fd.append(k, v))
      if (user?.email) fd.append('citizen_email', user.email)
      if (quickFile) fd.append('media', quickFile)

      const { data } = await axios.post('/api/reports', fd)
      setSubmittedReport(data)
      toast.success('Incident registered and triaged by AI')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Submission failed')
    } finally {
      setProcessing(false)
    }
  }

  const handleTrackLookup = async (e) => {
    e.preventDefault()
    if (!trackingId.trim()) return

    setSearchingTicket(true)
    setTrackingResult(null)
    try {
      const { data } = await axios.get('/api/reports/lookup', {
        params: { q: trackingId.trim() }
      })
      setTrackingResult(data)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No complaint found matching this reference number')
    } finally {
      setSearchingTicket(false)
    }
  }

  return (
    <div className="space-y-16 lg:space-y-24">
      {/* Authority Diagnostics Bar (Visible exclusively to Municipal Authority accounts) */}
      {isAuthority && healthInfo && (
        <div className="border-b border-[#ba7c29]/25 bg-[#fffaf0] dark:bg-[#071f23] px-5 py-2 text-[11px] font-mono text-[#0d3035] dark:text-[#f6f4ee] transition-colors">
          <div className="mx-auto max-w-[1240px] flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-[#15803d] animate-pulse" />
              <span className="font-bold text-[#ba7c29] uppercase tracking-wider text-[10px]">
                Authority Diagnostics
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-[10px]">
              <span>
                Gemini AI:{' '}
                <strong className={healthInfo.gemini_configured ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-600'}>
                  {healthInfo.gemini_configured ? 'Online' : 'Not configured'}
                </strong>
              </span>
              <span className="text-[#95a9a6]">•</span>
              <span>
                Email:{' '}
                <strong className={healthInfo.email_configured ? 'text-emerald-700 dark:text-emerald-400' : 'text-amber-600'}>
                  {healthInfo.email_configured ? 'Active' : 'Disabled'}
                </strong>
              </span>
              <span className="text-[#95a9a6]">•</span>
              <span>
                SLA Watchdog:{' '}
                <strong className={healthInfo.watchdog_running ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-600'}>
                  {healthInfo.watchdog_running ? 'Running' : 'Stopped'}
                </strong>
              </span>
              <span className="text-[#95a9a6]">•</span>
              <span>
                SLA Time Scale:{' '}
                <strong className="text-[#0d3035] dark:text-[#e8b855]">
                  {healthInfo.sla_time_scale || 1}x
                </strong>
              </span>
            </div>
          </div>
        </div>
      )}
      {/* Demo Time Compression Banner */}
      {stats?.sla_time_scale && stats.sla_time_scale !== 1 && (
        <div className="mx-auto max-w-[1240px] pt-4 px-4 sm:px-6">
          <div className="bg-gradient-to-r from-[#ba7c29] to-[#d99738] text-white py-2.5 px-4 sm:px-6 rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-2 text-xs font-bold shadow-md">
            <div className="flex items-center gap-2.5">
              <span className="relative flex size-2.5">
                <span className="animate-ping absolute inline-flex size-full rounded-full bg-white opacity-85" />
                <span className="relative inline-flex size-2.5 rounded-full bg-white" />
              </span>
              <span>DEMO TIME COMPRESSION ACTIVE: x{stats.sla_time_scale} ACCELERATION</span>
            </div>
            <span className="text-[10px] font-mono bg-black/20 px-2.5 py-0.5 rounded-full text-white/90">
              SLA Watchdog Background Agent Running
            </span>
          </div>
        </div>
      )}

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-4 pb-12 sm:pt-10 sm:pb-16">
        <div className="civic-grid absolute inset-0 opacity-40 pointer-events-none" />
        <div className="absolute -right-32 top-6 size-[440px] rounded-full border border-[#bd7f23]/15 pointer-events-none" />
        <div className="absolute -right-8 top-28 size-[260px] rounded-full border border-[#bd7f23]/20 pointer-events-none" />

        <div className="relative mx-auto grid max-w-[1240px] items-center gap-12 lg:grid-cols-[1.05fr_.95fr]">
          {/* Left Text Presentation */}
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[#bd7f23]/25 bg-[#fffaf0] dark:bg-[#0d3035] px-4 py-1.5 text-[11px] font-bold tracking-[0.14em] uppercase text-[#956018] dark:text-[#e8b855] shadow-xs">
              <span className="size-1.5 rounded-full bg-[#ba7c29] dark:bg-[#e8b855]" />
              <span><span className="text-[#ba7c29] dark:text-[#e8b855]">जन</span>Aawaz • AI-POWERED CIVIC RESPONSE</span>
            </div>

            <h1 className="max-w-2xl font-serif text-[44px] font-semibold leading-[1.03] tracking-[-0.035em] text-[#0d3035] dark:text-[#f6f4ee] sm:text-[62px] lg:text-[74px]">
              Speak up.<br />
              We’ll <em className="font-normal text-[#ba7c29]">take it forward.</em>
            </h1>

            <p className="mt-7 max-w-xl text-base leading-7 text-[#536866] dark:text-[#95a9a6] sm:text-lg">
              Share visual or audio evidence of local problems. <span className="font-bold text-[#0d3035] dark:text-[#f6f4ee]"><span className="text-[#ba7c29] dark:text-[#e8b855]">जन</span>Aawaz</span>’s multimodal AI understands what happened, evaluates the priority level, and forwards it to the responsible authority.
            </p>

            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <button
                onClick={() => {
                  setActiveTab('report')
                  document.getElementById('portal-card')?.scrollIntoView({ behavior: 'smooth' })
                }}
                className="btn-primary group"
              >
                REPORT AN ISSUE
                <span className="flex size-7 items-center justify-center rounded-full bg-white/10 transition group-hover:translate-x-1">
                  <CivicIcon name="arrow" size={16} />
                </span>
              </button>

              <button
                onClick={() => {
                  setActiveTab('track')
                  document.getElementById('portal-card')?.scrollIntoView({ behavior: 'smooth' })
                }}
                className="btn-secondary"
              >
                <CivicIcon name="search" size={17} /> TRACK A COMPLAINT
              </button>
            </div>

            <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-3 text-xs font-semibold text-[#667977] dark:text-[#8a9896]">
              <span className="flex items-center gap-2">
                <CivicIcon name="shield" size={17} className="text-[#3c776a] dark:text-[#70b99e]" />
                Your information is protected
              </span>
              <span className="flex items-center gap-2">
                <CivicIcon name="clock" size={17} className="text-[#3c776a] dark:text-[#70b99e]" />
                Takes less than 3 minutes
              </span>
            </div>
          </div>

          {/* Right Interactive Portal Card */}
          <div id="portal-card" className="relative mx-auto w-full max-w-[540px]">
            <div className="absolute -inset-4 rotate-2 rounded-[32px] bg-[#e9b955]/20 pointer-events-none" />
            <div className="relative overflow-hidden rounded-[26px] border border-white/70 dark:border-white/10 bg-white dark:bg-[#0d3035] shadow-[0_30px_70px_rgba(26,53,52,.16)]">
              {/* Tab Header */}
              <div className="flex border-b border-[#193d40]/10 dark:border-white/10 bg-[#fbfaf6] dark:bg-[#082024] p-1.5">
                <button
                  type="button"
                  onClick={() => setActiveTab('report')}
                  className={`flex-1 rounded-xl px-4 py-3 text-xs font-bold transition ${
                    activeTab === 'report'
                      ? 'bg-[#0d3035] dark:bg-[#e8b855] text-white dark:text-[#0d3035] shadow-sm'
                      : 'text-[#70807f] hover:text-[#0d3035] dark:text-[#8a9896] dark:hover:text-white'
                  }`}
                >
                  REPORT AN ISSUE
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('track')}
                  className={`flex-1 rounded-xl px-4 py-3 text-xs font-bold transition ${
                    activeTab === 'track'
                      ? 'bg-[#0d3035] dark:bg-[#e8b855] text-white dark:text-[#0d3035] shadow-sm'
                      : 'text-[#70807f] hover:text-[#0d3035] dark:text-[#8a9896] dark:hover:text-white'
                  }`}
                >
                  TRACK COMPLAINT
                </button>
              </div>

              {/* Tab Content 1: Report */}
              {activeTab === 'report' ? (
                processing ? (
                  <div className="flex min-h-[500px] flex-col items-center justify-center p-8 text-center">
                    <div className="ai-orbit relative flex size-20 items-center justify-center rounded-full bg-[#0d3035] text-[#e9b955]">
                      <CivicIcon name="brain" size={32} />
                      <span className="absolute -right-1 top-0 size-3 rounded-full bg-[#e9b955]" />
                    </div>
                    <p className="mt-7 text-[11px] font-bold tracking-[0.16em] text-[#ba7c29]">CIVIC AI IS REVIEWING</p>
                    <h2 className="mt-2 font-serif text-3xl font-bold">Assessing your report</h2>
                    <p className="mt-3 max-w-sm text-sm leading-6 text-[#687977] dark:text-[#95a9a6]">
                      Interpreting evidence, evaluating priority, and routing to the responsible engineering department.
                    </p>
                  </div>
                ) : submittedReport ? (
                  <div className="flex min-h-[460px] flex-col items-center justify-center p-8 text-center">
                    <div className="flex size-16 items-center justify-center rounded-full bg-[#e3f0ea] dark:bg-[#1a4540] text-[#2f7661] dark:text-[#70b99e]">
                      <CivicIcon name="check" size={30} />
                    </div>
                    <p className="mt-6 text-[11px] font-bold tracking-[0.16em] text-[#ba7c29]">
                      UNDERSTOOD, EVALUATED & FORWARDED
                    </p>
                    <h2 className="mt-2 font-serif text-3xl font-bold">Your report is in motion.</h2>
                    <p className="mt-3 max-w-sm text-sm leading-6 text-[#687977] dark:text-[#95a9a6]">
                      AI identified <strong className="text-[#0d3035] dark:text-[#e8b855]">{submittedReport.category.replace('_', ' ')}</strong> and forwarded docket <strong className="text-[#0d3035] dark:text-white font-mono">{submittedReport.docket_no || `#${submittedReport.id.substring(0, 8).toUpperCase()}`}</strong> to {submittedReport.routed_to}.
                    </p>
                    <div className="mt-6 grid w-full grid-cols-2 gap-3 text-left">
                      <div className="rounded-xl bg-[#fff4dd] dark:bg-amber-950/40 p-3.5 border border-amber-200 dark:border-amber-900/40">
                        <p className="text-[9px] font-bold tracking-[.12em] text-[#94611b] dark:text-amber-300">AI PRIORITY</p>
                        <p className="mt-1 flex items-center gap-1.5 text-sm font-extrabold capitalize text-amber-950 dark:text-amber-200">
                          <CivicIcon name="alert" size={15} /> {submittedReport.severity}
                        </p>
                      </div>
                      <div className="rounded-xl bg-[#e8f2ed] dark:bg-[#15454b] p-3.5 border border-emerald-200 dark:border-emerald-900/40">
                        <p className="text-[9px] font-bold tracking-[.12em] text-[#427465] dark:text-emerald-300">FORWARDED TO</p>
                        <p className="mt-1 flex items-center gap-1.5 text-sm font-extrabold text-emerald-950 dark:text-emerald-200 truncate">
                          <CivicIcon name="route" size={15} /> {submittedReport.routed_to}
                        </p>
                      </div>
                    </div>
                    <div className="mt-7 flex gap-3">
                      <Link
                        to={`/reports/${submittedReport.id}`}
                        className="btn-primary text-xs"
                      >
                        VIEW INCIDENT DOCKET →
                      </Link>
                      <button
                        onClick={() => {
                          setSubmittedReport(null)
                          setQuickForm({
                            title: '',
                            category: 'road_damage',
                            description: '',
                            location: '',
                            latitude: '',
                            longitude: '',
                          })
                          setQuickFile(null)
                        }}
                        className="btn-secondary text-xs"
                      >
                        FILE ANOTHER
                      </button>
                    </div>
                  </div>
                ) : (
                  <form onSubmit={handleQuickSubmit} className="p-6 sm:p-8 space-y-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="text-[10px] font-bold tracking-[0.16em] text-[#ba7c29]">SECURE CIVIC INGESTION</p>
                        <h2 className="mt-1 font-serif text-2xl font-bold">Tell us what happened</h2>
                      </div>
                      <span className="rounded-full bg-[#eef2ed] dark:bg-white/10 px-3 py-1.5 text-[10px] font-bold text-[#58706d] dark:text-[#95a9a6]">
                        2 MIN
                      </span>
                    </div>

                    <div>
                      <label className="mb-1.5 block text-xs font-bold text-[#102a2f] dark:text-[#f6f4ee]">
                        Issue Summary / Title
                      </label>
                      <input
                        required
                        className="input"
                        placeholder="e.g. Hazardous deep pothole near intersection"
                        value={quickForm.title}
                        onChange={e => setQuickForm(f => ({ ...f, title: e.target.value }))}
                      />
                    </div>

                    <div>
                      <label className="mb-1.5 block text-xs font-bold text-[#102a2f] dark:text-[#f6f4ee]">
                        Infrastructure Department
                      </label>
                      <select
                        className="input"
                        value={quickForm.category}
                        onChange={e => setQuickForm(f => ({ ...f, category: e.target.value }))}
                      >
                        {CATEGORIES.map(c => (
                          <option key={c.value} value={c.value}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="mb-1.5 block text-xs font-bold text-[#102a2f] dark:text-[#f6f4ee]">
                        Field Description
                      </label>
                      <textarea
                        required
                        rows={3}
                        className="input resize-none"
                        placeholder="What happened? Dimensions, safety hazard, nearby landmarks..."
                        value={quickForm.description}
                        onChange={e => setQuickForm(f => ({ ...f, description: e.target.value }))}
                      />
                    </div>

                    <div>
                      <div className="mb-1.5 flex items-center justify-between">
                        <label className="block text-xs font-bold text-[#102a2f] dark:text-[#f6f4ee]">
                          Location / Street Reference
                        </label>
                        <button
                          type="button"
                          onClick={acquireQuickLocation}
                          disabled={quickLocating}
                          className="flex items-center gap-1 text-[10px] font-bold text-[#ba7c29] hover:underline"
                        >
                          <CivicIcon name="location" size={11} />
                          <span>{quickLocating ? 'Acquiring GPS...' : (quickForm.latitude ? 'GPS Pinned ✓' : 'Pin My GPS')}</span>
                        </button>
                      </div>
                      <div className="relative">
                        <CivicIcon name="location" size={17} className="absolute left-3.5 top-3.5 text-[#617572]" />
                        <input
                          required
                          className="input pl-10"
                          placeholder="Street, landmark, or intersection"
                          value={quickForm.location}
                          onChange={e => setQuickForm(f => ({ ...f, location: e.target.value }))}
                        />
                      </div>
                      {!quickForm.latitude && (
                        <p className="mt-1 text-[10px] text-[#70807f] dark:text-[#95a9a6]">
                          💡 Submitting without GPS coordinates will open the interactive map picker.
                        </p>
                      )}
                    </div>

                    {/* Evidence buttons */}
                    <div className="pt-1">
                      <label className="mb-2 block text-xs font-bold text-[#102a2f] dark:text-[#f6f4ee]">
                        Photographic / Audio Evidence
                      </label>
                      <input
                        type="file"
                        id="quick-evidence-file"
                        className="hidden"
                        accept="image/*,audio/*"
                        onChange={e => setQuickFile(e.target.files[0] || null)}
                      />
                      <input
                        type="file"
                        id="quick-evidence-camera"
                        className="hidden"
                        accept="image/*"
                        capture="environment"
                        onChange={e => setQuickFile(e.target.files[0] || null)}
                      />

                      <div className="grid grid-cols-2 gap-2.5">
                        <button
                          type="button"
                          onClick={() => document.getElementById('quick-evidence-camera')?.click()}
                          className="flex items-center gap-2.5 rounded-xl border border-[#2d615c]/25 dark:border-white/10 bg-[#0d3035] dark:bg-white/10 p-3 text-left text-white transition hover:bg-[#16444a] dark:hover:bg-white/20"
                        >
                          <span className="flex size-7 items-center justify-center rounded-lg bg-white/10 text-[#e8b855]">
                            <CivicIcon name="camera" size={16} />
                          </span>
                          <span className="text-xs font-bold">Take Photo</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => document.getElementById('quick-evidence-file')?.click()}
                          className="flex items-center gap-2.5 rounded-xl border border-[#2d615c]/25 dark:border-white/10 bg-[#0d3035] dark:bg-white/10 p-3 text-left text-white transition hover:bg-[#16444a] dark:hover:bg-white/20"
                        >
                          <span className="flex size-7 items-center justify-center rounded-lg bg-white/10 text-[#e8b855]">
                            <CivicIcon name="upload" size={16} />
                          </span>
                          <span className="text-xs font-bold">Upload File</span>
                        </button>
                      </div>

                      {quickFile && (
                        <p className="mt-2 text-xs font-medium text-[#347161] dark:text-[#70b99e] flex items-center gap-1.5 truncate">
                          <CivicIcon name="check" size={14} /> Attached: {quickFile.name}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-3 rounded-xl border border-[#d6b873]/35 bg-[#fffaf0] dark:bg-amber-950/20 px-3.5 py-2.5">
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-[#0d3035] text-[#e9b955]">
                        <CivicIcon name="brain" size={15} />
                      </span>
                      <p className="text-[10px] leading-4 text-[#63716f] dark:text-[#cbd5e1]">
                        <strong className="text-[#273e40] dark:text-[#e8b855]">AI Understanding & Evaluation:</strong> The issue is identified, prioritized, and dispatched automatically.
                      </p>
                    </div>

                    <button
                      type="submit"
                      disabled={processing}
                      className="btn-gold w-full flex items-center justify-center gap-2 text-xs font-extrabold"
                    >
                      SUBMIT FOR AI EVALUATION <CivicIcon name="arrow" size={16} />
                    </button>
                  </form>
                )
              ) : (
                /* Tab Content 2: Track Complaint */
                <div className="min-h-[480px] p-6 sm:p-9 space-y-4">
                  <div>
                    <p className="text-[10px] font-bold tracking-[0.16em] text-[#ba7c29]">STATUS LOOKUP</p>
                    <h2 className="mt-1 font-serif text-3xl font-bold">Track your complaint</h2>
                    <p className="mt-2 text-sm leading-6 text-[#6b7b79] dark:text-[#95a9a6]">
                      Enter your docket ID or keyword to view real-time municipal engineering updates.
                    </p>
                  </div>

                  <form onSubmit={handleTrackLookup} className="space-y-3 pt-2">
                    <label className="block text-xs font-bold text-[#102a2f] dark:text-[#f6f4ee]">
                      Complaint ID / Docket Reference
                    </label>
                    <div className="relative">
                      <CivicIcon name="file" size={17} className="absolute left-3.5 top-3.5 text-[#718481]" />
                      <input
                        value={trackingId}
                        onChange={e => setTrackingId(e.target.value)}
                        placeholder="e.g. 1 or JA-2026-00001 or water burst"
                        className="input pl-10"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={searchingTicket}
                      className="btn-primary w-full py-3.5"
                    >
                      {searchingTicket ? 'SEARCHING REGISTRY...' : 'CHECK STATUS'} <CivicIcon name="arrow" size={16} />
                    </button>
                  </form>

                  {/* Tracking Result Card */}
                  {trackingResult && (
                    <div className="mt-4 rounded-xl border border-[#347161]/30 bg-[#edf5ef] dark:bg-[#12383e] p-4 text-xs space-y-2 animate-fadeIn">
                      <div className="flex items-center justify-between">
                        <span className="font-serif font-bold text-base text-[#0d3035] dark:text-[#f6f4ee]">
                          {trackingResult.title}
                        </span>
                        <span className={`px-2 py-0.5 rounded uppercase font-bold text-[10px] ${
                          trackingResult.status === 'resolved'
                            ? 'bg-emerald-100 text-emerald-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}>
                          {trackingResult.status.replace('_', ' ')}
                        </span>
                      </div>
                      <p className="text-[#536866] dark:text-[#cbd5e1] line-clamp-2">
                        {trackingResult.description}
                      </p>
                      <div className="pt-2 border-t border-black/10 dark:border-white/10 flex items-center justify-between">
                        <span className="text-[10px] text-[#718481] dark:text-[#95a9a6]">
                          Jurisdiction: {trackingResult.routed_to}
                        </span>
                        <Link
                          to={`/reports/${trackingResult.id}`}
                          className="font-bold text-[#0d3035] dark:text-[#e8b855] hover:underline"
                        >
                          View Full Docket →
                        </Link>
                      </div>
                    </div>
                  )}

                  <div className="rounded-xl border border-[#193d40]/10 dark:border-white/10 bg-[#f7f5ef] dark:bg-white/5 p-4 text-xs leading-5 text-[#637572] dark:text-[#95a9a6] flex items-start gap-3">
                    <CivicIcon name="shield" size={18} className="mt-0.5 shrink-0 text-[#3d776b] dark:text-[#70b99e]" />
                    <p>For your privacy, exact personal contact details are never exposed on public dashboards.</p>
                  </div>
                </div>
              )}
            </div>

            {/* Resolved Badge on Floating Card */}
            {stats && (
              <div className="absolute -bottom-5 -left-6 hidden sm:flex items-center gap-3 rounded-2xl border border-white dark:border-white/10 bg-white dark:bg-[#0d3035] px-4 py-3 shadow-[0_15px_35px_rgba(27,52,51,.15)]">
                <div className="flex size-9 items-center justify-center rounded-full bg-[#e4f0e8] text-[#33715f]">
                  <CivicIcon name="check" size={18} />
                </div>
                <div>
                  <p className="text-[10px] text-[#7e8e8b] dark:text-[#95a9a6]">Resolved</p>
                  <p className="text-sm font-extrabold text-[#0d3035] dark:text-[#f6f4ee]">
                    {stats.resolved + (stats.closed || 0)} issues
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="rounded-[30px] bg-[#0d3035] text-white p-7 sm:p-12 lg:p-16">
        <div className="max-w-[1240px] mx-auto">
          <div className="flex flex-col justify-between gap-5 border-b border-white/10 pb-8 sm:flex-row sm:items-end">
            <div>
              <p className="text-[11px] font-bold tracking-[0.18em] text-[#e8b855]">A SIMPLE, TRANSPARENT PROCESS</p>
              <h2 className="mt-3 max-w-xl font-serif text-3xl sm:text-4xl lg:text-5xl leading-tight">
                From your street to the right desk.
              </h2>
            </div>
            <p className="max-w-sm text-xs sm:text-sm leading-6 text-white/60">
              Every report is timestamped, triaged by machine vision, routed, and tracked so you always know what happens next.
            </p>
          </div>

          <div className="grid sm:grid-cols-3 pt-4">
            {[
              { no: '01', icon: 'camera', title: 'Capture the issue', copy: 'Share a photo, voice note, or written description from wherever you are.' },
              { no: '02', icon: 'brain', title: 'AI understands it', copy: 'AI interprets the visual or audio evidence and evaluates urgency level and SLA.' },
              { no: '03', icon: 'route', title: 'Forward & resolve', copy: 'The evaluated report is dispatched to the responsible department for field action.' },
            ].map((item, index) => (
              <article
                key={item.no}
                className={`py-8 sm:px-8 ${
                  index ? 'border-t border-white/10 sm:border-l sm:border-t-0' : ''
                } ${index === 0 ? 'sm:pl-0' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <span className="flex size-12 items-center justify-center rounded-full border border-[#e8b855]/40 text-[#e8b855]">
                    <CivicIcon name={item.icon} size={21} />
                  </span>
                  <span className="font-serif text-4xl text-white/15">{item.no}</span>
                </div>
                <h3 className="mt-6 font-serif text-2xl font-bold">{item.title}</h3>
                <p className="mt-2.5 max-w-xs text-xs sm:text-sm leading-6 text-white/60">{item.copy}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* AI Civic Intelligence & Pulse Brief Section */}
      {insights && (
        <section className="rounded-[28px] border border-amber-300/40 dark:border-amber-500/20 bg-[#fffdfa] dark:bg-[#072124] p-6 sm:p-10 shadow-sm space-y-6">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-black/10 dark:border-white/10 pb-6">
            <div className="flex items-center gap-3">
              <div className="flex size-12 items-center justify-center rounded-2xl bg-[#0d3035] text-[#e8b855] shadow-xs">
                <CivicIcon name="brain" size={24} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-[10px] font-bold tracking-[0.18em] uppercase text-[#ba7c29]">
                    LIVE MUNICIPAL INTELLIGENCE
                  </p>
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 font-bold">
                    10m Live Cache
                  </span>
                </div>
                <h2 className="font-serif text-2xl sm:text-3xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                  AI Civic Pulse Brief
                </h2>
              </div>
            </div>

            {/* Quick Metrics Pills */}
            <div className="flex flex-wrap items-center gap-2 text-xs font-bold">
              <span className="rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-white/5 px-3 py-2 text-[#0d3035] dark:text-white">
                {insights.total_reports} Logged Issues
              </span>
              <span className="rounded-xl border border-amber-200 dark:border-amber-900/30 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 text-amber-800 dark:text-amber-300">
                {insights.hotspots?.length || 0} 300m Hotspots
              </span>
              <span className="rounded-xl border border-rose-200 dark:border-rose-900/30 bg-rose-50 dark:bg-rose-950/40 px-3 py-2 text-rose-800 dark:text-rose-300">
                {insights.overdue_count || 0} Overdue
              </span>
            </div>
          </div>

          {/* Brief Content */}
          {insights.status === 'not_enough_data' || insights.brief === 'not enough data yet' ? (
            <div className="p-6 rounded-2xl bg-slate-50 dark:bg-white/5 text-center text-xs text-slate-500">
              Not enough data yet. Jan Aawaz requires at least 3 reported grievances to synthesize spatial hotspot clusters and compute departmental resolution velocity.
            </div>
          ) : (
            <div className="grid gap-6 lg:grid-cols-[1.2fr_.8fr]">
              {/* Executive Brief Text */}
              <div className="space-y-4">
                <p className="text-sm sm:text-base leading-relaxed text-[#2a4043] dark:text-[#cbd5e1] font-medium">
                  {insights.brief}
                </p>

                {/* Hotspot Clusters Highlights */}
                {insights.hotspots && insights.hotspots.length > 0 && (
                  <div className="rounded-2xl border border-amber-200/60 dark:border-amber-900/30 bg-[#fff9ed] dark:bg-amber-950/20 p-4 space-y-2">
                    <div className="flex items-center justify-between text-xs font-bold text-amber-900 dark:text-amber-300">
                      <span>Spatial 300m Clusters</span>
                      <Link to="/reports" className="text-[11px] underline hover:text-[#0d3035]">
                        View Map →
                      </Link>
                    </div>
                    <div className="flex flex-wrap gap-2 pt-1">
                      {insights.hotspots.slice(0, 4).map((h, i) => (
                        <span
                          key={i}
                          className="text-[11px] font-mono px-2.5 py-1 rounded-lg bg-white dark:bg-black/40 border border-amber-200 dark:border-amber-900/40 text-amber-900 dark:text-amber-200"
                        >
                          📍 {h.count}x {h.dominant_category.replace('_', ' ')}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* 3 Recommended Priority Actions */}
              <div className="space-y-3">
                <p className="text-xs font-bold uppercase tracking-wider text-[#0d3035] dark:text-[#e8b855]">
                  Recommended Municipal Interventions
                </p>
                <div className="space-y-2.5">
                  {insights.recommended_actions?.map((action, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-3 rounded-2xl border border-black/10 dark:border-white/10 bg-white dark:bg-[#0b2529] p-3.5 shadow-xs"
                    >
                      <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-[#0d3035] text-[11px] font-bold text-[#e8b855]">
                        {idx + 1}
                      </span>
                      <p className="text-xs leading-5 text-[#30484b] dark:text-[#e2e8f0] font-medium">
                        {action}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Live Public Accountability Section */}
      <section id="accountability">
        <div className="max-w-[1240px] mx-auto">
          <div className="grid items-end gap-6 lg:grid-cols-[1fr_.8fr] mb-10">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-[#2e7165]/20 bg-[#edf5ef] dark:bg-[#12383e] px-3.5 py-2 text-[10px] font-bold tracking-[.14em] text-[#347061] dark:text-[#70b99e]">
                <span className="size-2 animate-pulse rounded-full bg-[#3b8b72]" /> LIVE PUBLIC ACCOUNTABILITY
              </div>
              <h2 className="mt-4 font-serif text-3xl sm:text-5xl leading-[1.08] text-[#0d3035] dark:text-[#f6f4ee]">
                Every report counts.<br />
                <em className="font-normal text-[#ba7c29]">Every response is visible.</em>
              </h2>
            </div>
            <p className="max-w-lg text-xs sm:text-sm leading-relaxed text-[#617370] dark:text-[#95a9a6] lg:justify-self-end">
              Residents can see what is being reported, how quickly engineering departments respond, and which issues remain active—without exposing personal citizen details.
            </p>
          </div>

          <div className="grid gap-6 lg:grid-cols-[1.15fr_.85fr]">
            {/* Left Accountability Overview Card */}
            <div className="card">
              <div className="flex flex-col justify-between gap-4 border-b border-[#173e42]/10 dark:border-white/10 pb-5 sm:flex-row sm:items-center">
                <div>
                  <p className="text-[10px] font-bold tracking-[.14em] text-[#70817e] dark:text-[#8a9896]">
                    MUNICIPAL OVERVIEW
                  </p>
                  <h3 className="mt-1 font-serif text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    Service benchmark metrics
                  </h3>
                </div>
                {stats && (
                  <div className="flex gap-2 text-[10px] font-bold">
                    <span className="rounded-full bg-[#e7f2ec] dark:bg-[#15454b] px-3 py-1.5 text-[#33705f] dark:text-[#70b99e]">
                      {stats.resolved + (stats.closed || 0)} RESOLVED
                    </span>
                    <span className="rounded-full bg-[#fff2d8] dark:bg-amber-950/40 px-3 py-1.5 text-[#94611b] dark:text-amber-300">
                      {stats.open} OPEN
                    </span>
                  </div>
                )}
              </div>

              <div className="grid gap-7 pt-7 sm:grid-cols-[.85fr_1.15fr]">
                {/* Resolution Gauge */}
                <div className="flex min-h-[240px] flex-col justify-center rounded-2xl bg-[#0d3035] p-6 text-white shadow-sm">
                  <p className="text-[10px] font-bold tracking-[.15em] text-white/60">SLA COMPLIANCE</p>
                  <p className="mt-2 font-serif text-5xl sm:text-6xl font-bold">
                    {stats?.total > 0 && stats?.sla_compliance_rate !== undefined ? (
                      <>
                        {stats.sla_compliance_rate}<span className="text-3xl text-[#e8b855]">%</span>
                      </>
                    ) : (
                      '—'
                    )}
                  </p>
                  <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/15">
                    <div
                      className="h-full rounded-full bg-[#e8b855] transition-all duration-500"
                      style={{ width: `${stats?.total > 0 ? (stats?.sla_compliance_rate || 0) : 0}%` }}
                    />
                  </div>
                  <p className="mt-3 text-xs leading-5 text-white/60">
                    Average turnaround: {stats?.avg_resolution_hours > 0 ? `${stats.avg_resolution_hours}h` : '—'}
                  </p>
                </div>

                {/* Category Breakdown */}
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]">Reports by category</p>
                    <span className="text-[#3f776b] dark:text-[#70b99e]">
                      <CivicIcon name="chart" size={18} />
                    </span>
                  </div>

                  <div className="space-y-4">
                    {stats?.by_category &&
                      Object.entries(stats.by_category).slice(0, 4).map(([cat, count]) => {
                        const pct = stats.total > 0 ? Math.round((count / stats.total) * 100) : 25
                        return (
                          <div key={cat}>
                            <div className="mb-1.5 flex justify-between text-xs">
                              <span className="font-semibold text-[#102a2f] dark:text-[#f6f4ee] capitalize">
                                {cat.replace('_', ' ')}
                              </span>
                              <span className="text-[#7b8987] font-mono">{count}</span>
                            </div>
                            <div className="h-1.5 rounded-full bg-[#e9ece6] dark:bg-white/10">
                              <div
                                className="h-full rounded-full bg-[#3f776b] dark:bg-[#e8b855]"
                                style={{ width: `${Math.max(pct, 12)}%` }}
                              />
                            </div>
                          </div>
                        )
                      })}
                  </div>
                </div>
              </div>
            </div>

            {/* Right Priority Watch Card */}
            <div className="card bg-[#fffaf0] dark:bg-[#082024] border-[#d6b873]/30">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-bold tracking-[.14em] text-[#95661e] dark:text-[#e8b855]">
                    PRIORITY WATCH
                  </p>
                  <h3 className="mt-1 font-serif text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    Urgent local issues
                  </h3>
                </div>
                <span className="flex size-10 items-center justify-center rounded-full bg-[#f4dfb6] dark:bg-amber-950/60 text-[#95661e] dark:text-amber-300">
                  <CivicIcon name="alert" size={20} />
                </span>
              </div>

              <div className="mt-6 space-y-3">
                {criticalReports.length === 0 ? (
                  <p className="text-xs text-[#788683] py-6 text-center">No critical hazards currently active.</p>
                ) : (
                  criticalReports.slice(0, 3).map((r, index) => (
                    <article
                      key={r.id}
                      className="rounded-xl border border-[#6d572b]/15 dark:border-white/10 bg-white dark:bg-[#0d3035] p-3.5 shadow-xs transition hover:border-[#ba7c29]"
                    >
                      <Link to={`/reports/${r.id}`} className="block">
                        <div className="flex items-start gap-3">
                          <span
                            className={`mt-1 size-2 shrink-0 rounded-full ${
                              r.severity === 'critical' ? 'bg-[#b04b37] animate-ping' : 'bg-[#d69636]'
                            }`}
                          />
                          <div className="min-w-0 flex-1">
                            <h4 className="text-xs font-bold text-[#102a2f] dark:text-[#f6f4ee] truncate">
                              {r.title}
                            </h4>
                            <p className="mt-0.5 text-[10px] text-[#788683] dark:text-[#95a9a6] truncate">
                              {r.location} · {r.sla_hours ? `${r.sla_hours}h SLA` : 'Urgent'}
                            </p>
                            <div className="mt-2 flex items-center gap-1.5 text-[9px] font-bold tracking-[.08em] text-[#427266] dark:text-[#70b99e] uppercase">
                              <CivicIcon name="route" size={12} /> ROUTED TO {r.routed_to}
                            </div>
                          </div>
                        </div>
                      </Link>
                    </article>
                  ))
                )}
              </div>

              <Link
                to="/reports?severity=critical"
                className="btn-secondary w-full mt-5 text-[11px] font-bold py-2.5"
              >
                EXPLORE REGISTRY <CivicIcon name="arrow" size={14} />
              </Link>
            </div>
          </div>
        </div>
      </section>

    </div>
  )
}
