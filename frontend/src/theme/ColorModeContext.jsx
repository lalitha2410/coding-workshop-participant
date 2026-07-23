/**
 * Light/dark color-mode provider.
 *
 * Persists the chosen mode to localStorage (default: light), builds the LoadBalance
 * theme for that mode, and exposes a toggle. Because components read semantic
 * tokens from the theme, flipping mode is a pure palette swap.
 */

import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { buildTheme } from './theme';

const STORAGE_KEY = 'meridian_mode';
const ColorModeContext = createContext({ mode: 'light', toggle: () => {}, setMode: () => {} });

export function ColorModeProvider({ children }) {
  const [mode, setMode] = useState(() => {
    const saved = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEY) : null;
    return saved === 'dark' || saved === 'light' ? saved : 'light';
  });

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, mode); } catch { /* ignore */ }
  }, [mode]);

  const theme = useMemo(() => buildTheme(mode), [mode]);
  const value = useMemo(
    () => ({ mode, setMode, toggle: () => setMode((m) => (m === 'light' ? 'dark' : 'light')) }),
    [mode],
  );

  return (
    <ColorModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}

export function useColorMode() {
  return useContext(ColorModeContext);
}
