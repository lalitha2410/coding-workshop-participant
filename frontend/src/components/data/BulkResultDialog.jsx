/**
 * Shown after a bulk action that had partial failures. States the outcome and
 * lists exactly which rows failed and why (e.g. "Not permitted", "Already gone",
 * or the backend's own message for an FK constraint).
 */

import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button,
  List, ListItem, ListItemText, Chip, Box,
} from '@mui/material';
import { bulkSummaryText } from '../../utils/bulk';

export function BulkResultDialog({ result, labelFor, onClose }) {
  const open = Boolean(result);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth
      slotProps={{ paper: { sx: { borderRadius: 3 } } }}>
      <DialogTitle sx={{ fontWeight: 700 }}>
        {result ? bulkSummaryText(result, result.singular, result.verbPast) : ''}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ fontSize: '0.8125rem', color: 'text.secondary', mb: 1 }}>
          These couldn’t be completed:
        </Box>
        <List dense disablePadding>
          {result?.failures.map((f, i) => (
            <ListItem
              key={i}
              disableGutters
              secondaryAction={
                <Chip
                  label={f.status ? `${f.message} (${f.status})` : f.message}
                  size="small" color="error" variant="outlined"
                  sx={{ height: 22, fontWeight: 600 }}
                />
              }
            >
              <ListItemText
                primary={labelFor(f.item)}
                primaryTypographyProps={{ sx: { fontSize: '0.8125rem', fontWeight: 600, pr: 1 } }}
              />
            </ListItem>
          ))}
        </List>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button onClick={onClose} variant="contained">Done</Button>
      </DialogActions>
    </Dialog>
  );
}
