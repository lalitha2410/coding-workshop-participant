/**
 * Manage a deliverable's dependency chain: what it "depends on" (editable by
 * Contributor+) and its "dependents" (read-only — managed from the other side).
 * The picker is scoped to the same project; cycles/duplicates surface as a
 * friendly inline error from the backend's 400.
 */

import { useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions, Button, Box, Typography,
  MenuItem, TextField, IconButton, Alert, Chip, Divider, CircularProgress, Tooltip,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/CloseRounded';
import AddIcon from '@mui/icons-material/AddRounded';
import RemoveIcon from '@mui/icons-material/LinkOffRounded';
import ArrowIcon from '@mui/icons-material/ArrowForwardRounded';
import { getDependencies, addDependency, removeDependency, listDeliverables } from '../../api/deliverables';
import { useAsync } from '../../hooks/useAsync';
import { StatusChip } from '../../components/data/StatusChip';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../auth/roles';
import { useToast } from '../../components/common/Toast';
import { dependencyMsg } from '../../utils/messages';

function DepRow({ item, onRemove, canManage }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 0.75, borderTop: '1px solid', borderColor: 'divider' }}>
      <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600, flex: 1, minWidth: 0 }} noWrap>{item.name}</Typography>
      <StatusChip status={item.status} />
      {onRemove && canManage && (
        <Tooltip title="Remove dependency">
          <IconButton size="small" onClick={() => onRemove(item.id)}><RemoveIcon sx={{ fontSize: 18 }} /></IconButton>
        </Tooltip>
      )}
    </Box>
  );
}

export function DependenciesDialog({ open, deliverable, onClose }) {
  const { role } = useAuth();
  const toast = useToast();
  const canManage = can(role, 'create');

  const deps = useAsync(() => getDependencies(deliverable.id), [deliverable.id]);
  const pool = useAsync(() => listDeliverables({ project_id: deliverable.project_id, limit: 200 }), [deliverable.project_id]);

  const [pick, setPick] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const dependsOn = deps.data?.depends_on || [];
  const dependents = deps.data?.dependents || [];
  // Offer only feasible candidates: exclude the deliverable itself, prerequisites
  // it already has, and its direct dependents (which would create an immediate
  // cycle). Deeper/transitive cycles are caught by the backend and shown inline.
  const excluded = new Set([deliverable.id, ...dependsOn.map((d) => d.id), ...dependents.map((d) => d.id)]);
  const candidates = (pool.data?.items || []).filter((d) => !excluded.has(d.id));

  async function add() {
    if (!pick) return;
    const name = candidates.find((c) => c.id === Number(pick))?.name || `#${pick}`;
    setError(''); setBusy(true);
    try {
      await addDependency(deliverable.id, Number(pick));
      setPick('');
      toast.success(dependencyMsg(name, 'added'));
      deps.refetch();
    } catch (err) {
      // Friendly cycle/duplicate/reference messages come straight from the API.
      setError(err?.message || 'Could not add dependency.');
    } finally { setBusy(false); }
  }

  async function remove(depId) {
    const name = dependsOn.find((d) => d.id === depId)?.name || `#${depId}`;
    setError(''); setBusy(true);
    try {
      await removeDependency(deliverable.id, depId);
      toast.success(dependencyMsg(name, 'removed'));
      deps.refetch();
    } catch (err) {
      setError(err?.message || 'Could not remove dependency.');
    } finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: 3 } } }}>
      <DialogTitle sx={{ fontWeight: 700, pr: 6 }}>
        Dependencies
        <Typography variant="body2" sx={{ color: 'text.secondary', fontWeight: 400 }}>{deliverable.name}</Typography>
        <IconButton onClick={onClose} sx={{ position: 'absolute', right: 12, top: 12 }} aria-label="Close">
          <CloseIcon sx={{ fontSize: 20 }} />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {deps.loading ? (
          <Box sx={{ py: 4, display: 'grid', placeItems: 'center' }}><CircularProgress size={22} /></Box>
        ) : deps.error ? (
          <Alert severity="error" action={<Button size="small" onClick={deps.refetch}>Retry</Button>}>Failed to load dependencies.</Alert>
        ) : (
          <>
            {/* Chain visual: THIS  → depends on →  [ ... ] */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap', p: 1.5, mb: 2, borderRadius: 2, bgcolor: 'background.default', border: '1px solid', borderColor: 'divider' }}>
              <Chip label={deliverable.name} size="small" sx={{ bgcolor: 'action.selected', color: 'primary.main', fontWeight: 700, maxWidth: 200 }} />
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.disabled' }}>
                <ArrowIcon sx={{ fontSize: 16 }} />
                <Typography variant="caption">depends on</Typography>
              </Box>
              {dependsOn.length === 0
                ? <Typography variant="caption" sx={{ color: 'text.disabled', fontStyle: 'italic' }}>nothing yet</Typography>
                : dependsOn.map((d) => <Chip key={d.id} label={d.name} size="small" variant="outlined" sx={{ maxWidth: 180 }} />)}
            </Box>

            {/* Depends on (editable) */}
            <Typography variant="overline">Depends on ({dependsOn.length})</Typography>
            {dependsOn.length === 0
              ? <Typography variant="body2" sx={{ color: 'text.disabled', py: 1 }}>This deliverable has no prerequisites.</Typography>
              : <Box sx={{ mb: 1 }}>{dependsOn.map((d) => <DepRow key={d.id} item={d} onRemove={remove} canManage={canManage} />)}</Box>}

            {canManage && (
              <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                <TextField
                  select size="small" fullWidth label="Add a prerequisite"
                  value={pick} onChange={(e) => setPick(e.target.value)}
                  disabled={busy || candidates.length === 0}
                  helperText={candidates.length === 0 ? 'No other deliverables in this project to depend on.' : ' '}
                >
                  {candidates.map((c) => <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>)}
                </TextField>
                <Button variant="contained" startIcon={<AddIcon />} onClick={add} disabled={!pick || busy} sx={{ flexShrink: 0, height: 40 }}>Add</Button>
              </Box>
            )}

            <Divider sx={{ my: 2 }} />

            {/* Dependents (read-only) */}
            <Typography variant="overline">Depended on by ({dependents.length})</Typography>
            {dependents.length === 0
              ? <Typography variant="body2" sx={{ color: 'text.disabled', py: 1 }}>Nothing depends on this deliverable yet.</Typography>
              : <Box>{dependents.map((d) => <DepRow key={d.id} item={d} />)}</Box>}
          </>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button onClick={onClose} color="inherit">Close</Button>
      </DialogActions>
    </Dialog>
  );
}
