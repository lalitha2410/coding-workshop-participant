/**
 * Generic "coming soon" page for sections not yet built (projects, deliverables,
 * resources, allocations, users). Keeps the shell fully navigable in the
 * foundation stage while matching the design language.
 */

import { Box, Card, CardContent, Typography } from '@mui/material';
import ConstructionIcon from '@mui/icons-material/HandymanOutlined';
import { PageHeader } from '../components/common/PageHeader';

export default function PlaceholderPage({ title, subtitle }) {
  return (
    <Box>
      <PageHeader title={title} subtitle={subtitle} />
      <Card>
        <CardContent sx={{ py: 8, textAlign: 'center' }}>
          <Box
            sx={{
              width: 52, height: 52, borderRadius: 3, mx: 'auto', mb: 2,
              display: 'grid', placeItems: 'center',
              bgcolor: 'action.selected', color: 'primary.main',
            }}
          >
            <ConstructionIcon />
          </Box>
          <Typography variant="h3" sx={{ mb: 0.5 }}>{title} coming next</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary', maxWidth: 420, mx: 'auto' }}>
            This screen will be built on the Meridian design system in the next stage,
            wired to the {title.toLowerCase()} service.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}
