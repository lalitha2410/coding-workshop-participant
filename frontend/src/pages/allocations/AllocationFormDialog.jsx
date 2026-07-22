import { useState } from 'react';
import { MenuItem } from '@mui/material';
import { FormDialog } from '../../components/form/FormDialog';
import { FormField } from '../../components/common/FormField';
import { createAllocation, updateAllocation } from '../../api/allocations';
import { useToast } from '../../components/common/Toast';

export function AllocationFormDialog({ open, allocation, resources, projects, onClose, onSaved }) {
  const editing = Boolean(allocation);
  const toast = useToast();
  const [form, setForm] = useState({
    resource_id: allocation?.resource_id ?? '',
    project_id: allocation?.project_id ?? '',
    allocation_pct: allocation?.allocation_pct ?? 0,
    start_date: allocation?.start_date ?? '',
    end_date: allocation?.end_date ?? '',
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const valid = form.resource_id !== '' && form.project_id !== '';

  async function submit() {
    setError(''); setBusy(true);
    const payload = {
      resource_id: Number(form.resource_id),
      project_id: Number(form.project_id),
      allocation_pct: form.allocation_pct === '' ? null : Number(form.allocation_pct),
      start_date: form.start_date || null,
      end_date: form.end_date || null,
    };
    try {
      if (editing) await updateAllocation(allocation.id, payload);
      else await createAllocation(payload);
      toast.success(editing ? 'Allocation updated' : 'Allocation created');
      onSaved();
    } catch (err) {
      setError(err?.details?.length ? err.details.join(' ') : err?.message || 'Could not save allocation.');
    } finally { setBusy(false); }
  }

  return (
    <FormDialog open={open} title={editing ? 'Edit allocation' : 'New allocation'} onClose={onClose}
      onSubmit={submit} busy={busy} error={error}
      submitLabel={editing ? 'Save changes' : 'Create allocation'} submitDisabled={!valid}>
      <FormField id="a-resource" label="Resource" select value={form.resource_id} onChange={set('resource_id')}>
        <MenuItem value=""><em>Select a resource…</em></MenuItem>
        {resources.map((r) => <MenuItem key={r.id} value={r.id}>{r.name}</MenuItem>)}
      </FormField>
      <FormField id="a-project" label="Project" select value={form.project_id} onChange={set('project_id')}>
        <MenuItem value=""><em>Select a project…</em></MenuItem>
        {projects.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
      </FormField>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
        <FormField id="a-pct" label="Allocation %" type="number" value={form.allocation_pct} onChange={set('allocation_pct')}
          inputProps={{ min: 0, max: 100 }} />
        <FormField id="a-start" label="Start" type="date" value={form.start_date} onChange={set('start_date')} />
        <FormField id="a-end" label="End" type="date" value={form.end_date} onChange={set('end_date')} />
      </div>
    </FormDialog>
  );
}
