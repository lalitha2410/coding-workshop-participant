/**
 * Drives a paginated list endpoint that returns {items,total,limit,offset}.
 * Manages offset + filters, cancels stale responses, and exposes refetch.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

export function usePaginatedList(fetcher, { limit = 20, initialFilters = {} } = {}) {
  const [offset, setOffset] = useState(0);
  const [filters, setFiltersState] = useState(initialFilters);
  const [state, setState] = useState({ items: [], total: 0, loading: true, error: null });
  const reqId = useRef(0);

  const load = useCallback(async () => {
    const id = ++reqId.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const res = await fetcher({ ...filters, limit, offset });
      if (id === reqId.current) {
        setState({ items: res.items || [], total: res.total || 0, loading: false, error: null });
      }
    } catch (error) {
      if (id === reqId.current) setState((s) => ({ ...s, loading: false, error }));
    }
  }, [fetcher, filters, limit, offset]);

  useEffect(() => { load(); }, [load]);

  // Changing a filter resets to the first page.
  const setFilters = useCallback((next) => {
    setOffset(0);
    setFiltersState((prev) => (typeof next === 'function' ? next(prev) : { ...prev, ...next }));
  }, []);

  return { ...state, limit, offset, filters, setFilters, setOffset, refetch: load };
}
