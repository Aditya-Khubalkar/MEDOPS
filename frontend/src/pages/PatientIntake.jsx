import React, { useState, useEffect, useRef } from 'react';
import { Stethoscope, Send, Loader2, AlertCircle, CheckCircle2, RefreshCw, ArrowRight, FileText } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

const PROCESSING_STAGES = [
  'Parsing clinical notes',
  'Evaluating emergency indicators',
  'Calculating triage priority',
  'Generating assessment report',
];

export default function PatientIntake() {
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  const stageTimerRef = useRef(null);

  // Advance UI stage indicator while waiting (visual only — does not affect real processing)
  useEffect(() => {
    if (loading && stage < PROCESSING_STAGES.length - 1) {
      stageTimerRef.current = setTimeout(() => setStage(s => s + 1), 1800);
    }
    return () => clearTimeout(stageTimerRef.current);
  }, [loading, stage]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!input.trim()) return;

    setLoading(true);
    setError(null);
    setStage(0);
    setResult(null);

    try {
      const res = await fetch(`${BACKEND_URL}/api/triage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient_input: input.trim() }),
        signal: AbortSignal.timeout(120_000), // 2 min timeout (LLM can be slow)
      });

      if (!res.ok) {
        const text = await res.text().catch(() => `HTTP ${res.status}`);
        throw new Error(text || `Server returned ${res.status}`);
      }

      const data = await res.json();

      if (data.error) {
        throw new Error(data.error);
      }

      setStage(PROCESSING_STAGES.length - 1);
      setTimeout(() => {
        setLoading(false);
        setResult(data);
        // Store in session so ClinicianWorkspace can display this case
        try {
          const existing = JSON.parse(sessionStorage.getItem('medops_pending_cases') || '[]');
          const newCase = {
            caseNumber: `CASE-${Date.now().toString(36).toUpperCase()}`,
            intake: input.trim(),
            audit_report: data.audit_report,
            trace_id: data.trace_id,
            priority: data.actions?.esi_category || null,
            redFlags: data.actions?.red_flags || [],
            time: 'Just now',
            vitals: null,
          };
          sessionStorage.setItem('medops_pending_cases', JSON.stringify([newCase, ...existing].slice(0, 20)));
        } catch (_) {}
      }, 600);

    } catch (err) {
      setLoading(false);
      if (err.name === 'TimeoutError') {
        setError('The triage service took too long to respond. Please try again.');
      } else if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        setError('Cannot reach the backend server. Make sure the FastAPI server is running on port 8000.');
      } else {
        setError(err.message || 'An unexpected error occurred.');
      }
    }
  };

  const reset = () => {
    setResult(null);
    setInput('');
    setError(null);
  };

  return (
    <div className="max-w-2xl mx-auto py-2">

      {/* Page Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-9 h-9 bg-rose-100 rounded-lg flex items-center justify-center flex-shrink-0">
            <Stethoscope size={20} className="text-rose-600" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Patient Intake</h1>
        </div>
        <p className="text-gray-500 text-sm ml-12">
          Enter clinical observations or patient complaints to generate an initial triage assessment.
        </p>
      </div>

      {/* Error State */}
      {error && (
        <div className="mb-5 bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle size={18} className="text-red-500 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-red-800 text-sm mb-0.5">Triage Service Unavailable</p>
            <p className="text-red-700 text-sm">{error}</p>
            <button
              onClick={handleSubmit}
              className="mt-3 flex items-center gap-1.5 text-sm font-medium text-red-700 hover:text-red-800"
            >
              <RefreshCw size={14} /> Retry
            </button>
          </div>
        </div>
      )}

      {/* Input Form */}
      {!result && !loading && (
        <form onSubmit={handleSubmit} className="card-lg overflow-hidden">
          <div className="p-5">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Chief Complaint &amp; Clinical Notes
            </label>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              rows={7}
              placeholder="E.g., Patient is a 58yo female presenting with sudden onset substernal chest pressure (8/10), radiating to the left shoulder and jaw, onset 40 minutes ago. Associated diaphoresis and mild dyspnoea. History of hypertension and type 2 diabetes. No prior cardiac events."
              className="input-field resize-none"
              required
            />
          </div>
          <div className="bg-gray-50 border-t border-gray-100 px-5 py-3 flex justify-between items-center">
            <p className="text-xs text-gray-400 flex items-center gap-1.5">
              <FileText size={12} />
              Assessment must be reviewed by a licensed clinician before clinical action.
            </p>
            <button
              type="submit"
              disabled={!input.trim()}
              className="btn-primary flex items-center gap-2"
            >
              <span>Run Triage</span>
              <Send size={14} />
            </button>
          </div>
        </form>
      )}

      {/* Processing State */}
      {loading && (
        <div className="card-lg p-8 flex flex-col items-center justify-center min-h-[260px]">
          <Loader2 className="animate-spin text-rose-500 mb-6" size={36} />
          <div className="space-y-3 w-full max-w-xs">
            {PROCESSING_STAGES.map((text, idx) => (
              <div
                key={idx}
                className={`flex items-center gap-3 transition-opacity duration-500 ${stage >= idx ? 'opacity-100' : 'opacity-25'}`}
              >
                {stage > idx ? (
                  <CheckCircle2 size={18} className="text-emerald-500 flex-shrink-0" />
                ) : stage === idx ? (
                  <Loader2 size={18} className="animate-spin text-rose-500 flex-shrink-0" />
                ) : (
                  <div className="w-4.5 h-4.5 rounded-full border-2 border-gray-200 flex-shrink-0" />
                )}
                <span className={`text-sm ${stage >= idx ? 'text-gray-800 font-medium' : 'text-gray-400'}`}>
                  {text}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Result */}
      {result && !loading && (
        <div className="space-y-4">
          <div className="card-lg overflow-hidden">
            <div className="bg-emerald-50 border-b border-emerald-100 px-5 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2 text-emerald-800 font-semibold text-sm">
                <CheckCircle2 size={17} className="text-emerald-600" />
                Assessment Complete
              </div>
              {result.trace_id && (
                <span className="text-xs text-gray-500 font-mono">
                  Trace: {result.trace_id.slice(0, 12)}…
                </span>
              )}
            </div>

            <div className="p-5 space-y-5">
              {/* Original input */}
              <div>
                <p className="section-label mb-2">Clinical Notes Submitted</p>
                <div className="bg-gray-50 border border-gray-100 rounded-lg p-3 text-sm text-gray-700">
                  {input}
                </div>
              </div>

              {/* Report */}
              <div>
                <p className="section-label mb-2">Triage Assessment Report</p>
                {result.audit_report ? (
                  <div className="bg-white border border-gray-200 rounded-lg p-4 text-sm text-gray-800 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
                    {result.audit_report}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 italic">No structured report generated.</p>
                )}
              </div>
            </div>

            <div className="border-t border-gray-100 bg-gray-50 px-5 py-3 flex justify-between items-center">
              <p className="text-xs text-gray-400">
                This assessment is generated by an LLM and must be verified by a clinician.
              </p>
              <div className="flex gap-2">
                <button onClick={reset} className="btn-secondary">
                  New Patient
                </button>
                <button
                  onClick={() => navigate('/clinician')}
                  className="btn-primary flex items-center gap-1.5"
                >
                  Clinician Review
                  <ArrowRight size={14} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
