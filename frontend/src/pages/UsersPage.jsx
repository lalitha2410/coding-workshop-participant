/**
 * Users (Admin only) — full CRUD. Table with search, pagination, create, edit
 * (username/email), a confirmed role change, and delete. Guards against
 * changing/deleting your own account (backend enforces the same).
 */

import { useCallback, useState } from 'react';
import {
  Box, Card, Button, TextField, InputAdornment, MenuItem, Table, TableHead, TableBody, TableRow, TableCell,
  IconButton, Tooltip, Avatar, Typography, Chip, CircularProgress, Checkbox,
} from '@mui/material';
import AddIcon from '@mui/icons-material/AddRounded';
import SearchIcon from '@mui/icons-material/SearchRounded';
import EditIcon from '@mui/icons-material/EditOutlined';
import DeleteIcon from '@mui/icons-material/DeleteOutline';
import { PageHeader } from '../components/common/PageHeader';
import { ResultStates, TableSkeleton, EmptyState } from '../components/data/ResultStates';
import { PaginationBar } from '../components/data/PaginationBar';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { BulkActionBar } from '../components/data/BulkActionBar';
import { BulkResultDialog } from '../components/data/BulkResultDialog';
import { UserFormDialog } from './UserFormDialog';
import { usePaginatedList } from '../hooks/usePaginatedList';
import { useBulk } from '../hooks/useBulk';
import { useSelection } from '../utils/selection';
import { pluralize } from '../utils/bulk';
import { listUsers, changeUserRole, deleteUser, ROLE_OPTIONS } from '../api/users';
import { fmtDate } from '../utils/format';
import { useAuth } from '../auth/AuthContext';
import { can } from '../auth/roles';
import { useToast } from '../components/common/Toast';
import { entityMsg } from '../utils/messages';

function initials(name = '') {
  const p = name.trim().split(/[\s._-]+/).filter(Boolean);
  return ((p[0]?.[0] || '') + (p[1]?.[0] || '')).toUpperCase() || name[0]?.toUpperCase() || '?';
}

