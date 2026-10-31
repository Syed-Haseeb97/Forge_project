import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import axios from 'axios'
import toast from 'react-hot-toast'
import { Star, ThumbsUp, Send } from 'lucide-react'
import CivicIcon from '../components/CivicIcon'
import { isWatched, toggleWatchlist } from '../components/constants'
import CivicMap from '../components/CivicMap'
import CameraCapture from '../components/CameraCapture'

const STATUSES = ['open', 'in_progress', 'resolved', 'closed']

export default function ReportDetail() {
  const { id } = useParams()
  const [report, setReport] = useState(null)
  const [timeline, setTimeline] = useState([])
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [comments, setComments] = useState([])
  const [commentForm, setCommentForm] = useState({ author: '', role: 'citizen', content: '' })
  const [submittingComment, setSubmittingComment] = useState(false)
  const [watched, setWatched] = useState(false)

  // Resolve modal/form state
  const [showResolveForm, setShowResolveForm] = useState(false)
  const [resolveNotes, setResolveNotes] = useState('')
  const [resolveActor, setResolveActor] = useState('Municipal Works Inspector')
  const [resolveProofFile, setResolveProofFile] = useState(null)
  const [resolveProofPreview, setResolveProofPreview] = useState(null)
  const [resolving, setResolving] = useState(false)

  const loadData = async () => {
    try {
      const [rRes, tRes, cRes] = await Promise.all([
        axios.get(`/api/reports/${id}`),
        axios.get(`/api/reports/${id}/timeline`).catch(() => ({ data: [] })),
        axios.get(`/api/reports/${id}/comments`).catch(() => ({ data: [] })),
      ])
      setReport(rRes.data)
      setTimeline(tRes.data)
      setComments(cRes.data)
      setWatched(isWatched(rRes.data.id))
    } catch {
      toast.error('Failed to load incident record')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [id])

  const handleUpvote = async () => {
    try {
      const { data } = await axios.post(`/api/reports/${id}/upvote`)
      setReport(r => ({ ...r, upvotes: data.upvotes }))
      toast.success('Recorded municipal endorsement')
    } catch {
      toast.error('Failed to record endorsement')
    }
  }

  const handleToggleWatch = () => {
    const updated = toggleWatchlist(report.id)
    const isNow = updated.includes(report.id)
    setWatched(isNow)
    toast.success(isNow ? 'Added to Monitored Registry' : 'Removed from Monitored Registry')
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
      fd.append('actor', resolveActor)
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

  const handleCommentSubmit = async (e) => {
    e.preventDefault()
    if (!commentForm.content.trim()) return
    setSubmittingComment(true)
    try {
      const { data } = await axios.post(`/api/reports/${id}/comments`, {
        author: commentForm.author || 'Anonymous Citizen',
        role: commentForm.role,
        content: commentForm.content,
      })
      setComments(prev => [...prev, data])
      setCommentForm(f => ({ ...f, content: '', author: '' }))
      toast.success('Municipal comment appended')

      if (commentForm.role === 'authority') {
        const tRes = await axios.get(`/api/reports/${id}/timeline`)
        setTimeline(tRes.data)
      }
    } catch {
      toast.error('Failed to append comment')
    } finally {
      setSubmittingComment(false)
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
  const referenceCode = `CL-2026-${String(report.id).padStart(5, '0')}`

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
          {/* Statutory Critical Alert Strip */}
          {isCritical && (
            <div className="bg-[#b04b37] text-white text-[10px] sm:text-[11px] font-bold tracking-[0.14em] uppercase px-5 py-2 flex items-center justify-between -mx-6 sm:-mx-9 -mt-6 sm:-mt-9 mb-6 shadow-sm">
              <span className="flex items-center gap-2">
                <span className="relative flex size-2">
                  <span className="animate-ping absolute inline-flex size-full rounded-full bg-white opacity-85" />
                  <span className="relative inline-flex size-2 rounded-full bg-white" />
                </span>
                CRITICAL INFRASTRUCTURE HAZARD · STATUTORY PRIORITY 1
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
            <div className="flex items-center gap-2 shrink-0">
              {isCritical ? (
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
          {report.media_url && report.media_url.match(/\.(mp3|wav|ogg|m4a)$/i) && (
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
              <span className="block text-[10px] font-bold uppercase tracking-wider text-[#8a9b98]">STATUTORY SLA</span>
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

        {/* Verified Resolution Proof (Pre vs Post Remediation Comparison) */}
        {(report.resolved_media_url || report.resolution_notes) && (
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
                  Official Engineering Remediation Proof
                </h2>
              </div>
              {report.resolved_at && (
                <span className="font-mono text-xs font-bold text-[#347161] dark:text-[#70b99e]">
                  {new Date(report.resolved_at).toLocaleDateString()}
                </span>
              )}
            </div>

            {report.resolution_notes && (
              <div className="rounded-xl border border-[#347161]/20 bg-white dark:bg-[#0b2529] p-4 text-xs sm:text-sm">
                <span className="block text-[10px] font-bold uppercase tracking-wider text-[#347161] dark:text-[#70b99e] mb-1">
                  OFFICIAL CLOSEOUT REPORT
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
                    PRE-REMEDIATION EVIDENCE
                  </span>
                  <img src={report.media_url} alt="Pre-remediation" className="h-44 w-full object-cover" />
                </div>
                <div className="rounded-xl overflow-hidden border border-[#347161]/30 bg-white dark:bg-[#0b2529]">
                  <span className="block px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider bg-[#e3f0ea] dark:bg-[#123830] text-[#2f7661] dark:text-[#70b99e] border-b border-[#347161]/20">
                    POST-REMEDIATION VERIFICATION
                  </span>
                  <img src={report.resolved_media_url} alt="Post-remediation" className="h-44 w-full object-cover" />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Lifecycle Audit Trail */}
        {timeline.length > 0 && (
          <div className="rounded-[26px] border border-[#173e42]/12 dark:border-[#173e42]/30 bg-white dark:bg-[#0b2529] p-6 sm:p-8 space-y-4 shadow-sm">
            <div className="flex items-center gap-2">
              <CivicIcon name="clock" size={18} className="text-[#347161]" />
              <h2 className="font-serif text-xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
                Statutory Lifecycle & Audit Trail
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
          </div>

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

        {/* Public Inquiry & Municipal Discourse */}
        <div className="rounded-[26px] border border-[#173e42]/12 dark:border-[#173e42]/30 bg-white dark:bg-[#0b2529] p-6 sm:p-8 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-serif text-xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
              Public Inquiry & Official Discourse
            </h2>
            <span className="font-mono text-xs text-[#718481]">
              {comments.length} {comments.length === 1 ? 'record' : 'records'}
            </span>
          </div>

          <div className="space-y-3">
            {comments.length === 0 ? (
              <p className="text-xs text-[#8a9996] text-center py-6">
                No citizen inquiries or authority updates appended yet.
              </p>
            ) : (
              comments.map(c => (
                <div key={c.id} className="rounded-xl border border-[#173e42]/10 dark:border-[#173e42]/20 bg-[#f8f8f4] dark:bg-[#06181b] p-4 text-xs">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-bold text-[#0d3035] dark:text-[#f6f4ee]">{c.author}</span>
                    <span className="font-mono text-[10px] text-[#8a9996]">
                      {new Date(c.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-[#4e6361] dark:text-[#95a9a6] leading-relaxed">{c.content}</p>
                </div>
              ))
            )}
          </div>

          {/* Comment Form */}
          <form onSubmit={handleCommentSubmit} className="pt-3 border-t border-[#173e42]/10 dark:border-[#173e42]/30 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                type="text"
                placeholder="Your Name (or Department)"
                value={commentForm.author}
                onChange={e => setCommentForm(f => ({ ...f, author: e.target.value }))}
                className="rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] px-3.5 py-2.5 text-xs text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
              />
              <select
                value={commentForm.role}
                onChange={e => setCommentForm(f => ({ ...f, role: e.target.value }))}
                className="rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] px-3.5 py-2.5 text-xs font-semibold text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
              >
                <option value="citizen">Citizen Stakeholder</option>
                <option value="authority">Municipal Authority Representative</option>
              </select>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Append formal inquiry or status note..."
                value={commentForm.content}
                onChange={e => setCommentForm(f => ({ ...f, content: e.target.value }))}
                className="flex-1 rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] px-3.5 py-2.5 text-xs text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
              />
              <button
                type="submit"
                disabled={submittingComment || !commentForm.content.trim()}
                className="flex items-center justify-center rounded-xl bg-[#0d3035] px-4 text-white hover:bg-[#16444a] transition disabled:opacity-50"
              >
                <Send size={14} />
              </button>
            </div>
          </form>
        </div>

      </div>
    </div>
  )
}
