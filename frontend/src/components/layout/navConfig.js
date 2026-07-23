/**
 * Sidebar navigation model, shared by the Sidebar and the TopBar title lookup.
 * Items may declare a `permission` or `role` to gate them (client-side hint only).
 */

import DashboardIcon from '@mui/icons-material/SpaceDashboardOutlined';
import ProjectsIcon from '@mui/icons-material/FolderOutlined';
import DeliverablesIcon from '@mui/icons-material/ChecklistOutlined';
import ResourcesIcon from '@mui/icons-material/GroupsOutlined';
import AllocationsIcon from '@mui/icons-material/DonutSmallOutlined';
import UsersIcon from '@mui/icons-material/ManageAccountsOutlined';

export const NAV = [
  {
    heading: 'Overview',
    items: [{ to: '/', label: 'Dashboard', icon: DashboardIcon, end: true }],
  },
  {
    heading: 'Portfolio',
    items: [
      { to: '/projects', label: 'Projects', icon: ProjectsIcon },
      { to: '/deliverables', label: 'Deliverables', icon: DeliverablesIcon },
    ],
  },
  {
    heading: 'Capacity',
    items: [
      { to: '/resources', label: 'Resources', icon: ResourcesIcon },
      { to: '/allocations', label: 'Allocations', icon: AllocationsIcon },
    ],
  },
  {
    heading: 'Admin',
    items: [{ to: '/users', label: 'Users', icon: UsersIcon, permission: 'manage_users' }],
  },
];

const TITLES = NAV.flatMap((s) => s.items).reduce((acc, i) => ((acc[i.to] = i.label), acc), {});

export function titleForPath(pathname) {
  if (TITLES[pathname]) return TITLES[pathname];
  // Match the deepest section prefix (e.g. /projects/123 -> Projects).
  const hit = NAV.flatMap((s) => s.items)
    .filter((i) => i.to !== '/' && pathname.startsWith(i.to))
    .sort((a, b) => b.to.length - a.to.length)[0];
  return hit?.label ?? 'LoadBalance';
}
