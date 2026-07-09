/**
 * SOAP Notes — physician view of generated clinical summaries.
 * Read-only view of AI-generated SOAP notes for review and sign-off.
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

interface SessionWithSOAP {
  session_id: string;
  patient_id: string;
  urgency_level: string | null;
  primary_complaint: string;
  department: string | null;
  started_at: string;
  completed_at: string | null;
  has_override: boolean;
}

const URGENCY_COLORS: Record<string, string> = {
  EMERGENCY: '#dc2626',
  URGENT: '#b45309',
  STANDARD: '#2563eb',
  ROUTINE: '#15803d',
};

export function SOAPNotes() {
  const [sessions, setSessions] = useState<SessionWithSOAP[]>([]);
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
          const data: SessionWithSOAP[] = await res.json();
          // Show completed sessions (they have SOAP notes)
          setSessions(data.filter(s => s.completed_at));
        }
      } catch (e) { /* ignore */ }
      finally { setLoading(false); }
    }
    fetch();
  }, []);

  if (loading) return <div className="dash__page"><div className="skeleton skeleton--card" /><div className="skeleton skeleton--card" /></div>;

  return (
    <div className="dash__page">
      <div className="dash__page-header">
        <h1 className="dash__title">Clinical Notes (SOAP)</h1>
        <span className="dash__subtitle">{sessions.length} completed assessments with clinical summaries</span>
      </div>

      {sessions.length === 0 ? (
        <div className="dash__card" style={{ textAlign: 'center', padding: '48px' }}>
          <p style={{ color: '#64748b' }}>No completed assessments with SOAP notes yet.</p>
        </div>
      ) : (
        <div className="dash__soap-grid">
          {sessions.map(item => (
            <div key={item.session_id} className="dash__soap-card">
              <div className="dash__soap-card-header">
                <span className="dash__soap-urgency" style={{ color: URGENCY_COLORS[item.urgency_level || ''] || '#64748b' }}>
                  {item.urgency_level || 'UNSCORED'}
                </span>
                <span className="dash__soap-date">
                  {new Date(item.completed_at!).toLocaleDateString()}
                </span>
              </div>
              <p className="dash__soap-complaint">{item.primary_complaint}</p>
              <div className="dash__soap-meta">
                <span>{item.department || 'No dept'}</span>
                {item.has_override && <span className="dash__override-badge">Override</span>}
              </div>
              <Link to={`/dashboard/session/${item.session_id}`} className="dash__soap-link">
                View Full Note →
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
