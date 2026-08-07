/**
 * MEDOPS — Core Leaflet Map Service
 * ===================================
 * Centralizes ALL Leaflet-specific logic. No Leaflet imports should
 * exist in page/component files — only this module.
 *
 * Public API:
 *   initializeMap(containerId, options)
 *   destroyMap(mapInstance)
 *   addMarker(mapInstance, lat, lng, options)
 *   updateMarker(markerInstance, lat, lng)
 *   removeMarker(markerInstance)
 *   drawRoute(mapInstance, waypoints, options)
 *   clearRoute(polylineInstance)
 *   fitMapToMarkers(mapInstance, markers, padding)
 *   setTileLayer(mapInstance, tileProvider)
 *   calculateDistance(lat1, lng1, lat2, lng2)
 *   fetchOsrmRoute(from, to, routingProvider)
 */

import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { DEFAULT_LIGHT_TILE, DEFAULT_DARK_TILE } from './tileProviders.js';

// Fix Leaflet's missing default marker icon paths (broken in bundlers)
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl,
  iconRetinaUrl,
  shadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

// ──────────────────────────────────────────────────
// CUSTOM SVG MARKER ICONS
// ──────────────────────────────────────────────────

/**
 * Creates a DivIcon with an SVG and optional badge label.
 */
function createSvgMarkerIcon(svgContent, options = {}) {
  const {
    size = 40,
    iconAnchor = null,
    className = 'medops-marker',
    label = null,
  } = options;

  const anchor = iconAnchor || [size / 2, size];

  const html = `
    <div class="marker-wrapper" style="position:relative;width:${size}px;height:${size}px;">
      ${svgContent}
      ${label ? `<div class="marker-label" style="position:absolute;bottom:-18px;left:50%;transform:translateX(-50%);white-space:nowrap;font-size:10px;font-weight:700;background:rgba(0,0,0,0.75);color:#fff;padding:1px 5px;border-radius:4px;">${label}</div>` : ''}
    </div>
  `;

  return L.divIcon({
    html,
    className,
    iconSize: [size, size],
    iconAnchor: anchor,
    popupAnchor: [0, -(size / 2) - 4],
  });
}

// Ambulance marker (red, pulsing border)
export function createAmbulanceIcon(label = null, isCritical = false) {
  const color = isCritical ? '#ef4444' : '#f97316';
  const pulse = isCritical
    ? `<circle cx="20" cy="20" r="18" fill="none" stroke="${color}" stroke-width="2" opacity="0.5"><animate attributeName="r" from="14" to="20" dur="1s" repeatCount="indefinite"/><animate attributeName="opacity" from="0.6" to="0" dur="1s" repeatCount="indefinite"/></circle>`
    : '';

  const svg = `
    <svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
      ${pulse}
      <circle cx="20" cy="20" r="16" fill="${color}" stroke="white" stroke-width="2.5" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.3))"/>
      <text x="20" y="26" font-size="18" text-anchor="middle" fill="white">🚑</text>
    </svg>
  `;
  return createSvgMarkerIcon(svg, { size: 40, iconAnchor: [20, 20], label });
}

// Hospital marker (blue cross)
export function createHospitalIcon(label = null) {
  const svg = `
    <svg width="36" height="36" viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="2" width="32" height="32" rx="6" fill="#2563eb" stroke="white" stroke-width="2" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.3))"/>
      <path d="M18 9v18M9 18h18" stroke="white" stroke-width="4" stroke-linecap="round"/>
    </svg>
  `;
  return createSvgMarkerIcon(svg, { size: 36, iconAnchor: [18, 18], label });
}

// Patient/pickup location marker
export function createPatientIcon() {
  const svg = `
    <svg width="34" height="34" viewBox="0 0 34 34" xmlns="http://www.w3.org/2000/svg">
      <circle cx="17" cy="17" r="14" fill="#8b5cf6" stroke="white" stroke-width="2.5" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.3))"/>
      <text x="17" y="23" font-size="16" text-anchor="middle" fill="white">👤</text>
    </svg>
  `;
  return createSvgMarkerIcon(svg, { size: 34, iconAnchor: [17, 17] });
}

