/**
 * Dashboard Metrics — quick overview of triage activity.
 */

import { useEffect, useState } from 'react';

interface QueueItem {
  status: string;
  urgency_level: string | null;
  started_at: string;
  completed_at: string | null;
  has_override: boolean;
}

export function Metrics() {
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
        if (res.ok) setSessions(await res.json());
      } catch (e) { /* ignore */ }
      finally { setLoading(false); }
    }
    fetch();
  }, []);

  if (loading) return <div className="dash__page"><div className="skeleton skeleton--card" /></div>;

  const today = new Date().toDateString();
  const todaySessions = sessions.filter(s => new Date(s.started_at).toDateString() === today);
  const completed = sessions.filter(s => s.status === 'COMPLETED');
  const emergency = sessions.filter(s => s.urgency_level === 'EMERGENCY');
  const overrides = sessions.filter(s => s.has_override);

  // Avg duration for completed sessions
  const avgDuration = completed.length > 0
    ? completed.reduce((sum, s) => {
        if (!s.completed_at) return sum;
        return sum + (new Date(s.completed_at).getTime() - new Date(s.started_at).getTime());
      }, 0) / completed.length / 60000
    : 0;

  return (
    <div className="dash__page">
      <h1 className="dash__title">Metrics Overview</h1>

      <div className="dash__metrics-grid">
        <div className="dash__metric-card">
          <span className="dash__metric-value">{sessions.length}</span>
          <span className="dash__metric-label">Total Sessions</span>
        </div>
        <div className="dash__metric-card">
          <span className="dash__metric-value">{todaySessions.length}</span>
          <span className="dash__metric-label">Today</span>
        </div>
        <div className="dash__metric-card dash__metric-card--red">
          <span className="dash__metric-value">{emergency.length}</span>
          <span className="dash__metric-label">Emergency</span>
        </div>
        <div className="dash__metric-card">
          <span className="dash__metric-value">{avgDuration.toFixed(1)}m</span>
          <span className="dash__metric-label">Avg Duration</span>
        </div>
        <div className="dash__metric-card">
          <span className="dash__metric-value">{overrides.length}</span>
          <span className="dash__metric-label">Nurse Overrides</span>
        </div>
        <div className="dash__metric-card">
          <span className="dash__metric-value">{completed.length > 0 ? `${((completed.length / sessions.length) * 100).toFixed(0)}%` : '—'}</span>
          <span className="dash__metric-label">Completion Rate</span>
        </div>
      </div>

      {/* Urgency breakdown */}
      <section className="dash__card" style={{ marginTop: '32px' }}>
        <h2>Urgency Distribution</h2>
        <div className="dash__breakdown">
          {['EMERGENCY', 'URGENT', 'STANDARD', 'ROUTINE'].map(level => {
            const count = sessions.filter(s => s.urgency_level === level).length;
            const pct = sessions.length > 0 ? (count / sessions.length) * 100 : 0;
            return (
              <div key={level} className="dash__breakdown-row">
                <span className="dash__breakdown-label">{level}</span>
                <div className="dash__breakdown-bar">
                  <div className="dash__breakdown-fill" style={{ width: `${pct}%`, background: level === 'EMERGENCY' ? '#dc2626' : level === 'URGENT' ? '#b45309' : level === 'STANDARD' ? '#2563eb' : '#15803d' }} />
                </div>
                <span className="dash__breakdown-count">{count}</span>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
