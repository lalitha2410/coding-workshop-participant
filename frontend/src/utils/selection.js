/**
 * Row-selection logic for bulk actions on list tables. The pure helpers are unit
 * tested; `useSelection` wraps them with state and the "clear on page/filter
 * change" behaviour.
 *
 * Selection is always scoped to the CURRENT page — it clears whenever the page
 * or filters change (via `resetKey`), so the selected set only ever holds ids
 * that are visible right now. "Select all" means "all selectable rows on this
 * page".
 */

import { useCallback, useEffect, useMemo, useState } from 'react';

/** Ids of the rows on this page that may be selected (respects `isSelectable`). */
export function pageSelectableIds(items, isSelectable) {
  return items.filter((it) => !isSelectable || isSelectable(it)).map((it) => it.id);
}

/** Return a new Set with `id` toggled. */
export function toggleId(selected, id) {
  const next = new Set(selected);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/**
 * Toggle the whole page: if every selectable row is already selected, clear
 * them; otherwise select them all. Only touches `pageIds`.
 */
export function toggleAll(selected, pageIds) {
  const allOn = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const next = new Set(selected);
  if (allOn) pageIds.forEach((id) => next.delete(id));
  else pageIds.forEach((id) => next.add(id));
  return next;
}

/** Derive header-checkbox state from the selected set and this page's ids. */
export function selectionSummary(selected, pageIds) {
  const count = pageIds.reduce((n, id) => (selected.has(id) ? n + 1 : n), 0);
  const allSelected = pageIds.length > 0 && count === pageIds.length;
  const someSelected = count > 0 && !allSelected;
  return { count, allSelected, someSelected };
}

export function useSelection(items, resetKey, isSelectable) {
  const [selected, setSelected] = useState(() => new Set());

  // Clear the selection whenever the page or filters change.
  useEffect(() => { setSelected(new Set()); }, [resetKey]);

  const pageIds = useMemo(() => pageSelectableIds(items, isSelectable), [items, isSelectable]);
  const { count, allSelected, someSelected } = selectionSummary(selected, pageIds);
  const selectedItems = useMemo(() => items.filter((it) => selected.has(it.id)), [items, selected]);

  const toggle = useCallback((id) => setSelected((s) => toggleId(s, id)), []);
  const toggleAllOnPage = useCallback(() => setSelected((s) => toggleAll(s, pageIds)), [pageIds]);
  const clear = useCallback(() => setSelected(new Set()), []);

  return {
    count,
    allSelected,
    someSelected,
    selectedItems,
    isSelected: (id) => selected.has(id),
    toggle,
    toggleAll: toggleAllOnPage,
    clear,
  };
}
