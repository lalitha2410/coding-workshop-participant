/**
 * Reusable "Export CSV" button. Fetches the rows to export (via `fetchRows`,
 * which the caller wires to the current filters), converts them with the shared
 * CSV utility, and triggers a download. Shows a loading state and a toast.
 *
 * Export is a read action, so this is available to all authenticated roles.
 */

import { useState } from 'react';
import { Button, CircularProgress } from '@mui/material';
import DownloadIcon from '@mui/icons-material/FileDownloadOutlined';
import { toCsv, downloadCsv, csvFilename } from '../../utils/csv';
import { useToast } from '../common/Toast';

export function ExportButton({ filenamePrefix, columns, fetchRows, label = 'Export CSV', size }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      const rows = await fetchRows();
      if (!rows || rows.length === 0) {
        toast.info('Nothing to export for the current filters.');
        return;
      }
      downloadCsv(csvFilename(filenamePrefix), toCsv(rows, columns));
      toast.success(`Exported ${rows.length} row${rows.length === 1 ? '' : 's'}.`);
    } catch (err) {
      toast.error(err?.message || 'Export failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button
      variant="outlined"
      size={size}
      onClick={run}
      disabled={busy}
      startIcon={busy ? <CircularProgress size={16} thickness={5} /> : <DownloadIcon />}
    >
      {busy ? 'Exporting…' : label}
    </Button>
  );
}
