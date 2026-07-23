import { useCallback, useState } from 'react';
import {
  Box, Card, Button, MenuItem, TextField, Table, TableHead, TableBody, TableRow, TableCell,
  IconButton, Tooltip, LinearProgress, Checkbox,
} from '@mui/material';
import AddIcon from '@mui/icons-material/AddRounded';
import EditIcon from '@mui/icons-material/EditOutlined';
import DeleteIcon from '@mui/icons-material/DeleteOutline';
import LabelIcon from '@mui/icons-material/LabelOutlined';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusChip, RiskChip } from '../../components/data/StatusChip';
import { ResultStates, TableSkeleton, EmptyState } from '../../components/data/ResultStates';
import { PaginationBar } from '../../components/data/PaginationBar';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { BulkActionBar } from '../../components/data/BulkActionBar';
import { BulkStatusDialog } from '../../components/data/BulkStatusDialog';
import { BulkResultDialog } from '../../components/data/BulkResultDialog';
import { ProjectFormDialog } from './ProjectFormDialog';
import { usePaginatedList } from '../../hooks/usePaginatedList';
import { useBulk } from '../../hooks/useBulk';
import { useSelection } from '../../utils/selection';
import { pluralize } from '../../utils/bulk';
import { ExportButton } from '../../components/data/ExportButton';
import { fetchAllRows } from '../../api/fetchAll';
import { listProjects, deleteProject, updateProject, PROJECT_STATUSES, DEPARTMENTS } from '../../api/projects';
import { fmtMoney, fmtDate, isAtRisk } from '../../utils/format';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../auth/roles';
import { useToast } from '../../components/common/Toast';
import { entityMsg } from '../../utils/messages';

const STATUS_OPTIONS = PROJECT_STATUSES.map((s) => ({ value: s, label: s.replace(/_/g, ' ') }));

const EXPORT_COLUMNS = [
  { header: 'ID', value: 'id' },
  { header: 'Name', value: 'name' },
  { header: 'Description', value: 'description' },
  { header: 'Status', value: 'status' },
  { header: 'Department', value: 'department' },
  { header: 'Start Date', value: 'start_date' },
  { header: 'End Date', value: 'end_date' },
  { header: 'Deadline', value: 'deadline' },
  { header: 'Budget Planned', value: 'budget_planned' },
  { header: 'Budget Consumed', value: 'budget_consumed' },
];

