/**
 * The signature over-allocation motif: a horizontal capacity bar that fills
 * toward 100% and visibly *breaks* into an amber/rose "over" zone beyond it.
 * Reused across the dashboard, resource list, and resource detail.
 */

import { Box, Typography } from '@mui/material';
import { fontFamily } from '../../theme/tokens';

export function CapacityMeter({ name, pct, subtitle }) {
  const over = pct > 100;
  const filled = Math.min(pct, 100);
  const overflow = over ? Math.min(pct - 100, 60) : 0; // cap the visual overflow

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
      <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 1 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }} noWrap>{name}</Typography>
          {subtitle && <Typography variant="caption" sx={{ color: 'text.disabled' }} noWrap>{subtitle}</Typography>}
        </Box>
        <Typography
          sx={{
            fontFamily: fontFamily.mono, fontSize: '0.8125rem', fontWeight: 700,
            fontVariantNumeric: 'tabular-nums',
            color: over ? 'error.dark' : 'text.secondary',
          }}
        >
          {pct}%
        </Typography>
      </Box>

      <Box sx={{ position: 'relative', display: 'flex', height: 8, borderRadius: 999, bgcolor: 'action.hover', overflow: 'hidden' }}>
        <Box
          sx={{
            width: `${filled}%`,
            bgcolor: over ? 'warning.main' : 'primary.main',
            transition: 'width 400ms cubic-bezier(0.2,0,0,1)',
          }}
        />
        {over && (
          <Box
            sx={{
              width: `${overflow}%`,
              bgcolor: 'error.main',
              transition: 'width 400ms cubic-bezier(0.2,0,0,1)',
            }}
          />
        )}
        {/* 100% reference tick */}
        <Box sx={{ position: 'absolute', top: -1, bottom: -1, left: `${over ? (100 / (100 + overflow)) * 100 : 100}%`, width: '2px', bgcolor: 'background.paper', opacity: over ? 0.9 : 0 }} />
      </Box>
    </Box>
  );
}
