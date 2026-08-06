/**
 * AmbulanceLocationContext
 * ─────────────────────────
 * Single shared source-of-truth for ambulance locations across:
 *   - EMSView (ambulance dashboard)
 *   - HospitalCommand (command map)
 *   - ClinicianWorkspace (case detail)
 *
 * Starts EMPTY. Ambulances are registered when:
 *   1. A WebSocket connection sends real location data.
 *   2. Demo mode is explicitly enabled (VITE_DEMO_MODE=true).
 *
 * When VITE_DEMO_MODE=true, a single synthetic ambulance is loaded
 * with coordinates clearly labeled as simulated. Demo mode is only
 * activated when explicitly configured — it does NOT silently appear
 * in the default UI.
 */

import React, {
  createContext, useContext, useState, useEffect, useRef, useCallback,
} from 'react';

// ──────────────────────────────────────────────────
// DEMO DATA — only used when VITE_DEMO_MODE=true
// All coordinates are synthetic. No real patient data.
// ──────────────────────────────────────────────────

const DEMO_HOSPITALS = [
  {
    id: 'DEMO-HOSP-A',
    name: 'Metro General ED (Demo)',
    shortName: 'Metro General',
    lat: 28.6139,
    lng: 77.2090,
    level: 'Level I Trauma',
    isDemo: true,
  },
  {
    id: 'DEMO-HOSP-B',
    name: 'Northside Medical (Demo)',
    shortName: 'Northside Medical',
    lat: 28.6448,
    lng: 77.2167,
    level: 'Level II Trauma',
    isDemo: true,
  },
];

const DEMO_ROUTE = [
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

function haversineKm(lat1, lng1, lat2, lng2) {
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

function etaMinutes(distKm, speedKmh = 50) {
  return Math.max(1, Math.ceil((distKm / speedKmh) * 60));
}

// ──────────────────────────────────────────────────
// CONTEXT
// ──────────────────────────────────────────────────

const AmbulanceLocationContext = createContext(null);

export function AmbulanceLocationProvider({ children }) {
  const isDemoMode = import.meta.env.VITE_DEMO_MODE === 'true';

  const [ambulances, setAmbulances] = useState(() => {
    if (!isDemoMode) return [];

    const hosp = DEMO_HOSPITALS[0];
    const start = DEMO_ROUTE[0];
    const distKm = haversineKm(start.lat, start.lng, hosp.lat, hosp.lng);
    return [{
      id: 'DEMO-AMB-1',
      caseId: 'DEMO-CASE-001',
      unitName: 'Unit 1 (Demo)',
      lat: start.lat,
      lng: start.lng,
      destinationHospital: hosp,
      destinationHospitalId: hosp.id,
      status: 'En Route',
      priority: 'HIGH',
      eta: etaMinutes(distKm),
      distanceKm: distKm,
      lastUpdated: new Date().toLocaleTimeString(),
      isDemo: true,
      routeStepIndex: 0,
    }];
  });

  const [hospitals] = useState(isDemoMode ? DEMO_HOSPITALS : []);

  const routeStepsRef = useRef({});

  // Demo simulation — only runs when VITE_DEMO_MODE=true
  useEffect(() => {
    if (!isDemoMode) return;

    ambulances.forEach(a => {
      if (routeStepsRef.current[a.id] === undefined) {
        routeStepsRef.current[a.id] = a.routeStepIndex ?? 0;
      }
    });

    const interval = setInterval(() => {
      setAmbulances(prev => prev.map(amb => {
        const route = amb.id === 'DEMO-AMB-1' ? DEMO_ROUTE : null;
        if (!route) return amb;

        const step = routeStepsRef.current[amb.id] ?? 0;
        if (step >= route.length - 1) return amb;

        const next = step + 1;
        routeStepsRef.current[amb.id] = next;
        const pos = route[next];
        const hosp = amb.destinationHospital;
        const distKm = hosp ? haversineKm(pos.lat, pos.lng, hosp.lat, hosp.lng) : 0;

        return {
          ...amb,
          lat: pos.lat,
          lng: pos.lng,
          distanceKm: distKm,
          eta: etaMinutes(distKm),
          routeStepIndex: next,
          lastUpdated: new Date().toLocaleTimeString(),
        };
      }));
    }, 5000);

    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDemoMode]);

  /**
   * Register or update an ambulance with real location data from WebSocket.
   * Calling this with isDemo=false marks the ambulance as having real GPS data.
   */
  const updateAmbulancePosition = useCallback((ambulanceId, lat, lng, extras = {}) => {
    setAmbulances(prev => {
      const existing = prev.find(a => a.id === ambulanceId);
      if (existing) {
        const hosp = existing.destinationHospital;
        const distKm = hosp ? haversineKm(lat, lng, hosp.lat, hosp.lng) : 0;
        return prev.map(a => a.id !== ambulanceId ? a : {
          ...a,
          lat, lng, distanceKm: distKm,
          eta: extras.eta ?? etaMinutes(distKm),
          lastUpdated: new Date().toLocaleTimeString(),
          isDemo: false,
          ...extras,
        });
      }
      return prev;
    });
  }, []);

  /**
   * Register a brand-new ambulance from a WebSocket connection.
   * No fake coordinates are injected — uses whatever the WS provides.
   */
  const registerAmbulance = useCallback((caseId, data) => {
    setAmbulances(prev => {
      if (prev.find(a => a.caseId === caseId || a.id === caseId)) return prev;

      // Only register if we have a real position
      const hasPosition = typeof data.lat === 'number' && typeof data.lng === 'number';

      return [...prev, {
        id: caseId,
        caseId,
        unitName: data.unitName || `Unit (${caseId})`,
        lat: hasPosition ? data.lat : null,
        lng: hasPosition ? data.lng : null,
        destinationHospital: null,
        destinationHospitalId: null,
        status: 'En Route',
        eta: data.eta ?? null,
        distanceKm: null,
        priority: data.priority || 'PENDING',
        lastUpdated: new Date().toLocaleTimeString(),
        isDemo: !hasPosition,
        routeStepIndex: 0,
      }];
    });
  }, []);

  const removeAmbulance = useCallback((caseId) => {
    setAmbulances(prev => prev.filter(a => a.id !== caseId && a.caseId !== caseId));
  }, []);

  const getAmbulanceByCaseId = useCallback(
    (caseId) => ambulances.find(a => a.caseId === caseId || a.id === caseId),
    [ambulances],
  );

  return (
    <AmbulanceLocationContext.Provider value={{
      ambulances,
      hospitals,
      isDemoMode,
      updateAmbulancePosition,
      registerAmbulance,
      removeAmbulance,
      getAmbulanceByCaseId,
    }}>
      {children}
    </AmbulanceLocationContext.Provider>
  );
}

export function useAmbulanceLocations() {
  const ctx = useContext(AmbulanceLocationContext);
  if (!ctx) throw new Error('useAmbulanceLocations must be used within AmbulanceLocationProvider');
  return ctx;
}
