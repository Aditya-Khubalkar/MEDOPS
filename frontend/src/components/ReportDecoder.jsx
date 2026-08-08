import { useState, useRef } from 'react';
import {
  UploadCloud, FileText, Languages, Volume2, Loader2,
  CheckCircle2, AlertTriangle, FileImage, X, AlertCircle, RefreshCw
} from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

const SUPPORTED_LANGUAGES = ['English', 'Hindi', 'Tamil', 'Telugu', 'Marathi'];

export default function ReportDecoder() {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [language, setLanguage] = useState('English');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const fileInputRef = useRef(null);

  const ACCEPTED = '.pdf,.png,.jpg,.jpeg';
  const MAX_MB = 10;

  const handleDrag = (e) => {
    e.preventDefault(); e.stopPropagation();
    setIsDragging(e.type === 'dragenter' || e.type === 'dragover');
  };

  const acceptFile = (f) => {
    if (!f) return;
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(`File too large. Maximum size is ${MAX_MB} MB.`);
      return;
    }
    setFile(f);
    setResult(null);
    setError(null);
    stopSpeech();
  };

  const handleDrop = (e) => {
    e.preventDefault(); e.stopPropagation();
    setIsDragging(false);
    acceptFile(e.dataTransfer.files?.[0]);
  };

  const handleChange = (e) => {
    e.preventDefault();
    acceptFile(e.target.files?.[0]);
  };

  const analyzeReport = async () => {
    if (!file) return;
    setIsAnalyzing(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('language', language);

    try {
      const res = await fetch(`${BACKEND_URL}/api/decode-report`, {
        method: 'POST',
        body: formData,
        signal: AbortSignal.timeout(90_000),
      });

      if (!res.ok) {
        const text = await res.text().catch(() => `HTTP ${res.status}`);
        throw new Error(text || `Server returned ${res.status}`);
      }

      const data = await res.json();

      if (data.error) {
        throw new Error(data.error);
      }

      setResult(data);
    } catch (err) {
      if (err.name === 'TimeoutError') {
        setError('The analysis took too long. Please try again.');
      } else if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
        setError('Cannot reach the backend server. Make sure the FastAPI server is running.');
      } else {
        setError(err.message || 'An unexpected error occurred during analysis.');
      }
    } finally {
      setIsAnalyzing(false);
    }
  };

  const stopSpeech = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    setIsSpeaking(false);
  };

  const toggleSpeech = () => {
    if (!result?.translated_summary) return;
    if (isSpeaking) { stopSpeech(); return; }

    const langMap = { Hindi: 'hi-IN', Tamil: 'ta-IN', Telugu: 'te-IN', Marathi: 'mr-IN', English: 'en-IN' };
    const utterance = new SpeechSynthesisUtterance(result.translated_summary);
    utterance.lang = langMap[language] || 'en-IN';
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    window.speechSynthesis.speak(utterance);
    setIsSpeaking(true);
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    stopSpeech();
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="max-w-3xl mx-auto py-2 space-y-5">

      {/* Page Header */}
      <div className="mb-2">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
          <div className="w-9 h-9 bg-rose-100 rounded-lg flex items-center justify-center flex-shrink-0">
            <FileText size={20} className="text-rose-600" />
          </div>
          Report Decoder
        </h1>
        <p className="text-sm text-gray-500 mt-1 ml-12">
          Upload a lab report or prescription. The backend uses Gemini to extract metrics and explain
          them in plain language. Requires a valid{' '}
          <code className="bg-gray-100 px-1 rounded text-xs">GEMINI_API_KEY</code> in the backend environment.
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle size={17} className="text-red-500 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <p className="font-semibold text-red-800 text-sm mb-0.5">Analysis Failed</p>
            <p className="text-red-700 text-sm">{error}</p>
            <button
              onClick={analyzeReport}
              className="mt-2 flex items-center gap-1.5 text-sm font-medium text-red-700 hover:text-red-800"
            >
              <RefreshCw size={13} /> Retry
            </button>
          </div>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
            <X size={15} />
          </button>
        </div>
      )}

      {/* Upload Card */}
      <div className="card-lg overflow-hidden">

        {/* Drop Zone */}
        <div className="p-6 border-b border-gray-100">
          <div
            onDragEnter={handleDrag} onDragLeave={handleDrag}
            onDragOver={handleDrag} onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
              isDragging
                ? 'border-rose-400 bg-rose-50'
                : file
                ? 'border-emerald-400 bg-emerald-50/50'
                : 'border-gray-200 hover:border-rose-300 hover:bg-gray-50/50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleChange}
              accept={ACCEPTED}
              className="hidden"
            />

            {!file ? (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="flex flex-col items-center w-full cursor-pointer"
              >
                <div className="w-14 h-14 bg-rose-100 rounded-full flex items-center justify-center mb-3">
                  <UploadCloud size={26} className="text-rose-500" />
                </div>
                <p className="font-semibold text-gray-800 mb-1">Drop your report here</p>
                <p className="text-sm text-gray-400 mb-3">PDF, PNG, or JPEG — up to {MAX_MB} MB</p>
                <span className="btn-secondary text-sm">Browse Files</span>
              </button>
            ) : (
              <div className="flex flex-col items-center">
                <FileImage size={36} className="text-emerald-500 mb-2" />
                <p className="font-semibold text-gray-900 mb-1 text-sm break-all">{file.name}</p>
                <p className="text-xs text-gray-400 mb-3">
                  {(file.size / 1024).toFixed(1)} KB
                </p>
                <div className="flex items-center gap-3 flex-wrap justify-center">
                  {/* Language selector */}
                  <div className="relative">
                    <Languages size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                    <select
                      value={language}
                      onChange={e => setLanguage(e.target.value)}
                      className="input-field pl-8 pr-3 py-1.5 text-sm w-36"
                    >
                      {SUPPORTED_LANGUAGES.map(l => <option key={l}>{l}</option>)}
                    </select>
                  </div>
                  <button
                    onClick={reset}
                    className="btn-secondary text-sm py-1.5 px-3 flex items-center gap-1"
                  >
                    <X size={13} /> Remove
                  </button>
                  <button
                    onClick={analyzeReport}
                    disabled={isAnalyzing}
                    className="btn-primary flex items-center gap-2"
                  >
                    {isAnalyzing ? <Loader2 size={15} className="animate-spin" /> : <FileText size={15} />}
                    {isAnalyzing ? 'Analysing…' : 'Analyse Report'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Results */}
        {result && (
          <div className="p-6 space-y-5 bg-gray-50/50">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2 text-sm">
                <CheckCircle2 size={16} className="text-emerald-500" />
                Analysis Complete
              </h3>
              <div className="flex items-center gap-2">
                {'speechSynthesis' in window && result.translated_summary && (
                  <button
                    onClick={toggleSpeech}
                    className={`flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-lg border transition-colors ${
                      isSpeaking
                        ? 'bg-rose-50 border-rose-200 text-rose-700'
                        : 'btn-secondary'
                    }`}
                  >
                    <Volume2 size={15} className={isSpeaking ? 'animate-pulse' : ''} />
                    {isSpeaking ? 'Stop' : 'Read Aloud'}
                  </button>
                )}
                <button onClick={reset} className="btn-secondary text-sm py-1.5 px-3">
                  New Report
                </button>
              </div>
            </div>

            {/* Summary */}
            {result.translated_summary && (
              <div className="card p-4">
                <p className="section-label mb-2">Summary ({language})</p>
                <p className="text-sm text-gray-800 leading-relaxed">{result.translated_summary}</p>
              </div>
            )}

            {/* Findings */}
            {result.findings && result.findings.length > 0 && (
              <div>
                <p className="section-label mb-3">Extracted Findings</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {result.findings.map((f, i) => (
                    <div key={i} className="card p-4">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="font-semibold text-gray-900 text-sm">{f.metric}</div>
                        <StatusBadge status={f.status} />
                      </div>
                      {f.observed_value && (
                        <div className="text-xs text-gray-500 mb-1">
                          Value: <strong>{f.observed_value}</strong>
                          {f.reference_range && ` (ref: ${f.reference_range})`}
                        </div>
                      )}
                      {(f.plain_meaning || f.meaning) && (
                        <p className="text-xs text-gray-600 leading-relaxed">{f.plain_meaning || f.meaning}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Disclaimer */}
            {result.disclaimer && (
              <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl px-4 py-3">
                <AlertTriangle size={14} className="text-amber-500 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-amber-800">{result.disclaimer}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }) {
  if (!status) return null;
  const s = status.toLowerCase();
  if (s.includes('high') || s.includes('elevated') || s.includes('abnormal')) {
    return <span className="badge-critical">{status}</span>;
  }
  if (s.includes('low')) return <span className="badge-warning">{status}</span>;
  return <span className="badge-normal">{status}</span>;
}
