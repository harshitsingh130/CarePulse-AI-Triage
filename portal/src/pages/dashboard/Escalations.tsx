/**
 * Escalation Alerts — physician view of high-priority cases needing attention.
 * Shows EMERGENCY and URGENT sessions, nurse overrides pending sign-off.
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

interface QueueItem {
  session_id: string;
  patient_id: string;
  status: string;
  urgency_level: string | null;
  confidence: number | null;
  primary_complaint: string;
  department: string | null;
  started_at: string;
  has_override: boolean;
}

export function Escalations() {
  const [sessions, setSessions] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
        const token = sessionStorage.getItem('accessToken');
        const res = await window.fetch(`${API_BASE}/admin/sessions`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data: QueueItem[] = await res.json();
          // Filter to only EMERGENCY, URGENT, and ESCALATED sessions
          setSessions(data.filter(s =>
            s.urgency_level === 'EMERGENCY' ||
            s.urgency_level === 'URGENT' ||
            s.status === 'ESCALATED'
          ));
        }
      } catch (e) { /* ignore */ }
      finally { setLoading(false); }
    }
    fetch();
    const interval = setInterval(fetch, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="dash__page"><div className="skeleton skeleton--card" /><div className="skeleton skeleton--card" /></div>;

  const emergencies = sessions.filter(s => s.urgency_level === 'EMERGENCY' || s.status === 'ESCALATED');
  const urgent = sessions.filter(s => s.urgency_level === 'URGENT' && s.status !== 'ESCALATED');

  return (
    <div className="dash__page">
      <div className="dash__page-header">
        <h1 className="dash__title">Escalation Alerts</h1>
        <span className="dash__subtitle">{sessions.length} cases requiring physician attention</span>
      </div>

      {/* Emergency section */}
      {emergencies.length > 0 && (
        <section style={{ marginBottom: '32px' }}>
          <h2 className="dash__section-title dash__section-title--red">🚨 Emergency ({emergencies.length})</h2>
          <div className="dash__alert-list">
            {emergencies.map(item => (
              <div key={item.session_id} className="dash__alert-card dash__alert-card--emergency">
                <div className="dash__alert-header">
                  <span className="dash__alert-urgency">EMERGENCY</span>
                  {item.has_override && <span className="dash__override-badge">Nurse Override</span>}
                  <span className="dash__alert-time">{new Date(item.started_at).toLocaleString()}</span>
                </div>
                <p className="dash__alert-complaint">{item.primary_complaint}</p>
                <div className="dash__alert-footer">
                  <span className="dash__alert-dept">{item.department || 'Unrouted'}</span>
                  <Link to={`/dashboard/session/${item.session_id}`} className="btn btn--sm btn--primary">
                    Review Case
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Urgent section */}
      {urgent.length > 0 && (
        <section>
          <h2 className="dash__section-title dash__section-title--amber">⚠️ Urgent ({urgent.length})</h2>
          <div className="dash__alert-list">
            {urgent.map(item => (
              <div key={item.session_id} className="dash__alert-card dash__alert-card--urgent">
                <div className="dash__alert-header">
                  <span className="dash__alert-urgency" style={{ color: '#b45309' }}>URGENT</span>
                  {item.has_override && <span className="dash__override-badge">Nurse Override</span>}
                  <span className="dash__alert-time">{new Date(item.started_at).toLocaleString()}</span>
                </div>
                <p className="dash__alert-complaint">{item.primary_complaint}</p>
                <div className="dash__alert-footer">
                  <span className="dash__alert-dept">{item.department || 'Unrouted'}</span>
                  <Link to={`/dashboard/session/${item.session_id}`} className="btn btn--sm btn--secondary">
                    Review
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {sessions.length === 0 && (
        <div className="dash__card" style={{ textAlign: 'center', padding: '64px 32px' }}>
          <p style={{ fontSize: '2rem', marginBottom: '12px' }}>✅</p>
          <p style={{ color: '#64748b', fontSize: '1rem' }}>No escalations at this time. All cases are under control.</p>
        </div>
      )}
    </div>
  );
}