export default function ProjectsPage() {
  const { role } = useAuth();
  const toast = useToast();
  const list = usePaginatedList(listProjects, { limit: 10 });
  const [form, setForm] = useState({ open: false, project: null });
  const [del, setDel] = useState({ open: false, project: null, busy: false });

  const canCreate = can(role, 'create');
  const canUpdate = can(role, 'update');
  const canDelete = can(role, 'delete');
  const showSelection = canDelete || canUpdate;

  // Bulk selection + actions. Selection clears on page/filter change (resetKey)
  // and after every completed action (via onSettled).
  const resetKey = `${list.offset}|${JSON.stringify(list.filters)}`;
  const sel = useSelection(list.items, resetKey);
  const bulk = useBulk({ onSettled: () => { sel.clear(); list.refetch(); } });
  const [bulkDelete, setBulkDelete] = useState(false);
  const [bulkStatus, setBulkStatus] = useState(false);

  const onSaved = useCallback(() => { setForm({ open: false, project: null }); list.refetch(); }, [list]);

  async function runBulkDelete() {
    setBulkDelete(false);
    await bulk.run(sel.selectedItems, (p) => deleteProject(p.id), { singular: 'project', verbPast: 'deleted' });
  }

  async function runBulkStatus(status) {
    setBulkStatus(false);
    await bulk.run(sel.selectedItems, (p) => updateProject(p.id, { status }), { singular: 'project', verbPast: 'updated' });
  }

  async function confirmDelete() {
    setDel((d) => ({ ...d, busy: true }));
    try {
      await deleteProject(del.project.id);
      toast.success(entityMsg('Project', del.project.name, 'deleted'));
      setDel({ open: false, project: null, busy: false });
      list.refetch();
    } catch (err) {
      toast.error(err?.message || 'Could not delete project.');
      setDel((d) => ({ ...d, busy: false }));
    }
  }

  return (
    <Box>
      <PageHeader
        title="Projects"
        subtitle="Plan, track, and manage the project portfolio."
        actions={
          <>
            <ExportButton
              filenamePrefix="projects"
              columns={EXPORT_COLUMNS}
              fetchRows={() => fetchAllRows(listProjects, { status: list.filters.status, department: list.filters.department })}
            />
            {canCreate && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setForm({ open: true, project: null })}>New project</Button>}
          </>
        }
      />

      {/* Filters */}
      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <TextField select size="small" label="Status" value={list.filters.status || ''} sx={{ minWidth: 160 }}
          onChange={(e) => list.setFilters({ status: e.target.value })}>
          <MenuItem value="">All statuses</MenuItem>
          {PROJECT_STATUSES.map((s) => <MenuItem key={s} value={s}>{s.replace('_', ' ')}</MenuItem>)}
        </TextField>
        <TextField select size="small" label="Department" value={list.filters.department || ''} sx={{ minWidth: 180 }}
          onChange={(e) => list.setFilters({ department: e.target.value })}>
          <MenuItem value="">All departments</MenuItem>
          {DEPARTMENTS.map((d) => <MenuItem key={d} value={d}>{d}</MenuItem>)}
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
          empty={<EmptyState title="No projects found" message="Try clearing filters, or create the first project." action={canCreate && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setForm({ open: true, project: null })}>New project</Button>} />}
        >
          <Table>
            <TableHead>
              <TableRow>
                {showSelection && (
                  <TableCell padding="checkbox">
                    <Checkbox size="small" checked={sel.allSelected} indeterminate={sel.someSelected} onChange={sel.toggleAll} inputProps={{ 'aria-label': 'Select all projects on this page' }} />
                  </TableCell>
                )}
                <TableCell>Project</TableCell>
                <TableCell>Department</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Deadline</TableCell>
                <TableCell align="right">Budget</TableCell>
                {(canUpdate || canDelete) && <TableCell align="right" width={96}>Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {list.items.map((p) => {
                const planned = Number(p.budget_planned) || 0;
                const consumed = Number(p.budget_consumed) || 0;
                const pct = planned > 0 ? Math.min(Math.round((consumed / planned) * 100), 999) : 0;
                return (
                  <TableRow key={p.id} hover selected={sel.isSelected(p.id)}>
                    {showSelection && (
                      <TableCell padding="checkbox">
                        <Checkbox size="small" checked={sel.isSelected(p.id)} onChange={() => sel.toggle(p.id)} inputProps={{ 'aria-label': `Select ${p.name}` }} />
                      </TableCell>
                    )}
                    <TableCell sx={{ fontWeight: 600 }}>{p.name}</TableCell>
                    <TableCell sx={{ color: 'text.secondary' }}>{p.department || '—'}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center', flexWrap: 'wrap' }}>
                        <StatusChip status={p.status} />
                        {isAtRisk(p) && <RiskChip />}
                      </Box>
                    </TableCell>
                    <TableCell className="mono" sx={{ whiteSpace: 'nowrap' }}>{fmtDate(p.deadline)}</TableCell>
                    <TableCell align="right" sx={{ minWidth: 160 }}>
                      <Box className="mono" sx={{ fontSize: '0.75rem', fontWeight: 600, mb: 0.5 }}>
                        {fmtMoney(consumed)} <Box component="span" sx={{ color: 'text.disabled' }}>/ {fmtMoney(planned)}</Box>
                      </Box>
                      <LinearProgress variant="determinate" value={Math.min(pct, 100)}
                        color={pct >= 100 ? 'error' : pct >= 90 ? 'warning' : 'primary'}
                        sx={{ height: 5, borderRadius: 999, bgcolor: 'action.hover' }} />
                    </TableCell>
                    {(canUpdate || canDelete) && (
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.25 }}>
                          {canUpdate && (
                            <Tooltip title="Edit"><IconButton size="small" onClick={() => setForm({ open: true, project: p })}><EditIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
                          )}
                          {canDelete && (
                            <Tooltip title="Delete"><IconButton size="small" onClick={() => setDel({ open: true, project: p, busy: false })}><DeleteIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
                          )}
                        </Box>
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <PaginationBar total={list.total} limit={list.limit} offset={list.offset} itemCount={list.items.length} onOffsetChange={list.setOffset} />
        </ResultStates>
      </Card>

      {form.open && (
        <ProjectFormDialog open project={form.project} onClose={() => setForm({ open: false, project: null })} onSaved={onSaved} />
      )}
      <ConfirmDialog
        open={del.open}
        title="Delete project?"
        message={`"${del.project?.name}" and its deliverables/allocations will be permanently removed.`}
        confirmLabel="Delete"
        destructive
        busy={del.busy}
        onConfirm={confirmDelete}
        onClose={() => setDel({ open: false, project: null, busy: false })}
      />

      <ConfirmDialog
        open={bulkDelete}
        title="Delete projects?"
        message={`Delete ${pluralize(sel.count, 'project')}? This can't be undone — their deliverables and allocations go too.`}
        confirmLabel="Delete"
        destructive
        onConfirm={runBulkDelete}
        onClose={() => setBulkDelete(false)}
      />
      <BulkStatusDialog
        open={bulkStatus}
        count={sel.count}
        singular="project"
        statuses={STATUS_OPTIONS}
        onConfirm={runBulkStatus}
        onClose={() => setBulkStatus(false)}
      />
      <BulkResultDialog result={bulk.result} labelFor={(p) => p.name} onClose={bulk.clearResult} />
    </Box>
  );
}
