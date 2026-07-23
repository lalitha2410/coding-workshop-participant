import { useCallback, useState } from 'react';
import {
  Box, Card, Button, TextField, InputAdornment, Table, TableHead, TableBody, TableRow, TableCell,
  IconButton, Tooltip, Avatar, Typography, Checkbox,
} from '@mui/material';
import AddIcon from '@mui/icons-material/AddRounded';
import SearchIcon from '@mui/icons-material/SearchRounded';
import EditIcon from '@mui/icons-material/EditOutlined';
import DeleteIcon from '@mui/icons-material/DeleteOutline';
import { PageHeader } from '../../components/common/PageHeader';
import { ResultStates, TableSkeleton, EmptyState } from '../../components/data/ResultStates';
import { PaginationBar } from '../../components/data/PaginationBar';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { BulkActionBar } from '../../components/data/BulkActionBar';
import { BulkResultDialog } from '../../components/data/BulkResultDialog';
import { ResourceFormDialog } from './ResourceFormDialog';
import { usePaginatedList } from '../../hooks/usePaginatedList';
import { useBulk } from '../../hooks/useBulk';
import { useSelection } from '../../utils/selection';
import { pluralize } from '../../utils/bulk';
import { ExportButton } from '../../components/data/ExportButton';
import { fetchAllRows } from '../../api/fetchAll';
import { listResources, deleteResource } from '../../api/resources';
import { fmtDate } from '../../utils/format';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../auth/roles';
import { useToast } from '../../components/common/Toast';
import { entityMsg } from '../../utils/messages';

const EXPORT_COLUMNS = [
  { header: 'ID', value: 'id' },
  { header: 'Name', value: 'name' },
  { header: 'Email', value: 'email' },
  { header: 'Title', value: 'title' },
  { header: 'Created At', value: 'created_at' },
];

function initials(name = '') {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] || '') + (parts[1]?.[0] || '')).toUpperCase() || '?';
}

