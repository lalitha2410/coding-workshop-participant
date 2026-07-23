/**
 * Fetch ALL rows matching `filters` from a paginated list endpoint, following
 * the {items,total,limit,offset} envelope. Used by CSV export so the file
 * contains every matching row — not just the current page — while respecting
 * the active filters/search. Pages are fetched at the backend's max limit (200).
 */

const PAGE_SIZE = 200;

export async function fetchAllRows(listFn, filters = {}) {
  const first = await listFn({ ...filters, limit: PAGE_SIZE, offset: 0 });
  let items = first.items || [];
  const total = first.total ?? items.length;

  while (items.length < total) {
    const next = await listFn({ ...filters, limit: PAGE_SIZE, offset: items.length });
    const page = next.items || [];
    if (page.length === 0) break; // safety: avoid an infinite loop on inconsistent totals
    items = items.concat(page);
  }
  return items;
}
