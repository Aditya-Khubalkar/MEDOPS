import React, { useState, useEffect } from 'react';
import {
  Activity, Clock, Users, Radio, AlertTriangle, HeartPulse,
  Stethoscope, Map as MapIcon, X, ChevronRight
} from 'lucide-react';
import MedopsMap from '../components/MedopsMap';
import { useAmbulanceLocations } from '../context/AmbulanceLocationContext';

const BACKEND_WS = import.meta.env.VITE_BACKEND_WS || 'ws://localhost:8000';

export default function HospitalCommand() {
  const { ambulances, hospitals, registerAmbulance, isDemoMode } = useAmbulanceLocations();
  const [wsConnected, setWsConnected] = useState(false);
  const [selectedAmbulanceId, setSelectedAmbulanceId] = useState(null);
  const [showMap, setShowMap] = useState(true);

  // WebSocket: receives live ambulance updates
  useEffect(() => {
    let ws;
    let reconnectTimer;

    const connect = () => {
      try {
        ws = new WebSocket(`${BACKEND_WS}/ws/hospital`);

        ws.onopen = () => setWsConnected(true);
        ws.onclose = () => {
          setWsConnected(false);
          reconnectTimer = setTimeout(connect, 5000);
        };
        ws.onerror = () => setWsConnected(false);

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'AMBULANCE_UPDATE') {
              const { case_id, data } = msg;
              if (data?.type === 'TELEMETRY') {
                registerAmbulance(case_id, {
                  lat: data.lat ?? null,
                  lng: data.lng ?? null,
                  eta: data.eta ?? null,
                  unitName: data.unitName,
                });
              }
            }
          } catch (_) {}
        };
      } catch (_) {
        setWsConnected(false);
        reconnectTimer = setTimeout(connect, 5000);
      }
    };

    connect();
    return () => {
      clearTimeout(reconnectTimer);
      try { ws?.close(); } catch (_) {}
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedAmbulance = selectedAmbulanceId
    ? ambulances.find(a => a.id === selectedAmbulanceId)
    : null;

  const criticalCount = ambulances.filter(a => a.priority === 'CRITICAL').length;
  const hasLiveData = ambulances.length > 0;

  return (
    <div className="flex flex-col gap-5">

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <Activity size={24} className="text-rose-500" />
            Hospital Command
          </h1>
          <p className="text-sm text-gray-500 mt-0.5 ml-9">Incoming ambulance queue and live telemetry</p>
        </div>

        <div className="flex items-center gap-3">
          {isDemoMode && (
            <span className="text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200 px-2.5 py-1 rounded-lg">
              Demo Mode
            </span>
          )}
          {criticalCount > 0 && (
            <div className="bg-red-50 border border-red-200 px-3 py-1.5 rounded-xl flex items-center gap-1.5">
              <AlertTriangle size={14} className="text-red-500" />
              <span className="text-sm font-bold text-red-700">{criticalCount} Critical</span>
            </div>
          )}
          <div className="card px-3 py-2 flex items-center gap-2">
            <Users size={15} className="text-gray-400" />
            <div>
              <div className="text-[10px] text-gray-400 font-semibold uppercase">Active Cases</div>
              <div className="text-sm font-bold text-gray-900 leading-none">{ambulances.length}</div>
            </div>
          </div>
          <div className={`px-3 py-2 rounded-xl border flex items-center gap-2 ${
            wsConnected
              ? 'bg-emerald-50 border-emerald-200'
              : 'bg-gray-100 border-gray-200'
          }`}>
            <Radio size={15} className={wsConnected ? 'text-emerald-500 animate-pulse' : 'text-gray-400'} />
            <div>
              <div className="text-[10px] text-gray-400 font-semibold uppercase">Network</div>
              <div className={`text-sm font-bold leading-none ${wsConnected ? 'text-emerald-700' : 'text-gray-500'}`}>
                {wsConnected ? 'Live' : 'Offline'}
              </div>
            </div>
          </div>
          <button
            onClick={() => setShowMap(v => !v)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
              showMap ? 'bg-rose-50 border-rose-200 text-rose-700' : 'btn-secondary'
            }`}
          >
            <MapIcon size={15} />
            {showMap ? 'Hide Map' : 'Show Map'}
          </button>
        </div>
      </div>

      {/* Command Map */}
      {showMap && (
        <div className="card-lg overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
              <MapIcon size={15} className="text-rose-500" />
              Command Map
              <span className="text-xs font-normal text-gray-400">
                — {ambulances.length} unit{ambulances.length !== 1 ? 's' : ''} tracked
              </span>
            </div>
            {selectedAmbulance && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-rose-600 font-medium bg-rose-50 border border-rose-100 px-2 py-1 rounded">
                  Tracking {selectedAmbulance.unitName}
                </span>
                <button
                  onClick={() => setSelectedAmbulanceId(null)}
                  className="p-1 text-gray-400 hover:text-gray-600 rounded"
                >
                  <X size={13} />
                </button>
              </div>
            )}
          </div>
          <MedopsMap
            style={{ height: 320 }}
            ambulances={ambulances}
            hospitals={hospitals}
            selectedAmbulance={selectedAmbulance}
            showRoute={!!selectedAmbulance}
            showLegend
            connectionStatus={wsConnected ? 'connected' : 'disconnected'}
            isDemo={isDemoMode}
            onMarkerClick={({ type, data }) => {
              if (type === 'ambulance') setSelectedAmbulanceId(data.id);
            }}
          />
        </div>
      )}

      {/* Queue */}
      <div className="card-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50">
          <h2 className="text-sm font-semibold text-gray-700">Incoming Queue</h2>
        </div>

        {!hasLiveData ? (
          /* Empty state */
          <div className="py-16 flex flex-col items-center text-center">
            <div className="w-14 h-14 bg-gray-100 rounded-full flex items-center justify-center mb-4">
              <Activity size={26} className="text-gray-300" />
            </div>
            <p className="font-semibold text-gray-500 mb-1">No active cases</p>
            <p className="text-sm text-gray-400 max-w-xs">
              {isDemoMode
                ? 'Demo ambulance data will appear here when the ambulance view is open.'
                : 'Incoming ambulances will appear here when they connect to the WebSocket.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/50">
                  {['Case / Unit', 'Status & ETA', 'Priority', 'Location', 'Action'].map(h => (
                    <th key={h} className="px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {ambulances.map(amb => (
                  <tr
                    key={amb.id}
                    onClick={() => setSelectedAmbulanceId(amb.id === selectedAmbulanceId ? null : amb.id)}
                    className={`hover:bg-gray-50 transition-colors cursor-pointer ${
                      selectedAmbulanceId === amb.id ? 'bg-rose-50/40' : ''
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="font-semibold text-gray-900 flex items-center gap-2">
                        {amb.unitName}
                        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      </div>
                      <div className="text-xs text-gray-400 font-mono mt-0.5">{amb.caseId}</div>
                      {amb.isDemo && (
                        <div className="text-[10px] text-amber-600 mt-0.5">⚠ Demo position</div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <Clock size={13} className="text-blue-500" />
                        <span className="text-sm font-semibold text-gray-800">{amb.status}</span>
                      </div>
                      {amb.eta !== null && (
                        <div className="text-xs text-gray-500 font-mono">
                          ETA {amb.eta} min · {amb.distanceKm?.toFixed(1) ?? '—'} km
                        </div>
                      )}
                      {amb.lastUpdated && (
                        <div className="text-[10px] text-gray-400 mt-0.5">Updated {amb.lastUpdated}</div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <PriorityBadge priority={amb.priority} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {amb.lat !== null && amb.lng !== null
                        ? <span className="font-mono text-xs">{amb.lat?.toFixed(4)}, {amb.lng?.toFixed(4)}</span>
                        : <span className="text-gray-400 italic text-xs">Location unavailable</span>
                      }
                    </td>
                    <td className="px-4 py-3">
                      <button
                        className="btn-secondary flex items-center gap-1 text-xs px-3 py-1.5"
                        onClick={e => { e.stopPropagation(); setSelectedAmbulanceId(amb.id); }}
                      >
                        <Stethoscope size={13} /> Review
                        <ChevronRight size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function PriorityBadge({ priority }) {
  if (!priority || priority === 'PENDING') return <span className="badge-pending">{priority ?? 'Pending'}</span>;
  if (priority === 'CRITICAL' || priority === 'ESI-1') return <span className="badge-critical">{priority}</span>;
  if (priority === 'HIGH' || priority === 'ESI-2') return <span className="badge-warning">{priority}</span>;
  return <span className="badge-normal">{priority}</span>;
}
