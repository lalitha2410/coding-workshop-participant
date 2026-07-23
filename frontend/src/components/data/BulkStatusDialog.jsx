/**
 * Confirmation dialog for a bulk STATUS CHANGE (Projects, Deliverables). Picks a
 * target status and confirms, naming how many rows will change.
 */

import { useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions,
  Button, TextField, MenuItem,
} from '@mui/material';
import { pluralize } from '../../utils/bulk';

export function BulkStatusDialog({ open, count, singular, statuses, busy, onConfirm, onClose }) {
  const [status, setStatus] = useState('');

  // Reset the picker each time the dialog opens.
  const reset = () => setStatus('');

  const chosen = statuses.find((s) => s.value === status);

  return (
    <Dialog
      open={open} onClose={busy ? undefined : onClose} maxWidth="xs" fullWidth
      slotProps={{ paper: { sx: { borderRadius: 3 } } }}
      TransitionProps={{ onEnter: reset }}
    >
      <DialogTitle sx={{ fontWeight: 700 }}>Change status</DialogTitle>
      <DialogContent>
        <DialogContentText sx={{ fontSize: '0.875rem', mb: 2 }}>
          {chosen
            ? `Set ${pluralize(count, singular)} to "${chosen.label}". Each selected ${singular} will be updated.`
            : `Choose a status for the ${pluralize(count, singular)} you selected.`}
        </DialogContentText>
        <TextField
          select fullWidth size="small" label="New status"
          value={status} onChange={(e) => setStatus(e.target.value)}
        >
          {statuses.map((s) => <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>)}
        </TextField>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button onClick={onClose} disabled={busy} color="inherit">Cancel</Button>
        <Button onClick={() => onConfirm(status)} disabled={busy || !status} variant="contained">
          {busy ? 'Working…' : 'Set status'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
