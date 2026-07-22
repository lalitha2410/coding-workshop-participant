/**
 * Full-screen status pages: 403 (not permitted) and 404 (not found).
 */

import { Link as RouterLink } from 'react-router-dom';
import { Box, Typography, Button } from '@mui/material';
import BlockIcon from '@mui/icons-material/LockOutlined';
import SearchOffIcon from '@mui/icons-material/SearchOffRounded';

function StatusScreen({ icon: Icon, code, title, message }) {
  return (
    <Box sx={{ minHeight: '60vh', display: 'grid', placeItems: 'center', px: 3, textAlign: 'center' }}>
      <Box sx={{ maxWidth: 420 }}>
        <Box
          sx={{
            width: 56, height: 56, borderRadius: 3, mx: 'auto', mb: 2.5,
            display: 'grid', placeItems: 'center', bgcolor: 'action.selected', color: 'primary.main',
          }}
        >
          <Icon />
        </Box>
        <Typography className="mono" sx={{ fontSize: '0.75rem', fontWeight: 700, color: 'text.disabled', letterSpacing: '0.1em', mb: 1 }}>
          {code}
        </Typography>
        <Typography variant="h2" sx={{ mb: 1 }}>{title}</Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>{message}</Typography>
        <Button component={RouterLink} to="/" variant="contained">Back to dashboard</Button>
      </Box>
    </Box>
  );
}

export function NotPermittedPage() {
  return (
    <StatusScreen
      icon={BlockIcon}
      code="403 · FORBIDDEN"
      title="You don't have access to this"
      message="Your role doesn't permit this action. If you think this is a mistake, ask an ACME admin to adjust your access."
    />
  );
}

export function NotFoundPage() {
  return (
    <StatusScreen
      icon={SearchOffIcon}
      code="404 · NOT FOUND"
      title="This page doesn't exist"
      message="The page you're looking for may have moved or never existed."
    />
  );
}
