/**
 * Standard loading / error / empty handling for data views.
 * - loading -> a skeleton block (caller supplies shape, or a default)
 * - error   -> an inline Alert with a Retry action
 * - empty   -> a calm empty state
 * - else    -> children
 */

import { Box, Alert, Button, Typography, Skeleton, Stack } from '@mui/material';
import InboxIcon from '@mui/icons-material/InboxOutlined';

export function TableSkeleton({ rows = 6, cols = 4 }) {
  return (
    <Box sx={{ p: 2 }}>
      {Array.from({ length: rows }).map((_, r) => (
        <Box key={r} sx={{ display: 'flex', gap: 2, py: 1.25, alignItems: 'center' }}>
          {Array.from({ length: cols }).map((_, c) => (
            <Skeleton key={c} variant="rounded" height={16} sx={{ flex: c === 0 ? 2 : 1 }} />
          ))}
        </Box>
      ))}
    </Box>
  );
}

export function EmptyState({ title = 'Nothing here yet', message, action }) {
  return (
    <Box sx={{ py: 7, textAlign: 'center' }}>
      <Box sx={{ width: 46, height: 46, borderRadius: 2.5, mx: 'auto', mb: 1.5, display: 'grid', placeItems: 'center', bgcolor: 'action.selected', color: 'primary.main' }}>
        <InboxIcon />
      </Box>
      <Typography variant="h4" sx={{ mb: 0.5 }}>{title}</Typography>
      {message && <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: 380, mx: 'auto', mb: action ? 2 : 0 }}>{message}</Typography>}
      {action}
    </Box>
  );
}

export function ErrorState({ error, onRetry }) {
  const message = error?.message || 'Something went wrong.';
  return (
    <Box sx={{ p: 2 }}>
      <Alert
        severity="error"
        action={onRetry && <Button color="inherit" size="small" onClick={onRetry}>Retry</Button>}
      >
        {message}
      </Alert>
    </Box>
  );
}

/** Convenience wrapper: pick the right state for a list view. */
export function ResultStates({ loading, error, isEmpty, onRetry, skeleton, empty, children }) {
  if (loading) return skeleton ?? <TableSkeleton />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (isEmpty) return empty ?? <EmptyState />;
  return children;
}

export { Stack };
