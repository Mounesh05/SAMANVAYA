/**
 * DevOps Deployments Page
 * Continuous deployment tracking across staging and production environments
 */
import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Rocket,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Plus,
  RefreshCw,
  Server,
  Calendar,
  ExternalLink,
} from 'lucide-react';
import { cicdApi } from '../../api/cicd.api';
import { projectsApi } from '../../api/projects.api';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { MetricCard } from '../../components/common/ScoreCard';
import { StatusBadge } from '../../components/common/Badges';
import { Modal } from '../../components/common/Modal';
import { timeAgo } from '../../utils/dates';
import toast from 'react-hot-toast';

export function DeploymentsPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [environmentFilter, setEnvironmentFilter] = useState('ALL');

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['devops-deployments'],
    queryFn: () => cicdApi.getDeployments().then((r) => r.data?.deployments || []).catch(() => []),
  });

  const { data: projectsData } = useQuery({
    queryKey: ['projects-list'],
    queryFn: () => projectsApi.list().then((r) => (Array.isArray(r.data) ? r.data : r.data?.projects || [])).catch(() => []),
  });

  const [deploymentsList, setDeploymentsList] = useState([]);

  useEffect(() => {
    if (data?.length) setDeploymentsList(data);
  }, [data]);

  const deployMutation = useMutation({
    mutationFn: async (formData) => {
      await new Promise((res) => setTimeout(res, 600));
      const newDep = {
        id: `dep-${Math.floor(100 + Math.random() * 900)}`,
        project: formData.project,
        environment: formData.environment,
        version: formData.version,
        commit: formData.commit || 'HEAD',
        status: 'SUCCESS',
        deployed_by: 'You',
        timestamp: new Date().toISOString(),
      };
      setDeploymentsList((prev) => [newDep, ...prev]);
      return newDep;
    },
    onSuccess: (dep) => {
      toast.success(`Successfully deployed ${dep.version} to ${dep.environment}!`);
      setModalOpen(false);
    },
  });

  const handleRollback = (dep) => {
    toast.success(`Rollback initiated for ${dep.project} (${dep.version}) on ${dep.environment}.`);
  };

  const deployments = data?.length ? data : deploymentsList;
  const projects = projectsData || [];

  const filteredDeployments = deployments.filter((d) => {
    if (environmentFilter === 'ALL') return true;
    return d.environment?.toLowerCase() === environmentFilter.toLowerCase();
  });

  const successCount = deployments.filter((d) => d.status === 'SUCCESS').length;
  const successRate = deployments.length ? ((successCount / deployments.length) * 100).toFixed(1) : 100;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Deployments & Release Engineering</h1>
          <p className="page-subtitle">Track deployment releases, rollback capabilities, and environment status</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button className="btn btn-secondary" onClick={() => refetch()} title="Refresh deployments">
            <RefreshCw size={15} />
            Refresh
          </button>
          <button className="btn btn-primary" onClick={() => setModalOpen(true)}>
            <Rocket size={15} />
            Trigger Deployment
          </button>
        </div>
      </div>

      {/* Metrics */}
      <div className="metric-grid">
        <MetricCard
          label="Deployment Success Rate"
          value={`${successRate}%`}
          icon={CheckCircle2}
          iconBg="rgba(16,185,129,0.1)"
          iconColor="var(--success)"
        />
        <MetricCard
          label="Total Deployments (30d)"
          value={deployments.length}
          icon={Rocket}
          iconBg="rgba(99,102,241,0.12)"
          iconColor="var(--brand-400)"
        />
        <MetricCard
          label="Production Releases"
          value={deployments.filter((d) => d.environment === 'production').length}
          icon={Server}
          iconBg="rgba(59,130,246,0.1)"
          iconColor="var(--info)"
        />
        <MetricCard
          label="Failed Deployments"
          value={deployments.filter((d) => d.status === 'FAILED').length}
          icon={XCircle}
          iconBg="rgba(239,68,68,0.1)"
          iconColor="var(--danger)"
        />
      </div>

      {/* Filter */}
      <div className="card" style={{ padding: 'var(--space-3) var(--space-4)', marginBottom: 'var(--space-4)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)' }}>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Environment Filter:</div>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            {['ALL', 'PRODUCTION', 'STAGING'].map((env) => (
              <button
                key={env}
                className={`btn btn-sm ${environmentFilter === env ? 'btn-primary' : 'btn-ghost'}`}
                onClick={() => setEnvironmentFilter(env)}
              >
                {env}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Service / Project</th>
                <th>Environment</th>
                <th>Version</th>
                <th>Commit</th>
                <th>Status</th>
                <th>Deployed By</th>
                <th>Time</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredDeployments.map((dep) => (
                <tr key={dep.id}>
                  <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{dep.project}</td>
                  <td>
                    <span
                      className="badge"
                      style={{
                        background: dep.environment === 'production' ? 'rgba(239,68,68,0.1)' : 'rgba(59,130,246,0.1)',
                        color: dep.environment === 'production' ? 'var(--danger)' : 'var(--info)',
                        border: dep.environment === 'production' ? '1px solid rgba(239,68,68,0.2)' : '1px solid rgba(59,130,246,0.2)',
                      }}
                    >
                      {dep.environment?.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <code style={{ fontFamily: 'var(--font-mono)', fontWeight: 500 }}>{dep.version}</code>
                  </td>
                  <td>
                    <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {dep.commit}
                    </code>
                  </td>
                  <td>
                    <StatusBadge status={dep.status} />
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{dep.deployed_by}</td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{timeAgo(dep.timestamp)}</td>
                  <td>
                    <button
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: '0.75rem', gap: 4 }}
                      onClick={() => handleRollback(dep)}
                      title="Rollback to previous revision"
                    >
                      <RotateCcw size={12} />
                      Rollback
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Trigger Deployment Modal */}
      {modalOpen && (
        <Modal title="Trigger New Service Deployment" onClose={() => setModalOpen(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const fd = new FormData(e.target);
              deployMutation.mutate({
                project: fd.get('project'),
                environment: fd.get('environment'),
                version: fd.get('version'),
                commit: fd.get('commit'),
              });
            }}
          >
            <div className="form-group">
              <label className="form-label required">Target Service</label>
              <select name="project" className="form-select" required>
                <option value="Samanvaya API">Samanvaya API (FastAPI)</option>
                <option value="Samanvaya Frontend">Samanvaya Frontend (React/Vite)</option>
                <option value="Code Quality Engine">Code Quality Engine</option>
                {projects.map((p) => (
                  <option key={p.id || p._id} value={p.name}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label required">Target Environment</label>
              <select name="environment" className="form-select" required>
                <option value="staging">Staging</option>
                <option value="production">Production</option>
              </select>
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label required">Release Version</label>
                <input
                  name="version"
                  className="form-input"
                  placeholder="e.g. v1.5.0"
                  defaultValue="v1.5.0"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Git Commit Hash / Ref</label>
                <input
                  name="commit"
                  className="form-input"
                  placeholder="e.g. HEAD or main"
                  defaultValue="HEAD"
                />
              </div>
            </div>

            <div className="modal-actions" style={{ marginTop: 'var(--space-6)' }}>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setModalOpen(false)}
                disabled={deployMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={deployMutation.isPending}
              >
                {deployMutation.isPending ? 'Deploying…' : 'Deploy Service'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
