/**
 * Route tree: public auth routes, and a protected shell hosting the app pages.
 * All app pages require a valid token; the Users page additionally requires the
 * manage_users permission (Admin) and 403s to /not-permitted otherwise.
 */

import { Routes, Route } from 'react-router-dom';
import { ProtectedRoute, PublicOnlyRoute } from './auth/ProtectedRoute';
import AppShell from './components/layout/AppShell';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ProjectsPage from './pages/projects/ProjectsPage';
import DeliverablesPage from './pages/deliverables/DeliverablesPage';
import ResourcesPage from './pages/resources/ResourcesPage';
import AllocationsPage from './pages/allocations/AllocationsPage';
import UsersPage from './pages/UsersPage';
import { NotPermittedPage, NotFoundPage } from './pages/StatusPages';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<PublicOnlyRoute><LoginPage /></PublicOnlyRoute>} />
      <Route path="/register" element={<PublicOnlyRoute><RegisterPage /></PublicOnlyRoute>} />

      <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
        <Route index element={<DashboardPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="deliverables" element={<DeliverablesPage />} />
        <Route path="resources" element={<ResourcesPage />} />
        <Route path="allocations" element={<AllocationsPage />} />
        <Route
          path="users"
          element={
            <ProtectedRoute permission="manage_users">
              <UsersPage />
            </ProtectedRoute>
          }
        />
        <Route path="not-permitted" element={<NotPermittedPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
