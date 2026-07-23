/**
 * Bridges a list page's `?search=` URL param to its paginated-list filter.
 *
 * The URL is the source of truth, so the command palette can drive a list page
 * by navigating to `/projects?search=Apollo` — the box fills in and the list
 * filters, even when the page is already mounted. Typing in the box updates the
 * URL (replace, no history spam), which flows back into the list filter.
 */

import { useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

export function useUrlSearchFilter(list, key = 'search') {
  const [params, setParams] = useSearchParams();
  const value = params.get(key) || '';

  // Push the URL value into the list filter whenever it actually differs, so we
  // don't trigger a redundant refetch on the common (no-search) mount.
  useEffect(() => {
    const current = list.filters[key] || '';
    if (value !== current) list.setFilters({ [key]: value || undefined });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const setValue = useCallback((next) => {
    setParams((prev) => {
      const p = new URLSearchParams(prev);
      if (next) p.set(key, next);
      else p.delete(key);
      return p;
    }, { replace: true });
  }, [setParams, key]);

  return [value, setValue];
}
