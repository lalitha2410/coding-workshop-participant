/**
 * Labeled input: label sits above the field (dense-form friendly), matching the
 * Meridian form direction. Thin wrapper over MUI TextField.
 */

import { Box, Typography, TextField } from '@mui/material';

export function FormField({ label, id, ...props }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
      <Typography
        component="label"
        htmlFor={id}
        sx={{ fontSize: '0.8125rem', fontWeight: 600, color: 'text.secondary' }}
      >
        {label}
      </Typography>
      <TextField id={id} fullWidth size="small" variant="outlined" {...props} />
    </Box>
  );
}
