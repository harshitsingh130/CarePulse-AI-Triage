/**
 * User Management — admin view of Cognito users and their roles.
 */

import { useEffect, useState } from 'react';

interface UserInfo {
  username: string;
  email: string;
  status: string;
  enabled: boolean;
  groups: string[];
  created_at: string | null;
  last_modified: string | null;
}

const GROUP_COLORS: Record<string, string> = {
  admin: '#7e22ce',
  nurse: '#2563eb',
  physician: '#0d9488',
  patient: '#64748b',
};

export function Users() {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
        const token = sessionStorage.getItem('accessToken');
        const res = await window.fetch(`${API_BASE}/admin/users`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) setUsers(await res.json());
      } catch (e) { /* ignore */ }
      finally { setLoading(false); }
    }
    fetch();
  }, []);

  if (loading) return <div className="dash__page"><div className="skeleton skeleton--card" /></div>;

  const groupCounts = users.reduce((acc, u) => {
    u.groups.forEach(g => { acc[g] = (acc[g] || 0) + 1; });
    if (u.groups.length === 0) acc['no-group'] = (acc['no-group'] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="dash__page">
      <div className="dash__page-header">
        <h1 className="dash__title">User Management</h1>
        <span className="dash__subtitle">{users.length} users in the system</span>
      </div>

      {/* Role summary cards */}
      <div className="dash__metrics-grid" style={{ marginBottom: '24px' }}>
        {Object.entries(groupCounts).map(([group, count]) => (
          <div key={group} className="dash__metric-card">
            <span className="dash__metric-value" style={{ color: GROUP_COLORS[group] || '#334155' }}>{count}</span>
            <span className="dash__metric-label">{group === 'no-group' ? 'Unassigned' : group.charAt(0).toUpperCase() + group.slice(1) + 's'}</span>
          </div>
        ))}
      </div>

      {/* Users table */}
      <div className="dash__table-wrap">
        <table className="dash__table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Role(s)</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.username}>
                <td>
                  <span style={{ fontWeight: 500 }}>{user.email || user.username}</span>
                </td>
                <td>
                  {user.groups.length > 0 ? user.groups.map(g => (
                    <span key={g} className="dash__role-pill" style={{ color: GROUP_COLORS[g] || '#475569', background: `${GROUP_COLORS[g] || '#475569'}15` }}>
                      {g}
                    </span>
                  )) : <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>No role</span>}
                </td>
                <td>
                  <span className={`dash__status-pill ${user.status === 'CONFIRMED' ? 'dash__status-pill--completed' : ''}`}>
                    {user.status}
                  </span>
                </td>
                <td className="dash__time-cell">
                  {user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
