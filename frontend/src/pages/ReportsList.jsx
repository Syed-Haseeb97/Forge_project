import { useEffect, useState } from 'react'
import axios from 'axios'
import { Download, Star, SlidersHorizontal, RotateCcw } from 'lucide-react'
import ReportCard from '../components/ReportCard'
import CivicMap from '../components/CivicMap'
import CivicIcon from '../components/CivicIcon'
import { CATEGORIES, getWatchlist } from '../components/constants'
import toast from 'react-hot-toast'

const STATUSES = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'closed', label: 'Closed' },
]

const SEVERITIES = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
]

export default function ReportsList() {
  const [reports, setReports] = useState([])
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ status: '', severity: '', category: '', search: '' })
  const [viewMode, setViewMode] = useState('grid') // 'grid' | 'map'
  const [onlyWatched, setOnlyWatched] = useState(false)
  const [watchlist, setWatchlist] = useState(() => getWatchlist())
  const [exportOpen, setExportOpen] = useState(false)
  const [showMobileFilters, setShowMobileFilters] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const params = {}
      if (filters.status) params.status = filters.status
      if (filters.severity) params.severity = filters.severity
      if (filters.category) params.category = filters.category
      if (filters.search) params.search = filters.search
      const [reportsRes, insightsRes] = await Promise.all([
        axios.get('/api/reports', { params }),
        axios.get('/api/insights').catch(() => ({ data: null })),
      ])
      setReports(reportsRes.data)
      if (insightsRes?.data) setInsights(insightsRes.data)
    } catch {
      toast.error('Failed to query municipal registry')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [filters.status, filters.severity, filters.category])

  const handleSearch = (e) => {
    e.preventDefault()
    load()
  }

  const set = (k) => (e) => setFilters(f => ({ ...f, [k]: e.target.value }))

  const handleUpvote = (id, upvotes) => {
    setReports(prev => prev.map(r => r.id === id ? { ...r, upvotes } : r))
  }

  const handleWatchlistChange = () => {
    setWatchlist(getWatchlist())
  }

  const handleExport = (format) => {
    const params = new URLSearchParams()
    params.set('format', format)
    if (filters.status) params.set('status', filters.status)
    if (filters.severity) params.set('severity', filters.severity)
    if (filters.category) params.set('category', filters.category)
    window.open(`/api/reports/export?${params.toString()}`, '_blank')
    setExportOpen(false)
    toast.success(`Exporting ${format.toUpperCase()} record archive...`)
  }

  const displayedReports = onlyWatched
    ? reports.filter(r => watchlist.includes(r.id))
    : reports

  const hasActiveFilters = Boolean(filters.status || filters.severity || filters.category || filters.search || onlyWatched)

  return (
    <div className="min-h-screen bg-[#f6f4ee] dark:bg-[#06181b] text-[#102a2f] dark:text-[#f6f4ee] transition-colors py-8 sm:py-12">
      <div className="mx-auto max-w-[1240px] px-5 lg:px-8 space-y-7">

        {/* Header Strip & Title */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-[#173e42]/10 dark:border-[#173e42]/30 pb-7">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-[#2e7165]/25 bg-[#edf5ef] dark:bg-[#0d3035] px-3.5 py-1.5 text-[10px] font-bold tracking-[.14em] text-[#347061] dark:text-[#70b99e]">
              <span className="size-2 animate-pulse rounded-full bg-[#3b8b72]" />
              LIVE MUNICIPAL INCIDENT REGISTRY
            </div>

            <h1 className="mt-4 font-serif text-3xl sm:text-5xl font-bold tracking-tight text-[#0d3035] dark:text-[#f6f4ee]">
              Civic Reports & Infrastructure GIS
            </h1>

            <p className="mt-2 text-xs sm:text-sm text-[#5f716e] dark:text-[#95a9a6] max-w-2xl leading-relaxed">
              Public registry of reported hazards. Every complaint is evaluated by AI, routed to responsible municipal departments, and maintained openly for accountability.
            </p>
          </div>

          {/* Action Tools */}
          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            {/* Watchlist Filter Button */}
            <button
              type="button"
              onClick={() => setOnlyWatched(!onlyWatched)}
              className={`flex items-center gap-1.5 rounded-full px-4 py-2.5 text-xs font-bold transition border ${
                onlyWatched
                  ? 'bg-[#ba7c29] text-white border-[#ba7c29] shadow-sm'
                  : 'bg-white dark:bg-[#0b2529] text-[#0d3035] dark:text-[#f6f4ee] border-[#173e42]/15 hover:border-[#ba7c29]'
              }`}
            >
              <Star size={13} fill={onlyWatched ? 'currentColor' : 'none'} className={onlyWatched ? 'text-white' : 'text-[#ba7c29]'} />
              <span>Watchlist</span>
              <span className="ml-0.5 rounded-full bg-black/10 dark:bg-white/10 px-1.5 py-0.2 text-[10px]">
                {watchlist.length}
              </span>
            </button>

            {/* Grid / Map Switcher Tabs */}
            <div className="flex rounded-full border border-[#173e42]/15 bg-white/70 dark:bg-[#0b2529] p-1">
              <button
                type="button"
                onClick={() => setViewMode('grid')}
                className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-bold transition ${
                  viewMode === 'grid'
                    ? 'bg-[#0d3035] text-white shadow-sm'
                    : 'text-[#617471] dark:text-[#8ea5a2] hover:text-[#0d3035] dark:hover:text-white'
                }`}
              >
                <CivicIcon name="file" size={13} />
                <span>Grid</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('map')}
                className={`flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-bold transition ${
                  viewMode === 'map'
                    ? 'bg-[#0d3035] text-white shadow-sm'
                    : 'text-[#617471] dark:text-[#8ea5a2] hover:text-[#0d3035] dark:hover:text-white'
                }`}
              >
                <CivicIcon name="location" size={13} />
                <span>GIS Map</span>
              </button>
            </div>

            {/* Mobile Filter Toggle */}
            <button
              type="button"
              onClick={() => setShowMobileFilters(!showMobileFilters)}
              className="sm:hidden flex items-center gap-1.5 rounded-full border border-[#173e42]/15 bg-white dark:bg-[#0b2529] px-3.5 py-2 text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee]"
            >
              <SlidersHorizontal size={13} />
              <span>Filters</span>
            </button>

            {/* Export Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setExportOpen(!exportOpen)}
                className="flex items-center gap-1.5 rounded-full border border-[#173e42]/15 bg-white dark:bg-[#0b2529] px-3.5 py-2.5 text-xs font-bold text-[#0d3035] dark:text-[#f6f4ee] hover:bg-[#fffaf0] dark:hover:bg-[#123035] transition"
              >
                <Download size={13} />
                <span>Export</span>
              </button>

              {exportOpen && (
                <div className="absolute right-0 mt-1.5 w-48 rounded-xl border border-[#173e42]/15 bg-white dark:bg-[#0b2529] p-1.5 shadow-xl z-30 text-xs">
                  <button
                    type="button"
                    onClick={() => handleExport('csv')}
                    className="w-full text-left rounded-lg px-3 py-2 text-[#0d3035] dark:text-[#f6f4ee] font-semibold hover:bg-[#f6f4ee] dark:hover:bg-[#123035]"
                  >
                    Download CSV Table
                  </button>
                  <button
                    type="button"
                    onClick={() => handleExport('json')}
                    className="w-full text-left rounded-lg px-3 py-2 text-[#0d3035] dark:text-[#f6f4ee] font-semibold hover:bg-[#f6f4ee] dark:hover:bg-[#123035]"
                  >
                    Download GeoJSON GIS
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        <div className={`rounded-[22px] border border-[#173e42]/12 dark:border-[#173e42]/30 bg-white dark:bg-[#0b2529] p-4 sm:p-5 shadow-[0_10px_30px_rgba(27,52,51,.04)] ${showMobileFilters ? 'block' : 'hidden sm:block'}`}>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 items-center">
            {/* Search Input */}
            <div className="sm:col-span-2">
              <form onSubmit={handleSearch} className="relative">
                <CivicIcon name="search" size={16} className="absolute left-3.5 top-3.5 text-[#70817e]" />
                <input
                  type="text"
                  className="w-full rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] py-3 pl-10 pr-4 text-xs sm:text-sm text-[#0d3035] dark:text-[#f6f4ee] placeholder:text-[#8a9996] outline-none focus:border-[#ba7c29] focus:ring-2 focus:ring-[#ba7c29]/15 transition"
                  placeholder="Search by keywords, road, landmark..."
                  value={filters.search}
                  onChange={set('search')}
                />
              </form>
            </div>

            {/* Status Select */}
            <div className="relative">
              <select
                className="w-full appearance-none rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] px-3.5 py-3 text-xs sm:text-sm font-semibold text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
                value={filters.status}
                onChange={set('status')}
              >
                <option value="">All Statuses</option>
                {STATUSES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
              <CivicIcon name="chevron" size={14} className="pointer-events-none absolute right-3.5 top-4 rotate-90 text-[#70817e]" />
            </div>

            {/* Severity Select */}
            <div className="relative">
              <select
                className="w-full appearance-none rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] px-3.5 py-3 text-xs sm:text-sm font-semibold text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
                value={filters.severity}
                onChange={set('severity')}
              >
                <option value="">All Severities</option>
                {SEVERITIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
              <CivicIcon name="chevron" size={14} className="pointer-events-none absolute right-3.5 top-4 rotate-90 text-[#70817e]" />
            </div>

            {/* Category Select + Reset Button */}
            <div className="flex gap-2">
              <div className="relative flex-1 min-w-0">
                <select
                  className="w-full truncate appearance-none rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] px-3.5 py-3 text-xs sm:text-sm font-semibold text-[#0d3035] dark:text-[#f6f4ee] outline-none focus:border-[#ba7c29]"
                  value={filters.category}
                  onChange={set('category')}
                >
                  <option value="">All Departments</option>
                  {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
                <CivicIcon name="chevron" size={14} className="pointer-events-none absolute right-3.5 top-4 rotate-90 text-[#70817e]" />
              </div>

              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={() => {
                    setFilters({ status: '', severity: '', category: '', search: '' })
                    setOnlyWatched(false)
                  }}
                  className="flex items-center justify-center size-11 rounded-xl border border-[#173e42]/15 bg-[#f8f8f4] dark:bg-[#06181b] text-[#556966] hover:text-[#b04b37] hover:border-[#b04b37]/30 transition shrink-0"
                  title="Clear all filters"
                >
                  <RotateCcw size={14} />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Content Area */}
        {loading ? (
          <div className="flex min-h-[380px] flex-col items-center justify-center py-16 text-center">
            <div className="ai-orbit relative flex size-16 items-center justify-center rounded-full bg-[#0d3035] text-[#e8b855]">
              <CivicIcon name="brain" size={26} />
              <span className="absolute -right-1 top-0 size-2.5 rounded-full bg-[#e8b855]" />
            </div>
            <p className="mt-5 font-serif text-xl font-bold">Querying Municipal Registry</p>
            <p className="mt-1 text-xs text-[#6e807e] dark:text-[#8ea5a2]">Synchronizing active incident dockets and triage records...</p>
          </div>
        ) : displayedReports.length === 0 ? (
          <div className="rounded-[26px] border border-[#173e42]/12 dark:border-[#173e42]/30 bg-white dark:bg-[#0b2529] p-12 text-center shadow-sm">
            <div className="mx-auto flex size-14 items-center justify-center rounded-full bg-[#e3f0ea] dark:bg-[#123830] text-[#2f7661] dark:text-[#70b99e]">
              <CivicIcon name="shield" size={26} />
            </div>
            <h3 className="mt-4 font-serif text-2xl font-bold text-[#0d3035] dark:text-[#f6f4ee]">
              No Incident Records Found
            </h3>
            <p className="mx-auto mt-2 max-w-md text-xs sm:text-sm text-[#617471] dark:text-[#8ea5a2] leading-relaxed">
              {onlyWatched
                ? 'You have not added any incidents to your monitored watchlist yet. Click the star icon on any complaint to follow its status.'
                : 'No incident reports match your active filter criteria. Try adjusting keywords or resetting filters.'}
            </p>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={() => {
                  setFilters({ status: '', severity: '', category: '', search: '' })
                  setOnlyWatched(false)
                }}
                className="mt-6 inline-flex items-center gap-2 rounded-full bg-[#0d3035] px-6 py-3 text-xs font-bold text-white transition hover:bg-[#16444a]"
              >
                <RotateCcw size={13} />
                <span>Reset All Filters</span>
              </button>
            )}
          </div>
        ) : viewMode === 'map' ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-xl border border-[#173e42]/12 dark:border-[#173e42]/30 bg-white dark:bg-[#0b2529] px-4 py-2.5 text-xs text-[#526663] dark:text-[#8ea5a2]">
              <span className="font-semibold">
                Plotting {displayedReports.filter(r => r.latitude && r.longitude).length} geocoded incidents on OpenStreetMap GIS
              </span>
              <span className="font-mono text-[10px] font-bold text-[#ba7c29] uppercase tracking-wider">
                MUNICIPAL GIS DISPATCH
              </span>
            </div>
            <div className="overflow-hidden rounded-[26px] border border-[#173e42]/15 shadow-[0_20px_50px_rgba(27,52,51,.1)]">
              <CivicMap reports={displayedReports} height="560px" hotspots={insights?.hotspots || []} />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5 sm:gap-6">
            {displayedReports.map(r => (
              <ReportCard
                key={r.id}
                report={r}
                onUpvote={handleUpvote}
                onWatchlistChange={handleWatchlistChange}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
