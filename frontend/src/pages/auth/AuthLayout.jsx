/**
 * Split-screen auth layout — the premium first impression.
 * Left: slate-blue brand panel (desktop only) with the product promise and the
 * signature capacity-meter motif. Right: the form card, with a theme toggle.
 */

import { Box, Typography, IconButton, Tooltip } from '@mui/material';
import LightModeIcon from '@mui/icons-material/LightModeOutlined';
import DarkModeIcon from '@mui/icons-material/DarkModeOutlined';
import { LogoMark } from '../../components/common/Logo';
import { useColorMode } from '../../theme/ColorModeContext';

function BrandMeter({ label, pct, over }) {
  const filled = Math.min(pct, 100);
  const overflow = over ? Math.min(pct - 100, 50) : 0;
  return (
    <Box sx={{ mb: 1.75 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography sx={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.75)' }}>{label}</Typography>
        <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: over ? '#F6C77A' : 'rgba(255,255,255,0.9)', fontFamily: 'JetBrains Mono Variable, monospace' }}>
          {pct}%
        </Typography>
      </Box>
      <Box sx={{ display: 'flex', height: 6, borderRadius: 999, bgcolor: 'rgba(255,255,255,0.16)', overflow: 'hidden' }}>
        <Box sx={{ width: `${filled}%`, bgcolor: over ? '#F0C368' : 'rgba(255,255,255,0.9)' }} />
        {over && <Box sx={{ width: `${overflow}%`, bgcolor: '#E5686C' }} />}
      </Box>
    </Box>
  );
}

export default function AuthLayout({ children }) {
  const { mode, toggle } = useColorMode();

  return (
    <Box sx={{ minHeight: '100dvh', display: 'flex', bgcolor: 'background.default' }}>
      {/* Brand panel (desktop) */}
      <Box
        sx={{
          display: { xs: 'none', md: 'flex' },
          flexDirection: 'column', justifyContent: 'space-between',
          width: '46%', maxWidth: 620, p: 6, color: '#fff',
          position: 'relative', overflow: 'hidden',
          background: 'linear-gradient(150deg, #3554C7 0%, #2A44A6 55%, #223787 100%)',
        }}
      >
        <Box sx={{ position: 'absolute', inset: 0, background: 'radial-gradient(1100px 500px at 15% -10%, rgba(255,255,255,0.14), transparent 60%)' }} />
        <Box sx={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 1.25 }}>
          <LogoMark size={34} />
          <Box>
            <Typography sx={{ fontWeight: 700, fontSize: '1.05rem', letterSpacing: '-0.02em' }}>Meridian</Typography>
            <Typography sx={{ fontSize: '0.625rem', fontWeight: 600, letterSpacing: '0.16em', opacity: 0.7 }}>ACME</Typography>
          </Box>
        </Box>

        <Box sx={{ position: 'relative', maxWidth: 420 }}>
          <Typography sx={{ fontSize: '2rem', fontWeight: 700, lineHeight: 1.15, letterSpacing: '-0.025em', mb: 1.5 }}>
            See your whole portfolio at a glance.
          </Typography>
          <Typography sx={{ fontSize: '0.95rem', color: 'rgba(255,255,255,0.8)', mb: 4, lineHeight: 1.6 }}>
            Projects, deliverables, budgets, and people — in one calm operations desk.
            Spot over-allocation before it bites.
          </Typography>

          <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.14)', backdropFilter: 'blur(4px)' }}>
            <Typography sx={{ fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', opacity: 0.7, mb: 1.5 }}>
              Team capacity
            </Typography>
            <BrandMeter label="Priya · Design" pct={72} />
            <BrandMeter label="Marcus · Engineering" pct={128} over />
            <BrandMeter label="Ana · Delivery" pct={94} />
          </Box>
        </Box>

        <Typography sx={{ position: 'relative', fontSize: '0.75rem', opacity: 0.6 }}>
          © {new Date().getFullYear()} ACME · Meridian portfolio operations
        </Typography>
      </Box>

      {/* Form side */}
      <Box sx={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', p: { xs: 3, sm: 5 } }}>
        <Box sx={{ position: 'absolute', top: 16, right: 16 }}>
          <Tooltip title={mode === 'light' ? 'Switch to dark' : 'Switch to light'}>
            <IconButton onClick={toggle} aria-label="Toggle color mode">
              {mode === 'light' ? <DarkModeIcon sx={{ fontSize: 20 }} /> : <LightModeIcon sx={{ fontSize: 20 }} />}
            </IconButton>
          </Tooltip>
        </Box>
        <Box sx={{ width: '100%', maxWidth: 384 }}>{children}</Box>
      </Box>
    </Box>
  );
}
