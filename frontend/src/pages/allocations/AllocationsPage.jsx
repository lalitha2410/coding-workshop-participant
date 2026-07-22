import { useCallback, useMemo, useState } from 'react';
import {
  Box, Card, CardContent, Button, TextField, MenuItem, Table, TableHead, TableBody, TableRow, TableCell,
  IconButton, Tooltip, Typography, LinearProgress,
} from '@mui/material';
import AddIcon from '@mui/icons-material/AddRounded';
import EditIcon from '@mui/icons-material/EditOutlined';
import DeleteIcon from '@mui/icons-material/DeleteOutline';
import OverIcon from '@mui/icons-material/WarningAmberRounded';
import { PageHeader } from '../../components/common/PageHeader';
import { ResultStates, TableSkeleton, EmptyState } from '../../components/data/ResultStates';
import { PaginationBar } from '../../components/data/PaginationBar';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { AllocationFormDialog } from './AllocationFormDialog';
import { usePaginatedList } from '../../hooks/usePaginatedList';
import { useAsync } from '../../hooks/useAsync';
import { listAllocations, deleteAllocation, overAllocated } from '../../api/allocations';
import { listResources } from '../../api/resources';
import { listProjects } from '../../api/projects';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../auth/roles';
import { useToast } from '../../components/common/Toast';

export default function AllocationsPage() {
  const { role } = useAuth();
  const toast = useToast();
  const list = usePaginatedList(listAllocations, { limit: 10 });
  const { data: resData } = useAsync(() => listResources({ limit: 200 }), []);
  const { data: projData } = useAsync(() => listProjects({ limit: 200 }), []);
  const { data: over, refetch: refetchOver } = useAsync(overAllocated, []);

  const resources = resData?.items || [];
  const projects = projData?.items || [];
  const resourceName = useMemo(() => Object.fromEntries(resources.map((r) => [r.id, r.name])), [resources]);
  const projectName = useMemo(() => Object.fromEntries(projects.map((p) => [p.id, p.name])), [projects]);

  const [form, setForm] = useState({ open: false, allocation: null });
  const [del, setDel] = useState({ open: false, allocation: null, busy: false });

  const canCreate = can(role, 'create');
  const canUpdate = can(role, 'update');
  const canDelete = can(role, 'delete');
  const ready = resources.length > 0 && projects.length > 0;

  const onSaved = useCallback(() => {
    setForm({ open: false, allocation: null });
    list.refetch();
    refetchOver();
  }, [list, refetchOver]);

  async function confirmDelete() {
    setDel((d) => ({ ...d, busy: true }));
    try {
      await deleteAllocation(del.allocation.id);
      toast.success('Allocation deleted');
      setDel({ open: false, allocation: null, busy: false });
      list.refetch();
      refetchOver();
    } catch (err) {
      toast.error(err?.message || 'Could not delete allocation.');
      setDel((d) => ({ ...d, busy: false }));
    }
  }

  return (
    <Box>
      <PageHeader
        title="Allocations"
        subtitle="Who's assigned where — and who's over-allocated."
        actions={canCreate && <Button variant="contained" startIcon={<AddIcon />} disabled={!ready} onClick={() => setForm({ open: true, allocation: null })}>New allocation</Button>}
      />

      {/* Over-allocation strip (from /allocations/over-allocated) */}
      {Array.isArray(over) && over.length > 0 && (
        <Card sx={{ mb: 2, borderColor: (t) => t.palette.meridian.errorBorder, bgcolor: (t) => t.palette.meridian.errorBg }}>
          <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: (t) => t.palette.meridian.errorFg }}>
              <OverIcon sx={{ fontSize: 20 }} />
              <Typography sx={{ fontWeight: 700, fontSize: '0.875rem' }}>{over.length} over-allocated</Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              {over.map((o) => (
                <Box key={o.resource_id} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 1.25, py: 0.5, borderRadius: 1.5, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
                  <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{o.resource_name}</Typography>
                  <Typography className="mono" sx={{ fontSize: '0.8125rem', fontWeight: 700, color: (t) => t.palette.meridian.errorFg }}>{o.total_allocation_pct}%</Typography>
                </Box>
              ))}
            </Box>
          </CardContent>
        </Card>
      )}

      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <TextField select size="small" label="Resource" value={list.filters.resource_id || ''} sx={{ minWidth: 200 }}
          onChange={(e) => list.setFilters({ resource_id: e.target.value })}>
          <MenuItem value="">All resources</MenuItem>
          {resources.map((r) => <MenuItem key={r.id} value={r.id}>{r.name}</MenuItem>)}
        </TextField>
        <TextField select size="small" label="Project" value={list.filters.project_id || ''} sx={{ minWidth: 220 }}
          onChange={(e) => list.setFilters({ project_id: e.target.value })}>
          <MenuItem value="">All projects</MenuItem>
          {projects.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
        </TextField>
      </Box>

      <Card>
        <ResultStates
          loading={list.loading}
          error={list.error}
          isEmpty={list.items.length === 0}
          onRetry={list.refetch}
          skeleton={<TableSkeleton rows={6} cols={4} />}
          empty={<EmptyState title="No allocations found" message="Assign a resource to a project to get started." action={canCreate && ready && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setForm({ open: true, allocation: null })}>New allocation</Button>} />}
        >
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Resource</TableCell>
                <TableCell>Project</TableCell>
                <TableCell sx={{ minWidth: 180 }}>Allocation</TableCell>
                {(canUpdate || canDelete) && <TableCell align="right" width={96}>Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {list.items.map((a) => (
                <TableRow key={a.id} hover>
                  <TableCell sx={{ fontWeight: 600 }}>{resourceName[a.resource_id] || `#${a.resource_id}`}</TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>{projectName[a.project_id] || `#${a.project_id}`}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <LinearProgress variant="determinate" value={Math.min(Number(a.allocation_pct) || 0, 100)}
                        sx={{ flex: 1, height: 5, borderRadius: 999, bgcolor: 'action.hover' }} />
                      <Typography className="mono" sx={{ fontSize: '0.75rem', fontWeight: 600, width: 34, textAlign: 'right' }}>{a.allocation_pct}%</Typography>
                    </Box>
                  </TableCell>
                  {(canUpdate || canDelete) && (
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.25 }}>
                        {canUpdate && <Tooltip title="Edit"><IconButton size="small" onClick={() => setForm({ open: true, allocation: a })}><EditIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>}
                        {canDelete && <Tooltip title="Delete"><IconButton size="small" onClick={() => setDel({ open: true, allocation: a, busy: false })}><DeleteIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>}
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
        <AllocationFormDialog open allocation={form.allocation} resources={resources} projects={projects}
          onClose={() => setForm({ open: false, allocation: null })} onSaved={onSaved} />
      )}
      <ConfirmDialog
        open={del.open} title="Delete allocation?"
        message="This allocation will be permanently removed."
        confirmLabel="Delete" destructive busy={del.busy}
        onConfirm={confirmDelete} onClose={() => setDel({ open: false, allocation: null, busy: false })}
      />
    </Box>
  );
}
