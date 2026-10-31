export const SEVERITY_COLORS = {
  critical: 'severity-critical',
  high: 'severity-high',
  medium: 'severity-medium',
  low: 'severity-low',
}

export const STATUS_COLORS = {
  open: 'status-open',
  in_progress: 'status-in_progress',
  resolved: 'status-resolved',
  closed: 'status-closed',
}

export const CATEGORIES = [
  { value: 'road_damage', label: 'Road & Highway Infrastructure' },
  { value: 'bridge_damage', label: 'Bridge & Structural Works' },
  { value: 'water_leak', label: 'Water Supply & Distribution' },
  { value: 'pollution', label: 'Environmental & Industrial Effluent' },
  { value: 'streetlight', label: 'Public Lighting & Electrical' },
  { value: 'garbage', label: 'Solid Waste & Sanitation' },
  { value: 'drainage', label: 'Stormwater & Drainage' },
  { value: 'other', label: 'General Municipal Works' },
]

export const CATEGORY_LABELS = Object.fromEntries(
  CATEGORIES.map(c => [c.value, c.label])
)

export const CATEGORY_EMOJIS = Object.fromEntries(
  CATEGORIES.map(c => [c.value, ''])
)

export const getWatchlist = () => {
  try {
    return JSON.parse(localStorage.getItem('janaawaz_watchlist') || localStorage.getItem('fordge_watchlist') || '[]')
  } catch {
    return []
  }
}

export const toggleWatchlist = (id) => {
  try {
    const list = getWatchlist()
    const idx = list.indexOf(id)
    if (idx >= 0) {
      list.splice(idx, 1)
    } else {
      list.push(id)
    }
    localStorage.setItem('janaawaz_watchlist', JSON.stringify(list))
    return list
  } catch {
    return []
  }
}

export const isWatched = (id) => {
  return getWatchlist().includes(id)
}
