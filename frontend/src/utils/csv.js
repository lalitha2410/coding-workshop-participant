/**
 * Shared CSV export utility — one place for CSV generation + download, used by
 * every list page's Export button (no per-page copy-paste).
 *
 * `columns` is an array of { header, value } where `value` is either a field key
 * (string) or an accessor function (row) => cellValue.
 */

// RFC 4180 escaping: quote a field that contains a comma, quote, CR, or LF, and
// double any interior quotes.
function escapeCell(value) {
  if (value === null || value === undefined) return '';
  const s = String(value);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function cellValue(row, column) {
  const v = typeof column.value === 'function' ? column.value(row) : row[column.value];
  return escapeCell(v);
}

/** Convert rows + column defs into a CSV string (CRLF line endings). */
export function toCsv(rows, columns) {
  const header = columns.map((c) => escapeCell(c.header)).join(',');
  const lines = rows.map((row) => columns.map((c) => cellValue(row, c)).join(','));
  return [header, ...lines].join('\r\n');
}

/** `${prefix}-YYYY-MM-DD.csv` */
export function csvFilename(prefix) {
  const date = new Date().toISOString().slice(0, 10);
  return `${prefix}-${date}.csv`;
}

/** Trigger a browser download of `csv` as `filename` (UTF-8 BOM for Excel). */
export function downloadCsv(filename, csv) {
  const blob = new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
