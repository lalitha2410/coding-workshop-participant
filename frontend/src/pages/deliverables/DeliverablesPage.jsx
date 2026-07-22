import { useCallback, useMemo, useState } from 'react';
import {
  Box, Card, Button, TextField, MenuItem, Table, TableHead, TableBody, TableRow, TableCell,
  IconButton, Tooltip, LinearProgress, Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/AddRounded';
import EditIcon from '@mui/icons-material/EditOutlined';
import DeleteIcon from '@mui/icons-material/DeleteOutline';
import { PageHeader } from '../../components/common/PageHeader';
import { StatusChip } from '../../components/data/StatusChip';
import { ResultStates, TableSkeleton, EmptyState } from '../../components/data/ResultStates';
import { PaginationBar } from '../../components/data/PaginationBar';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { DeliverableFormDialog } from './DeliverableFormDialog';
import { usePaginatedList } from '../../hooks/usePaginatedList';
import { useAsync } from '../../hooks/useAsync';
import { listDeliverables, deleteDeliverable, DELIVERABLE_STATUSES } from '../../api/deliverables';
import { listProjects } from '../../api/projects';
import { fmtDate } from '../../utils/format';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../auth/roles';
import { useToast } from '../../components/common/Toast';

export default function DeliverablesPage() {
  const { role } = useAuth();
  const toast = useToast();
  const list = usePaginatedList(listDeliverables, { limit: 10 });
  const { data: projectsData } = useAsync(() => listProjects({ limit: 200 }), []);
  const projects = projectsData?.items || [];
  const projectName = useMemo(() => Object.fromEntries(projects.map((p) => [p.id, p.name])), [projects]);

  const [form, setForm] = useState({ open: false, deliverable: null });
  const [del, setDel] = useState({ open: false, deliverable: null, busy: false });

  const canCreate = can(role, 'create');
  const canUpdate = can(role, 'update');
  const canDelete = can(role, 'delete');

  const onSaved = useCallback(() => { setForm({ open: false, deliverable: null }); list.refetch(); }, [list]);

  async function confirmDelete() {
    setDel((d) => ({ ...d, busy: true }));
    try {
      await deleteDeliverable(del.deliverable.id);
      toast.success('Deliverable deleted');
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
        actions={canCreate && <Button variant="contained" startIcon={<AddIcon />} disabled={projects.length === 0} onClick={() => setForm({ open: true, deliverable: null })}>New deliverable</Button>}
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
                <TableCell>Deliverable</TableCell>
                <TableCell>Project</TableCell>
                <TableCell>Status</TableCell>
                <TableCell sx={{ minWidth: 160 }}>Completion</TableCell>
                <TableCell>Due</TableCell>
                {(canUpdate || canDelete) && <TableCell align="right" width={96}>Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {list.items.map((d) => (
                <TableRow key={d.id} hover>
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
                  {(canUpdate || canDelete) && (
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.25 }}>
                        {canUpdate && <Tooltip title="Edit"><IconButton size="small" onClick={() => setForm({ open: true, deliverable: d })}><EditIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>}
                        {canDelete && <Tooltip title="Delete"><IconButton size="small" onClick={() => setDel({ open: true, deliverable: d, busy: false })}><DeleteIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>}
                      </Box>
                    </TableCell>
                  )}
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
    </Box>
  );
}
