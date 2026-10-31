import axios from 'axios'

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

/**
 * Reverse geocode latitude and longitude to a human-readable street/locality name.
 * Uses backend API with in-memory caching and 1 req/sec rate limit, with graceful browser fallback.
 */
export const reverseGeocodeAddress = async (lat, lng) => {
  if (!lat || !lng) return ''
  try {
    const { data } = await axios.get('/api/reports/reverse-geocode', {
      params: { latitude: lat, longitude: lng },
      timeout: 6000,
    })
    if (data?.address) return data.address
  } catch (err) {
    console.warn('Backend reverse-geocode lookup failed, attempting browser fallback', err)
  }

  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`,
      { headers: { Accept: 'application/json' } }
    )
    if (res.ok) {
      const json = await res.json()
      const addr = json.address || {}
      const parts = [
        addr.road || addr.pedestrian || addr.highway,
        addr.suburb || addr.neighbourhood || addr.residential || addr.subdistrict,
        addr.city || addr.town || addr.county,
      ].filter(Boolean)
      if (parts.length > 0) return parts.join(', ')
      if (json.display_name) return json.display_name
    }
  } catch (err) {
    console.warn('Direct Nominatim geocode fallback failed', err)
  }

  return `Near coordinates (${Number(lat).toFixed(4)}, ${Number(lng).toFixed(4)})`
}
