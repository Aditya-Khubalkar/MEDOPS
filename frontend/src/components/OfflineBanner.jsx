import { AlertTriangle } from 'lucide-react';

export default function OfflineBanner() {
  return (
    <div className="bg-amber-500/10 border-b border-amber-500/20 text-amber-800 dark:text-amber-200 py-2 px-4 flex justify-center items-center gap-2 text-sm font-medium animate-in slide-in-from-top-2 duration-300">
      <AlertTriangle size={16} />
      <span>Running on Local Edge AI (Quantized Model) — Cloud Sync Paused</span>
    </div>
  );
}
