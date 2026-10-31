import { useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Circle, useMapEvents, useMap } from 'react-leaflet'
import L from 'leaflet'
import { Link } from 'react-router-dom'
import { SEVERITY_COLORS, STATUS_COLORS } from './constants'

const SEVERITY_PIN_COLORS = {
  critical: '#b91c1c',
  high: '#c2410c',
  medium: '#475569',
  low: '#15803d',
}

const createPinIcon = (severity = 'medium', isPicker = false) => {
  const isCrit = severity === 'critical'
  const color = isPicker ? '#0f172a' : (SEVERITY_PIN_COLORS[severity] || '#475569')
  const size = isCrit ? 36 : 28

  return L.divIcon({
    className: 'custom-leaflet-marker',
    html: `
      <div style="position: relative; width: ${size}px; height: ${size}px;">
        ${isCrit ? `
          <div style="
            position: absolute;
            top: -6px;
            left: -6px;
            width: ${size + 12}px;
            height: ${size + 12}px;
            border-radius: 50%;
            background: rgba(185, 28, 28, 0.35);
            animation: leaflet-ping 1.6s cubic-bezier(0, 0, 0.2, 1) infinite;
          "></div>
        ` : ''}
        <div style="
          background-color: ${color};
          width: ${size}px;
          height: ${size}px;
          border-radius: 50% 50% 50% 0;
          transform: rotate(-45deg);
          display: flex;
          align-items: center;
          justify-content: center;
          border: 2px solid #ffffff;
          box-shadow: ${isCrit ? '0 0 12px rgba(185, 28, 28, 0.6), 0 3px 6px rgba(0, 0, 0, 0.3)' : '0 2px 4px rgba(0, 0, 0, 0.25)'};
        ">
          <div style="
            width: ${isCrit ? '8px' : '6px'};
            height: ${isCrit ? '8px' : '6px'};
            border-radius: 50%;
            background-color: #ffffff;
          "></div>
        </div>
      </div>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size],
    popupAnchor: [0, -size],
  })
}

function LocationPickerEvents({ onSelect }) {
  useMapEvents({
    click(e) {
      if (onSelect) {
        onSelect({
          latitude: Number(e.latlng.lat.toFixed(6)),
          longitude: Number(e.latlng.lng.toFixed(6)),
        })
      }
    },
  })
  return null
}

function ChangeView({ center, zoom }) {
  const map = useMap()
  useEffect(() => {
    if (center && center[0] && center[1]) {
      map.setView(center, zoom || map.getZoom())
    }
  }, [center, zoom, map])
  return null
}

export default function CivicMap({
  reports = [],
  hotspots = [],
  hotspotCircles = null,
  selectedPosition = null,
  onPositionSelect = null,
  height = '420px',
  interactivePicker = false,
  zoom = 13,
  center = null,
}) {
  const validReports = reports.filter(r => r.latitude && r.longitude)
  const activeHotspots = Array.isArray(hotspotCircles)
    ? hotspotCircles
    : (hotspots && hotspots.length > 0 ? hotspots : [])

  // Center on selectedPosition if set, or center prop (when no selectedPosition), or average of valid reports, or neutral India-wide center
  let defaultCenter = [20.5937, 78.9629]
  let effectiveZoom = zoom !== undefined ? zoom : (selectedPosition && selectedPosition[0] ? 14 : (center && center[0] ? 13 : 5))

  if (selectedPosition && selectedPosition[0] && selectedPosition[1]) {
    defaultCenter = selectedPosition
  } else if (center && center[0] && center[1]) {
    defaultCenter = center
  } else if (validReports.length > 0) {
    const avgLat = validReports.reduce((s, r) => s + r.latitude, 0) / validReports.length
    const avgLng = validReports.reduce((s, r) => s + r.longitude, 0) / validReports.length
    defaultCenter = [avgLat, avgLng]
    if (zoom === undefined) effectiveZoom = 12
  }

  return (
    <div
      className="w-full rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 shadow-sm relative z-0"
      style={{ height }}
    >
      <MapContainer
        center={defaultCenter}
        zoom={effectiveZoom}
        scrollWheelZoom={true}
        style={{ height: '100%', width: '100%' }}
      >
        <ChangeView center={defaultCenter} zoom={effectiveZoom} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {interactivePicker && (
          <LocationPickerEvents onSelect={onPositionSelect} />
        )}

        {/* Selected Position Marker (in picker mode) */}
        {interactivePicker && selectedPosition && selectedPosition[0] && selectedPosition[1] && (
          <Marker
            position={selectedPosition}
            icon={createPinIcon('critical', true)}
            draggable={true}
            eventHandlers={{
              dragend: (e) => {
                const marker = e.target
                const pos = marker.getLatLng()
                onPositionSelect?.({
                  latitude: Number(pos.lat.toFixed(6)),
                  longitude: Number(pos.lng.toFixed(6)),
                })
              },
            }}
          >
            <Popup>
              <div className="text-xs font-semibold p-1">
                Selected Incident Location<br />
                <span className="text-slate-500 font-normal text-[11px]">
                  Drag pin to reposition
                </span>
              </div>
            </Popup>
          </Marker>
        )}

        {/* 300m Hotspot Cluster Overlays */}
        {!interactivePicker &&
          activeHotspots.map((h, idx) => (
            <Circle
              key={`hotspot-${idx}-${h.lat}-${h.lon}`}
              center={[h.lat, h.lon]}
              radius={h.radius_meters || 300}
              pathOptions={{
                color: '#e8b855',
                fillColor: '#e8b855',
                fillOpacity: 0.22,
                weight: 2,
                dashArray: '5, 5',
              }}
            >
              <Popup>
                <div className="p-1 min-w-[190px] max-w-[240px]">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse"></span>
                    <span className="text-[11px] font-bold text-amber-800 dark:text-amber-400 uppercase tracking-wider font-mono">
                      300m Civic Hotspot
                    </span>
                  </div>
                  <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 mb-1">
                    {h.count} Grievance{h.count > 1 ? 's' : ''} in Cluster
                  </p>
                  <p className="text-[11px] text-slate-600 dark:text-slate-400 mb-1.5">
                    Dominant: <strong className="capitalize">{h.dominant_category?.replace('_', ' ')}</strong>
                  </p>
                  {h.sample_titles && h.sample_titles.length > 0 && (
                    <div className="text-[10px] text-slate-500 border-t border-slate-200 dark:border-slate-700 pt-1 mt-1">
                      <span className="font-medium text-slate-700 dark:text-slate-300">Cluster Samples:</span>
                      <ul className="list-disc list-inside mt-0.5 space-y-0.5">
                        {h.sample_titles.map((st, i) => (
                          <li key={i} className="truncate text-slate-600 dark:text-slate-400">{st}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </Popup>
            </Circle>
          ))}

        {/* Reports markers (in viewer mode) */}
        {!interactivePicker &&
          validReports.map((r) => (
            <Marker
              key={r.id}
              position={[r.latitude, r.longitude]}
              icon={createPinIcon(r.severity, false)}
            >
              <Popup className="civic-map-popup">
                <div className="p-1 min-w-[210px] max-w-[250px]">
                  <div className="mb-1.5">
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 block mb-0.5">
                      {r.category.replace('_', ' ')}
                    </span>
                    <h4 className="font-semibold text-slate-900 dark:text-slate-100 text-xs truncate">
                      {r.title}
                    </h4>
                  </div>

                  {r.media_url && r.media_url.match(/\.(jpg|jpeg|png|webp|gif)$/i) && (
                    <img
                      src={r.media_url}
                      alt="Evidence"
                      className="w-full h-20 object-cover rounded mb-2 border border-slate-200 dark:border-slate-700"
                    />
                  )}

                  <div className="flex gap-1 mb-2">
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${SEVERITY_COLORS[r.severity]}`}>
                      {r.severity}
                    </span>
                    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded uppercase tracking-wider ${STATUS_COLORS[r.status]}`}>
                      {r.status.replace('_', ' ')}
                    </span>
                  </div>

                  <p className="text-[11px] text-slate-600 dark:text-slate-400 line-clamp-2 mb-2 leading-tight">
                    {r.description}
                  </p>

                  <div className="text-[10px] text-slate-500 dark:text-slate-400 mb-2 truncate">
                    {r.location}
                  </div>

                  <Link
                    to={`/reports/${r.id}`}
                    className="block text-center text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white dark:bg-sky-600 dark:hover:bg-sky-500 py-1.5 px-2 rounded transition-colors"
                  >
                    View Incident Docket
                  </Link>
                </div>
              </Popup>
            </Marker>
          ))}
      </MapContainer>
    </div>
  )
}
