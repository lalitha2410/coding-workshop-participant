/**
 * Status shown as a colored dot + label (the calm "status-as-dot" language),
 * covering both project and deliverable statuses. Reads status tokens from theme.
 */

import { Box, Typography } from '@mui/material';

const STATUS = {
  planning: { label: 'Planning', tone: 'neutral' },
  active: { label: 'Active', tone: 'success' },
  on_hold: { label: 'On hold', tone: 'warning' },
  completed: { label: 'Completed', tone: 'neutral' },
  cancelled: { label: 'Cancelled', tone: 'error' },
  not_started: { label: 'Not started', tone: 'neutral' },
  in_progress: { label: 'In progress', tone: 'info' },
  blocked: { label: 'Blocked', tone: 'error' },
};

const TONE_FG = { success: 'successFg', warning: 'warningFg', error: 'errorFg', info: 'infoFg', neutral: 'neutralFg' };
const TONE_BG = { success: 'successBg', warning: 'warningBg', error: 'errorBg', info: 'infoBg', neutral: 'neutralBg' };

export function StatusChip({ status, size = 'md' }) {
  const cfg = STATUS[status] || { label: status || '—', tone: 'neutral' };
  const fg = (t) => t.palette.meridian[TONE_FG[cfg.tone]];
  const bg = (t) => t.palette.meridian[TONE_BG[cfg.tone]];

  return (
    <Box
      sx={{
        display: 'inline-flex', alignItems: 'center', gap: 0.75,
        px: 1, py: size === 'sm' ? 0.15 : 0.35, borderRadius: 1.5,
        bgcolor: bg, whiteSpace: 'nowrap',
      }}
    >
      <Box sx={{ width: 6, height: 6, borderRadius: 999, bgcolor: fg, flexShrink: 0 }} />
      <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: fg }}>{cfg.label}</Typography>
    </Box>
  );
}

/** Small emphatic badge for the over-allocated / at-risk cases. */
export function RiskChip({ label = 'At risk' }) {
  return (
    <Box
      sx={{
        display: 'inline-flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.35, borderRadius: 1.5,
        bgcolor: (t) => t.palette.meridian.errorBg,
      }}
    >
      <Box sx={{ width: 6, height: 6, borderRadius: 999, bgcolor: (t) => t.palette.meridian.errorFg }} />
      <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: (t) => t.palette.meridian.errorFg }}>{label}</Typography>
    </Box>
  );
}