export default function UsersPage() {
  const { user: me, role } = useAuth();
  const toast = useToast();
  const list = usePaginatedList(listUsers, { limit: 10 });
  const [form, setForm] = useState({ open: false, user: null });
  const [roleChange, setRoleChange] = useState(null); // { user, newRole, busy }
  const [del, setDel] = useState({ open: false, user: null, busy: false });

  // Bulk delete (Manager+). Your own account can't be selected — same guard as
  // the single-row delete; the backend also blocks it.
  const canDelete = can(role, 'delete');
  const isSelectable = useCallback((u) => u.id !== me?.id, [me]);
  const resetKey = `${list.offset}|${JSON.stringify(list.filters)}`;
  const sel = useSelection(list.items, resetKey, isSelectable);
  const bulk = useBulk({ onSettled: () => { sel.clear(); list.refetch(); } });
  const [bulkDelete, setBulkDelete] = useState(false);

  const onSaved = useCallback(() => { setForm({ open: false, user: null }); list.refetch(); }, [list]);

  async function runBulkDelete() {
    setBulkDelete(false);
    await bulk.run(sel.selectedItems, (u) => deleteUser(u.id), { singular: 'user', verbPast: 'deleted' });
  }

  // Role dropdown -> open a confirmation (rather than applying immediately).
  const requestRoleChange = (u, newRole) => {
    if (newRole !== u.role) setRoleChange({ user: u, newRole, busy: false });
  };

  async function confirmRoleChange() {
    const { user, newRole } = roleChange;
    setRoleChange((r) => ({ ...r, busy: true }));
    try {
      await changeUserRole(user.id, newRole);
      toast.success(`Role updated to ${newRole}.`);
      setRoleChange(null);
      list.refetch();
    } catch (err) {
      toast.error(err?.message || 'Could not change role.');
      setRoleChange(null); // revert the dropdown
    }
  }

  async function confirmDelete() {
    setDel((d) => ({ ...d, busy: true }));
    try {
      await deleteUser(del.user.id);
      toast.success(entityMsg('User', del.user.username, 'deleted'));
      setDel({ open: false, user: null, busy: false });
      list.refetch();
    } catch (err) {
      toast.error(err?.message || 'Could not delete user.');
      setDel((d) => ({ ...d, busy: false }));
    }
  }

  return (
    <Box>
      <PageHeader
        title="Users"
        subtitle="Manage accounts and roles across ACME."
        actions={<Button variant="contained" startIcon={<AddIcon />} onClick={() => setForm({ open: true, user: null })}>New user</Button>}
      />

      <Box sx={{ mb: 2, maxWidth: 340 }}>
        <TextField
          size="small" fullWidth placeholder="Search by username or email…"
          value={list.filters.search || ''}
          onChange={(e) => list.setFilters({ search: e.target.value })}
          InputProps={{ startAdornment: <InputAdornment position="start"><SearchIcon sx={{ fontSize: 18, color: 'text.disabled' }} /></InputAdornment> }}
        />
      </Box>

      {canDelete && sel.count > 0 && (
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
          skeleton={<TableSkeleton rows={6} cols={5} />}
          empty={<EmptyState title="No users found" message="Try a different search, or create a user." action={<Button variant="contained" startIcon={<AddIcon />} onClick={() => setForm({ open: true, user: null })}>New user</Button>} />}
        >
          <Table>
            <TableHead>
              <TableRow>
                {canDelete && (
                  <TableCell padding="checkbox">
                    <Checkbox size="small" checked={sel.allSelected} indeterminate={sel.someSelected} onChange={sel.toggleAll} inputProps={{ 'aria-label': 'Select all users on this page' }} />
                  </TableCell>
                )}
                <TableCell>User</TableCell>
                <TableCell>Email</TableCell>
                <TableCell width={180}>Role</TableCell>
                <TableCell>Created</TableCell>
                <TableCell align="right" width={104}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {list.items.map((u) => {
                const isSelf = me?.id === u.id;
                const pending = roleChange && roleChange.user.id === u.id;
                const selectValue = pending ? roleChange.newRole : u.role;
                return (
                  <TableRow key={u.id} hover selected={sel.isSelected(u.id)}>
                    {canDelete && (
                      <TableCell padding="checkbox">
                        <Tooltip title={isSelf ? "You can't delete your own account" : ''} disableHoverListener={!isSelf}>
                          <span>
                            <Checkbox size="small" checked={sel.isSelected(u.id)} disabled={isSelf} onChange={() => sel.toggle(u.id)} inputProps={{ 'aria-label': `Select ${u.username}` }} />
                          </span>
                        </Tooltip>
                      </TableCell>
                    )}
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                        <Avatar sx={{ width: 30, height: 30, fontSize: '0.7rem', fontWeight: 700, bgcolor: 'action.selected', color: 'primary.main' }}>{initials(u.username)}</Avatar>
                        <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{u.username}</Typography>
                        {isSelf && <Chip label="You" size="small" sx={{ height: 18, fontSize: '0.625rem', fontWeight: 700, bgcolor: 'action.selected', color: 'primary.main' }} />}
                      </Box>
                    </TableCell>
                    <TableCell className="mono" sx={{ color: 'text.secondary' }}>{u.email}</TableCell>
                    <TableCell>
                      <Tooltip title={isSelf ? "You can't change your own role" : ''} disableHoverListener={!isSelf}>
                        <span>
                          <TextField
                            select size="small" value={selectValue} sx={{ minWidth: 150 }}
                            disabled={isSelf || (pending && roleChange.busy)}
                            onChange={(e) => requestRoleChange(u, e.target.value)}
                            InputProps={{ endAdornment: pending && roleChange.busy ? <CircularProgress size={14} sx={{ mr: 2 }} /> : null }}
                          >
                            {ROLE_OPTIONS.map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>)}
                          </TextField>
                        </span>
                      </Tooltip>
                    </TableCell>
                    <TableCell className="mono" sx={{ whiteSpace: 'nowrap' }}>{fmtDate(u.created_at)}</TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.25 }}>
                        <Tooltip title="Edit user"><IconButton size="small" onClick={() => setForm({ open: true, user: u })}><EditIcon sx={{ fontSize: 18 }} /></IconButton></Tooltip>
                        <Tooltip title={isSelf ? "You can't delete your own account" : 'Delete user'}>
                          <span>
                            <IconButton size="small" disabled={isSelf} onClick={() => setDel({ open: true, user: u, busy: false })}><DeleteIcon sx={{ fontSize: 18 }} /></IconButton>
                          </span>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <PaginationBar total={list.total} limit={list.limit} offset={list.offset} itemCount={list.items.length} onOffsetChange={list.setOffset} />
        </ResultStates>
      </Card>

      {form.open && <UserFormDialog open user={form.user} onClose={() => setForm({ open: false, user: null })} onSaved={onSaved} />}

      <ConfirmDialog
        open={Boolean(roleChange)}
        title="Change role?"
        message={roleChange ? `Change ${roleChange.user.username}'s role from ${roleChange.user.role} to ${roleChange.newRole}? This will change what they can do in the app.` : ''}
        confirmLabel="Change role"
        busy={roleChange?.busy}
        onConfirm={confirmRoleChange}
        onClose={() => setRoleChange(null)}
      />

      <ConfirmDialog
        open={del.open}
        title="Delete user?"
        message={`"${del.user?.username}" will be permanently removed and won't be able to sign in.`}
        confirmLabel="Delete"
        destructive
        busy={del.busy}
        onConfirm={confirmDelete}
        onClose={() => setDel({ open: false, user: null, busy: false })}
      />

      <ConfirmDialog
        open={bulkDelete}
        title="Delete users?"
        message={`Delete ${pluralize(sel.count, 'user')}? This can't be undone — they won't be able to sign in.`}
        confirmLabel="Delete"
        destructive
        onConfirm={runBulkDelete}
        onClose={() => setBulkDelete(false)}
      />
      <BulkResultDialog result={bulk.result} labelFor={(u) => u.username} onClose={bulk.clearResult} />
    </Box>
  );
}
