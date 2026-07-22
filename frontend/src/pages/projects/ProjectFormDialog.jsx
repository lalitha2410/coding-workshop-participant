import { useState } from 'react';
import { MenuItem } from '@mui/material';
import { FormDialog } from '../../components/form/FormDialog';
import { FormField } from '../../components/common/FormField';
import { createProject, updateProject, PROJECT_STATUSES, DEPARTMENTS } from '../../api/projects';
import { useToast } from '../../components/common/Toast';

const STATUS_LABELS = {
  planning: 'Planning', active: 'Active', on_hold: 'On hold', completed: 'Completed', cancelled: 'Cancelled',
};

function toForm(p) {
  return {
    name: p?.name ?? '',
    department: p?.department ?? '',
    status: p?.status ?? 'planning',
    description: p?.description ?? '',
    start_date: p?.start_date ?? '',
    end_date: p?.end_date ?? '',
    deadline: p?.deadline ?? '',
    budget_planned: p?.budget_planned ?? '',
    budget_consumed: p?.budget_consumed ?? '',
  };
}

export function ProjectFormDialog({ open, project, onClose, onSaved }) {
  const editing = Boolean(project);
  const toast = useToast();
  const [form, setForm] = useState(toForm(project));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit() {
    setError('');
    setBusy(true);
    // Only send fields with values; numbers as numbers, blanks omitted.
    const payload = {
      name: form.name.trim(),
      department: form.department || null,
      status: form.status,
      description: form.description || null,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
      deadline: form.deadline || null,
      budget_planned: form.budget_planned === '' ? null : Number(form.budget_planned),
      budget_consumed: form.budget_consumed === '' ? null : Number(form.budget_consumed),
    };
    try {
      if (editing) await updateProject(project.id, payload);
      else await createProject(payload);
      toast.success(editing ? 'Project updated' : 'Project created');
      onSaved();
    } catch (err) {
      setError(err?.details?.length ? err.details.join(' ') : err?.message || 'Could not save project.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <FormDialog
      open={open}
      title={editing ? 'Edit project' : 'New project'}
      onClose={onClose}
      onSubmit={submit}
      busy={busy}
      error={error}
      submitLabel={editing ? 'Save changes' : 'Create project'}
      submitDisabled={!form.name.trim()}
    >
      <FormField id="p-name" label="Name" value={form.name} onChange={set('name')} autoFocus placeholder="Project name" />
      <FormField id="p-dept" label="Department" select value={form.department} onChange={set('department')}>
        <MenuItem value=""><em>None</em></MenuItem>
        {DEPARTMENTS.map((d) => <MenuItem key={d} value={d}>{d}</MenuItem>)}
      </FormField>
      <FormField id="p-status" label="Status" select value={form.status} onChange={set('status')}>
        {PROJECT_STATUSES.map((s) => <MenuItem key={s} value={s}>{STATUS_LABELS[s]}</MenuItem>)}
      </FormField>
      <FormField id="p-desc" label="Description" value={form.description} onChange={set('description')} multiline minRows={2} placeholder="Short description" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
        <FormField id="p-start" label="Start" type="date" value={form.start_date} onChange={set('start_date')} />
        <FormField id="p-end" label="End" type="date" value={form.end_date} onChange={set('end_date')} />
        <FormField id="p-deadline" label="Deadline" type="date" value={form.deadline} onChange={set('deadline')} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <FormField id="p-bp" label="Budget planned" type="number" value={form.budget_planned} onChange={set('budget_planned')} placeholder="0" />
        <FormField id="p-bc" label="Budget consumed" type="number" value={form.budget_consumed} onChange={set('budget_consumed')} placeholder="0" />
      </div>
    </FormDialog>
  );
}