// Critical case marker (red, pulsing)
export function createCriticalIcon() {
  const svg = `
    <svg width="38" height="38" viewBox="0 0 38 38" xmlns="http://www.w3.org/2000/svg">
      <circle cx="19" cy="19" r="17" fill="none" stroke="#ef4444" stroke-width="2" opacity="0.4">
        <animate attributeName="r" from="13" to="19" dur="0.8s" repeatCount="indefinite"/>
        <animate attributeName="opacity" from="0.5" to="0" dur="0.8s" repeatCount="indefinite"/>
      </circle>
      <circle cx="19" cy="19" r="14" fill="#ef4444" stroke="white" stroke-width="2.5"/>
      <text x="19" y="25" font-size="16" text-anchor="middle" fill="white">⚠</text>
    </svg>
  `;
  return createSvgMarkerIcon(svg, { size: 38, iconAnchor: [19, 19] });
}

// High-priority marker (amber)
export function createHighPriorityIcon(label = null) {
  const svg = `
    <svg width="34" height="34" viewBox="0 0 34 34" xmlns="http://www.w3.org/2000/svg">
      <circle cx="17" cy="17" r="14" fill="#f59e0b" stroke="white" stroke-width="2.5" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.25))"/>
      <text x="17" y="23" font-size="15" text-anchor="middle" fill="white">!</text>
    </svg>
  `;
  return createSvgMarkerIcon(svg, { size: 34, iconAnchor: [17, 17], label });
}

// ──────────────────────────────────────────────────
// COORDINATE VALIDATION
// ──────────────────────────────────────────────────

/**
 * Returns true if lat/lng is a valid geographic coordinate.
 */
export function isValidLatLng(lat, lng) {
  return (
    typeof lat === 'number' &&
    typeof lng === 'number' &&
    !isNaN(lat) &&
    !isNaN(lng) &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180
  );
}

// ──────────────────────────────────────────────────
// MAP INITIALIZATION
// ──────────────────────────────────────────────────

/**
 * Initializes a Leaflet map in the given DOM container.
 *
 * @param {string|HTMLElement} container - DOM element or ID string
 * @param {Object} options
 * @param {number} options.lat - Initial center latitude
 * @param {number} options.lng - Initial center longitude
 * @param {number} options.zoom - Initial zoom level (default 13)
 * @param {boolean} options.isDark - Use dark tile theme
 * @param {Object} options.tileProvider - Override tile provider
 * @returns {L.Map|null} Leaflet map instance, or null on failure
 */
export function initializeMap(container, options = {}) {
  try {
    const {
      lat = 28.6139,
      lng = 77.2090,
      zoom = 13,
      isDark = false,
      tileProvider = null,
    } = options;

    if (!isValidLatLng(lat, lng)) {
      console.warn('[MapService] Invalid initial coordinates, using defaults');
    }

    const map = L.map(container, {
      center: [lat, lng],
      zoom,
      zoomControl: false, // We add custom controls
      attributionControl: true,
    });

    // Attribution must always be visible (OSM requirement)
    map.attributionControl.setPrefix(false);

    // Apply tile layer
    const provider = tileProvider || (isDark ? DEFAULT_DARK_TILE : DEFAULT_LIGHT_TILE);
    setTileLayer(map, provider);

    // Custom zoom control (top-right)
    L.control.zoom({ position: 'topright' }).addTo(map);

    return map;
  } catch (err) {
    console.error('[MapService] Failed to initialize map:', err);
    return null;
  }
}

/**
 * Destroys/removes a Leaflet map instance and cleans up.
 */
export function destroyMap(map) {
  try {
    if (map) map.remove();
  } catch (err) {
    console.error('[MapService] Error destroying map:', err);
  }
}

// ──────────────────────────────────────────────────
// TILE LAYER
// ──────────────────────────────────────────────────

let _activeTileLayer = null;

