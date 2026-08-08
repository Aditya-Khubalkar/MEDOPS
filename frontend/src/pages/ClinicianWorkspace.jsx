import React, { useState } from 'react';
import {
  UserCheck, FileText, AlertTriangle, CheckCircle2, Clock,
  Activity, Fingerprint, ExternalLink, Map as MapIcon
} from 'lucide-react';
import MedopsMap from '../components/MedopsMap';
import { useAmbulanceLocations } from '../context/AmbulanceLocationContext';

/**
 * ClinicianWorkspace
 *
 * Displays cases that have completed the PatientIntake → Triage pipeline.
 * In production, this list would be populated from the backend database.
 * Right now there is no persistence layer wired up to this view, so it
 * shows an empty state when there are no cases to review.
 *
 * The case list is populated in sessionStorage by PatientIntake on success
 * so that a completed triage flows through to this page within a session.
 */

export default function ClinicianWorkspace() {
  const { ambulances, hospitals, isDemoMode } = useAmbulanceLocations();

  // Load any cases stored in session by PatientIntake
  const [sessionCases] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('medops_pending_cases') || '[]');
    } catch {
      return [];
    }
  });

  const [selectedIdx, setSelectedIdx] = useState(sessionCases.length > 0 ? 0 : null);
  const [notes, setNotes] = useState('');
  const [showCaseMap, setShowCaseMap] = useState(true);
  const [actionTaken, setActionTaken] = useState(null); // null | 'approved' | 'overridden'

  const active = selectedIdx !== null ? sessionCases[selectedIdx] : null;

  // Try to link the active case to a live ambulance from context
  const liveAmbulance = active?.ambulanceId
    ? ambulances.find(a => a.id === active.ambulanceId || a.caseId === active.ambulanceId)
    : null;

  // Map data for this case
  const caseAmbulances = liveAmbulance ? [liveAmbulance] : [];

  const handleApprove = () => setActionTaken('approved');
  const handleOverride = () => setActionTaken('overridden');

  if (sessionCases.length === 0) {
    return (
      <div className="max-w-2xl mx-auto py-2">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <UserCheck size={24} className="text-rose-500" />
            Clinician Review
          </h1>
          <p className="text-sm text-gray-500 mt-1 ml-9">
            Review triage assessments before clinical action.
          </p>
        </div>
        <div className="card-lg py-16 flex flex-col items-center text-center">
          <div className="w-14 h-14 bg-gray-100 rounded-full flex items-center justify-center mb-4">
            <CheckCircle2 size={26} className="text-gray-300" />
          </div>
          <p className="font-semibold text-gray-500 mb-2">No cases pending review</p>
          <p className="text-sm text-gray-400 max-w-sm">
            Cases appear here after a patient intake is processed. Go to{' '}
            <a href="/" className="text-rose-600 hover:underline">Patient Intake</a>{' '}
            to create a new case.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] -m-4 md:-m-6 lg:-m-8">

      {/* Case List Sidebar */}
      <div className="w-72 bg-white border-r border-gray-200 flex flex-col hidden md:flex flex-shrink-0">
        <div className="px-4 py-3 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800 text-sm flex items-center gap-2">
            <Clock size={15} className="text-rose-500" />
            Pending Review ({sessionCases.length})
          </h2>
        </div>
        <div className="flex-1 overflow-y-auto">
          {sessionCases.map((c, idx) => (
            <button
              key={idx}
              onClick={() => { setSelectedIdx(idx); setActionTaken(null); }}
              className={`w-full text-left px-4 py-3 border-b border-gray-50 transition-colors ${
                selectedIdx === idx
                  ? 'bg-rose-50 border-l-4 border-l-rose-500'
                  : 'hover:bg-gray-50 border-l-4 border-l-transparent'
              }`}
            >
              <div className="flex items-center justify-between mb-0.5">
                <span className="font-semibold text-gray-900 text-sm truncate">
                  {c.caseNumber || `Case ${idx + 1}`}
                </span>
                {c.priority && <PriorityBadge priority={c.priority} />}
              </div>
              {c.patient && (
                <p className="text-xs text-gray-500 truncate">{c.patient}</p>
              )}
              <p className="text-[10px] text-gray-400 mt-1">{c.time || 'Just now'}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Main Workspace */}
      <div className="flex-1 bg-gray-50 overflow-y-auto">
        {active ? (
          <div className="p-6 md:p-8 max-w-3xl mx-auto space-y-5">

            {/* Header */}
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div>
                <div className="flex items-center gap-2.5 mb-1 flex-wrap">
                  <h1 className="text-xl font-bold text-gray-900">
                    {active.caseNumber || `Case ${selectedIdx + 1}`}
                  </h1>
                  {active.priority && <PriorityBadge priority={active.priority} />}
                  {liveAmbulance && (
                    <span className="text-xs bg-blue-50 border border-blue-200 text-blue-700 px-2 py-0.5 rounded-full flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                      En Route
                    </span>
                  )}
                </div>
                {active.patient && (
                  <p className="text-sm text-gray-500 flex items-center gap-1.5">
                    <UserCheck size={14} /> {active.patient}
                  </p>
                )}
              </div>
              <div className="text-right text-xs text-gray-400">
                {new Date().toLocaleDateString()}
              </div>
            </div>

            {/* Action taken banner */}
            {actionTaken && (
              <div className={`rounded-xl px-4 py-3 flex items-center gap-2 text-sm font-medium ${
                actionTaken === 'approved'
                  ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
                  : 'bg-amber-50 border border-amber-200 text-amber-800'
              }`}>
                <CheckCircle2 size={16} />
                {actionTaken === 'approved'
                  ? `Triage priority ${active.priority || ''} approved.`
                  : 'Triage overridden — manual assessment required.'}
                {' '}This action would be recorded in a production system.
              </div>
            )}

            {/* Live ETA bar */}
            {liveAmbulance && (
              <div className="card p-3 flex items-center justify-between gap-3 bg-blue-50 border-blue-200">
                <div className="flex items-center gap-3">
                  <span className="text-xl">🚑</span>
                  <div>
                    <div className="font-semibold text-blue-900 text-sm">{liveAmbulance.unitName} — En Route</div>
                    <div className="text-xs text-blue-700 mt-0.5">
                      ETA <strong>{liveAmbulance.eta ?? '—'} min</strong>
                      {liveAmbulance.distanceKm !== null && ` · ${liveAmbulance.distanceKm.toFixed(1)} km`}
                      {liveAmbulance.isDemo && ' · Demo position'}
                    </div>
                  </div>
                </div>
                <div className="text-xs text-blue-500">{liveAmbulance.lastUpdated}</div>
              </div>
            )}

            {/* Vitals */}
            {active.vitals && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {Object.entries(active.vitals).map(([k, v]) => (
                  <div key={k} className="card p-3">
                    <div className="text-[10px] text-gray-400 uppercase font-semibold mb-1">{k}</div>
                    <div className="text-lg font-bold text-gray-900">
                      {v ?? <span className="text-gray-400 font-normal text-sm">N/A</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Case Map */}
            {(liveAmbulance || (isDemoMode && ambulances.length > 0)) && (
              <div className="card-lg overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                  <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
                    <MapIcon size={14} className="text-rose-500" /> Case Location Map
                  </div>
                  <button
                    onClick={() => setShowCaseMap(v => !v)}
                    className="text-xs text-rose-500 hover:text-rose-700 font-medium"
                  >
                    {showCaseMap ? 'Hide' : 'Show'}
                  </button>
                </div>
                {showCaseMap && (
                  <MedopsMap
                    style={{ height: 240 }}
                    ambulances={caseAmbulances.length ? caseAmbulances : ambulances.slice(0, 1)}
                    hospitals={hospitals}
                    selectedAmbulance={liveAmbulance || ambulances[0]}
                    showRoute
                    showLegend={false}
                    connectionStatus="connected"
                    isDemo={isDemoMode}
                  />
                )}
              </div>
            )}

            {/* Two-column layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

              {/* Clinical content */}
              <div className="lg:col-span-2 space-y-4">
                {active.intake && (
                  <div className="card p-5">
                    <h3 className="section-label mb-2 flex items-center gap-1.5">
                      <FileText size={13} /> Patient Complaint
                    </h3>
                    <p className="text-sm text-gray-700 leading-relaxed">"{active.intake}"</p>
                  </div>
                )}

                {active.audit_report && (
                  <div className="card p-5">
                    <div className="flex items-start justify-between mb-2 gap-2">
                      <h3 className="section-label flex items-center gap-1.5">
                        <Activity size={13} /> Triage Assessment Report
                      </h3>
                      {active.trace_id && (
                        <span className="text-[10px] text-gray-400 font-mono bg-gray-100 px-2 py-0.5 rounded flex items-center gap-1 flex-shrink-0">
                          <Fingerprint size={10} /> {active.trace_id.slice(0, 12)}
                        </span>
                      )}
                    </div>
                    <div className="bg-gray-50 border border-gray-100 rounded-lg p-4 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap max-h-72 overflow-y-auto">
                      {active.audit_report}
                    </div>
                  </div>
                )}

                {!active.intake && !active.audit_report && (
                  <div className="card p-5 text-sm text-gray-400 italic">
                    No clinical details available for this case.
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="space-y-4">
                {active.redFlags && active.redFlags.length > 0 && (
                  <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                    <h3 className="text-xs font-bold text-red-700 uppercase tracking-wider mb-3 flex items-center gap-1.5">
                      <AlertTriangle size={13} /> Red Flags
                    </h3>
                    <ul className="space-y-1.5">
                      {active.redFlags.map((flag, i) => (
                        <li key={i} className="text-sm text-red-700 flex items-start gap-1.5">
                          <span className="mt-1 text-red-400">•</span> {flag}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="card p-4 space-y-3">
                  <h3 className="text-sm font-semibold text-gray-900">Clinical Action</h3>
                  {!actionTaken ? (
                    <>
                      <button
                        onClick={handleApprove}
                        className="w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 px-4 rounded-lg transition-colors text-sm"
                      >
                        <CheckCircle2 size={16} />
                        Approve {active.priority || 'Triage'}
                      </button>
                      <button
                        onClick={handleOverride}
                        className="btn-secondary w-full flex items-center justify-center gap-2"
                      >
                        <UserCheck size={16} />
                        Override Triage
                      </button>
                    </>
                  ) : (
                    <div className="text-sm text-gray-500 text-center py-2">
                      Action recorded.
                    </div>
                  )}
                  <div>
                    <label className="section-label block mb-2">Clinical Notes</label>
                    <textarea
                      value={notes}
                      onChange={e => setNotes(e.target.value)}
                      rows={4}
                      placeholder="Add clinical notes, override reasoning, or additional observations…"
                      className="input-field resize-none text-sm"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center p-8">
            <CheckCircle2 size={40} className="text-gray-200 mb-3" />
            <p className="text-gray-500 font-medium">Select a case to begin review</p>
          </div>
        )}
      </div>
    </div>
  );
}

function PriorityBadge({ priority }) {
  if (!priority) return null;
  const p = priority.toUpperCase();
  if (p.includes('1') || p === 'CRITICAL') return <span className="badge-critical">{priority}</span>;
  if (p.includes('2') || p === 'HIGH')     return <span className="badge-warning">{priority}</span>;
  if (p.includes('3') || p.includes('4') || p.includes('5')) return <span className="badge-normal">{priority}</span>;
  return <span className="badge-pending">{priority}</span>;
}
