/**
 * Contextual bar shown above a list table when one or more rows are selected.
 * Renders the selection count + caller-supplied action buttons + "Clear", and
 * switches to a determinate progress bar (disabling everything) while a bulk
 * action runs.
 */

import { Box, Typography, Button, LinearProgress } from '@mui/material';

export function BulkActionBar({ count, running, progress, onClear, children }) {
  const pct = progress?.total ? Math.round((progress.done / progress.total) * 100) : 0;

  return (
    <Box
      sx={{
        mb: 2, borderRadius: 2, overflow: 'hidden',
        border: '1px solid', borderColor: 'primary.main',
        bgcolor: 'action.selected',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 2, py: 1.25, flexWrap: 'wrap' }}>
        <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, color: 'primary.main' }}>
          {running
            ? `Working… ${progress.done} of ${progress.total}`
            : `${count} selected`}
        </Typography>
        <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          {children}
          {/* Quiet, non-destructive: plain muted text so it can't be mistaken
              for the error-coloured Delete action sitting beside it. */}
          <Button
            size="small" variant="text" color="inherit"
            onClick={onClear} disabled={running}
            sx={{ color: 'text.secondary', fontWeight: 500 }}
          >
            Deselect all
          </Button>
        </Box>
      </Box>
      {running && <LinearProgress variant="determinate" value={pct} sx={{ height: 3 }} />}
    </Box>
  );
}