/**
 * Sets or replaces the tile layer on a map instance.
 * @param {L.Map} map
 * @param {Object} tileProvider - Provider config from tileProviders.js
 */
export function setTileLayer(map, tileProvider) {
  try {
    if (_activeTileLayer) {
      map.removeLayer(_activeTileLayer);
    }
    _activeTileLayer = L.tileLayer(tileProvider.url, {
      attribution: tileProvider.attribution,
      maxZoom: tileProvider.maxZoom || 19,
    });
    _activeTileLayer.addTo(map);

    // Graceful tile error handling
    _activeTileLayer.on('tileerror', () => {
      console.warn('[MapService] Tile load error. Check network or tile provider.');
    });

    return _activeTileLayer;
  } catch (err) {
    console.error('[MapService] Failed to set tile layer:', err);
    return null;
  }
}

// ──────────────────────────────────────────────────
// MARKERS
// ──────────────────────────────────────────────────

/**
 * Adds a marker to the map.
 *
 * @param {L.Map} map
 * @param {number} lat
 * @param {number} lng
 * @param {Object} options
 * @param {L.Icon} options.icon - Custom icon (from createXxxIcon helpers)
 * @param {string} options.popup - HTML popup content
 * @param {string} options.tooltip - Tooltip text
 * @returns {L.Marker|null}
 */
export function addMarker(map, lat, lng, options = {}) {
  try {
    if (!isValidLatLng(lat, lng)) {
      console.warn('[MapService] addMarker: invalid coordinates', lat, lng);
      return null;
    }

    const { icon, popup, tooltip, draggable = false } = options;

    const markerOptions = { draggable };
    if (icon) markerOptions.icon = icon;

    const marker = L.marker([lat, lng], markerOptions);

    if (popup) marker.bindPopup(popup, { maxWidth: 320 });
    if (tooltip) marker.bindTooltip(tooltip, { direction: 'top', offset: [0, -10] });

    marker.addTo(map);
    return marker;
  } catch (err) {
    console.error('[MapService] addMarker error:', err);
    return null;
  }
}

/**
 * Updates a marker's position smoothly.
 * @param {L.Marker} marker
 * @param {number} lat
 * @param {number} lng
 */
export function updateMarker(marker, lat, lng) {
  try {
    if (!marker || !isValidLatLng(lat, lng)) return;
    marker.setLatLng([lat, lng]);
  } catch (err) {
    console.error('[MapService] updateMarker error:', err);
  }
}

/**
 * Removes a marker from the map.
 * @param {L.Marker} marker
 */
export function removeMarker(marker) {
  try {
    if (marker) marker.remove();
  } catch (err) {
    console.error('[MapService] removeMarker error:', err);
  }
}

/**
 * Updates a marker's popup content.
 */
export function updateMarkerPopup(marker, html) {
  try {
    if (marker) marker.setPopupContent(html);
  } catch (err) {
    console.error('[MapService] updateMarkerPopup error:', err);
  }
}

// ──────────────────────────────────────────────────
// ROUTES / POLYLINES
// ──────────────────────────────────────────────────

/**
 * Draws a route polyline on the map.
 *
 * @param {L.Map} map
 * @param {Array<{lat, lng}>} waypoints
 * @param {Object} options
 * @returns {L.Polyline|null}
 */
export function drawRoute(map, waypoints, options = {}) {
  try {
    if (!waypoints || waypoints.length < 2) return null;

    const {
      color = '#3b82f6',
      weight = 5,
      opacity = 0.8,
      dashArray = null,
      className = '',
    } = options;

    const latlngs = waypoints.map((wp) => [wp.lat, wp.lng]);
    const polyline = L.polyline(latlngs, {
      color,
      weight,
      opacity,
      dashArray,
      className,
      lineCap: 'round',
      lineJoin: 'round',
    });

    polyline.addTo(map);
    return polyline;
  } catch (err) {
    console.error('[MapService] drawRoute error:', err);
    return null;
  }
}

/**
 * Removes a polyline from the map.
 */
export function clearRoute(polyline) {
  try {
    if (polyline) polyline.remove();
  } catch (err) {
    console.error('[MapService] clearRoute error:', err);
  }
}