export default function ResourcesPage() {
  const { role } = useAuth();
  const toast = useToast();
  const list = usePaginatedList(listResources, { limit: 10 });
  const [form, setForm] = useState({ open: false, resource: null });
  const [del, setDel] = useState({ open: false, resource: null, busy: false });

  const canCreate = can(role, 'create');
  const canUpdate = can(role, 'update');
  const canDelete = can(role, 'delete');
  const showSelection = canDelete; // only bulk action here is delete (Manager+)

  const resetKey = `${list.offset}|${JSON.stringify(list.filters)}`;
  const sel = useSelection(list.items, resetKey);
  const bulk = useBulk({ onSettled: () => { sel.clear(); list.refetch(); } });
  const [bulkDelete, setBulkDelete] = useState(false);

  const onSaved = useCallback(() => { setForm({ open: false, resource: null }); list.refetch(); }, [list]);

  async function runBulkDelete() {
    setBulkDelete(false);
    await bulk.run(sel.selectedItems, (r) => deleteResource(r.id), { singular: 'resource', verbPast: 'deleted' });
  }

  async function confirmDelete() {
    setDel((d) => ({ ...d, busy: true }));
    try {
      await deleteResource(del.resource.id);
      toast.success(entityMsg('Resource', del.resource.name, 'deleted'));
      setDel({ open: false, resource: null, busy: false });
      list.refetch();
    } catch (err) {
      toast.error(err?.message || 'Could not delete resource.');
      setDel((d) => ({ ...d, busy: false }));
    }
  }

  return (
    <Box>
      <PageHeader
        title="Resources"
        subtitle="People and their skills across the organization."
        actions={
          <>
            <ExportButton
              filenamePrefix="resources"
              columns={EXPORT_COLUMNS}
              fetchRows={() => fetchAllRows(listResources, { search: list.filters.search })}
            />
            {canCreate && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setForm({ open: true, resource: null })}>New resource</Button>}
          </>
        }
      />

      <Box sx={{ mb: 2, maxWidth: 340 }}>
        <TextField
          size="small" fullWidth placeholder="Search by name or title…"
          value={list.filters.search || ''}
          onChange={(e) => list.setFilters({ search: e.target.value })}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon sx={{ fontSize: 18, color: 'text.disabled' }} /></InputAdornment> }}
        />
      </Box>

      {showSelection && sel.count > 0 && (
        <BulkActionBar count={sel.count} running={bulk.running} progress={bulk.progress} onClear={sel.clear}>
          <Button size="small" color="error" startIcon={<DeleteIcon sx={{ fontSize: 16 }} />} disabled={bulk.running} onClick={() => setBulkDelete(true)}>
            Delete
          </Button>
        </BulkActionBar>
      )}

      <Card>
        <ResultStates
          loading={list.loading}
          error={list.error}
          isEmpty={list.items.length === 0}
          onRetry={list.refetch}
          skeleton={<TableSkeleton rows={6} cols={4} />}
          empty={<EmptyState title="No resources found" message="Try a different search, or add a team member." action={canCreate && <Button variant="contained" startIcon={<AddIcon />} onClick={() => setForm({ open: true, resource: null })}>New resource</Button>} />}
        >
          <Table>
            <TableHead>
              <TableRow>
                {showSelection && (
                  <TableCell padding="checkbox">
                    <Checkbox size="small" checked={sel.allSelected} indeterminate={sel.someSelected} onChange={sel.toggleAll} inputProps={{ 'aria-label': 'Select all resources on this page' }} />
                  </TableCell>
                )}
                <TableCell>Name</TableCell>
                <TableCell>Title</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Added</TableCell>
                {(canUpdate || canDelete) && <TableCell align="right" width={96}>Actions</TableCell>}
              </TableRow>
            </TableHead>
            <TableBody>
              {list.items.map((r) => (
                <TableRow key={r.id} hover selected={sel.isSelected(r.id)}>
                  {showSelection && (
                    <TableCell padding="checkbox">
                      <Checkbox size="small" checked={sel.isSelected(r.id)} onChange={() => sel.toggle(r.id)} inputProps={{ 'aria-label': `Select ${r.name}` }} />
                    </TableCell>
                  )}
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                      <Avatar sx={{ width: 30, height: 30, fontSize: '0.7rem', fontWeight: 700, bgcolor: 'action.selected', color: 'primary.main' }}>{initials(r.name)}</Avatar>
                      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{r.name}</Typography>
                    </Box>
                  </TableCell>
                  <TableCell sx={{ color: 'text.secondary' }}>{r.title || '—'}</TableCell>
                  <TableCell className="mono" sx={{ color: 'text.secondary' }}>{r.email}</TableCell>
                  <TableCell className="mono" sx={{ whiteSpace: 'nowrap' }}>{fmtDate(r.created_at)}</TableCell>
                  {(canUpdate || canDelete) && (
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.25 }}>
                        {canUpdate && <Tooltip title="Edit"><IconButton size="small" onClick={() => setForm({ open: true, resource: r })}><EditIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>}
                        {canDelete && <Tooltip title="Delete"><IconButton size="small" onClick={() => setDel({ open: true, resource: r, busy: false })}><DeleteIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>}
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

      {form.open && <ResourceFormDialog open resource={form.resource} onClose={() => setForm({ open: false, resource: null })} onSaved={onSaved} />}
      <ConfirmDialog
        open={del.open} title="Delete resource?"
        message={`"${del.resource?.name}" and their allocations will be permanently removed.`}
        confirmLabel="Delete" destructive busy={del.busy}
        onConfirm={confirmDelete} onClose={() => setDel({ open: false, resource: null, busy: false })}
      />

      <ConfirmDialog
        open={bulkDelete}
        title="Delete resources?"
        message={`Delete ${pluralize(sel.count, 'resource')}? This can't be undone — their allocations go too.`}
        confirmLabel="Delete"
        destructive
        onConfirm={runBulkDelete}
        onClose={() => setBulkDelete(false)}
      />
      <BulkResultDialog result={bulk.result} labelFor={(r) => r.name} onClose={bulk.clearResult} />
    </Box>
  );
}
