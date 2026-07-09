/**
 * Nurse Triage Queue — shows all sessions with urgency, complaint, and time.
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
  completed_at: string | null;
  has_override: boolean;
}

const URGENCY_COLORS: Record<string, string> = {
  EMERGENCY: '#dc2626',
  URGENT: '#b45309',
  STANDARD: '#2563eb',
  ROUTINE: '#15803d',
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function TriageQueue() {
  const [sessions, setSessions] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');

  useEffect(() => {
    async function fetchQueue() {
      try {
        const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';
        const token = sessionStorage.getItem('accessToken');
        const res = await fetch(`${API_BASE}/admin/sessions`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          setSessions(data);
        }
      } catch (e) {
        console.error('Failed to load queue', e);
      } finally {
        setLoading(false);
      }
    }
    fetchQueue();
    const interval = setInterval(fetchQueue, 15000); // Refresh every 15s
    return () => clearInterval(interval);
  }, []);

  const filtered = filter === 'all'
    ? sessions
    : sessions.filter(s => s.urgency_level === filter);

  const counts = {
    all: sessions.length,
    EMERGENCY: sessions.filter(s => s.urgency_level === 'EMERGENCY').length,
    URGENT: sessions.filter(s => s.urgency_level === 'URGENT').length,
    STANDARD: sessions.filter(s => s.urgency_level === 'STANDARD').length,
    ROUTINE: sessions.filter(s => s.urgency_level === 'ROUTINE').length,
  };

  if (loading) {
    return (
      <div className="dash__page">
        <h1 className="dash__title">Triage Queue</h1>
        <div className="skeleton skeleton--card" />
        <div className="skeleton skeleton--card" />
      </div>
    );
  }

  return (
    <div className="dash__page">
      <div className="dash__page-header">
        <h1 className="dash__title">Triage Queue</h1>
        <span className="dash__subtitle">{sessions.length} sessions total</span>
      </div>

      {/* Filter tabs */}
      <div className="dash__filters">
        {(['all', 'EMERGENCY', 'URGENT', 'STANDARD', 'ROUTINE'] as const).map((f) => (
          <button
            key={f}
            className={`dash__filter-btn ${filter === f ? 'dash__filter-btn--active' : ''}`}
            onClick={() => setFilter(f)}
            style={f !== 'all' ? { '--filter-color': URGENCY_COLORS[f] } as React.CSSProperties : undefined}
          >
            {f === 'all' ? 'All' : f.charAt(0) + f.slice(1).toLowerCase()}
            <span className="dash__filter-count">{counts[f]}</span>
          </button>
        ))}
      </div>

      {/* Queue table */}
      <div className="dash__table-wrap">
        <table className="dash__table">
          <thead>
            <tr>
              <th>Urgency</th>
              <th>Complaint</th>
              <th>Department</th>
              <th>Status</th>
              <th>Time</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item) => (
              <tr key={item.session_id} className={item.urgency_level === 'EMERGENCY' ? 'dash__row--emergency' : ''}>
                <td>
                  <span className="dash__urgency-dot" style={{ background: URGENCY_COLORS[item.urgency_level || ''] || '#94a3b8' }} />
                  {item.urgency_level || '—'}
                  {item.has_override && <span className="dash__override-badge">Override</span>}
                </td>
                <td className="dash__complaint-cell">{item.primary_complaint}</td>
                <td>{item.department || '—'}</td>
                <td>
                  <span className={`dash__status-pill dash__status-pill--${(item.status || '').toLowerCase().replace('_', '-')}`}>
                    {(item.status || '').replace(/_/g, ' ')}
                  </span>
                </td>
                <td className="dash__time-cell">{timeAgo(item.started_at)}</td>
                <td>
                  <Link to={`/dashboard/session/${item.session_id}`} className="dash__action-link">
                    Review
                  </Link>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={6} className="dash__empty-row">No sessions matching filter</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
