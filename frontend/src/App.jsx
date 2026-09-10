/**
 * Router and providers only.
 *
 * The previous App.jsx was a single 3,106-line component holding roughly forty
 * useState hooks and every screen at once. Screens now live in `src/routes`.
 */

import { Suspense, lazy } from 'react';
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom';

import AppShell from './components/layout/AppShell';
import { Spinner } from './components/ui';
import { AuthProvider, useAuth } from './context/AuthContext';
import { I18nProvider } from './context/I18nContext';
import { ThemeProvider } from './context/ThemeContext';

import Login from './routes/Login';
import Scan from './routes/Scan';

// Split off the heavier screens. The dashboard pulls in the whole charting
// library, which an inspector scanning packages in a shop never needs to download.
const Dashboard = lazy(() => import('./routes/Dashboard'));
const Repository = lazy(() => import('./routes/Repository'));
const InspectionDetail = lazy(() => import('./routes/InspectionDetail'));
const Rules = lazy(() => import('./routes/Rules'));
const Officers = lazy(() => import('./routes/Officers'));
const SettingsPage = lazy(() => import('./routes/Settings'));

function FullPageSpinner() {
  return (
    <div className="grid min-h-screen place-items-center bg-canvas">
      <Spinner className="h-7 w-7" />
    </div>
  );
}

function RequireAuth({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <FullPageSpinner />;
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

/**
 * Hides a route from roles that cannot use it. This is convenience, not security -
 * every endpoint behind these screens is authorised again on the server.
 */
function RequireRole({ role, children }) {
  const { hasRole } = useAuth();
  return hasRole(role) ? children : <Navigate to="/" replace />;
}

function RedirectIfAuthed({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <FullPageSpinner />;
  return isAuthenticated ? <Navigate to="/" replace /> : children;
}

export default function App() {
  return (
    <ThemeProvider>
      <I18nProvider>
        <Router>
          <AuthProvider>
            <Routes>
              <Route
                path="/login"
                element={
                  <RedirectIfAuthed>
                    <Login />
                  </RedirectIfAuthed>
                }
              />

              <Route
                element={
                  <RequireAuth>
                    <Suspense fallback={<FullPageSpinner />}>
                      <AppShell />
                    </Suspense>
                  </RequireAuth>
                }
              >
                <Route index element={<Dashboard />} />
                <Route path="scan" element={<Scan />} />
                <Route path="repository" element={<Repository />} />
                <Route path="inspections/:id" element={<InspectionDetail />} />
                <Route path="rules" element={<Rules />} />
                <Route
                  path="officers"
                  element={
                    <RequireRole role="ADMIN">
                      <Officers />
                    </RequireRole>
                  }
                />
                <Route path="settings" element={<SettingsPage />} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AuthProvider>
        </Router>
      </I18nProvider>
    </ThemeProvider>
  );
}
