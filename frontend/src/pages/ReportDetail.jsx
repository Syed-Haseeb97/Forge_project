import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import axios from 'axios'
import toast from 'react-hot-toast'
import {
  Star,
  ThumbsUp,
  ChevronDown,
  ChevronUp,
  Cpu,
  Sparkles,
  Copy,
  Check,
  AlertTriangle,
  Clock,
  Mail,
  CheckCircle2,
  XCircle,
  Volume2,
  VolumeX,
  Languages,
  Loader2,
} from 'lucide-react'
import CivicIcon from '../components/CivicIcon'
import { isWatched, toggleWatchlist } from '../components/constants'
import CivicMap from '../components/CivicMap'
import CameraCapture from '../components/CameraCapture'
import { useAuth } from '../components/AuthContext'

const STATUSES = ['open', 'in_progress', 'resolved', 'closed']

const SUPPORTED_LANGS = [
  { code: 'en', label: 'English', native: 'English', voiceLang: 'en-IN' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी', voiceLang: 'hi-IN' },
  { code: 'ta', label: 'Tamil', native: 'தமிழ்', voiceLang: 'ta-IN' },
  { code: 'ml', label: 'Malayalam', native: 'മലയാളം', voiceLang: 'ml-IN' },
  { code: 'te', label: 'Telugu', native: 'తెలుగు', voiceLang: 'te-IN' },
  { code: 'kn', label: 'Kannada', native: 'ಕನ್ನಡ', voiceLang: 'kn-IN' },
  { code: 'bn', label: 'Bengali', native: 'বাংলা', voiceLang: 'bn-IN' },
  { code: 'mr', label: 'Marathi', native: 'मराठी', voiceLang: 'mr-IN' },
]

export default function ReportDetail() {
  const { id } = useParams()
  const { user, isAuthority } = useAuth()
  const [report, setReport] = useState(null)
  const [timeline, setTimeline] = useState([])
  const [dispatches, setDispatches] = useState([])
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [showTrace, setShowTrace] = useState(true)
  const [copiedDispatch, setCopiedDispatch] = useState(false)
  const [submittingFeedback, setSubmittingFeedback] = useState(false)
  const [watched, setWatched] = useState(false)

  // Resolve modal/form state
  const [showResolveForm, setShowResolveForm] = useState(false)
  const [resolveNotes, setResolveNotes] = useState('')
  const [resolveActor, setResolveActor] = useState('')
  const [resolveProofFile, setResolveProofFile] = useState(null)
  const [resolveProofPreview, setResolveProofPreview] = useState(null)
  const [resolving, setResolving] = useState(false)

  // Multilingual Plain-Language Explainer & Speech Synthesis state
  const [selectedLang, setSelectedLang] = useState('en')
  const [explanation, setExplanation] = useState('')
  const [loadingExplanation, setLoadingExplanation] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const speechSupported = typeof window !== 'undefined' && 'speechSynthesis' in window

  const loadData = async () => {
    try {
      const [rRes, tRes, dRes] = await Promise.all([
        axios.get(`/api/reports/${id}`),
        axios.get(`/api/reports/${id}/timeline`).catch(() => ({ data: [] })),
        axios.get(`/api/reports/${id}/dispatches`).catch(() => ({ data: [] })),
      ])
      setReport(rRes.data)
      setTimeline(tRes.data)
      setDispatches(dRes.data)
      setWatched(isWatched(rRes.data.id))
    } catch {
      toast.error('Failed to load incident record')
    } finally {
      setLoading(false)
    }
  }

  const fetchExplanation = async (langCode) => {
    setLoadingExplanation(true)
    if (speechSupported) {
      window.speechSynthesis.cancel()
      setIsSpeaking(false)
    }
    try {
      const { data } = await axios.post(`/api/reports/${id}/explain?lang=${langCode}`)
      setExplanation(data.text)
    } catch (err) {
      console.error('Failed to load plain-language explanation', err)
      toast.error('Could not load explanation for selected language')
    } finally {
      setLoadingExplanation(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [id])

  // Poll live trace if report is actively triaging
  useEffect(() => {
    if (!id || !report || report.triage_status !== 'triaging') return

    const interval = setInterval(async () => {
      try {
        const { data } = await axios.get(`/api/reports/${id}/trace`)
        setReport(prev => {
          if (!prev) return prev
          return {
            ...prev,
            triage_status: data.triage_status,
            severity: data.severity || prev.severity,
            routed_to: data.routed_to || prev.routed_to,
            sla_hours: data.sla_hours || prev.sla_hours,
            agent_trace: data.agent_trace,
            needs_human_review: data.needs_human_review,
          }
        })
        if (data.is_complete) {
          clearInterval(interval)
          loadData()
        }
      } catch (e) {
        console.error('Error polling trace:', e)
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [id, report?.triage_status])

  useEffect(() => {
    if (id && report && report.triage_status === 'done' && !['spam', 'suspicious'].includes(report.authenticity)) {
      fetchExplanation(selectedLang)
    }
  }, [id, selectedLang, report?.triage_status, report?.authenticity])

  // Cleanup speech synthesis on component unmount
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  const handleToggleSpeech = () => {
    if (!speechSupported || !explanation) return
    if (isSpeaking) {
      window.speechSynthesis.cancel()
      setIsSpeaking(false)
      return
    }

    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(explanation)
    const currentLangObj = SUPPORTED_LANGS.find(l => l.code === selectedLang)
    utterance.lang = currentLangObj?.voiceLang || 'en-IN'
    utterance.rate = 0.95
    utterance.onend = () => setIsSpeaking(false)
    utterance.onerror = () => setIsSpeaking(false)
    setIsSpeaking(true)
    window.speechSynthesis.speak(utterance)
  }

  const handleUpvote = async () => {
    try {
      const { data } = await axios.post(`/api/reports/${id}/upvote`)
      setReport(r => ({ ...r, upvotes: data.upvotes, has_upvoted: Boolean(data.has_upvoted) }))
      if (data.has_upvoted) {
        toast.success('Recorded municipal endorsement')
      } else {
        toast.success('Removed municipal endorsement')
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to record endorsement')
    }
  }

  const handleToggleWatch = () => {
    const updated = toggleWatchlist(report.id)
    const isNow = updated.includes(report.id)
    setWatched(isNow)
    toast.success(isNow ? 'Added to Monitored Registry' : 'Removed from Monitored Registry')
  }

  const handleCopyDispatch = (text) => {
    if (!text) return
    navigator.clipboard.writeText(text)
    setCopiedDispatch(true)
    toast.success('Dispatch letter copied to clipboard', { icon: '📋' })
    setTimeout(() => setCopiedDispatch(false), 2500)
  }

  const handleFeedback = async (feedbackType) => {
    const note = feedbackType === 'disputed'
      ? window.prompt('Please state why this grievance remains unresolved on the ground:')
      : 'Resolution verified on-site by resident.'
    if (feedbackType === 'disputed' && note === null) return

    setSubmittingFeedback(true)
    try {
      const { data } = await axios.post(`/api/reports/${id}/feedback`, {
        feedback: feedbackType,
        notes: note || undefined,
      })
      setReport(data)
      const tRes = await axios.get(`/api/reports/${id}/timeline`)
      setTimeline(tRes.data)
      toast.success(
        feedbackType === 'disputed'
          ? 'Dispute lodged. Docket returned to active engineering status.'
          : 'Thank you for confirming the municipal resolution!',
        { icon: feedbackType === 'disputed' ? '⚠️' : '✅' }
      )
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Feedback submission failed')
    } finally {
      setSubmittingFeedback(false)
    }
  }

  const handleStatusChange = async (status) => {
    if (status === 'resolved') {
      setShowResolveForm(true)
      return
    }
    setUpdating(true)
    try {
      await axios.patch(`/api/reports/${id}/status?status=${status}`)
      setReport(r => ({ ...r, status }))
      toast.success(`Docket status updated to ${status.replace('_', ' ')}`)
      const tRes = await axios.get(`/api/reports/${id}/timeline`)
      setTimeline(tRes.data)
    } catch {
      toast.error('Failed to update status')
    } finally {
      setUpdating(false)
    }
  }

  const handleResolveProofSubmit = async (e) => {
    e.preventDefault()
    if (!resolveNotes.trim()) {
      toast.error('Please enter formal resolution notes')
      return
    }
    setResolving(true)
    try {
      const fd = new FormData()
      fd.append('status', 'resolved')
      fd.append('resolution_notes', resolveNotes)
      if (resolveActor && resolveActor.trim()) fd.append('actor', resolveActor.trim())
      if (resolveProofFile) fd.append('media', resolveProofFile)

      const { data } = await axios.post(`/api/reports/${id}/resolve`, fd)
      setReport(data)
      setShowResolveForm(false)
      setResolveProofFile(null)
      setResolveProofPreview(null)
      toast.success('Incident marked resolved with verified closeout evidence')

      const tRes = await axios.get(`/api/reports/${id}/timeline`)
      setTimeline(tRes.data)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to submit resolution audit')
    } finally {
      setResolving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[480px] flex-col items-center justify-center py-20 text-center">
        <div className="ai-orbit relative flex size-16 items-center justify-center rounded-full bg-[#0d3035] text-[#e8b855]">
          <CivicIcon name="brain" size={26} />
          <span className="absolute -right-1 top-0 size-2.5 rounded-full bg-[#e8b855]" />
        </div>
        <p className="mt-5 font-serif text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">Loading Incident Record</p>
        <p className="mt-1 text-xs text-[#6e807e] dark:text-[#8ea5a2]">Accessing public audit trail and triage parameters...</p>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="mx-auto max-w-xl py-20 text-center">
        <div className="rounded-[26px] border border-[#173e42]/15 bg-white dark:bg-[#0b2529] p-10">
          <CivicIcon name="alert" size={32} className="mx-auto text-[#b04b37]" />
          <h2 className="mt-4 font-serif text-2xl font-bold">Record Not Found</h2>
          <p className="mt-2 text-xs text-[#687a77] dark:text-[#8ea5a2]">This incident docket does not exist in the active public database.</p>
          <Link to="/reports" className="mt-6 inline-flex items-center gap-2 rounded-full bg-[#0d3035] px-6 py-3 text-xs font-bold text-white">
            Return to Incident Registry
          </Link>
        </div>
      </div>
    )
  }

  const isCritical = report.severity === 'critical'
  const isHigh = report.severity === 'high'
  const [analysisText, recommendedActionText] = (report.ai_analysis || '').split('**Recommended Action:**')
  const referenceCode = report.docket_no || (typeof report.id === 'string' && report.id.length > 8 ? `JA-2026-${report.id.slice(0, 8).toUpperCase()}` : `JA-2026-${String(report.id).padStart(5, '0')}`)

  let traceSteps = []
  if (report.agent_trace) {
    try {
      traceSteps = typeof report.agent_trace === 'string' ? JSON.parse(report.agent_trace) : report.agent_trace
    } catch {
      traceSteps = []
    }
  }

  return (
    <div className="min-h-screen bg-[#f6f4ee] dark:bg-[#06181b] text-[#102a2f] dark:text-[#f6f4ee] transition-colors py-8 sm:py-12">
      <div className="mx-auto max-w-[960px] px-5 lg:px-8 space-y-6">

        {/* Top Breadcrumbs & Actions */}
        <div className="flex items-center justify-between">
          <Link
            to="/reports"
            className="group inline-flex items-center gap-2 text-xs sm:text-sm font-bold text-[#0d3035] dark:text-[#f6f4ee] hover:text-[#ba7c29] transition"
          >
            <span className="flex size-7 items-center justify-center rounded-full border border-[#173e42]/15 bg-white dark:bg-[#0b2529] transition group-hover:-translate-x-0.5">
              <CivicIcon name="arrow" size={14} className="rotate-180" />
            </span>
            <span>Back to Incident Registry</span>
          </Link>

          <button
            type="button"
            onClick={handleToggleWatch}
            className={`flex items-center gap-2 rounded-full px-4 py-2 text-xs font-bold transition border ${
              watched
                ? 'bg-[#ba7c29] text-white border-[#ba7c29] shadow-sm'
                : 'bg-white dark:bg-[#0b2529] text-[#0d3035] dark:text-[#f6f4ee] border-[#173e42]/15 hover:border-[#ba7c29]'
            }`}
          >
            <Star size={13} fill={watched ? 'currentColor' : 'none'} className={watched ? 'text-white' : 'text-[#ba7c29]'} />
            <span>{watched ? 'Monitored in Watchlist' : 'Monitor Incident'}</span>
          </button>
        </div>

        {/* Main Incident Overview Card */}
        <article
          className={`overflow-hidden rounded-[26px] p-6 sm:p-9 border shadow-[0_20px_50px_rgba(27,52,51,.08)] transition ${
            isCritical
              ? 'bg-[#fffcfb] dark:bg-[#181112] border-2 border-[#b04b37] dark:border-[#e05d43]'
              : 'bg-white dark:bg-[#0b2529] border-[#173e42]/12 dark:border-[#173e42]/30'
          }`}
        >
          {/* SLA Watchdog Overdue Alert */}
          {report.is_overdue && (
            <div className="bg-[#b04b37] text-white text-[10px] sm:text-[11px] font-bold tracking-[0.14em] uppercase px-5 py-2.5 flex items-center justify-between -mx-6 sm:-mx-9 -mt-6 sm:-mt-9 mb-6 shadow-md animate-pulse">
              <span className="flex items-center gap-2">
                <AlertTriangle size={15} />
                SLA DEADLINE EXCEEDED · ESCALATED TO CIVIC OVERSIGHT (LEVEL {report.escalation_level || 3})
              </span>
              <span className="bg-black/35 text-white font-mono text-[10px] px-2.5 py-0.5 rounded-full font-bold">
                OVERDUE
              </span>
            </div>
          )}

          {/* SLA Watchdog Tiered Escalation Notice */}
          {!report.is_overdue && report.escalation_level > 0 && (
            <div className="bg-[#ba7c29] text-white text-[10px] sm:text-[11px] font-bold tracking-[0.14em] uppercase px-5 py-2 flex items-center justify-between -mx-6 sm:-mx-9 -mt-6 sm:-mt-9 mb-6 shadow-sm">
              <span className="flex items-center gap-2">
                <Clock size={14} />
                SLA WATCHDOG ACTIVE · ESCALATION LEVEL {report.escalation_level} (REMINDER DISPATCHED)
              </span>
              <span className="bg-black/25 text-white font-mono text-[10px] px-2.5 py-0.5 rounded-full font-bold">
                LEVEL {report.escalation_level}
              </span>
            </div>
          )}

          {/* Critical Alert Strip */}
          {isCritical && (
            <div className="bg-[#b04b37] text-white text-[10px] sm:text-[11px] font-bold tracking-[0.14em] uppercase px-5 py-2 flex items-center justify-between -mx-6 sm:-mx-9 -mt-6 sm:-mt-9 mb-6 shadow-sm">
              <span className="flex items-center gap-2">
                <span className="relative flex size-2">
                  <span className="animate-ping absolute inline-flex size-full rounded-full bg-white opacity-85" />
                  <span className="relative inline-flex size-2 rounded-full bg-white" />
                </span>
                CRITICAL INFRASTRUCTURE HAZARD · TARGET PRIORITY 1
              </span>
              <span className="bg-black/25 text-white font-mono text-[10px] px-2.5 py-0.5 rounded font-bold uppercase">
                {report.sla_hours ? `${report.sla_hours}H SLA DEADLINE` : 'IMMEDIATE SLA'}
              </span>
            </div>
          )}

          {/* Heading Row */}
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-[#173e42]/10 dark:border-[#173e42]/30 pb-6">
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#e3f0ea] dark:bg-[#123830] px-3 py-1 text-[10px] font-bold tracking-wider text-[#2f7661] dark:text-[#70b99e] uppercase">
                  <CivicIcon name="route" size={13} />
                  {report.routed_to ? `ROUTED TO ${report.routed_to.toUpperCase()}` : 'ROUTED TO PUBLIC WORKS'}
                </span>
                <span className="font-mono text-xs font-semibold text-[#8a9b98] dark:text-[#6f8582]">
                  {referenceCode}
                </span>
              </div>

              <h1 className="font-serif text-2xl sm:text-4xl font-bold leading-tight text-[#0d3035] dark:text-[#f6f4ee]">
                {report.title}
              </h1>
            </div>

            {/* Badges */}
            <div className="flex flex-wrap items-center gap-2 shrink-0">
              {report.needs_human_review && isAuthority && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#fef3c7] dark:bg-[#2e230d] text-[#b45309] dark:text-[#fde68a] border border-[#f59e0b]/40 px-3 py-1 text-xs font-bold uppercase shadow-sm">
                  <AlertTriangle size={13} /> AI IS UNSURE: HUMAN REVIEW RECOMMENDED
                </span>
              )}

              {/* Phase M: Authenticity Badges */}
              {report.authenticity === 'genuine' && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#e3f0ea] text-[#2f7661] border border-[#347161]/30 px-3 py-1 text-xs font-bold uppercase">
                  <CivicIcon name="check" size={13} /> AUTHENTIC
                </span>
              )}
              {report.authenticity === 'suspicious' && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#fef3c7] text-[#b45309] border border-[#f59e0b]/40 px-3 py-1 text-xs font-bold uppercase">
                  <AlertTriangle size={13} /> HELD: SUSPICIOUS
                </span>
              )}
              {report.authenticity === 'spam' && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#fce8e6] text-[#b04b37] border border-[#b04b37]/40 px-3 py-1 text-xs font-bold uppercase">
                  <CivicIcon name="alert" size={13} /> HELD: SPAM
                </span>
              )}

              {report.triage_status === 'triaging' ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#fef3c7] dark:bg-[#2e230d] text-[#b45309] dark:text-[#fde68a] border border-[#f59e0b]/40 px-3 py-1 text-xs font-bold uppercase animate-pulse">
                  <Loader2 size={13} className="animate-spin" /> TRIAGING...
                </span>
              ) : isCritical ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#fce8e6] text-[#b04b37] border border-[#b04b37]/30 px-3 py-1 text-xs font-extrabold uppercase">
                  <CivicIcon name="alert" size={13} /> CRITICAL
                </span>
              ) : isHigh ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#fff4dd] text-[#956018] border border-[#bd7f23]/30 px-3 py-1 text-xs font-bold uppercase">
                  <CivicIcon name="alert" size={13} /> HIGH
                </span>
              ) : (
                <span className="rounded-full bg-[#f0f4f3] dark:bg-[#163035] px-3 py-1 text-xs font-bold uppercase text-[#556e6b] dark:text-[#8ea7a4]">
                  {report.severity}
                </span>
              )}

              {report.status === 'resolved' ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#e3f0ea] text-[#2f7661] border border-[#347161]/30 px-3 py-1 text-xs font-bold uppercase">
                  <CivicIcon name="check" size={13} /> RESOLVED
                </span>
              ) : report.status === 'in_progress' ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#fff4dd] text-[#94611b] border border-[#e8b855]/30 px-3 py-1 text-xs font-bold uppercase">
                  <CivicIcon name="clock" size={13} /> IN PROGRESS
                </span>
              ) : (
                <span className="rounded-full bg-[#f0f4f5] dark:bg-[#173035] px-3 py-1 text-xs font-bold uppercase text-[#527174] dark:text-[#95b0b3]">
                  OPEN
                </span>
              )}
            </div>
          </div>

          {/* Phase M: Authenticity Gate "Under Review" Banner */}
          {['suspicious', 'spam'].includes(report.authenticity) && (
            <div className="my-6 p-4 sm:p-5 rounded-2xl border-2 border-amber-500/40 bg-amber-50/90 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={16} className="text-amber-600 dark:text-amber-400 shrink-0" />
                    <h4 className="font-bold text-xs uppercase tracking-wider text-amber-900 dark:text-amber-200">
                      Under Review: {report.authenticity_reason || 'Could not immediately confirm this is an actionable civic issue'}
                    </h4>
                  </div>
                  <p className="text-xs opacity-90 pl-6">
                    This ticket is held from public feeds and automated dispatch pending human municipal review.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2 pl-6 sm:pl-0">
                  {report.is_owner && !report.appeal_submitted && (
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          await axios.post(`/api/reports/${id}/appeal`, { note: 'Citizen appealed via docket page' });
                          toast.success('Appeal submitted to municipal oversight queue');
                          loadData();
                        } catch (err) {
                          toast.error(err.response?.data?.detail || 'Failed to submit appeal');
                        }
                      }}
                      className="px-3.5 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs transition shadow-xs"
                    >
                      Appeal Classification
                    </button>
                  )}

                  {isAuthority && (
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            await axios.post(`/api/reports/${id}/authenticity`, { verdict: 'genuine', note: 'Approved by municipal authority' });
                            toast.success('Report approved as genuine. Dispatched to department.');
                            loadData();
                          } catch (err) {
                            toast.error(err.response?.data?.detail || 'Failed to update authenticity');
                          }
                        }}
                        className="px-3 py-1.5 rounded-lg bg-[#2f7661] hover:bg-[#235848] text-white font-bold text-xs transition shadow-xs"
                      >
                        Approve (Genuine)
                      </button>
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            await axios.post(`/api/reports/${id}/authenticity`, { verdict: 'spam', note: 'Marked spam by municipal authority' });
                            toast.success('Report confirmed as spam.');
                            loadData();
                          } catch (err) {
                            toast.error(err.response?.data?.detail || 'Failed to update authenticity');
                          }
                        }}
                        className="px-3 py-1.5 rounded-lg bg-[#b04b37] hover:bg-[#8c3b2b] text-white font-bold text-xs transition shadow-xs"
                      >
                        Mark Spam
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Description */}
          <div className="py-6">
            <h3 className="text-xs font-bold uppercase tracking-[0.12em] text-[#8a9996] mb-2">
              CITIZEN STATEMENT & OBSERVATIONS
            </h3>
            <p className="text-sm sm:text-base leading-relaxed text-[#2f4244] dark:text-[#c4d6d3]">
              {report.description}
            </p>
          </div>

          {/* Evidence Photo */}
          {report.media_url && report.media_url.match(/\.(jpg|jpeg|png|webp|gif)$/i) && (
            <div className="mb-6 overflow-hidden rounded-2xl border border-[#173e42]/15 bg-[#0d3035]/5">
              <span className="block bg-[#f8f8f4] dark:bg-[#06181b] px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#70817e] border-b border-[#173e42]/10">
                CITIZEN FIELD PHOTOGRAPHIC RECORD
              </span>
              <img
                src={report.media_url}
                alt={report.title}
                className="w-full max-h-96 object-cover"
              />
            </div>
          )}

          {/* Audio Evidence */}
          {report.media_url && report.media_url.match(/\.(mp3|wav|ogg|m4a|webm|mp4|aac|opus)$/i) && (
            <div className="mb-6 rounded-2xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] p-4">
              <span className="block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee] mb-2">
                CITIZEN AUDIO TESTIMONIAL RECORD
              </span>
              <audio controls src={report.media_url} className="w-full" />
            </div>
          )}

          {/* Meta Columns */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-6 border-t border-[#173e42]/10 dark:border-[#173e42]/30 text-xs">
            <div>
              <span className="block text-[10px] font-bold uppercase tracking-wider text-[#8a9b98]">LOCATION</span>
              <span className="mt-1 font-semibold text-[#0d3035] dark:text-[#f6f4ee] truncate block">{report.location}</span>
            </div>
            <div>
              <span className="block text-[10px] font-bold uppercase tracking-wider text-[#8a9b98]">DEPARTMENT</span>
              <span className="mt-1 font-semibold text-[#0d3035] dark:text-[#f6f4ee] truncate block">{report.routed_to || 'Public Works'}</span>
            </div>
            <div>
              <span className="block text-[10px] font-bold uppercase tracking-wider text-[#8a9b98]">TARGET SLA</span>
              <span className="mt-1 font-semibold text-[#0d3035] dark:text-[#f6f4ee] block">{report.sla_hours ? `${report.sla_hours} Hours` : 'N/A'}</span>
            </div>
            <div>
              <span className="block text-[10px] font-bold uppercase tracking-wider text-[#8a9b98]">ENDORSEMENTS</span>
              <button
                type="button"
                onClick={handleUpvote}
                className="mt-1 inline-flex items-center gap-1.5 font-bold text-[#ba7c29] hover:underline"
              >
                <ThumbsUp size={12} />
                <span>{report.upvotes || 0} Citizens</span>
              </button>
            </div>
          </div>
        </article>

        {/* Multilingual Plain-Language Explainer (जन संवाद) */}
        <div className="rounded-[26px] border border-teal-800/20 dark:border-teal-400/20 bg-[#f4f8f6] dark:bg-[#072428] p-6 sm:p-8 space-y-4 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-xl bg-[#0d3035] text-[#e8b855] shrink-0">
                <Languages size={20} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#347061] dark:text-[#70b99e]">
                    CITIZEN MULTILINGUAL EXPLAINER
                  </p>
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-teal-100 dark:bg-teal-900/60 text-teal-800 dark:text-teal-300 font-bold">
                    जन संवाद
                  </span>
                </div>
                <h2 className="font-serif text-xl sm:text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                  Plain-Language Docket Summary
                </h2>
              </div>
            </div>

            {/* Language Selector & Listen Button */}
            <div className="flex items-center flex-wrap gap-2 sm:self-center">
              <div className="relative">
                <select
                  value={selectedLang}
                  onChange={(e) => setSelectedLang(e.target.value)}
                  className="text-xs font-bold rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-[#0b2529] text-slate-800 dark:text-slate-100 py-2 pl-3 pr-8 shadow-xs cursor-pointer focus:outline-hidden focus:ring-2 focus:ring-[#0d3035]"
                >
                  {SUPPORTED_LANGS.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                      {lang.native} ({lang.label})
                    </option>
                  ))}
                </select>
              </div>

              {speechSupported && (
                <button
                  type="button"
                  onClick={handleToggleSpeech}
                  disabled={loadingExplanation || !explanation}
                  className={`inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition shadow-xs ${
                    isSpeaking
                      ? 'bg-rose-600 hover:bg-rose-700 text-white animate-pulse'
                      : 'bg-[#0d3035] hover:bg-[#124249] text-[#e8b855]'
                  }`}
                  title={isSpeaking ? 'Stop voice playback' : 'Read aloud in selected language'}
                >
                  {isSpeaking ? (
                    <>
                      <VolumeX size={15} />
                      <span>Stop Listening</span>
                    </>
                  ) : (
                    <>
                      <Volume2 size={15} />
                      <span>Listen</span>
                    </>
                  )}
                </button>
              )}
            </div>
          </div>

          {/* Explanation Text */}
          <div className="rounded-xl border border-teal-800/15 dark:border-white/10 bg-white dark:bg-[#0b2529] p-5 text-sm leading-relaxed text-[#2a4043] dark:text-[#cbd5e1] space-y-3">
            {loadingExplanation ? (
              <div className="flex items-center gap-3 py-4 text-xs font-medium text-slate-500">
                <div className="w-4 h-4 border-2 border-teal-600 border-t-transparent rounded-full animate-spin"></div>
                <span>Translating and simplifying docket briefing into {SUPPORTED_LANGS.find(l => l.code === selectedLang)?.native || selectedLang}...</span>
              </div>
            ) : explanation ? (
              <div className="space-y-3">
                <p className="whitespace-pre-line font-medium leading-relaxed">
                  {explanation}
                </p>
                <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-500">
                  <span>Language: <strong className="text-slate-700 dark:text-slate-300">{SUPPORTED_LANGS.find(l => l.code === selectedLang)?.native}</strong></span>
                  <span className="text-[10px] font-mono text-teal-700 dark:text-teal-400">AI-generated summary</span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic py-2">
                Click a language above to generate a plain-language summary.
              </p>
            )}
          </div>
        </div>

        {/* Multimodal AI Technical Triage Card */}
        {report.ai_analysis && (
          <div className="rounded-[26px] border border-[#d6b873]/35 bg-[#fffaf0] dark:bg-[#121c1f] p-6 sm:p-8 space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-xl bg-[#0d3035] text-[#e8b855]">
                <CivicIcon name="brain" size={20} />
              </div>
              <div>
                <p className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#956018] dark:text-[#e8b855]">
                  AUTOMATED MULTIMODAL EVALUATION
                </p>
                <h2 className="font-serif text-xl sm:text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                  AI Technical Diagnosis & Engineering Protocol
                </h2>
              </div>
            </div>

            <div className="rounded-xl border border-[#d6b873]/25 bg-white dark:bg-[#0b2529] p-4 text-xs sm:text-sm leading-relaxed text-[#405658] dark:text-[#a5b9b6] space-y-3">
              <p className="whitespace-pre-line">{analysisText.trim()}</p>

              {recommendedActionText && (
                <div className="pt-3 border-t border-[#173e42]/10 dark:border-[#173e42]/30">
                  <span className="block text-[10px] font-bold uppercase tracking-wider text-[#ba7c29] mb-1">
                    MANDATED REMEDIATION PROTOCOL:
                  </span>
                  <p className="font-semibold text-[#0d3035] dark:text-[#f6f4ee]">
                    {recommendedActionText.trim()}
                  </p>
                </div>
              )}
            </div>

            {report.safety_precautions && (
              <div className="flex items-start gap-3 rounded-xl border border-[#b04b37]/30 bg-[#fff5f2] dark:bg-[#201210] p-4 text-xs">
                <CivicIcon name="alert" size={18} className="mt-0.5 shrink-0 text-[#b04b37]" />
                <div>
                  <span className="block text-[10px] font-extrabold uppercase tracking-wider text-[#b04b37]">
                    PUBLIC SAFETY CAUTION FOR RESIDENTS:
                  </span>
                  <p className="mt-0.5 font-medium text-[#7d2f21] dark:text-[#f5a192]">
                    {report.safety_precautions}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Collapsible AI Reasoning Trace Card */}
        {(report.agent_trace || report.severity_rationale || report.triage_status === 'triaging') && (
          <div className="rounded-[26px] border border-[#173e42]/15 dark:border-white/10 bg-white dark:bg-[#0b2529] p-6 sm:p-8 space-y-5 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-xl bg-[#0d3035] text-[#e8b855]">
                  <Cpu size={20} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#ba7c29]">
                      AGENTIC CIVIC TRIAGE PIPELINE
                    </p>
                    {report.confidence !== null && report.confidence !== undefined && (
                      <span className="rounded-full bg-[#e3f0ea] dark:bg-[#123830] px-2 py-0.5 text-[10px] font-bold text-[#2f7661] dark:text-[#70b99e]">
                        {Math.round(report.confidence * 100)}% Confidence
                      </span>
                    )}
                  </div>
                  <h2 className="font-serif text-xl sm:text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    AI Reasoning Trace & Decision Signals
                  </h2>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setShowTrace(!showTrace)}
                className="flex items-center gap-1.5 rounded-full border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] px-3.5 py-1.5 text-xs font-bold text-[#556b68] dark:text-[#95a9a6] hover:text-[#0d3035] dark:hover:text-white transition"
              >
                <span>{showTrace ? 'Collapse Trace' : 'Expand Trace'}</span>
                {showTrace ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
              </button>
            </div>

            {showTrace && (
              <div className="space-y-4 pt-2">
                {/* Live Triage Pulse State */}
                {report.triage_status === 'triaging' && (
                  <div className="flex items-center gap-3 p-3.5 rounded-xl border border-[#ba7c29]/30 bg-[#fffaf0] dark:bg-[#1a2522]">
                    <Loader2 size={16} className="animate-spin text-[#ba7c29] shrink-0" />
                    <div className="text-xs">
                      <span className="font-bold text-[#ba7c29]">Live Multi-Signal Agent Triage in Progress: </span>
                      <span className="text-[#556b68] dark:text-[#95a9a6]">Streaming steps concurrently... Severity, department and SLA will lock once decision agent finishes.</span>
                    </div>
                  </div>
                )}

                {/* Confidence Bar */}
                {report.confidence !== null && report.confidence !== undefined && (
                  <div className="rounded-xl border border-[#173e42]/10 dark:border-white/10 bg-[#f8f8f4] dark:bg-[#06181b] p-3.5 space-y-1.5">
                    <div className="flex items-center justify-between text-xs font-bold">
                      <span className="text-[#556b68] dark:text-[#95a9a6]">Triage Confidence Rating</span>
                      <span className="font-mono text-[#0d3035] dark:text-[#e8b855]">{Math.round(report.confidence * 100)}%</span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-[#ba7c29] to-[#347161] transition-all duration-500"
                        style={{ width: `${Math.min(100, Math.max(10, Math.round(report.confidence * 100)))}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Triage Rationale Quote Box */}
                {report.severity_rationale && (
                  <div className="rounded-xl border border-[#ba7c29]/30 bg-[#fffaf0] dark:bg-[#1a2522] p-4 text-xs leading-relaxed">
                    <div className="flex items-center gap-2 mb-1.5 text-[#ba7c29] font-bold uppercase text-[10px] tracking-wider">
                      <Sparkles size={14} />
                      <span>Multi-Signal Synthesis Rationale</span>
                    </div>
                    <p className="text-[#3b4e4c] dark:text-[#cad8d5] font-medium italic">
                      “{report.severity_rationale}”
                    </p>
                    {(report.locality || report.detected_language) && (
                      <p className="mt-2 text-[10px] text-[#718481] dark:text-[#8ea5a2] border-t border-[#ba7c29]/15 pt-2">
                        {report.locality && <span>Locality Reference: <strong>{report.locality}</strong></span>}
                        {report.locality && report.detected_language && <span className="mx-2">•</span>}
                        {report.detected_language && <span>Detected Citizen Language: <strong>{report.detected_language}</strong></span>}
                      </p>
                    )}
                  </div>
                )}

                {/* Step-by-Step Execution Trace */}
                {traceSteps.length > 0 && (
                  <div className="space-y-2.5">
                    <p className="text-[10px] font-bold tracking-wider uppercase text-[#718481] dark:text-[#8ea5a2]">
                      Pipeline Execution Sequence ({traceSteps.length} steps)
                    </p>
                    <div className="divide-y divide-[#173e42]/10 dark:divide-white/10 rounded-xl border border-[#173e42]/10 dark:border-white/10 bg-[#f8f8f4] dark:bg-[#06181b] overflow-hidden">
                      {traceSteps.map((step, idx) => {
                        const isFallback = step.status === 'fallback'
                        const isDegraded = step.status === 'degraded'
                        const isSuccess = step.status === 'success'
                        const isWarning = step.status === 'warning'
                        const isError = step.status === 'error'
                        return (
                          <div key={idx} className="p-3.5 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div className="flex items-start gap-3">
                              <span className="flex size-7 items-center justify-center rounded-lg bg-white dark:bg-[#0b2529] border border-[#173e42]/10 dark:border-white/10 text-[#0d3035] dark:text-[#e8b855] font-mono text-[11px] font-bold shrink-0 mt-0.5 sm:mt-0">
                                {idx + 1}
                              </span>
                              <div>
                                <div className="flex items-center gap-2">
                                  <span className="font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                                    {step.step.replace('_', ' ').toUpperCase()}
                                  </span>
                                  <span className="font-mono text-[10px] text-[#718481] dark:text-[#8ea5a2]">
                                    via {step.tool}
                                  </span>
                                </div>
                                <p className="mt-0.5 text-[#556b68] dark:text-[#95a9a6] text-xs">
                                  {step.summary}
                                </p>
                                {(step.data?.transcript || step.data?.english_translation) && (
                                  <div className="mt-2 rounded-lg border border-[#ba7c29]/25 bg-[#fffaf0] dark:bg-[#1a2522] p-2.5 text-[11px] space-y-1">
                                    <div className="flex items-center gap-2 font-bold text-[#ba7c29] text-[10px] uppercase tracking-wide">
                                      <span>Spoken Voice Evidence Detected</span>
                                      {step.data.detected_language && (
                                        <span className="rounded bg-[#ba7c29]/20 px-1.5 py-0.5 text-[9px]">
                                          {step.data.detected_language}
                                        </span>
                                      )}
                                    </div>
                                    {step.data.transcript && (
                                      <p className="text-[#3b4e4c] dark:text-[#cad8d5] italic">
                                        “{step.data.transcript}”
                                      </p>
                                    )}
                                    {step.data.english_translation && (
                                      <p className="text-[#2f7661] dark:text-[#70b99e] font-medium border-t border-[#ba7c29]/15 pt-1">
                                        <span className="font-semibold text-[#1d5242] dark:text-[#8ac5b0]">English Translation: </span>
                                        “{step.data.english_translation}”
                                      </p>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>

                            <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                              <span className="font-mono text-[10px] text-[#8a9b98]">
                                {step.duration_ms}ms
                              </span>
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                                isSuccess
                                  ? 'bg-[#e3f0ea] dark:bg-[#123830] text-[#2f7661] dark:text-[#70b99e]'
                                  : isWarning
                                  ? 'bg-amber-100 dark:bg-amber-950/80 text-amber-800 dark:text-amber-300 border border-amber-400'
                                  : isDegraded
                                  ? 'bg-amber-100 dark:bg-amber-950/80 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-700/50'
                                  : isFallback
                                  ? 'bg-[#fff4dd] dark:bg-amber-950/60 text-[#94611b] dark:text-amber-300'
                                  : isError
                                  ? 'bg-[#ffebe8] dark:bg-red-950/60 text-[#b04b37]'
                                  : 'bg-black/5 dark:bg-white/10 text-[#718481]'
                              }`}>
                                {step.status}
                              </span>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Dispatch Pending State during Triage */}
        {report.triage_status === 'triaging' && (!dispatches || dispatches.length === 0) && (
          <div className="rounded-[26px] border border-[#173e42]/15 dark:border-white/10 bg-white dark:bg-[#0b2529] p-6 sm:p-8 space-y-3 shadow-sm text-center">
            <div className="inline-flex size-10 items-center justify-center rounded-xl bg-[#0d3035] text-[#e8b855] mx-auto">
              <Mail size={20} />
            </div>
            <div>
              <p className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#ba7c29]">
                DEPARTMENTAL DISPATCH
              </p>
              <h2 className="font-serif text-lg sm:text-xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                Dispatch Work Order Pending Triage Completion
              </h2>
            </div>
            <p className="text-xs text-[#556b68] dark:text-[#95a9a6] max-w-lg mx-auto">
              Departmental work order will be generated autonomously and transmitted once the live AI triage pipeline concludes.
            </p>
          </div>
        )}

        {/* Dispatch Work Order Card */}
        {dispatches && dispatches.length > 0 && (
          <div className="rounded-[26px] border border-[#173e42]/15 dark:border-white/10 bg-white dark:bg-[#0b2529] p-6 sm:p-8 space-y-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#173e42]/10 dark:border-white/10 pb-4">
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-xl bg-[#0d3035] text-[#e8b855]">
                  <Mail size={20} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#ba7c29]">
                      DEPARTMENTAL DISPATCH TRANSMISSION
                    </p>
                    <span className="rounded-full bg-[#e3f0ea] dark:bg-[#123830] px-2 py-0.5 text-[10px] font-bold text-[#2f7661] dark:text-[#70b99e]">
                      {dispatches.length} {dispatches.length === 1 ? 'Notice' : 'Notices'}{dispatches[0].sent ? ' Transmitted' : ''}
                    </span>
                  </div>
                  <h2 className="font-serif text-xl sm:text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                    Prototype Dispatch Work Order
                  </h2>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleCopyDispatch(dispatches[0].body)}
                  className="flex items-center gap-1.5 rounded-full border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] px-4 py-2 text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee] hover:bg-[#ba7c29] hover:text-white transition shadow-xs"
                >
                  {copiedDispatch ? <Check size={14} className="text-[#347161]" /> : <Copy size={14} />}
                  <span>{copiedDispatch ? 'Copied to Clipboard' : 'Copy Dispatch Letter'}</span>
                </button>
              </div>
            </div>

            {/* Note on transmission destination */}
            <p className="text-xs text-[#6e807e] dark:text-[#95a9a6]">
              {dispatches[0].sent
                ? (dispatches[0].mode === 'demo'
                    ? 'Sent (demo inbox)'
                    : `Sent to ${dispatches[0].recipient_office || 'department'}`)
                : 'Not sent'
              } on {new Date(dispatches[0].created_at).toLocaleString()}.
            </p>

            {/* Latest Dispatch Letter Presentation */}
            <div className="rounded-xl border border-[#173e42]/10 dark:border-white/10 bg-[#f8f8f4] dark:bg-[#06181b] p-4 font-mono text-xs leading-relaxed text-[#354f4d] dark:text-[#a0b8b5] whitespace-pre-wrap max-h-80 overflow-y-auto">
              <div className="pb-3 mb-3 border-b border-[#173e42]/10 dark:border-white/10 font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                SUBJECT: {dispatches[0].subject}
              </div>
              {dispatches[0].body}
            </div>
          </div>
        )}

        {/* Verified Resolution Proof (Pre vs Post Remediation Comparison) */}
        {(report.resolved_media_url || report.resolution_notes || report.resolution_verdict) && (
          <div className="rounded-[26px] border border-[#347161]/30 bg-[#f0f7f3] dark:bg-[#0d2621] p-6 sm:p-8 space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-xl bg-[#347161] text-white">
                <CivicIcon name="check" size={20} />
              </div>
              <div className="flex-1">
                <p className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#347161] dark:text-[#70b99e]">
                  VERIFIED CLOSEOUT AUDIT
                </p>
                <h2 className="font-serif text-xl sm:text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                  Closeout Audit
                </h2>
              </div>
              {report.resolved_at && (
                <span className="font-mono text-xs font-bold text-[#347161] dark:text-[#70b99e]">
                  {new Date(report.resolved_at).toLocaleDateString()}
                </span>
              )}
            </div>

            {/* AI Verification Verdict Banner */}
            {report.resolution_verdict && (
              <div className={`rounded-xl p-4 text-xs space-y-1.5 border ${
                report.resolution_verdict === 'fixed'
                  ? 'bg-[#e7f5ee] dark:bg-[#102b23] border-[#347161]/30 text-[#1b5042] dark:text-[#82c9b6]'
                  : report.resolution_verdict === 'partially_fixed'
                  ? 'bg-[#fff5e5] dark:bg-[#2b1f0e] border-[#ba7c29]/30 text-[#855513] dark:text-[#e2b77d]'
                  : 'bg-rose-50 dark:bg-rose-950/40 border-rose-300 dark:border-rose-900/40 text-rose-900 dark:text-rose-200'
              }`}>
                <div className="flex items-center justify-between font-bold text-xs">
                  <span className="flex items-center gap-2 uppercase tracking-wider text-[11px]">
                    <Sparkles size={14} />
                    AI RESOLUTION AUDIT VERDICT: {report.resolution_verdict.replace('_', ' ').toUpperCase()}
                  </span>
                  {!['fixed', 'partially_fixed'].includes(report.resolution_verdict) ? (
                    <span className="px-2 py-0.5 rounded-full bg-rose-200 dark:bg-rose-900 text-rose-900 dark:text-rose-100 text-[10px] uppercase font-bold tracking-wider">
                      Closure rejected
                    </span>
                  ) : report.resolution_confidence ? (
                    <span className="font-mono text-[10px]">
                      {Math.round(report.resolution_confidence * 100)}% Confidence
                    </span>
                  ) : null}
                </div>
                <p className="leading-relaxed">
                  {report.resolution_explanation}
                </p>
              </div>
            )}

            {report.resolution_notes && (
              <div className="rounded-xl border border-[#347161]/20 bg-white dark:bg-[#0b2529] p-4 text-xs sm:text-sm">
                <span className="block text-[10px] font-bold uppercase tracking-wider text-[#347161] dark:text-[#70b99e] mb-1">
                  REMEDIATION CLOSEOUT REPORT
                </span>
                <p className="text-[#324b49] dark:text-[#b8d4cf] leading-relaxed">
                  {report.resolution_notes}
                </p>
              </div>
            )}

            {/* Before vs After Photos */}
            {report.media_url && report.resolved_media_url && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="rounded-xl overflow-hidden border border-[#173e42]/15 bg-white dark:bg-[#0b2529]">
                  <span className="block px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider bg-[#f8f8f4] dark:bg-[#06181b] text-[#70817e] border-b border-[#173e42]/10">
                    PRE-REMEDIATION BASELINE (BEFORE)
                  </span>
                  <img src={report.media_url} alt="Pre-remediation baseline" className="h-44 w-full object-cover" />
                </div>
                <div className="rounded-xl overflow-hidden border border-[#347161]/30 bg-white dark:bg-[#0b2529]">
                  <span className="block px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider bg-[#e3f0ea] dark:bg-[#123830] text-[#2f7661] dark:text-[#70b99e] border-b border-[#347161]/20">
                    POST-REMEDIATION VERIFICATION (AFTER)
                  </span>
                  <img src={report.resolved_media_url} alt="Post-remediation proof" className="h-44 w-full object-cover" />
                </div>
              </div>
            )}

            {/* Citizen Resolution Feedback */}
            <div className="rounded-xl border border-[#173e42]/10 dark:border-white/10 bg-[#f8f8f4] dark:bg-[#06181b] p-4 text-xs space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <span className="font-bold uppercase tracking-wider text-[10px] text-[#ba7c29] block">
                    RESIDENT ON-SITE VERIFICATION
                  </span>
                  <p className="text-[#556b68] dark:text-[#95a9a6] mt-0.5">
                    Have you observed the completed repairs at this location?
                  </p>
                </div>

                {report.citizen_feedback ? (
                  <div className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider inline-flex items-center gap-1.5 ${
                    report.citizen_feedback === 'confirmed'
                      ? 'bg-[#e3f0ea] dark:bg-[#123830] text-[#2f7661] dark:text-[#70b99e]'
                      : 'bg-[#ffebe8] dark:bg-red-950/60 text-[#b04b37]'
                  }`}>
                    {report.citizen_feedback === 'confirmed' ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                    <span>Resident Feedback: {report.citizen_feedback}</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={submittingFeedback}
                      onClick={() => handleFeedback('confirmed')}
                      className="px-3.5 py-1.5 rounded-full bg-[#347161] hover:bg-[#2b5e50] text-white font-bold text-xs transition disabled:opacity-50"
                    >
                      Confirm Fixed
                    </button>
                    <button
                      type="button"
                      disabled={submittingFeedback}
                      onClick={() => handleFeedback('disputed')}
                      className="px-3.5 py-1.5 rounded-full border border-[#b04b37]/30 text-[#b04b37] hover:bg-[#ffebe8] font-bold text-xs transition disabled:opacity-50"
                    >
                      Dispute (Reopen)
                    </button>
                  </div>
                )}
              </div>
              {report.feedback_notes && (
                <p className="italic text-[11px] text-[#6d807e] dark:text-[#8ea5a2] border-t border-[#173e42]/10 dark:border-white/10 pt-2">
                  Resident feedback notes: “{report.feedback_notes}”
                </p>
              )}
            </div>
          </div>
        )}

        {/* Lifecycle Audit Trail */}
        {timeline.length > 0 && (
          <div className="rounded-[26px] border border-[#173e42]/12 dark:border-[#173e42]/30 bg-white dark:bg-[#0b2529] p-6 sm:p-8 space-y-4 shadow-sm">
            <div className="flex items-center gap-2">
              <CivicIcon name="clock" size={18} className="text-[#347161]" />
              <h2 className="font-serif text-xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                Incident Lifecycle & Audit Trail
              </h2>
            </div>

            <div className="relative pl-6 space-y-5 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-[#173e42]/15">
              {timeline.map((entry, idx) => (
                <div key={entry.id || idx} className="relative text-xs">
                  <div className="absolute -left-6 top-1 size-3 rounded-full bg-[#e8b855] border-2 border-[#0d3035]" />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-bold text-[#0d3035] dark:text-[#f6f4ee]">{entry.actor}</span>
                    <span className="rounded-full bg-[#f0f4f5] dark:bg-[#173035] px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-[#527174] dark:text-[#95b0b3]">
                      {entry.action_type.replace('_', ' ')}
                    </span>
                    <span className="ml-auto font-mono text-[10px] text-[#718481]">
                      {new Date(entry.created_at).toLocaleString()}
                    </span>
                  </div>
                  {entry.notes && (
                    <p className="mt-1 text-[#5b6e6b] dark:text-[#95a9a6] leading-relaxed">{entry.notes}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Municipal Operations Status Management */}
        <div className="rounded-[26px] border border-[#173e42]/12 dark:border-[#173e42]/30 bg-white dark:bg-[#0b2529] p-6 sm:p-8 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] font-bold tracking-[0.16em] uppercase text-[#ba7c29]">
                MUNICIPAL DISPATCH ACTIONS
              </p>
              <h2 className="font-serif text-xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                Update Operations Status
              </h2>
            </div>
            {!isAuthority && (
              <span className="rounded-full bg-[#f0f2f0] dark:bg-[#122527] px-3 py-1 text-[10px] font-bold text-[#687a77] dark:text-[#8ea5a2]">
                Authority Clearance Required
              </span>
            )}
          </div>

          {isAuthority ? (
            <>
              <div className="flex flex-wrap gap-2.5">
                {STATUSES.map(s => (
                  <button
                    key={s}
                    type="button"
                    disabled={updating || report.status === s}
                    onClick={() => handleStatusChange(s)}
                    className={`rounded-full px-4 py-2 text-xs font-bold uppercase tracking-wider transition disabled:opacity-50 ${
                      report.status === s
                        ? 'bg-[#0d3035] text-white shadow-sm'
                        : 'border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] text-[#556b68] dark:text-[#95a9a6] hover:bg-[#fffaf0] hover:text-[#0d3035]'
                    }`}
                  >
                    {s.replace('_', ' ')}
                  </button>
                ))}
              </div>

              {/* Resolve Form Modal / Accordion */}
              {showResolveForm && (
                <form onSubmit={handleResolveProofSubmit} className="mt-4 rounded-2xl border border-[#347161]/30 bg-[#f0f7f3] dark:bg-[#0e2924] p-5 space-y-4">
                  <div className="flex items-center gap-2">
                    <CivicIcon name="check" size={18} className="text-[#347161]" />
                    <h3 className="font-serif text-lg font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                      Closeout Resolution & Field Verification Evidence
                    </h3>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee] mb-1.5">
                      Inspecting Agent / Department *
                    </label>
                    <input
                      type="text"
                      required
                      value={resolveActor}
                      onChange={e => setResolveActor(e.target.value)}
                      className="w-full rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#06181b] px-3.5 py-2.5 text-xs text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee] mb-1.5">
                      Technical Resolution Summary *
                    </label>
                    <textarea
                      required
                      rows={3}
                      value={resolveNotes}
                      onChange={e => setResolveNotes(e.target.value)}
                      placeholder="Detail corrective actions executed (e.g. Asphalting completed, pipeline sealed, drainage cleared)..."
                      className="w-full rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#06181b] p-3 text-xs text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29] resize-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee] mb-1.5">
                      Post-Remediation Completion Photo
                    </label>
                    <CameraCapture
                      onCapture={(f, previewUrl) => {
                        setResolveProofFile(f)
                        setResolveProofPreview(previewUrl)
                      }}
                      onClear={() => {
                        setResolveProofFile(null)
                        setResolveProofPreview(null)
                      }}
                      currentPreview={resolveProofPreview}
                      label="Repair Completion Photo"
                    />
                  </div>

                  <div className="flex gap-3 pt-2">
                    <button
                      type="submit"
                      disabled={resolving || !resolveNotes.trim()}
                      className="flex-1 rounded-full bg-[#0d3035] py-3 text-xs font-bold uppercase tracking-wider text-white hover:bg-[#16444a] transition"
                    >
                      {resolving ? 'Publishing Closeout Audit...' : 'Confirm Resolution & Publish Closeout'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowResolveForm(false)}
                      className="rounded-full border border-[#173e42]/15 px-5 py-3 text-xs font-bold text-[#718481] hover:bg-white"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              )}
            </>
          ) : (
            <p className="text-xs text-[#718481] dark:text-[#8ea5a2] py-2">
              Operational status updates and closeout verifications are restricted to authorized municipal representatives.
            </p>
          )}
        </div>

        {/* Geospatial Map */}
        {report.latitude && report.longitude && (
          <div className="rounded-[26px] border border-[#173e42]/12 dark:border-[#173e42]/30 bg-white dark:bg-[#0b2529] p-6 sm:p-8 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CivicIcon name="location" size={18} className="text-[#347161]" />
                <h2 className="font-serif text-xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                  Geospatial GIS Inspection
                </h2>
              </div>
              <a
                href={`https://www.google.com/maps?q=${report.latitude},${report.longitude}`}
                target="_blank"
                rel="noreferrer"
                className="text-xs font-bold text-[#ba7c29] hover:underline inline-flex items-center gap-1"
              >
                Open External Map ↗
              </a>
            </div>
            <div className="overflow-hidden rounded-2xl border border-[#173e42]/15">
              <CivicMap reports={[report]} height="240px" zoom={15} />
            </div>
            <p className="text-xs text-[#6e807e] dark:text-[#8ea5a2] font-medium">
              Physical Reference: {report.location}
            </p>
          </div>
        )}

        

      </div>
    </div>
  )
}
