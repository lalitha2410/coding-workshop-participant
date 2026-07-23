/**
 * Builds the LoadBalance MUI theme from design tokens for a given mode.
 *
 * The heavy component overrides here are what make MUI stop looking like MUI:
 * hairline-first surfaces, no ripple, crisp focus rings, tinted low-opacity
 * shadows, no uppercase buttons, and status-aware inputs/chips/tables.
 */

import { createTheme, alpha } from '@mui/material/styles';
import { palette, radius, fontFamily, layout } from './tokens';

// Tinted, low-opacity, tight shadow ramp (index 0 = none).
function buildShadows(ink) {
  const s = (a) => `0 1px 2px rgba(${ink}, ${a[0]}), 0 ${a[1]}px ${a[2]}px rgba(${ink}, ${a[3]})`;
  const none = 'none';
  return [
    none,
    s([0.04, 1, 3, 0.06]), // 1 raised card / hover
    s([0.04, 2, 6, 0.06]), // 2
    s([0.05, 4, 12, 0.08]), // 3 popover / menu
    s([0.05, 6, 16, 0.09]), // 4
    s([0.06, 8, 20, 0.10]), // 5
    ...Array(19).fill(s([0.07, 16, 40, 0.12])), // 6..24 modal-class
  ];
}

export function buildTheme(mode) {
  const c = palette(mode);
  const isDark = mode === 'dark';

  return createTheme({
    palette: {
      mode,
      primary: { main: c.primaryMain, light: c.primaryLight, dark: c.primaryDark, contrastText: c.onPrimary },
      secondary: { main: c.secondaryMain, light: c.secondaryLight, dark: c.secondaryDark, contrastText: c.onSecondary },
      success: { main: c.successMain, light: c.successBg, dark: c.successFg, contrastText: '#FFFFFF' },
      warning: { main: c.warningMain, light: c.warningBg, dark: c.warningFg, contrastText: '#20170A' },
      error: { main: c.errorMain, light: c.errorBg, dark: c.errorFg, contrastText: '#FFFFFF' },
      info: { main: c.infoMain, light: c.infoBg, dark: c.infoFg, contrastText: '#FFFFFF' },
      background: { default: c.canvas, paper: c.surface },
      text: { primary: c.ink, secondary: c.text2, disabled: c.textMuted },
      divider: c.hairline,
      action: {
        hover: c.hover,
        selected: c.selected,
        active: c.text2,
        disabled: c.textMuted,
        focus: c.focusRing,
      },
      // Custom slots consumed via theme.palette.meridian.* in components.
      meridian: { ...c, radius, fontFamily, layout },
    },

    shape: { borderRadius: radius.md },
    spacing: 8,
    shadows: buildShadows(c.shadowInk),

    typography: {
      fontFamily: fontFamily.sans,
      // Slightly tighter, crisper defaults than MUI's 16/400.
      htmlFontSize: 16,
      fontSize: 14,
      h1: { fontSize: '1.75rem', fontWeight: 700, lineHeight: 1.2, letterSpacing: '-0.02em' },
      h2: { fontSize: '1.375rem', fontWeight: 700, lineHeight: 1.25, letterSpacing: '-0.015em' },
      h3: { fontSize: '1.125rem', fontWeight: 600, lineHeight: 1.35, letterSpacing: '-0.01em' },
      h4: { fontSize: '1rem', fontWeight: 600, lineHeight: 1.4 },
      h5: { fontSize: '0.9375rem', fontWeight: 600, lineHeight: 1.4 },
      h6: { fontSize: '0.875rem', fontWeight: 600, lineHeight: 1.4 },
      subtitle1: { fontSize: '0.875rem', fontWeight: 500, lineHeight: 1.5 },
      subtitle2: { fontSize: '0.8125rem', fontWeight: 500, lineHeight: 1.45, color: c.text2 },
      body1: { fontSize: '0.875rem', fontWeight: 400, lineHeight: 1.55 },
      body2: { fontSize: '0.8125rem', fontWeight: 400, lineHeight: 1.5 },
      button: { fontSize: '0.875rem', fontWeight: 600, textTransform: 'none', letterSpacing: 0 },
      caption: { fontSize: '0.75rem', fontWeight: 400, lineHeight: 1.4, color: c.text2 },
      overline: {
        fontSize: '0.6875rem', fontWeight: 600, lineHeight: 1.4,
        letterSpacing: '0.06em', textTransform: 'uppercase', color: c.textMuted,
      },
    },

    components: {
      // Crisp, non-Material feel everywhere: no ripple by default.
      MuiButtonBase: { defaultProps: { disableRipple: true } },

      MuiCssBaseline: {
        styleOverrides: {
          ':root': { colorScheme: mode },
          body: {
            backgroundColor: c.canvas,
            color: c.ink,
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
            fontFeatureSettings: '"cv11", "ss01"',
          },
          '*::-webkit-scrollbar': { width: 10, height: 10 },
          '*::-webkit-scrollbar-thumb': {
            backgroundColor: c.hairlineStrong, borderRadius: 999,
            border: `2px solid ${c.canvas}`,
          },
          '*::-webkit-scrollbar-thumb:hover': { backgroundColor: c.textMuted },
          // Tabular figures wherever numbers matter.
          '.tnum': { fontVariantNumeric: 'tabular-nums' },
          '.mono': { fontFamily: fontFamily.mono, fontVariantNumeric: 'tabular-nums' },
        },
      },

      MuiPaper: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: { backgroundImage: 'none' },
          outlined: { borderColor: c.hairline },
        },
      },

      MuiCard: {
        defaultProps: { variant: 'outlined' },
        styleOverrides: {
          root: {
            borderColor: c.hairline,
            borderRadius: radius.md,
            backgroundColor: c.surface,
            transition: 'border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease',
          },
        },
      },
      MuiCardContent: { styleOverrides: { root: { padding: 20, '&:last-child': { paddingBottom: 20 } } } },

      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: {
            borderRadius: radius.sm,
            paddingInline: 14,
            minHeight: 38,
            fontWeight: 600,
            transition: 'background-color 130ms ease, border-color 130ms ease, box-shadow 130ms ease, transform 130ms ease',
            '&:focus-visible': { boxShadow: `0 0 0 3px ${c.focusRing}` },
          },
          sizeSmall: { minHeight: 32, paddingInline: 10, fontSize: '0.8125rem' },
          sizeLarge: { minHeight: 44, paddingInline: 18, fontSize: '0.9375rem' },
          containedPrimary: {
            backgroundColor: c.primaryMain,
            color: c.onPrimary,
            '&:hover': { backgroundColor: c.primaryDark, transform: 'translateY(-1px)' },
            '&:active': { backgroundColor: c.primaryDarker, transform: 'translateY(0)' },
          },
          outlined: {
            borderColor: c.hairlineStrong,
            color: c.ink,
            backgroundColor: c.surface,
            '&:hover': { borderColor: c.textMuted, backgroundColor: c.hover },
          },
          text: {
            color: c.text2,
            '&:hover': { backgroundColor: c.hover, color: c.ink },
          },
        },
      },

      MuiIconButton: {
        styleOverrides: {
          root: {
            borderRadius: radius.sm,
            color: c.text2,
            transition: 'background-color 130ms ease, color 130ms ease',
            '&:hover': { backgroundColor: c.hover, color: c.ink },
            '&:focus-visible': { boxShadow: `0 0 0 3px ${c.focusRing}` },
          },
        },
      },

      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            borderRadius: radius.sm,
            backgroundColor: c.surface,
            fontSize: '0.875rem',
            transition: 'box-shadow 130ms ease, border-color 130ms ease',
            '& .MuiOutlinedInput-notchedOutline': { borderColor: c.hairlineStrong },
            '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: c.textMuted },
            '&.Mui-focused': { boxShadow: `0 0 0 3px ${c.focusRing}` },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: c.primaryMain, borderWidth: 1 },
            '&.Mui-error.Mui-focused': { boxShadow: `0 0 0 3px ${alpha(c.errorMain, 0.28)}` },
          },
          input: {
            padding: '10px 12px',
            '&::placeholder': { color: c.textMuted, opacity: 1 },
          },
        },
      },
      MuiInputLabel: {
        styleOverrides: {
          root: {
            fontSize: '0.8125rem', fontWeight: 500, color: c.text2,
            '&.Mui-focused': { color: c.primaryMain },
          },
        },
      },
      MuiFormHelperText: { styleOverrides: { root: { marginLeft: 2, fontSize: '0.75rem' } } },

      MuiChip: {
        styleOverrides: {
          root: { borderRadius: radius.chip, fontWeight: 600, fontSize: '0.75rem', height: 24 },
          outlined: { borderColor: c.hairline },
          label: { paddingInline: 8 },
        },
      },

      MuiMenu: {
        styleOverrides: {
          paper: {
            borderRadius: radius.md,
            border: `1px solid ${c.hairline}`,
            boxShadow: `0 4px 12px rgba(${c.shadowInk}, 0.10)`,
            marginTop: 6,
          },
          list: { padding: 6 },
        },
      },
      MuiMenuItem: {
        styleOverrides: {
          root: {
            borderRadius: radius.sm,
            fontSize: '0.8125rem',
            minHeight: 36,
            gap: 10,
            '&:hover': { backgroundColor: c.hover },
            '&.Mui-selected': { backgroundColor: c.selected },
            '&.Mui-selected:hover': { backgroundColor: c.selected },
          },
        },
      },

      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: isDark ? '#000000' : '#1B1F27',
            color: '#FFFFFF',
            fontSize: '0.75rem', fontWeight: 500,
            borderRadius: radius.sm, padding: '6px 10px',
          },
          arrow: { color: isDark ? '#000000' : '#1B1F27' },
        },
      },

      MuiDivider: { styleOverrides: { root: { borderColor: c.hairline } } },

      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: radius.sm,
            transition: 'background-color 120ms ease, color 120ms ease',
            '&:hover': { backgroundColor: c.hover },
            '&.Mui-selected': { backgroundColor: c.selected, color: c.primaryMain },
            '&.Mui-selected:hover': { backgroundColor: c.selected },
          },
        },
      },

      MuiTableHead: {
        styleOverrides: { root: { backgroundColor: c.surfaceSunken } },
      },
      MuiTableCell: {
        styleOverrides: {
          root: { borderBottomColor: c.hairline, fontSize: '0.8125rem', padding: '12px 16px' },
          head: {
            color: c.textMuted, fontWeight: 600, fontSize: '0.6875rem',
            letterSpacing: '0.06em', textTransform: 'uppercase',
          },
        },
      },
      MuiTableRow: {
        styleOverrides: { root: { '&:hover': { backgroundColor: c.hover } } },
      },

      MuiLink: {
        defaultProps: { underline: 'hover' },
        styleOverrides: { root: { color: c.primaryMain, fontWeight: 500 } },
      },

      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: radius.sm, fontSize: '0.8125rem', border: '1px solid transparent' },
          standardError: { backgroundColor: c.errorBg, color: c.errorFg, borderColor: c.errorBorder },
          standardSuccess: { backgroundColor: c.successBg, color: c.successFg, borderColor: c.successBorder },
          standardWarning: { backgroundColor: c.warningBg, color: c.warningFg, borderColor: c.warningBorder },
          standardInfo: { backgroundColor: c.infoBg, color: c.infoFg, borderColor: c.infoBorder },
        },
      },

      MuiSkeleton: {
        styleOverrides: { root: { backgroundColor: c.surfaceSunken, borderRadius: radius.sm } },
      },
    },
  });
}
