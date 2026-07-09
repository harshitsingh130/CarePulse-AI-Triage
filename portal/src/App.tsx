/**
 * Root App component — routing and layout.
 * Patient portal + Nurse dashboard (separate layout).
 */

import { useState, useCallback } from 'react';
import { BrowserRouter, Route, Routes, Link, useNavigate } from 'react-router-dom';
import { Landing } from '@/pages/Landing';
import { Auth } from '@/pages/Auth';
import { TriageChat } from '@/pages/TriageChat';
import { Status } from '@/pages/Status';
import { History } from '@/pages/History';
import { Appointments } from '@/pages/Appointments';
import { DashboardLayout } from '@/pages/dashboard/DashboardLayout';
import { TriageQueue } from '@/pages/dashboard/TriageQueue';
import { SessionDetail } from '@/pages/dashboard/SessionDetail';
import { Metrics } from '@/pages/dashboard/Metrics';
import { AuditLog } from '@/pages/dashboard/AuditLog';
import { Users } from '@/pages/dashboard/Users';
import { Roles } from '@/pages/dashboard/Roles';
import { Escalations } from '@/pages/dashboard/Escalations';
import { SOAPNotes } from '@/pages/dashboard/SOAPNotes';
import { authService } from '@/services/auth';

function AppContent() {
  const [isLoggedIn, setIsLoggedIn] = useState(authService.isAuthenticated());
  const navigate = useNavigate();

  const handleLogin = useCallback(() => {
    setIsLoggedIn(true);
  }, []);

  const handleLogout = useCallback(() => {
    authService.logout();
    setIsLoggedIn(false);
    navigate('/auth');
  }, [navigate]);

  return (
    <Routes>
      {/* Nurse Dashboard — separate layout, no patient header */}
      <Route path="/dashboard" element={<DashboardLayout />}>
        <Route index element={<TriageQueue />} />
        <Route path="session/:sessionId" element={<SessionDetail />} />
        <Route path="metrics" element={<Metrics />} />
        <Route path="escalations" element={<Escalations />} />
        <Route path="soap-notes" element={<SOAPNotes />} />
        <Route path="audit" element={<AuditLog />} />
        <Route path="users" element={<Users />} />
        <Route path="roles" element={<Roles />} />
      </Route>

      {/* Patient Portal — original layout */}
      <Route path="*" element={
        <div className="app">
          <header className="app-header">
            <nav className="app-nav" aria-label="Main navigation">
              <div className="app-nav__brand">
                <span className="app-nav__logo" aria-label="CarePulse">
                  CarePulse
                  <svg className="app-nav__heartbeat" viewBox="0 0 24 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <polyline points="0,8 4,8 6,2 8,14 10,6 12,10 14,8 24,8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </span>
                <span className="app-nav__tagline">AI-Powered Patient Triage</span>
              </div>
              <ul className="app-nav__links">
                {!authService.isClinicalUser() && (
                  <>
                    <li><Link to="/">Triage</Link></li>
                    <li><Link to="/appointments">Appointments</Link></li>
                    <li><Link to="/history">History</Link></li>
                  </>
                )}
                {authService.isClinicalUser() && (
                  <li><Link to="/dashboard" className="nav-btn nav-btn--primary">
                    {authService.getUserGroups().includes('admin') ? 'Admin' : authService.getUserGroups().includes('physician') ? 'Physician' : 'Nurse'} Station
                  </Link></li>
                )}
                {!isLoggedIn && !authService.isClinicalUser() && (
                  <li><Link to="/dashboard" className="nav-btn">Staff Login</Link></li>
                )}
                {isLoggedIn ? (
                  <li><button className="nav-btn" onClick={handleLogout}>Sign Out</button></li>
                ) : (
                  <li><Link to="/auth" className="nav-btn nav-btn--primary">Sign In</Link></li>
                )}
              </ul>
            </nav>
          </header>

          <main id="main-content" className="app-main">
            <Routes>
              <Route path="/" element={<Landing />} />
              <Route path="/auth" element={<Auth onLogin={handleLogin} />} />
              <Route path="/triage/:sessionId" element={<TriageChat />} />
              <Route path="/triage/:sessionId/status" element={<Status />} />
              <Route path="/history" element={<History />} />
              <Route path="/appointments" element={<Appointments />} />
            </Routes>
          </main>
        </div>
      } />
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}

export default App;
