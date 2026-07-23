/**
 * Command palette (Cmd/Ctrl+K). Searches the entity types the current role may
 * see — in parallel, debounced, degrading gracefully if one endpoint fails —
 * and groups results by type. Arrow keys move across groups; Enter opens the
 * highlighted result; Esc closes. With no query it shows role-filtered quick nav.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Dialog, Box, InputBase, Typography, CircularProgress, Divider, Chip,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/SearchRounded';
import CloseIcon from '@mui/icons-material/CloseRounded';
import WarningIcon from '@mui/icons-material/WarningAmberRounded';
import ArrowIcon from '@mui/icons-material/SubdirectoryArrowLeftRounded';
import { StatusChip } from '../data/StatusChip';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { fmtMoney } from '../../utils/format';
import {
  searchableTypes, quickNavActions, groupResults, flattenNavigable, moveHighlight,
} from '../../utils/commandPalette';
import { listProjects } from '../../api/projects';
import { listDeliverables } from '../../api/deliverables';
import { listResources } from '../../api/resources';
import { listAllocations } from '../../api/allocations';
import { listUsers } from '../../api/users';

const FETCHERS = {
  project: listProjects,
  deliverable: listDeliverables,
  resource: listResources,
  allocation: listAllocations,
  user: listUsers,
};

const PER_GROUP = 5;
const isMac = typeof navigator !== 'undefined' && /Mac|iP(hone|ad)/.test(navigator.platform || navigator.userAgent);

/** Primary text, secondary meta, and the search term to navigate with. */
function describe(type, item, ref = {}) {
  const projectName = ref.projectName || {};
  const resourceName = ref.resourceName || {};
  const allocTotals = ref.allocTotals || {};
  switch (type) {
    case 'project':
      return {
        primary: item.name,
        term: item.name,
        meta: (
          <>
            <span>{item.department || '—'}</span>
            <StatusChip status={item.status} />
            <span className="mono">{fmtMoney(item.budget_planned)}</span>
          </>
        ),
      };
    case 'deliverable':
      return {
        primary: item.name,
        term: item.name,
        meta: (
          <>
            <span>in {projectName[item.project_id] || `#${item.project_id}`}</span>
            <StatusChip status={item.status} />
          </>
        ),
      };
    case 'resource': {
      const total = allocTotals[item.id];
      const over = Number.isFinite(total) && total > 100;
      return {
        primary: item.name,
        term: item.name,
        meta: (
          <>
            <span>{item.title || '—'}</span>
            {Number.isFinite(total) && (
              <span className="mono" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                {over && <WarningIcon sx={{ fontSize: 13, color: 'warning.main' }} />}
                {total}% allocated
              </span>
            )}
          </>
        ),
      };
    }
    case 'allocation': {
      const r = resourceName[item.resource_id] || `#${item.resource_id}`;
      const p = projectName[item.project_id] || `#${item.project_id}`;
      return {
        primary: `${r} → ${p}`,
        term: r,
        meta: <span className="mono">{item.allocation_pct}%</span>,
      };
    }
    case 'user':
      return {
        primary: item.username,
        term: item.username,
        meta: (
          <>
            <span className="mono">{item.email}</span>
            <Chip label={item.role} size="small" sx={{ height: 18, fontSize: '0.625rem', fontWeight: 700 }} />
          </>
        ),
      };
    default:
      return { primary: item.name || String(item.id), term: item.name || '', meta: null };
  }
}

function Row({ selected, onActivate, onHover, index, children }) {
  return (
    <Box
      data-index={index}
      onMouseMove={onHover}
      onClick={onActivate}
      sx={{
        display: 'flex', alignItems: 'center', gap: 1.25, px: 2, py: 1, cursor: 'pointer', borderRadius: 1.5,
        bgcolor: selected ? 'action.selected' : 'transparent',
        '&:hover': { bgcolor: selected ? 'action.selected' : 'action.hover' },
      }}
    >
      {children}
    </Box>
  );
}

