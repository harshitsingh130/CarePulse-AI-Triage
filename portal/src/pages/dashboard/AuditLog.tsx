/**
 * Audit Log Viewer — admin-only view of all clinical events.
 */

import { useEffect, useState } from 'react';

interface AuditEntry {
  patient_id: string;
  timestamp: string;
  event_type: string;
  session_id: string;
  actor_type: string;
  actor_id: string;
  details: Record<string, any>;
}

const EVENT_COLORS: Record<string, string> = {
  NURSE_OVERRIDE: '#b45309',
  URGENCY_ASSIGNED: '#2563eb',
  ESCALATION_TRIGGERED: '#dc2626',
  TRIAGE_STARTED: '#15803d',
  ROUTING_DECIDED: '#7e22ce',
  SOAP_GENERATED: '#0d9488',
};

export function AuditLog() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
        const token = sessionStorage.getItem('accessToken');
        const res = await window.fetch(`${API_BASE}/admin/audit`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) setEntries(await res.json());
      } catch (e) { /* ignore */ }
      finally { setLoading(false); }
    }
    fetch();
  }, []);

  if (loading) return <div className="dash__page"><div className="skeleton skeleton--card" /><div className="skeleton skeleton--card" /></div>;

  return (
    <div className="dash__page">
      <div className="dash__page-header">
        <h1 className="dash__title">Audit Log</h1>
        <span className="dash__subtitle">{entries.length} events recorded</span>
      </div>

      {entries.length === 0 ? (
        <div className="dash__card" style={{ textAlign: 'center', padding: '48px' }}>
          <p style={{ color: '#64748b' }}>No audit events yet. Events appear after triage sessions complete or nurse overrides occur.</p>
        </div>
      ) : (
        <div className="dash__table-wrap">
          <table className="dash__table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Event</th>
                <th>Actor</th>
                <th>Session</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry, i) => (
                <tr key={i}>
                  <td className="dash__time-cell">
                    {new Date(entry.timestamp).toLocaleDateString()}<br />
                    <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
                      {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  </td>
                  <td>
                    <span className="dash__event-badge" style={{ color: EVENT_COLORS[entry.event_type] || '#475569' }}>
                      {entry.event_type.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td>
                    <span className="dash__actor">{entry.actor_type}</span>
                    <br />
                    <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>{entry.actor_id.slice(0, 12)}</span>
                  </td>
                  <td><code style={{ fontSize: '0.7rem' }}>{entry.session_id?.slice(0, 8) || '—'}</code></td>
                  <td className="dash__details-cell">
                    {entry.details && Object.keys(entry.details).length > 0 ? (
                      <details>
                        <summary style={{ cursor: 'pointer', fontSize: '0.75rem', color: '#3b82f6' }}>View</summary>
                        <pre style={{ fontSize: '0.65rem', marginTop: '4px', whiteSpace: 'pre-wrap', color: '#475569' }}>
                          {JSON.stringify(entry.details, null, 2)}
                        </pre>
                      </details>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
