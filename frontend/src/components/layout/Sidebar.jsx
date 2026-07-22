/**
 * Left sidebar navigation. Fixed 240px on desktop; rendered inside a temporary
 * Drawer on mobile (controlled by AppShell). Nav items are role-gated via the
 * client-side permission mirror.
 */

import { NavLink } from 'react-router-dom';
import {
  Box, List, ListItemButton, ListItemIcon, ListItemText, Typography, Divider,
} from '@mui/material';
import { Logo } from '../common/Logo';
import { NAV } from './navConfig';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../auth/roles';

function SidebarNavItem({ item, onNavigate }) {
  const Icon = item.icon;
  return (
    <ListItemButton
      component={NavLink}
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      sx={{
        px: 1.25, py: 0.75, mb: 0.25,
        color: 'text.secondary',
        '&.active': {
          bgcolor: 'action.selected',
          color: 'primary.main',
          '& .MuiListItemIcon-root': { color: 'primary.main' },
        },
      }}
    >
      <ListItemIcon sx={{ minWidth: 32, color: 'text.disabled' }}>
        <Icon sx={{ fontSize: 20 }} />
      </ListItemIcon>
      <ListItemText
        primary={item.label}
        primaryTypographyProps={{ fontSize: '0.8125rem', fontWeight: 600 }}
      />
    </ListItemButton>
  );
}

export default function Sidebar({ onNavigate }) {
  const { role } = useAuth();

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'background.paper' }}>
      <Box sx={{ height: 60, px: 2, display: 'flex', alignItems: 'center', flexShrink: 0 }}>
        <Logo />
      </Box>
      <Divider />

      <Box sx={{ flex: 1, overflowY: 'auto', px: 1.5, py: 2 }}>
        {NAV.map((section) => {
          const items = section.items.filter((i) => !i.permission || can(role, i.permission));
          if (items.length === 0) return null;
          return (
            <Box key={section.heading} sx={{ mb: 2.5 }}>
              <Typography variant="overline" sx={{ px: 1.25, mb: 0.5, display: 'block' }}>
                {section.heading}
              </Typography>
              <List disablePadding>
                {items.map((item) => (
                  <SidebarNavItem key={item.to} item={item} onNavigate={onNavigate} />
                ))}
              </List>
            </Box>
          );
        })}
      </Box>

      <Divider />
      <Box sx={{ px: 2, py: 1.5 }}>
        <Typography variant="caption" sx={{ color: 'text.disabled' }}>
          Portfolio operations
        </Typography>
      </Box>
    </Box>
  );
}