const metaSx = {
  display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap',
  fontSize: '0.75rem', color: 'text.secondary',
  '& .mono': { fontFamily: 'var(--font-mono, monospace)' },
};

export function CommandPalette({ open, onClose, role, navigate, refData }) {
  const [query, setQuery] = useState('');
  const debounced = useDebouncedValue(query.trim(), 250);
  const [byType, setByType] = useState(null);
  const [loading, setLoading] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const reqId = useRef(0);
  const listRef = useRef(null);

  const allowed = useMemo(() => searchableTypes(role), [role]);

  // Reset transient state each time the palette opens.
  useEffect(() => {
    if (open) { setQuery(''); setByType(null); setHighlight(0); }
  }, [open]);

  // Run the parallel search when the debounced query changes.
  useEffect(() => {
    if (!debounced) { setByType(null); setLoading(false); return; }
    const id = ++reqId.current;
    setLoading(true);
    Promise.all(
      allowed.map((t) =>
        FETCHERS[t.type]({ search: debounced, limit: PER_GROUP + 1 })
          .then((r) => ({ type: t.type, items: r.items || [], total: r.total ?? 0 }))
          .catch(() => ({ type: t.type, error: true })),
      ),
    ).then((settled) => {
      if (id !== reqId.current) return; // ignore stale responses
      setByType(Object.fromEntries(settled.map((s) => [s.type, s])));
      setLoading(false);
    });
  }, [debounced, allowed]);

  const groups = useMemo(
    () => (debounced && byType ? groupResults(byType, allowed, PER_GROUP) : []),
    [debounced, byType, allowed],
  );

  const navActions = useMemo(() => quickNavActions(role), [role]);

  // Flat navigable list: results when searching, quick-nav actions otherwise.
  const navItems = useMemo(() => {
    if (debounced) return flattenNavigable(groups).map((x) => ({ kind: 'result', ...x }));
    return navActions.map((a) => ({ kind: 'nav', ...a }));
  }, [debounced, groups, navActions]);

  useEffect(() => { setHighlight(navItems.length ? 0 : -1); }, [navItems]);

  // Keep the highlighted row in view.
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-index="${highlight}"]`);
    if (el) el.scrollIntoView({ block: 'nearest' });
  }, [highlight]);

  function activate(entry) {
    if (!entry) return;
    if (entry.kind === 'nav') navigate(entry.route);
    else navigate(`${entry.route}?search=${encodeURIComponent(describe(entry.type, entry.item, refData).term)}`);
    onClose();
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setHighlight((h) => moveHighlight(h, navItems.length, 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlight((h) => moveHighlight(h, navItems.length, -1)); }
    else if (e.key === 'Enter') { e.preventDefault(); activate(navItems[highlight]); }
    else if (e.key === 'Escape') { e.preventDefault(); onClose(); }
  }

  // Render helpers ----------------------------------------------------------
  let cursor = 0; // running flat index across groups

  return (
    <Dialog
      open={open} onClose={onClose} fullWidth maxWidth="sm"
      sx={{ '& .MuiDialog-container': { alignItems: 'flex-start' } }}
      slotProps={{ paper: { sx: { mt: '10vh', borderRadius: 3, overflow: 'hidden' } } }}
    >
      {/* Search input */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 2, py: 1.5, borderBottom: '1px solid', borderColor: 'divider' }}>
        <SearchIcon sx={{ fontSize: 20, color: 'text.disabled' }} />
        <InputBase
          autoFocus fullWidth value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={onKeyDown}
          placeholder="Search projects, deliverables, resources, people…"
          sx={{ fontSize: '0.9375rem' }}
        />
        {loading && <CircularProgress size={16} thickness={5} />}
        {/* Real close control that still shows the Esc hint. Native <button> so
            it's keyboard-reachable (Tab) and activates on Enter/Space. */}
        <Box
          component="button" type="button" onClick={onClose}
          aria-label="Close search" title="Close search (Esc)"
          sx={{
            display: 'inline-flex', alignItems: 'center', gap: 0.5, flexShrink: 0,
            height: 22, px: 0.75, borderRadius: 1,
            border: '1px solid', borderColor: 'divider', bgcolor: 'transparent',
            color: 'text.secondary', cursor: 'pointer', font: 'inherit',
            fontSize: '0.625rem', fontWeight: 600, lineHeight: 1,
            transition: 'background-color 120ms, border-color 120ms, color 120ms',
            '&:hover': { bgcolor: 'action.hover', borderColor: 'text.disabled', color: 'text.primary' },
            '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: '1px' },
          }}
        >
          <CloseIcon sx={{ fontSize: 13 }} />
          Esc
        </Box>
      </Box>

      {/* Results / quick nav */}
      <Box ref={listRef} sx={{ maxHeight: '56vh', overflowY: 'auto', py: 1 }}>
        {!debounced && (
          <>
            <SectionHeader>Quick navigation</SectionHeader>
            {navItems.map((a, i) => (
              <Row key={a.route} index={i} selected={i === highlight}
                onActivate={() => activate(a)} onHover={() => setHighlight(i)}>
                <ArrowIcon sx={{ fontSize: 16, color: 'text.disabled' }} />
                <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{a.label}</Typography>
              </Row>
            ))}
          </>
        )}

        {debounced && groups.map((g) => {
          const base = cursor;
          cursor += g.items.length;
          return (
            <Box key={g.type}>
              <SectionHeader>
                {g.label}
                {g.error
                  ? <Box component="span" sx={{ color: 'error.main', ml: 1, fontWeight: 600 }}>· couldn’t load</Box>
                  : <Box component="span" sx={{ color: 'text.disabled', ml: 1 }}>{g.total}</Box>}
              </SectionHeader>
              {g.items.map((item, i) => {
                const idx = base + i;
                const d = describe(g.type, item, refData);
                return (
                  <Row key={`${g.type}-${item.id}`} index={idx} selected={idx === highlight}
                    onActivate={() => activate({ kind: 'result', type: g.type, route: g.route, item })}
                    onHover={() => setHighlight(idx)}>
                    <Box sx={{ minWidth: 0, flex: 1 }}>
                      <Typography noWrap sx={{ fontSize: '0.8125rem', fontWeight: 600 }}>{d.primary}</Typography>
                      {d.meta && <Box sx={metaSx}>{d.meta}</Box>}
                    </Box>
                  </Row>
                );
              })}
              {g.hasMore && (
                <Box
                  onClick={() => { navigate(`${g.route}?search=${encodeURIComponent(debounced)}`); onClose(); }}
                  sx={{ px: 2, py: 0.75, cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, color: 'primary.main', '&:hover': { textDecoration: 'underline' } }}
                >
                  See all {g.total} in {g.label} →
                </Box>
              )}
              <Divider sx={{ my: 0.5 }} />
            </Box>
          );
        })}

        {debounced && !loading && groups.length === 0 && (
          <Box sx={{ px: 2, py: 4, textAlign: 'center', color: 'text.secondary' }}>
            <Typography sx={{ fontSize: '0.875rem', fontWeight: 600 }}>No results for “{debounced}”</Typography>
            <Typography sx={{ fontSize: '0.8125rem', mt: 0.5 }}>Try a different name or keyword.</Typography>
          </Box>
        )}
      </Box>

      {/* Footer hint */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, px: 2, py: 1, borderTop: '1px solid', borderColor: 'divider', fontSize: '0.6875rem', color: 'text.disabled' }}>
        <span>↑↓ to navigate</span>
        <span>↵ to open</span>
        <Box sx={{ ml: 'auto' }}>{isMac ? '⌘K' : 'Ctrl K'}</Box>
      </Box>
    </Dialog>
  );
}

function SectionHeader({ children }) {
  return (
    <Typography sx={{ px: 2, pt: 1, pb: 0.5, fontSize: '0.6875rem', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'text.disabled' }}>
      {children}
    </Typography>
  );
}
