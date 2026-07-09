/**
 * Dashboard layout with sidebar navigation for nurse/admin views.
 * Requires authentication + nurse/physician/admin group membership.
 */

import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { authService } from '@/services/auth';

export function DashboardLayout() {
  const navigate = useNavigate();
  const [authorized, setAuthorized] = useState<boolean | null>(null);

  useEffect(() => {
    if (!authService.isAuthenticated()) {
      navigate('/auth?redirect=/dashboard');
      return;
    }
    if (!authService.isClinicalUser()) {
      // Patients should never see the dashboard — redirect to home
      navigate('/');
      return;
    }
    setAuthorized(true);
  }, [navigate]);

  if (authorized === null) {
    return <div className="dash"><div className="dash__content"><div className="skeleton skeleton--card" /></div></div>;
  }

  if (authorized === false) {
    return null; // Will redirect via useEffect
  }

  const username = authService.getUsername();
  const groups = authService.getUserGroups();

  const isAdmin = groups.includes('admin');
  const isPhysician = groups.includes('physician');

  // Determine role label for station branding
  const roleLabel = isAdmin ? 'Admin' : isPhysician ? 'Physician' : 'Nurse';

  return (
    <div className="dash">
      <aside className="dash__sidebar">
        <div className="dash__brand" aria-label="CarePulse logo">
          <span className="dash__brand-icon">🏥</span>
          <div>
            <span className="dash__brand-name">CarePulse</span>
            <span className="dash__brand-role">{roleLabel} Station</span>
          </div>
        </div>
        <nav className="dash__nav">
          {/* Triage Queue — visible to all clinical roles */}
          <NavLink to="/dashboard" end className={({ isActive }) => `dash__nav-item ${isActive ? 'dash__nav-item--active' : ''}`}>
            <span className="dash__nav-icon">📋</span> Triage Queue
          </NavLink>

          {/* Escalations — physician and admin only */}
          {(isPhysician || isAdmin) && (
            <NavLink to="/dashboard/escalations" className={({ isActive }) => `dash__nav-item ${isActive ? 'dash__nav-item--active' : ''}`}>
              <span className="dash__nav-icon">🚨</span> Escalations
            </NavLink>
          )}

          {/* SOAP Notes — physician and admin only */}
          {(isPhysician || isAdmin) && (
            <NavLink to="/dashboard/soap-notes" className={({ isActive }) => `dash__nav-item ${isActive ? 'dash__nav-item--active' : ''}`}>
              <span className="dash__nav-icon">📄</span> SOAP Notes
            </NavLink>
          )}

          {/* Metrics — visible to all clinical roles */}
          <NavLink to="/dashboard/metrics" className={({ isActive }) => `dash__nav-item ${isActive ? 'dash__nav-item--active' : ''}`}>
            <span className="dash__nav-icon">📊</span> Metrics
          </NavLink>

          {/* Audit Log — admin only */}
          {isAdmin && (
            <NavLink to="/dashboard/audit" className={({ isActive }) => `dash__nav-item ${isActive ? 'dash__nav-item--active' : ''}`}>
              <span className="dash__nav-icon">📜</span> Audit Log
            </NavLink>
          )}

          {/* User Management — admin only */}
          {isAdmin && (
            <NavLink to="/dashboard/users" className={({ isActive }) => `dash__nav-item ${isActive ? 'dash__nav-item--active' : ''}`}>
              <span className="dash__nav-icon">👥</span> Users
            </NavLink>
          )}

          {/* Role Management — admin only */}
          {isAdmin && (
            <NavLink to="/dashboard/roles" className={({ isActive }) => `dash__nav-item ${isActive ? 'dash__nav-item--active' : ''}`}>
              <span className="dash__nav-icon">🔑</span> Roles
            </NavLink>
          )}
        </nav>
        <div className="dash__sidebar-footer">
          <div className="dash__user-info">
            <span className="dash__user-name">{username || 'Clinician'}</span>
            <span className="dash__user-role">{groups.join(', ')}</span>
          </div>
          <NavLink to="/" className="dash__nav-item dash__nav-item--back">
            ← Go Home
          </NavLink>
        </div>
      </aside>
      <main className="dash__content">
        <Outlet />
      </main>
    </div>
  );
}
