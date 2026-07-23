import { useCallback, useMemo, useState } from 'react';
import {
  Box, Card, Button, TextField, MenuItem, Table, TableHead, TableBody, TableRow, TableCell,
  IconButton, Tooltip, LinearProgress, Typography, Checkbox,
} from '@mui/material';
import AddIcon from '@mui/icons-material/AddRounded';
import EditIcon from '@mui/icons-material/EditOutlined';
import DeleteIcon from '@mui/icons-material/DeleteOutline';
import LabelIcon from '@mui/icons-material/LabelOutlined';
import DependenciesIcon from '@mui/icons-material/AccountTreeOutlined';
import { PageHeader } from '../../components/common/PageHeader';
import { DependenciesDialog } from './DependenciesDialog';
import { StatusChip } from '../../components/data/StatusChip';
import { ResultStates, TableSkeleton, EmptyState } from '../../components/data/ResultStates';
import { PaginationBar } from '../../components/data/PaginationBar';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { BulkActionBar } from '../../components/data/BulkActionBar';
import { BulkStatusDialog } from '../../components/data/BulkStatusDialog';
import { BulkResultDialog } from '../../components/data/BulkResultDialog';
import { DeliverableFormDialog } from './DeliverableFormDialog';
import { usePaginatedList } from '../../hooks/usePaginatedList';
import { useAsync } from '../../hooks/useAsync';
import { useBulk } from '../../hooks/useBulk';
import { useSelection } from '../../utils/selection';
import { pluralize } from '../../utils/bulk';
import { ExportButton } from '../../components/data/ExportButton';
import { fetchAllRows } from '../../api/fetchAll';
import { listDeliverables, deleteDeliverable, updateDeliverable, DELIVERABLE_STATUSES } from '../../api/deliverables';
import { listProjects } from '../../api/projects';
import { fmtDate } from '../../utils/format';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../auth/roles';
import { useToast } from '../../components/common/Toast';
import { entityMsg } from '../../utils/messages';

const STATUS_OPTIONS = DELIVERABLE_STATUSES.map((s) => ({ value: s, label: s.replace(/_/g, ' ') }));

