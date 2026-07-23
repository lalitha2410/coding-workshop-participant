import { describe, it, expect } from 'vitest';
import { toCsv, csvFilename } from './csv';

describe('toCsv', () => {
  const cols = [
    { header: 'Name', value: 'name' },
    { header: 'Note', value: 'note' },
    { header: 'Description', value: 'desc' },
    { header: 'Budget Planned', value: 'budget' },
    { header: 'Department', value: (r) => r.dept }, // accessor function
  ];

  it('emits a header row with CRLF line endings', () => {
    const csv = toCsv([], cols);
    expect(csv).toBe('Name,Note,Description,Budget Planned,Department');
    const multi = toCsv([{ name: 'a', note: 'b', desc: 'c', budget: 1, dept: 'd' }], cols);
    expect(multi.split('\r\n')).toHaveLength(2);
  });

  it('quotes values containing commas', () => {
    const csv = toCsv([{ name: 'Apollo, Phase 1' }], [{ header: 'Name', value: 'name' }]);
    expect(csv).toContain('"Apollo, Phase 1"');
  });

  it('escapes quotes by doubling and wrapping', () => {
    const csv = toCsv([{ note: 'He said "go"' }], [{ header: 'Note', value: 'note' }]);
    expect(csv).toContain('"He said ""go"""');
  });

  it('wraps values containing newlines', () => {
    const csv = toCsv([{ desc: 'line1\nline2' }], [{ header: 'Description', value: 'desc' }]);
    expect(csv).toContain('"line1\nline2"');
  });

  it('renders null/undefined as empty and preserves 0', () => {
    const rows = [{ name: 'Simple', note: 'ok', desc: '', budget: 0, dept: null }];
    const line = toCsv(rows, cols).split('\r\n')[1];
    expect(line).toBe('Simple,ok,,0,Data'.replace('Data', '')); // dept null -> empty
    expect(line).toBe('Simple,ok,,0,');
  });

  it('supports accessor functions for computed columns', () => {
    const csv = toCsv([{ dept: 'Data' }], [{ header: 'Department', value: (r) => r.dept.toUpperCase() }]);
    expect(csv.split('\r\n')[1]).toBe('DATA');
  });
});

describe('csvFilename', () => {
  it('builds "<prefix>-YYYY-MM-DD.csv"', () => {
    expect(csvFilename('projects')).toMatch(/^projects-\d{4}-\d{2}-\d{2}\.csv$/);
    expect(csvFilename('over-allocated')).toMatch(/^over-allocated-\d{4}-\d{2}-\d{2}\.csv$/);
  });
});
