/** "Showing X–Y of Z" with Prev/Next, driven by total/limit/offset. */

import { Box, Typography, Button } from '@mui/material';
import ChevronLeft from '@mui/icons-material/ChevronLeftRounded';
import ChevronRight from '@mui/icons-material/ChevronRightRounded';

export function PaginationBar({ total, limit, offset, onOffsetChange, itemCount }) {
  if (!total) return null;
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + (itemCount ?? limit), total);
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2, py: 1.5, borderTop: '1px solid', borderColor: 'divider' }}>
      <Typography variant="caption" className="tnum" sx={{ color: 'text.secondary' }}>
        Showing <strong>{start}–{end}</strong> of <strong>{total}</strong>
      </Typography>
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button size="small" variant="outlined" startIcon={<ChevronLeft />} disabled={!canPrev}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}>Prev</Button>
        <Button size="small" variant="outlined" endIcon={<ChevronRight />} disabled={!canNext}
          onClick={() => onOffsetChange(offset + limit)}>Next</Button>
      </Box>
    </Box>
  );
}
