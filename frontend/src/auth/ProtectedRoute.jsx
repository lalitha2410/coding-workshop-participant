/**
 * Route guards.
 *
 * <ProtectedRoute> — requires authentication (optionally a permission/role);
 *   unauthenticated -> /login (remembering where they were headed),
 *   authenticated-but-unauthorized -> /not-permitted.
 * <PublicOnlyRoute> — for /login and /register; sends signed-in users home.
 */

import { Navigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { useAuth } from './AuthContext';
import { can } from './roles';

function FullscreenLoader() {
  return (
    <Box sx={{ minHeight: '100dvh', display: 'grid', placeItems: 'center', bgcolor: 'background.default' }}>
      <CircularProgress size={22} thickness={5} />
    </Box>
  );
}

export function ProtectedRoute({ children, permission, role }) {
  const { isAuthenticated, isBootstrapping, role: userRole } = useAuth();
  const location = useLocation();

  if (isBootstrapping) return <FullscreenLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />;

  const roleOk = !role || userRole === role;
  const permOk = !permission || can(userRole, permission);
  if (!roleOk || !permOk) return <Navigate to="/not-permitted" replace />;

  return children;
}

export function PublicOnlyRoute({ children }) {
  const { isAuthenticated, isBootstrapping } = useAuth();
  if (isBootstrapping) return <FullscreenLoader />;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return children;
}
