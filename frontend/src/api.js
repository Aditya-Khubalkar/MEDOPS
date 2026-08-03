/**
 * api.js — Shared API helpers
 * 
 * These functions are used by components that call the MEDOPS backend.
 * All URLs respect the VITE_BACKEND_URL environment variable.
 */

const BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

/**
 * Upload a report file for decoding.
 * @param {File} file
 * @param {string} language
 */
export const uploadReport = async (file, language = 'English') => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('language', language);

  const res = await fetch(`${BASE}/api/decode-report`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text().catch(() => `HTTP ${res.status}`);
    throw new Error(text);
  }

  return res.json();
};

/**
 * Speech synthesis helpers — wrapped here so components don't
 * need to reference the Web Speech API directly.
 */
const LANGUAGE_MAP = {
  Hindi:   'hi-IN',
  Tamil:   'ta-IN',
  Telugu:  'te-IN',
  Marathi: 'mr-IN',
  English: 'en-IN',
};

export const speakSummary = (text, language, onEnd) => {
  if (!('speechSynthesis' in window)) {
    if (onEnd) setTimeout(onEnd, 500);
    return;
  }
  window.speechSynthesis.cancel();
  const utt = new SpeechSynthesisUtterance(text);
  utt.lang = LANGUAGE_MAP[language] || 'en-IN';
  if (onEnd) { utt.onend = onEnd; utt.onerror = onEnd; }
  window.speechSynthesis.speak(utt);
};

export const cancelSpeech = () => {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel();
};
