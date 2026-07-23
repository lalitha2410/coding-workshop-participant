/**
 * LoadBalance brandmark: a slate-blue tile with an abstract arc + node, paired
 * with the wordmark. `compact` renders the mark only (collapsed rail / mobile).
 */

import { Box, Typography } from '@mui/material';

export function LogoMark({ size = 30 }) {
  return (
    <Box
      component="svg"
      viewBox="0 0 32 32"
      sx={{ width: size, height: size, flexShrink: 0, display: 'block' }}
      aria-hidden
    >
      <defs>
        <linearGradient id="mrd-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#4A66D6" />
          <stop offset="1" stopColor="#2A44A6" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="32" height="32" rx="8" fill="url(#mrd-g)" />
      <ellipse cx="16" cy="16" rx="6.2" ry="10" fill="none" stroke="rgba(255,255,255,0.9)" strokeWidth="1.6" />
      <line x1="16" y1="5" x2="16" y2="27" stroke="rgba(255,255,255,0.55)" strokeWidth="1.6" />
      <circle cx="16" cy="11.3" r="2.2" fill="#F0C368" />
    </Box>
  );
}

export function Logo({ compact = false, size = 30 }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
      <LogoMark size={size} />
      {!compact && (
        <Box sx={{ lineHeight: 1, minWidth: 0 }}>
          <Typography sx={{ fontWeight: 700, fontSize: '1rem', letterSpacing: '-0.02em', color: 'text.primary' }}>
            LoadBalance
          </Typography>
          <Typography sx={{ fontSize: '0.625rem', fontWeight: 600, letterSpacing: '0.14em', color: 'text.disabled', textTransform: 'uppercase' }}>
            ACME
          </Typography>
        </Box>
      )}
    </Box>
  );
}
