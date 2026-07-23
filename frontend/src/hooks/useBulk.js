/**
 * Drives a bulk action: runs the loop, tracks progress, toasts the outcome, and
 * surfaces a result dialog when some items fail. Keeps the per-page wiring thin.
 */

import { useCallback, useState } from 'react';
import { runBulk, bulkSummaryText } from '../utils/bulk';
import { useToast } from '../components/common/Toast';

export function useBulk({ onSettled } = {}) {
  const toast = useToast();
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [result, setResult] = useState(null); // { ...summary, singular, verbPast } | null

  const run = useCallback(async (items, op, { singular, verbPast }) => {
    if (!items.length) return null;
    setRunning(true);
    setProgress({ done: 0, total: items.length });

    const summary = await runBulk(items, op, {
      onProgress: (done, total) => setProgress({ done, total }),
    });

    setRunning(false);
    const message = bulkSummaryText(summary, singular, verbPast);
    if (summary.ok) toast.success(message);
    else toast.error(message);

    // Only keep a result to display when there's detail worth showing (failures).
    setResult(summary.ok ? null : { ...summary, singular, verbPast });

    if (onSettled) onSettled(summary);
    return summary;
  }, [onSettled, toast]);

  return { running, progress, result, run, clearResult: () => setResult(null) };
}
