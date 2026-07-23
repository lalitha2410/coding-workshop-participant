/**
 * Owns command-palette open state, the global Cmd/Ctrl+K shortcut, and a one-time
 * prefetch of reference data (project/resource names + allocation totals) used to
 * enrich results. Mounted inside AppShell so it has Router + Auth context.
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { CommandPaletteContext } from './CommandPaletteContext';
import { CommandPalette } from './CommandPalette';
import { listProjects } from '../../api/projects';
import { listResources } from '../../api/resources';
import { allocationSummary } from '../../api/allocations';

export function CommandPaletteProvider({ children }) {
  const [open, setOpen] = useState(false);
  const [refData, setRefData] = useState(null);
  const { role } = useAuth();
  const navigate = useNavigate();

  // Load the name maps + allocation totals once (best-effort; the palette still
  // works without them, just with less context in each row).
  const loadRefData = useCallback(async () => {
    if (refData) return;
    const [projects, resources, summary] = await Promise.all([
      listProjects({ limit: 200 }).catch(() => ({ items: [] })),
      listResources({ limit: 200 }).catch(() => ({ items: [] })),
      allocationSummary().catch(() => []),
    ]);
    setRefData({
      projectName: Object.fromEntries((projects.items || []).map((p) => [p.id, p.name])),
      resourceName: Object.fromEntries((resources.items || []).map((r) => [r.id, r.name])),
      allocTotals: Object.fromEntries(
        (Array.isArray(summary) ? summary : []).map((s) => [s.resource_id, Number(s.total_allocation_pct)]),
      ),
    });
  }, [refData]);

  const openPalette = useCallback(() => { setOpen(true); loadRefData(); }, [loadRefData]);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        setOpen((o) => !o);
        loadRefData();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [loadRefData]);

  return (
    <CommandPaletteContext.Provider value={{ open: openPalette }}>
      {children}
      <CommandPalette
        open={open}
        onClose={() => setOpen(false)}
        role={role}
        navigate={navigate}
        refData={refData}
      />
    </CommandPaletteContext.Provider>
  );
}
