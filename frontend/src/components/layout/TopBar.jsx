/**
 * Slim top bar: mobile menu button + page title on the left; theme toggle and
 * user menu (name, role, logout) on the right.
 */

import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Box, IconButton, Typography, Menu, MenuItem, Avatar, Divider, Chip, Tooltip, ListItemIcon,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/MenuRounded';
import LightModeIcon from '@mui/icons-material/LightModeOutlined';
import DarkModeIcon from '@mui/icons-material/DarkModeOutlined';
import LogoutIcon from '@mui/icons-material/LogoutRounded';
import { useColorMode } from '../../theme/ColorModeContext';
import { useAuth } from '../../auth/AuthContext';
import { titleForPath } from './navConfig';

function initials(name = '') {
  const parts = name.trim().split(/[\s._-]+/).filter(Boolean);
  return ((parts[0]?.[0] || '') + (parts[1]?.[0] || '')).toUpperCase() || name[0]?.toUpperCase() || '?';
}

export default function TopBar({ onMenuClick }) {
  const { mode, toggle } = useColorMode();
  const { user, role, logout } = useAuth();
  const { pathname } = useLocation();
  const [anchor, setAnchor] = useState(null);

  return (
    <Box
      component="header"
      sx={{
        height: 60, flexShrink: 0, px: { xs: 1.5, md: 3 },
        display: 'flex', alignItems: 'center', gap: 1,
        bgcolor: 'background.paper',
        borderBottom: '1px solid', borderColor: 'divider',
        position: 'sticky', top: 0, zIndex: (t) => t.zIndex.appBar,
      }}
    >
      <IconButton onClick={onMenuClick} edge="start" sx={{ display: { md: 'none' } }} aria-label="Open navigation">
        <MenuIcon />
      </IconButton>

      <Typography variant="h3" sx={{ fontSize: '1.0625rem', flex: 1, minWidth: 0, noWrap: true }} noWrap>
        {titleForPath(pathname)}
      </Typography>

      <Tooltip title={mode === 'light' ? 'Switch to dark' : 'Switch to light'}>
        <IconButton onClick={toggle} aria-label="Toggle color mode">
          {mode === 'light' ? <DarkModeIcon sx={{ fontSize: 20 }} /> : <LightModeIcon sx={{ fontSize: 20 }} />}
        </IconButton>
      </Tooltip>

      <Box sx={{ width: '1px', height: 24, bgcolor: 'divider', mx: 0.5 }} />

      <Tooltip title="Account">
        <IconButton onClick={(e) => setAnchor(e.currentTarget)} sx={{ p: 0.5 }} aria-label="Account menu">
          <Avatar sx={{ width: 30, height: 30, fontSize: '0.75rem', fontWeight: 700, bgcolor: 'primary.main', color: 'primary.contrastText' }}>
            {initials(user?.username)}
          </Avatar>
        </IconButton>
      </Tooltip>

      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        slotProps={{ paper: { sx: { minWidth: 220 } } }}
      >
        <Box sx={{ px: 1.5, py: 1 }}>
          <Typography sx={{ fontWeight: 600, fontSize: '0.875rem' }} noWrap>{user?.username}</Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }} noWrap>{user?.email}</Typography>
          <Box sx={{ mt: 0.75 }}>
            <Chip
              label={role}
              size="small"
              sx={{
                height: 20, fontSize: '0.6875rem', fontWeight: 600,
                bgcolor: 'action.selected', color: 'primary.main',
              }}
            />
          </Box>
        </Box>
        <Divider sx={{ my: 0.5 }} />
        <MenuItem onClick={() => { setAnchor(null); logout(); }}>
          <ListItemIcon><LogoutIcon sx={{ fontSize: 18 }} /></ListItemIcon>
          Sign out
        </MenuItem>
      </Menu>
    </Box>
  );
}
