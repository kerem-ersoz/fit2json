import { useEffect } from 'react'
import { MapContainer, Polyline, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'

function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap()
  useEffect(() => {
    if (positions.length) {
      const bounds = L.latLngBounds(positions.map(([a, b]) => L.latLng(a, b)))
      map.fitBounds(bounds, { padding: [24, 24] })
    }
  }, [map, positions])
  return null
}

/**
 * GPS track map. scrollWheelZoom is disabled so the page keeps scrolling on
 * desktop; one-finger pan still works for touch. Height is fixed (Leaflet needs it).
 */
export function ActivityMap({ positions }: { positions: [number, number][] }) {
  if (!positions.length) return null
  return (
    <div className="activity-map overflow-hidden rounded-xl border border-divider">
      <MapContainer
        center={positions[0]}
        zoom={13}
        scrollWheelZoom={false}
        style={{ height: '18rem', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Polyline positions={positions} pathOptions={{ color: 'var(--color-accent)', weight: 4 }} />
        <FitBounds positions={positions} />
      </MapContainer>
    </div>
  )
}
