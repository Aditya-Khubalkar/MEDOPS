import React, { useState, useEffect, useRef } from 'react';
import {
  Ambulance, HeartPulse, Activity, Send, Clock,
  AlertTriangle, MapPin, WifiOff, Navigation2
} from 'lucide-react';
import MedopsMap from '../components/MedopsMap';
import { useAmbulanceLocations } from '../context/AmbulanceLocationContext';

const BACKEND_WS = import.meta.env.VITE_BACKEND_WS || 'ws://localhost:8000';

export default function EMSView() {
  const { ambulances, hospitals, updateAmbulancePosition, isDemoMode } = useAmbulanceLocations();

  // For this view we track a single active ambulance session.
  // In a real deployment the unit ID would come from auth/config.
  const [unitId] = useState(() => `AMB-${Date.now().toString(36).toUpperCase()}`);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const [vitals, setVitals] = useState({ hr: null, o2: null, bp: null });
  const [notes, setNotes] = useState('');
  const [messages, setMessages] = useState([]);
  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);

  // Use the first matching ambulance from context (demo) or null
  const ambulance = ambulances[0] ?? null;
  const eta = ambulance?.eta ?? null;
  const distanceKm = ambulance?.distanceKm ?? null;

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // WebSocket connection
  useEffect(() => {
    let ws;
    let reconnectTimer;

    const connect = () => {
      setWsStatus('connecting');
      try {
        ws = new WebSocket(`${BACKEND_WS}/ws/ambulance/${unitId}`);
        wsRef.current = ws;

        ws.onopen = () => {
          setWsStatus('connected');
          setMessages(prev => [...prev, {
            id: Date.now(), from: 'System',
            text: `Unit ${unitId} connected to hospital command.`,
            time: new Date().toLocaleTimeString(),
          }]);
        };

        ws.onclose = () => {
          setWsStatus('disconnected');
          // Reconnect after 5 s
          reconnectTimer = setTimeout(connect, 5000);
        };

        ws.onerror = () => {
          setWsStatus('disconnected');
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'LOCATION_ACK') {
              // Backend confirmed location update
            } else if (msg.type === 'HOSPITAL_MESSAGE') {
              setMessages(prev => [...prev, {
                id: Date.now(), from: 'Hospital',
                text: msg.content,
                time: new Date().toLocaleTimeString(),
              }]);
            }
          } catch (_) {}
        };
      } catch (_) {
        setWsStatus('disconnected');
        reconnectTimer = setTimeout(connect, 5000);
      }
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      try { ws?.close(); } catch (_) {}
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unitId]);

  const sendMessage = () => {
    if (!notes.trim()) return;
    const msg = { id: Date.now(), from: 'EMS', text: notes, time: new Date().toLocaleTimeString() };
    setMessages(prev => [...prev, msg]);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'NOTES', content: notes, timestamp: new Date().toISOString(),
      }));
    }
    setNotes('');
  };

  const wsStatusLabel = wsStatus === 'connected'
    ? 'Connected to hospital'
    : wsStatus === 'connecting'
    ? 'Connecting…'
    : 'Offline — reconnecting';

  const wsStatusClass = wsStatus === 'connected'
    ? 'status-dot-online'
    : wsStatus === 'connecting'
    ? 'status-dot-connecting'
    : 'status-dot-offline';

  return (
    <div className="flex flex-col gap-5">

      {/* Header */}
      <div className="card-lg p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-rose-100 rounded-xl flex items-center justify-center flex-shrink-0">
            <Ambulance size={22} className="text-rose-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              Ambulance View
              {isDemoMode && (
                <span className="text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200 px-2 py-0.5 rounded">
                  Demo Mode
                </span>
              )}
            </h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`${wsStatusClass} flex-shrink-0`} />
              <span className="text-xs text-gray-500">{wsStatusLabel}</span>
              <span className="text-gray-300 mx-1">·</span>
              <span className="text-xs text-gray-400 font-mono">{unitId}</span>
            </div>
          </div>
        </div>

        {/* ETA / Distance */}
        <div className="flex items-center gap-3">
          {eta !== null ? (
            <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-2 rounded-xl flex items-center gap-2">
              <Clock size={16} />
              <div>
                <div className="text-[10px] font-bold uppercase text-red-500">ETA</div>
                <div className="text-base font-bold leading-none">{eta} min</div>
              </div>
            </div>
          ) : (
            <div className="bg-gray-100 border border-gray-200 text-gray-500 px-4 py-2 rounded-xl flex items-center gap-2 text-sm">
              <MapPin size={15} /> No destination set
            </div>
          )}
          {distanceKm !== null && (
            <div className="bg-blue-50 border border-blue-200 text-blue-800 px-3 py-2 rounded-xl flex items-center gap-1.5 text-sm">
              <Navigation2 size={14} />
              <span className="font-semibold">{distanceKm.toFixed(1)} km</span>
            </div>
          )}
        </div>
      </div>

      {/* Demo mode notice */}
      {isDemoMode && ambulance?.isDemo && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 flex items-start gap-2 text-sm">
          <AlertTriangle size={16} className="text-amber-500 flex-shrink-0 mt-0.5" />
          <p className="text-amber-800">
            <strong>Demo mode active.</strong> Ambulance position and route are simulated.
            To disable, set <code className="bg-amber-100 px-1 rounded">VITE_DEMO_MODE=false</code> in your environment.
          </p>
        </div>
      )}

      {/* Vitals Row — only shown when connected or in demo mode */}
      {(wsStatus === 'connected' || isDemoMode) && (
        <div className="grid grid-cols-3 gap-4">
          <VitalCard
            label="Heart Rate"
            value={vitals.hr}
            unit="bpm"
            icon={<HeartPulse size={16} className="text-rose-500" />}
            warn={vitals.hr !== null && (vitals.hr > 130 || vitals.hr < 50)}
          />
          <VitalCard
            label="SpO₂"
            value={vitals.o2}
            unit="%"
            icon={<Activity size={16} className="text-blue-500" />}
            warn={vitals.o2 !== null && vitals.o2 < 92}
          />
          <VitalCard
            label="Blood Pressure"
            value={vitals.bp}
            unit=""
            icon={<Activity size={16} className="text-emerald-500" />}
          />
        </div>
      )}

      {/* Map + Comms */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Map */}
        <div className="lg:col-span-2 card-lg overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
              <MapPin size={15} className="text-rose-500" />
              Ambulance Route
            </div>
            {ambulance?.lastUpdated && (
              <span className="text-xs text-gray-400">Updated {ambulance.lastUpdated}</span>
            )}
          </div>
          <MedopsMap
            style={{ height: 340 }}
            ambulances={ambulance ? [ambulance] : []}
            hospitals={hospitals}
            selectedAmbulance={ambulance}
            showRoute
            showLegend
            connectionStatus={wsStatus}
            isDemo={isDemoMode}
          />
        </div>

        {/* Comms */}
        <div className="card-lg flex flex-col" style={{ maxHeight: 460 }}>
          <div className="px-4 py-3 border-b border-gray-100 flex-shrink-0">
            <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <AlertTriangle size={15} className="text-amber-500" />
              Pre-Arrival Comms
            </h3>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-gray-50/50">
            {messages.length === 0 && (
              <div className="flex items-center justify-center h-20 text-xs text-gray-400 text-center">
                {wsStatus === 'connected' ? 'No messages yet.' : 'Connect to send messages.'}
              </div>
            )}
            {messages.map(msg => (
              <div key={msg.id} className={`flex flex-col ${msg.from === 'EMS' ? 'items-end' : 'items-start'}`}>
                <span className="text-[10px] text-gray-400 font-medium mb-0.5 px-1">
                  {msg.from} · {msg.time}
                </span>
                <div className={`px-3 py-2 rounded-xl text-sm max-w-[85%] leading-snug ${
                  msg.from === 'EMS'
                    ? 'bg-rose-600 text-white rounded-tr-sm'
                    : msg.from === 'System'
                    ? 'bg-gray-200 text-gray-600 text-xs italic rounded-tl-sm'
                    : 'bg-white border border-gray-200 text-gray-800 rounded-tl-sm'
                }`}>
                  {msg.text}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          <div className="p-3 border-t border-gray-100 flex-shrink-0">
            <div className="relative">
              <textarea
                value={notes}
                onChange={e => setNotes(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
                rows={2}
                placeholder={wsStatus === 'connected' ? 'Message hospital team…' : 'Connect to send messages'}
                disabled={wsStatus !== 'connected'}
                className="input-field pr-10 resize-none text-sm"
              />
              <button
                onClick={sendMessage}
                disabled={!notes.trim() || wsStatus !== 'connected'}
                className="absolute right-2 bottom-2 p-1.5 bg-rose-600 hover:bg-rose-700 disabled:bg-gray-200 disabled:text-gray-400 text-white rounded-lg transition-colors"
              >
                <Send size={14} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Disconnected state */}
      {wsStatus === 'disconnected' && !isDemoMode && ambulances.length === 0 && (
        <div className="card-lg p-8 flex flex-col items-center text-center">
          <WifiOff size={36} className="text-gray-300 mb-3" />
          <p className="font-semibold text-gray-500 mb-1">Not connected to backend</p>
          <p className="text-sm text-gray-400">
            The WebSocket connection to the hospital server could not be established.
            Make sure the backend is running and try again.
          </p>
        </div>
      )}
    </div>
  );
}

function VitalCard({ label, value, unit, icon, warn }) {
  return (
    <div className={`card-lg p-4 ${warn ? 'border-red-300 bg-red-50' : ''}`}>
      <div className="flex items-center gap-1.5 text-gray-500 text-xs font-medium mb-2">
        {icon} {label}
        {warn && <span className="ml-auto text-[10px] font-bold text-red-500 bg-red-100 border border-red-200 px-1.5 rounded">ALERT</span>}
      </div>
      {value !== null && value !== undefined ? (
        <div className={`text-3xl font-bold tabular-nums ${warn ? 'text-red-700' : 'text-gray-900'}`}>
          {value}
          {unit && <span className="text-base font-normal text-gray-400 ml-1">{unit}</span>}
        </div>
      ) : (
        <div className="text-sm text-gray-400 italic">Not available</div>
      )}
    </div>
  );
}
