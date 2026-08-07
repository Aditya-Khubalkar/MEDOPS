/**
 * MEDOPS — MedopsMap React Component
 * =====================================
 * A reusable, self-contained Leaflet map component for MEDOPS.
 *
 * Features:
 * - Ambulance markers (real-time updatable)
 * - Hospital markers
 * - Patient/pickup markers
 * - Route polylines (OSRM or fallback)
 * - Fit-to-route control
 * - Demo/simulated location badge
 * - Error and loading states
 * - Responsive, no overflow
 * - Legend overlay
 * - Map status (connection, last update, demo badge)
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  initializeMap,
  destroyMap,
  addMarker,
  updateMarker,
  removeMarker,
  drawRoute,
  clearRoute,
  fitMapToMarkers,
  fetchOsrmRoute,
  calculateDistance,
  formatDistance,
  createAmbulanceIcon,
  createHospitalIcon,
  createPatientIcon,
  createCriticalIcon,
  isValidLatLng,
  setTileLayer,
} from '../services/maps/mapService.js';
import { DEFAULT_LIGHT_TILE } from '../services/maps/tileProviders.js';

// ──────────────────────────────────────────────────
// POPUP TEMPLATES
// ──────────────────────────────────────────────────

function ambulancePopupHtml({ unitName, caseId, status, eta, distanceKm, lastUpdated, isDemo }) {
  return `
    <div style="font-family:'Outfit',sans-serif;min-width:200px;">
      <div style="font-weight:700;font-size:14px;margin-bottom:6px;color:#1e293b;">
        🚑 ${unitName || 'Ambulance'}
        ${isDemo ? '<span style="font-size:9px;background:#f59e0b;color:#fff;padding:1px 5px;border-radius:4px;margin-left:4px;">DEMO</span>' : ''}
      </div>
      ${caseId ? `<div style="font-size:11px;color:#64748b;margin-bottom:4px;">Case: <strong>${caseId}</strong></div>` : ''}
      ${status ? `<div style="font-size:11px;color:#64748b;margin-bottom:4px;">Status: <strong style="color:#f97316">${status}</strong></div>` : ''}
      ${eta !== undefined ? `<div style="font-size:11px;color:#64748b;margin-bottom:4px;">ETA: <strong>${eta} min</strong></div>` : ''}
      ${distanceKm !== undefined ? `<div style="font-size:11px;color:#64748b;margin-bottom:4px;">Distance: <strong>${formatDistance(distanceKm)}</strong></div>` : ''}
      ${lastUpdated ? `<div style="font-size:10px;color:#94a3b8;margin-top:6px;">Updated: ${lastUpdated}</div>` : ''}
      ${isDemo ? '<div style="font-size:10px;color:#f59e0b;margin-top:6px;border-top:1px solid #fde68a;padding-top:4px;">⚠ Demo / Simulated Location</div>' : ''}
    </div>
  `;
}

function hospitalPopupHtml({ name, level, capacity, id }) {
  return `
    <div style="font-family:'Outfit',sans-serif;min-width:180px;">
      <div style="font-weight:700;font-size:14px;margin-bottom:6px;color:#1e293b;">
        🏥 ${name}
      </div>
      ${level ? `<div style="font-size:11px;color:#64748b;margin-bottom:4px;">${level}</div>` : ''}
      ${id ? `<div style="font-size:11px;color:#64748b;margin-bottom:4px;">ID: ${id}</div>` : ''}
      ${capacity ? `<div style="font-size:11px;margin-top:4px;color:#64748b;">Capacity: <strong style="color:#2563eb">${capacity.available}/${capacity.total} beds available</strong></div>` : ''}
    </div>
  `;
}

// ──────────────────────────────────────────────────
// MAIN COMPONENT
// ──────────────────────────────────────────────────

/**
 * @param {Object} props
 * @param {string} [props.className] - CSS class for the outer container
 * @param {string} [props.style] - Inline style for the outer container
 * @param {number} [props.initialLat] - Map center latitude
 * @param {number} [props.initialLng] - Map center longitude
 * @param {number} [props.initialZoom] - Zoom level
 * @param {boolean} [props.isDark] - Use dark tile theme
 * @param {Array} [props.ambulances] - Array of ambulance data objects
 * @param {Array} [props.hospitals] - Array of hospital data objects
 * @param {Object} [props.selectedAmbulance] - Currently focused ambulance
 * @param {boolean} [props.showRoute] - Whether to draw route between ambulance & hospital
 * @param {boolean} [props.showLegend] - Show/hide the legend
 * @param {string} [props.connectionStatus] - 'connected' | 'disconnected' | 'connecting'
 * @param {boolean} [props.isDemo] - Override demo flag
 * @param {Function} [props.onMapReady] - Called with map instance when initialized
 * @param {Function} [props.onMarkerClick] - Called when a marker is clicked
 */
