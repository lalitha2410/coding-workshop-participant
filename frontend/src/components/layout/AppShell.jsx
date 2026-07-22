/**
 * Responsive application shell: permanent 240px sidebar on desktop, off-canvas
 * Drawer on mobile, a sticky top bar, and a constrained content area that hosts
 * the routed pages via <Outlet />.
 */

import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Box, Drawer } from '@mui/material';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import { layout } from '../../theme/tokens';

export default function AppShell() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const W = layout.sidebarWidth;

  return (
    <Box sx={{ minHeight: '100dvh', bgcolor: 'background.default' }}>
      {/* Permanent sidebar (desktop) */}
      <Box
        component="nav"
        sx={{
          display: { xs: 'none', md: 'block' },
          width: W, flexShrink: 0,
          position: 'fixed', top: 0, left: 0, bottom: 0,
          borderRight: '1px solid', borderColor: 'divider',
          zIndex: (t) => t.zIndex.appBar + 1,
        }}
      >
        <Sidebar />
      </Box>

      {/* Off-canvas drawer (mobile) */}
      <Drawer
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{ display: { xs: 'block', md: 'none' } }}
        slotProps={{ paper: { sx: { width: W, borderRight: '1px solid', borderColor: 'divider' } } }}
      >
        <Sidebar onNavigate={() => setMobileOpen(false)} />
      </Drawer>

      {/* Main column */}
      <Box sx={{ ml: { md: `${W}px` }, display: 'flex', flexDirection: 'column', minHeight: '100dvh' }}>
        <TopBar onMenuClick={() => setMobileOpen(true)} />
        <Box component="main" sx={{ flex: 1, px: { xs: 2, md: 3 }, py: { xs: 2.5, md: 3 } }}>
          <Box sx={{ maxWidth: layout.contentMaxWidth, mx: 'auto', width: '100%' }}>
            <Outlet />
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
