/**
 * Activity (Manager+) — the audit trail. Shows who did what to which entity and
 * when, newest first, with field-level changes spelled out readably. Filters by
 * entity type / action / user, paginates, and exports the filtered log to CSV.
 *
 * The backend enforces access (Manager+; user-management entries are Admin-only);
 * this page is an additional client-side guard via the view_activity permission.
 */

import { useMemo } from 'react';
import {
  Box, Card, TextField, MenuItem, Table, TableHead, TableBody, TableRow, TableCell,
  Avatar, Typography, Chip, Tooltip,
} from '@mui/material';
import { PageHeader } from '../../components/common/PageHeader';
import { ResultStates, TableSkeleton, EmptyState } from '../../components/data/ResultStates';
import { PaginationBar } from '../../components/data/PaginationBar';
import { ExportButton } from '../../components/data/ExportButton';
import { fetchAllRows } from '../../api/fetchAll';
import { usePaginatedList } from '../../hooks/usePaginatedList';
import { useAsync } from '../../hooks/useAsync';
import { listActivity, ACTIVITY_ENTITY_TYPES, ACTIVITY_ACTIONS } from '../../api/activity';
import { fmtRelativeOrDate, fmtDateTime } from '../../utils/format';
import { summaryText, changeLines, actorName } from '../../utils/activityText';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../auth/roles';

// Colour the action chip so the log is scannable at a glance.
const ACTION_COLOR = { created: 'success', updated: 'warning', deleted: 'error' };

const EXPORT_COLUMNS = [
  { header: 'When', value: (r) => fmtDateTime(r.created_at) },
  { header: 'Actor', value: (r) => r.username || '' },
  { header: 'Action', value: 'action' },
  { header: 'Entity type', value: 'entity_type' },
  { header: 'Entity', value: 'entity_name' },
  { header: 'Summary', value: (r) => summaryText(r) },
  { header: 'Changes', value: (r) => (r.changes || []).map((c) => `${c.field}: ${c.old} → ${c.new}`).join('; ') },
];

function initials(name = '') {
  const p = name.trim().split(/[\s._-]+/).filter(Boolean);
  return ((p[0]?.[0] || '') + (p[1]?.[0] || '')).toUpperCase() || name[0]?.toUpperCase() || '?';
}

export default function ActivityPage() {
  const { role } = useAuth();
  const isAdmin = can(role, 'manage_users');
  const list = usePaginatedList(listActivity, { limit: 20 });

  // Actor options come from the activity log itself — via the Activity endpoint
  // this role can already read — NOT /auth/users (which Managers can't access, so
  // they'd 403). This lists only people who've actually done something, and adds
  // no new visibility: a Manager's sample already excludes user-management rows.
  const { data: actorSample } = useAsync(() => listActivity({ limit: 200 }), []);
  const actors = useMemo(() => {
    const byId = new Map();
    for (const e of actorSample?.items || []) {
      // Newest-first, so the first username seen for an id is its latest name.
      // Skip entries whose actor was deleted (user_id nulled) — can't filter by id.
      if (e.user_id != null && e.username && !byId.has(e.user_id)) byId.set(e.user_id, e.username);
    }
    return [...byId.entries()]
      .map(([id, username]) => ({ id, username }))
      .sort((a, b) => a.username.localeCompare(b.username, undefined, { sensitivity: 'base' }));
  }, [actorSample]);

  // Hide the 'user' entity type from non-Admins — they never receive those rows,
  // so offering the filter would just return nothing.
  const entityTypeOptions = useMemo(
    () => ACTIVITY_ENTITY_TYPES.filter((t) => t !== 'user' || isAdmin),
    [isAdmin],
  );

  const exportFilters = {
    entity_type: list.filters.entity_type,
    action: list.filters.action,
    user: list.filters.user,
  };

  return (
    <Box>
      <PageHeader
        title="Activity"
        subtitle="Audit trail of every change across LoadBalance — newest first."
        actions={
          <ExportButton
            filenamePrefix="activity"
            columns={EXPORT_COLUMNS}
            fetchRows={() => fetchAllRows(listActivity, exportFilters)}
          />
        }
      />

      {/* Filters */}
      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <TextField
          select size="small" label="Entity type" sx={{ minWidth: 170 }}
          value={list.filters.entity_type || ''}
          onChange={(e) => list.setFilters({ entity_type: e.target.value })}
        >
          <MenuItem value="">All types</MenuItem>
          {entityTypeOptions.map((t) => <MenuItem key={t} value={t} sx={{ textTransform: 'capitalize' }}>{t}</MenuItem>)}
        </TextField>
        <TextField
          select size="small" label="Action" sx={{ minWidth: 150 }}
          value={list.filters.action || ''}
          onChange={(e) => list.setFilters({ action: e.target.value })}
        >
          <MenuItem value="">All actions</MenuItem>
          {ACTIVITY_ACTIONS.map((a) => <MenuItem key={a} value={a} sx={{ textTransform: 'capitalize' }}>{a}</MenuItem>)}
        </TextField>
        <TextField
          select size="small" label="User" sx={{ minWidth: 180 }}
          value={list.filters.user ?? ''}
          onChange={(e) => list.setFilters({ user: e.target.value })}
        >
          {/* Value is the user_id, label is the username — so the user picks a
              name while the backend still filters by id (contract unchanged). */}
          <MenuItem value="">All users</MenuItem>
          {actors.map((a) => <MenuItem key={a.id} value={a.id}>{a.username}</MenuItem>)}
        </TextField>
      </Box>

      <Card>
        <ResultStates
          loading={list.loading}
          error={list.error}
          isEmpty={list.items.length === 0}
          onRetry={list.refetch}
          skeleton={<TableSkeleton rows={8} cols={3} />}
          empty={<EmptyState title="No activity found" message="Nothing matches these filters yet. Try widening them — actions across the app will show up here." />}
        >
          <Table>
            <TableHead>
              <TableRow>
                <TableCell width={104}>Action</TableCell>
                <TableCell>Details</TableCell>
                <TableCell align="right" width={150}>When</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {list.items.map((e) => {
                const lines = changeLines(e);
                return (
                  <TableRow key={e.id} hover>
                    <TableCell>
                      <Chip
                        label={e.action}
                        size="small"
                        color={ACTION_COLOR[e.action] || 'default'}
                        variant="outlined"
                        sx={{ textTransform: 'capitalize', fontWeight: 600, height: 22 }}
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.25 }}>
                        <Avatar sx={{ width: 28, height: 28, mt: 0.25, fontSize: '0.68rem', fontWeight: 700, bgcolor: 'action.selected', color: 'primary.main' }}>
                          {initials(actorName(e))}
                        </Avatar>
                        <Box sx={{ minWidth: 0 }}>
                          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{summaryText(e)}</Typography>
                          {lines.length > 0 && (
                            <Box component="ul" sx={{ m: '2px 0 0', pl: 2, color: 'text.secondary' }}>
                              {lines.map((line, i) => (
                                <Typography key={i} component="li" sx={{ fontSize: '0.75rem', lineHeight: 1.5 }}>{line}</Typography>
                              ))}
                            </Box>
                          )}
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell align="right" sx={{ whiteSpace: 'nowrap', color: 'text.secondary' }}>
                      <Tooltip title={fmtDateTime(e.created_at)}>
                        <span>{fmtRelativeOrDate(e.created_at)}</span>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <PaginationBar total={list.total} limit={list.limit} offset={list.offset} itemCount={list.items.length} onOffsetChange={list.setOffset} />
        </ResultStates>
      </Card>
    </Box>
  );
}
