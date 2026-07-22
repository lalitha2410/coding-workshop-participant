/** Reusable create/edit dialog: title, form fields (children), error alert, actions. */

import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Alert, Box, IconButton } from '@mui/material';
import CloseIcon from '@mui/icons-material/CloseRounded';

export function FormDialog({ open, title, onClose, onSubmit, busy = false, error, submitLabel = 'Save', submitDisabled = false, children }) {
  return (
    <Dialog open={open} onClose={busy ? undefined : onClose} maxWidth="sm" fullWidth
      slotProps={{ paper: { sx: { borderRadius: 3 } } }}>
      <Box component="form" onSubmit={(e) => { e.preventDefault(); onSubmit(); }} noValidate>
        <DialogTitle sx={{ fontWeight: 700, pr: 6 }}>
          {title}
          <IconButton onClick={onClose} disabled={busy} sx={{ position: 'absolute', right: 12, top: 12 }} aria-label="Close">
            <CloseIcon sx={{ fontSize: 20 }} />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.25, pt: 0.5 }}>
            {children}
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button onClick={onClose} disabled={busy} color="inherit">Cancel</Button>
          <Button type="submit" variant="contained" disabled={busy || submitDisabled}>
            {busy ? 'Saving…' : submitLabel}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
