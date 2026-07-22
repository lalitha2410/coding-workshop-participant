/**
 * Meridian design tokens.
 *
 * Single source of truth for the "calm operations desk" design system. Every
 * component reads semantic tokens from the MUI theme (theme.palette.*) — never
 * hardcoded hex — so switching light <-> dark is a palette swap, not a redesign.
 *
 * Light is fully tuned; dark is a considered scaffold to be polished later.
 */

// ---- Brand + status hues, expressed per-mode ------------------------------

const light = {
  // Cool-slate neutrals: the quiet 90% of the UI.
  canvas: '#F6F7F9', // app background
  surface: '#FFFFFF', // cards, tables, menus
  surfaceSunken: '#F1F3F6', // table headers, insets
  surfaceRaised: '#FFFFFF',
  hairline: '#E6E9EF', // default borders / dividers
  hairlineStrong: '#D3D8E2', // inputs, emphasis edges
  ink: '#1B1F27', // primary text
  text2: '#5B6472', // secondary text
  textMuted: '#8B94A3', // labels, meta, placeholders

  // Primary — Slate Blue (used sparingly: primary actions, active nav, focus).
  primaryTint: '#ECEFFB',
  primaryLight: '#6E85E8',
  primaryMain: '#3554C7',
  primaryDark: '#2A44A6',
  primaryDarker: '#223787',
  onPrimary: '#FFFFFF',

  // Secondary — Amber (warm accent: highlights, KPI accents, secondary CTAs).
  secondaryTint: '#FBF1DD',
  secondaryLight: '#F0C368',
  secondaryMain: '#E0A106',
  secondaryDark: '#B77F00',
  onSecondary: '#20170A',

  // Semantic status (foreground / tint bg / border). Muted, never neon.
  successFg: '#067A57', successMain: '#0E9F6E', successBg: '#E6F6EF', successBorder: '#BEE7D5',
  warningFg: '#9A6400', warningMain: '#D0900C', warningBg: '#FBF1DD', warningBorder: '#F1DBAE',
  errorFg: '#C4342B', errorMain: '#E5484D', errorBg: '#FBEAEA', errorBorder: '#F3C6C6',
  infoFg: '#1F63C7', infoMain: '#2E77D0', infoBg: '#E8F1FC', infoBorder: '#C4DBF6',
  neutralFg: '#5B6472', neutralBg: '#EEF1F5', neutralBorder: '#DBE0E9',

  // Interaction wash (hover/selected tints on neutral surfaces).
  hover: 'rgba(27, 31, 39, 0.04)',
  selected: 'rgba(53, 84, 199, 0.08)',
  focusRing: 'rgba(53, 84, 199, 0.35)',

  // Shadow ink (tinted, not pure black) — the premium tell.
  shadowInk: '16, 24, 40',
};

const dark = {
  canvas: '#0D1017',
  surface: '#14181F',
  surfaceSunken: '#1A1F28',
  surfaceRaised: '#191E27',
  hairline: '#262C38',
  hairlineStrong: '#333B49',
  ink: '#E7EAF0',
  text2: '#98A2B3',
  textMuted: '#6B7482',

  primaryTint: 'rgba(110, 133, 232, 0.16)',
  primaryLight: '#93A6F0',
  primaryMain: '#6E85E8',
  primaryDark: '#5570D8',
  primaryDarker: '#455FC0',
  onPrimary: '#0B1020',

  secondaryTint: 'rgba(232, 179, 62, 0.16)',
  secondaryLight: '#F1CB78',
  secondaryMain: '#E8B33E',
  secondaryDark: '#C9971F',
  onSecondary: '#20170A',

  successFg: '#4FD1A5', successMain: '#2FB587', successBg: 'rgba(47, 181, 135, 0.14)', successBorder: 'rgba(47, 181, 135, 0.30)',
  warningFg: '#E6B860', warningMain: '#D9A23C', warningBg: 'rgba(217, 162, 60, 0.14)', warningBorder: 'rgba(217, 162, 60, 0.30)',
  errorFg: '#F08A8A', errorMain: '#E5686C', errorBg: 'rgba(229, 104, 108, 0.14)', errorBorder: 'rgba(229, 104, 108, 0.30)',
  infoFg: '#7FB0F0', infoMain: '#4F91E5', infoBg: 'rgba(79, 145, 229, 0.14)', infoBorder: 'rgba(79, 145, 229, 0.30)',
  neutralFg: '#98A2B3', neutralBg: 'rgba(152, 162, 179, 0.12)', neutralBorder: 'rgba(152, 162, 179, 0.24)',

  hover: 'rgba(231, 234, 240, 0.05)',
  selected: 'rgba(110, 133, 232, 0.16)',
  focusRing: 'rgba(110, 133, 232, 0.45)',

  shadowInk: '0, 0, 0',
};

// ---- Shared scalar tokens (mode-independent) ------------------------------

export const radius = {
  chip: 6,
  sm: 8, // inputs, buttons
  md: 12, // cards, panels, menus
  lg: 16, // modals
  pill: 999,
};

export const fontFamily = {
  sans: '"Inter Variable", Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  mono: '"JetBrains Mono Variable", "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace',
};

// Sidebar geometry, shared across shell + layout math.
export const layout = {
  sidebarWidth: 240,
  sidebarCollapsed: 72,
  topBarHeight: 60,
  contentMaxWidth: 1520,
};

export function palette(mode) {
  return mode === 'dark' ? dark : light;
}
