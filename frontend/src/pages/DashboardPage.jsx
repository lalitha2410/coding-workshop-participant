/**
 * Dashboard — fully live. Every number and list comes from the backend:
 * project totals/budgets from the projects list, deliverable counts from totals,
 * and capacity/over-allocation from the /allocations analytics endpoints.
 */

import { Box, Card, CardContent, Typography, Button, Divider, Skeleton } from '@mui/material';
import AddIcon from '@mui/icons-material/AddRounded';
import ProjectsIcon from '@mui/icons-material/FolderOutlined';
import DeliverablesIcon from '@mui/icons-material/ChecklistOutlined';
import BudgetIcon from '@mui/icons-material/AccountBalanceWalletOutlined';
import OverIcon from '@mui/icons-material/WarningAmberRounded';
import { useNavigate } from 'react-router-dom';
import { PageHeader } from '../components/common/PageHeader';
import { StatCard } from '../components/common/StatCard';
import { CapacityMeter } from '../components/common/CapacityMeter';
import { StatusChip, RiskChip } from '../components/data/StatusChip';
import { ErrorState } from '../components/data/ResultStates';
import { useAsync } from '../hooks/useAsync';
import { listProjects } from '../api/projects';
import { listDeliverables } from '../api/deliverables';
import { overAllocated, allocationSummary } from '../api/allocations';
import { fmtMoney, fmtDate, isAtRisk } from '../utils/format';
import { useAuth } from '../auth/AuthContext';
import { can } from '../auth/roles';

function loadDashboard() {
  return Promise.all([
    listProjects({ limit: 200 }),
    listDeliverables({ limit: 1 }),
    listDeliverables({ status: 'completed', limit: 1 }),
    overAllocated(),
    allocationSummary(),
  ]).then(([projects, delivAll, delivDone, over, summary]) => ({
    projects: projects.items || [],
    projectTotal: projects.total || 0,
    delivOpen: (delivAll.total || 0) - (delivDone.total || 0),
    delivDone: delivDone.total || 0,
    over: over || [],
    summary: summary || [],
  }));
}

function KpiSkeletons() {
  return (
    <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, mb: 2 }}>
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i}><CardContent><Skeleton width={90} height={14} /><Skeleton width={70} height={40} sx={{ my: 0.5 }} /><Skeleton width={110} height={14} /></CardContent></Card>
      ))}
    </Box>
  );
}

export default function DashboardPage() {
  const { user, role } = useAuth();
  const navigate = useNavigate();
  const { data, loading, error, refetch } = useAsync(loadDashboard, []);

  const header = (
    <PageHeader
      title={`Good to see you, ${user?.username || 'there'}`}
      subtitle="Portfolio health across ACME — projects, budgets, and team capacity."
      actions={can(role, 'create') && (
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => navigate('/projects')}>New project</Button>
      )}
    />
  );

  if (error) {
    return <Box>{header}<Card><ErrorState error={error} onRetry={refetch} /></Card></Box>;
  }

  if (loading || !data) {
    return (
      <Box>
        {header}
        <KpiSkeletons />
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '5fr 7fr' } }}>
          <Card><CardContent><Skeleton height={24} width={140} /><Skeleton height={120} sx={{ mt: 2 }} /></CardContent></Card>
          <Card><CardContent><Skeleton height={24} width={140} /><Skeleton height={200} sx={{ mt: 2 }} /></CardContent></Card>
        </Box>
      </Box>
    );
  }

  const { projects, projectTotal, delivOpen, delivDone, over, summary } = data;
  const activeCount = projects.filter((p) => p.status === 'active').length;
  const planned = projects.reduce((s, p) => s + (Number(p.budget_planned) || 0), 0);
  const consumed = projects.reduce((s, p) => s + (Number(p.budget_consumed) || 0), 0);
  const budgetPct = planned > 0 ? Math.round((consumed / planned) * 100) : 0;
  const capacity = [...summary].sort((a, b) => b.total_allocation_pct - a.total_allocation_pct).slice(0, 6);
  const recent = [...projects]
    .sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0))
    .slice(0, 6);

  return (
    <Box>
      {header}

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, mb: 2 }}>
        <StatCard label="Active projects" value={activeCount} icon={ProjectsIcon} caption={`of ${projectTotal} total`} />
        <StatCard label="Deliverables open" value={delivOpen} icon={DeliverablesIcon} caption={`${delivDone} completed`} />
        <StatCard label="Budget consumed" value={budgetPct} unit="%" icon={BudgetIcon} caption={`${fmtMoney(consumed)} of ${fmtMoney(planned)}`} />
        <StatCard label="Over-allocated" value={over.length} icon={OverIcon}
          delta={over.length ? 'needs review' : 'all clear'} deltaTone={over.length ? 'down' : 'up'} caption="people >100%" />
      </Box>

      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '5fr 7fr' } }}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h3">Team capacity</Typography>
              {over.length > 0 && (
                <Typography variant="caption" sx={{ color: 'error.dark', fontWeight: 700 }}>{over.length} over-allocated</Typography>
              )}
            </Box>
            {capacity.length === 0 ? (
              <Typography variant="body2" sx={{ color: 'text.secondary' }}>No allocations yet.</Typography>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {capacity.map((r) => (
                  <CapacityMeter key={r.resource_id} name={r.resource_name}
                    subtitle={`${r.project_count} project${r.project_count === 1 ? '' : 's'}`}
                    pct={r.total_allocation_pct} />
                ))}
              </Box>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent sx={{ p: 0 }}>
            <Box sx={{ px: 2.5, py: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="h3">Recent projects</Typography>
              <Button size="small" variant="text" onClick={() => navigate('/projects')}>View all</Button>
            </Box>
            <Divider />
            <Box sx={{ display: 'grid', gridTemplateColumns: '2.2fr 1fr 1.3fr 1fr', px: 2.5, py: 1.25, bgcolor: 'background.default' }}>
              {['Project', 'Department', 'Status', 'Budget'].map((h) => (
                <Typography key={h} variant="overline" sx={{ textAlign: h === 'Budget' ? 'right' : 'left' }}>{h}</Typography>
              ))}
            </Box>
            {recent.map((p, i) => (
              <Box key={p.id} sx={{ display: 'grid', gridTemplateColumns: '2.2fr 1fr 1.3fr 1fr', alignItems: 'center', px: 2.5, py: 1.5, borderTop: i === 0 ? 'none' : '1px solid', borderColor: 'divider', cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }} onClick={() => navigate('/projects')}>
                <Typography sx={{ fontSize: '0.8125rem', fontWeight: 600 }} noWrap>{p.name}</Typography>
                <Typography sx={{ fontSize: '0.8125rem', color: 'text.secondary' }} noWrap>{p.department || '—'}</Typography>
                <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center', flexWrap: 'wrap' }}>
                  <StatusChip status={p.status} />
                  {isAtRisk(p) && <RiskChip />}
                </Box>
                <Typography className="mono" sx={{ fontSize: '0.8125rem', fontWeight: 600, textAlign: 'right' }}>
                  {fmtMoney(p.budget_consumed)}
                </Typography>
              </Box>
            ))}
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
}
