import { useState } from 'react';
import { FormDialog } from '../../components/form/FormDialog';
import { FormField } from '../../components/common/FormField';
import { createResource, updateResource } from '../../api/resources';
import { useToast } from '../../components/common/Toast';
import { entityMsg, describeUpdate } from '../../utils/messages';

const UPDATE_CONFIG = {
  entity: 'resource', possessive: 'their', nameKey: 'name',
  fields: [
    { key: 'email', label: 'email' },
    { key: 'title', label: 'title' },
  ],
};

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function ResourceFormDialog({ open, resource, onClose, onSaved }) {
  const editing = Boolean(resource);
  const toast = useToast();
  const [form, setForm] = useState({
    name: resource?.name ?? '', email: resource?.email ?? '', title: resource?.title ?? '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const emailBad = form.email.length > 0 && !EMAIL_RE.test(form.email);
  const valid = form.name.trim() && EMAIL_RE.test(form.email);

  async function submit() {
    setError(''); setBusy(true);
    const payload = { name: form.name.trim(), email: form.email.trim(), title: form.title || null };
    try {
      if (editing) {
        const desc = describeUpdate(resource, payload, UPDATE_CONFIG);
        if (desc.changed) await updateResource(resource.id, payload);
        (desc.changed ? toast.success : toast.info)(desc.message);
      } else {
        await createResource(payload);
        toast.success(entityMsg('Resource', payload.name, 'created'));
      }
      onSaved();
    } catch (err) {
      setError(err?.details?.length ? err.details.join(' ') : err?.message || 'Could not save resource.');
    } finally { setBusy(false); }
  }

  return (
    <FormDialog open={open} title={editing ? 'Edit resource' : 'New resource'} onClose={onClose}
      onSubmit={submit} busy={busy} error={error}
      submitLabel={editing ? 'Save changes' : 'Create resource'} submitDisabled={!valid}>
      <FormField id="r-name" label="Name" value={form.name} onChange={set('name')} autoFocus placeholder="Full name" />
      <FormField id="r-email" label="Email" type="email" value={form.email} onChange={set('email')}
        placeholder="name@acme.test" error={emailBad} helperText={emailBad ? 'Enter a valid email address.' : ' '} />
      <FormField id="r-title" label="Title" value={form.title} onChange={set('title')} placeholder="e.g. Staff Engineer" />
    </FormDialog>
  );
}