// ──────────────────────────────────────────────────
// VIEW FITTING
// ──────────────────────────────────────────────────

/**
 * Fits the map viewport to show all given markers/coordinates.
 *
 * @param {L.Map} map
 * @param {Array<L.Marker|{lat,lng}>} items - Markers or coordinate objects
 * @param {Object} paddingOptions - Leaflet fitBounds padding options
 */
export function fitMapToMarkers(map, items, paddingOptions = {}) {
  try {
    if (!map || !items || items.length === 0) return;

    const latlngs = items
      .map((item) => {
        if (item instanceof L.Marker) return item.getLatLng();
        if (item.lat !== undefined) return L.latLng(item.lat, item.lng);
        return null;
      })
      .filter(Boolean);

    if (latlngs.length === 0) return;

    const bounds = L.latLngBounds(latlngs);
    map.fitBounds(bounds, {
      padding: [40, 40],
      maxZoom: 16,
      ...paddingOptions,
    });
  } catch (err) {
    console.error('[MapService] fitMapToMarkers error:', err);
  }
}

// ──────────────────────────────────────────────────
// DISTANCE CALCULATION
// ──────────────────────────────────────────────────

/**
 * Calculates the straight-line (haversine) distance in km.
 * @returns {number} distance in km
 */
export function calculateDistance(lat1, lng1, lat2, lng2) {
  try {
    const from = L.latLng(lat1, lng1);
    const to = L.latLng(lat2, lng2);
    return from.distanceTo(to) / 1000; // meters → km
  } catch {
    return 0;
  }
}

/**
 * Formats distance for display.
 */
export function formatDistance(km) {
  if (km < 1) return `${Math.round(km * 1000)} m`;
  return `${km.toFixed(1)} km`;
}

// ──────────────────────────────────────────────────
// OSRM ROUTING (Abstracted)
// ──────────────────────────────────────────────────

/**
 * Fetches a road-following route from OSRM or falls back to straight-line.
 *
 * NOTE: Uses OSRM demo server — for testing/demo ONLY.
 * Returns an array of {lat, lng} waypoints.
 *
 * @param {{lat,lng}} from - Origin coordinate
 * @param {{lat,lng}} to - Destination coordinate
 * @param {Object} routingProvider - Provider config (defaults to OSRM demo)
 * @returns {Promise<{waypoints: Array, distanceKm: number, durationMin: number}>}
 */
export async function fetchOsrmRoute(from, to, routingProvider = null) {
  const baseUrl = routingProvider?.baseUrl || 'https://router.project-osrm.org/route/v1/driving';

  try {
    if (!isValidLatLng(from.lat, from.lng) || !isValidLatLng(to.lat, to.lng)) {
      throw new Error('Invalid coordinates for routing');
    }

    const url = `${baseUrl}/${from.lng},${from.lat};${to.lng},${to.lat}?overview=full&geometries=geojson&steps=false`;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);

    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeout);

    if (!res.ok) throw new Error(`OSRM returned ${res.status}`);

    const data = await res.json();

    if (data.code !== 'Ok' || !data.routes || data.routes.length === 0) {
      throw new Error('No route found by OSRM');
    }

    const route = data.routes[0];
    const coords = route.geometry.coordinates; // [lng, lat] pairs
    const waypoints = coords.map(([lng, lat]) => ({ lat, lng }));
    const distanceKm = route.distance / 1000;
    const durationMin = Math.ceil(route.duration / 60);

    return { waypoints, distanceKm, durationMin, source: 'osrm' };
  } catch (err) {
    console.warn('[MapService] OSRM routing failed, using fallback straight-line:', err.message);

    // Fallback: straight line between two points
    const distanceKm = calculateDistance(from.lat, from.lng, to.lat, to.lng);
    const durationMin = Math.ceil((distanceKm / 50) * 60); // assume 50 km/h

    return {
      waypoints: [from, to],
      distanceKm,
      durationMin,
      source: 'fallback_straight_line',
    };
  }
}
