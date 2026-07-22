/**
 * KPI stat card: overline label, a large tabular (mono) figure, and an optional
 * signed delta. Part of the "instrument" language — numbers align, color = meaning.
 */

import { Card, CardContent, Box, Typography } from '@mui/material';
import ArrowUpIcon from '@mui/icons-material/ArrowDropUpRounded';
import ArrowDownIcon from '@mui/icons-material/ArrowDropDownRounded';
import { fontFamily } from '../../theme/tokens';

export function StatCard({ label, value, unit, delta, deltaTone = 'neutral', icon: Icon, caption }) {
  const positive = deltaTone === 'up';
  const negative = deltaTone === 'down';
  const deltaColor = positive ? 'success.dark' : negative ? 'error.dark' : 'text.disabled';

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="overline">{label}</Typography>
          {Icon && <Icon sx={{ fontSize: 18, color: 'text.disabled' }} />}
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.75 }}>
          <Typography
            sx={{ fontFamily: fontFamily.mono, fontSize: '1.9rem', fontWeight: 600, letterSpacing: '-0.02em', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}
          >
            {value}
          </Typography>
          {unit && <Typography sx={{ color: 'text.disabled', fontWeight: 600, fontSize: '0.9rem' }}>{unit}</Typography>}
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minHeight: 20 }}>
          {delta != null && (
            <Box sx={{ display: 'flex', alignItems: 'center', color: deltaColor, fontWeight: 700, fontSize: '0.75rem' }}>
              {positive && <ArrowUpIcon sx={{ fontSize: 18, ml: -0.5 }} />}
              {negative && <ArrowDownIcon sx={{ fontSize: 18, ml: -0.5 }} />}
              {delta}
            </Box>
          )}
          {caption && <Typography variant="caption" sx={{ color: 'text.disabled' }}>{caption}</Typography>}
        </Box>
      </CardContent>
    </Card>
  );
}
