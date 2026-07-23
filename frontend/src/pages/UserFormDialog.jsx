/**
 * Create / edit a user (Admin). Create: username, email, password, role (all
 * four selectable). Edit: username + email only (password and role are separate
 * concerns). Client-side validation, with backend 400s (duplicate, etc.) shown
 * inline.
 */

import { useState } from 'react';
import { MenuItem } from '@mui/material';
import { FormDialog } from '../components/form/FormDialog';
import { FormField } from '../components/common/FormField';
import { createUser, updateUser, ROLE_OPTIONS } from '../api/users';
import { useToast } from '../components/common/Toast';
import { entityMsg, describeUpdate } from '../utils/messages';

const UPDATE_CONFIG = {
  entity: 'user', possessive: 'their', nameKey: 'username',
  fields: [{ key: 'email', label: 'email' }],
};

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function UserFormDialog({ open, user, onClose, onSaved }) {
  const editing = Boolean(user);
  const toast = useToast();
  const [form, setForm] = useState({
    username: user?.username ?? '',
    email: user?.email ?? '',
    password: '',
    role: user?.role ?? 'Viewer',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const emailBad = form.email.length > 0 && !EMAIL_RE.test(form.email);
  const pwBad = !editing && form.password.length > 0 && (form.password.length < 8 || form.password.length > 72);
  const valid =
    form.username.trim() &&
    EMAIL_RE.test(form.email) &&
    (editing || (form.password.length >= 8 && form.password.length <= 72));

  async function submit() {
    setError('');
    setBusy(true);
    try {
      if (editing) {
        const changes = { username: form.username.trim(), email: form.email.trim() };
        const desc = describeUpdate(user, changes, UPDATE_CONFIG);
        if (desc.changed) await updateUser(user.id, changes);
        (desc.changed ? toast.success : toast.info)(desc.message);
      } else {
        await createUser({
          username: form.username.trim(),
          email: form.email.trim(),
          password: form.password,
          role: form.role,
        });
        toast.success(entityMsg('User', form.username.trim(), 'created'));
      }
      onSaved();
    } catch (err) {
      setError(err?.details?.length ? err.details.join(' ') : err?.message || 'Could not save user.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <FormDialog
      open={open}
      title={editing ? 'Edit user' : 'New user'}
      onClose={onClose}
      onSubmit={submit}
      busy={busy}
      error={error}
      submitLabel={editing ? 'Save changes' : 'Create user'}
      submitDisabled={!valid}
    >
      <FormField id="u-username" label="Username" value={form.username} onChange={set('username')} autoFocus placeholder="jordan.lee" autoComplete="off" />
      <FormField id="u-email" label="Email" type="email" value={form.email} onChange={set('email')} placeholder="jordan@acme.test"
        error={emailBad} helperText={emailBad ? 'Enter a valid email address.' : ' '} autoComplete="off" />
      {!editing && (
        <>
          <FormField id="u-password" label="Password" type="password" value={form.password} onChange={set('password')}
            placeholder="At least 8 characters" error={pwBad} helperText={pwBad ? 'Must be 8–72 characters.' : ' '} autoComplete="new-password" />
          <FormField id="u-role" label="Role" select value={form.role} onChange={set('role')}>
            {ROLE_OPTIONS.map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
          </FormField>
        </>
      )}
    </FormDialog>
  );
}
