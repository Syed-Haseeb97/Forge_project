import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import axios from 'axios'
import toast from 'react-hot-toast'
import {
  Clock,
  CheckCircle2,
  AlertTriangle,
  Copy,
  Check,
  Shield,
  Send,
  Building2,
  Calendar,
  MapPin,
  ExternalLink,
  RotateCw,
} from 'lucide-react'
import CivicIcon from '../components/CivicIcon'
import { CATEGORY_LABELS } from '../components/constants'

export default function PublicTrack() {
  const { token } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [copiedToken, setCopiedToken] = useState(false)
  const [copiedLink, setCopiedLink] = useState(false)

  const loadTicket = async () => {
    setLoading(true)
    try {
      const res = await axios.get(`/api/track/${encodeURIComponent(token.trim())}`)
      setData(res.data)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Ticket not found or invalid tracking token')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (token) loadTicket()
  }, [token])

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(text)
    if (type === 'token') {
      setCopiedToken(true)
      setTimeout(() => setCopiedToken(false), 2000)
    } else {
      setCopiedLink(true)
      setTimeout(() => setCopiedLink(false), 2000)
    }
    toast.success(`Copied ${type === 'token' ? 'tracking token' : 'tracking link'} to clipboard`)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#f6f4ee] dark:bg-[#06181b] flex flex-col items-center justify-center p-6 text-center">
        <div className="ai-orbit relative flex size-16 items-center justify-center rounded-full bg-[#0d3035] text-[#e8b855] shadow-lg">
          <CivicIcon name="brain" size={28} />
          <span className="absolute -right-1 top-0 size-2.5 rounded-full bg-[#e8b855]" />
        </div>
        <p className="mt-5 font-serif text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
          Accessing Citizen Tracking Ledger
        </p>
        <p className="mt-1 text-xs text-[#6e807e] dark:text-[#8ea5a2]">
          Verifying token #{token} against municipal redressal records...
        </p>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-[#f6f4ee] dark:bg-[#06181b] flex items-center justify-center p-6 text-center">
        <div className="max-w-md w-full rounded-[26px] border border-[#173e42]/15 bg-white dark:bg-[#0b2529] p-8 sm:p-12 shadow-lg space-y-4">
          <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300">
            <AlertTriangle size={28} />
          </div>
          <h2 className="font-serif text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
            Tracking Reference Not Found
          </h2>
          <p className="text-xs text-[#556966] dark:text-[#95a9a6] leading-relaxed">
            No grievance was found matching token <strong className="font-mono">{token}</strong>. Please ensure the token matches the code provided in your submission confirmation.
          </p>
          <div className="pt-4 flex flex-col gap-2">
            <Link
              to="/"
              className="btn-primary w-full justify-center text-xs"
            >
              Back to Public Dashboard
            </Link>
          </div>
        </div>
      </div>
    )
  }

  const isResolved = data.status === 'resolved' || data.status === 'closed'
  const isCritical = data.severity === 'critical'
  const categoryLabel = CATEGORY_LABELS[data.category] || data.category.replace('_', ' ')

  return (
    <div className="min-h-screen bg-[#f6f4ee] dark:bg-[#06181b] text-[#102a2f] dark:text-[#f6f4ee] py-8 sm:py-12 transition-colors">
      <div className="mx-auto max-w-[860px] px-4 sm:px-6 space-y-6">

        {/* Top Breadcrumb & Share Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee] hover:text-[#ba7c29] transition"
          >
            <CivicIcon name="arrow" size={14} className="rotate-180" />
            <span>Return to Public Dashboard</span>
          </Link>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => handleCopy(window.location.href, 'link')}
              className="inline-flex items-center gap-1.5 rounded-full border border-[#173e42]/15 bg-white dark:bg-[#0b2529] px-3.5 py-1.5 text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee] hover:bg-[#fffaf0] dark:hover:bg-[#123035] transition"
            >
              {copiedLink ? <Check size={13} className="text-[#347161]" /> : <ExternalLink size={13} />}
              <span>{copiedLink ? 'Link Copied' : 'Share Tracking Link'}</span>
            </button>
            <button
              type="button"
              onClick={loadTicket}
              className="inline-flex items-center gap-1.5 rounded-full border border-[#173e42]/15 bg-white dark:bg-[#0b2529] px-3 py-1.5 text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee] hover:bg-[#fffaf0] transition"
              title="Refresh status"
            >
              <RotateCw size={13} />
            </button>
          </div>
        </div>

        {/* Overdue / Escalation Alert Banner */}
        {data.is_overdue && (
          <div className="rounded-2xl bg-[#b04b37] text-white p-4 flex items-center justify-between shadow-md animate-pulse text-xs font-bold">
            <div className="flex items-center gap-2.5">
              <AlertTriangle size={18} className="shrink-0" />
              <span>SLA DEADLINE BREACHED · ESCALATED TO SENIOR CIVIC OVERSIGHT</span>
            </div>
            <span className="font-mono bg-black/30 px-2.5 py-0.5 rounded-full text-[10px]">
              LEVEL {data.escalation_level}
            </span>
          </div>
        )}

        {/* Main Status & Token Dossier Card */}
        <div className="rounded-[26px] border border-[#173e42]/15 dark:border-white/10 bg-white dark:bg-[#0b2529] p-6 sm:p-9 shadow-[0_20px_50px_rgba(27,52,51,.08)] space-y-6">

          {/* Header Row */}
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-black/10 dark:border-white/10 pb-6">
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="font-mono text-xs font-bold text-[#ba7c29] bg-[#fffaf0] dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/40 px-2.5 py-0.5 rounded-lg">
                  #{data.docket_no}
                </span>
                <span className="text-black/30 dark:text-white/30">•</span>
                <span className="text-xs font-semibold text-[#556966] dark:text-[#95a9a6] capitalize">
                  {categoryLabel}
                </span>
              </div>
              <h1 className="font-serif text-2xl sm:text-3xl font-bold leading-tight text-[#0d3035] dark:text-[#f6f4ee]">
                {data.title}
              </h1>
              <p className="mt-2 text-xs sm:text-sm text-[#5f716e] dark:text-[#95a9a6] flex items-center gap-1.5">
                <MapPin size={14} className="text-[#347161] shrink-0" />
                <span>{data.locality}</span>
              </p>
            </div>

            {/* Badges */}
            <div className="flex flex-wrap items-center gap-2 shrink-0">
              <span className={`px-3 py-1 rounded-full text-xs font-extrabold uppercase ${
                isCritical
                  ? 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200 border border-rose-300'
                  : 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200'
              }`}>
                {data.severity}
              </span>
              <span className={`px-3 py-1 rounded-full text-xs font-extrabold uppercase ${
                isResolved
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200 border border-emerald-300'
                  : 'bg-[#0d3035] text-[#e8b855] dark:bg-[#e8b855] dark:text-[#0d3035]'
              }`}>
                {data.status.replace('_', ' ')}
              </span>
            </div>
          </div>

          {/* Citizen Private Tracking Token Card */}
          <div className="rounded-2xl border border-[#ba7c29]/30 bg-[#fffaf0] dark:bg-amber-950/20 p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <span className="text-[10px] font-bold tracking-[0.14em] uppercase text-[#ba7c29]">
                PRIVATE CITIZEN TRACKING TOKEN
              </span>
              <div className="mt-1 font-mono text-xl sm:text-2xl font-extrabold text-[#0d3035] dark:text-[#e8b855] tracking-wider">
                {data.tracking_token}
              </div>
              <p className="mt-1 text-[11px] text-[#70807d] dark:text-[#95a9a6]">
                Save this token to check real-time progress anytime without exposing personal information.
              </p>
            </div>
            <button
              type="button"
              onClick={() => handleCopy(data.tracking_token, 'token')}
              className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-[#0d3035] hover:bg-[#16444a] text-[#e8b855] px-4 py-2.5 text-xs font-bold transition shadow-xs shrink-0 self-start sm:self-auto"
            >
              {copiedToken ? <Check size={14} /> : <Copy size={14} />}
              <span>{copiedToken ? 'Copied Token' : 'Copy Token'}</span>
            </button>
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <h3 className="text-[11px] font-bold uppercase tracking-wider text-[#70817e] dark:text-[#8ea5a2]">
              Citizen Incident Description
            </h3>
            <p className="text-sm sm:text-base leading-relaxed text-[#2f4345] dark:text-[#cad8d5]">
              {data.description}
            </p>
          </div>

          {/* SLA & Dispatch Snapshot Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-black/10 dark:border-white/10">
            {/* SLA Countdown Card */}
            <div className="rounded-xl border border-black/10 dark:border-white/10 bg-[#f8f8f4] dark:bg-[#06181b] p-4 space-y-1">
              <div className="flex items-center justify-between text-[11px] font-bold uppercase text-[#70817e]">
                <span className="flex items-center gap-1.5">
                  <Clock size={13} className="text-[#ba7c29]" /> Target SLA Window
                </span>
                <span className="font-mono">{data.sla_hours}h SLA</span>
              </div>
              <p className="font-serif text-xl sm:text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                {data.sla_countdown}
              </p>
              <p className="text-[10px] text-[#8a9996]">
                Deadline: {new Date(data.sla_deadline).toLocaleString()}
              </p>
            </div>

            {/* Departmental Dispatch Snapshot */}
            <div className="rounded-xl border border-black/10 dark:border-white/10 bg-[#f8f8f4] dark:bg-[#06181b] p-4 space-y-1">
              <div className="flex items-center justify-between text-[11px] font-bold uppercase text-[#70817e]">
                <span className="flex items-center gap-1.5">
                  <Building2 size={13} className="text-[#347161]" /> Municipal Dispatch
                </span>
                <span className={`px-2 py-0.2 rounded text-[9px] font-bold ${
                  data.dispatch_info?.provider_accepted ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'
                }`}>
                  {data.dispatch_info?.provider_accepted ? 'SENT' : 'PENDING'}
                </span>
              </div>
              <p className="font-semibold text-sm sm:text-base text-[#0d3035] dark:text-[#f6f4ee] truncate">
                {data.dispatch_info?.designation || 'Municipal Engineering Division'}
              </p>
              <p className="text-[10px] text-[#8a9996] truncate">
                {data.dispatch_info?.time_sent
                  ? `Notice sent: ${new Date(data.dispatch_info.time_sent).toLocaleString()}`
                  : 'Preparing formal work order...'}
              </p>
            </div>
          </div>

          {/* Evidence Media Preview */}
          {data.media_url && (
            <div className="rounded-xl border border-black/10 dark:border-white/10 overflow-hidden">
              <span className="block bg-[#f8f8f4] dark:bg-[#06181b] px-4 py-2 text-[10px] font-bold uppercase tracking-wider text-[#70817e]">
                Citizen Attached Evidence
              </span>
              {data.media_url.match(/\.(jpg|jpeg|png|webp|gif)$/i) ? (
                <img
                  src={data.media_url}
                  alt={data.title}
                  className="w-full max-h-72 object-cover"
                />
              ) : (
                <div className="p-4 bg-white dark:bg-[#0b2529]">
                  <audio controls src={data.media_url} className="w-full" />
                </div>
              )}
            </div>
          )}

          {/* Verified Remediation Proof if Resolved */}
          {data.resolved_media_url && (
            <div className="rounded-xl border border-emerald-300 dark:border-emerald-800/40 overflow-hidden bg-emerald-50 dark:bg-emerald-950/20 p-4 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-emerald-900 dark:text-emerald-300">
                <CheckCircle2 size={16} />
                <span>Verified Field Remediation Evidence</span>
              </div>
              <img
                src={data.resolved_media_url}
                alt="Remediation Closeout Proof"
                className="w-full max-h-72 object-cover rounded-lg"
              />
            </div>
          )}
        </div>

        {/* Public Audit Timeline */}
        <div className="rounded-[26px] border border-[#173e42]/15 dark:border-white/10 bg-white dark:bg-[#0b2529] p-6 sm:p-9 shadow-sm space-y-5">
          <div className="flex items-center justify-between border-b border-black/10 dark:border-white/10 pb-4">
            <h2 className="font-serif text-xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
              Official Action Timeline
            </h2>
            <span className="text-[10px] font-mono text-[#718481] dark:text-[#8ea5a2]">
              {data.timeline?.length || 0} Audit Events
            </span>
          </div>

          <div className="space-y-4">
            {data.timeline && data.timeline.length > 0 ? (
              data.timeline.map((entry, idx) => (
                <div key={idx} className="flex items-start gap-3 text-xs">
                  <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-[#0d3035] text-[#e8b855] text-[10px] font-bold font-mono mt-0.5">
                    {idx + 1}
                  </div>
                  <div className="flex-1 rounded-xl border border-black/10 dark:border-white/10 bg-[#f8f8f4] dark:bg-[#06181b] p-3.5 space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                        {entry.actor}
                      </span>
                      <span className="text-[10px] text-[#718481] dark:text-[#8ea5a2]">
                        {entry.created_at ? new Date(entry.created_at).toLocaleString() : ''}
                      </span>
                    </div>
                    <p className="text-[#3b4e4c] dark:text-[#cad8d5] leading-relaxed">
                      {entry.notes}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-xs text-[#718481] py-4 text-center">No timeline updates recorded yet.</p>
            )}
          </div>
        </div>

        {/* Privacy Assurance Strip */}
        <div className="rounded-xl border border-[#347161]/20 bg-[#edf5ef] dark:bg-[#123830] p-4 text-xs text-[#2f7661] dark:text-[#70b99e] flex items-center gap-3">
          <Shield size={20} className="shrink-0" />
          <p>
            <strong>Zero-PII Public Ledger:</strong> For resident privacy, citizen identity, email, and phone numbers are strictly protected and never displayed on public tracking records.
          </p>
        </div>

      </div>
    </div>
  )
}
