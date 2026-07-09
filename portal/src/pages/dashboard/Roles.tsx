/**
 * Role Management — admin view for creating and managing Cognito groups (roles).
 * Only accessible to users in the 'admin' group.
 */

import { useEffect, useState } from 'react';

interface RoleInfo {
  name: string;
  description: string;
  precedence: number | null;
  created_at: string | null;
  last_modified: string | null;
}

const PROTECTED_ROLES = new Set(['admin', 'nurse', 'physician', 'patient']);

export function Roles() {
  const [roles, setRoles] = useState<RoleInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [showForm, setShowForm] = useState(false);
  const [newRoleName, setNewRoleName] = useState('');
  const [newRoleDesc, setNewRoleDesc] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);

  // Delete state
  const [deleting, setDeleting] = useState<string | null>(null);

  const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

  const fetchRoles = async () => {
    try {
      const token = sessionStorage.getItem('accessToken');
      const res = await fetch(`${API_BASE}/admin/roles`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        setRoles(await res.json());
        setError(null);
      } else {
        setError('Failed to load roles');
      }
    } catch (e) {
      setError('Failed to load roles');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRoles();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRoleName.trim()) return;

    setCreating(true);
    setCreateError(null);
    setCreateSuccess(null);

    try {
      const token = sessionStorage.getItem('accessToken');
      const res = await fetch(`${API_BASE}/admin/roles`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          name: newRoleName.trim().toLowerCase(),
          description: newRoleDesc.trim(),
        }),
      });

      const data = await res.json();

      if (res.ok) {
        setCreateSuccess(`Role "${data.name}" created successfully`);
        setNewRoleName('');
        setNewRoleDesc('');
        setShowForm(false);
        fetchRoles();
      } else {
        setCreateError(data.error || 'Failed to create role');
      }
    } catch (e) {
      setCreateError('Network error — could not create role');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (roleName: string) => {
    if (!window.confirm(`Are you sure you want to delete the role "${roleName}"? This cannot be undone.`)) {
      return;
    }

    setDeleting(roleName);
    try {
      const token = sessionStorage.getItem('accessToken');
      const res = await fetch(`${API_BASE}/admin/roles/${roleName}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (res.ok) {
        setCreateSuccess(`Role "${roleName}" deleted`);
        fetchRoles();
      } else {
        const data = await res.json();
        setCreateError(data.error || 'Failed to delete role');
      }
    } catch (e) {
      setCreateError('Network error — could not delete role');
    } finally {
      setDeleting(null);
    }
  };

  if (loading) {
    return (
      <div className="dash__page">
        <h1 className="dash__title">Role Management</h1>
        <div className="skeleton skeleton--card" />
      </div>
    );
  }

  return (
    <div className="dash__page">
      <div className="dash__page-header">
        <h1 className="dash__title">Role Management</h1>
        <span className="dash__subtitle">Create and manage system roles (Cognito groups)</span>
      </div>

      {/* Feedback messages */}
      {createSuccess && (
        <div className="dash__toast dash__toast--success" role="status">
          {createSuccess}
          <button className="dash__toast-close" onClick={() => setCreateSuccess(null)} aria-label="Dismiss">×</button>
        </div>
      )}
      {createError && (
        <div className="dash__toast dash__toast--error" role="alert">
          {createError}
          <button className="dash__toast-close" onClick={() => setCreateError(null)} aria-label="Dismiss">×</button>
        </div>
      )}
      {error && (
        <div className="dash__toast dash__toast--error" role="alert">{error}</div>
      )}

      {/* Create role button / form */}
      <div style={{ marginBottom: 'var(--sp-6, 24px)' }}>
        {!showForm ? (
          <button className="btn btn--primary" onClick={() => setShowForm(true)}>
            + Create New Role
          </button>
        ) : (
          <div className="dash__card" style={{ maxWidth: '480px' }}>
            <h2>Create New Role</h2>
            <form onSubmit={handleCreate} className="dash__role-form">
              <div className="dash__form-field">
                <label className="dash__field-label" htmlFor="role-name">Role Name</label>
                <input
                  id="role-name"
                  type="text"
                  className="dash__input"
                  value={newRoleName}
                  onChange={(e) => setNewRoleName(e.target.value)}
                  placeholder="e.g. pharmacist, receptionist"
                  pattern="^[a-z][a-z0-9\-]{1,127}$"
                  title="Lowercase letters, numbers, hyphens. Must start with a letter."
                  required
                  autoFocus
                />
                <span className="dash__input-hint">Lowercase letters, numbers, and hyphens only. Starts with a letter.</span>
              </div>
              <div className="dash__form-field">
                <label className="dash__field-label" htmlFor="role-desc">Description (optional)</label>
                <input
                  id="role-desc"
                  type="text"
                  className="dash__input"
                  value={newRoleDesc}
                  onChange={(e) => setNewRoleDesc(e.target.value)}
                  placeholder="Brief description of this role's purpose"
                />
              </div>
              <div className="dash__form-actions">
                <button
                  type="submit"
                  className="btn btn--primary"
                  disabled={creating || !newRoleName.trim()}
                >
                  {creating ? 'Creating...' : 'Create Role'}
                </button>
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => { setShowForm(false); setNewRoleName(''); setNewRoleDesc(''); }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}
      </div>

      {/* Roles table */}
      <div className="dash__table-wrap">
        <table className="dash__table">
          <thead>
            <tr>
              <th>Role Name</th>
              <th>Description</th>
              <th>Type</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {roles.map((role) => (
              <tr key={role.name}>
                <td>
                  <span className="dash__role-pill" style={{
                    color: PROTECTED_ROLES.has(role.name) ? '#7e22ce' : '#0d9488',
                    background: PROTECTED_ROLES.has(role.name) ? '#7e22ce15' : '#0d948815',
                  }}>
                    {role.name}
                  </span>
                </td>
                <td style={{ color: '#64748b', fontSize: '0.875rem' }}>
                  {role.description || '—'}
                </td>
                <td>
                  {PROTECTED_ROLES.has(role.name) ? (
                    <span className="dash__status-pill" style={{ background: '#fef3c7', color: '#92400e' }}>System</span>
                  ) : (
                    <span className="dash__status-pill">Custom</span>
                  )}
                </td>
                <td className="dash__time-cell">
                  {role.created_at ? new Date(role.created_at).toLocaleDateString() : '—'}
                </td>
                <td>
                  {PROTECTED_ROLES.has(role.name) ? (
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Protected</span>
                  ) : (
                    <button
                      className="btn btn--sm btn--danger"
                      onClick={() => handleDelete(role.name)}
                      disabled={deleting === role.name}
                    >
                      {deleting === role.name ? 'Deleting...' : 'Delete'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {roles.length === 0 && (
              <tr>
                <td colSpan={5} className="dash__empty-row">No roles found. Create one to get started.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
