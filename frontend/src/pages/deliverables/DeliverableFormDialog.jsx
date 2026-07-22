import { useState } from 'react';
import { MenuItem } from '@mui/material';
import { FormDialog } from '../../components/form/FormDialog';
import { FormField } from '../../components/common/FormField';
import { createDeliverable, updateDeliverable, DELIVERABLE_STATUSES } from '../../api/deliverables';
import { useToast } from '../../components/common/Toast';

const STATUS_LABELS = { not_started: 'Not started', in_progress: 'In progress', blocked: 'Blocked', completed: 'Completed' };

export function DeliverableFormDialog({ open, deliverable, projects, defaultProjectId, onClose, onSaved }) {
  const editing = Boolean(deliverable);
  const toast = useToast();
  const [form, setForm] = useState({
    project_id: deliverable?.project_id ?? defaultProjectId ?? '',
    name: deliverable?.name ?? '',
    description: deliverable?.description ?? '',
    status: deliverable?.status ?? 'not_started',
    completion_pct: deliverable?.completion_pct ?? 0,
    due_date: deliverable?.due_date ?? '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const valid = form.name.trim() && form.project_id !== '';

  async function submit() {
    setError(''); setBusy(true);
    const payload = {
      project_id: Number(form.project_id),
      name: form.name.trim(),
      description: form.description || null,
      status: form.status,
      completion_pct: form.completion_pct === '' ? null : Number(form.completion_pct),
      due_date: form.due_date || null,
    };
    try {
      if (editing) await updateDeliverable(deliverable.id, payload);
      else await createDeliverable(payload);
      toast.success(editing ? 'Deliverable updated' : 'Deliverable created');
      onSaved();
    } catch (err) {
      setError(err?.details?.length ? err.details.join(' ') : err?.message || 'Could not save deliverable.');
    } finally { setBusy(false); }
  }

  return (
    <FormDialog open={open} title={editing ? 'Edit deliverable' : 'New deliverable'} onClose={onClose}
      onSubmit={submit} busy={busy} error={error}
      submitLabel={editing ? 'Save changes' : 'Create deliverable'} submitDisabled={!valid}>
      <FormField id="d-project" label="Project" select value={form.project_id} onChange={set('project_id')}>
        <MenuItem value=""><em>Select a project…</em></MenuItem>
        {projects.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
      </FormField>
      <FormField id="d-name" label="Name" value={form.name} onChange={set('name')} autoFocus placeholder="Deliverable name" />
      <FormField id="d-desc" label="Description" value={form.description} onChange={set('description')} multiline minRows={2} placeholder="Short description" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
        <FormField id="d-status" label="Status" select value={form.status} onChange={set('status')}>
          {DELIVERABLE_STATUSES.map((s) => <MenuItem key={s} value={s}>{STATUS_LABELS[s]}</MenuItem>)}
        </FormField>
        <FormField id="d-pct" label="Completion %" type="number" value={form.completion_pct} onChange={set('completion_pct')}
          inputProps={{ min: 0, max: 100 }} />
        <FormField id="d-due" label="Due date" type="date" value={form.due_date} onChange={set('due_date')} />
      </div>
    </FormDialog>
  );
}
