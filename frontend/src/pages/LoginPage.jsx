import { useState } from 'react';
import { useNavigate, useLocation, Link as RouterLink } from 'react-router-dom';
import { Box, Typography, Button, Alert, Link, InputAdornment, IconButton } from '@mui/material';
import Visibility from '@mui/icons-material/VisibilityOutlined';
import VisibilityOff from '@mui/icons-material/VisibilityOffOutlined';
import AuthLayout from './auth/AuthLayout';
import { FormField } from '../components/common/FormField';
import { LogoMark } from '../components/common/Logo';
import { useAuth } from '../auth/AuthContext';
import { hasBackendConfig } from '../config/endpoints';

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const dest = location.state?.from?.pathname || '/';

  async function onSubmit(e) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(identifier.trim(), password);
      navigate(dest, { replace: true });
    } catch (err) {
      setError(err?.status === 401 ? 'Invalid credentials. Check your username/email and password.' : err?.message || 'Sign in failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <Box component="form" onSubmit={onSubmit} noValidate>
        <Box sx={{ display: { xs: 'flex', md: 'none' }, mb: 3 }}><LogoMark size={34} /></Box>

        <Typography variant="h1" sx={{ fontSize: '1.5rem', mb: 0.5 }}>Welcome back</Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3.5 }}>
          Sign in to your Meridian workspace.
        </Typography>

        {!hasBackendConfig() && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            No backend URLs configured. Run <code>bin/generate-env.sh</code> after deploying.
          </Alert>
        )}
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.25 }}>
          <FormField
            id="identifier" label="Username or email" autoComplete="username" autoFocus
            placeholder="you@acme.com" value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
          />
          <FormField
            id="password" label="Password" type={showPw ? 'text' : 'password'}
            autoComplete="current-password" placeholder="••••••••"
            value={password} onChange={(e) => setPassword(e.target.value)}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton onClick={() => setShowPw((s) => !s)} edge="end" size="small" aria-label="Toggle password visibility">
                    {showPw ? <VisibilityOff sx={{ fontSize: 18 }} /> : <Visibility sx={{ fontSize: 18 }} />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </Box>

        <Button type="submit" variant="contained" size="large" fullWidth disabled={busy || !identifier || !password} sx={{ mt: 3 }}>
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>

        <Typography variant="body2" sx={{ color: 'text.secondary', mt: 3, textAlign: 'center' }}>
          New to ACME?{' '}
          <Link component={RouterLink} to="/register" sx={{ fontWeight: 600 }}>Create an account</Link>
        </Typography>
      </Box>
    </AuthLayout>
  );
}
