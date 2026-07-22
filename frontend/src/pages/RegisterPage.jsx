import { useState } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import { Box, Typography, Button, Alert, Link } from '@mui/material';
import AuthLayout from './auth/AuthLayout';
import { FormField } from '../components/common/FormField';
import { LogoMark } from '../components/common/Logo';
import { useAuth } from '../auth/AuthContext';
import { hasBackendConfig } from '../config/endpoints';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const pwTooShort = form.password.length > 0 && form.password.length < 8;
  const emailBad = form.email.length > 0 && !EMAIL_RE.test(form.email);
  const valid = form.username.trim() && EMAIL_RE.test(form.email) && form.password.length >= 8;

  async function onSubmit(e) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await register({ username: form.username.trim(), email: form.email.trim(), password: form.password });
      navigate('/', { replace: true });
    } catch (err) {
      setError(err?.message || 'Could not create your account.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <Box component="form" onSubmit={onSubmit} noValidate>
        <Box sx={{ display: { xs: 'flex', md: 'none' }, mb: 3 }}><LogoMark size={34} /></Box>

        <Typography variant="h1" sx={{ fontSize: '1.5rem', mb: 0.5 }}>Create your account</Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3.5 }}>
          You'll start with <strong>Viewer</strong> access — an admin can elevate your role.
        </Typography>

        {!hasBackendConfig() && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            No backend URLs configured. Run <code>bin/generate-env.sh</code> after deploying.
          </Alert>
        )}
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.25 }}>
          <FormField id="username" label="Username" autoComplete="username" autoFocus
            placeholder="jordan.lee" value={form.username} onChange={set('username')} />
          <FormField id="email" label="Email" type="email" autoComplete="email"
            placeholder="jordan@acme.com" value={form.email} onChange={set('email')}
            error={emailBad} helperText={emailBad ? 'Enter a valid email address.' : ' '} />
          <FormField id="password" label="Password" type="password" autoComplete="new-password"
            placeholder="At least 8 characters" value={form.password} onChange={set('password')}
            error={pwTooShort} helperText={pwTooShort ? 'Must be at least 8 characters.' : ' '} />
        </Box>

        <Button type="submit" variant="contained" size="large" fullWidth disabled={busy || !valid} sx={{ mt: 1 }}>
          {busy ? 'Creating account…' : 'Create account'}
        </Button>

        <Typography variant="body2" sx={{ color: 'text.secondary', mt: 3, textAlign: 'center' }}>
          Already have an account?{' '}
          <Link component={RouterLink} to="/login" sx={{ fontWeight: 600 }}>Sign in</Link>
        </Typography>
      </Box>
    </AuthLayout>
  );
}
