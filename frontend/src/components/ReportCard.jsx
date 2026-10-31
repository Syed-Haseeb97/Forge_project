import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Star, ThumbsUp } from 'lucide-react'
import CivicIcon from './CivicIcon'
import { isWatched, toggleWatchlist } from './constants'
import axios from 'axios'
import toast from 'react-hot-toast'

export default function ReportCard({ report, onUpvote, onWatchlistChange }) {
  const [watched, setWatched] = useState(() => isWatched(report.id))
  const isCritical = report.severity === 'critical'
  const isHigh = report.severity === 'high'

  const handleUpvote = async (e) => {
    e.preventDefault()
    e.stopPropagation()
    try {
      const { data } = await axios.post(`/api/reports/${report.id}/upvote`)
      onUpvote?.(report.id, data.upvotes)
      toast.success('Recorded municipal endorsement')
    } catch {
      toast.error('Failed to register endorsement')
    }
  }

  const handleToggleWatch = (e) => {
    e.preventDefault()
    e.stopPropagation()
    const updated = toggleWatchlist(report.id)
    const isNowWatched = updated.includes(report.id)
    setWatched(isNowWatched)
    onWatchlistChange?.(report.id, isNowWatched)
    toast.success(isNowWatched ? 'Added to Monitored Registry' : 'Removed from Monitored Registry')
  }

  // Format reference number
  const referenceCode = `CL-2026-${String(report.id).padStart(5, '0')}`

  return (
    <Link to={`/reports/${report.id}`} className="block h-full group focus:outline-none">
      <article
        className={`h-full flex flex-col justify-between rounded-[22px] p-5 sm:p-6 transition-all duration-200 border ${
          isCritical
            ? 'bg-[#fffcfb] dark:bg-[#181112] border-2 border-[#b04b37] dark:border-[#e05d43] shadow-[0_12px_36px_rgba(176,75,55,.16)] hover:shadow-[0_18px_45px_rgba(176,75,55,.24)] hover:-translate-y-0.5'
            : 'bg-white dark:bg-[#0b2529] border-[#173e42]/12 dark:border-[#173e42]/30 shadow-[0_12px_35px_rgba(27,52,51,.05)] hover:shadow-[0_18px_45px_rgba(27,52,51,.12)] hover:-translate-y-0.5'
        }`}
      >
        <div>
          {/* Statutory Critical Hazard Top Strip */}
          {isCritical && (
            <div className="bg-[#b04b37] text-white text-[10px] sm:text-[11px] font-bold tracking-[0.14em] uppercase px-4 py-1.5 flex items-center justify-between -mx-5 sm:-mx-6 -mt-5 sm:-mt-6 mb-4 rounded-t-[20px] shadow-sm">
              <span className="flex items-center gap-2">
                <span className="relative flex size-2">
                  <span className="animate-ping absolute inline-flex size-full rounded-full bg-white opacity-85" />
                  <span className="relative inline-flex size-2 rounded-full bg-white" />
                </span>
                CRITICAL HAZARD · STATUTORY PRIORITY 1
              </span>
              <span className="bg-black/25 text-white font-mono text-[9px] px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                {report.sla_hours ? `${report.sla_hours}H SLA` : 'IMMEDIATE SLA'}
              </span>
            </div>
          )}

          {/* Top Metadata Row: Route badge + Priority / Status Badges */}
          <div className="flex items-start justify-between gap-2.5 mb-3">
            <div className="flex flex-wrap items-center gap-2 min-w-0">
              <span className="inline-flex items-center gap-1.5 text-[9px] sm:text-[10px] font-bold tracking-[0.12em] uppercase text-[#347161] dark:text-[#70b99e] bg-[#e3f0ea] dark:bg-[#123830] px-2.5 py-1 rounded-full">
                <CivicIcon name="route" size={12} />
                <span className="truncate max-w-[130px] sm:max-w-[170px]">
                  {report.routed_to ? `ROUTED TO ${report.routed_to.toUpperCase()}` : 'ROUTED TO PUBLIC WORKS'}
                </span>
              </span>

              <span className="text-[10px] font-mono text-[#8a9b98] dark:text-[#6f8582]">
                {referenceCode}
              </span>
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              {/* Priority Badge */}
              {isCritical ? (
                <span className="inline-flex items-center gap-1 text-[9px] sm:text-[10px] font-extrabold uppercase px-2.5 py-0.5 rounded-full bg-[#fce8e6] text-[#b04b37] border border-[#b04b37]/30">
                  <CivicIcon name="alert" size={11} /> CRITICAL
                </span>
              ) : isHigh ? (
                <span className="inline-flex items-center gap-1 text-[9px] sm:text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-[#fff4dd] text-[#956018] border border-[#bd7f23]/30 dark:bg-[#2b210f] dark:text-[#e8b855]">
                  <CivicIcon name="alert" size={11} /> HIGH
                </span>
              ) : (
                <span className="inline-flex items-center text-[9px] sm:text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-[#f0f4f3] dark:bg-[#163035] text-[#556e6b] dark:text-[#8ea7a4]">
                  {report.severity}
                </span>
              )}

              {/* Status Badge */}
              {report.status === 'resolved' ? (
                <span className="inline-flex items-center gap-1 text-[9px] sm:text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-[#e3f0ea] text-[#2f7661] border border-[#347161]/20 dark:bg-[#123830] dark:text-[#70b99e]">
                  <CivicIcon name="check" size={11} /> RESOLVED
                </span>
              ) : report.status === 'in_progress' ? (
                <span className="inline-flex items-center gap-1 text-[9px] sm:text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-[#fff4dd] text-[#94611b] border border-[#e8b855]/30 dark:bg-[#2e230e] dark:text-[#e8b855]">
                  <CivicIcon name="clock" size={11} /> IN PROGRESS
                </span>
              ) : (
                <span className="inline-flex items-center text-[9px] sm:text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-[#f0f4f5] dark:bg-[#173035] text-[#527174] dark:text-[#95b0b3]">
                  OPEN
                </span>
              )}
            </div>
          </div>

          {/* Title in Caslon Serif */}
          <h3
            className={`font-serif text-lg sm:text-[20px] font-bold leading-snug tracking-tight transition-colors ${
              isCritical
                ? 'text-[#681c10] dark:text-[#ff9885] group-hover:text-[#b04b37]'
                : 'text-[#0d3035] dark:text-[#f6f4ee] group-hover:text-[#ba7c29] dark:group-hover:text-[#e8b855]'
            }`}
          >
            {report.title}
          </h3>

          {/* Description */}
          <p
            className={`mt-2 text-xs sm:text-sm line-clamp-2 leading-relaxed ${
              isCritical
                ? 'text-[#6e3830] dark:text-[#e8b8b0]'
                : 'text-[#5f716e] dark:text-[#95a9a6]'
            }`}
          >
            {report.description}
          </p>

          {/* Evidence photo preview if present */}
          {report.media_url && report.media_url.match(/\.(jpg|jpeg|png|webp|gif)$/i) && (
            <div className="relative mt-3.5 overflow-hidden rounded-xl border border-[#173e42]/10 dark:border-white/10 aspect-video bg-[#0d3035]/5">
              <img
                src={report.media_url}
                alt={report.title}
                loading="lazy"
                className="size-full object-cover group-hover:scale-[1.02] transition duration-300"
              />
              <span className="absolute bottom-2 left-2 rounded-full bg-black/60 backdrop-blur-sm px-2.5 py-1 text-[9px] font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <CivicIcon name="camera" size={11} /> CITIZEN EVIDENCE
              </span>
            </div>
          )}
        </div>

        {/* Footer Meta Row */}
        <div className="mt-4 pt-3.5 border-t border-[#173e42]/10 dark:border-[#173e42]/30 flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-1.5 min-w-0 text-[#607572] dark:text-[#8da5a1]">
            <CivicIcon name="location" size={14} className="shrink-0 text-[#3d776b]" />
            <span className="truncate text-[11px] sm:text-xs font-medium">
              {report.location}
            </span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {report.sla_hours && (
              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-[#687a77] dark:text-[#95a9a6] bg-[#f6f4ee] dark:bg-[#06181b] px-2.5 py-1 rounded-full border border-[#173e42]/10">
                <CivicIcon name="clock" size={11} />
                {report.sla_hours}h SLA
              </span>
            )}

            {/* Watchlist toggle */}
            <button
              onClick={handleToggleWatch}
              type="button"
              title={watched ? 'Remove from Monitored Registry' : 'Add to Monitored Registry'}
              className={`p-1.5 rounded-full transition ${
                watched
                  ? 'text-[#ba7c29] bg-[#fffaf0] dark:bg-[#34260f]'
                  : 'text-[#8a9996] hover:text-[#ba7c29] hover:bg-[#f6f4ee] dark:hover:bg-[#123035]'
              }`}
            >
              <Star size={14} fill={watched ? 'currentColor' : 'none'} />
            </button>

            {/* Endorsement count */}
            <button
              onClick={handleUpvote}
              type="button"
              title="Endorse priority for this issue"
              className="flex items-center gap-1 text-[11px] font-bold text-[#0d3035] dark:text-[#f6f4ee] bg-[#f6f4ee] dark:bg-[#163035] hover:bg-[#e8b855] dark:hover:bg-[#e8b855] dark:hover:text-[#0d3035] px-2.5 py-1 rounded-full transition"
            >
              <ThumbsUp size={11} />
              <span>{report.upvotes || 0}</span>
            </button>
          </div>
        </div>
      </article>
    </Link>
  )
}
