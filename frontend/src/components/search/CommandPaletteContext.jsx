import { createContext, useContext } from 'react';

// Exposes `open()` to trigger the palette from anywhere (e.g. the top bar).
export const CommandPaletteContext = createContext({ open: () => {} });

export function useCommandPalette() {
  return useContext(CommandPaletteContext);
}
