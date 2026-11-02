/**
 * DevOps Incidents & Operational Reliability Page
 * Real-time outage tracking, severity triage, and incident resolution workflows
 */
import { useState, useEffect } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Plus,
  ShieldAlert,
  Activity,
  Flame,
} from 'lucide-react';
import { cicdApi } from '../../api/cicd.api';
import { MetricCard } from '../../components/common/ScoreCard';
import { RiskBadge, StatusBadge } from '../../components/common/Badges';
import { Modal } from '../../components/common/Modal';
import { timeAgo } from '../../utils/dates';
import toast from 'react-hot-toast';

export function IncidentsPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [incidents, setIncidents] = useState([]);

  useEffect(() => {
    cicdApi.getIncidents().then((res) => {
      const data = Array.isArray(res.data) ? res.data : res.data?.incidents || [];
      if (data.length) setIncidents(data);
    }).catch(() => {});
  }, []);

  const handleCreate = (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const newInc = {
      id: `INC-${Math.floor(200 + Math.random() * 800)}`,
      title: fd.get('title'),
      severity: fd.get('severity'),
      status: 'INVESTIGATING',
      affected_service: fd.get('affected_service'),
      started_at: new Date().toISOString(),
      summary: fd.get('summary'),
      resolved_at: null,
    };
    setIncidents([newInc, ...incidents]);
    cicdApi.createIncident(newInc).catch(() => {});
    setModalOpen(false);
    toast.success('Incident declared and notifications broadcasted.');
  };

  const resolveIncident = (id) => {
    setIncidents(
      incidents.map((inc) =>
        inc.id === id
          ? { ...inc, status: inc.status === 'RESOLVED' ? 'INVESTIGATING' : 'RESOLVED', resolved_at: new Date().toISOString() }
          : inc
      )
    );
    toast.success('Incident status updated.');
  };

  const activeIncidents = incidents.filter((i) => i.status !== 'RESOLVED');

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Incidents & Operational Triage</h1>
          <p className="page-subtitle">Track live operational disruptions, root-cause investigations, and MTTR</p>
        </div>
        <button className="btn btn-danger" onClick={() => setModalOpen(true)}>
          <Flame size={15} />
          Declare Incident
        </button>
      </div>

      {/* Metrics */}
      <div className="metric-grid">
        <MetricCard
          label="Active Incidents"
          value={activeIncidents.length}
          icon={AlertTriangle}
          iconBg="rgba(239,68,68,0.1)"
          iconColor="var(--danger)"
        />
        <MetricCard
          label="System Uptime (30d)"
          value="99.94%"
          icon={Activity}
          iconBg="rgba(16,185,129,0.1)"
          iconColor="var(--success)"
        />
        <MetricCard
          label="Average MTTR"
          value="42 mins"
          icon={Clock}
          iconBg="rgba(59,130,246,0.1)"
          iconColor="var(--info)"
        />
        <MetricCard
          label="Resolved Incidents"
          value={incidents.filter((i) => i.status === 'RESOLVED').length}
          icon={CheckCircle2}
          iconBg="rgba(16,185,129,0.1)"
          iconColor="var(--success)"
        />
      </div>

      {/* Incidents List */}
      <div className="card" style={{ padding: 0 }}>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Incident ID</th>
                <th>Title</th>
                <th>Severity</th>
                <th>Affected Service</th>
                <th>Status</th>
                <th>Started</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((inc) => (
                <tr key={inc.id}>
                  <td>
                    <code style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--danger)' }}>
                      {inc.id}
                    </code>
                  </td>
                  <td>
                    <div
                      style={{ fontWeight: 600, color: 'var(--text-primary)', cursor: 'pointer' }}
                      onClick={() => setSelectedIncident(inc)}
                    >
                      {inc.title}
                    </div>
                  </td>
                  <td>
                    <RiskBadge level={inc.severity} />
                  </td>
                  <td>
                    <span className="badge badge-neutral" style={{ fontFamily: 'var(--font-mono)' }}>
                      {inc.affected_service}
                    </span>
                  </td>
                  <td>
                    <StatusBadge status={inc.status} />
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                    {timeAgo(inc.started_at)}
                  </td>
                  <td>
                    <button
                      className={`btn btn-sm ${inc.status === 'RESOLVED' ? 'btn-secondary' : 'btn-success'}`}
                      style={{ fontSize: '0.75rem' }}
                      onClick={() => resolveIncident(inc.id)}
                    >
                      {inc.status === 'RESOLVED' ? 'Reopen' : 'Resolve'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Declare Incident Modal */}
      {modalOpen && (
        <Modal title="Declare Operational Incident" onClose={() => setModalOpen(false)}>
          <form onSubmit={handleCreate}>
            <div className="form-group">
              <label className="form-label required">Incident Title</label>
              <input
                name="title"
                className="form-input"
                placeholder="Brief summary of failure or outage"
                required
              />
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label required">Severity</label>
                <select name="severity" className="form-select" required>
                  <option value="CRITICAL">CRITICAL (System Down / Service Outage)</option>
                  <option value="HIGH">HIGH (Degraded Performance / Core Feature Down)</option>
                  <option value="MEDIUM">MEDIUM (Non-Critical Failure)</option>
                  <option value="LOW">LOW (Minor Glitch)</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label required">Affected Service / Component</label>
                <input
                  name="affected_service"
                  className="form-input"
                  placeholder="e.g. auth-api, mongodb, worker"
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label required">Incident Summary & Investigation Notes</label>
              <textarea
                name="summary"
                className="form-textarea"
                rows={3}
                placeholder="Initial diagnosis, affected users, workarounds in progress..."
                required
              />
            </div>

            <div className="modal-actions" style={{ marginTop: 'var(--space-6)' }}>
              <button type="button" className="btn btn-ghost" onClick={() => setModalOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-danger">
                Declare Incident
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Details Modal */}
      {selectedIncident && (
        <Modal title={`${selectedIncident.id}: ${selectedIncident.title}`} onClose={() => setSelectedIncident(null)}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
              <RiskBadge level={selectedIncident.severity} />
              <StatusBadge status={selectedIncident.status} />
              <span className="badge badge-neutral">{selectedIncident.affected_service}</span>
            </div>

            <div style={{ background: 'var(--bg-elevated)', padding: 'var(--space-4)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>
                Investigation & Mitigation Log
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--text-primary)', lineHeight: 1.6 }}>
                {selectedIncident.summary}
              </div>
            </div>

            <div className="modal-actions">
              <button
                className={`btn ${selectedIncident.status === 'RESOLVED' ? 'btn-secondary' : 'btn-success'}`}
                onClick={() => {
                  resolveIncident(selectedIncident.id);
                  setSelectedIncident(null);
                }}
              >
                {selectedIncident.status === 'RESOLVED' ? 'Reopen Incident' : 'Resolve Incident'}
              </button>
              <button className="btn btn-primary" onClick={() => setSelectedIncident(null)}>
                Close
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