export default function MedopsMap({
  className = '',
  style = {},
  initialLat,
  initialLng,
  initialZoom = 13,
  ambulances = [],
  hospitals = [],
  selectedAmbulance = null,
  showRoute = true,
  showLegend = true,
  connectionStatus = 'connecting',
  isDemo: propIsDemo = false,
  onMapReady,
  onMarkerClick,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef({}); // { [id]: L.Marker }
  const hospitalMarkersRef = useRef({});
  const routeLayersRef = useRef({}); // { [ambulanceId]: L.Polyline }
  const tileLayerRef = useRef(null);

  const [mapError, setMapError] = useState(null);
  const [routeStatus, setRouteStatus] = useState('idle'); // idle | loading | loaded | failed
  const [routeInfo, setRouteInfo] = useState(null); // { distanceKm, durationMin }
  const [isInitialized, setIsInitialized] = useState(false);

  const isDemo = propIsDemo === true;

  // ── Initialize Map ──────────────────────────────
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    try {
      // Determine center: first ambulance, first hospital, or fallback
      const centerLat =
        initialLat ??
        ambulances[0]?.lat ??
        hospitals[0]?.lat ??
        28.6139;
      const centerLng =
        initialLng ??
        ambulances[0]?.lng ??
        hospitals[0]?.lng ??
        77.209;

      const map = initializeMap(container, {
        lat: centerLat,
        lng: centerLng,
        zoom: initialZoom,
        isDark,
      });

      if (!map) {
        setMapError('Failed to initialize map. The map library could not be loaded.');
        return;
      }

      mapRef.current = map;
      setIsInitialized(true);
      if (onMapReady) onMapReady(map);
    } catch (err) {
      console.error('[MedopsMap] init error:', err);
      setMapError('Map could not be initialized. Please reload the page.');
    }

    return () => {
      // Clean up on unmount
      Object.values(routeLayersRef.current).forEach(clearRoute);
      routeLayersRef.current = {};
      destroyMap(mapRef.current);
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Update tile layer when initialized ─────────
  useEffect(() => {
    if (!mapRef.current || !isInitialized) return;
    setTileLayer(mapRef.current, DEFAULT_LIGHT_TILE);
  }, [isInitialized]);

  // ── Sync Hospital Markers ───────────────────────
  useEffect(() => {
    if (!mapRef.current || !isInitialized) return;
    const map = mapRef.current;
    const existing = hospitalMarkersRef.current;

    // Remove stale
    Object.keys(existing).forEach((id) => {
      if (!hospitals.find((h) => h.id === id)) {
        removeMarker(existing[id]);
        delete existing[id];
      }
    });

    // Add/update
    hospitals.forEach((hosp) => {
      if (!isValidLatLng(hosp.lat, hosp.lng)) return;
      if (existing[hosp.id]) {
        updateMarker(existing[hosp.id], hosp.lat, hosp.lng);
      } else {
        const icon = createHospitalIcon(hosp.shortName);
        const popup = hospitalPopupHtml(hosp);
        const marker = addMarker(map, hosp.lat, hosp.lng, { icon, popup });
        if (marker) {
          marker.on('click', () => onMarkerClick?.({ type: 'hospital', data: hosp }));
          existing[hosp.id] = marker;
        }
      }
    });
  }, [hospitals, isInitialized, onMarkerClick]);

  // ── Sync Ambulance Markers ──────────────────────
  useEffect(() => {
    if (!mapRef.current || !isInitialized) return;
    const map = mapRef.current;
    const existing = markersRef.current;

    // Remove stale
    Object.keys(existing).forEach((id) => {
      if (!ambulances.find((a) => a.id === id)) {
        removeMarker(existing[id]);
        delete existing[id];
      }
    });

    // Add/update each ambulance
    ambulances.forEach((amb) => {
      if (!isValidLatLng(amb.lat, amb.lng)) return;

      const isCritical = amb.priority === 'CRITICAL';
      const icon = createAmbulanceIcon(amb.unitName, isCritical);
      const distKm =
        amb.destinationHospital && isValidLatLng(amb.lat, amb.lng)
          ? calculateDistance(
              amb.lat,
              amb.lng,
              amb.destinationHospital.lat,
              amb.destinationHospital.lng
            )
          : undefined;

      const popup = ambulancePopupHtml({
        unitName: amb.unitName,
        caseId: amb.caseId,
        status: amb.status,
        eta: amb.eta,
        distanceKm: distKm,
        lastUpdated: amb.lastUpdated,
        isDemo: isDemo || amb.isDemo,
      });

      if (existing[amb.id]) {
        updateMarker(existing[amb.id], amb.lat, amb.lng);
        existing[amb.id].setIcon(icon);
        existing[amb.id].setPopupContent(popup);
      } else {
        const marker = addMarker(map, amb.lat, amb.lng, { icon, popup });
        if (marker) {
          marker.on('click', () => onMarkerClick?.({ type: 'ambulance', data: amb }));
          existing[amb.id] = marker;
        }
      }
    });
  }, [ambulances, isInitialized, isDemo, onMarkerClick]);

  // ── Draw Route for Selected Ambulance ──────────
  const drawSelectedRoute = useCallback(async () => {
    if (!mapRef.current || !selectedAmbulance || !showRoute) return;

    const { lat, lng, destinationHospital } = selectedAmbulance;

    if (!isValidLatLng(lat, lng)) return;
    if (!destinationHospital || !isValidLatLng(destinationHospital.lat, destinationHospital.lng))
      return;

    // Clear previous route for this ambulance
    if (routeLayersRef.current[selectedAmbulance.id]) {
      clearRoute(routeLayersRef.current[selectedAmbulance.id]);
    }

    setRouteStatus('loading');

    try {
      const result = await fetchOsrmRoute(
        { lat, lng },
        { lat: destinationHospital.lat, lng: destinationHospital.lng }
      );

      if (!mapRef.current) return; // Unmounted during fetch

      const polyline = drawRoute(mapRef.current, result.waypoints, {
        color: '#3b82f6',
        weight: 5,
        opacity: 0.85,
        dashArray: result.source === 'fallback_straight_line' ? '8 6' : null,
      });

      if (polyline) {
        routeLayersRef.current[selectedAmbulance.id] = polyline;
      }

      setRouteInfo({ distanceKm: result.distanceKm, durationMin: result.durationMin });
      setRouteStatus(result.source === 'fallback_straight_line' ? 'fallback' : 'loaded');
    } catch {
      setRouteStatus('failed');
    }
  }, [selectedAmbulance, showRoute]);

  useEffect(() => {
    drawSelectedRoute();
  }, [drawSelectedRoute]);

  // ── Fit map to markers ──────────────────────────
  const handleFitAll = useCallback(() => {
    if (!mapRef.current) return;
    const allItems = [
      ...Object.values(markersRef.current),
      ...Object.values(hospitalMarkersRef.current),
    ];
    if (allItems.length > 0) {
      fitMapToMarkers(mapRef.current, allItems);
    }
  }, []);

  // Auto-fit when ambulances or hospitals change significantly
  useEffect(() => {
    if (!isInitialized) return;
    const total =
      Object.keys(markersRef.current).length + Object.keys(hospitalMarkersRef.current).length;
    if (total > 0) {
      handleFitAll();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isInitialized]);

  // ──────────────────────────────────────────────────
  // RENDER
  // ──────────────────────────────────────────────────

  if (mapError) {
    return (
      <div
        className={`relative rounded-xl overflow-hidden border border-red-200 bg-red-50 flex flex-col items-center justify-center text-center p-8 ${className}`}
        style={{ minHeight: 280, ...style }}
      >
        <div className="text-4xl mb-3">🗺️</div>
        <p className="font-bold text-red-700 mb-1">Map Unavailable</p>
        <p className="text-sm text-red-600">{mapError}</p>
        <p className="text-xs text-gray-400 mt-2">Check your network connection and reload.</p>
      </div>
    );
  }

  return (
    <div
      className={`relative overflow-hidden bg-gray-100 ${className}`}
      style={{ minHeight: 280, ...style }}
    >
      {/* Map container */}
      <div ref={containerRef} style={{ width: '100%', height: '100%', minHeight: 300 }} />

      {/* Loading shimmer */}
      {!isInitialized && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 z-10">
          <div className="flex flex-col items-center gap-3">
            <div className="w-9 h-9 border-4 border-rose-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-gray-500 font-medium">Loading map…</span>
          </div>
        </div>
      )}

      {/* TOP-LEFT: Demo badge + route info */}
      <div className="absolute top-3 left-3 z-[400] flex flex-col gap-2 pointer-events-none">
        {isDemo && (
          <div className="flex items-center gap-1.5 bg-amber-500/90 backdrop-blur-sm text-white text-[11px] font-bold px-2.5 py-1 rounded-lg shadow-md">
            <span className="text-xs">⚠</span>
            Demo / Simulated Position
          </div>
        )}
        {routeStatus === 'loading' && (
          <div className="bg-white/90 backdrop-blur-sm text-blue-600 text-[11px] font-medium px-2.5 py-1 rounded-lg shadow-md flex items-center gap-1.5">
            <div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            Calculating route…
          </div>
        )}
        {routeInfo && routeStatus !== 'loading' && (
          <div className="bg-white/90 backdrop-blur-sm text-gray-800 text-[11px] font-medium px-2.5 py-1.5 rounded-lg shadow-md">
            <div className="font-bold text-blue-600">
              📍 {formatDistance(routeInfo.distanceKm)} · ~{routeInfo.durationMin} min
            </div>
            {routeStatus === 'fallback' && (
              <div className="text-gray-400 text-[10px] mt-0.5">Straight-line (routing unavailable)</div>
            )}
          </div>
        )}
      </div>

      {/* TOP-RIGHT: Custom controls */}
      <div className="absolute top-3 right-14 z-[400] flex flex-col gap-1.5">
        <button
          onClick={handleFitAll}
          title="Fit map to all markers"
          className="w-8 h-8 bg-white hover:bg-rose-50 border border-gray-200 rounded-lg shadow-sm flex items-center justify-center text-gray-600 transition-colors text-sm font-bold"
        >
          ⊞
        </button>
      </div>

      {/* BOTTOM-LEFT: Connection status */}
      <div className="absolute bottom-8 left-3 z-[400] flex items-center gap-1.5 bg-white/90 backdrop-blur-sm px-2.5 py-1 rounded-lg shadow-sm text-[11px] font-medium">
        <span className={`w-2 h-2 rounded-full ${
          connectionStatus === 'connected' ? 'bg-emerald-500 animate-pulse'
          : connectionStatus === 'connecting' ? 'bg-amber-400 animate-pulse'
          : 'bg-red-500'
        }`} />
        <span className="text-gray-600 capitalize">{connectionStatus}</span>
      </div>

      {/* BOTTOM-RIGHT: Legend */}
      {showLegend && (
        <div className="absolute bottom-8 right-3 z-[400] bg-white/90 backdrop-blur-sm rounded-xl shadow-sm border border-gray-100 px-3 py-2 text-[10px] font-medium text-gray-600">
          <div className="font-bold text-gray-700 mb-1.5 text-[11px]">Legend</div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-base leading-none">🚑</span>
              <span>Ambulance</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-base leading-none">🏥</span>
              <span>Hospital</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block w-6 h-0.5 rounded-full" style={{ background: '#3b82f6' }} />
              <span>Route</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
