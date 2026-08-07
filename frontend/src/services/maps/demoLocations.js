/**
 * demoLocations.js
 * ─────────────────
 * Synthetic coordinates used ONLY when VITE_DEMO_MODE=true.
 *
 * All data is entirely fabricated for development and testing purposes.
 * No real hospital names, real addresses, or real patient data is used.
 * All coordinate objects carry `isDemo: true` to prevent confusion with
 * real operational data.
 *
 * In production, set VITE_DEMO_MODE=false (default).
 * Demo data is then never loaded or displayed.
 */

// These coordinates are near central Delhi — chosen arbitrarily.
// They do NOT represent real hospitals or real emergency vehicles.

export const DEMO_ROUTE_WAYPOINTS = [
  { lat: 28.6350, lng: 77.2210 },
  { lat: 28.6320, lng: 77.2195 },
  { lat: 28.6290, lng: 77.2175 },
  { lat: 28.6265, lng: 77.2155 },
  { lat: 28.6240, lng: 77.2135 },
  { lat: 28.6210, lng: 77.2115 },
  { lat: 28.6180, lng: 77.2100 },
  { lat: 28.6155, lng: 77.2093 },
  { lat: 28.6139, lng: 77.2090 },
];

export const DEMO_HOSPITALS = [
  {
    id: 'DEMO-HOSP-A',
    name: 'Demo Hospital A',
    lat: 28.6139,
    lng: 77.2090,
    level: 'Demo Level I',
    isDemo: true,
  },
  {
    id: 'DEMO-HOSP-B',
    name: 'Demo Hospital B',
    lat: 28.6448,
    lng: 77.2167,
    level: 'Demo Level II',
    isDemo: true,
  },
];

/**
 * Haversine distance in kilometres.
 */
export function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
    Math.cos((lat2 * Math.PI) / 180) *
    Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/**
 * Estimated ETA in minutes given distance and assumed speed.
 */
export function etaMinutes(distKm, speedKmh = 50) {
  return Math.max(1, Math.ceil((distKm / speedKmh) * 60));
}

/**
 * Format distance for display.
 */
export function formatDistance(km) {
  return km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1)} km`;
}