export default function DeliverablesPage() {
  const { role } = useAuth();
  const toast = useToast();
  const list = usePaginatedList(listDeliverables, { limit: 10 });
  const { data: projectsData } = useAsync(() => listProjects({ limit: 200 }), []);
  const projects = projectsData?.items || [];
  const projectName = useMemo(() => Object.fromEntries(projects.map((p) => [p.id, p.name])), [projects]);

  const exportColumns = useMemo(() => [
    { header: 'ID', value: 'id' },
    { header: 'Project', value: (d) => projectName[d.project_id] || `#${d.project_id}` },
    { header: 'Name', value: 'name' },
    { header: 'Description', value: 'description' },
    { header: 'Status', value: 'status' },
    { header: 'Completion %', value: 'completion_pct' },
    { header: 'Due Date', value: 'due_date' },
  ], [projectName]);

  const [form, setForm] = useState({ open: false, deliverable: null });
  const [depsFor, setDepsFor] = useState(null);
  const [del, setDel] = useState({ open: false, deliverable: null, busy: false });

  const canCreate = can(role, 'create');
  const canUpdate = can(role, 'update');
  const canDelete = can(role, 'delete');
  const showSelection = canDelete || canUpdate;

  const resetKey = `${list.offset}|${JSON.stringify(list.filters)}`;
  const sel = useSelection(list.items, resetKey);
  const bulk = useBulk({ onSettled: () => { sel.clear(); list.refetch(); } });
  const [bulkDelete, setBulkDelete] = useState(false);
  const [bulkStatus, setBulkStatus] = useState(false);

  const onSaved = useCallback(() => { setForm({ open: false, deliverable: null }); list.refetch(); }, [list]);

  async function runBulkDelete() {
    setBulkDelete(false);
    await bulk.run(sel.selectedItems, (d) => deleteDeliverable(d.id), { singular: 'deliverable', verbPast: 'deleted' });
  }

  async function runBulkStatus(status) {
    setBulkStatus(false);
    await bulk.run(sel.selectedItems, (d) => updateDeliverable(d.id, { status }), { singular: 'deliverable', verbPast: 'updated' });
  }

  async function confirmDelete() {
    setDel((d) => ({ ...d, busy: true }));
    try {
      await deleteDeliverable(del.deliverable.id);
      toast.success(entityMsg('Deliverable', del.deliverable.name, 'deleted'));
      setDel({ open: false, deliverable: null, busy: false });
      list.refetch();
    } catch (err) {
      toast.error(err?.message || 'Could not delete deliverable.');
      setDel((d) => ({ ...d, busy: false }));
    }
  }

  return (
    <Box>
      <PageHeader
        title="Deliverables"
        subtitle="Milestones and their status across projects."
        actions={
          <>
            <ExportButton
              filenamePrefix="deliverables"
              columns={exportColumns}
              fetchRows={() => fetchAllRows(listDeliverables, { project_id: list.filters.project_id, status: list.filters.status })}
            />
            {canCreate && <Button variant="contained" startIcon={<AddIcon />} disabled={projects.length === 0} onClick={() => setForm({ open: true, deliverable: null })}>New deliverable</Button>}
          </>
        }
      />

      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <TextField select size="small" label="Project" value={list.filters.project_id || ''} sx={{ minWidth: 220 }}
          onChange={(e) => list.setFilters({ project_id: e.target.value })}>
          <MenuItem value="">All projects</MenuItem>
          {projects.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
        </TextField>
        <TextField select size="small" label="Status" value={list.filters.status || ''} sx={{ minWidth: 160 }}
          onChange={(e) => list.setFilters({ status: e.target.value })}>
          <MenuItem value="">All statuses</MenuItem>
          {DELIVERABLE_STATUSES.map((s) => <MenuItem key={s} value={s}>{s.replace('_', ' ')}</MenuItem>)}
        </TextField>
      </Box>

      {showSelection && sel.count > 0 && (
        <BulkActionBar count={sel.count} running={bulk.running} progress={bulk.progress} onClear={sel.clear}>
          {canUpdate && (
            <Button size="small" startIcon={<LabelIcon sx={{ fontSize: 16 }} />} disabled={bulk.running} onClick={() => setBulkStatus(true)}>
              Set status
            </Button>
          )}
          {canDelete && (
            <Button size="small" color="error" startIcon={<DeleteIcon sx={{ fontSize: 16 }} />} disabled={bulk.running} onClick={() => setBulkDelete(true)}>
              Delete
            </Button>
          )}
        </BulkActionBar>
      )}

      <Card>
        <ResultStates
          loading={list.loading}
          error={list.error}
          isEmpty={list.items.length === 0}
          onRetry={list.refetch}
          skeleton={<TableSkeleton rows={6} cols={5} />}
          empty={<EmptyState title="No deliverables found" message="Adjust filters, or add a deliverable to a project." action={canCreate && projects.length > 0 && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setForm({ open: true, deliverable: null })}>New deliverable</Button>} />}
        >
          <Table>
            <TableHead>
              <TableRow>
                {showSelection && (
                  <TableCell padding="checkbox">
                    <Checkbox size="small" checked={sel.allSelected} indeterminate={sel.someSelected} onChange={sel.toggleAll} inputProps={{ 'aria-label': 'Select all deliverables on this page' }} />
                  </TableCell>
                )}
                <TableCell>Deliverable</TableCell>
                <TableCell>Project</TableCell>
                <TableCell>Status</TableCell>
                <TableCell sx={{ minWidth: 160 }}>Completion</TableCell>
                <TableCell>Due</TableCell>
                <TableCell align="right" width={132}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {list.items.map((d) => (
                <TableRow key={d.id} hover selected={sel.isSelected(d.id)}>
                  {showSelection && (
                    <TableCell padding="checkbox">
                      <Checkbox size="small" checked={sel.isSelected(d.id)} onChange={() => sel.toggle(d.id)} inputProps={{ 'aria-label': `Select ${d.name}` }} />
                    </TableCell>
                  )}
                  <TableCell sx={{ fontWeight: 600 }}>{d.name}</TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>{projectName[d.project_id] || `#${d.project_id}`}</TableCell>
                  <TableCell><StatusChip status={d.status} /></TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <LinearProgress variant="determinate" value={Number(d.completion_pct) || 0}
                        color={d.status === 'blocked' ? 'error' : 'primary'}
                        sx={{ flex: 1, height: 5, borderRadius: 999, bgcolor: 'action.hover' }} />
                      <Typography className="mono" sx={{ fontSize: '0.75rem', fontWeight: 600, width: 34, textAlign: 'right' }}>{d.completion_pct}%</Typography>
                    </Box>
                  </TableCell>
                  <TableCell className="mono" sx={{ whiteSpace: 'nowrap' }}>{fmtDate(d.due_date)}</TableCell>
                  <TableCell align="right">
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.25 }}>
                      <Tooltip title="Dependencies"><IconButton size="small" onClick={() => setDepsFor(d)}><DependenciesIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
                      {canUpdate && <Tooltip title="Edit"><IconButton size="small" onClick={() => setForm({ open: true, deliverable: d })}><EditIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>}
                      {canDelete && <Tooltip title="Delete"><IconButton size="small" onClick={() => setDel({ open: true, deliverable: d, busy: false })}><DeleteIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>}
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <PaginationBar total={list.total} limit={list.limit} offset={list.offset} itemCount={list.items.length} onOffsetChange={list.setOffset} />
        </ResultStates>
      </Card>

      {form.open && (
        <DeliverableFormDialog open deliverable={form.deliverable} projects={projects}
          defaultProjectId={list.filters.project_id || ''}
          onClose={() => setForm({ open: false, deliverable: null })} onSaved={onSaved} />
      )}
      <ConfirmDialog
        open={del.open} title="Delete deliverable?"
        message={`"${del.deliverable?.name}" will be permanently removed.`}
        confirmLabel="Delete" destructive busy={del.busy}
        onConfirm={confirmDelete} onClose={() => setDel({ open: false, deliverable: null, busy: false })}
      />

      <ConfirmDialog
        open={bulkDelete}
        title="Delete deliverables?"
        message={`Delete ${pluralize(sel.count, 'deliverable')}? This can't be undone.`}
        confirmLabel="Delete"
        destructive
        onConfirm={runBulkDelete}
        onClose={() => setBulkDelete(false)}
      />
      <BulkStatusDialog
        open={bulkStatus}
        count={sel.count}
        singular="deliverable"
        statuses={STATUS_OPTIONS}
        onConfirm={runBulkStatus}
        onClose={() => setBulkStatus(false)}
      />
      <BulkResultDialog result={bulk.result} labelFor={(d) => d.name} onClose={bulk.clearResult} />

      {depsFor && (
        <DependenciesDialog open deliverable={depsFor} onClose={() => setDepsFor(null)} />
      )}
    </Box>
  );
}
